"""SSVEP direction decoder, session A.

CCA (Nh = 2/3/4), FBCCA, ensemble TRCA and extended (template) CCA; window lengths 1-4 s;
leave-one-run-out CV for the trained methods; bootstrap CIs; ITR; a center / no-selection
rejection rule evaluated run-wise and on eyes-open rest data as a null.

Run:  PYTHONUTF8=1 .venv/Scripts/python.exe analysis/ssvep.py
"""
import sys, json, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal, linalg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
from prep import load_session, bandpass, notch, rereference, epoch, FS, OUT

TARGETS = ["Bathroom", "Kitchen", "Bed", "Door"]
FREQS = {"Bathroom": 12.0, "Kitchen": 60 / 7, "Bed": 7.5, "Door": 60 / 9}
DELAY = 0.14                              # visual response delay after flicker_on
WINDOWS = [1.0, 2.0, 3.0, 4.0]
OCC = ["O1", "Oz", "O2", "P3", "Pz", "P4", "P7", "P8"]
FB_BANDS = [(5, 50), (13, 50), (21, 50), (29, 50)]
FB_W = np.array([m ** -1.25 + 0.25 for m in range(1, len(FB_BANDS) + 1)])
NH_MAIN = 3
TIMING = "cnt"
RNG = np.random.default_rng(0)
N_BOOT = 2000


# ----------------------------------------------------------------------------- signal helpers
def refs(f, T, nh):
    t = np.arange(T) / FS
    return np.vstack([fn(2 * np.pi * k * f * t) for k in range(1, nh + 1) for fn in (np.sin, np.cos)])


def cca(X, Y, reg=1e-6):
    """Canonical correlations between X (p, T) and Y (q, T) via whitened cross-covariance SVD.
    Returns (rhos descending, Wx (p, r), Wy (q, r))."""
    X = X - X.mean(1, keepdims=True)
    Y = Y - Y.mean(1, keepdims=True)
    T = X.shape[1]
    Cxx = X @ X.T / T
    Cyy = Y @ Y.T / T
    Cxy = X @ Y.T / T
    Cxx += reg * np.trace(Cxx) / len(Cxx) * np.eye(len(Cxx))
    Cyy += reg * np.trace(Cyy) / len(Cyy) * np.eye(len(Cyy))
    Kx = linalg.inv(linalg.cholesky(Cxx, lower=True))
    Ky = linalg.inv(linalg.cholesky(Cyy, lower=True))
    U, S, Vt = linalg.svd(Kx @ Cxy @ Ky.T, full_matrices=False)
    return S, Kx.T @ U, Ky.T @ Vt.T


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float(a @ b / np.sqrt((a @ a) * (b @ b) + 1e-30))


def cca_scores(X, nh):
    return np.array([cca(X, refs(FREQS[t], X.shape[1], nh))[0][0] for t in TARGETS])


def fbcca_scores(Xbands, nh):
    rho = np.array([[cca(Xb, refs(FREQS[t], Xb.shape[1], nh))[0][0] for t in TARGETS] for Xb in Xbands])
    return (FB_W[:, None] * rho ** 2).sum(0)


def trca_filter(Xk, reg=1e-6):
    """Task-related component analysis spatial filter for one class. Xk: (n_trials, p, T)."""
    Xc = Xk - Xk.mean(2, keepdims=True)
    ssum = Xc.sum(0)
    S = ssum @ ssum.T - sum(x @ x.T for x in Xc)
    Xcat = np.concatenate(list(Xc), axis=1)
    Q = Xcat @ Xcat.T
    Q += reg * np.trace(Q) / len(Q) * np.eye(len(Q))
    _, V = linalg.eigh(S, Q)
    return V[:, -1]


def trca_train(E, y):
    W = np.column_stack([trca_filter(E[y == t]) for t in TARGETS])          # ensemble: all class filters
    templates = {t: E[y == t].mean(0) for t in TARGETS}
    return W, templates


