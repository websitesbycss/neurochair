"""
Loaders for the wheelchair-BCI recordings (subject S1, 2026-11-07).

* load_lsl_session()  : LSL .npz + events .csv  -> mne.io.RawArray with annotations
* parse_evt()         : ANT eego .evt (binary MFC serialisation) -> DataFrame of markers
* parse_seg()         : ANT eego .seg -> list of segment boundaries
* load_cnt()          : ANT eego .cnt -> mne Raw (via mne.io.read_raw_ant / antio)
* align_cnt_to_lsl()  : cross-correlation alignment of .cnt to the .npz stream
"""
from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import mne
from scipy import signal

mne.set_log_level("WARNING")

DATA = Path(__file__).resolve().parents[1] / "data"


def find_cnt(data_dir: Path = DATA) -> Path:
    """The single eego .cnt recording in data_dir (its .evt/.seg sidecars share the stem)."""
    found = sorted(Path(data_dir).glob("*.cnt"))
    if len(found) != 1:
        raise FileNotFoundError(f"expected exactly one .cnt in {data_dir}, found {len(found)}")
    return found[0]

# ----------------------------------------------------------------------------- labels
# LSL labels are mixed case; map everything onto the standard_1020 spelling.
LABEL_FIX = {
    "fp1": "Fp1", "fp2": "Fp2", "f9": "F9", "f7": "F7", "f3": "F3", "fz": "Fz", "f4": "F4",
    "f8": "F8", "f10": "F10", "m1": "M1", "t7": "T7", "c3": "C3", "c4": "C4", "t8": "T8",
    "m2": "M2", "cz": "Cz", "p7": "P7", "p3": "P3", "pz": "Pz", "p4": "P4", "p8": "P8",
    "oz": "Oz", "o1": "O1", "o2": "O2", "trigger": "Trigger", "cpz": "CPz",
}


def norm_label(lbl: str) -> str:
    return LABEL_FIX.get(str(lbl).strip().lower(), str(lbl).strip())


EEG_CHANNELS = ["Fp1", "Fp2", "F9", "F7", "F3", "Fz", "F4", "F8", "F10", "M1", "T7", "C3", "C4",
                "T8", "M2", "Cz", "P7", "P3", "Pz", "P4", "P8", "Oz", "O1", "O2"]
MASTOIDS = ["M1", "M2"]
OCC_PAR = ["O1", "Oz", "O2", "P3", "Pz", "P4", "P7", "P8"]
FRONTAL_EOG = ["Fp1", "Fp2", "F9", "F10", "F7", "F8"]


# ----------------------------------------------------------------------------- LSL npz + csv
@dataclass
class LslSession:
    name: str
    raw: mne.io.BaseRaw               # unfiltered, V, all channels (Trigger dropped)
    events: pd.DataFrame              # csv + 'sample' + 't' (seconds from first EEG sample)
    timestamps: np.ndarray            # LSL time of every sample
    fs: float
    labels: list[str]
    config: dict = field(default_factory=dict)

    @property
    def t0(self) -> float:
        return float(self.timestamps[0])

    def lsl_to_sample(self, t) -> np.ndarray:
        return np.searchsorted(self.timestamps, np.atleast_1d(t))

    def ev(self, block=None, event=None) -> pd.DataFrame:
        df = self.events
        if block is not None:
            df = df[df.block == block]
        if event is not None:
            df = df[df.event == event]
        return df


def read_events_csv(csv_path) -> pd.DataFrame:
    ev = pd.read_csv(csv_path, dtype={"detail": str}, keep_default_na=False)
    ev["lsl_time"] = ev["lsl_time"].astype(float)
    return ev


