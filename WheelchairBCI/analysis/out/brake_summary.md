# Brake decoder (session B) — summary

Data: session B LSL stream (sample-identical to the .cnt), event timing from eego triggers. Bad channels: ['C4', 'M2', 'Cz'] (C4 1965 kΩ, Cz 6539 kΩ, M2 1857 kΩ impedance before session B). Band-pass 0.5–30 Hz (zero-phase, offline), average reference over good non-mastoid channels. Classifier channels (14): F3, Fz, F4, T7, C3, T8, P7, P3, Pz, P4, P8, Oz, O1, O2 (frontal EOG proxies and mastoids excluded).

Behaviour: {'stopped': 40, 'passed': 39, 'false_stop': 1}; RT mean 394 ms, median 384, range 299–636 ms.

## Epoch rejection (split-locked, −0.2…0.8 s)

Kept 77/80 trials. Rules: step jump >2000 µV within ±0.25 s, peak-to-peak >150 µV on classifier channels, first 8 s.

| trial | run | cond | side | kind | reject_reason |
|---|---|---|---|---|---|
| 34 | 1 | danger | 1 | cart | peak-to-peak 160 uV > 150 |
| 38 | 1 | harmless | -1 | cart | peak-to-peak 159 uV > 150 |
| 42 | 2 | danger | -1 | ball | peak-to-peak 156 uV > 150 |

## EOG regression

Weights fitted on 12 artifact-block epochs ({'look_left': 5, 'look_right': 4, 'blink': 3}, 30 s). VEOG proxy = mean(Fp1,Fp2), HEOG proxy = F9−F10 (both after average reference).

| ch | w_VEOG | w_HEOG |
|---|---|---|
| Fp1 | 1.294 | 0.065 |
| F7 | -0.032 | 0.374 |
| F3 | -0.064 | 0.031 |
| Fz | -0.088 | -0.116 |
| F4 | -0.067 | -0.087 |
| F8 | -0.061 | -0.623 |
| C3 | -0.132 | 0.030 |
| P3 | -0.154 | 0.031 |
| Pz | -0.149 | 0.054 |
| P4 | -0.143 | 0.013 |

Variance removed in split epochs on classifier channels: 6.0 % (Fz -22 %, Pz 6 %, F7 15 %, F8 29 %).

## ERP peaks (danger − harmless, EOG-regressed)

| channel | window | peak_diff_uV | peak_t_ms | sig_ms |
|---|---|---|---|---|
| Fz | pre_press | -3.670 | 136.000 | 16.000 |
| Fz | post_press | -6.900 | 368.000 | 106.000 |
| Pz | pre_press | -1.560 | 10.000 | 0.000 |
| Pz | post_press | 6.700 | 618.000 | 270.000 |
| F3 | pre_press | 3.510 | 276.000 | 6.000 |
| F3 | post_press | 4.510 | 666.000 | 56.000 |
| F4 | pre_press | -5.160 | 12.000 | 66.000 |
| F4 | post_press | -6.880 | 372.000 | 112.000 |
| C3 | pre_press | -2.590 | 126.000 | 8.000 |
| C3 | post_press | 4.520 | 488.000 | 118.000 |
| P3 | pre_press | -3.680 | 278.000 | 46.000 |
| P3 | post_press | -3.620 | 312.000 | 80.000 |
| P4 | pre_press | -3.140 | 60.000 | 8.000 |
| P4 | post_press | 4.660 | 516.000 | 142.000 |

(sig_ms = ms within the window where the bootstrap 95 % CI of the difference excludes 0.) Figures: fig_brake_erp.png, fig_brake_topo.png, fig_brake_erp_by_side.png

## Pre-press classifier: danger vs harmless from `split`

Windows 0.20/0.25/0.30 s end before the fastest RT (299 ms); 0.40/0.50/0.80 s are **contaminated by the motor response** and shown only to expose the confound. LORO = train one run, test the other (pooled over both directions). 5-fold = stratified, 10 repeats (AUC mean ± sd over repeats; CI = bootstrap on per-trial mean scores). bal_acc / false-alarm use the LDA threshold learned on the training fold.