def trca_scores(X, W, templates):
    T = X.shape[1]
    return np.array([corr((W.T @ X).ravel(), (W.T @ templates[t][:, :T]).ravel()) for t in TARGETS])


def ecca_scores(X, templates, nh):
    """Extended CCA (Chen et al. 2015 combination): sine refs + training template, 4 coefficients."""
    out = []
    T = X.shape[1]
    for t in TARGETS:
        Xb = templates[t][:, :T]
        Y = refs(FREQS[t], T, nh)
        r1, Wx1, _ = cca(X, Y)
        _, Wx2, _ = cca(X, Xb)
        _, Wx3, _ = cca(Xb, Y)
        w1, w2, w3 = Wx1[:, 0], Wx2[:, 0], Wx3[:, 0]
        r = [r1[0], corr(w2 @ X, w2 @ Xb), corr(w1 @ X, w1 @ Xb), corr(w3 @ X, w3 @ Xb)]
        out.append(sum(np.sign(ri) * ri ** 2 for ri in r))
    return np.array(out)


def itr_bits_per_min(p, n, T):
    if p <= 1 / n:
        return 0.0
    b = np.log2(n) + (p * np.log2(p) if p > 0 else 0) + ((1 - p) * np.log2((1 - p) / (n - 1)) if p < 1 else 0)
    return float(b * 60 / T)


def boot_ci(correct, n_boot=N_BOOT):
    c = np.asarray(correct, float)
    if len(c) == 0:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(c), (n_boot, len(c)))
    acc = c[idx].mean(1)
    return (float(np.percentile(acc, 2.5)), float(np.percentile(acc, 97.5)))


def reject_features(S):
    s = np.sort(S, 1)[:, ::-1]
    return {"max": s[:, 0], "margin": s[:, 0] - s[:, 1], "rel_margin": (s[:, 0] - s[:, 1]) / np.maximum(s[:, 0], 1e-12)}


# ----------------------------------------------------------------------------- load + preprocess
A = load_session("A")
print("bads:", A.bads)
rows = A.ev("ssvep", "flicker_on").reset_index(drop=True)
rows["trial"] = np.arange(1, len(rows) + 1)
y = rows.detail.values
run = rows.run.astype(int).values
is_tgt = np.isin(y, TARGETS)
print(f"{len(rows)} flicker_on trials; per class: {pd.Series(y).value_counts().to_dict()}; per run: {pd.Series(run).value_counts().to_dict()}")
Xn = notch(A.X, FS)


def prep_cont(ref):
    Xr = rereference(Xn, A.ch, ref, A.bads)
    main = bandpass(Xr, FS, 5, 45)
    bands = []
    for lo, hi in FB_BANDS:
        sos = signal.cheby1(4, 0.5, [lo, hi], btype="band", fs=FS, output="sos")
        bands.append(signal.sosfiltfilt(sos, Xr, axis=-1))
    return main, bands


def cut(Xcont, L, chans):
    E, keep, log = epoch(Xcont, rows, TIMING, DELAY, DELAY + L, steps=A.steps)
    return E[:, chans, :], keep, log


results = {"timing": TIMING, "delay_s": DELAY, "bads": A.bads, "channels": OCC, "windows_s": WINDOWS,
           "nh_main": NH_MAIN, "fb_bands": FB_BANDS, "fb_weights": FB_W.tolist()}

# ---- reference comparison (plain CCA, Nh=3, 4 s, occipital/parietal set)
occ_idx = A.idx(OCC)
ref_cmp = {}
cont = {}
for ref in ("avg", "mastoid", "none"):
    cont[ref] = prep_cont(ref)
    E, keep, _ = cut(cont[ref][0], 4.0, occ_idx)
    pred = np.array([TARGETS[np.argmax(cca_scores(e, NH_MAIN))] for e in E])
    m = is_tgt[keep]
    ref_cmp[ref] = float((pred[m] == y[keep][m]).mean())