def load_lsl_session(stamp: str, data_dir: Path = DATA, name: str | None = None,
                     bads: tuple[str, ...] = ("Cz",)) -> LslSession:
    """stamp e.g. 'S1_20261107_182835'. Returns an LslSession with an mne RawArray.

    Values in the .npz are assumed to be microvolts (eego LSL output) and are scaled to volts.
    Annotations are created from every CSV event whose onset falls inside the recording.
    """
    base = Path(data_dir) / f"{stamp}_wc"
    z = np.load(str(base) + "_eeg.npz", allow_pickle=False)
    data = np.asarray(z["data"], dtype=np.float64)        # (n_samples, n_ch)
    ts = np.asarray(z["timestamps"], dtype=np.float64)
    fs = float(z["fs"])
    labels = [norm_label(l) for l in z["labels"].tolist()]
    cfg = json.loads(Path(str(base) + "_config.json").read_text())
    ev = read_events_csv(str(base) + "_events.csv")

    # sample index for every event: searchsorted on the LSL timestamps (same clock)
    ev["sample"] = np.searchsorted(ts, ev["lsl_time"].values)
    ev["in_eeg"] = (ev["lsl_time"] >= ts[0]) & (ev["lsl_time"] <= ts[-1])
    ev["t"] = ev["sample"] / fs                                 # seconds on the uniform Raw grid

    ch_types = ["stim" if l == "Trigger" else "eeg" for l in labels]
    info = mne.create_info(labels, fs, ch_types)
    X = data.T.copy()
    eeg_idx = [i for i, t in enumerate(ch_types) if t == "eeg"]
    X[eeg_idx] *= 1e-6                                         # uV -> V
    raw = mne.io.RawArray(X, info, verbose=False)
    wall0 = datetime.fromisoformat(ev.iloc[0]["wall_time"]).replace(tzinfo=timezone.utc)
    raw.set_meas_date(wall0 - timedelta(seconds=float(ev.iloc[0]["lsl_time"] - ts[0])))
    raw.drop_channels(["Trigger"])                              # all zeros - documented
    mont = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(mont, on_missing="warn")
    raw.info["bads"] = [b for b in bads if b in raw.ch_names]

    keep = ev[ev.in_eeg & ~ev.event.isin(["config"])]
    desc = (keep.block + "/" + keep.event + np.where(keep.detail != "", "/" + keep.detail, "")).values
    onset = keep["t"].values
    raw.set_annotations(mne.Annotations(onset=onset, duration=np.zeros(len(onset)), description=desc))
    return LslSession(name=name or stamp, raw=raw, events=ev, timestamps=ts, fs=fs,
                      labels=raw.ch_names, config=cfg)


# ----------------------------------------------------------------------------- eego .evt / .seg
OLE_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)


def ole_to_datetime(days: float, frac_s: float = 0.0) -> datetime:
    return OLE_EPOCH + timedelta(days=float(days), seconds=float(frac_s))


def parse_evt(path) -> pd.DataFrame:
    """Parse the ANT eego .evt binary (serialised MFC objects).

    Record layout (found by inspection):
      <len><'Epoch Event' | 'Event Marker'>\\0  24 header bytes  \\0
      <double: OLE date, integer seconds>  <double: fractional second>  <int32 n_fields>
      then n_fields x (<len><name>, VARIANT value).
    Returns DataFrame[kind, days, frac, t_abs, label, impedances, datetime_utc, block, event, detail, stream].
    """
    b = Path(path).read_bytes()
    recs = []
    for m in re.finditer(rb"\x0bEpoch Event\x00|\x0cEvent Marker\x00", b):
        kind = "epoch" if b[m.start()] == 0x0B else "marker"
        p = m.end() + 25
        days, frac = struct.unpack_from("<dd", b, p)
        nfields = struct.unpack_from("<I", b, p + 16)[0]
        q = p + 20
        label, imp = "", None
        for _ in range(nfields):
            ln = b[q]
            fname = b[q + 1:q + 1 + ln].decode("latin1")
            q += 1 + ln
            vt = struct.unpack_from("<H", b, q)[0]
            q += 2
            if vt == 8:                                            # VT_BSTR, UTF-16LE, byte length
                nb = struct.unpack_from("<I", b, q)[0]
                q += 4
                s = b[q:q + nb].decode("utf-16-le", errors="replace")
                q += nb
                if fname == "Condition":
                    label = s
            elif vt == 3:                                          # VT_I4
                q += 4
            elif vt == 0x200C:                                     # VT_ARRAY | VT_R4 (impedances)
                q += 4                                              # element size
                q += 2                                              # flags
                n = struct.unpack_from("<I", b, q)[0]
                q += 4
                imp = np.frombuffer(b[q:q + 4 * n], dtype="<f4").copy()
                q += 4 * n
                ln2 = b[q]
                q += 1 + ln2                                        # unit string ('kOhm')
                q += 1
            else:
                break
        recs.append(dict(kind=kind, days=days, frac=frac, label=label,
                         impedances=imp, t_abs=days * 86400.0 + frac))
    df = pd.DataFrame(recs)
    df["datetime_utc"] = [ole_to_datetime(d, f) for d, f in zip(df.days, df.frac)]
    core = df.label.str.replace(r"###.*$", "", regex=True)
    parts = core.str.split("|", n=2, expand=True)
    for i, col in enumerate(["block", "event", "detail"]):
        df[col] = parts[i].fillna("") if parts.shape[1] > i else ""
    df["stream"] = df.label.str.extract(r"###(.*)$")[0].fillna("")
    return df


