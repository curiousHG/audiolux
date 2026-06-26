"""Offline analysis: schema, bounded spectrum, beat detection, colour not stuck white."""
import collections
import os

import numpy as np
import soundfile as sf
import pytest

from backend import analysis, modes

SR = 22050


def _write(tmp_path, name, y):
    p = os.path.join(tmp_path, name)
    sf.write(p, (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32), SR)
    return p


@pytest.fixture(scope="module")
def click_120(tmp_path_factory):
    """A 120 BPM click track + a low bass bed."""
    d = tmp_path_factory.mktemp("audio")
    dur = 12
    t = np.arange(int(SR * dur)) / SR
    click = np.zeros_like(t)
    for b in np.arange(0, dur, 0.5):          # every 0.5 s = 120 BPM
        i = int(b * SR)
        click[i:i + 200] += np.hanning(200)
    bass = 0.4 * np.sin(2 * np.pi * 80 * t)
    return analysis.analyze(_write(str(d), "click.wav", click + bass))


def test_schema_complete(click_120):
    tl = click_120
    assert tl["version"] == analysis.VERSION
    n = len(tl["bright"])
    for key in ("color", "centroid", "dir", "mood", "spec"):
        assert len(tl[key]) == n, f"{key} length mismatch"
    assert tl["beats"] and tl["bpm"] > 0


def test_spectrum_bounded(click_120):
    spec = np.array(click_120["spec"])
    assert spec.shape[1] == 40
    assert spec.min() >= 0.0 and spec.max() <= 1.0   # the 'bars too high' regression


def test_color_indices_and_mood_in_range(click_120):
    assert all(0 <= c < len(modes.FREQ_COLORS) for c in click_120["color"])
    assert all(0 <= m < len(modes.MOOD_NAMES) for m in click_120["mood"])


def test_beat_detection_120bpm(click_120):
    assert 110 <= click_120["bpm"] <= 130, f"expected ~120, got {click_120['bpm']}"


def test_bass_signal_is_not_white(tmp_path):
    # a pure low-frequency bass tone must read warm (red/violet), never white
    t = np.arange(int(SR * 6)) / SR
    y = np.sin(2 * np.pi * 70 * t)
    tl = analysis.analyze(_write(str(tmp_path), "bass.wav", y))
    counts = collections.Counter(modes.FREQ_COLORS[c] for c in tl["color"])
    dominant = counts.most_common(1)[0][0]
    assert dominant in ("RD", "VT", "BU"), f"bass should be warm/low, got {dominant}"
    assert counts["WH"] / sum(counts.values()) < 0.2, "bass should rarely be white"


def test_treble_signal_is_bright(tmp_path):
    # a high-frequency tone should read bright (yellow/white), not red
    t = np.arange(int(SR * 6)) / SR
    y = np.sin(2 * np.pi * 9000 * t)
    tl = analysis.analyze(_write(str(tmp_path), "treble.wav", y))
    counts = collections.Counter(modes.FREQ_COLORS[c] for c in tl["color"])
    dominant = counts.most_common(1)[0][0]
    assert dominant in ("YE", "WH", "GN"), f"treble should be bright, got {dominant}"