print("reference comparison (CCA Nh=3, 4 s, OCC):", ref_cmp)
best_ref = max(ref_cmp, key=ref_cmp.get)
REF = "avg" if ref_cmp[best_ref] - ref_cmp["avg"] <= 0.10 else best_ref
print("=> using reference:", REF)
results["reference_comparison_acc_cca_4s"] = ref_cmp
results["reference_used"] = REF
main_cont, band_cont = cont[REF]

# ---- channel-set comparison
good_idx = A.idx(A.good)
chan_cmp = {}
for name, idx in (("occ_par_8", occ_idx), ("all_good_%d" % len(good_idx), good_idx)):
    E, keep, _ = cut(main_cont, 4.0, idx)
    pred = np.array([TARGETS[np.argmax(cca_scores(e, NH_MAIN))] for e in E])
    m = is_tgt[keep]
    chan_cmp[name] = float((pred[m] == y[keep][m]).mean())
print("channel-set comparison (CCA Nh=3, 4 s):", chan_cmp)
results["channel_set_comparison_acc_cca_4s"] = chan_cmp

# ----------------------------------------------------------------------------- scores for every method / window
METHODS = ["CCA_nh2", "CCA_nh3", "CCA_nh4", "FBCCA_nh3", "TRCA", "eCCA_nh3"]
TRAINED = {"TRCA", "eCCA_nh3"}
scores = {m: {} for m in METHODS}
keep_by_L = {}
reject_log = None
E4, keep4, log4 = cut(main_cont, 4.0, occ_idx)            # training epochs for TRCA / templates (full 4 s)
for L in WINDOWS:
    E, keep, log = cut(main_cont, L, occ_idx)
    Eb = [cut(b, L, occ_idx)[0] for b in band_cont]
    keep_by_L[L] = keep
    if L == 4.0:
        reject_log = log
    n = len(rows)
    for m in METHODS:
        scores[m][L] = np.full((n, len(TARGETS)), np.nan)
    kidx = np.where(keep)[0]
    for j, i in enumerate(kidx):
        for nh in (2, 3, 4):
            scores[f"CCA_nh{nh}"][L][i] = cca_scores(E[j], nh)
        scores["FBCCA_nh3"][L][i] = fbcca_scores([b[j] for b in Eb], NH_MAIN)
    # trained methods: leave-one-run-out
    for test_run in (1, 2):
        train_run = 3 - test_run
        tr = keep4 & (run == train_run) & is_tgt
        W, templates = trca_train(E4[np.where(keep4)[0].searchsorted(np.where(tr)[0])], y[tr])
        for j, i in enumerate(kidx):
            if run[i] != test_run:
                continue
            scores["TRCA"][L][i] = trca_scores(E[j], W, templates)
            scores["eCCA_nh3"][L][i] = ecca_scores(E[j], templates, NH_MAIN)

# ----------------------------------------------------------------------------- accuracy tables
acc_rows = []
conf = {}
for m in METHODS:
    for L in WINDOWS:
        S = scores[m][L]
        ok = np.isfinite(S).all(1)
        pred = np.array([TARGETS[k] if o else "" for k, o in zip(np.nanargmax(np.nan_to_num(S, nan=-9), 1), ok)])
        sel = ok & is_tgt
        correct = pred[sel] == y[sel]
        lo, hi = boot_ci(correct)
        r1 = sel & (run == 1); r2 = sel & (run == 2)
        acc_rows.append(dict(method=m, L=L, n=int(sel.sum()), acc=float(correct.mean()), ci_lo=lo, ci_hi=hi,
                             acc_run1=float((pred[r1] == y[r1]).mean()), acc_run2=float((pred[r2] == y[r2]).mean()),
                             itr_T=itr_bits_per_min(float(correct.mean()), 4, L),
                             itr_T_plus1=itr_bits_per_min(float(correct.mean()), 4, L + 1)))
        cm = pd.crosstab(pd.Categorical(y[ok], CLASSES := TARGETS + ["center"]), pd.Categorical(pred[ok], TARGETS), rownames=["true"], colnames=["pred"], dropna=False)
        conf[(m, L)] = cm
