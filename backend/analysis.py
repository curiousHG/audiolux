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
from backend.dsp import ema, smooth

# 44100 Hz -> Nyquist 22050 Hz, so the 16 kHz spectrum bars are real (cymbals/air ->
# the white/treble colour band). Matches the live mic engine's rate. NFFT/HOP scaled
# with SR so the window (~93 ms), frequency resolution (~10.8 Hz/bin) and frame rate
# (~21.5 fps, so `dt` is unchanged) all stay the same as before — only Nyquist doubles.
SR = 44100
NFFT = 4096
HOP = 2048
NBARS = 40
BAR_EDGES = np.logspace(np.log10(30), np.log10(16000), NBARS + 1)
VERSION = 11               # bump when the timeline schema/algorithm changes (forces re-analysis)
DIR_GATE = 0.05            # below this brightness, direction holds


def _color_track(groups, bright):
    """Dominant colour per frame from the WHITENED 6-group energy (same signal the
    spectrum draws), so the chosen colour matches the tallest visible bars. White
    is slightly de-emphasised; the colour holds through near-silence."""
    weight = np.array([1.0, 1.0, 1.0, 0.97, 0.92, params.get("white_deemph")])
    silence = params.get("colour_silence")
    n_bands, T = groups.shape
    smoothed = np.zeros(n_bands)
    out = np.zeros(T, dtype=np.int16)
    cur = 0
    for t in range(T):
        if bright[t] < silence:
            out[t] = cur
            continue
        smoothed = 0.6 * smoothed + 0.4 * (groups[:, t] * weight)
        cur = int(np.argmax(smoothed))
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


def _trailing_tempo(beats, g, T, dt, K=8):
    """Per-frame local tempo from a trailing window of K recent beats (median inter-
    beat interval -> BPM), octave-folded toward the global tempo `g` so it stays in
    [0.7g, 1.4g]. Held between beats, then lightly smoothed."""
    out = np.full(T, g, dtype=float)
    if len(beats) < 3:
        return out
    per_beat, cur = [], g
    for i in range(len(beats)):
        window = beats[max(0, i - K + 1):i + 1]
        intervals = np.diff(window)
        intervals = intervals[(intervals > 0.2) & (intervals < 2.0)]
        if intervals.size:
            bpm = 60.0 / float(np.median(intervals))
            while bpm < g * 0.7:
                bpm *= 2
            while bpm > g * 1.4:
                bpm /= 2
            cur = bpm
        per_beat.append(cur)
    beat_idx = 0
    for t in range(T):
        frame_time = t * dt
        while beat_idx + 1 < len(beats) and beats[beat_idx + 1] <= frame_time:
            beat_idx += 1
        out[t] = per_beat[beat_idx]
    return smooth(out, 9)


def _direction_track(bright, slow):
    """Commit forward on a build, backward on a release; hold otherwise."""
    T = len(bright)
    out = np.ones(T, dtype=np.int8)
    build, release = params.get("dir_build"), params.get("dir_release")
    direction = 1
    for t in range(T):
        if bright[t] > DIR_GATE:
            if bright[t] > slow[t] * build:
                direction = 1
            elif bright[t] < slow[t] * release:
                direction = 0
        out[t] = direction
    return out


