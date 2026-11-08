"""Align the eego .cnt to the two LSL .npz recordings and check the eego trigger timing.

Outputs (analysis/out/):
  alignment.json        lags, segments, dropouts, timing-error statistics
  fig_alignment.png     per-chunk lag vs time, event timing error vs time, jaw-clench sync overlay
"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import hilbert

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from wc_io import DATA, find_cnt, load_lsl_session, load_cnt, parse_evt, parse_seg, bandpass, xcorr_lag

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
CNT = find_cnt(DATA)
FS = 500.0

raw_cnt = load_cnt(CNT)
Xc = raw_cnt.get_data() * 1e6                      # µV
ch = raw_cnt.ch_names
evt = parse_evt(CNT.with_suffix(".evt"))
seg = parse_seg(CNT.with_suffix(".seg"))[0]
cnt_t0 = evt.t_abs.iloc[0]                         # recording start = first (impedance) marker
n_total = raw_cnt.n_times

# ---- segment structure: hypothesis test. The .seg number is either the start index of
# segment 2 or its length; decide with the session-B markers (cnt triggers vs eego clock).
ann = raw_cnt.annotations
ann_df = pd.DataFrame({"sample": np.round(ann.onset * FS).astype(int),
                       "desc": [(d.split("/", 1)[1] if "/" in d else d).split("###")[0] for d in ann.description]})
print("annotation descriptions without '/':", [d for d in ann.description if "/" not in d][:5])
ann_df = ann_df[ann_df.desc.str.contains(r"\|")].reset_index(drop=True)
seg2_t = seg["days"] * 86400 + seg["frac"]
evt_m = evt[evt.kind == "epoch"].reset_index(drop=True)
evt_m["lab"] = evt_m.label.str.split("###").str[0]


def match_triggers(pred_samples, labels, tol=1500):
    """For every evt marker find the cnt trigger with the same label nearest to the predicted sample."""
    out = np.full(len(pred_samples), np.nan)
    for i, (p, l) in enumerate(zip(pred_samples, labels)):
        cand = ann_df[ann_df.desc == l]["sample"].values
        if len(cand):
            k = np.argmin(np.abs(cand - p))
            if abs(cand[k] - p) <= tol:
                out[i] = cand[k]
    return out


res = {}
in_seg2 = evt_m.t_abs.values >= seg2_t - 1.0
for hyp, s2 in (("seg_value_is_start", seg["start_sample"]), ("seg_value_is_length", n_total - seg["start_sample"])):
    pred = np.where(in_seg2, s2 + (evt_m.t_abs.values - seg2_t) * FS, (evt_m.t_abs.values - cnt_t0) * FS)
    trig = match_triggers(pred, evt_m.lab.values, tol=40000)
    resid = trig - pred
    res[hyp] = dict(seg2_start=int(s2), n_matched=int(np.isfinite(resid).sum()),
                    seg1_median_resid=float(np.nanmedian(resid[~in_seg2])), seg2_median_resid=float(np.nanmedian(resid[in_seg2])),
                    seg2_resid_sd=float(np.nanstd(resid[in_seg2])))
print("segment hypotheses (residual = cnt trigger sample - sample predicted from eego clock):", json.dumps(res, indent=1))
seg2_start = min(res.values(), key=lambda r: abs(r["seg2_median_resid"]))["seg2_start"]
print("=> segment 2 starts at cnt sample", seg2_start, f"({seg2_start/FS:.2f} s); segment 1 = {seg2_start/FS:.2f} s, segment 2 = {(n_total-seg2_start)/FS:.2f} s")
seg1_end_utc = evt.datetime_utc.iloc[0] + pd.Timedelta(seconds=seg2_start / FS)
seg2_end_utc = seg["datetime_utc"] + pd.Timedelta(seconds=(n_total - seg2_start) / FS)
print(f"   segment 1: {evt.datetime_utc.iloc[0]} -> {seg1_end_utc}   (2nd impedance marker at {evt[evt.kind=='marker'].datetime_utc.iloc[1]})")
print(f"   segment 2: {seg['datetime_utc']} -> {seg2_end_utc}")

# eego-clock -> cnt sample for any marker time
def eego_t_to_sample(t_abs):
    t_abs = np.atleast_1d(t_abs)
    s = np.where(t_abs < seg["days"] * 86400 + seg["frac"] - 1.0,
                 (t_abs - cnt_t0) * FS,
                 seg2_start + (t_abs - (seg["days"] * 86400 + seg["frac"])) * FS)
    return s

evt["cnt_sample_evt"] = eego_t_to_sample(evt.t_abs.values)
evt_m["cnt_sample_evt"] = eego_t_to_sample(evt_m.t_abs.values)
print(f"cnt triggers: {len(ann_df)}  evt epoch markers: {len(evt_m)}")
evt_m["cnt_sample_trig"] = match_triggers(evt_m.cnt_sample_evt.values, evt_m.lab.values, tol=1500)
evt_m["trigger_source"] = np.where(np.isfinite(evt_m.cnt_sample_trig), "cnt_trigger", "evt_time")
evt_m["cnt_sample_trig"] = evt_m.cnt_sample_trig.fillna(evt_m.cnt_sample_evt.round())
d = (evt_m.cnt_sample_trig - evt_m.cnt_sample_evt)
print(f"evt-time vs cnt-trigger sample difference: n={d.notna().sum()}  median={d.median():.2f}  min={d.min():.2f}  max={d.max():.2f} samples")
print("  unmatched evt markers (no cnt trigger):", evt_m[d.isna()][["datetime_utc", "label", "cnt_sample_evt"]].to_string())
evt_m.to_csv(OUT / "evt_markers_matched.csv", index=False)

# ---------------------------------------------------------------- cross-correlation alignment
results = {"seg2_start": int(seg2_start), "n_total": int(n_total), "cnt_start_utc": str(evt.datetime_utc.iloc[0]),
           "seg2_start_utc": str(seg["datetime_utc"]), "segments": res, "sessions": {}}
fig, axes = plt.subplots(3, 2, figsize=(15, 11))
sessions = {"A": ("S1_20261107_182835", 0, seg2_start), "B": ("S1_20261107_183742", seg2_start, n_total)}
lsl = {}
for col, (nm, (stamp, c0, c1)) in enumerate(sessions.items()):
    s = load_lsl_session(stamp, name=nm)
    lsl[nm] = s
    Xl = s.raw.get_data() * 1e6
    assert s.raw.ch_names == ch, (s.raw.ch_names, ch)
    fz_l = Xl[ch.index("Fz")]
    fz_c = Xc[ch.index("Fz"), c0:c1]
    a = bandpass(fz_l, FS, 1, 40); b = bandpass(fz_c, FS, 1, 40)
    a = np.clip(a, *np.percentile(a, [0.5, 99.5])); b = np.clip(b, *np.percentile(b, [0.5, 99.5]))
    # coarse lag: lsl[n] ~ cntseg[n + lag]
    lag0, r0, lags, vals = xcorr_lag(a, b, int(60 * FS))
    print(f"\nSession {nm}: coarse lag {lag0} samples ({lag0/FS:+.3f} s), r={r0:.3f}; 2nd peak ratio "
          f"{np.sort(vals)[-2]/vals.max():.2f}")
    # fine: 10-s chunks, search ±3 s around coarse lag
    L = int(10 * FS); W = int(3 * FS)
    ct, cl, cr = [], [], []
    for st in range(0, len(a) - L, L // 2):
        lo, hi = st + lag0 - W, st + lag0 + L + W
        if lo < 0 or hi > len(b):
            continue
        lag, r, _, _ = xcorr_lag(np.pad(a[st:st + L], (W, W)), b[lo:hi], W)
        ct.append((st + L / 2) / FS); cl.append(lag0 + lag); cr.append(r)
    ct, cl, cr = map(np.array, (ct, cl, cr))
    jumps = np.where(np.diff(cl) != 0)[0]
    print(f"  per-chunk lag: unique values {np.unique(cl)}; lag changes at t≈ {np.round(ct[jumps], 1)} s (LSL-rel); min r={cr.min():.3f}")
    # exact sample-level check: for each chunk verify identity cnt == lsl at the lag (raw values)
    # Determine dropout positions precisely with a sample-by-sample raw comparison
    lag_fn = np.interp(np.arange(len(fz_l)) / FS, ct, cl)
    # locate change points by scanning raw equality of Fz values
    change_pts = []
    cur = int(cl[0])
    i = 0
    while i < len(fz_l) - 1:
        k = i + cur
        if 0 <= k < len(fz_c) and abs(fz_l[i] - fz_c[k]) < 1e-3 * max(1.0, abs(fz_c[k])) * 0 + 0.02:
            i += 1
            continue
        # mismatch: search new lag within ±2000 samples that matches the next 50 samples
        found = None
        for dlt in range(0, 2000):
            for sgn in (1, -1):
                k2 = i + cur + sgn * dlt
                if 0 <= k2 < len(fz_c) - 50 and i + 50 < len(fz_l) and np.allclose(fz_l[i:i + 50], fz_c[k2:k2 + 50], atol=0.02):
                    found = cur + sgn * dlt; break
            if found is not None:
                break
        if found is None:
            i += 1; continue
        if found != cur:
            change_pts.append(dict(lsl_sample=int(i), t_lsl_rel=float(i / FS), old_lag=int(cur), new_lag=int(found),
                                   dropped_samples=int(found - cur)))
            cur = found
        i += 1
    print(f"  raw-identity scan: {len(change_pts)} lag changes:", change_pts)
    total_dropped = sum(c["dropped_samples"] for c in change_pts)
    # amplitude / units comparison on a clean chunk
    i0 = int(60 * FS); i1 = i0 + int(60 * FS); k0 = i0 + int(cl[0])
    ratio = np.std(fz_c[k0:k0 + (i1 - i0)]) / np.std(fz_l[i0:i1])
    exact = np.mean(np.abs(fz_l[i0:i1] - fz_c[k0:k0 + (i1 - i0)]) < 0.02)
    print(f"  units: std ratio cnt/lsl at 60-120 s = {ratio:.5f}; fraction of exactly equal samples = {exact:.4f}")
    # ---- event timing error of the LSL path: csv->lsl sample (+ local lag) vs cnt trigger sample
    ev = s.events.copy()
    lab = (ev.block + "|" + ev.event + "|" + ev.detail).values
    em = evt_m[(evt_m.cnt_sample_trig >= c0) & (evt_m.cnt_sample_trig < c1)].reset_index(drop=True)
    # match sequentially (both lists are in chronological order; CSV may contain events eego never saw)
    j = 0; trig = np.full(len(ev), np.nan)
    for i, l in enumerate(lab):
        hits = [k for k in range(j, min(j + 6, len(em))) if em.lab.iloc[k] == l]
        if hits:
            trig[i] = em.cnt_sample_trig.iloc[hits[0]] - c0; j = hits[0] + 1
    ev["cnt_trig_sample"] = trig
    print(f"  CSV events matched to cnt triggers: {np.isfinite(trig).sum()} / {len(ev)}")
    lag_at_ev = np.interp(ev["sample"].values / FS, ct, cl)
    # piecewise-constant lag from change points
    lag_pc = np.full(len(ev), float(cl[0]))
    for cp in change_pts:
        lag_pc[ev["sample"].values >= cp["lsl_sample"]] = cp["new_lag"]
    ev["lsl_pred_cnt_sample"] = ev["sample"] + lag_pc
    ev["timing_err_ms"] = (ev["lsl_pred_cnt_sample"] - ev["cnt_trig_sample"]) / FS * 1000   # + = LSL path later
    ok = ev.cnt_trig_sample.notna() & ev.in_eeg
    e = ev.loc[ok, "timing_err_ms"]
    print(f"  LSL-path event timing error vs cnt trigger (ms): n={ok.sum()} mean={e.mean():.1f} median={e.median():.1f} "
          f"sd={e.std():.1f} min={e.min():.1f} max={e.max():.1f}")
    # by block
    print(ev.loc[ok].groupby("block").timing_err_ms.describe()[["count", "mean", "std", "min", "max"]].round(1).to_string())
    ev.to_csv(OUT / f"events_{nm}_with_cnt.csv", index=False)
    # ---- jaw clench check: HF envelope on F7/F8/T7/T8 around sync cues
    hf_idx = [ch.index(c) for c in ("F7", "F8", "T7", "T8")]
    def envelope(X):
        y = bandpass(X, FS, 20, 100)
        return np.abs(hilbert(y, axis=-1)).mean(0)
    env_l = envelope(Xl[hf_idx]); env_c = envelope(Xc[hf_idx, c0:c1])
    cues = ev[(ev.event == "jaw_clench_cue") & ev.in_eeg]
    peak_l, peak_c = [], []
    for _, r in cues.iterrows():
        i0 = int(r["sample"]); i1 = i0 + int(1.5 * FS)
        if i1 < len(env_l):
            pl = i0 + np.argmax(env_l[i0:i1]); peak_l.append(pl)
            k0 = int(i0 + lag_pc[cues.index.get_loc(_)] if False else i0 + np.interp(i0 / FS, ct, cl))
            k0 = int(round(k0))
            if 0 <= k0 and k0 + int(1.5 * FS) < len(env_c):
                pc = k0 + np.argmax(env_c[k0:k0 + int(1.5 * FS)]); peak_c.append(pc)
    print("  clench HF-burst peaks (LSL sample -> cnt sample) differences:",
          [int(pc - pl) for pl, pc in zip(peak_l, peak_c)], " expected lag:", np.unique(cl))
    print("  clench burst latency after cue (s):", np.round((np.array(peak_l) - cues["sample"].values[:len(peak_l)]) / FS, 3))
    results["sessions"][nm] = dict(stamp=stamp, cnt_seg=[int(c0), int(c1)], coarse_lag_samples=int(lag0), coarse_r=r0,
                                   chunk_t=ct.tolist(), chunk_lag=cl.tolist(), chunk_r=cr.tolist(),
                                   lag_changes=change_pts, total_dropped_samples=int(total_dropped),
                                   units_std_ratio=float(ratio), frac_identical=float(exact),
                                   timing_err_ms=dict(n=int(ok.sum()), mean=float(e.mean()), median=float(e.median()),
                                                      sd=float(e.std()), min=float(e.min()), max=float(e.max())),
                                   lsl_rate_from_timestamps=float((len(s.timestamps) - 1) / (s.timestamps[-1] - s.timestamps[0])))
    # ---- plots
    ax = axes[0, col]; ax.plot(ct, cl / FS, ".-"); ax.set_title(f"Session {nm}: lag cnt-vs-LSL per 10 s chunk (r min {cr.min():.3f})")
    ax.set_xlabel("LSL-relative time (s)"); ax.set_ylabel("lag (s): cnt_sample = lsl_sample + lag")
    for cp in change_pts:
        ax.axvline(cp["t_lsl_rel"], color="r", alpha=.5)
    ax = axes[1, col]; ax.plot(ev.loc[ok, "t"], ev.loc[ok, "timing_err_ms"], ".", ms=4)
    ax.axhline(0, color="k", lw=.5); ax.set_title(f"Session {nm}: LSL-path event time minus cnt trigger (ms)")
    ax.set_xlabel("LSL-relative time (s)"); ax.set_ylabel("ms")
    ax = axes[2, col]
    r = cues.iloc[0]; i0 = int(r["sample"]) - int(1 * FS); i1 = int(cues.iloc[-1]["sample"]) + int(3 * FS) if len(cues) <= 3 else int(cues.iloc[2]["sample"]) + int(3 * FS)
    lag_here = int(round(np.interp(i0 / FS, ct, cl)))
    i0 = max(i0, -lag_here)                      # cnt segment may start after the first cue window
    k0 = i0 + lag_here
    print(f"  clench plot window: lsl {i0}-{i1}, cnt {k0}-{k0 + (i1 - i0)} (len env_c {len(env_c)})", flush=True)
    tt = np.arange(i1 - i0) / FS
    ax.plot(tt, env_l[i0:i1], label="LSL npz"); ax.plot(tt, env_c[k0:k0 + (i1 - i0)], "--", label="cnt (aligned)")
    for _, rr in cues.iloc[:3].iterrows():
        ax.axvline((rr["sample"] - i0) / FS, color="g", alpha=.6)
    ax.legend(); ax.set_title(f"Session {nm}: 20-100 Hz envelope F7/F8/T7/T8, first sync block (green = cue)")
    ax.set_xlabel("s"); ax.set_ylabel("µV")
plt.tight_layout(); plt.savefig(OUT / "fig_alignment.png", dpi=110)
with open(OUT / "alignment.json", "w") as f:
    json.dump(results, f, indent=1, default=float)
print("\nsaved", OUT / "alignment.json")