acc = pd.DataFrame(acc_rows)
print("\n4-class accuracy (targets only, chance 0.25):")
print(acc.pivot(index="method", columns="L", values="acc").round(3).to_string())
results["accuracy"] = acc.to_dict(orient="records")

# main training-free method
free_4 = acc[(acc.L == 4.0) & acc.method.isin(["CCA_nh3", "FBCCA_nh3"])]
free_mean = acc[acc.method.isin(["CCA_nh3", "FBCCA_nh3"])].groupby("method").acc.mean()
MAIN = free_mean.idxmax()
print("main training-free method (best mean accuracy over windows):", MAIN, free_mean.round(3).to_dict())
results["main_training_free_method"] = MAIN
results["confusion"] = {f"{m}|{L}": conf[(m, L)].values.tolist() for (m, L) in conf}
results["confusion_labels"] = dict(rows=TARGETS + ["center"], cols=TARGETS)

# ----------------------------------------------------------------------------- per-trial table (4 s)
tab = rows[["trial", "run", "detail", "lsl_time", "sample_cnt"]].rename(columns={"detail": "true"}).copy()
tab["kept"] = keep_by_L[4.0]
tab["reject_reason"] = reject_log.reject_reason.values
for m in METHODS:
    S = scores[m][4.0]
    ok = np.isfinite(S).all(1)
    tab[f"pred_{m}_4s"] = np.where(ok, np.array(TARGETS)[np.nanargmax(np.nan_to_num(S, nan=-9), 1)], "")
    if m in (MAIN, "CCA_nh3"):
        for k, t in enumerate(TARGETS):
            tab[f"{m}_score_{t}"] = S[:, k]
tab.to_csv(OUT / "ssvep_trials.csv", index=False)

# ----------------------------------------------------------------------------- center / no-selection rejection
rej = {}
curves = {}
for L in WINDOWS:
    S = scores[MAIN][L]
    ok = np.isfinite(S).all(1)
    pred = np.array(TARGETS)[np.nanargmax(np.nan_to_num(S, nan=-9), 1)]
    feats = reject_features(np.nan_to_num(S, nan=0))
    rej[L] = {}
    curves[L] = {}
    for fname, f in feats.items():
        # leave-one-run-out threshold: smallest threshold that rejects every center trial and every
        # misclassified target trial of the training run
        pooled = dict(center_n=0, center_false=0, tgt_n=0, correct=0, wrong=0, missed=0, thr=[])
        for test_run in (1, 2):
            tr = ok & (run == 3 - test_run)
            te = ok & (run == test_run)
            should_reject = tr & ((y == "center") | (pred != y))
            thr = f[should_reject].max() if should_reject.any() else -np.inf
            accept = f > thr
            c = te & (y == "center")
            t = te & is_tgt
            pooled["center_n"] += int(c.sum()); pooled["center_false"] += int((accept & c).sum())
            pooled["tgt_n"] += int(t.sum())
            pooled["correct"] += int((accept & t & (pred == y)).sum())
            pooled["wrong"] += int((accept & t & (pred != y)).sum())
            pooled["missed"] += int((~accept & t).sum())
            pooled["thr"].append(float(thr))
        rej[L][fname] = dict(false_selection_rate=pooled["center_false"] / pooled["center_n"],
                             wrong_destination_rate=pooled["wrong"] / pooled["tgt_n"],
                             correct_selection_rate=pooled["correct"] / pooled["tgt_n"],
                             missed_selection_rate=pooled["missed"] / pooled["tgt_n"],
                             thresholds_run1_test_run2_test=pooled["thr"][::-1], **{k: v for k, v in pooled.items() if k != "thr"})
        # pooled tradeoff curve (threshold chosen on all data -> optimistic, for the plot only)
        grid = np.unique(np.concatenate([[-np.inf], f[ok]]))
        fsr = []; csr = []; wdr = []
        for thr in grid:
            accept = (f > thr) & ok
            fsr.append((accept & (y == "center")).sum() / (ok & (y == "center")).sum())
            csr.append((accept & is_tgt & (pred == y)).sum() / (ok & is_tgt).sum())
            wdr.append((accept & is_tgt & (pred != y)).sum() / (ok & is_tgt).sum())
        curves[L][fname] = dict(thr=grid.tolist(), false_selection=fsr, correct_selection=csr, wrong_destination=wdr)
        # best pooled operating point with zero false selections and zero wrong destinations (optimistic)
        zero = [(c_, t_) for f_, w_, c_, t_ in zip(fsr, wdr, csr, grid) if f_ == 0 and w_ == 0]
        rej[L][fname]["pooled_zero_error_max_correct_rate"] = max(zero)[0] if zero else 0.0
