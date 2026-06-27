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
from backend import params
from backend import planner
from backend import protocol as P
from backend.logging_config import get_logger

log = get_logger("player")


# Detected tempo is ~constant within a song so sets only a cross-song baseline; the
# live "drive" supplies within-song movement and lets speed reach the whole range:
#     sp = SPEED_MIN + (SPEED_MAX-SPEED_MIN) · clip(TEMPO_W·tempo01 + DRIVE_W·drive, 0, 1)
SPEED_MIN, SPEED_MAX = 5, 100
TEMPO_W, DRIVE_W = 0.3, 0.9


def _rgb(color_code):
    """Resolve a colour code to an (r, g, b) tuple via the hex palette."""
    hex_str = M.COLOR_HEX.get(color_code, "#ffffff").lstrip("#")
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)


def _clamp(v, lo, hi):
    """Clamp v into the inclusive [lo, hi] range."""
    return lo if v < lo else hi if v > hi else v


class PlayerEngine:
    def __init__(self, controller, engine):
        """Wire the player to its strip controller and the shared mic engine."""
        self.c = controller
        self.engine = engine            # shares cfg, active_families, catalog
        self.catalog = engine.catalog
        self.track = None
        self.tl = None
        self._loading = False
        self._loading_task = None
        self._reset_runtime()

    def _reset_runtime(self):
        """Reset all per-track playback/runtime state to defaults."""
        self.pos = 0.0
        self.playing = False
        self.beat_count = 0
        self._last_switch_beat = 0
        self._fam_idx = -1
        self.cur_mode = None
        self.cur_family = None
        self.color_code = "RD"          # actual colour the strip is showing
        self.music_color = "RD"         # colour the music suggests
        self.dir_forward = True
        self.brightness_val = 0
        self.speed_val = 0
        self.centroid = 0.0
        self.bpm_local = 0.0
        self.drive = 0.0
        self.mood = 0
        self.spectrum = []
        self.beat_flash = 0.0
        self._strobe_on = False
        self._dev_bright = -999
        self._dev_speed = -999
        self._tokens = 0.0
        self._token_t = -999.0
        self._last_t = -999.0
        self._prev_playing = False
        self.plan = None
        self._plan_key = None
        self._plan_t0 = []
        self._seg_idx = -1

    @property
    def loaded(self) -> bool:
        """True once a track timeline has been loaded."""
        return self.tl is not None

    def load(self, track: dict, timeline: dict):
        """Load a track + its analysed timeline and reset runtime state."""
        self.track = track
        self.tl = timeline
        self._reset_runtime()
        log.info("loaded '%s' — %ss, %s BPM, %s beats",
                 (track or {}).get("title", "?"), timeline.get("duration"),
                 timeline.get("bpm"), len(timeline.get("beats", [])))

    def _frame_at(self, t):
        """Return the clamped timeline frame index for playback time t."""
        frame_count = len(self.tl["bright"])
        i = int(t / self.tl["dt"])
        return _clamp(i, 0, frame_count - 1)

    # ----- precomputed mode plan (followed by tick, drawn by the UI) -----
    def ensure_plan(self):
        """Rebuild the mode plan if the config/timeline changed; return it."""
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
        """Return the plan segment index active at time t, or -1 if none."""
        if not self._plan_t0:
            return -1
        return max(0, bisect.bisect_right(self._plan_t0, t) - 1)

    def signals(self, n=2200):
        """Downsampled full-song brightness + colour arrays for the timeline view.
        Sampled densely (~8/s) so the graph tracks the per-frame brightness and the
        per-frame strobe colour closely — a truthful representation of what's sent."""
        bright, colors, dt = self.tl["bright"], self.tl["color"], self.tl["dt"]
        bpm_curve = self.tl.get("bpm_curve") or []
        cfg = self.engine.cfg
        floor_frac = (cfg["bright_floor"] / 100.0) if cfg.get("react_bright", True) else 0.0
        frame_count = len(bright)
        step = max(1, frame_count // n)
        indices = range(0, frame_count, step)
        return {
            "sig_t": [round(i * dt, 2) for i in indices],
            "level": [round(floor_frac + bright[i] * (1 - floor_frac), 3) for i in indices],
            "scolor": [M.FREQ_COLORS[colors[i]] for i in indices],
            "bpm_curve": [bpm_curve[i] for i in indices] if bpm_curve else [],
            "bright_floor": cfg["bright_floor"],
            "freq_colors": M.FREQ_COLORS,
        }

    # ----- driven by the browser audio clock -----
    async def tick(self, t: float, playing: bool):
        """Advance to audio time t and send the due light commands for this frame."""
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
        self.bpm_local = self.tl["bpm_curve"][i] if self.tl.get("bpm_curve") else self.tl["bpm"]
        self.drive = self.tl["drive"][i] if self.tl.get("drive") else 0.0
        self.spectrum = self.tl.get("spec", [[]])[i] if self.tl.get("spec") else []

        beats = self.tl["beats"]
        beat_count = bisect.bisect_right(beats, t)
        self.beat_count = beat_count
        self.beat_flash = 1.0 if (beat_count > 0 and t - beats[beat_count - 1] < 0.12) else self.beat_flash * 0.6

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
            if just_paused:
                await self._safe(self.c.send(P.color(*_rgb(self.color_code)), critical=True))
            return

        segment = None
        if cfg["switch_modes"] and self.plan and self.plan["segments"]:
            seg_idx = self._seg_at(t)
            segment = self.plan["segments"][seg_idx]
        is_strobe = bool(segment and segment.get("kind") == "strobe")

        want_bright = None
        if cfg["react_bright"]:
            want_bright = int(cfg["bright_floor"] + bright01 * (100 - cfg["bright_floor"]))
            self.brightness_val = want_bright

        # strobe sent CRITICAL every tick so the on-frame can never be dropped (the old
        # "stuck dark" bug); no speed commands during a strobe.
        if is_strobe:
            if seg_idx != self._seg_idx:
                self._seg_idx = seg_idx
                self.cur_mode, self.cur_family = None, "Colour Strobe"
                bright_level = want_bright if want_bright is not None else 90
                self._dev_bright = bright_level
                await self._safe(self.c.send(P.brightness(bright_level), critical=True))
            self._strobe_on = not self._strobe_on
            self.color_code = self.music_color
            rgb = _rgb(self.music_color) if self._strobe_on else (0, 0, 0)
            await self._safe(self.c.send(P.color(*rgb), critical=True))
            return

        want_speed = None
        if cfg["react_speed"] and self.bpm_local > 0:
            tempo01 = _clamp((self.bpm_local - params.get("speed_bpm_lo")) / params.get("speed_span"), 0.0, 1.0)
            pace = _clamp(TEMPO_W * tempo01 + DRIVE_W * self.drive, 0.0, 1.0)
            want_speed = int(round(SPEED_MIN + (SPEED_MAX - SPEED_MIN) * pace))
            self.speed_val = want_speed

        if segment is not None and seg_idx != self._seg_idx:
            self._seg_idx = seg_idx
            self.cur_mode, self.cur_family, self.color_code = segment["mode"], segment["family"], segment["color"]
            await self._safe(self.c.send(P.mode(segment["mode"]), critical=True))

        # at most ONE non-critical command per tick (bursting gets dropped by the rate
        # limiter), spent on whichever of brightness/speed has drifted furthest.
        rate = max(2.0, float(self.c.max_rate))
        self._tokens = min(self._tokens + max(0.0, t - self._token_t) * rate, 1.0)
        self._token_t = t
        if self._tokens >= 1.0:
            pending = []
            if want_bright is not None and abs(want_bright - self._dev_bright) >= 3:
                pending.append((abs(want_bright - self._dev_bright), P.brightness(want_bright), "bright", want_bright))
            if want_speed is not None and abs(want_speed - self._dev_speed) >= 3:
                pending.append((abs(want_speed - self._dev_speed), P.speed(want_speed), "speed", want_speed))
            if pending:
                _, payload, kind, val = max(pending, key=lambda c: c[0])
                self._tokens -= 1.0
                await self._safe(self.c.send(payload, critical=False))
                if kind == "bright":
                    self._dev_bright = val
                else:
                    self._dev_speed = val

    async def stop(self):
        """Halt playback and cancel any loading animation."""
        self.playing = False
        self._prev_playing = False
        self.stop_loading()

    # ----- "loading" light: a gentle breathing pulse while a track preprocesses -----
    def start_loading(self):
        """Start the breathing 'loading' pulse animation on the strip."""
        self.stop_loading()
        self._loading = True
        self._loading_task = asyncio.create_task(self._loading_pulse())

    def stop_loading(self):
        """Stop the loading pulse animation and cancel its task."""
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
                brightness = int(12 + 40 * (0.5 - 0.5 * math.cos(2 * math.pi * phase)))
                await self._safe(self.c.send(P.brightness(brightness), critical=False))
                i += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    @staticmethod
    async def _safe(coro):
        """Await coro, swallowing any exception (best-effort strip send)."""
        try:
            await coro
        except Exception:
            pass

    def state(self) -> dict:
        """Return the serialisable player state snapshot for the UI."""
        return {
            "loaded": self.loaded,
            "playing": self.playing,
            "pos": round(self.pos, 2),
            "track": self.track,
            "duration": self.tl["duration"] if self.loaded else 0,
            "bpm": round(self.bpm_local, 1) if self.loaded else 0,
            "beats": self.beat_count,
            "beat_flash": round(self.beat_flash, 3),
            "brightness": self.brightness_val,
            "speed": self.speed_val,
            "centroid": round(self.centroid, 3),
            "color": self.color_code,           # actual colour the strip shows
            "music_color": self.music_color,    # colour the music suggests
            "family": self.cur_family,
            "mode": self.cur_mode,
            "direction": "fwd" if self.dir_forward else "bwd",
            "mood": M.MOOD_NAMES[self.mood] if self.loaded else None,
            "spectrum": self.spectrum,
            "loading": self._loading,
        }
