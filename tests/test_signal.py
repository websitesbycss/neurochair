"""Answer-key test: the synthetic stream has a KNOWN movement pattern
(mu power drops on Ch9-12 for 2 s out of every 6 s). Processing code must find it."""
from itertools import islice

import numpy as np

from dsp.features import MU, band_power
from stream_replay import CHUNK, N_CH, SRATE, synthetic

SECONDS = 30


def _data():
    chunks = [c for c, _ in islice(synthetic(), SECONDS * SRATE // CHUNK)]
    return np.vstack(chunks)


def test_stream_shape():
    x = _data()
    assert x.shape == (SECONDS * SRATE, N_CH)
    assert np.isfinite(x).all()


def test_mu_drop_detected_on_motor_channels():
    x = _data()
    rest, move = [], []
    for s in range(SECONDS):
        w = x[s * SRATE:(s + 1) * SRATE, 8:12]
        (move if (s % 6) >= 4 else rest).append(band_power(w, SRATE, *MU).mean())
    assert np.mean(move) < 0.5 * np.mean(rest)


def test_non_motor_channels_unaffected():
    x = _data()
    rest, move = [], []
    for s in range(SECONDS):
        w = x[s * SRATE:(s + 1) * SRATE, 0:4]
        (move if (s % 6) >= 4 else rest).append(band_power(w, SRATE, *MU).mean())
    assert abs(np.mean(move) / np.mean(rest) - 1) < 0.2