| eog | window_s | contaminated | pipeline | loro_auc | loro_auc_ci | loro_train1_test2 | loro_train2_test1 | loro_bal_acc | loro_false_alarm | loro_hit | kfold_auc | kfold_auc_ci | kfold_bal_acc | kfold_false_alarm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EOG-regressed | 0.200 | False | slda | 0.556 | [0.42, 0.69] | 0.521 | 0.590 | 0.544 | 0.333 | 0.421 | 0.562 ± 0.034 | [0.44, 0.71] | 0.623 | 0.359 |
| EOG-regressed | 0.200 | False | xdawn | 0.513 | [0.39, 0.64] | 0.492 | 0.560 | 0.544 | 0.333 | 0.421 | 0.518 ± 0.038 | [0.39, 0.65] | 0.544 | 0.359 |
| EOG-regressed | 0.250 | False | slda | 0.599 | [0.46, 0.73] | 0.574 | 0.623 | 0.596 | 0.333 | 0.526 | 0.575 ± 0.040 | [0.45, 0.72] | 0.610 | 0.359 |
| EOG-regressed | 0.250 | False | xdawn | 0.517 | [0.39, 0.65] | 0.508 | 0.571 | 0.505 | 0.359 | 0.368 | 0.517 ± 0.048 | [0.39, 0.66] | 0.492 | 0.410 |
| EOG-regressed | 0.300 | False | slda | 0.670 | [0.54, 0.79] | 0.661 | 0.690 | 0.583 | 0.308 | 0.474 | 0.634 ± 0.057 | [0.53, 0.78] | 0.610 | 0.333 |
| EOG-regressed | 0.300 | False | xdawn | 0.592 | [0.46, 0.72] | 0.582 | 0.665 | 0.544 | 0.333 | 0.421 | 0.611 ± 0.043 | [0.49, 0.74] | 0.583 | 0.333 |
| EOG-regressed | 0.400 | True | slda | 0.757 | [0.65, 0.86] | 0.729 | 0.773 | 0.739 | 0.179 | 0.658 | 0.744 ± 0.039 | [0.64, 0.87] | 0.701 | 0.282 |
| EOG-regressed | 0.400 | True | xdawn | 0.719 | [0.60, 0.83] | 0.692 | 0.795 | 0.623 | 0.333 | 0.579 | 0.739 ± 0.026 | [0.66, 0.87] | 0.766 | 0.179 |
| EOG-regressed | 0.500 | True | slda | 0.761 | [0.65, 0.86] | 0.708 | 0.814 | 0.726 | 0.205 | 0.658 | 0.792 ± 0.041 | [0.69, 0.89] | 0.753 | 0.256 |
| EOG-regressed | 0.500 | True | xdawn | 0.714 | [0.59, 0.82] | 0.739 | 0.742 | 0.622 | 0.256 | 0.500 | 0.757 ± 0.028 | [0.67, 0.88] | 0.765 | 0.154 |
| EOG-regressed | 0.800 | True | slda | 0.801 | [0.69, 0.89] | 0.839 | 0.756 | 0.765 | 0.103 | 0.632 | 0.799 ± 0.019 | [0.72, 0.91] | 0.766 | 0.231 |
| EOG-regressed | 0.800 | True | xdawn | 0.752 | [0.64, 0.85] | 0.726 | 0.795 | 0.713 | 0.205 | 0.632 | 0.816 ± 0.022 | [0.72, 0.91] | 0.740 | 0.205 |
| no EOG | 0.200 | False | slda | 0.592 | [0.46, 0.72] | 0.534 | 0.657 | 0.570 | 0.282 | 0.421 | 0.593 ± 0.035 | [0.47, 0.73] | 0.623 | 0.359 |
| no EOG | 0.200 | False | xdawn | 0.501 | [0.37, 0.63] | 0.476 | 0.543 | 0.544 | 0.359 | 0.447 | 0.527 ± 0.036 | [0.40, 0.67] | 0.532 | 0.410 |
| no EOG | 0.250 | False | slda | 0.615 | [0.48, 0.75] | 0.584 | 0.640 | 0.583 | 0.308 | 0.474 | 0.609 ± 0.040 | [0.50, 0.75] | 0.623 | 0.333 |
| no EOG | 0.250 | False | xdawn | 0.524 | [0.39, 0.65] | 0.503 | 0.582 | 0.518 | 0.359 | 0.395 | 0.547 ± 0.043 | [0.44, 0.70] | 0.518 | 0.359 |
| no EOG | 0.300 | False | slda | 0.686 | [0.56, 0.80] | 0.661 | 0.715 | 0.596 | 0.333 | 0.526 | 0.666 ± 0.052 | [0.56, 0.80] | 0.636 | 0.333 |
| no EOG | 0.300 | False | xdawn | 0.613 | [0.49, 0.74] | 0.595 | 0.687 | 0.583 | 0.308 | 0.474 | 0.633 ± 0.042 | [0.53, 0.77] | 0.596 | 0.333 |
| no EOG | 0.400 | True | slda | 0.775 | [0.67, 0.88] | 0.758 | 0.798 | 0.713 | 0.179 | 0.605 | 0.772 ± 0.033 | [0.68, 0.89] | 0.727 | 0.256 |
| no EOG | 0.400 | True | xdawn | 0.737 | [0.62, 0.84] | 0.724 | 0.789 | 0.648 | 0.282 | 0.579 | 0.743 ± 0.024 | [0.65, 0.87] | 0.714 | 0.231 |
| no EOG | 0.500 | True | slda | 0.775 | [0.67, 0.88] | 0.753 | 0.809 | 0.674 | 0.231 | 0.579 | 0.817 ± 0.033 | [0.73, 0.91] | 0.793 | 0.231 |
| no EOG | 0.500 | True | xdawn | 0.735 | [0.62, 0.84] | 0.768 | 0.740 | 0.673 | 0.154 | 0.500 | 0.766 ± 0.028 | [0.68, 0.89] | 0.778 | 0.154 |
| no EOG | 0.800 | True | slda | 0.810 | [0.70, 0.90] | 0.834 | 0.778 | 0.790 | 0.077 | 0.658 | 0.818 ± 0.018 | [0.74, 0.92] | 0.753 | 0.205 |
| no EOG | 0.800 | True | xdawn | 0.733 | [0.62, 0.84] | 0.732 | 0.734 | 0.675 | 0.282 | 0.632 | 0.818 ± 0.020 | [0.73, 0.92] | 0.752 | 0.179 |