results["rejection"] = {str(L): v for L, v in rej.items()}
print("\nCenter rejection (LORO thresholds), main method", MAIN)
for L in WINDOWS:
    for fname in ("max", "margin", "rel_margin"):
        r = rej[L][fname]
        print(f"  L={L:.0f}s {fname:10s} false-sel {r['false_selection_rate']:.2f}  wrong-dest {r['wrong_destination_rate']:.2f}  "
              f"correct {r['correct_selection_rate']:.2f}  missed {r['missed_selection_rate']:.2f}  "
              f"(pooled zero-error max correct {r['pooled_zero_error_max_correct_rate']:.2f})")

# ---- null: sliding windows in the eyes-open rest block
ev = A.events
def ev_sample(event):
    r = ev[(ev.block == "rest") & (ev.event == event)].iloc[0]
    return int(r.sample_cnt if np.isfinite(r.sample_cnt) else r.sample_lsl)
eo0, eo1 = ev_sample("eyes_open_start"), ev_sample("eyes_open_end")
ec0, ec1 = ev_sample("eyes_closed_start"), ev_sample("eyes_closed_end")
null = {}
for L in WINDOWS:
    n_win = int(L * FS); step = int(0.5 * FS)
    starts = np.arange(eo0 + int(DELAY * FS), eo1 - n_win, step)
    starts = [s for s in starts if not np.any((A.steps >= s) & (A.steps < s + n_win))]
    if MAIN.startswith("FBCCA"):
        S = np.array([fbcca_scores([b[occ_idx, s:s + n_win] for b in band_cont], NH_MAIN) for s in starts])
    else:
        S = np.array([cca_scores(main_cont[occ_idx, s:s + n_win], NH_MAIN) for s in starts])
    feats = reject_features(S)
    null[L] = {"n_windows": len(starts)}
    for fname, f in feats.items():
        thrs = rej[L][fname]["thresholds_run1_test_run2_test"]
        rates = [float((f > thr).mean()) for thr in thrs]
        null[L][fname] = dict(false_selection_rate_per_fold_threshold=rates, mean=float(np.mean(rates)),
                              would_pick=pd.Series(np.array(TARGETS)[np.argmax(S, 1)]).value_counts().to_dict())
    print(f"  eyes-open null L={L:.0f}s ({len(starts)} windows): false-selection rate "
          + ", ".join(f"{k}={null[L][k]['mean']:.2f}" for k in ("max", "margin", "rel_margin")))
results["null_eyes_open"] = {str(L): v for L, v in null.items()}

