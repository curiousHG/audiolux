"""Track player engine — drives the strip from a precomputed timeline, clocked by
the browser's <audio> element.

The browser plays the downloaded audio and reports `currentTime` via ticks; this
engine looks up the matching timeline frame and sends light commands. It reuses the
mic engine's controls (cfg + selected families + pick_mode), so the same UI knobs
apply whether the source is the mic or a track. No audio is captured here — the
lights follow the song's own analysed samples, so room/fan noise is irrelevant.
"""
import bisect

from . import modes as M
from . import protocol as P


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class PlayerEngine:
    def __init__(self, controller, engine):
        self.c = controller
        self.engine = engine            # shares cfg, active_families, catalog
        self.catalog = engine.catalog
        self.track = None               # {id,title,uploader,duration}
        self.tl = None                  # analysed timeline dict
        self._reset_runtime()

    def _reset_runtime(self):
        self.pos = 0.0
        self.playing = False
        self.beat_count = 0
        self._last_switch_beat = 0
        self._fam_idx = -1
        self.cur_mode = None
        self.cur_family = None
        self.color_code = "RD"
        self.dir_forward = True
        self.brightness_val = 0
        self.speed_val = 0
        self.centroid = 0.0
        self.beat_flash = 0.0
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
        self.color_code = M.FREQ_COLORS[self.tl["color"][i]]
        self.centroid = self.tl["centroid"][i]
        self.dir_forward = bool(self.tl["dir"][i])

        beats = self.tl["beats"]
        bc = bisect.bisect_right(beats, t)
        self.beat_count = bc
        self.beat_flash = 1.0 if (bc > 0 and t - beats[bc - 1] < 0.12) else self.beat_flash * 0.6
        if seek:
            self._last_switch_beat = bc             # don't fire a burst after scrubbing

        # power on the moment playback (re)starts
        if playing and not self._prev_playing:
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

        if cfg["switch_modes"]:
            fams = [f for f in self.engine.active_families if f in self.catalog]
            if fams and bc - self._last_switch_beat >= cfg["beats_per_switch"]:
                self._last_switch_beat = bc
                self._fam_idx = (self._fam_idx + 1) % len(fams)
                fam = fams[self._fam_idx]
                n = M.pick_mode(self.catalog, fam, self.color_code,
                                self.dir_forward, cfg["use_direction"])
                if n:
                    self.cur_mode, self.cur_family = n, fam
                    await self._safe(self.c.send(P.mode(n), critical=True))

    async def stop(self):
        self.playing = False
        self._prev_playing = False

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
            "color": self.color_code,
            "family": self.cur_family,
            "mode": self.cur_mode,
            "direction": "fwd" if self.dir_forward else "bwd",
        }