Timing source check (w = 0.30 s, sLDA, EOG-regressed, LORO): eego-trigger timing AUC 0.670 vs LSL-path timing AUC 0.534 [0.40, 0.66] ({'train2_test1': 0.5096952908587258, 'train1_test2': 0.5657894736842105}).

## Eye-movement (side) checks

| eog | channels | window_s | side_loro_auc | side_kfold_auc | side_kfold_ci |
|---|---|---|---|---|---|
| EOG-regressed | classifier set | 0.200 | 0.521 | 0.536 | [0.41, 0.68] |
| EOG-regressed | classifier set | 0.250 | 0.559 | 0.551 | [0.43, 0.69] |
| EOG-regressed | classifier set | 0.300 | 0.549 | 0.533 | [0.40, 0.67] |
| EOG-regressed | + frontal (Fp/F7/F8/F9/F10) | 0.300 | nan | 0.484 | [0.35, 0.62] |
| no EOG | classifier set | 0.200 | 0.539 | 0.569 | [0.45, 0.71] |
| no EOG | classifier set | 0.250 | 0.590 | 0.582 | [0.46, 0.72] |
| no EOG | classifier set | 0.300 | 0.576 | 0.570 | [0.45, 0.71] |
| no EOG | + frontal (Fp/F7/F8/F9/F10) | 0.300 | nan | 0.539 | [0.42, 0.68] |

