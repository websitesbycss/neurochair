"""Brain-brake decoder, session B.

Danger-vs-harmless from EEG locked to `split` (the moment the object starts to veer), using only
pre-press data (0-0.30 s, fastest RT 299 ms), with the motor confound shown explicitly; EOG
regression trained on the artifact block; side (eye-movement) checks; press-locked beta/mu ERD and
a single-trial 'intent to stop' detector.  Event timing = eego native triggers (timing='cnt').

Run:  PYTHONUTF8=1 .venv/Scripts/python.exe analysis/brake.py
"""
import sys, json, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
from scipy.signal import hilbert
from scipy.fft import next_fast_len
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.metrics import roc_auc_score, balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings("ignore")
mne.set_log_level("ERROR")
sys.path.insert(0, str(Path(__file__).parent))
from prep import (load_session, bandpass, notch, rereference, epoch, eog_proxies, fit_eog_regression,
                  apply_eog_regression, FS, OUT)

RNG = np.random.default_rng(0)
FRONTAL_EOG = ["Fp1", "Fp2", "F9", "F10", "F7", "F8"]
MASTOIDS = ["M1", "M2"]
ERP_CH = ["Fz", "Pz", "F3", "F4", "C3", "P3", "P4"]
WIN_MAIN = [0.20, 0.25, 0.30]
WIN_CONTAM = [0.40, 0.50, 0.80]
BIN_S = 0.025
PTP_THR = 150.0
MEDIAN_RT = 0.394
FASTEST_RT = 0.299
N_BOOT = 2000
results = {}
md = []          # markdown summary lines


def T(df, floatfmt=".3f"):
    """DataFrame -> markdown table (no tabulate dependency)."""
    df = df.copy()
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(format(v, floatfmt) if isinstance(v, (float, np.floating)) and np.isfinite(v) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def boot_ci(y, s, fn, n=N_BOOT, seed=0):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y)); out = []
    for _ in range(n):
        b = rng.choice(idx, len(idx), replace=True)
        if len(np.unique(y[b])) < 2:
            continue
        out.append(fn(y[b], s[b]))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def binned(E, n_bins):
    """Mean amplitude in n_bins consecutive time bins -> (n_trials, n_ch*n_bins)."""
    parts = np.array_split(np.arange(E.shape[-1]), n_bins)
    F = np.stack([E[:, :, p].mean(-1) for p in parts], -1)
    return F.reshape(len(E), -1)


def make_lda():
    return LDA(solver="eigen", shrinkage="auto")


class Pipe:
    """'slda': binned amplitudes -> shrinkage LDA.  'xdawn': xDAWN (fit on train only) -> binned -> sLDA."""

    def __init__(self, kind, n_bins, ch_names, n_comp=3):
        self.kind, self.n_bins, self.ch_names, self.n_comp = kind, n_bins, ch_names, n_comp

    def _xd_epochs(self, E, y):
        info = mne.create_info(self.ch_names, FS, "eeg")
        ev = np.c_[np.arange(len(E)) * (E.shape[-1] + 10), np.zeros(len(E), int), y + 1]
        return mne.EpochsArray(E * 1e-6, info, events=ev, tmin=0.0, event_id={"harmless": 1, "danger": 2}, verbose=False)

    def fit(self, E, y):
        if self.kind == "xdawn":
            ep = self._xd_epochs(E, y)
            self.xd = mne.preprocessing.Xdawn(n_components=self.n_comp, correct_overlap=False).fit(ep)
            Z = self.xd.transform(ep)
        else:
            Z = E
        self.clf = make_lda().fit(binned(Z, self.n_bins), y)
        return self

    def score(self, E):
        Z = self.xd.transform(E * 1e-6) if self.kind == "xdawn" else E
        F = binned(Z, self.n_bins)
        return self.clf.decision_function(F), self.clf.predict(F)


def eval_loro(E, y, run, pipe_fn):
    s = np.full(len(y), np.nan); p = np.zeros(len(y), int); per_run = {}
    for r_test in (1, 2):
        tr, te = run != r_test, run == r_test
        pipe = pipe_fn().fit(E[tr], y[tr])
        s[te], p[te] = pipe.score(E[te])
        per_run[f"train{3 - r_test}_test{r_test}"] = float(roc_auc_score(y[te], s[te]))
    return s, p, per_run


def eval_kfold(E, y, pipe_fn, reps=10, k=5):
    S = np.zeros((reps, len(y))); P = np.zeros((reps, len(y)), int)
    for rep in range(reps):
        for tr, te in StratifiedKFold(k, shuffle=True, random_state=rep).split(E, y):
            pipe = pipe_fn().fit(E[tr], y[tr])
            S[rep, te], P[rep, te] = pipe.score(E[te])
    return S, P


def metrics(y, s, p):
    return dict(auc=float(roc_auc_score(y, s)), bal_acc=float(balanced_accuracy_score(y, p)),
                false_alarm=float(np.mean(p[y == 0] == 1)), hit=float(np.mean(p[y == 1] == 1)),
                auc_ci=boot_ci(y, s, roc_auc_score))


