"""Track player engine — drives the strip from a precomputed timeline, clocked by
the browser's <audio> element.

The browser plays the downloaded audio and reports `currentTime` via ticks; this
engine looks up the matching timeline frame and sends light commands. It reuses the
mic engine's controls (cfg + selected families + pick_mode), so the same UI knobs
apply whether the source is the mic or a track. No audio is captured here — the
lights follow the song's own analysed samples, so room/fan noise is irrelevant.
"""
import asyncio
import bisect
import math

from backend import modes as M
from backend import planner
from backend import protocol as P
from backend.logging_config import get_logger

log = get_logger("player")


def _rgb(color_code):
    h = M.COLOR_HEX.get(color_code, "#ffffff").lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class PlayerEngine:
    def __init__(self, controller, engine):
        self.c = controller
        self.engine = engine            # shares cfg, active_families, catalog
        self.catalog = engine.catalog
        self.track = None               # {id,title,uploader,duration}
        self.tl = None                  # analysed timeline dict
        self._loading = False
        self._loading_task = None
        self._reset_runtime()

    def _reset_runtime(self):
        self.pos = 0.0
        self.playing = False
        self.beat_count = 0
        self._last_switch_beat = 0
        self._fam_idx = -1
        self.cur_mode = None
        self.cur_family = None
        self.color_code = "RD"          # actual colour the strip is showing
        self.music_color = "RD"         # per-frame colour the music suggests
        self.dir_forward = True
        self.brightness_val = 0
        self.speed_val = 0
        self.centroid = 0.0
        self.mood = 0
        self.spectrum = []
        self.beat_flash = 0.0
        self._strobe_on = False
        self._last_bright = -1
        self._last_speed = -1
        self._last_t = -999.0
        self._prev_playing = False
        self.plan = None
        self._plan_key = None
        self._plan_t0 = []
        self._seg_idx = -1

    @property
    def loaded(self) -> bool:
        return self.tl is not None

    def load(self, track: dict, timeline: dict):
        self.track = track
        self.tl = timeline
        self._reset_runtime()
        log.info("loaded '%s' — %ss, %s BPM, %s beats",
                 (track or {}).get("title", "?"), timeline.get("duration"),
                 timeline.get("bpm"), len(timeline.get("beats", [])))

    def _frame_at(self, t):
        n = len(self.tl["bright"])
        i = int(t / self.tl["dt"])
        return _clamp(i, 0, n - 1)

    # ----- precomputed mode plan (followed by tick, drawn by the UI) -----
    def ensure_plan(self):
        if not self.loaded:
            self.plan = None
            return None
        key = planner.plan_key(self.tl, self.engine.cfg, self.engine.active_families)
        if key != self._plan_key:
            self.plan = planner.build_plan(self.catalog, self.tl, self.engine.cfg, self.engine.active_families)
            self._plan_t0 = [s["t0"] for s in self.plan["segments"]]
            self._plan_key = key
            self._seg_idx = -1                      # force re-apply on the next tick
        return self.plan

    def _seg_at(self, t):
        if not self._plan_t0:
            return -1
        return max(0, bisect.bisect_right(self._plan_t0, t) - 1)

    def signals(self, n=420):
        """Downsampled full-song brightness + colour arrays, plus the times at which
        the effect direction flips, for the timeline view."""
        bright, colors, dt = self.tl["bright"], self.tl["color"], self.tl["dt"]
        m = len(bright)
        step = max(1, m // n)
        idx = range(0, m, step)
        dirs = self.tl.get("dir") or []
        marks, last = [], None
        for i, d in enumerate(dirs):
            if d != last:
                if last is not None:                 # skip the initial state, only flips
                    marks.append({"t": round(i * dt, 2), "fwd": bool(d)})
                last = d
        return {
            "sig_t": [round(i * dt, 2) for i in idx],
            "level": [round(bright[i], 3) for i in idx],
            "scolor": [M.FREQ_COLORS[colors[i]] for i in idx],
            "dir_marks": marks,
            "freq_colors": M.FREQ_COLORS,
        }

    # ----- driven by the browser audio clock -----
    async def tick(self, t: float, playing: bool):
        if not self.loaded:
            return
        self.ensure_plan()
        cfg = self.engine.cfg
        i = self._frame_at(t)
        bright01 = self.tl["bright"][i]
        self.music_color = M.FREQ_COLORS[self.tl["color"][i]]
        self.centroid = self.tl["centroid"][i]
        self.dir_forward = bool(self.tl["dir"][i])
        self.mood = self.tl.get("mood", [0])[i] if self.tl.get("mood") else 0
        self.spectrum = self.tl.get("spec", [[]])[i] if self.tl.get("spec") else []

        beats = self.tl["beats"]
        bc = bisect.bisect_right(beats, t)
        self.beat_count = bc
        self.beat_flash = 1.0 if (bc > 0 and t - beats[bc - 1] < 0.12) else self.beat_flash * 0.6

        # power on + take over from the loading animation the moment playback starts
        if playing and not self._prev_playing:
            self.stop_loading()
            await self._safe(self.c.send(P.power(True), critical=True))
            self._seg_idx = -1                  # re-apply the current effect on resume
        just_paused = self._prev_playing and not playing
        self._prev_playing = playing
        self.playing = playing
        self.pos, self._last_t = t, t
        if not playing:
            # video paused -> freeze the strip on a static colour (it stops animating)
            if just_paused:
                await self._safe(self.c.send(P.color(*_rgb(self.color_code)), critical=True))
            return

        if cfg["react_bright"]:
            b = int(cfg["bright_floor"] + bright01 * (100 - cfg["bright_floor"]))
            self.brightness_val = b
            if abs(b - self._last_bright) >= 4:
                self._last_bright = b
                await self._safe(self.c.send(P.brightness(b), critical=False))

        if cfg["react_speed"] and self.tl["bpm"] > 0:
            sp = int(_clamp(round(25 + (self.tl["bpm"] - 70) / 90 * 75), 5, 100))
            self.speed_val = sp
            if abs(sp - self._last_speed) >= 5:
                self._last_speed = sp
                await self._safe(self.c.send(P.speed(sp), critical=False))

        # follow the precomputed plan: apply the segment covering the current time
        if not (cfg["switch_modes"] and self.plan and self.plan["segments"]):
            return
        si = self._seg_at(t)
        seg = self.plan["segments"][si]
        if seg["kind"] == "strobe":
            # coloured strobe — flash solid colours in the live music colour
            self._strobe_on = not self._strobe_on
            self.cur_family, self.cur_mode = "Colour Strobe", None
            self.color_code = self.music_color
            rgb = _rgb(self.music_color) if self._strobe_on else (0, 0, 0)
            await self._safe(self.c.send(P.color(*rgb), critical=False))
            self._seg_idx = si
        elif si != self._seg_idx:                   # entered a new mode segment (incl. after a seek)
            self._seg_idx = si
            self.cur_mode, self.cur_family, self.color_code = seg["mode"], seg["family"], seg["color"]
            await self._safe(self.c.send(P.mode(seg["mode"]), critical=True))

    async def stop(self):
        self.playing = False
        self._prev_playing = False
        self.stop_loading()

    # ----- "loading" light: a gentle breathing pulse while a track preprocesses -----
    def start_loading(self):
        self.stop_loading()
        self._loading = True
        self._loading_task = asyncio.create_task(self._loading_pulse())

    def stop_loading(self):
        self._loading = False
        if self._loading_task:
            self._loading_task.cancel()
            self._loading_task = None

    async def _loading_pulse(self):
        """Slowly breathe brightness while drifting through hues — reads as 'working'."""
        hues = ["VT", "BU", "GN", "YE", "RD"]
        try:
            await self._safe(self.c.send(P.power(True), critical=True))
            i, last_hue = 0, None
            while self._loading:
                hue = hues[(i // 24) % len(hues)]
                if hue != last_hue:
                    last_hue = hue
                    await self._safe(self.c.send(P.color(*_rgb(hue)), critical=False))
                phase = (i % 24) / 24.0
                b = int(12 + 40 * (0.5 - 0.5 * math.cos(2 * math.pi * phase)))   # breathe 12..52
                await self._safe(self.c.send(P.brightness(b), critical=False))
                i += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    @staticmethod
    async def _safe(coro):
        try:
            await coro
        except Exception:
            pass

    def state(self) -> dict:
        return {
            "loaded": self.loaded,
            "playing": self.playing,
            "pos": round(self.pos, 2),
            "track": self.track,
            "duration": self.tl["duration"] if self.loaded else 0,
            "bpm": self.tl["bpm"] if self.loaded else 0,
            "beats": self.beat_count,
            "beat_flash": round(self.beat_flash, 3),
            "brightness": self.brightness_val,
            "speed": self.speed_val,
            "centroid": round(self.centroid, 3),
            "color": self.color_code,           # actual colour the strip shows
            "music_color": self.music_color,    # per-frame colour the music suggests
            "family": self.cur_family,
            "mode": self.cur_mode,
            "direction": "fwd" if self.dir_forward else "bwd",
            "mood": M.MOOD_NAMES[self.mood] if self.loaded else None,
            "spectrum": self.spectrum,
            "loading": self._loading,
        }
