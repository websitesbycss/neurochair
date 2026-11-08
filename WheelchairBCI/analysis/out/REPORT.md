# Wheelchair BCI, subject S1, 2026-11-07: decoding report

Code: `analysis/` (run `PYTHONUTF8=1 .venv/Scripts/python.exe analysis/run_all.py` from the project folder). All numbers below come from `analysis/out/*.json|csv|md`; figures are in `analysis/out/fig_*.png`.

## 1. Files, alignment of the eego `.cnt` to the LSL stream

**What the native files contain**

- `.cnt`: RF64 "CNT eeph" file, 24 channels, 500 Hz, 488 640 samples (977.28 s), calibration 0.0078125 µV/LSB, **reference CPz, units µV** (so the LSL stream, which is sample-identical, is in µV too). Loaded with `mne.io.read_raw_ant` (antio). No separate trigger channel; the triggers are embedded and come out as MNE annotations.
- `.evt`: 533 serialised records: 2 impedance checks (one at recording start 23:28:42.10 UTC = 18:28:42 local, one at 23:37:24.71 UTC during the pause between sessions) and **531 LSL markers from the stimulus PC's `WheelchairMarkers` stream**, i.e. the eego software recorded the CSV events itself. Each record carries an eego-clock timestamp (OLE date with integer seconds + fractional second). Parsed by `wc_io.parse_evt`.
- `.seg`: two segments. The number in it (227 330) is the **length of the last segment**, not its start index: segment 1 = samples 0–261 309 (522.62 s, ends exactly at the 2nd impedance check), segment 2 = samples 261 310–488 639 (454.66 s, starts 23:37:47.62 UTC). Verified by the trigger positions (eego-clock prediction vs embedded trigger: residual −0.3 to −0.9 samples for all 530 triggers under this interpretation, ~27 000 samples under the other).

**Cross-correlation alignment** (`align.py`, Fz 1–40 Hz, then per-10-s-chunk lags, then a raw sample-identity scan):

| session | cnt segment | lag (cnt sample = LSL sample + lag) | identical samples | drift / dropouts |
|---|---|---|---|---|
| A (182835) | 1 | −4123 (−8.246 s) | 100 % (std ratio 1.00000) | none: lag constant in every chunk |
| B (183742) | 2 | −3611 (−7.222 s) | 100 % | none |

The jaw-clench bursts (20–100 Hz envelope on F7/F8/T7/T8) land at the same lag in both files (fig_alignment.png). **Conclusion: the LSL stream lost no samples; the two files are the same data.** The 499.0 Hz implied by the LSL timestamps is the stimulus PC's clock-sync estimate, not missing samples.

**Coverage.** The `.cnt` starts 8.25 s into session A (it misses only amplifier settling) and 7.22 s into session B (just before the first clench cue at 9.2 s). It ends at the same instant as the session-B LSL stream, because the eego recording was stopped then. So the last 4 artifact trials and the final sync block are **not recoverable from any file**; 16 of 20 artifact trials are available in both.

**Event timing: the eego triggers are right, the LSL-path mapping is not (early in each recording).** The difference between the CSV→`np.searchsorted(timestamps)` sample and the eego trigger sample is a smooth curve that starts at −300 ms and decays to ~0 with a ~90 s time constant (fig_alignment.png middle row): session A sync/rest −310…+148 ms, SSVEP −44…+42 ms (sd 15 ms); session B brake run 1 −294…−20 ms, run 2 ≈ 0 ms, artifact block +6 ms. That is the signature of liblsl's `proc_dejitter` regression converging on the recording PC (its default smoothing half-time is 90 s), not of network latency in the eego path. Objective test (`timing_check.py`):

| test | LSL-path timing | eego-trigger timing |
|---|---|---|
| SSVEP inter-trial phase coherence at 2f (O1/Oz/O2), Bathroom / Kitchen / Bed / Door | 0.26 / 0.60 / 0.65 / 0.69 | **0.68 / 0.85 / 0.85 / 0.75** |
| same at f | 0.69 / 0.42 / 0.52 / 0.54 | **0.85 / 0.49 / 0.54 / 0.55** |
| flicker_on VEP, Oz grand-average peak | 3.8 µV | **5.0 µV** |
| `appear` VEP, Oz peak, brake run 1 / run 2 | 4.0 / 6.1 µV | **6.8 / 6.2 µV** |