# ============================================================================ data
B = load_session("B")
ch = B.ch
print("bads:", B.bads, " steps after 8 s:", np.round(B.steps[B.steps > 8 * FS] / FS, 2))
CLS_CH = [c for c in ch if c not in B.bads and c not in FRONTAL_EOG and c not in MASTOIDS]
cls_idx = B.idx(CLS_CH)
print("classifier channels:", CLS_CH)

# ---- trial table from the event stream
ev = B.events
trials = []
cur = None
for _, r in ev[ev.block == "brake"].iterrows():
    if r.event == "appear":
        cond, kind, side, idx = r.detail.split("|")
        cur = dict(trial=len(trials) + 1, run=int(r.run), cond=cond, kind=kind, side=int(side), idx=idx,
                   appear_cnt=r.sample_cnt, split_cnt=np.nan, press_cnt=np.nan, rt_ms=np.nan, outcome="",
                   split_lsl=np.nan, press_lsl=np.nan)
        trials.append(cur)
    elif cur is not None:
        if r.event == "split":
            cur["split_cnt"], cur["split_lsl"] = r.sample_cnt, r.sample_lsl
        elif r.event == "brake_press":
            cur["press_cnt"], cur["press_lsl"] = r.sample_cnt, r.sample_lsl
        elif r.event == "rt":
            cur["rt_ms"] = float(r.detail)
        elif r.event == "outcome":
            cur["outcome"] = r.detail.split("|")[1]
tr = pd.DataFrame(trials)
tr["y"] = (tr.cond == "danger").astype(int)
tr["sample_cnt"] = tr.split_cnt; tr["sample_lsl"] = tr.split_lsl
print(tr.groupby(["run", "cond"]).size().to_string())
print("outcomes:", tr.outcome.value_counts().to_dict(), " RT ms: mean %.0f median %.0f min %.0f max %.0f" %
      (tr.rt_ms.mean(), tr.rt_ms.median(), tr.rt_ms.min(), tr.rt_ms.max()))
results["behaviour"] = dict(outcomes=tr.outcome.value_counts().to_dict(), rt_mean=float(tr.rt_ms.mean()),
                            rt_median=float(tr.rt_ms.median()), rt_min=float(tr.rt_ms.min()), rt_max=float(tr.rt_ms.max()))

# ---- filtering + reference + EOG regression
Xf = rereference(bandpass(B.X, FS, 0.5, 30), ch, "avg", B.bads)          # ERP band
Xw = rereference(notch(bandpass(B.X, FS, 1, 45), FS), ch, "avg", B.bads)  # for beta/mu power
art = ev[(ev.block == "artifacts") & (ev.event == "artifact") & ev.detail.isin(["blink", "look_left", "look_right"])]
art = art[np.isfinite(art.sample_cnt)]
mask = np.zeros(Xf.shape[1], bool)
for _, r in art.iterrows():
    s0 = int(r.sample_cnt); mask[s0:s0 + int(2.5 * FS)] = True
print(f"EOG training: {len(art)} artifact epochs ({art.detail.value_counts().to_dict()}), {mask.sum()/FS:.1f} s")
Beog = fit_eog_regression(Xf, ch, mask)
Xc = apply_eog_regression(Xf, ch, Beog)
Beog_w = fit_eog_regression(Xw, ch, mask)
Xwc = apply_eog_regression(Xw, ch, Beog_w)
eog_tab = pd.DataFrame({"ch": ch, "w_VEOG": Beog[:, 0], "w_HEOG": Beog[:, 1]})
results["eog"] = dict(n_train_epochs=int(len(art)), train_s=float(mask.sum() / FS),
                      weights={c: [float(a), float(b)] for c, a, b in zip(ch, Beog[:, 0], Beog[:, 1])})
print("EOG weights (VEOG, HEOG):", {c: np.round(Beog[ch.index(c)], 3).tolist() for c in ("Fz", "Pz", "F7", "F8", "C3")})

# ---- split-locked epochs (-0.2..0.8), reject steps + ptp>150 on classifier channels (EOG-regressed data)
E_c, keep, log = epoch(Xc, tr, "cnt", -0.2, 0.8, steps=B.steps, ptp_thr=PTP_THR, ptp_chans=cls_idx)
E_r, keep_r, log_r = epoch(Xf, tr, "cnt", -0.2, 0.8, steps=B.steps)       # raw (no EOG) version, same trials
E_r = E_r[keep[keep_r]]                                                        # keep_r ⊇ keep
assert E_c.shape == E_r.shape
rej = log[~log.kept][["trial", "run", "cond", "side", "kind", "reject_reason"]]
print(f"split epochs kept {keep.sum()}/{len(keep)}; rejected:\n{rej.to_string() if len(rej) else '  none'}")
results["rejection_split"] = rej.to_dict(orient="records")
t_ep = np.arange(E_c.shape[-1]) / FS - 0.2
i0 = int(0.2 * FS)
E_c = E_c - E_c[:, :, :i0].mean(-1, keepdims=True)
E_r = E_r - E_r[:, :, :i0].mean(-1, keepdims=True)
trk = tr[keep].reset_index(drop=True)
y = trk.y.values; run = trk.run.values; side = trk.side.values
var_removed = 1 - E_c[:, cls_idx].var() / E_r[:, cls_idx].var()
var_removed_ch = 1 - E_c.var((0, 2)) / E_r.var((0, 2))
results["eog"]["variance_removed_classifier_channels"] = float(var_removed)
results["eog"]["variance_removed_per_channel"] = {c: float(v) for c, v in zip(ch, var_removed_ch)}
print(f"EOG regression removed {100*var_removed:.1f}% of variance on classifier channels in split epochs; "
      f"Fz {100*var_removed_ch[ch.index('Fz')]:.0f}%, Pz {100*var_removed_ch[ch.index('Pz')]:.0f}%, F7 {100*var_removed_ch[ch.index('F7')]:.0f}%")

