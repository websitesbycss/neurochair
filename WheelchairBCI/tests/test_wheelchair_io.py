"""Fast, data-free checks for the WheelchairBCI analysis helpers."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from wc_io import parse_seg, xcorr_lag, find_cnt, norm_label  # noqa: E402
from prep import bandpass, notch  # noqa: E402


def test_parse_seg_reads_second_segment(tmp_path):
    seg = tmp_path / "rec.seg"
    seg.write_text("NumberSegments=      2\r\n4.6333984571759262000e+004 6.2086699999999950000e-001 227330\r\n")
    (s,) = parse_seg(seg)
    assert s["start_sample"] == 227330
    assert s["datetime_utc"].year == 2026 and s["datetime_utc"].month == 11
    assert s["frac"] == pytest.approx(0.620867)


@pytest.mark.parametrize("shift", [-37, 0, 120])
def test_xcorr_lag_recovers_known_shift(shift):
    rng = np.random.default_rng(0)
    b = rng.standard_normal(5000)
    a = np.roll(b, -shift)[500:4500]          # a[n] == b[n + 500 + shift]
    lag, r, _, _ = xcorr_lag(a, b[500:4500], max_lag=200)
    assert lag == shift
    assert r > 0.9


def test_filters_keep_shape_and_remove_mains():
    fs = 500.0
    t = np.arange(int(4 * fs)) / fs
    x = np.vstack([np.sin(2 * np.pi * 10 * t) + np.sin(2 * np.pi * 60 * t)] * 3)
    y = notch(bandpass(x, fs, 5, 45), fs)
    assert y.shape == x.shape
    spec = np.abs(np.fft.rfft(y[0, 500:-500]))
    freqs = np.fft.rfftfreq(y.shape[1] - 1000, 1 / fs)
    assert spec[np.argmin(np.abs(freqs - 60))] < 0.01 * spec[np.argmin(np.abs(freqs - 10))]


def test_find_cnt_requires_exactly_one(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_cnt(tmp_path)
    (tmp_path / "rec.cnt").write_bytes(b"")
    assert find_cnt(tmp_path).name == "rec.cnt"


def test_norm_label_maps_mixed_case():
    assert [norm_label(c) for c in ["cz", "t7", "Fp1", "trigger"]] == ["Cz", "T7", "Fp1", "Trigger"]
