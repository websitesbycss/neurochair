# SSVEP (direction) decoder, session A

Timing source: eego `.cnt` triggers (`sample_cnt`). Visual delay 0.14 s. Reference: **avg** (CCA Nh=3, 4 s accuracy by reference: avg=0.88, mastoid=0.82, none=0.85). Channels: O1, Oz, O2, P3, Pz, P4, P7, P8 (all good channels: {'occ_par_8': 0.875, 'all_good_21': 0.825}). Bad channels: ['C4', 'M2', 'Cz']. Filters: 60/120 Hz notch, 5-45 Hz band-pass (CCA/TRCA/eCCA); FBCCA sub-bands [(5, 50), (13, 50), (21, 50), (29, 50)] (Chebyshev-I order 4, zero-phase).

Trials: 50 flicker_on (10 per class, 5 per run). Rejected at 4 s: 0 (no step jumps inside any trial; 45 step samples in the session, all outside the flicker windows).
Kept-epoch peak-to-peak on the 8 channels: median 117 uV, max 234 uV.

## 4-class accuracy (targets only, chance = 0.25)

| method    |   L |   n | acc (95% CI)     | run1 / run2   | ITR T=L / T=L+1 (bit/min)   |
|:----------|----:|----:|:-----------------|:--------------|:----------------------------|
| CCA_nh2   |   1 |  40 | 0.40 (0.25-0.55) | 0.55 / 0.25   | 4.7 / 2.3                   |
| CCA_nh2   |   2 |  40 | 0.47 (0.33-0.62) | 0.50 / 0.45   | 5.1 / 3.4                   |
| CCA_nh2   |   3 |  40 | 0.72 (0.60-0.88) | 0.75 / 0.70   | 14.3 / 10.7                 |
| CCA_nh2   |   4 |  40 | 0.88 (0.78-0.97) | 0.85 / 0.90   | 18.9 / 15.1                 |
| CCA_nh3   |   1 |  40 | 0.40 (0.25-0.55) | 0.55 / 0.25   | 4.7 / 2.3                   |
| CCA_nh3   |   2 |  40 | 0.50 (0.35-0.65) | 0.55 / 0.45   | 6.2 / 4.2                   |
| CCA_nh3   |   3 |  40 | 0.75 (0.62-0.88) | 0.70 / 0.80   | 15.8 / 11.9                 |
| CCA_nh3   |   4 |  40 | 0.88 (0.75-0.95) | 0.85 / 0.90   | 18.9 / 15.1                 |
| CCA_nh4   |   1 |  40 | 0.42 (0.28-0.57) | 0.45 / 0.40   | 6.3 / 3.1                   |
| CCA_nh4   |   2 |  40 | 0.50 (0.35-0.65) | 0.50 / 0.50   | 6.2 / 4.2                   |
| CCA_nh4   |   3 |  40 | 0.78 (0.65-0.90) | 0.70 / 0.85   | 17.5 / 13.1                 |
| CCA_nh4   |   4 |  40 | 0.90 (0.80-0.97) | 0.90 / 0.90   | 20.6 / 16.5                 |
| FBCCA_nh3 |   1 |  40 | 0.40 (0.25-0.55) | 0.45 / 0.35   | 4.7 / 2.3                   |
| FBCCA_nh3 |   2 |  40 | 0.42 (0.28-0.57) | 0.40 / 0.45   | 3.1 / 2.1                   |
| FBCCA_nh3 |   3 |  40 | 0.68 (0.53-0.82) | 0.65 / 0.70   | 11.5 / 8.6                  |
| FBCCA_nh3 |   4 |  40 | 0.85 (0.72-0.95) | 0.90 / 0.80   | 17.3 / 13.8                 |
| TRCA      |   1 |  40 | 0.55 (0.40-0.70) | 0.65 / 0.45   | 17.6 / 8.8                  |
| TRCA      |   2 |  40 | 0.72 (0.57-0.85) | 0.75 / 0.70   | 21.5 / 14.3                 |
| TRCA      |   3 |  40 | 0.85 (0.72-0.95) | 0.90 / 0.80   | 23.0 / 17.3                 |
| TRCA      |   4 |  40 | 0.90 (0.80-0.97) | 0.95 / 0.85   | 20.6 / 16.5                 |
| eCCA_nh3  |   1 |  40 | 0.57 (0.42-0.72) | 0.60 / 0.55   | 20.6 / 10.3                 |
| eCCA_nh3  |   2 |  40 | 0.55 (0.40-0.70) | 0.50 / 0.60   | 8.8 / 5.9                   |
| eCCA_nh3  |   3 |  40 | 0.78 (0.65-0.90) | 0.75 / 0.80   | 17.5 / 13.1                 |
| eCCA_nh3  |   4 |  40 | 0.93 (0.82-1.00) | 0.90 / 0.95   | 22.5 / 18.0                 |

CCA/FBCCA are training-free (evaluated on all 40 target trials, split by run for reference); TRCA and eCCA are trained on one run and tested on the other (pooled over both folds).

Main training-free method: **CCA_nh3** (mean accuracy over windows 0.63 vs 0.59).

## Confusion matrices (CCA_nh3; rows = true incl. center, cols = predicted)

L = 1 s

| true     |   Bathroom |   Kitchen |   Bed |   Door |
|:---------|-----------:|----------:|------:|-------:|
| Bathroom |          7 |         0 |     0 |      3 |
| Kitchen  |          2 |         2 |     2 |      4 |
| Bed      |          4 |         0 |     2 |      4 |
| Door     |          3 |         1 |     1 |      5 |
| center   |          5 |         2 |     2 |      1 |