(ITPC null with ±200 ms jitter: mean 0.30, 95th pct 0.47.) Run 2 of the brake session, where the LSL error had converged, gives the same VEP from both sources; run 1 does not. **All decoding below uses the eego trigger positions** (`events.sample_cnt`), mapped onto the LSL sample grid with the lags above. The EEG samples themselves are taken from the `.npz` (identical to the `.cnt`).

Deliverable 1 loaders: `wc_io.load_lsl_session()` (npz + CSV → `mne.io.RawArray`, labels normalised to standard_1020, Trigger dropped, Cz marked bad, CSV annotations) and `wc_io.load_cnt_session()` (the `.cnt` segment of a session, with `trig/...` annotations from the native triggers and `csv/...` annotations from the CSV mapped with the lag). `wc_io.parse_evt/parse_seg` read the eego sidecar files.

## 2. Preprocessing summary

Full tables in `preprocessing_summary.md`.

- **Units**: µV (from the `.cnt` header). DC offsets −47 000…+63 000 µV removed per channel.
- **Bad channels, both sessions: Cz, C4, M2.** Impedance at the start of A / B: Cz 2 092 / 6 539 kΩ, C4 2 815 / 1 965 kΩ, M2 187 / 1 857 kΩ; 1–40 Hz std of Cz 168 / 266 µV, M2 111 / 61 µV (median channel 15 µV). M1 (83 / 142 kΩ, std 64 / 74 µV) and P7 (259 / 538 kΩ) are noisy but kept. Consequence: a linked-mastoid reference is not available (M2 is bad); the "mastoid" option below is M1 alone, and the central motor channel C4 is unusable.
- **Settling**: first 8 s of each recording excluded. **Step jumps** (> 2000 µV/sample on a good channel): session A 45 samples, all at 6–8.2 s, 333.0 s (between runs) and 524 s (end sync); session B 157 samples, all before 7.3 s. No decoding epoch contained one.
- **Filters** (all zero-phase offline): 60 + 120 Hz IIR notch (Q 30); SSVEP 5–45 Hz Butterworth order 4, FBCCA sub-bands [5,50] [13,50] [21,50] [29,50]; brake 0.5–30 Hz.
- **Reference**: average of the good non-mastoid channels (chosen: SSVEP CCA 4 s accuracy 0.875 vs 0.85 with CPz as recorded vs 0.825 with M1).
- **Epochs rejected**: SSVEP 0 / 50. Brake: see section 4.

## 3. Direction decoder (SSVEP, session A)

Setup: 8 channels O1 Oz O2 P3 Pz P4 P7 P8 (all 21 good channels did worse: 0.825 vs 0.875), windows start 0.14 s after `flicker_on`, L = 1/2/3/4 s (4 s = 0.14–4.14 s). 50 trials, 10 per class, 5 per run. CCA/FBCCA are training-free; TRCA and extended CCA (eCCA = template + sine references) are trained on one run and tested on the other (leave-one-run-out, both directions pooled). Chance = 25 % for the 4 targets.

**4-class accuracy on the 40 target trials, bootstrap 95 % CI, run1 / run2**

| method | 1 s | 2 s | 3 s | 4 s |
|---|---|---|---|---|
| CCA, 3 harmonics (main training-free) | 0.40 (0.25–0.55) 0.55/0.25 | 0.50 (0.35–0.65) 0.55/0.45 | 0.75 (0.62–0.88) 0.70/0.80 | **0.875 (0.75–0.95)** 0.85/0.90 |
| CCA, 2 / 4 harmonics | 0.40 / 0.425 | 0.475 / 0.50 | 0.725 / 0.775 | 0.875 / 0.90 |
| FBCCA, 3 harmonics | 0.40 | 0.425 | 0.675 | 0.85 |
| TRCA (ensemble), LORO | 0.55 (0.40–0.70) 0.65/0.45 | 0.725 (0.57–0.85) 0.75/0.70 | 0.85 (0.72–0.95) 0.90/0.80 | **0.90 (0.80–0.97)** 0.95/0.85 |
| eCCA, LORO | 0.575 (0.42–0.72) | 0.55 (0.40–0.70) | 0.775 (0.65–0.90) | **0.925 (0.82–1.00)** 0.90/0.95 |