# ============================================================================ 1. ERPs
def ga_ci(E, n=N_BOOT, seed=0):
    rng = np.random.default_rng(seed)
    m = E.mean(0)
    bs = np.stack([E[rng.choice(len(E), len(E), replace=True)].mean(0) for _ in range(n)])
    return m, np.percentile(bs, 2.5, 0), np.percentile(bs, 97.5, 0)


def diff_ci(Ea, Eb, n=N_BOOT, seed=0):
    rng = np.random.default_rng(seed)
    bs = np.stack([Ea[rng.choice(len(Ea), len(Ea), replace=True)].mean(0) - Eb[rng.choice(len(Eb), len(Eb), replace=True)].mean(0)
                   for _ in range(n)])
    return Ea.mean(0) - Eb.mean(0), np.percentile(bs, 2.5, 0), np.percentile(bs, 97.5, 0)


fig, axes = plt.subplots(2, 4, figsize=(18, 8))
axes = axes.ravel()
Ed, Eh = E_c[y == 1], E_c[y == 0]
md_erp = []
for k, c in enumerate(ERP_CH):
    ax = axes[k]; ci = ch.index(c)
    for E_, lab, col in ((Ed, f"danger (n={len(Ed)})", "C3"), (Eh, f"harmless (n={len(Eh)})", "C0")):
        m, lo, hi = ga_ci(E_[:, ci])
        ax.plot(t_ep, m, color=col, label=lab); ax.fill_between(t_ep, lo, hi, color=col, alpha=.2)
    d, lo, hi = diff_ci(Ed[:, ci], Eh[:, ci])
    ax.plot(t_ep, d, "k--", lw=1, label="difference"); ax.fill_between(t_ep, lo, hi, color="k", alpha=.12)
    for x, ls in ((0, "-"), (FASTEST_RT, ":"), (MEDIAN_RT, "--")):
        ax.axvline(x, color="gray", ls=ls, lw=.8)
    ax.axhline(0, color="gray", lw=.5); ax.set_title(f"{c}  (EOG-regressed, avg ref)"); ax.set_xlabel("s from split"); ax.set_ylabel("µV")
    if k == 0:
        ax.legend(fontsize=8)
    # largest |difference| with CI excluding 0 within 0-0.3 s and 0.3-0.8 s
    for lo_t, hi_t, nm in ((0.0, 0.30, "pre_press"), (0.30, 0.80, "post_press")):
        sel = (t_ep >= lo_t) & (t_ep < hi_t)
        sig = sel & ((lo > 0) | (hi < 0))
        j = np.argmax(np.abs(d) * sel)
        md_erp.append(dict(channel=c, window=nm, peak_diff_uV=float(d[j]), peak_t_ms=float(t_ep[j] * 1000),
                           sig_ms=float(sig.sum() / FS * 1000)))
ax = axes[7]
ax.plot(trk.rt_ms[y == 1], np.arange((y == 1).sum()), ".", ms=4); ax.set_title("danger RTs (ms from split)"); ax.set_xlabel("ms")
plt.suptitle("Session B: ERPs locked to `split` (vertical: 0, fastest RT 299 ms, median RT 394 ms)")
plt.tight_layout(); plt.savefig(OUT / "fig_brake_erp.png", dpi=110); plt.close()
erp_df = pd.DataFrame(md_erp)
results["erp_peaks"] = erp_df.to_dict(orient="records")
print(erp_df.round(2).to_string())

# topomaps of danger - harmless
topo_ch = [c for c in ch if c not in B.bads and c not in MASTOIDS]
info_t = mne.pick_info(B.raw.info, mne.pick_channels(B.raw.ch_names, topo_ch, ordered=True))
d_all = Ed.mean(0) - Eh.mean(0)
fig, axes = plt.subplots(2, 4, figsize=(14, 6))
for k, tm in enumerate((0.15, 0.25, 0.35, 0.45)):
    sel = (t_ep >= tm - 0.01) & (t_ep <= tm + 0.01)
    v = d_all[B.idx(topo_ch)][:, sel].mean(-1)
    vlim = np.abs(v).max()
    im, _ = mne.viz.plot_topomap(v, info_t, axes=axes[0, k], show=False, vlim=(-vlim, vlim), contours=4)
    axes[0, k].set_title(f"danger - harmless @ {int(tm*1000)} ms (±{vlim:.1f} µV)")
    # also raw (no EOG regression)
    d_raw = E_r[y == 1].mean(0) - E_r[y == 0].mean(0)
    v2 = d_raw[B.idx(topo_ch)][:, sel].mean(-1); vlim2 = np.abs(v2).max()
    mne.viz.plot_topomap(v2, info_t, axes=axes[1, k], show=False, vlim=(-vlim2, vlim2), contours=4)
    axes[1, k].set_title(f"no EOG regression @ {int(tm*1000)} ms (±{vlim2:.1f} µV)")
