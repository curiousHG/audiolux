"""Offline audio analysis (librosa) -> a light-control timeline.

Computes the SAME musical features the live mic engine derives, but over the whole
file at once (so beat tracking has global context and we get look-ahead):

  - perceptual loudness (RMS -> dB, normalised to the track's own 95th pct) -> brightness
  - 6 log-band energy -> per-band novelty (whitening) -> dominant colour code
  - spectral centroid (log) -> 0..1 telemetry line
  - build vs release of loudness -> effect direction
  - librosa global beat grid + BPM -> when to switch effect modes

Output is a compact, JSON-serialisable dict with columnar arrays sampled at a fixed
frame rate, plus the beat timestamps. Cached to disk so re-loads skip re-analysis.
"""
import numpy as np
import librosa

SR = 22050
NFFT = 2048
HOP = 1024                 # ~21.5 fps at 22050 Hz — plenty for smooth light control
DB_FLOOR = -45.0           # dB below the track's 95th-pct level = brightness 0


def _ema(x, a):
    out = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * acc + a * v
        out[i] = acc
    return out


def _smooth(x, w):
    if w <= 1:
        return x
    k = np.ones(w) / w
    return np.convolve(x, k, mode="same")


def _color_track(bands_norm):
    """Per-band novelty colour, frame by frame — mirrors the mic engine so the
    player and live modes choose colours the same way. Holds the last colour through
    steady passages (low novelty)."""
    n_bands, T = bands_norm.shape
    baseline = np.zeros(n_bands)
    ce = np.zeros(n_bands)
    out = np.zeros(T, dtype=np.int16)
    cur = 0
    for t in range(T):
        e = bands_norm[:, t]
        baseline = 0.98 * baseline + 0.02 * e
        nov = np.maximum(0.0, e - baseline)
        ce = 0.6 * ce + 0.4 * nov
        if ce.max() > 1e-3:
            cur = int(np.argmax(ce))
        out[t] = cur
    return out


def _direction_track(bright, slow):
    """Commit forward on a build, backward on a release; hold otherwise."""
    T = len(bright)
    out = np.ones(T, dtype=np.int8)
    d = 1
    for t in range(T):
        if bright[t] > 0.05:
            if bright[t] > slow[t] * 1.05:
                d = 1
            elif bright[t] < slow[t] * 0.95:
                d = 0
        out[t] = d
    return out


def analyze(path: str) -> dict:
    y, sr = librosa.load(path, sr=SR, mono=True)
    duration = len(y) / sr

    S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP))     # (1+NFFT/2, T)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=NFFT)
    T = S.shape[1]

    # --- brightness: perceptual dB from RMS, normalised to the song's own loud level ---
    rms = librosa.feature.rms(S=S, frame_length=NFFT, hop_length=HOP)[0]
    ref = float(np.percentile(rms, 95)) + 1e-9
    db = 20.0 * np.log10(rms / ref + 1e-9)
    bright = np.clip((db - DB_FLOOR) / (0.0 - DB_FLOOR), 0.0, 1.0)
    bright = _smooth(bright, 5)

    # --- colour: 6 log bands -> per-band novelty -> dominant band ---
    cedges = np.logspace(np.log10(40), np.log10(min(12000, sr / 2)), 7)
    band_rows = [np.where((freqs >= cedges[i]) & (freqs < cedges[i + 1]))[0] for i in range(6)]
    bands = np.stack([S[rows].sum(axis=0) if len(rows) else np.zeros(T) for rows in band_rows])
    bands_norm = bands / (bands.max(axis=1, keepdims=True) + 1e-9)
    color_idx = _color_track(bands_norm)

    # --- spectral centroid (log) -> 0..1 ---
    cen = librosa.feature.spectral_centroid(S=S, sr=sr, freq=freqs)[0]
    lo, hi = np.log10(30), np.log10(16000)
    centroid = np.clip((np.log10(np.maximum(cen, 30)) - lo) / (hi - lo), 0.0, 1.0)

    # --- direction: build vs release ---
    slow = _ema(bright, 0.02)
    direction = _direction_track(bright, slow)

    # --- beat grid + tempo ---
    # NB: pass an explicit onset envelope — beat_track(y=...) returns 0 beats on
    # librosa 0.11 + numpy 2.x; the onset_envelope path is correct (and faster).
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr,
                                           hop_length=HOP, units="time")
    bpm = float(np.atleast_1d(tempo)[0])

    return {
        "version": 1,
        "sr": sr,
        "duration": round(float(duration), 2),
        "bpm": round(bpm, 1),
        "dt": float(HOP / sr),                       # seconds per frame
        "fps": round(sr / HOP, 2),
        "beats": [round(float(b), 3) for b in beats],
        "bright": [round(float(v), 3) for v in bright],
        "color": [int(c) for c in color_idx],
        "centroid": [round(float(v), 3) for v in centroid],
        "dir": [int(d) for d in direction],
    }


def warmup():
    """Trigger numba JIT for every librosa call analyze() uses, so the first real
    track analyses in ~1 s instead of paying ~30 s of compilation."""
    y = np.zeros(SR, dtype=np.float32)
    y[::1000] = 1.0
    S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP))
    librosa.feature.rms(S=S, frame_length=NFFT, hop_length=HOP)
    librosa.feature.spectral_centroid(S=S, sr=SR)
    oenv = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    librosa.beat.beat_track(onset_envelope=oenv, sr=SR, hop_length=HOP, units="time")