ITR (bits/min, selection time T = L / T = L + 1 s for cue and gap): CCA 4.7/2.3, 6.2/4.2, 15.8/11.9, 18.9/15.1 for 1–4 s; TRCA 17.6/8.8, 21.5/14.3, 23.0/17.3, 20.6/16.5; eCCA at 4 s 22.5/18.0.

**Confusion matrix, CCA 3 harmonics, 4 s (rows = true):**

| true \ predicted | Bathroom 12 Hz | Kitchen 8.57 | Bed 7.5 | Door 6.67 |
|---|---|---|---|---|
| Bathroom | **10** | 0 | 0 | 0 |
| Kitchen | 1 | **9** | 0 | 0 |
| Bed | 2 | 0 | **8** | 0 |
| Door | 2 | 0 | 0 | **8** |
| center (no target) | 7 | 2 | 0 | 1 |

Every error at 3–4 s is a false "Bathroom". The trial-averaged Oz spectrum (fig_ssvep_psd.png) shows why: the subject's eyes-open alpha peak sits at 11.25 Hz, 0.75 Hz from the 12 Hz target, and it is present in every condition including center; the SSVEP peaks themselves are weak (Oz SNR at f 0.9–1.7, at 2f 1.4–2.4; Kitchen and Door are detected mainly through their second harmonics at 17.1 and 13.3 Hz). The anticipated 7.5 × 2 = 15 Hz vs 12 Hz confusion does not show up: Bed is never predicted as Bathroom's neighbour, but Bed/Door trials with a weak response fall onto the alpha-boosted 12 Hz reference. Eyes-closed/eyes-open alpha ratio 5.4 (fig_ssvep_alpha.png), so the rest blocks are a usable alpha baseline.

**"Center / no selection" rule** (`fig_ssvep_rejection.png`). Features: max CCA correlation ρ1, margin ρ1−ρ2, relative margin. Threshold chosen on one run (to reject all of its center and misclassified trials), applied to the other, pooled over 10 center + 40 target trials; also applied to sliding windows of the eyes-open rest block as a null:

| L | feature | false selection (center → destination) | wrong destination | correct selection | missed | rest-block false selection |
|---|---|---|---|---|---|---|
| 4 s | max ρ | 1/10 | 0/40 | 15/40 (38 %) | 62 % | 38 % of 112 windows |
| 4 s | margin | 3/10 | 0/40 | 14/40 | 65 % | 31 % |
| 3 s | rel. margin | 1/10 | 0/40 | 12/40 | 70 % | 30 % |
| 2 s | max ρ | 1/10 | 0/40 | 6/40 | 85 % | 29 % |
| 1 s | any | 0/10 | 1–2/40 | ≤ 4/40 | ≥ 88 % | 17–24 % |

Even with the threshold tuned on all 50 trials (optimistic), zero wrong/false selections at 4 s is only reachable while accepting 35 % of target trials. Center trials are not separable by correlation strength: all four squares flicker during a center trial and the alpha peak feeds the 12 Hz reference, so 7 of 10 center trials look like a confident "Bathroom". A correlation threshold therefore buys safety only at the price of rejecting ~2/3 of real selections.

## 4. Brain brake (session B)

Full tables in `brake_summary.md`, figures `fig_brake_*.png`, per-trial scores in `brake_trials.csv`.

**Setup.** Eego-trigger timing, 0.5–30 Hz, average reference over good non-mastoid channels, bads Cz/C4/M2. Classifier channels (14): F3 Fz F4 T7 C3 T8 P7 P3 Pz P4 P8 Oz O1 O2 (the six frontal EOG proxies and the mastoids are excluded so that eye movements cannot drive the classifier). Behaviour: 40/40 danger stopped, 39/40 harmless passed, 1 false stop; RT from `split` mean 394 ms, median 384, range 299–636 ms.

**Epochs rejected** (split-locked, −0.2…0.8 s, baseline −0.2…0): 3 of 80, all for peak-to-peak > 150 µV on classifier channels: trial 34 (run 1, danger, right, cart, 160 µV), trial 38 (run 1, harmless, left, cart, 159 µV), trial 42 (run 2, danger, left, ball, 156 µV). No step jumps after 8 s in session B. Press-locked: 41/41 presses and 38/38 harmless pseudo-presses kept.