plt.suptitle("Danger - harmless difference topographies (top: EOG-regressed; bottom: raw)")
plt.tight_layout(); plt.savefig(OUT / "fig_brake_topo.png", dpi=110); plt.close()

# ERPs by side, before/after EOG regression (lateral frontal + midline)
fig, axes = plt.subplots(2, 4, figsize=(18, 7))
for row, (E_, lab) in enumerate(((E_r, "no EOG regression"), (E_c, "EOG-regressed"))):
    for k, c in enumerate(("F7", "F8", "Fz", "Pz")):
        ax = axes[row, k]; ci = ch.index(c)
        for sd, col in ((-1, "C2"), (1, "C1")):
            for cond, ls in ((1, "-"), (0, "--")):
                sel = (side == sd) & (y == cond)
                ax.plot(t_ep, E_[sel, ci].mean(0), color=col, ls=ls, label=f"{'left' if sd < 0 else 'right'} {'danger' if cond else 'harmless'}")
        ax.axvline(0, color="gray", lw=.8); ax.axvline(FASTEST_RT, color="gray", ls=":", lw=.8); ax.axhline(0, color="gray", lw=.5)
        ax.set_title(f"{c} ({lab})"); ax.set_xlabel("s from split"); ax.set_ylabel("µV")
        if k == 0 and row == 0:
            ax.legend(fontsize=7)
plt.suptitle("ERPs by object side: lateralised eye activity before (top) and after (bottom) EOG regression")
plt.tight_layout(); plt.savefig(OUT / "fig_brake_erp_by_side.png", dpi=110); plt.close()

# ============================================================================ 2. pre-press classifier
def window(E, w):
    return E[:, cls_idx, i0:i0 + int(round(w * FS))]


clf_rows = []
scores_main = {}
for eog_lab, E_src in (("EOG-regressed", E_c), ("no EOG", E_r)):
    for w in WIN_MAIN + WIN_CONTAM:
        Ew = window(E_src, w)
        n_bins = int(round(w / BIN_S))
        for pipe in ("slda", "xdawn"):
            pf = lambda: Pipe(pipe, n_bins, CLS_CH)
            s, p, per_run = eval_loro(Ew, y, run, pf)
            m_loro = metrics(y, s, p)
            S, P = eval_kfold(Ew, y, pf)
            aucs = [roc_auc_score(y, S[r]) for r in range(len(S))]
            s_mean = S.mean(0); p_maj = (P.mean(0) > 0.5).astype(int)
            m_kf = metrics(y, s_mean, p_maj)
            clf_rows.append(dict(eog=eog_lab, window_s=w, contaminated=w > 0.31, pipeline=pipe,
                                 loro_auc=m_loro["auc"], loro_auc_ci=m_loro["auc_ci"], loro_bal_acc=m_loro["bal_acc"],
                                 loro_false_alarm=m_loro["false_alarm"], loro_hit=m_loro["hit"],
                                 loro_train1_test2=per_run["train1_test2"], loro_train2_test1=per_run["train2_test1"],
                                 kfold_auc_mean=float(np.mean(aucs)), kfold_auc_sd=float(np.std(aucs)),
                                 kfold_auc_ci=m_kf["auc_ci"], kfold_bal_acc=m_kf["bal_acc"], kfold_false_alarm=m_kf["false_alarm"]))
            if pipe == "slda" and w == 0.30:
                scores_main[eog_lab] = dict(loro_score=s, loro_pred=p, kfold_score=s_mean, kfold_pred=p_maj)
            print(f"{eog_lab:14s} w={w:.2f} {pipe:6s} LORO AUC {m_loro['auc']:.3f} [{m_loro['auc_ci'][0]:.2f},{m_loro['auc_ci'][1]:.2f}] "
                  f"bacc {m_loro['bal_acc']:.2f} FA {m_loro['false_alarm']:.2f} | 5-fold AUC {np.mean(aucs):.3f}±{np.std(aucs):.3f} "
                  f"bacc {m_kf['bal_acc']:.2f} FA {m_kf['false_alarm']:.2f}")
clf_df = pd.DataFrame(clf_rows)
results["classifier"] = clf_df.to_dict(orient="records")

# timing comparison: same thing with LSL-path timing
E_l, keep_l, _ = epoch(Xc, tr, "lsl", -0.2, 0.8, steps=B.steps, ptp_thr=PTP_THR, ptp_chans=cls_idx)
E_l = E_l - E_l[:, :, :i0].mean(-1, keepdims=True)
yl, runl = tr[keep_l].y.values, tr[keep_l].run.values
s, p, per_run = eval_loro(window(E_l, 0.30), yl, runl, lambda: Pipe("slda", 12, CLS_CH))
m_l = metrics(yl, s, p)
results["timing_lsl_vs_cnt"] = dict(lsl=dict(auc=m_l["auc"], ci=m_l["auc_ci"], per_run=per_run, n=int(len(yl))),
                                    cnt=dict(auc=clf_df[(clf_df.eog == "EOG-regressed") & (clf_df.window_s == 0.30) & (clf_df.pipeline == "slda")].loro_auc.iloc[0]))