# ----------------------------------------------------------------------------- plots
# (i) PSD at Oz per target
fig, ax = plt.subplots(figsize=(11, 5))
oz = OCC.index("Oz")
E, keep, _ = cut(main_cont, 4.0, occ_idx)
cols = {"Bathroom": "C0", "Kitchen": "C1", "Bed": "C2", "Door": "C3", "center": "k"}
psd_tab = {}
for t in TARGETS + ["center"]:
    m = (y[keep] == t)
    f_, p = signal.welch(E[m, oz, :], fs=FS, nperseg=1000, axis=-1)
    pm = p.mean(0)
    psd_tab[t] = (f_, pm)
    ax.semilogy(f_, pm, color=cols[t], label=f"{t} ({FREQS.get(t, 0):.2f} Hz)" if t in FREQS else t)
    if t in FREQS:
        for h in (1, 2, 3):
            ax.axvline(FREQS[t] * h, color=cols[t], lw=.6, ls=":" if h > 1 else "-", alpha=.7)
ax.set_xlim(5, 40); ax.set_ylim(0.1, 20); ax.set_xlabel("Hz"); ax.set_ylabel("PSD (uV^2/Hz)"); ax.legend()
ax.set_title("Session A: trial-averaged Welch PSD at Oz (avg ref, 0.14-4.14 s after flicker_on); lines = f, 2f, 3f")
plt.tight_layout(); plt.savefig(OUT / "fig_ssvep_psd.png", dpi=110); plt.close()
# SNR per target at f (power at f / mean power in ±1 Hz excluding ±0.25 Hz)
snr = {}
for t in TARGETS:
    f_, pm = psd_tab[t]
    for h in (1, 2):
        fh = FREQS[t] * h
        at = pm[np.argmin(np.abs(f_ - fh))]
        nb = pm[(np.abs(f_ - fh) <= 1.0) & (np.abs(f_ - fh) > 0.3)].mean()
        snr[f"{t}_h{h}"] = float(at / nb)
results["oz_psd_snr"] = snr
print("Oz PSD SNR at f / 2f:", {k: round(v, 1) for k, v in snr.items()})

# (ii) accuracy vs L
fig, ax = plt.subplots(figsize=(8, 5))
for k, m in enumerate(METHODS):
    sub = acc[acc.method == m]
    ax.errorbar(sub.L + (k - 2.5) * 0.05, sub.acc, yerr=[sub.acc - sub.ci_lo, sub.ci_hi - sub.acc], marker="o", capsize=3, label=m)
ax.axhline(0.25, color="k", ls="--", lw=.8, label="chance")
ax.set_xlabel("window length (s)"); ax.set_ylabel("4-class accuracy"); ax.set_ylim(0, 1.05); ax.legend(fontsize=8)
ax.set_title("Session A SSVEP: accuracy vs window (bootstrap 95 % CI; TRCA/eCCA = leave-one-run-out)")
plt.tight_layout(); plt.savefig(OUT / "fig_ssvep_accuracy.png", dpi=110); plt.close()

# (iii) confusion matrices (main method)
fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
for ax, L in zip(axes, WINDOWS):
    cm = conf[(MAIN, L)]
    ax.imshow(cm.values, cmap="Blues", vmin=0, vmax=10)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, int(cm.values[i, j]), ha="center", va="center", color="k")
    ax.set_xticks(range(4)); ax.set_xticklabels(TARGETS, rotation=30); ax.set_yticks(range(5)); ax.set_yticklabels(TARGETS + ["center"])
    ax.set_title(f"{MAIN}, L={L:.0f} s"); ax.set_xlabel("predicted"); ax.set_ylabel("true")
plt.tight_layout(); plt.savefig(OUT / "fig_ssvep_confusion.png", dpi=110); plt.close()

# (iv) rejection tradeoff curves
fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
for ax, L in zip(axes, WINDOWS):
    for fname, ls in (("max", "-"), ("margin", "--"), ("rel_margin", ":")):
        c = curves[L][fname]
        ax.plot(c["false_selection"], c["correct_selection"], ls, marker=".", label=f"{fname}: correct")
        ax.plot(c["false_selection"], c["wrong_destination"], ls, marker="x", alpha=.5, label=f"{fname}: wrong dest")
    ax.set_xlabel("false-selection rate (center trials)"); ax.set_ylabel("rate (target trials)"); ax.set_title(f"L={L:.0f} s (pooled)")
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
axes[0].legend(fontsize=7)
plt.tight_layout(); plt.savefig(OUT / "fig_ssvep_rejection.png", dpi=110); plt.close()

