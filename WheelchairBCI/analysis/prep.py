"""Preprocessing for the wheelchair-BCI recordings.

Session object (EEG samples + both event-timing sources), channel quality, filters,
step-jump detection, epoch extraction with rejection bookkeeping, EOG regression.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal
import mne

from wc_io import DATA, find_cnt, load_lsl_session, parse_evt, MASTOIDS

OUT = Path(__file__).parent / "out"
FS = 500.0
try:
    CNT = find_cnt(DATA)
except FileNotFoundError:          # no data checked out (e.g. CI): helpers still importable
    CNT = None
STAMPS = {"A": "S1_20261107_182835", "B": "S1_20261107_183742"}
IMPEDANCE_BAD_KOHM = 1000.0        # eego tolerates high impedance, but >1 MOhm channels were visibly bad
STD_RATIO_BAD = 5.0                # 1-40 Hz std more than 5x the median channel
STEP_THR_UV = 2000.0               # amplifier step jumps (brief: >2000 per sample)
SETTLE_S = 8.0                     # drop the first 8 s (amplifier settling)


@dataclass
class Session:
    name: str
    fs: float
    X: np.ndarray            # (n_ch, n_samples) µV, per-channel mean removed, LSL sample grid
    ch: list
    events: pd.DataFrame     # CSV events + sample_lsl / sample_cnt (both on the LSL sample grid)
    lag: int                 # cnt_segment_sample = lsl_sample + lag
    cnt_seg: tuple
    bads: list
    quality: pd.DataFrame
    steps: np.ndarray        # sample indices with a step jump on any good channel
    raw: mne.io.BaseRaw      # unfiltered mne Raw (V) with CSV annotations
    impedances: dict

    @property
    def good(self):
        return [c for c in self.ch if c not in self.bads]

    def idx(self, names):
        return [self.ch.index(c) for c in names]

    def ev(self, block=None, event=None, **kw):
        df = self.events
        if block is not None:
            df = df[df.block == block]
        if event is not None:
            df = df[df.event == event]
        return df


def load_session(nm: str, extra_bads=()) -> Session:
    s = load_lsl_session(STAMPS[nm], name=nm)
    al = json.load(open(OUT / "alignment.json"))["sessions"][nm]
    lag = int(al["coarse_lag_samples"])
    ev = pd.read_csv(OUT / f"events_{nm}_with_cnt.csv", dtype={"detail": str}, keep_default_na=False)
    ev["sample_lsl"] = ev["sample"].astype(int)
    ev["sample_cnt"] = pd.to_numeric(ev["cnt_trig_sample"], errors="coerce") - lag   # NaN where eego never saw the marker
    ev["t_lsl"] = ev["sample_lsl"] / FS
    ev["t_cnt"] = ev["sample_cnt"] / FS
    ev["run"] = np.nan
    for blk in ("ssvep", "brake"):
        rs = ev[(ev.block == blk) & (ev.event == "run_start")]
        for _, r in rs.iterrows():
            ev.loc[(ev.block == blk) & (ev.lsl_time >= r.lsl_time), "run"] = int(str(r.detail).split("|")[0])
    X = s.raw.get_data() * 1e6
    X = X - X.mean(1, keepdims=True)
    ch = list(s.raw.ch_names)
    # impedances from the eego .evt (first marker = before session A, second = before session B)
    evt = parse_evt(CNT.with_suffix(".evt"))
    imp_rows = evt[evt.kind == "marker"]
    imp = imp_rows.impedances.iloc[0 if nm == "A" else 1]
    cnt_ch = ["Fp1", "Fp2", "F9", "F7", "F3", "Fz", "F4", "F8", "F10", "M1", "T7", "C3", "C4", "T8", "M2", "Cz",
              "P7", "P3", "Pz", "P4", "P8", "Oz", "O1", "O2"]
    impedances = dict(zip(cnt_ch, map(float, imp)))
    # channel quality
    Xf = bandpass(X[:, int(10 * FS):], FS, 1, 40)
    sd = Xf.std(1)
    med = np.median(sd)
    q = pd.DataFrame({"ch": ch, "std_1_40_uV": sd, "std_ratio": sd / med,
                      "impedance_kOhm": [impedances.get(c, np.nan) for c in ch],
                      "max_step_uV": np.abs(np.diff(X, axis=1))[:, int(SETTLE_S * FS):].max(1)})
    q["bad_impedance"] = q.impedance_kOhm > IMPEDANCE_BAD_KOHM
    q["bad_variance"] = q.std_ratio > STD_RATIO_BAD
    q["bad"] = q.bad_impedance | q.bad_variance | q.ch.isin(["Cz"]) | q.ch.isin(list(extra_bads))
    bads = q.ch[q.bad].tolist()
    good_idx = [i for i, c in enumerate(ch) if c not in bads]
    steps = np.where((np.abs(np.diff(X[good_idx], axis=1)) > STEP_THR_UV).any(0))[0] + 1
    raw = s.raw.copy()
    raw.info["bads"] = bads
    return Session(name=nm, fs=FS, X=X, ch=ch, events=ev, lag=lag, cnt_seg=tuple(al["cnt_seg"]), bads=bads,
                   quality=q, steps=steps, raw=raw, impedances=impedances)


# ----------------------------------------------------------------------------- filters
def bandpass(X, fs, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype="band", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, X, axis=-1)


def lowpass(X, fs, hi, order=4):
    sos = signal.butter(order, hi, btype="low", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, X, axis=-1)


def highpass(X, fs, lo, order=2):
    sos = signal.butter(order, lo, btype="high", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, X, axis=-1)


def notch(X, fs, freqs=(60.0, 120.0), q=30.0):
    Y = X
    for f in freqs:
        if f < fs / 2:
            b, a = signal.iirnotch(f, q, fs)
            Y = signal.filtfilt(b, a, Y, axis=-1)
    return Y


def rereference(X, ch, mode, bads):
    """mode: 'avg' (mean of good non-mastoid channels), 'mastoid' (mean of good mastoids), 'none' (CPz)."""
    if mode == "none":
        return X.copy()
    if mode == "avg":
        ref_ch = [c for c in ch if c not in bads and c not in MASTOIDS]
    elif mode == "mastoid":
        ref_ch = [c for c in MASTOIDS if c not in bads]
        if not ref_ch:
            raise ValueError("no good mastoid")
    else:
        raise ValueError(mode)
    ref = X[[ch.index(c) for c in ref_ch]].mean(0, keepdims=True)
    return X - ref


# ----------------------------------------------------------------------------- epochs
def epoch(X, rows: pd.DataFrame, timing: str, tmin: float, tmax: float, fs=FS, steps=None,
          margin_s=0.25, settle_s=SETTLE_S, ptp_thr=None, ptp_chans=None):
    """Cut epochs [tmin, tmax) around rows[sample_<timing>].

    Returns E (n_keep, n_ch, n_t), keep (bool per row), log DataFrame with a reason for every rejected row.
    """
    col = {"cnt": "sample_cnt", "lsl": "sample_lsl"}[timing]
    n0, n1 = int(round(tmin * fs)), int(round(tmax * fs))
    m = int(margin_s * fs)
    E, keep, reasons = [], [], []
    for _, r in rows.iterrows():
        c = r[col]
        if not np.isfinite(c):
            keep.append(False); reasons.append("no %s timing" % timing); continue
        c = int(round(c)); s0, s1 = c + n0, c + n1
        if s0 < 0 or s1 > X.shape[1]:
            keep.append(False); reasons.append("outside recording"); continue
        if s0 < settle_s * fs:
            keep.append(False); reasons.append("amplifier settling (<%.0f s)" % settle_s); continue
        if steps is not None and np.any((steps >= s0 - m) & (steps < s1 + m)):
            keep.append(False); reasons.append("step jump within epoch"); continue
        e = X[:, s0:s1]
        if ptp_thr is not None:
            sub = e if ptp_chans is None else e[ptp_chans]
            ptp = (sub.max(1) - sub.min(1)).max()
            if ptp > ptp_thr:
                keep.append(False); reasons.append(f"peak-to-peak {ptp:.0f} uV > {ptp_thr:.0f}"); continue
        E.append(e); keep.append(True); reasons.append("")
    keep = np.array(keep, bool)
    log = rows.copy()
    log["kept"] = keep
    log["reject_reason"] = reasons
    return (np.stack(E) if E else np.zeros((0, X.shape[0], n1 - n0))), keep, log


# ----------------------------------------------------------------------------- EOG
def eog_proxies(X, ch):
    """VEOG proxy = mean(Fp1, Fp2);  HEOG proxy = F9 - F10 (fallback F7 - F8)."""
    v = X[[ch.index("Fp1"), ch.index("Fp2")]].mean(0)
    h = X[ch.index("F9")] - X[ch.index("F10")]
    return np.vstack([v, h])


def fit_eog_regression(Xf, ch, train_mask):
    """Least-squares weights B (n_ch, 2) so that Xf ~ B @ EOG on the training samples."""
    G = eog_proxies(Xf, ch)[:, train_mask]
    Y = Xf[:, train_mask]
    B = np.linalg.lstsq(G.T, Y.T, rcond=None)[0].T
    return B


def apply_eog_regression(Xf, ch, B):
    return Xf - B @ eog_proxies(Xf, ch)