print(f"timing check (w=0.3 sLDA EOG LORO): cnt AUC {results['timing_lsl_vs_cnt']['cnt']['auc']:.3f} vs lsl AUC {m_l['auc']:.3f} {per_run}")

# ============================================================================ 3. eye-movement / side checks
side_rows = []
ys = (side > 0).astype(int)
for eog_lab, E_src in (("EOG-regressed", E_c), ("no EOG", E_r)):
    for w in WIN_MAIN:
        Ew = window(E_src, w); n_bins = int(round(w / BIN_S))
        pf = lambda: Pipe("slda", n_bins, CLS_CH)
        s, p, _ = eval_loro(Ew, ys, run, pf)
        S, P = eval_kfold(Ew, ys, pf)
        side_rows.append(dict(eog=eog_lab, channels="classifier set", window_s=w, side_loro_auc=float(roc_auc_score(ys, s)),
                              side_kfold_auc=float(np.mean([roc_auc_score(ys, S[r]) for r in range(len(S))])),
                              side_kfold_ci=boot_ci(ys, S.mean(0), roc_auc_score)))
    # with the frontal channels included (shows that the eyes do follow the object)
    fr_idx = [ch.index(c) for c in ch if c not in B.bads and c not in MASTOIDS]
    for w in (0.30,):
        Ew = E_src[:, fr_idx, i0:i0 + int(round(w * FS))]; n_bins = int(round(w / BIN_S))
        pf = lambda: Pipe("slda", n_bins, [ch[i] for i in fr_idx])
        S, P = eval_kfold(Ew, ys, pf)
        side_rows.append(dict(eog=eog_lab, channels="+ frontal (Fp/F7/F8/F9/F10)", window_s=w, side_loro_auc=np.nan,
                              side_kfold_auc=float(np.mean([roc_auc_score(ys, S[r]) for r in range(len(S))])),
                              side_kfold_ci=boot_ci(ys, S.mean(0), roc_auc_score)))
side_df = pd.DataFrame(side_rows)
print(side_df.round(3).to_string())
results["side_decoding"] = side_df.to_dict(orient="records")

# danger-vs-harmless within each side, and cross-side generalisation (w = 0.30, sLDA)
within_rows = []
for eog_lab, E_src in (("EOG-regressed", E_c), ("no EOG", E_r)):
    Ew = window(E_src, 0.30); pf = lambda: Pipe("slda", 12, CLS_CH)
    s_loro = scores_main[eog_lab]["loro_score"]
    for sd, nm in ((-1, "left"), (1, "right")):
        sel = side == sd
        # LORO predictions restricted to this side, and 5-fold trained within side
        S, P = eval_kfold(Ew[sel], y[sel], pf)
        within_rows.append(dict(eog=eog_lab, test="danger-vs-harmless within %s-side trials" % nm, n=int(sel.sum()),
                                auc_from_loro_model=float(roc_auc_score(y[sel], s_loro[sel])),
                                auc_kfold_within_side=float(np.mean([roc_auc_score(y[sel], S[r]) for r in range(len(S))]))))
    for tr_sd, te_sd in ((-1, 1), (1, -1)):
        trm, tem = side == tr_sd, side == te_sd
        pipe = pf().fit(Ew[trm], y[trm]); s, p = pipe.score(Ew[tem])
        within_rows.append(dict(eog=eog_lab, test=f"train {'left' if tr_sd < 0 else 'right'} -> test {'left' if te_sd < 0 else 'right'}",
                                n=int(tem.sum()), auc_from_loro_model=np.nan, auc_kfold_within_side=float(roc_auc_score(y[tem], s)),
                                false_alarm=float(np.mean(p[y[tem] == 0] == 1))))
within_df = pd.DataFrame(within_rows)
print(within_df.round(3).to_string())
results["side_within_cross"] = within_df.to_dict(orient="records")

# ============================================================================ 4. press-locked analysis
def band_env_log(X, lo, hi):
    Y = bandpass(X, FS, lo, hi)
    n = next_fast_len(Y.shape[-1])
    A = np.abs(hilbert(Y, N=n, axis=-1))[..., :Y.shape[-1]]
    return 10 * np.log10(A ** 2 + 1e-12)


press = ev[(ev.block == "brake") & (ev.event == "brake_press") & np.isfinite(ev.sample_cnt)].copy()
press["cond"] = press.detail.str.split("|").str[0]
pseudo = trk[(trk.y == 0) & ~np.isfinite(trk.press_cnt)].copy()
pseudo["sample_cnt"] = pseudo.split_cnt + round(MEDIAN_RT * FS)
pseudo["sample_lsl"] = pseudo.split_lsl + round(MEDIAN_RT * FS)
pow_ch = ["C3", "F3", "P3", "F4", "P4"]
pow_idx = B.idx(pow_ch)
Lbeta = band_env_log(Xwc, 13, 30)
Lmu = band_env_log(Xwc, 8, 13)
Ep_b, kp, logp = epoch(Lbeta, press, "cnt", -1.0, 0.5, steps=B.steps)
Ep_m, _, _ = epoch(Lmu, press, "cnt", -1.0, 0.5, steps=B.steps)
Eq_b, kq, logq = epoch(Lbeta, pseudo, "cnt", -1.0, 0.5, steps=B.steps)
Eq_m, _, _ = epoch(Lmu, pseudo, "cnt", -1.0, 0.5, steps=B.steps)
print(f"press-locked epochs: {kp.sum()}/{len(kp)} presses, {kq.sum()}/{len(kq)} harmless pseudo-presses;"
      f" rejected press: {logp[~logp.kept].reject_reason.tolist()}, pseudo: {logq[~logq.kept].reject_reason.tolist()}")