**EOG regression.** Weights fitted on the 12 usable artifact-block epochs (5 look_left, 4 look_right, 3 blink, 30 s of data; VEOG = mean(Fp1, Fp2), HEOG = F9−F10). It removes only 6 % of the variance on the classifier channels (F8 29 %, F7 15 %, Pz 6 %; at Fz it adds noise), and changes no result materially: pre-press AUC at 0.30 s is 0.67 with and 0.69 without it. Side (left/right) is not decodable from the classifier channels in any pre-press window: AUC 0.52–0.56 with, 0.54–0.59 without regression, 0.48/0.54 with the frontal channels added (all CIs include 0.5). So horizontal eye movements are not what the decoder sees in the first 300 ms.

**ERPs (fig_brake_erp.png, fig_brake_topo.png).** Before the fastest press (< 300 ms after `split`) there is no reliable danger-vs-harmless difference: the longest stretch where the bootstrap CI of the difference excludes zero is 46 ms (P3, −3.7 µV at 278 ms); Fz shows nothing at N2 latency. After the press the difference is large and classic: fronto-central negativity at Fz/F4 (−6.9 µV at 368–372 ms, i.e. at the median RT), then a parietal P3 at Pz (+6.7 µV peaking at 618 ms, CI-significant for 270 ms), P4 (+4.7 µV at 516 ms) and C3 (+4.5 µV at 488 ms). These components coincide with or follow the hand press, so they are decision/motor/feedback related rather than early perception.

**Pre-press classifier (shrinkage LDA on 25 ms bins, EOG-regressed):**

| window after `split` | LORO AUC (95 % CI) | train 1→2 / 2→1 | balanced acc. | false alarms (harmless) | hits (danger) | 5-fold ×10 AUC |
|---|---|---|---|---|---|---|
| 0–0.20 s | 0.56 (0.42–0.69) | 0.52 / 0.59 | 0.54 | 33 % | 42 % | 0.56 ± 0.03 |
| 0–0.25 s | 0.60 (0.46–0.73) | 0.57 / 0.62 | 0.60 | 33 % | 53 % | 0.58 ± 0.04 |
| **0–0.30 s** | **0.67 (0.54–0.79)** | 0.66 / 0.69 | 0.58 | 31 % | 47 % | 0.63 ± 0.06 |
| 0–0.40 s, *contains the press* | 0.76 (0.65–0.86) | 0.73 / 0.77 | 0.74 | 18 % | 66 % | 0.74 ± 0.04 |
| 0–0.50 s, *contains the press* | 0.76 (0.65–0.86) | 0.71 / 0.81 | 0.73 | 21 % | 66 % | 0.79 ± 0.04 |
| 0–0.80 s, *contains the press* | 0.80 (0.69–0.89) | 0.84 / 0.76 | 0.77 | 10 % | 63 % | 0.80 ± 0.02 |

xDAWN (3 components) + LDA is worse pre-press (0.51 / 0.52 / 0.59) and 0.72–0.75 once the press is inside the window. The jump from 0.67 to 0.76–0.80 as soon as the window reaches the press is the motor confound made visible: a classifier trained on the usual 0–0.8 s window would mostly learn the hand movement and its P3. Within-side AUC at 0.30 s is 0.68–0.75 (left) and 0.60–0.65 (right); training on one side and testing on the other gives 0.59 and 0.49, so the small pre-press effect does not generalise across sides, which is another reason to call it weak. With the LSL-path timing instead of the eego triggers the same 0.30 s classifier drops to AUC 0.53.

**Press-locked motor activity (fig_brake_press_power.png, fig_brake_tfr_c3.png).** Epochs −1.0…+0.5 s around the 41 presses vs harmless trials aligned to `split` + 394 ms. C4 and Cz are bad, so only the left motor region (C3, with F3/P3 and F4/P4 as neighbours) is available. Beta (13–30 Hz): no press-specific decrease on any available channel (press and pseudo-press curves overlap). Mu (8–13 Hz): a press-specific decrease of 3–4 dB at C3, F3 and F4 that separates from the harmless curve 254 ms (C3), 172 ms (F3) and 170 ms (F4) before the press; with the 8–13 Hz envelope's own temporal smearing this is consistent with a motor-preparation/execution mu ERD rather than an early danger signal. Single-trial "intent" detector (log mu+beta power at C3/F3/P3 over −0.3…0 s, shrinkage LDA): AUC 0.61 (0.48–0.73) LORO, 0.61 ± 0.02 5-fold, false-alarm rate 42–47 % at balanced threshold. Not usable alone.

