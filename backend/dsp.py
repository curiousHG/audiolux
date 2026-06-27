"""Small, generic signal-processing helpers shared by the analysis pipeline.

Pure numpy — no project knowledge — so they can be reused and unit-tested on their own.
"""
import numpy as np


def ema(x, alpha):
    """Causal exponential moving average of `x` with smoothing factor `alpha`."""
    out = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - alpha) * acc + alpha * v
        out[i] = acc
    return out


def smooth(x, window):
    """Boxcar (moving-average) smooth of `x` over `window` samples; no-op if window <= 1."""
    if window <= 1:
        return x
    kernel = np.ones(window) / window
    return np.convolve(x, kernel, mode="same")