results["rejection_press"] = dict(press=logp[~logp.kept][["detail", "reject_reason"]].to_dict(orient="records"),
                                  pseudo=logq[~logq.kept][["trial", "reject_reason"]].to_dict(orient="records"),
                                  n_press_kept=int(kp.sum()), n_pseudo_kept=int(kq.sum()))
t_p = np.arange(Ep_b.shape[-1]) / FS - 1.0
bl = (t_p >= -1.0) & (t_p < -0.8)


def rel(E):
    return E - E[:, :, bl].mean(-1, keepdims=True)


fig, axes = plt.subplots(2, 5, figsize=(20, 7))
erd_rows = []
for row, (Ep, Eq, band) in enumerate(((Ep_b, Eq_b, "beta 13-30 Hz"), (Ep_m, Eq_m, "mu 8-13 Hz"))):
    Rp, Rq = rel(Ep), rel(Eq)
    for k, c in enumerate(pow_ch):
        ax = axes[row, k]; ci = ch.index(c)
        m, lo, hi = ga_ci(Rp[:, ci]); ax.plot(t_p, m, "C3", label=f"press-locked (n={len(Rp)})"); ax.fill_between(t_p, lo, hi, color="C3", alpha=.2)
        m2, lo2, hi2 = ga_ci(Rq[:, ci]); ax.plot(t_p, m2, "C0", label=f"harmless pseudo-press (n={len(Rq)})"); ax.fill_between(t_p, lo2, hi2, color="C0", alpha=.2)
        ax.axvline(0, color="k", lw=.8); ax.axhline(0, color="gray", lw=.5); ax.set_title(f"{c} {band}"); ax.set_xlabel("s from (pseudo-)press"); ax.set_ylabel("dB vs -1.0..-0.8 s")
        if k == 0:
            ax.legend(fontsize=7)
        # ERD onset: first time in [-0.8, 0] where upper CI < 0 for >= 50 ms (press-locked)
        below = (hi < 0) & (t_p >= -0.8) & (t_p <= 0.1)
        onset = np.nan
        run_len = int(0.05 * FS)
        for j in range(len(below) - run_len):
            if below[j:j + run_len].all():
                onset = t_p[j]; break
        # and difference press vs pseudo
        d, dlo, dhi = diff_ci(Rp[:, ci], Rq[:, ci])
        sel = (t_p >= -0.5) & (t_p <= 0)
        erd_rows.append(dict(band=band, channel=c, erd_onset_ms_before_press=float(-onset * 1000) if np.isfinite(onset) else np.nan,
                             min_dB_pre_press=float(m[sel].min()), min_t_ms=float(t_p[sel][np.argmin(m[sel])] * 1000),
                             press_minus_pseudo_dB_at_0=float(d[np.argmin(np.abs(t_p))]),
                             press_minus_pseudo_sig_ms_pre=float(((dhi < 0) & sel).sum() / FS * 1000)))
plt.suptitle("Press-locked band power (EOG-regressed, avg ref; C4 and Cz excluded as bad)")
plt.tight_layout(); plt.savefig(OUT / "fig_brake_press_power.png", dpi=110); plt.close()
erd_df = pd.DataFrame(erd_rows)
print(erd_df.round(2).to_string())
results["erd"] = erd_df.to_dict(orient="records")

# TFR at C3: press vs pseudo-press
Ewp, _, _ = epoch(Xwc, press, "cnt", -1.0, 0.5, steps=B.steps)
Ewq, _, _ = epoch(Xwc, pseudo, "cnt", -1.0, 0.5, steps=B.steps)
freqs = np.arange(4, 41, 1.0)
fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
tfrs = []
for k, (E_, lab) in enumerate(((Ewp, "press-locked"), (Ewq, "harmless pseudo-press"))):
    P = mne.time_frequency.tfr_array_morlet(E_[:, [ch.index("C3")], :] * 1e-6, sfreq=FS, freqs=freqs, n_cycles=freqs / 2,
                                            output="avg_power", zero_mean=True)[0]
    Pdb = 10 * np.log10(P / P[:, bl].mean(-1, keepdims=True))
    tfrs.append(Pdb)
    im = axes[k].imshow(Pdb, aspect="auto", origin="lower", extent=[t_p[0], t_p[-1], freqs[0], freqs[-1]], cmap="RdBu_r", vmin=-3, vmax=3)
    axes[k].axvline(0, color="k"); axes[k].set_title(f"C3 {lab} (dB vs -1.0..-0.8 s)"); axes[k].set_xlabel("s"); axes[k].set_ylabel("Hz")
    plt.colorbar(im, ax=axes[k])