**Bottom line for the brake.** Within the 300 ms that precede the fastest hand response, EEG separates danger from harmless with AUC ≈ 0.65 (CI 0.54–0.79) and roughly 30 % false alarms at 47 % hits. The strong, reliable signal (fronto-central negativity at ~370 ms, Pz P3 at 500–650 ms) arrives with or after the hand press and is confounded with it in this dataset.

## 5. Real-time recommendation (based on these numbers)

**Direction (SSVEP).**
- Channels: O1, Oz, O2, P3, Pz, P4, P7, P8, average-referenced over the good channels (adding the other 13 channels lowered accuracy). Exclude Cz, C4, M2 until their impedances are fixed (they were 2–6.5 MΩ).
- Filters: 60 Hz notch + 5–45 Hz band-pass; online use a causal IIR (≈ 20–30 ms group delay).
- Window: 4 s (3 s is the minimum: 75–85 % accuracy). Decoder: TRCA or extended CCA trained on one short calibration run (5 trials per target, ~3 min): 90–92.5 % at 4 s (CIs 80–100 %, 85–95 % per run); without calibration, CCA with 3 harmonics 87.5 % (75–95 %). ITR ≈ 19–23 bits/min with 4 s windows.
- Latency per decision: 0.14 s visual delay + 4 s window + filter and processing (< 0.1 s) + LSL chunk delay (tens of ms) ≈ 4.3 s from gaze onset. With a 4 s window sliding every 0.5 s and a two-consecutive-agreement rule, expect ≈ 4.5–5 s to a confirmed destination and 85–92 % correct; essentially all residual errors on this subject land on the 12 Hz target.
- No-selection: do not rely on correlation strength. The best threshold with zero wrong destinations rejects 62 % of genuine selections, still lets 10 % of center trials through, and fires on 38 % of eyes-open rest windows. Instead (i) flicker only when a selection is requested (a dwell or button-free "arm" state), (ii) require two agreeing consecutive windows before acting, and (iii) change the stimulus set: 12 Hz sits 0.75 Hz from this subject's eyes-open alpha peak (11.25 Hz) and attracts both center trials (7/10) and all 3–4 s errors; at 60 Hz refresh, 15 Hz (4 frames) and 20 Hz (3 frames) are the only alpha-free integer-period options, so a 120 Hz display would give more room.

**Brain brake.**
- As an EEG-only brake it is not ready: the pre-motor signal is weak (AUC 0.67 in 0–0.30 s, ~30 % false alarms on harmless events, which in a wheelchair means stopping for nothing every third harmless object). The reliable EEG response (N2-like at Fz ~370 ms, P3 at Pz 500–650 ms) comes with or after the hand press (median RT 384 ms), so an EEG brake would react ≈ 0.5–0.8 s after the obstacle starts to veer, no faster than the hand, and its performance in this dataset cannot be separated from the motor act.
- If a brake decoder is still wanted (e.g. for users who cannot press), the pipeline to iterate on is: Fz, F3, F4, C3, P3, Pz, P4 (plus C4/Cz once repaired), causal 0.5–30 Hz, average reference, 25 ms bins over a sliding 300 ms window, shrinkage LDA, EOG regression optional (it changed nothing here); expected latency ≈ 0.35–0.4 s after the veer begins at AUC ≈ 0.65; adding a 0.5–0.8 s window raises AUC to ≈ 0.8 with 10–20 % false alarms but needs a no-press (covert) condition in the next recording to prove it is not the motor response. Mu-ERD at C3 adds little (AUC 0.61).
- Next recording: include a covert condition (see the danger, do not press) and a press-without-danger condition, repair Cz/C4/M2, and record ≥ 80 trials per condition.

**Timing in real time.** Only the eego trigger path gave accurate event times. The recorder's LSL timestamps were off by up to 300 ms for the first ~3 minutes of each session (dejitter convergence). For online decoding this does not matter for the continuous SSVEP/brake classifiers themselves, but any calibration data must be aligned with the eego-recorded markers (or with `proc_dejitter` disabled / a ≥ 5 min warm-up before trusting LSL timestamps).