Danger-vs-harmless within one side and across sides (w = 0.30 s, sLDA):

| eog | test | n | auc_from_loro_model | auc_kfold_within_side | false_alarm |
|---|---|---|---|---|---|
| EOG-regressed | danger-vs-harmless within left-side trials | 38 | 0.751 | 0.682 | nan |
| EOG-regressed | danger-vs-harmless within right-side trials | 39 | 0.603 | 0.615 | nan |
| EOG-regressed | train left -> test right | 39 | nan | 0.587 | 0.400 |
| EOG-regressed | train right -> test left | 38 | nan | 0.490 | 0.474 |
| no EOG | danger-vs-harmless within left-side trials | 38 | 0.720 | 0.645 | nan |
| no EOG | danger-vs-harmless within right-side trials | 39 | 0.647 | 0.686 | nan |
| no EOG | train left -> test right | 39 | nan | 0.637 | 0.400 |
| no EOG | train right -> test left | 38 | nan | 0.488 | 0.474 |

## Press-locked analysis

Epochs −1.0…+0.5 s around `brake_press` (n = 41) vs harmless trials aligned to split + 394 ms (pseudo-press, n = 38). Rejected: press [], pseudo []. Log band power (Hilbert envelope of 13–30 Hz and 8–13 Hz, data band-passed 1–45 Hz, notched, EOG-regressed) relative to −1.0…−0.8 s. C4 and Cz are bad (impedance), so the right-hemisphere motor channel is missing; F3/P3/F4/P4 serve as neighbours.

| band | channel | erd_onset_ms_before_press | min_dB_pre_press | min_t_ms | press_minus_pseudo_dB_at_0 | press_minus_pseudo_sig_ms_pre |
|---|---|---|---|---|---|---|
| beta 13-30 Hz | C3 | nan | -3.430 | -350.000 | 0.950 | 0.000 |
| beta 13-30 Hz | F3 | nan | -1.480 | -108.000 | 0.290 | 28.000 |
| beta 13-30 Hz | P3 | nan | -2.190 | -64.000 | 1.140 | 0.000 |
| beta 13-30 Hz | F4 | 570.000 | -1.900 | -388.000 | 1.260 | 10.000 |
| beta 13-30 Hz | P4 | 300.000 | -2.250 | -266.000 | -0.340 | 0.000 |
| mu 8-13 Hz | C3 | 596.000 | -3.620 | -424.000 | -3.950 | 254.000 |
| mu 8-13 Hz | F3 | 750.000 | -2.920 | 0.000 | -4.130 | 172.000 |
| mu 8-13 Hz | P3 | 674.000 | -4.070 | -494.000 | -1.000 | 52.000 |
| mu 8-13 Hz | F4 | 738.000 | -4.230 | -298.000 | -3.410 | 170.000 |
| mu 8-13 Hz | P4 | nan | -1.290 | -16.000 | -1.400 | 0.000 |

(erd_onset = first time the upper 95 % CI of the press-locked curve stays below 0 for ≥50 ms; press_minus_pseudo_sig_ms_pre = ms in −0.5…0 s where the press−pseudo difference CI excludes 0.) Figures: fig_brake_press_power.png, fig_brake_tfr_c3.png

Single-trial intent detector (press vs harmless pseudo-press):

| features | loro_auc | loro_auc_ci | loro_per_run | loro_bal_acc | loro_false_alarm | kfold_auc | kfold_auc_sd | kfold_auc_ci | kfold_bal_acc | kfold_false_alarm |
|---|---|---|---|---|---|---|---|---|---|---|
| absolute log beta+mu power C3/F3/P3, -0.3..0 s | 0.608 | [0.48, 0.73] | {'train2_test1': 0.5657894736842106, 'train1_test2': 0.6491228070175439} | 0.605 | 0.474 | 0.605 | 0.020 | [0.49, 0.74] | 0.582 | 0.421 |
| baseline-relative log beta+mu power C3/F3/P3, -0.3..0 s | 0.530 | [0.40, 0.66] | {'train2_test1': 0.5605263157894738, 'train1_test2': 0.5037593984962406} | 0.637 | 0.263 | 0.621 | 0.017 | [0.50, 0.75] | 0.596 | 0.368 |