im = axes[2].imshow(tfrs[0] - tfrs[1], aspect="auto", origin="lower", extent=[t_p[0], t_p[-1], freqs[0], freqs[-1]], cmap="RdBu_r", vmin=-3, vmax=3)
axes[2].axvline(0, color="k"); axes[2].set_title("difference press - pseudo (dB)"); axes[2].set_xlabel("s"); plt.colorbar(im, ax=axes[2])
plt.tight_layout(); plt.savefig(OUT / "fig_brake_tfr_c3.png", dpi=110); plt.close()

# single-trial intent detector: log beta/mu power in [-0.3, 0] at C3, F3, P3 (absolute and baseline-relative)
det_idx = B.idx(["C3", "F3", "P3"])
win = (t_p >= -0.3) & (t_p < 0)


def det_feats(Eb, Em, relative):
    Rb, Rm = (rel(Eb), rel(Em)) if relative else (Eb, Em)
    return np.c_[Rb[:, det_idx][:, :, win].mean(-1), Rm[:, det_idx][:, :, win].mean(-1)]


yd = np.r_[np.ones(len(Ep_b), int), np.zeros(len(Eq_b), int)]
run_d = np.r_[press[kp].run.values.astype(int), pseudo[kq].run.values.astype(int)]
det_rows = []
for relative in (False, True):
    F = det_feats(np.r_[Ep_b, Eq_b], np.r_[Ep_m, Eq_m], relative)
    s = np.full(len(yd), np.nan); p = np.zeros(len(yd), int); pr = {}
    for r_test in (1, 2):
        trm, tem = run_d != r_test, run_d == r_test
        clf = make_lda().fit(F[trm], yd[trm]); s[tem] = clf.decision_function(F[tem]); p[tem] = clf.predict(F[tem])
        pr[f"train{3-r_test}_test{r_test}"] = float(roc_auc_score(yd[tem], s[tem]))
    m_loro = metrics(yd, s, p)
    S = np.zeros((10, len(yd))); P = np.zeros((10, len(yd)), int)
    for rep in range(10):
        for trm, tem in StratifiedKFold(5, shuffle=True, random_state=rep).split(F, yd):
            clf = make_lda().fit(F[trm], yd[trm]); S[rep, tem] = clf.decision_function(F[tem]); P[rep, tem] = clf.predict(F[tem])
    aucs = [roc_auc_score(yd, S[r]) for r in range(10)]
    m_kf = metrics(yd, S.mean(0), (P.mean(0) > 0.5).astype(int))
    det_rows.append(dict(features=("baseline-relative" if relative else "absolute") + " log beta+mu power C3/F3/P3, -0.3..0 s",
                         loro_auc=m_loro["auc"], loro_auc_ci=m_loro["auc_ci"], loro_per_run=pr, loro_bal_acc=m_loro["bal_acc"],
                         loro_false_alarm=m_loro["false_alarm"], kfold_auc=float(np.mean(aucs)), kfold_auc_sd=float(np.std(aucs)),
                         kfold_auc_ci=m_kf["auc_ci"], kfold_bal_acc=m_kf["bal_acc"], kfold_false_alarm=m_kf["false_alarm"]))
det_df = pd.DataFrame(det_rows)
print(det_df.round(3).to_string())
results["intent_detector"] = det_df.to_dict(orient="records")

# ============================================================================ outputs
tri = trk.copy()
for eog_lab in ("EOG-regressed", "no EOG"):
    key = "eog" if eog_lab == "EOG-regressed" else "raw"
    tri[f"loro_score_{key}"] = scores_main[eog_lab]["loro_score"]; tri[f"loro_pred_{key}"] = scores_main[eog_lab]["loro_pred"]
    tri[f"kfold_score_{key}"] = scores_main[eog_lab]["kfold_score"]; tri[f"kfold_pred_{key}"] = scores_main[eog_lab]["kfold_pred"]
tri["rejected"] = False
rej_full = tr[~keep].copy(); rej_full["rejected"] = True; rej_full["reject_reason"] = log[~log.kept].reject_reason.values
tri = pd.concat([tri, rej_full]).sort_values("trial")
tri.to_csv(OUT / "brake_trials.csv", index=False)
json.dump(results, open(OUT / "brake_results.json", "w"), indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))

# ---------------------------------------------------------------- markdown summary
L = md
L.append("# Brake decoder (session B) — summary\n")
L.append(f"Data: session B LSL stream (sample-identical to the .cnt), event timing from eego triggers. "
         f"Bad channels: {B.bads} (C4 1965 kΩ, Cz 6539 kΩ, M2 1857 kΩ impedance before session B). "
         f"Band-pass 0.5–30 Hz (zero-phase, offline), average reference over good non-mastoid channels. "
         f"Classifier channels ({len(CLS_CH)}): {', '.join(CLS_CH)} (frontal EOG proxies and mastoids excluded).\n")
L.append(f"Behaviour: {results['behaviour']['outcomes']}; RT mean {results['behaviour']['rt_mean']:.0f} ms, median {results['behaviour']['rt_median']:.0f}, "
         f"range {results['behaviour']['rt_min']:.0f}–{results['behaviour']['rt_max']:.0f} ms.\n")
