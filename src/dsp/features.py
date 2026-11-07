"""Band-power features. Shared by the live reader, the tests, and (later) the model."""
import numpy as np
from scipy.signal import welch

MU = (8, 12)
BETA = (13, 30)


def band_power(x, fs, lo, hi):
    """Mean PSD in [lo, hi] Hz per channel. x: (samples, channels)."""
    f, p = welch(x, fs=fs, nperseg=min(len(x), 256), axis=0)
    return p[(f >= lo) & (f <= hi)].mean(axis=0)