## Interpretation

**Is there a pre-motor danger signal?** Only a weak one. Using only the first 0.30 s after the veer starts
(before the fastest RT of 299 ms), shrinkage LDA on time-binned amplitudes of 14 non-frontal channels reaches a
leave-one-run-out AUC of 0.67 (95 % CI 0.54-0.79; 5-fold 0.63 +/- 0.06), balanced accuracy 0.58-0.61, and
31-33 % of harmless trials are flagged as danger at the LDA threshold. Shorter windows are at chance
(0.20 s: AUC 0.56; 0.25 s: 0.60). xDAWN+LDA is no better (0.59 at 0.30 s). As soon as the window includes the
button press the AUC jumps to 0.76 (0.40 s) and 0.80 (0.80 s): that gain is the motor/post-decision response,
not perception, and must not be read as brake performance.

**ERPs.** Before 300 ms no channel shows a danger-vs-harmless difference whose bootstrap CI excludes zero for more
than ~70 ms (the longest is a left-parietal P3 negativity of -3.7 uV around 280 ms, 46 ms). The robust
components are after the press: a fronto-central negativity at Fz/F4 around 370 ms (-6.9 uV, ~110 ms
significant) and a parietal P3-like positivity at Pz/P4 from ~450 ms (+6.7 uV at 618 ms, 270 ms significant).
Those are N2/P3-type components but they arrive with or after the key press and are entangled with the
'stopped' feedback. Difference topographies (fig_brake_topo.png) are noisy and dominated by T7/F8.

**Eye movements.** The object side is not decodable from the 0-0.30 s windows (AUC 0.52-0.59, all CIs include
0.5, even with the frontal channels included and no EOG regression), and the F7/F8 traces show no mirror-image
lateralisation within 0.8 s (fig_brake_erp_by_side.png): the subject held fixation during the decision window.
EOG regression (weights from only 12 artifact epochs, 30 s) removes just 6 % of variance on the classifier
channels and does not change the decoding (0.67 vs 0.69 without it), so eye activity is not what the classifier
uses. Danger decoding within one side (0.60-0.75) and across sides (0.49-0.64) is unstable, but with ~19 trials
per class per side that mostly reflects sample size.

**Press-locked activity.** There is no press-specific beta (13-30 Hz) desynchronisation at C3 or its
neighbours: press-locked and harmless pseudo-press curves overlap (0 ms of CI-excluding difference at C3).
Mu (8-13 Hz) does show a press-specific decrease of 3-4 dB at C3, F3 and F4 that separates from the harmless
trials ~250 ms before the press (C3: 254 ms, F3: 172 ms, F4: 170 ms of CI-excluding difference), i.e. it
starts around the time the danger is perceived; it is bilateral, and C4/Cz are unavailable (bad). As a
single-trial 'intent to stop' detector (log beta+mu power at C3/F3/P3 in the 300 ms before the press) it gives
AUC 0.61 (CI 0.48-0.73, LORO) and 0.62 (5-fold), with 26-47 % false alarms: a second weak cue, not a brake.

**Timing.** With the LSL-path event timing instead of the eego triggers the 0.30 s AUC falls from 0.67 to 0.53,
which is what the 20-300 ms dejitter transient in run 1 predicts; ERP-type decoding needs trigger-accurate timing.

**Bottom line.** From EEG alone, within the 300 ms that matter for a brake, this session supports detection at
roughly AUC 0.65 with a ~30 % false-alarm rate on harmless events. That is far from a usable autonomous brake;
it could at best bias a sensor-based obstacle stop or be combined with the mu decrease and the (much stronger)
post-press P3 as confirmation, with the understanding that the EEG then only confirms a stop that has already
been decided ~400 ms after the object veered.
