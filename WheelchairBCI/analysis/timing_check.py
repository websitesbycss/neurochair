"""Which event-timing source is accurate: LSL-path (csv lsl_time -> dejittered npz timestamps)
or the eego native triggers in the .cnt?

Test 1 (session A): inter-trial phase coherence (ITPC) of the SSVEP at the target frequency and
its 2nd harmonic at O1/Oz/O2 over 0.5-4.0 s after flicker_on.  Timing jitter of tens of ms
destroys phase coherence at 7-24 Hz, so the better-timed source has the higher ITPC.
Test 2: grand-average visual onset response (VEP) to flicker_on (A) and to `appear` (B, per run);
sharper timing -> larger/narrower average.
"""
import sys, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from prep import load_session, bandpass, lowpass, notch, epoch, rereference, FS, OUT

FREQS = {"Bathroom": 12.0, "Kitchen": 60 / 7, "Bed": 7.5, "Door": 60 / 9}
res = {}

A = load_session("A")
print("Session A bads:", A.bads)
Xa = rereference(notch(bandpass(A.X, FS, 2, 45), FS), A.ch, "avg", A.bads)
occ = A.idx(["O1", "Oz", "O2"])
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
itpc_tab = []
for timing in ("lsl", "cnt"):
    for tgt, f in FREQS.items():
        rows = A.ev("ssvep", "flicker_on"); rows = rows[rows.detail == tgt]
        E, keep, _ = epoch(Xa, rows, timing, 0.5, 4.0, steps=A.steps)
        t = np.arange(E.shape[-1]) / FS
        for h, name in ((1, "f"), (2, "2f")):
            c = (E[:, occ, :] * np.exp(-2j * np.pi * f * h * t)).mean(-1)      # (n_trials, 3)
            itpc = np.abs((c / np.abs(c)).mean(0)).mean()                       # mean over O1/Oz/O2
            snr = np.abs(c).mean()
            itpc_tab.append(dict(timing=timing, target=tgt, harmonic=name, n=E.shape[0], itpc=itpc))
df = pd.DataFrame(itpc_tab)
piv = df.pivot_table(index=["target", "harmonic"], columns="timing", values="itpc")
print("\nITPC (phase consistency across trials, 0.5-4 s, mean O1/Oz/O2):\n", piv.round(3).to_string())
res["itpc"] = piv.reset_index().to_dict(orient="records")
# null distribution: shuffle onsets by random +-200 ms
rng = np.random.default_rng(0)
null = []
for _ in range(20):
    rows = A.ev("ssvep", "flicker_on"); rows = rows[rows.detail == "Bathroom"].copy()
    rows["sample_cnt"] = rows["sample_cnt"] + rng.uniform(-100, 100, len(rows))
    E, keep, _ = epoch(Xa, rows, "cnt", 0.5, 4.0, steps=A.steps)
    t = np.arange(E.shape[-1]) / FS
    c = (E[:, occ, :] * np.exp(-2j * np.pi * 12.0 * t)).mean(-1)
    null.append(np.abs((c / np.abs(c)).mean(0)).mean())
print(f"ITPC null (12 Hz, cnt timing jittered +-200 ms): mean {np.mean(null):.3f}, 95th pct {np.percentile(null, 95):.3f}")
res["itpc_null_12Hz"] = dict(mean=float(np.mean(null)), p95=float(np.percentile(null, 95)))

# --- VEP to flicker_on, both timings
Xv = rereference(lowpass(A.X, FS, 30) if False else bandpass(A.X, FS, 0.5, 30), A.ch, "avg", A.bads)
for k, timing in enumerate(("lsl", "cnt")):
    rows = A.ev("ssvep", "flicker_on")
    E, keep, _ = epoch(Xv, rows, timing, -0.2, 0.5, steps=A.steps)
    E = E - E[:, :, :int(0.2 * FS)].mean(-1, keepdims=True)
    t = np.arange(E.shape[-1]) / FS - 0.2
    ga = E.mean(0)
    oz = ga[A.ch.index("Oz")]
    pk = np.abs(oz[(t > 0.05) & (t < 0.25)]).max()
    print(f"VEP flicker_on ({timing}): n={E.shape[0]} Oz peak |amp| 50-250 ms = {pk:.2f} uV")
    res[f"vep_flicker_on_{timing}"] = dict(n=int(E.shape[0]), oz_peak_uV=float(pk))
    ax = axes[0, k]
    for c in ("Oz", "O1", "O2", "Pz"):
        ax.plot(t, ga[A.ch.index(c)], label=c)
    ax.axvline(0, color="k", lw=.5); ax.legend(); ax.set_title(f"A: VEP to flicker_on, {timing} timing (n={E.shape[0]})")
    ax.set_xlabel("s"); ax.set_ylabel("uV")
ax = axes[0, 2]
for timing, mk in (("lsl", "o"), ("cnt", "s")):
    sub = df[(df.timing == timing) & (df.harmonic == "f")]
    ax.plot(sub.target, sub.itpc, mk + "-", label=f"{timing} timing, f")
    sub = df[(df.timing == timing) & (df.harmonic == "2f")]
    ax.plot(sub.target, sub.itpc, mk + "--", label=f"{timing} timing, 2f")
ax.axhline(np.percentile(null, 95), color="r", lw=.5, label="null 95%")
ax.set_ylim(0, 1); ax.legend(); ax.set_title("A: SSVEP inter-trial phase coherence")

# --- Session B: VEP to `appear`, per run
B = load_session("B")
print("Session B bads:", B.bads)
Xb = rereference(bandpass(B.X, FS, 0.5, 30), B.ch, "avg", B.bads)
for k, timing in enumerate(("lsl", "cnt")):
    ax = axes[1, k]
    for run in (1, 2):
        rows = B.ev("brake", "appear"); rows = rows[rows.run == run]
        E, keep, _ = epoch(Xb, rows, timing, -0.2, 0.6, steps=B.steps)
        E = E - E[:, :, :int(0.2 * FS)].mean(-1, keepdims=True)
        t = np.arange(E.shape[-1]) / FS - 0.2
        ga = E.mean(0)
        oz = ga[B.ch.index("Oz")]
        pk = np.abs(oz[(t > 0.05) & (t < 0.3)]).max()
        print(f"VEP appear ({timing}, run {run}): n={E.shape[0]} Oz peak |amp| 50-300 ms = {pk:.2f} uV")
        res[f"vep_appear_{timing}_run{run}"] = dict(n=int(E.shape[0]), oz_peak_uV=float(pk))
        ax.plot(t, oz, label=f"Oz run {run}")
        ax.plot(t, ga[B.ch.index("Pz")], "--", label=f"Pz run {run}")
    ax.axvline(0, color="k", lw=.5); ax.legend(); ax.set_title(f"B: VEP to object `appear`, {timing} timing")
    ax.set_xlabel("s"); ax.set_ylabel("uV")
ax = axes[1, 2]
err = B.events[(B.events.block == "brake") & np.isfinite(B.events.sample_cnt)]
ax.plot(err.t_lsl, (err.sample_lsl - err.sample_cnt) / FS * 1000, ".", ms=3)
ax.set_title("B: LSL-path timing minus cnt trigger (ms) vs time"); ax.set_xlabel("s"); ax.set_ylabel("ms")
plt.tight_layout(); plt.savefig(OUT / "fig_timing_check.png", dpi=110)
json.dump(res, open(OUT / "timing_check.json", "w"), indent=1)
print("saved", OUT / "fig_timing_check.png")
