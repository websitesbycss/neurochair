"""First look at all files: LSL npz/csv, eego cnt/evt/seg."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from wc_io import (DATA, find_cnt, load_lsl_session, load_cnt, parse_evt, parse_seg, cnt_header_text, bandpass)

pd.set_option("display.width", 200, "display.max_columns", 20, "display.max_rows", 200)

CNT = find_cnt(DATA)

print("=" * 80, "\nCNT header text\n", cnt_header_text(CNT)[:1500])

for stamp, nm in [("S1_20261107_182835", "A"), ("S1_20261107_183742", "B")]:
    s = load_lsl_session(stamp, name=nm)
    X = s.raw.get_data() * 1e6
    d = np.diff(s.timestamps) * 1000
    print("=" * 80)
    print(f"Session {nm}: {X.shape[1]} samples, {X.shape[1]/s.fs:.1f} s, LSL start {s.t0:.3f}, end {s.timestamps[-1]:.3f}")
    print(f"  ts spacing ms: median {np.median(d):.3f} min {d.min():.3f} max {d.max():.3f};"
          f" n(>2.5ms)={np.sum(d>2.5)}; implied fs from span = {(len(s.timestamps)-1)/(s.timestamps[-1]-s.t0):.4f}")
    print(f"  channels: {s.labels}")
    print(f"  bads: {s.raw.info['bads']}")
    means = X.mean(1)
    Xf = bandpass(X - means[:, None], s.fs, 1, 40)
    stds = Xf[:, int(10 * s.fs):].std(1)
    steps = np.abs(np.diff(X, axis=1)).max(0)
    print("  ch    mean(uV)   std_1-40Hz(uV)   max|step|(uV)")
    for ch, m, sd, st in zip(s.labels, means, stds, np.abs(np.diff(X, axis=1)).max(1)):
        print(f"  {ch:4s} {m:11.0f} {sd:14.1f} {st:14.0f}")
    big = np.where(steps > 2000)[0]
    print(f"  step jumps >2000uV in any channel: {len(big)} samples; first at {big[:5]/s.fs} s, last at {big[-5:]/s.fs} s")
    print(f"  events: {len(s.events)}  in_eeg={s.events.in_eeg.sum()}  annotations={len(s.raw.annotations)}")
    print(s.events.groupby(['block', 'event']).size().to_string())

print("=" * 80, "\nSEG:")
segs = parse_seg(CNT.with_suffix(".seg"))
for sg in segs:
    print(" ", sg)

print("=" * 80, "\nEVT:")
evt = parse_evt(CNT.with_suffix(".evt"))
print(f"  {len(evt)} records; kinds: {evt.kind.value_counts().to_dict()}")
print(f"  streams: {evt.stream.value_counts().to_dict()}")
print(f"  first: {evt.datetime_utc.iloc[0]}  last: {evt.datetime_utc.iloc[-1]}")
imp = evt[evt.kind == 'marker']
for _, r in imp.iterrows():
    print(f"  impedance marker at {r.datetime_utc}: {np.round(r.impedances, 1) if r.impedances is not None else None}")
print(evt.groupby(['block', 'event']).size().to_string())
print(evt[['datetime_utc', 'block', 'event', 'detail']].head(12).to_string())
print(evt[['datetime_utc', 'block', 'event', 'detail']].tail(12).to_string())
evt.to_csv(Path(__file__).parent / "out" / "evt_markers.csv", index=False)

print("=" * 80, "\nCNT via mne:")
raw = load_cnt(CNT)
print(raw)
print(raw.info)
print("  meas_date:", raw.info['meas_date'], " n_times:", raw.n_times, " dur:", raw.n_times / raw.info['sfreq'])
print("  ch_names:", raw.ch_names)
print("  annotations:", len(raw.annotations), set(raw.annotations.description))
if len(raw.annotations):
    print(pd.DataFrame({'onset': raw.annotations.onset, 'dur': raw.annotations.duration, 'desc': raw.annotations.description}).head(30).to_string())
Xc = raw.get_data(picks='eeg') * 1e6
print("  cnt eeg means (uV):", np.round(Xc.mean(1), 0))
Xcf = bandpass(Xc - Xc.mean(1, keepdims=True), raw.info['sfreq'], 1, 40)
print("  cnt 1-40Hz std (uV):", np.round(Xcf[:, 5000:].std(1), 1))
stepc = np.abs(np.diff(Xc, axis=1)).max(0)
bigc = np.where(stepc > 2000)[0]
print(f"  cnt step jumps >2000uV: {len(bigc)}; at s: {np.round(bigc / 500.0, 2)[:40]}")
# check for the pause / segment boundary at sample 227330
sb = segs[0]['start_sample']
print(f"  around segment boundary sample {sb}: Fz values {np.round(Xc[raw.ch_names.index('Fz'), sb-3:sb+4], 1)}")
# any flat / constant stretches?
flat = np.all(np.diff(Xc, axis=1) == 0, axis=0)
print(f"  samples where all channels have zero diff: {flat.sum()}")
