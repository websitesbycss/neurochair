"""Preprocessing summary (deliverable 2): channel quality + impedances, step jumps, filters,
recording coverage, eego .evt marker report.  Writes analysis/out/preprocessing_summary.md"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from prep import load_session, FS, OUT, CNT, STEP_THR_UV, SETTLE_S, IMPEDANCE_BAD_KOHM, STD_RATIO_BAD
from wc_io import parse_evt, parse_seg, load_cnt_session

al = json.load(open(OUT / "alignment.json"))
evt = parse_evt(CNT.with_suffix(".evt"))
seg = parse_seg(CNT.with_suffix(".seg"))[0]
L = []
L.append("# Preprocessing summary\n")
L.append("## Files and coverage\n")
L.append("| Session | LSL npz | cnt segment | lag (cnt = lsl + lag) | identical samples | LSL rate implied by timestamps |")
L.append("|---|---|---|---|---|---|")
for nm, s in al["sessions"].items():
    L.append(f"| {nm} | {s['stamp']}_wc_eeg.npz | samples {s['cnt_seg'][0]}–{s['cnt_seg'][1]} | {s['coarse_lag_samples']} samples ({s['coarse_lag_samples']/FS:+.3f} s) | {s['frac_identical']*100:.1f} % (std ratio {s['units_std_ratio']:.5f}) | {s['lsl_rate_from_timestamps']:.2f} Hz |")
L.append("")
L.append(f"- The `.cnt` has {al['n_total']} samples at 500 Hz in two segments: segment 1 starts {al['cnt_start_utc']} "
         f"(sample 0, session A, ends at the 2nd impedance check), segment 2 starts {al['seg2_start_utc']} at sample {al['seg2_start']} (session B). "
         f"The `.seg` file's number ({seg['start_sample']}) is the length of the *last* segment, not its start index.")
L.append("- The `.cnt` ends at the same instant as the session-B LSL stream (the eego recording was stopped there), so the last 4 "
         "artifact trials and the final sync block are not recoverable from any file.")
L.append("- Samples are bit-identical between `.cnt` and `.npz` (same amplifier stream, µV, DC-coupled, REF = CPz); no dropped samples in either session. "
         "The 499 Hz implied by the LSL timestamps is the stimulus PC's clock-sync/dejitter estimate, not lost samples.")
L.append("- Event timing: the eego native triggers (LSL markers received by eego) are used. The LSL-path mapping "
         "(csv lsl_time -> dejittered npz timestamps) deviates from them by a smooth transient of up to 300 ms in the first ~3 min of each recording "
         "(liblsl dejitter convergence); see timing_check.")
L.append("")
L.append("## eego .evt markers\n")
imp = evt[evt.kind == "marker"]
L.append(f"- {len(evt)} records: {int((evt.kind=='epoch').sum())} LSL markers from stream `WheelchairMarkers` (all CSV events except those sent before the eego recording started / after it stopped) and {len(imp)} impedance checks.")
cnt_ch = ["Fp1", "Fp2", "F9", "F7", "F3", "Fz", "F4", "F8", "F10", "M1", "T7", "C3", "C4", "T8", "M2", "Cz", "P7", "P3", "Pz", "P4", "P8", "Oz", "O1", "O2"]
L.append(f"- Impedance checks (kOhm) at {imp.datetime_utc.iloc[0]} (recording start / session A) and {imp.datetime_utc.iloc[1]} (pause before session B):\n")
L.append("| ch | " + " | ".join(cnt_ch) + " |")
L.append("|---|" + "---|" * len(cnt_ch))
for i, (_, r) in enumerate(imp.iterrows()):
    L.append(f"| check {i+1} | " + " | ".join(f"{v:.0f}" for v in r.impedances) + " |")
L.append("")
L.append("- The marker counts per block in the .evt match the CSV, except: session A `config`/`session_start` (sent before the eego recording started), "
         "session B artifact trials 17–20 and the final sync block (after the recording stopped), and the first jaw-clench cue of session A, "
         "which is in the .evt (t = 0.106 s) but is dropped by antio/MNE (it is restored from the .evt time).")
L.append("")
L.append("## Channel quality\n")
L.append(f"Rules: bad if impedance > {IMPEDANCE_BAD_KOHM:.0f} kOhm, or 1–40 Hz std > {STD_RATIO_BAD:.0f}× the median channel, or Cz (documented bad).\n")
rej_all = {}
for nm in ("A", "B"):
    S = load_session(nm)
    q = S.quality.copy()
    L.append(f"### Session {nm}: bad channels = {S.bads}\n")
    L.append("| ch | impedance kOhm | 1–40 Hz std µV | std / median | max step µV (after 8 s) | bad |")
    L.append("|---|---|---|---|---|---|")
    for _, r in q.iterrows():
        L.append(f"| {r.ch} | {r.impedance_kOhm:.0f} | {r.std_1_40_uV:.1f} | {r.std_ratio:.1f} | {r.max_step_uV:.0f} | {'**yes**' if r.bad else ''} |")
    st = S.steps
    st_after = st[st > SETTLE_S * FS]
    L.append("")
    L.append(f"- Step jumps > {STEP_THR_UV:.0f} µV/sample on any good channel: {len(st)} samples, of which {len(st_after)} after the first {SETTLE_S:.0f} s "
             f"(at EEG-relative s: {np.round(np.unique(np.round(st_after / FS, 1)), 1).tolist()}). Epochs overlapping these (±0.25 s) are rejected.")
    L.append("")
    rej_all[nm] = dict(bads=S.bads, steps=st.tolist())
L.append("## Filters\n")
L.append("- All offline filtering is zero-phase (scipy sosfiltfilt / filtfilt).")
L.append("- SSVEP: 60 Hz + 120 Hz IIR notch (Q = 30), 4th-order Butterworth band-pass 5–45 Hz; FBCCA sub-bands [5,50], [13,50], [21,50], [29,50] Hz.")
L.append("- Brake ERPs / classifier: 4th-order Butterworth band-pass 0.5–30 Hz (60 Hz is outside the pass band); press-locked spectra: 4–40 Hz Morlet.")
L.append("- Per-channel mean removed (DC offsets of −47 000…+63 000 µV); the first 8 s of each recording are excluded (amplifier settling).")
L.append("- Re-reference: average of the good non-mastoid channels (default). Linked mastoids are not usable: M2 is bad in both sessions "
         "(187 kOhm / 1857 kOhm, 1–40 Hz std 7–8× the median), so the 'mastoid' option is M1 alone.")
L.append("- Epoch rejection: step jump inside epoch (±0.25 s margin), epoch outside the recording, peak-to-peak threshold (brake: 150 µV on classifier channels).")
L.append("")
# cnt loader smoke test
rawA, evA = load_cnt_session("S1_20261107_182835")
rawB, evB = load_cnt_session("S1_20261107_183742")
L.append("## cnt-based loader (wc_io.load_cnt_session)\n")
for nm, r, e in (("A", rawA, evA), ("B", rawB, evB)):
    n_tr = sum(d.startswith("trig/") for d in r.annotations.description)
    n_csv = sum(d.startswith("csv/") for d in r.annotations.description)
    dd = (e.cnt_sample_xcorr - e.cnt_sample_trigger).dropna()
    L.append(f"- Session {nm}: {r.n_times/FS:.1f} s, {n_tr} native-trigger annotations, {n_csv} CSV-derived annotations; "
             f"CSV-mapped minus trigger: median {dd.median()/FS*1000:.0f} ms, min {dd.min()/FS*1000:.0f} ms, max {dd.max()/FS*1000:.0f} ms over {len(dd)} events.")
(OUT / "preprocessing_summary.md").write_text("\n".join(L), encoding="utf-8")
json.dump(rej_all, open(OUT / "preprocessing_channels.json", "w"), indent=1)
print("\n".join(L))