# (v) eyes open vs closed PSD at Oz (alpha check)
fig, ax = plt.subplots(figsize=(8, 4.5))
ozc = A.ch.index("Oz")
Xr = rereference(Xn, A.ch, REF, A.bads)
alpha = {}
for name, (s0, s1) in (("eyes open", (eo0, eo1)), ("eyes closed", (ec0, ec1))):
    f_, p = signal.welch(Xr[ozc, s0:s1], fs=FS, nperseg=2000)
    ax.semilogy(f_, p, label=name)
    band = (f_ >= 8) & (f_ <= 12)
    alpha[name] = dict(alpha_power=float(p[band].sum() * (f_[1] - f_[0])), peak_hz=float(f_[band][np.argmax(p[band])]))
ax.set_xlim(2, 40); ax.set_xlabel("Hz"); ax.set_ylabel("PSD (uV^2/Hz)"); ax.legend()
ax.set_title("Session A rest: Oz PSD eyes open vs eyes closed (8-12 Hz alpha check)")
plt.tight_layout(); plt.savefig(OUT / "fig_ssvep_alpha.png", dpi=110); plt.close()
alpha["closed_over_open_ratio"] = alpha["eyes closed"]["alpha_power"] / alpha["eyes open"]["alpha_power"]
results["alpha"] = alpha
print("alpha:", alpha)

# ----------------------------------------------------------------------------- rejection log + summary
rl = reject_log[["trial", "run", "detail", "kept", "reject_reason"]] if "trial" in reject_log else reject_log
rl = rows[["trial", "run", "detail"]].assign(kept=reject_log.kept.values, reason=reject_log.reject_reason.values)
rejected = rl[~rl.kept]
results["rejected_epochs_4s"] = rejected.to_dict(orient="records")
results["n_steps_in_session"] = int(len(A.steps))
# peak-to-peak stats of kept epochs (occipital channels) for the log
ptp = (E.max(-1) - E.min(-1)).max(1)
results["kept_epoch_ptp_uV_occ"] = dict(median=float(np.median(ptp)), max=float(ptp.max()))

json.dump(results, open(OUT / "ssvep_results.json", "w"), indent=1, default=float)

L_ = []
L_.append("# SSVEP (direction) decoder, session A\n")
L_.append(f"Timing source: eego `.cnt` triggers (`sample_cnt`). Visual delay {DELAY} s. Reference: **{REF}** "
          f"(CCA Nh=3, 4 s accuracy by reference: {', '.join(f'{k}={v:.2f}' for k, v in ref_cmp.items())}). "
          f"Channels: {', '.join(OCC)} (all good channels: {chan_cmp}). Bad channels: {A.bads}. "
          f"Filters: 60/120 Hz notch, 5-45 Hz band-pass (CCA/TRCA/eCCA); FBCCA sub-bands {FB_BANDS} (Chebyshev-I order 4, zero-phase).\n")
L_.append(f"Trials: {len(rows)} flicker_on (10 per class, 5 per run). Rejected at 4 s: {len(rejected)}"
          + (":\n" + rejected.to_markdown(index=False) if len(rejected) else " (no step jumps inside any trial; "
             f"{len(A.steps)} step samples in the session, all outside the flicker windows).")
          + f"\nKept-epoch peak-to-peak on the 8 channels: median {np.median(ptp):.0f} uV, max {ptp.max():.0f} uV.\n")