def analyze(path: str) -> dict:
    """Analyse an audio file into a JSON-serialisable light-control timeline."""
    y, sr = librosa.load(path, sr=SR, mono=True)
    duration = len(y) / sr

    S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=NFFT)
    T = S.shape[1]

    db_floor = params.get("db_floor")
    rms = librosa.feature.rms(S=S, frame_length=NFFT, hop_length=HOP)[0]
    ref = float(np.percentile(rms, 95)) + 1e-9
    db = 20.0 * np.log10(rms / ref + 1e-9)
    loudness = np.clip((db - db_floor) / (0.0 - db_floor), 0.0, 1.0)
    loudness = smooth(loudness, 5)
    # brightness OUTPUT stretched to the song's own 5th..95th pct so it spans the full
    # range; mood/direction/colour keep using the ABSOLUTE `loudness` below.
    lo_b, hi_b = float(np.percentile(loudness, 5)), float(np.percentile(loudness, 95))
    bright = np.clip((loudness - lo_b) / (hi_b - lo_b + 1e-9), 0.0, 1.0)

    centroid_hz = librosa.feature.spectral_centroid(S=S, sr=sr, freq=freqs)[0]
    lo, hi = np.log10(30), np.log10(16000)
    centroid = np.clip((np.log10(np.maximum(centroid_hz, 30)) - lo) / (hi - lo), 0.0, 1.0)

    # flatness -> "broadband" 0..1 (1 = noise-like white, 0 = tonal); normalised to the
    # song's own 95th-pct. Broadband loud moments are when a white Strobe is truthful.
    flat_raw = librosa.feature.spectral_flatness(S=S)[0]
    fref = float(np.percentile(flat_raw, 95)) + 1e-9
    flat = smooth(np.clip(flat_raw / fref, 0.0, 1.0), 5)

    bin_idx = np.searchsorted(freqs, BAR_EDGES)
    raw = np.zeros((NBARS, T))
    for i in range(NBARS):
        a, b = bin_idx[i], bin_idx[i + 1]
        if b > a:
            raw[i] = S[a:b].mean(axis=0)

    # per-band whitening: divide each band by its song-long average so the display
    # shows relative activity instead of the raw 1/f tilt (else bass always dominates).
    band_mean = raw.mean(axis=1, keepdims=True) + 1e-6
    white = raw / band_mean
    # not top-clipped — loud transients keep real height so the UI can auto-range.
    specbars = np.maximum(white * 0.5, 0.0) ** params.get("spec_gamma")

    centers = np.sqrt(BAR_EDGES[:-1] * BAR_EDGES[1:])
    group_edges = np.logspace(np.log10(40), np.log10(16000), 7)
    group_idx = np.clip(np.searchsorted(group_edges, centers) - 1, 0, 5)
    groups = np.zeros((6, T))
    for i in range(NBARS):
        groups[group_idx[i]] += white[i]
    color_idx = _color_track(groups, loudness)

    harmonic, percussive = librosa.decompose.hpss(S)
    harmonic_energy, percussive_energy = harmonic.sum(axis=0), percussive.sum(axis=0)
    pfrac = smooth(percussive_energy / (harmonic_energy + percussive_energy + 1e-9), 9)
    mood = _mood_track(loudness, pfrac)

    slow = ema(loudness, 0.02)
    direction = _direction_track(loudness, slow)

    # explicit onset envelope: beat_track(y=...) returns 0 beats on librosa 0.11 + numpy 2.x.
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr,
                                           hop_length=HOP, units="time")
    bpm = float(np.atleast_1d(tempo)[0])

    # trailing local tempo (median inter-beat interval, octave-folded toward the global
    # tempo) — a more honest "what's the beat doing now" than librosa's per-frame tempo.
    g = bpm if bpm > 0 else 120.0
    bpm_curve = _trailing_tempo(np.asarray(beats, float), g, T, float(HOP / sr))

    # "drive": onset density 0..1. Detected tempo is ~constant within a song, so the
    # onset envelope is what makes the animation speed breathe with the music.
    onset_density = onset_env.astype(float)
    if onset_density.size != T:
        onset_density = np.interp(np.linspace(0, 1, T),
                                  np.linspace(0, 1, onset_density.size), onset_density)
    # smooth, then stretch to the song's own 5th..95th pct so speed spans the full range.
    onset_density = smooth(onset_density, 7)
    lo_pct, hi_pct = np.percentile(onset_density, 5), np.percentile(onset_density, 95)
    drive = np.clip((onset_density - lo_pct) / (hi_pct - lo_pct + 1e-9), 0.0, 1.0)

    return {
        "version": VERSION,
        "sr": sr,
        "duration": round(float(duration), 2),
        "bpm": round(bpm, 1),
        "dt": float(HOP / sr),
        "fps": round(sr / HOP, 2),
        "beats": [round(float(b), 3) for b in beats],
        "bright": [round(float(v), 3) for v in bright],
        "color": [int(c) for c in color_idx],
        "centroid": [round(float(v), 3) for v in centroid],
        "flat": [round(float(v), 3) for v in flat],
        "drive": [round(float(v), 3) for v in drive],
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
    librosa.feature.spectral_flatness(S=S)
    librosa.decompose.hpss(S)
    onset_env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    librosa.beat.beat_track(onset_envelope=onset_env, sr=SR, hop_length=HOP, units="time")