def parse_seg(path) -> list[dict]:
    """.seg: 'NumberSegments= N' then one line per *additional* segment:
       <OLE date of segment start (integer seconds)> <fractional second> <first sample index>."""
    lines = [ln for ln in Path(path).read_text().strip().splitlines() if ln.strip()]
    n = int(lines[0].split("=")[1])
    segs = []
    for ln in lines[1:]:
        d, f, s = ln.split()
        segs.append(dict(days=float(d), frac=float(f), start_sample=int(s),
                         datetime_utc=ole_to_datetime(float(d), float(f))))
    assert len(segs) == n - 1, (n, segs)
    return segs


# ----------------------------------------------------------------------------- eego .cnt
def load_cnt(path, preload=True) -> mne.io.BaseRaw:
    path = Path(path)
    raw = mne.io.read_raw_ant(path, preload=preload, verbose=False)
    raw.rename_channels({c: norm_label(c) for c in raw.ch_names})
    mont = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(mont, on_missing="warn")
    return raw


def load_cnt_session(stamp: str, cnt_path=None, alignment_json=None, data_dir: Path = DATA,
                     bads: tuple[str, ...] = ("Cz",)) -> tuple[mne.io.BaseRaw, pd.DataFrame]:
    """eego .cnt loader for one LSL session (deliverable 1b).

    Returns (raw, events):
      raw    : the .cnt segment that corresponds to the session (segment 1 = A, segment 2 = B),
               µV->V, labels normalised, montage set, bad channels marked, annotations from
               (i) the eego native triggers ('trig/<block>/<event>/<detail>') and
               (ii) the CSV events mapped onto the .cnt timeline with the cross-correlation lag
                    ('csv/<block>/<event>/<detail>').
      events : the CSV with columns  cnt_sample_xcorr (csv lsl_time -> npz sample + lag) and
               cnt_sample_trigger (eego native trigger), both relative to the returned raw.
    Needs analysis/out/alignment.json and events_<A|B>_with_cnt.csv written by align.py.
    """
    import json
    here = Path(__file__).resolve().parent
    cnt_path = Path(cnt_path or find_cnt(data_dir))
    al = json.load(open(alignment_json or here / "out" / "alignment.json"))
    nm = {v["stamp"]: k for k, v in al["sessions"].items()}[stamp]
    sess = al["sessions"][nm]
    c0, c1 = sess["cnt_seg"]
    lag = int(sess["coarse_lag_samples"])
    raw = load_cnt(cnt_path, preload=True)
    fs = raw.info["sfreq"]
    # keep native triggers that fall inside the segment
    trig = raw.annotations
    keep = (trig.onset * fs >= c0) & (trig.onset * fs < c1)
    trig_desc = ["trig/" + (d.split("/", 1)[1] if "/" in d else d).split("###")[0].replace("|", "/")
                 for d in trig.description[keep]]
    trig_onset = trig.onset[keep] - c0 / fs
    raw = raw.copy().crop(tmin=c0 / fs, tmax=(c1 - 1) / fs, include_tmax=True)
    raw.set_annotations(None)
    ev = pd.read_csv(here / "out" / f"events_{nm}_with_cnt.csv", dtype={"detail": str}, keep_default_na=False)
    ev["cnt_sample_xcorr"] = ev["sample"].astype(int) + lag
    ev["cnt_sample_trigger"] = pd.to_numeric(ev["cnt_trig_sample"], errors="coerce")
    ok = (ev.cnt_sample_xcorr >= 0) & (ev.cnt_sample_xcorr < c1 - c0) & (ev.event != "config")
    csv_desc = ("csv/" + ev.block + "/" + ev.event + np.where(ev.detail != "", "/" + ev.detail, "")).values[ok]
    csv_onset = ev.cnt_sample_xcorr.values[ok] / fs
    onset = np.concatenate([trig_onset, csv_onset])
    desc = list(trig_desc) + list(csv_desc)
    raw.set_annotations(mne.Annotations(onset=onset, duration=np.zeros(len(onset)), description=desc))
    raw.info["bads"] = [b for b in bads if b in raw.ch_names]
    return raw, ev