L.append("## Epoch rejection (split-locked, −0.2…0.8 s)\n")
L.append(f"Kept {keep.sum()}/{len(keep)} trials. Rules: step jump >2000 µV within ±0.25 s, peak-to-peak >150 µV on classifier channels, first 8 s.\n")
L.append(T(rej) if len(rej) else "No split-locked epochs rejected.")
L.append("\n## EOG regression\n")
L.append(f"Weights fitted on {len(art)} artifact-block epochs ({art.detail.value_counts().to_dict()}, {mask.sum()/FS:.0f} s). "
         f"VEOG proxy = mean(Fp1,Fp2), HEOG proxy = F9−F10 (both after average reference).\n")
L.append(T(eog_tab[eog_tab.ch.isin(["Fz", "Pz", "F3", "F4", "C3", "P3", "P4", "F7", "F8", "Fp1"])]))
L.append(f"\nVariance removed in split epochs on classifier channels: {100*var_removed:.1f} % "
         f"(Fz {100*var_removed_ch[ch.index('Fz')]:.0f} %, Pz {100*var_removed_ch[ch.index('Pz')]:.0f} %, F7 {100*var_removed_ch[ch.index('F7')]:.0f} %, "
         f"F8 {100*var_removed_ch[ch.index('F8')]:.0f} %).\n")
L.append("## ERP peaks (danger − harmless, EOG-regressed)\n")
L.append(T(erp_df.round(2)))
L.append("\n(sig_ms = ms within the window where the bootstrap 95 % CI of the difference excludes 0.) Figures: fig_brake_erp.png, fig_brake_topo.png, fig_brake_erp_by_side.png\n")
L.append("## Pre-press classifier: danger vs harmless from `split`\n")
L.append("Windows 0.20/0.25/0.30 s end before the fastest RT (299 ms); 0.40/0.50/0.80 s are **contaminated by the motor response** and shown only to expose the confound. "
         "LORO = train one run, test the other (pooled over both directions). 5-fold = stratified, 10 repeats (AUC mean ± sd over repeats; CI = bootstrap on per-trial mean scores). "
         "bal_acc / false-alarm use the LDA threshold learned on the training fold.\n")
show = clf_df.copy()
show["loro_auc_ci"] = show.loro_auc_ci.apply(lambda c: f"[{c[0]:.2f}, {c[1]:.2f}]")
show["kfold_auc"] = show.apply(lambda r: f"{r.kfold_auc_mean:.3f} ± {r.kfold_auc_sd:.3f}", axis=1)
show["kfold_auc_ci"] = show.kfold_auc_ci.apply(lambda c: f"[{c[0]:.2f}, {c[1]:.2f}]")
L.append(T(show[["eog", "window_s", "contaminated", "pipeline", "loro_auc", "loro_auc_ci", "loro_train1_test2", "loro_train2_test1",
                 "loro_bal_acc", "loro_false_alarm", "loro_hit", "kfold_auc", "kfold_auc_ci", "kfold_bal_acc", "kfold_false_alarm"]].round(3)))
L.append(f"\nTiming source check (w = 0.30 s, sLDA, EOG-regressed, LORO): eego-trigger timing AUC {results['timing_lsl_vs_cnt']['cnt']['auc']:.3f} "
         f"vs LSL-path timing AUC {m_l['auc']:.3f} [{m_l['auc_ci'][0]:.2f}, {m_l['auc_ci'][1]:.2f}] ({per_run}).\n")
L.append("## Eye-movement (side) checks\n")
sshow = side_df.copy(); sshow["side_kfold_ci"] = sshow.side_kfold_ci.apply(lambda c: f"[{c[0]:.2f}, {c[1]:.2f}]")
L.append(T(sshow.round(3)))
L.append("\nDanger-vs-harmless within one side and across sides (w = 0.30 s, sLDA):\n")
L.append(T(within_df.round(3)))
L.append("\n## Press-locked analysis\n")
L.append(f"Epochs −1.0…+0.5 s around `brake_press` (n = {kp.sum()}) vs harmless trials aligned to split + 394 ms (pseudo-press, n = {kq.sum()}). "
         f"Rejected: press {logp[~logp.kept].reject_reason.tolist()}, pseudo {logq[~logq.kept].reject_reason.tolist()}. "
         "Log band power (Hilbert envelope of 13–30 Hz and 8–13 Hz, data band-passed 1–45 Hz, notched, EOG-regressed) relative to −1.0…−0.8 s. "
         "C4 and Cz are bad (impedance), so the right-hemisphere motor channel is missing; F3/P3/F4/P4 serve as neighbours.\n")
L.append(T(erd_df.round(2)))
L.append("\n(erd_onset = first time the upper 95 % CI of the press-locked curve stays below 0 for ≥50 ms; press_minus_pseudo_sig_ms_pre = ms in −0.5…0 s where the press−pseudo difference CI excludes 0.) Figures: fig_brake_press_power.png, fig_brake_tfr_c3.png\n")
L.append("Single-trial intent detector (press vs harmless pseudo-press):\n")
dshow = det_df.copy()
for c in ("loro_auc_ci", "kfold_auc_ci"):
    dshow[c] = dshow[c].apply(lambda c: f"[{c[0]:.2f}, {c[1]:.2f}]")
L.append(T(dshow.round(3)))
(OUT / "brake_summary.md").write_text("\n".join(L), encoding="utf-8")
print("\nwrote", OUT / "brake_summary.md")