L_.append("## 4-class accuracy (targets only, chance = 0.25)\n")
t = acc.copy()
t["acc (95% CI)"] = t.apply(lambda r: f"{r.acc:.2f} ({r.ci_lo:.2f}-{r.ci_hi:.2f})", axis=1)
t["run1 / run2"] = t.apply(lambda r: f"{r.acc_run1:.2f} / {r.acc_run2:.2f}", axis=1)
t["ITR T=L / T=L+1 (bit/min)"] = t.apply(lambda r: f"{r.itr_T:.1f} / {r.itr_T_plus1:.1f}", axis=1)
L_.append(t[["method", "L", "n", "acc (95% CI)", "run1 / run2", "ITR T=L / T=L+1 (bit/min)"]].to_markdown(index=False))
L_.append("\nCCA/FBCCA are training-free (evaluated on all 40 target trials, split by run for reference); "
          "TRCA and eCCA are trained on one run and tested on the other (pooled over both folds).\n")
L_.append(f"Main training-free method: **{MAIN}** (mean accuracy over windows {free_mean[MAIN]:.2f} vs "
          f"{free_mean.drop(MAIN).iloc[0]:.2f}).\n")
L_.append(f"## Confusion matrices ({MAIN}; rows = true incl. center, cols = predicted)\n")
for Lw in WINDOWS:
    L_.append(f"L = {Lw:.0f} s\n\n" + conf[(MAIN, Lw)].to_markdown() + "\n")
L_.append("## Center / no-selection rejection (threshold chosen on one run, applied to the other; pooled)\n")
rt = []
for Lw in WINDOWS:
    for fname in ("max", "margin", "rel_margin"):
        r = rej[Lw][fname]
        rt.append(dict(L=Lw, feature=fname, false_selection=f"{r['center_false']}/{r['center_n']} ({r['false_selection_rate']:.2f})",
                       wrong_destination=f"{r['wrong']}/{r['tgt_n']} ({r['wrong_destination_rate']:.2f})",
                       correct_selection=f"{r['correct']}/{r['tgt_n']} ({r['correct_selection_rate']:.2f})",
                       missed=f"{r['missed']}/{r['tgt_n']} ({r['missed_selection_rate']:.2f})",
                       eyes_open_null_false_selection=f"{null[Lw][fname]['mean']:.2f} (n={null[Lw]['n_windows']})",
                       pooled_zero_error_max_correct=f"{r['pooled_zero_error_max_correct_rate']:.2f}"))
L_.append(pd.DataFrame(rt).to_markdown(index=False))
L_.append("\n`pooled_zero_error_max_correct` = best correct-selection rate reachable with 0 false selections and 0 wrong "
          "destinations when the threshold is picked on all 50 trials (optimistic upper bound).\n")
L_.append("## Oz PSD SNR (power at f or 2f / neighbouring ±1 Hz)\n")
L_.append(pd.DataFrame([snr]).T.rename(columns={0: "SNR"}).round(1).to_markdown())
L_.append(f"\n## Alpha check\n\nEyes closed / eyes open 8-12 Hz power ratio at Oz = {alpha['closed_over_open_ratio']:.1f}; "
          f"peak {alpha['eyes closed']['peak_hz']:.1f} Hz (closed), {alpha['eyes open']['peak_hz']:.1f} Hz (open).\n")
L_.append("## Interpretation notes\n")
L_.append("- Harmonic overlap: Bed 7.5 Hz x 2 = 15 Hz and Bathroom 12 Hz; Door 6.67 Hz x 2 = 13.3 Hz is next to Kitchen 8.57 Hz x 3 = 25.7 Hz / "
          "Bathroom 12 Hz; Kitchen 8.57 Hz lies inside the alpha band. See the confusion matrices for which pairs actually confuse.\n"
          "- Center trials still see all four squares flicker, so their max correlation is not zero; the rejection table shows how "
          "separable they are from attended targets.\n")
(OUT / "ssvep_summary.md").write_text("\n".join(L_), encoding="utf-8")
print("\nwrote", OUT / "ssvep_summary.md")