def cnt_header_text(path, nbytes=4096) -> str:
    """The RF64 .cnt begins with a plain-text 'eeph' header: sampling rate, samples, channel table."""
    b = Path(path).read_bytes()[:nbytes]
    i = b.find(b"[File Version]")
    j = b.find(b"[History]")
    return b[i:j if j > 0 else nbytes].decode("latin1", errors="replace")


# ----------------------------------------------------------------------------- alignment
def bandpass(x, fs, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype="band", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x, axis=-1)


def xcorr_lag(a: np.ndarray, b: np.ndarray, max_lag: int):
    """Normalised cross-correlation via FFT.  Returns (lag, r, lags, r_all) where
    a[n] ~ b[n + lag] at the best lag (|lag| <= max_lag)."""
    a = (a - a.mean()) / (a.std() + 1e-12)
    b = (b - b.mean()) / (b.std() + 1e-12)
    n = len(a) + len(b) - 1
    nfft = 1 << (n - 1).bit_length()
    A = np.fft.rfft(a, nfft)
    B = np.fft.rfft(b, nfft)
    cc = np.fft.irfft(np.conj(A) * B, nfft)         # cc[k] = sum_n a[n] b[n + k]  (k >= 0 part)
    # negative k wrap to the end
    lags = np.arange(-max_lag, max_lag + 1)
    vals = cc[lags % nfft] / min(len(a), len(b))
    k = int(np.argmax(vals))
    return int(lags[k]), float(vals[k]), lags, vals


def align_cnt_to_lsl(cnt_x: np.ndarray, lsl_x: np.ndarray, fs: float, coarse_max_lag_s: float,
                     chunk_s: float = 30.0, band=(1.0, 40.0), clip_pct=(0.5, 99.5)):
    """Align a 1-D .cnt channel to the same channel of the LSL stream.

    1. coarse: full-length cross-correlation of the band-passed, amplitude-clipped signals
    2. fine:   per-chunk lags (chunk_s windows) -> linear fit lag(t) = intercept + slope*t

    Returns dict with `offset_samples` k such that  lsl[n] <-> cnt[n + k],
    peak correlation, per-chunk lags, and the fitted drift in ppm.
    """
    a = bandpass(lsl_x, fs, *band)
    b = bandpass(cnt_x, fs, *band)
    a = np.clip(a, *np.percentile(a, clip_pct))
    b = np.clip(b, *np.percentile(b, clip_pct))
    lag0, r0, _, _ = xcorr_lag(a, b, int(coarse_max_lag_s * fs))
    L = int(chunk_s * fs)
    w = int(2.0 * fs)
    ct, cl, cr = [], [], []
    for s in range(0, len(a) - L, L):
        seg_a = a[s:s + L]
        lo, hi = s + lag0 - w, s + lag0 + L + w
        if lo < 0 or hi > len(b):
            continue
        seg_b = b[lo:hi]
        # pad seg_a to seg_b length so lags are comparable; lag relative to 'lo'
        lag, r, _, _ = xcorr_lag(np.pad(seg_a, (w, w)), seg_b, w)
        ct.append((s + L / 2) / fs)
        cl.append(lag0 + lag)
        cr.append(r)
    ct, cl, cr = np.array(ct), np.array(cl), np.array(cr)
    if len(ct) >= 3:
        good = cr >= np.percentile(cr, 25)
        slope, intercept = np.polyfit(ct[good], cl[good], 1)
    else:
        slope, intercept = 0.0, float(lag0)
    return dict(offset_samples=lag0, peak_r=r0, chunk_t=ct, chunk_lag=cl, chunk_r=cr,
                fit_intercept=float(intercept), fit_slope_samples_per_s=float(slope),
                drift_ppm=float(slope / fs * 1e6))