L = 2 s

| true     |   Bathroom |   Kitchen |   Bed |   Door |
|:---------|-----------:|----------:|------:|-------:|
| Bathroom |          9 |         0 |     1 |      0 |
| Kitchen  |          4 |         2 |     2 |      2 |
| Bed      |          4 |         1 |     4 |      1 |
| Door     |          2 |         0 |     3 |      5 |
| center   |          7 |         1 |     1 |      1 |

L = 3 s

| true     |   Bathroom |   Kitchen |   Bed |   Door |
|:---------|-----------:|----------:|------:|-------:|
| Bathroom |          9 |         0 |     1 |      0 |
| Kitchen  |          2 |         7 |     0 |      1 |
| Bed      |          2 |         0 |     7 |      1 |
| Door     |          2 |         1 |     0 |      7 |
| center   |          7 |         2 |     0 |      1 |

L = 4 s

| true     |   Bathroom |   Kitchen |   Bed |   Door |
|:---------|-----------:|----------:|------:|-------:|
| Bathroom |         10 |         0 |     0 |      0 |
| Kitchen  |          1 |         9 |     0 |      0 |
| Bed      |          2 |         0 |     8 |      0 |
| Door     |          2 |         0 |     0 |      8 |
| center   |          7 |         2 |     0 |      1 |

## Center / no-selection rejection (threshold chosen on one run, applied to the other; pooled)

|   L | feature    | false_selection   | wrong_destination   | correct_selection   | missed       | eyes_open_null_false_selection   |   pooled_zero_error_max_correct |
|----:|:-----------|:------------------|:--------------------|:--------------------|:-------------|:---------------------------------|--------------------------------:|
|   1 | max        | 0/10 (0.00)       | 2/40 (0.05)         | 0/40 (0.00)         | 38/40 (0.95) | 0.17 (n=118)                     |                            0    |
|   1 | margin     | 0/10 (0.00)       | 1/40 (0.03)         | 3/40 (0.07)         | 36/40 (0.90) | 0.23 (n=118)                     |                            0.03 |
|   1 | rel_margin | 0/10 (0.00)       | 1/40 (0.03)         | 4/40 (0.10)         | 35/40 (0.88) | 0.24 (n=118)                     |                            0.1  |
|   2 | max        | 1/10 (0.10)       | 0/40 (0.00)         | 6/40 (0.15)         | 34/40 (0.85) | 0.29 (n=116)                     |                            0.15 |
|   2 | margin     | 1/10 (0.10)       | 0/40 (0.00)         | 3/40 (0.07)         | 37/40 (0.93) | 0.16 (n=116)                     |                            0.05 |
|   2 | rel_margin | 2/10 (0.20)       | 0/40 (0.00)         | 2/40 (0.05)         | 38/40 (0.95) | 0.12 (n=116)                     |                            0.03 |
|   3 | max        | 1/10 (0.10)       | 0/40 (0.00)         | 5/40 (0.12)         | 35/40 (0.88) | 0.29 (n=114)                     |                            0.1  |
|   3 | margin     | 1/10 (0.10)       | 0/40 (0.00)         | 10/40 (0.25)        | 30/40 (0.75) | 0.27 (n=114)                     |                            0.15 |
|   3 | rel_margin | 1/10 (0.10)       | 0/40 (0.00)         | 12/40 (0.30)        | 28/40 (0.70) | 0.30 (n=114)                     |                            0.2  |
|   4 | max        | 1/10 (0.10)       | 0/40 (0.00)         | 15/40 (0.38)        | 25/40 (0.62) | 0.38 (n=112)                     |                            0.35 |
|   4 | margin     | 3/10 (0.30)       | 0/40 (0.00)         | 14/40 (0.35)        | 26/40 (0.65) | 0.31 (n=112)                     |                            0.2  |
|   4 | rel_margin | 3/10 (0.30)       | 1/40 (0.03)         | 14/40 (0.35)        | 25/40 (0.62) | 0.28 (n=112)                     |                            0.15 |

`pooled_zero_error_max_correct` = best correct-selection rate reachable with 0 false selections and 0 wrong destinations when the threshold is picked on all 50 trials (optimistic upper bound).

## Oz PSD SNR (power at f or 2f / neighbouring ±1 Hz)

|             |   SNR |
|:------------|------:|
| Bathroom_h1 |   1.7 |
| Bathroom_h2 |   1.4 |
| Kitchen_h1  |   0.9 |
| Kitchen_h2  |   2.4 |
| Bed_h1      |   1.3 |
| Bed_h2      |   1.9 |
| Door_h1     |   0.9 |
| Door_h2     |   1.6 |

## Alpha check

Eyes closed / eyes open 8-12 Hz power ratio at Oz = 5.4; peak 10.0 Hz (closed), 11.2 Hz (open).

## Interpretation notes

- Harmonic overlap: Bed 7.5 Hz x 2 = 15 Hz and Bathroom 12 Hz; Door 6.67 Hz x 2 = 13.3 Hz is next to Kitchen 8.57 Hz x 3 = 25.7 Hz / Bathroom 12 Hz; Kitchen 8.57 Hz lies inside the alpha band. See the confusion matrices for which pairs actually confuse.
- Center trials still see all four squares flicker, so their max correlation is not zero; the rejection table shows how separable they are from attended targets.
