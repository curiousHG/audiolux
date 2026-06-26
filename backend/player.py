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

from . import modes as M
from . import protocol as P


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
        self._was_strobing = False
        self._last_bright = -1
        self._last_speed = -1
        self._last_t = -999.0
        self._prev_playing = False

    @property
    def loaded(self) -> bool:
        return self.tl is not None

    def load(self, track: dict, timeline: dict):
        self.track = track
        self.tl = timeline
        self._reset_runtime()

    def _frame_at(self, t):
        n = len(self.tl["bright"])
        i = int(t / self.tl["dt"])
        return _clamp(i, 0, n - 1)

    # ----- driven by the browser audio clock -----
    async def tick(self, t: float, playing: bool):
        if not self.loaded:
            return
        seek = abs(t - self._last_t) > 1.0          # a jump = the user scrubbed
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
        if seek:
            self._last_switch_beat = bc             # don't fire a burst after scrubbing

        # power on + take over from the loading animation the moment playback starts
        if playing and not self._prev_playing:
            self.stop_loading()
            await self._safe(self.c.send(P.power(True), critical=True))
        self._prev_playing = playing
        self.playing = playing
        self.pos, self._last_t = t, t
        if not playing:
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

        # PEAK: build our own COLOURED strobe by flashing solid colours in the live
        # music colour — punchy like the white Strobe mode, but it keeps the colour.
        if cfg.get("auto_family") and cfg.get("peak_strobe", True) and self.mood == 3:
            self._strobe_on = not self._strobe_on
            self._was_strobing = True
            self.cur_family, self.cur_mode = "Colour Strobe", None
            self.color_code = self.music_color
            rgb = _rgb(self.music_color) if self._strobe_on else (0, 0, 0)
            await self._safe(self.c.send(P.color(*rgb), critical=False))
            return
        if self._was_strobing:                    # leaving peak -> re-establish an effect mode
            self._was_strobing = False
            self._last_switch_beat = -10 ** 9

        if cfg["switch_modes"] and bc - self._last_switch_beat >= cfg["beats_per_switch"]:
            if cfg.get("auto_family"):
                fam = M.mood_family(self.catalog, self.mood, self.music_color)
            else:
                fams = [f for f in self.engine.active_families if f in self.catalog]
                fam = None
                if fams:
                    self._fam_idx = (self._fam_idx + 1) % len(fams)
                    fam = fams[self._fam_idx]
            if fam:
                self._last_switch_beat = bc
                n, label = M.resolve_mode(self.catalog, fam, self.music_color,
                                          self.dir_forward, cfg["use_direction"])
                if n:
                    self.cur_mode, self.cur_family = n, fam
                    self.color_code = M.label_color(label) or self.music_color
                    await self._safe(self.c.send(P.mode(n), critical=True))

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
