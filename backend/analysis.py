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

from backend import params

SR = 22050
NFFT = 2048
HOP = 1024                 # ~21.5 fps at 22050 Hz — plenty for smooth light control
NBARS = 40                 # spectrum bars; same log layout as the mic engine so colours align
BAR_EDGES = np.logspace(np.log10(30), np.log10(16000), NBARS + 1)
VERSION = 5                # bump when the timeline schema/algorithm changes (forces re-analysis)
DIR_GATE = 0.05            # below this brightness, direction holds (fixed)


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


def _color_track(groups, bright):
    """Dominant colour per frame from the WHITENED 6-group energy (same signal the
    spectrum draws), so the chosen colour matches the tallest visible bars. White
    is slightly de-emphasised; the colour holds through near-silence."""
    # band weights bass..treble; the top (white) band is down-weighted (tunable)
    weight = np.array([1.0, 1.0, 1.0, 0.97, 0.92, params.get("white_deemph")])
    silence = params.get("colour_silence")
    n_bands, T = groups.shape
    sm = np.zeros(n_bands)
    out = np.zeros(T, dtype=np.int16)
    cur = 0
    for t in range(T):
        if bright[t] < silence:               # near silence -> hold last colour
            out[t] = cur
            continue
        sm = 0.6 * sm + 0.4 * (groups[:, t] * weight)
        cur = int(np.argmax(sm))
        out[t] = cur
    return out


def _mood_track(bright, pfrac):
    """Classify each frame's musical character from energy + percussiveness:
    0 calm, 1 groove, 2 drive, 3 peak. Drives smart family selection."""
    peak_e, peak_p = params.get("mood_peak_e"), params.get("mood_peak_p")
    drive_e, groove_e = params.get("mood_drive_e"), params.get("mood_groove_e")
    T = len(bright)
    out = np.zeros(T, dtype=np.int8)
    for t in range(T):
        e, p = bright[t], pfrac[t]
        if e > peak_e and p > peak_p:
            out[t] = 3
        elif e > drive_e:
            out[t] = 2
        elif e > groove_e:
            out[t] = 1
        else:
            out[t] = 0
    return out


def _direction_track(bright, slow):
    """Commit forward on a build, backward on a release; hold otherwise."""
    T = len(bright)
    out = np.ones(T, dtype=np.int8)
    build, release = params.get("dir_build"), params.get("dir_release")
    d = 1
    for t in range(T):
        if bright[t] > DIR_GATE:
            if bright[t] > slow[t] * build:
                d = 1
            elif bright[t] < slow[t] * release:
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
    db_floor = params.get("db_floor")
    rms = librosa.feature.rms(S=S, frame_length=NFFT, hop_length=HOP)[0]
    ref = float(np.percentile(rms, 95)) + 1e-9
    db = 20.0 * np.log10(rms / ref + 1e-9)
    bright = np.clip((db - db_floor) / (0.0 - db_floor), 0.0, 1.0)
    bright = _smooth(bright, 5)

    # --- spectral centroid (log) -> 0..1 ---
    cen = librosa.feature.spectral_centroid(S=S, sr=sr, freq=freqs)[0]
    lo, hi = np.log10(30), np.log10(16000)
    centroid = np.clip((np.log10(np.maximum(cen, 30)) - lo) / (hi - lo), 0.0, 1.0)

    # --- spectrum bars (40, log) ---
    sidx = np.searchsorted(freqs, BAR_EDGES)
    raw = np.zeros((NBARS, T))
    for i in range(NBARS):
        a, b = sidx[i], sidx[i + 1]
        if b > a:
            raw[i] = S[a:b].mean(axis=0)

    # per-band WHITENING: divide each band by its own song-long average, so the
    # display shows relative activity instead of the raw 1/f tilt (otherwise bass
    # always dominates). The bars you SEE and the colour we pick now come from the
    # SAME signal, so they always agree.
    band_mean = raw.mean(axis=1, keepdims=True) + 1e-6
    white = raw / band_mean                                    # ~1.0 on average per band
    specbars = np.clip(white * 0.5, 0, 1) ** params.get("spec_gamma")   # display 0..1 (avg ~0.5)

    # --- colour: aggregate the whitened bars into 6 freq groups -> dominant group ---
    centers = np.sqrt(BAR_EDGES[:-1] * BAR_EDGES[1:])
    cedges = np.logspace(np.log10(40), np.log10(16000), 7)
    bargroup = np.clip(np.searchsorted(cedges, centers) - 1, 0, 5)
    groups = np.zeros((6, T))
    for i in range(NBARS):
        groups[bargroup[i]] += white[i]
    color_idx = _color_track(groups, bright)

    # --- percussiveness (HPSS) + mood ---
    H, Pp = librosa.decompose.hpss(S)
    he, pe = H.sum(axis=0), Pp.sum(axis=0)
    pfrac = _smooth(pe / (he + pe + 1e-9), 9)
    mood = _mood_track(bright, pfrac)

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

    # --- time-varying (local) tempo, octave-folded toward the global tempo ---
    dtempo = np.atleast_1d(np.asarray(
        librosa.feature.tempo(onset_envelope=oenv, sr=sr, hop_length=HOP, aggregate=None),
        dtype=float)).ravel()
    if dtempo.size != T:
        dtempo = np.interp(np.linspace(0, 1, T), np.linspace(0, 1, dtempo.size), dtempo)
    g = bpm if bpm > 0 else float(np.median(dtempo) or 120)
    for k in range(dtempo.size):
        v = dtempo[k] if dtempo[k] > 0 else g
        while v < g * 0.7:
            v *= 2
        while v > g * 1.4:
            v /= 2
        dtempo[k] = v
    bpm_curve = _smooth(dtempo, 15)

    return {
        "version": VERSION,
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
        "mood": [int(m) for m in mood],
        "bpm_curve": [round(float(v), 1) for v in bpm_curve],
        "spec": [[round(float(v), 2) for v in specbars[:, t]] for t in range(T)],
    }


def warmup():
    """Trigger numba JIT for every librosa call analyze() uses, so the first real
    track analyses in ~1 s instead of paying ~30 s of compilation."""
    y = np.zeros(SR, dtype=np.float32)
    y[::1000] = 1.0
    S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP))
    librosa.feature.rms(S=S, frame_length=NFFT, hop_length=HOP)
    librosa.feature.spectral_centroid(S=S, sr=SR)
    librosa.feature.spectral_centroid(S=S, sr=SR)
    librosa.decompose.hpss(S)
    oenv = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    librosa.beat.beat_track(onset_envelope=oenv, sr=SR, hop_length=HOP, units="time")
    librosa.feature.tempo(onset_envelope=oenv, sr=SR, hop_length=HOP, aggregate=None)
