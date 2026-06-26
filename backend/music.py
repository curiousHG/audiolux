"""Music engine: analyse the mic and drive the strip's EFFECT MODES, SPEED and
BRIGHTNESS in real time.

Mappings (validated against DSP/MIR literature):
  - loudness (perceptual dB) -> brightness
  - tempo (BPM, octave-folded) -> animation speed
  - beats (power-energy, variance-adaptive threshold) -> switch effect
  - dominant frequency BAND-NOVELTY -> colour variant within the chosen family
  - energy build/release -> effect direction (forward/backward)

Audio analysis runs in sounddevice's callback thread; an asyncio "director" task
reads the shared state and sends BLE commands at a controlled rate.
"""
import asyncio
import threading
import time

import numpy as np

from backend import modes as M
from backend import protocol as P
from backend.logging_config import get_logger

log = get_logger("mic")


class MusicEngine:
    SR = 44100
    BLOCK = 1024
    DB_FLOOR = -50.0          # dB window for perceptual loudness -> brightness
    NOISE_GATE = 1.5e-4       # RMS below this = treat as silence

    def __init__(self, controller, catalog):
        self.c = controller
        self.catalog = catalog
        self.active_families = [f for f in ("Run", "Trailing") if f in catalog] or list(catalog)[:1]
        self.running = False
        self.stream = None
        self._task = None
        self.lock = threading.Lock()

        self.cfg = {
            "react_bright": True,
            "react_speed": True,
            "switch_modes": True,
            "use_direction": True,
            "sensitivity": 1.5,       # base beat threshold C (variance lowers it)
            "beats_per_switch": 4,
            "bright_floor": 12,
            "smooth": 0.4,
            "auto_family": False,     # track player: pick family by music character (mood)
            "peak_strobe": True,      # track player: coloured solid-colour strobe on peaks
        }

        # --- beat-detection FFT: short window = good TIME resolution ---
        self.window = np.hanning(self.BLOCK)
        self.freqs = np.fft.rfftfreq(self.BLOCK, 1 / self.SR)
        self.bass = (self.freqs >= 40) & (self.freqs <= 150)   # kick band
        self.energy_hist: list[float] = []
        self.loudness = 0.0        # perceptual 0..1 (drives brightness)
        self.env_slow = 0.0
        self.envpeak = 1e-6
        self.dir_forward = True
        self.dir_committed = True
        self.beat_count = 0
        self.last_beat_t = 0.0
        self.beat_times: list[float] = []
        self.bpm = 0.0
        self.beat_flash = 0.0
        self.cur_C = self.cfg["sensitivity"]

        # --- spectrum FFT: long rolling window = good FREQUENCY resolution ---
        self.NFFT = 4096
        self._ring = np.zeros(self.NFFT, dtype=np.float32)
        self.window_spec = np.hanning(self.NFFT)
        self.freqs_spec = np.fft.rfftfreq(self.NFFT, 1 / self.SR)

        cedges = np.logspace(np.log10(40), np.log10(min(12000, self.SR / 2)), 7)
        self.color_energy = np.zeros(6)
        self.color_code = "RD"
        self.band_avg = np.zeros(6)      # slow per-band baseline (for novelty/whitening)
        self.centroid = 0.0              # spectral centroid, normalised 0..1

        self.NBARS = 40
        ehz = np.logspace(np.log10(30), np.log10(min(16000, self.SR / 2)), self.NBARS + 1)
        sidx = np.searchsorted(self.freqs_spec, ehz)
        self.barbins = list(zip(sidx[:-1].tolist(), sidx[1:].tolist()))
        self.bar_center = np.sqrt(ehz[:-1] * ehz[1:])
        self.specsmooth = np.zeros(self.NBARS)
        self.specpeak = 1e-6
        self.spectrum = [0.0] * self.NBARS
        self.bar_band = [int(np.clip(np.searchsorted(cedges, fc) - 1, 0, 5)) for fc in self.bar_center]
        self.bar_colors = [M.COLOR_HEX[M.FREQ_COLORS[b]] for b in self.bar_band]
        self.bar_band_count = np.array([max(1, self.bar_band.count(b)) for b in range(6)])
        self._logf_lo, self._logf_hi = np.log10(30), np.log10(16000)

        # director bookkeeping
        self._fam_idx = -1
        self.cur_mode = None
        self.cur_family = None
        self.brightness_val = 0
        self.speed_val = 0
        self._last_switch_beat = 0
        self._last_switch_t = 0.0
        self._last_bright = -1
        self._last_bright_t = 0.0
        self._last_speed = -1
        self._last_speed_t = 0.0

    # ----- lifecycle -----
    def start(self, loop):
        if self.running:
            return
        import sounddevice as sd
        # Open the mic FIRST — only flip `running` once it actually succeeds, so a
        # failed open can't leave the engine poisoned (on=True with no stream).
        self.stream = self._open_input(sd)
        self.running = True
        self._task = loop.create_task(self._director())
        log.info("mic engine started (families=%s)", self.active_families)

    def _open_input(self, sd):
        """Open + start the input stream, retrying once through a full PortAudio
        reset. On macOS, CoreAudio occasionally wedges when a long-lived process
        re-acquires the mic (PaError -9986); terminate/initialize clears it."""
        def _mk():
            s = sd.InputStream(channels=1, samplerate=self.SR,
                               blocksize=self.BLOCK, callback=self._audio_cb)
            s.start()
            return s
        try:
            return _mk()
        except Exception:
            try:
                sd._terminate(); sd._initialize()
            except Exception:
                pass
            return _mk()

    async def stop(self):
        was = self.running
        self.running = False
        if self._task:
            self._task.cancel(); self._task = None
        if self.stream:
            try:
                self.stream.stop(); self.stream.close()
            except Exception:
                pass
            self.stream = None
        if was:
            log.info("mic engine stopped")

    def configure(self, **kw):
        with self.lock:
            for k, v in kw.items():
                if v is not None and k in self.cfg:
                    self.cfg[k] = v

    def set_families(self, fams):
        fams = [f for f in fams if f in self.catalog]
        with self.lock:
            if fams:
                self.active_families = fams
                self._fam_idx = -1

    # ----- audio analysis (sounddevice thread) -----
    def _audio_cb(self, indata, frames, tinfo, status):
        x = indata[:, 0].astype(np.float32)
        now = time.monotonic()

        # --- perceptual loudness (RMS -> dB window) with AGC + noise gate ---
        rms = float(np.sqrt(np.mean(x * x)) + 1e-12)
        self.envpeak = max(rms, self.envpeak * 0.992)        # instant attack, ~3 s release
        if rms < self.NOISE_GATE:
            target = 0.0
        else:
            db = 20 * np.log10(rms / (self.envpeak + 1e-12) + 1e-12)   # <= 0 dB
            target = float(np.clip((db - self.DB_FLOOR) / (0 - self.DB_FLOOR), 0, 1))
        a = self.cfg["smooth"]
        self.loudness = (1 - a) * self.loudness + a * target

        # build/release (with absolute floor so silence doesn't flip it)
        self.env_slow = 0.98 * self.env_slow + 0.02 * self.loudness
        if self.loudness > 0.05:
            if self.loudness > self.env_slow * 1.05:
                self.dir_forward = True
            elif self.loudness < self.env_slow * 0.95:
                self.dir_forward = False

        # --- spectrum: long rolling FFT, gap-free log bars ---
        self._ring[:-self.BLOCK] = self._ring[self.BLOCK:]
        self._ring[-self.BLOCK:] = x
        spec = np.abs(np.fft.rfft(self._ring * self.window_spec))
        bars = np.empty(self.NBARS)
        for i, (s, e) in enumerate(self.barbins):
            bars[i] = spec[s:e].mean() if e > s else np.interp(self.bar_center[i], self.freqs_spec, spec)
        self.specpeak = max(float(bars.max()), self.specpeak * 0.99, 1e-6)
        self.specsmooth = 0.6 * self.specsmooth + 0.4 * np.clip(bars / self.specpeak, 0, 1)
        self.spectrum = [round(float(v), 3) for v in self.specsmooth]

        # spectral centroid (log axis) -> 0..1 (the standard "brightness" feature)
        w = self.specsmooth
        cen_hz = float((self.bar_center * w).sum() / (w.sum() + 1e-9))
        self.centroid = float(np.clip((np.log10(max(cen_hz, 30)) - self._logf_lo) /
                                      (self._logf_hi - self._logf_lo), 0, 1))

        # dominant colour via per-band NOVELTY (whitening) so it isn't stuck on bass
        band_e = np.zeros(6)
        for i, bi in enumerate(self.bar_band):
            band_e[bi] += self.specsmooth[i]
        band_e /= self.bar_band_count
        self.band_avg = 0.98 * self.band_avg + 0.02 * band_e
        novelty = np.maximum(0.0, band_e - self.band_avg)        # bands above their own baseline
        self.color_energy = 0.6 * self.color_energy + 0.4 * novelty
        if self.color_energy.max() > 1e-4:                       # else hold last colour (steady passage)
            self.color_code = M.FREQ_COLORS[int(np.argmax(self.color_energy))]

        # --- beat detection: bass POWER energy, variance-adaptive threshold ---
        spec_beat = np.abs(np.fft.rfft(x * self.window))
        be = float(np.sum(spec_beat[self.bass] ** 2))            # power, not magnitude
        self.energy_hist.append(be)
        if len(self.energy_hist) > 43:
            self.energy_hist.pop(0)
        arr = np.array(self.energy_hist)
        m = float(arr.mean())
        cv = float(arr.std() / (m + 1e-12))                     # coefficient of variation
        C = float(np.clip(self.cfg["sensitivity"] - 0.6 * min(cv, 1.0), 1.1, 2.6))
        self.cur_C = C
        self.beat_flash *= 0.85
        if m > 0 and be > m * C and (now - self.last_beat_t) > 0.25:
            self.last_beat_t = now
            self.beat_flash = 1.0
            with self.lock:
                self.beat_count += 1
                self.beat_times.append(now)
                if len(self.beat_times) > 16:                   # ~ standard integration window
                    self.beat_times.pop(0)
                if len(self.beat_times) >= 4:
                    diffs = [t2 - t1 for t1, t2 in zip(self.beat_times, self.beat_times[1:])]
                    diffs = [d for d in diffs if 0.25 < d < 1.5]
                    if diffs:
                        bpm = 60.0 / sorted(diffs)[len(diffs) // 2]
                        while bpm < 76:    bpm *= 2              # octave-fold toward ~120
                        while bpm >= 152:  bpm /= 2
                        self.bpm = 0.6 * self.bpm + 0.4 * bpm if self.bpm else bpm

    # pick a mode number in `fam` for the current colour + direction
    def _pick(self, fam):
        return M.pick_mode(self.catalog, fam, self.color_code,
                           forward=self.dir_forward, use_direction=self.cfg["use_direction"])

    # ----- director (asyncio loop) -----
    async def _director(self):
        try:
            await self.c.send(P.power(True), critical=True)
            while self.running:
                cfg = dict(self.cfg)
                now = time.monotonic()

                if cfg["react_bright"]:
                    b = int(cfg["bright_floor"] + self.loudness * (100 - cfg["bright_floor"]))
                    self.brightness_val = b
                    if abs(b - self._last_bright) >= 5 and (now - self._last_bright_t) > 0.1:
                        self._last_bright, self._last_bright_t = b, now
                        await self._safe(self.c.send(P.brightness(b), critical=False))

                if cfg["react_speed"] and self.bpm > 0:
                    sp = int(np.clip(np.interp(self.bpm, [70, 160], [25, 100]), 5, 100))
                    self.speed_val = sp
                    if abs(sp - self._last_speed) >= 5 and (now - self._last_speed_t) > 1.0:
                        self._last_speed, self._last_speed_t = sp, now
                        await self._safe(self.c.send(P.speed(sp), critical=False))

                if cfg["switch_modes"]:
                    with self.lock:
                        bc = self.beat_count
                        fams = [f for f in self.active_families if f in self.catalog]
                    if fams and bc - self._last_switch_beat >= cfg["beats_per_switch"] \
                            and (now - self._last_switch_t) > 0.8:
                        self._last_switch_beat, self._last_switch_t = bc, now
                        self._fam_idx = (self._fam_idx + 1) % len(fams)
                        fam = fams[self._fam_idx]
                        n = self._pick(fam)
                        if n:
                            self.cur_mode, self.cur_family = n, fam
                            self.dir_committed = self.dir_forward
                            await self._safe(self.c.send(P.mode(n), critical=True))

                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    @staticmethod
    async def _safe(coro):
        try:
            await coro
        except Exception:
            pass

    def state(self):
        with self.lock:
            return {
                "on": self.running,
                "bpm": round(self.bpm, 1),
                "beats": self.beat_count,
                "beat_flash": round(self.beat_flash, 3),
                "loudness": round(self.loudness, 3),
                "brightness": self.brightness_val,
                "speed": self.speed_val,
                "centroid": round(self.centroid, 3),
                "spectrum": self.spectrum,
                "mode": self.cur_mode,
                "family": self.cur_family,
                "color": self.color_code,
                "music_color": self.color_code,
                "direction": "fwd" if self.dir_committed else "bwd",
                "C": round(self.cur_C, 2),
                "active_families": list(self.active_families),
                "cfg": dict(self.cfg),
            }
