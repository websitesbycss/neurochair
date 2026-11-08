# Preprocessing summary

## Files and coverage

| Session | LSL npz | cnt segment | lag (cnt = lsl + lag) | identical samples | LSL rate implied by timestamps |
|---|---|---|---|---|---|
| A | S1_20261107_182835_wc_eeg.npz | samples 0–261310 | -4123 samples (-8.246 s) | 100.0 % (std ratio 1.00000) | 499.03 Hz |
| B | S1_20261107_183742_wc_eeg.npz | samples 261310–488640 | -3611 samples (-7.222 s) | 100.0 % (std ratio 1.00000) | 498.89 Hz |

- The `.cnt` has 488640 samples at 500 Hz in two segments: segment 1 starts 2026-11-07 23:28:42.100740+00:00 (sample 0, session A, ends at the 2nd impedance check), segment 2 starts 2026-11-07 23:37:47.620867+00:00 at sample 261310 (session B). The `.seg` file's number (227330) is the length of the *last* segment, not its start index.
- The `.cnt` ends at the same instant as the session-B LSL stream (the eego recording was stopped there), so the last 4 artifact trials and the final sync block are not recoverable from any file.
- Samples are bit-identical between `.cnt` and `.npz` (same amplifier stream, µV, DC-coupled, REF = CPz); no dropped samples in either session. The 499 Hz implied by the LSL timestamps is the stimulus PC's clock-sync/dejitter estimate, not lost samples.
- Event timing: the eego native triggers (LSL markers received by eego) are used. The LSL-path mapping (csv lsl_time -> dejittered npz timestamps) deviates from them by a smooth transient of up to 300 ms in the first ~3 min of each recording (liblsl dejitter convergence); see timing_check.

## eego .evt markers

- 533 records: 531 LSL markers from stream `WheelchairMarkers` (all CSV events except those sent before the eego recording started / after it stopped) and 2 impedance checks.
- Impedance checks (kOhm) at 2026-11-07 23:28:42.100740+00:00 (recording start / session A) and 2026-11-07 23:37:24.714740+00:00 (pause before session B):

| ch | Fp1 | Fp2 | F9 | F7 | F3 | Fz | F4 | F8 | F10 | M1 | T7 | C3 | C4 | T8 | M2 | Cz | P7 | P3 | Pz | P4 | P8 | Oz | O1 | O2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| check 1 | 36 | 46 | 12 | 32 | 35 | 88 | 70 | 36 | 20 | 83 | 147 | 147 | 2815 | 63 | 187 | 2092 | 259 | 59 | 104 | 170 | 209 | 9 | 42 | 64 |
| check 2 | 50 | 42 | 23 | 51 | 41 | 101 | 79 | 45 | 30 | 142 | 181 | 177 | 1965 | 72 | 1857 | 6539 | 538 | 89 | 142 | 313 | 262 | 21 | 77 | 86 |

- The marker counts per block in the .evt match the CSV, except: session A `config`/`session_start` (sent before the eego recording started), session B artifact trials 17–20 and the final sync block (after the recording stopped), and the first jaw-clench cue of session A, which is in the .evt (t = 0.106 s) but is dropped by antio/MNE (it is restored from the .evt time).

## Channel quality

Rules: bad if impedance > 1000 kOhm, or 1–40 Hz std > 5× the median channel, or Cz (documented bad).

### Session A: bad channels = ['C4', 'M2', 'Cz']

| ch | impedance kOhm | 1–40 Hz std µV | std / median | max step µV (after 8 s) | bad |
|---|---|---|---|---|---|
| Fp1 | 36 | 38.3 | 2.5 | 18197 |  |
| Fp2 | 46 | 35.2 | 2.3 | 18246 |  |
| F9 | 12 | 18.3 | 1.2 | 17360 |  |
| F7 | 32 | 16.0 | 1.0 | 17637 |  |
| F3 | 35 | 12.2 | 0.8 | 17611 |  |
| Fz | 88 | 10.9 | 0.7 | 19814 |  |
| F4 | 70 | 12.1 | 0.8 | 18242 |  |
| F8 | 36 | 23.1 | 1.5 | 17754 |  |
| F10 | 20 | 15.9 | 1.0 | 17540 |  |
| M1 | 83 | 64.0 | 4.1 | 16737 |  |
| T7 | 147 | 21.1 | 1.4 | 17789 |  |
| C3 | 147 | 12.7 | 0.8 | 20296 |  |
| C4 | 2815 | 52.2 | 3.4 | 21852 | **yes** |
| T8 | 63 | 15.1 | 1.0 | 17692 |  |
| M2 | 187 | 110.7 | 7.2 | 21135 | **yes** |
| Cz | 2092 | 168.0 | 10.9 | 25484 | **yes** |
| P7 | 259 | 22.5 | 1.5 | 24036 |  |
| P3 | 59 | 11.4 | 0.7 | 18559 |  |
| Pz | 104 | 10.5 | 0.7 | 18909 |  |
| P4 | 170 | 13.9 | 0.9 | 19295 |  |
| P8 | 209 | 14.6 | 0.9 | 18543 |  |
| Oz | 9 | 12.0 | 0.8 | 17587 |  |
| O1 | 42 | 12.0 | 0.8 | 18868 |  |
| O2 | 64 | 12.4 | 0.8 | 18577 |  |

- Step jumps > 2000 µV/sample on any good channel: 45 samples, of which 10 after the first 8 s (at EEG-relative s: [8.0, 8.1, 8.2]). Epochs overlapping these (±0.25 s) are rejected.

### Session B: bad channels = ['C4', 'M2', 'Cz']

| ch | impedance kOhm | 1–40 Hz std µV | std / median | max step µV (after 8 s) | bad |
|---|---|---|---|---|---|
| Fp1 | 50 | 67.2 | 3.6 | 629 |  |
| Fp2 | 42 | 43.8 | 2.4 | 520 |  |
| F9 | 23 | 19.4 | 1.1 | 651 |  |
| F7 | 51 | 19.5 | 1.1 | 1263 |  |
| F3 | 41 | 14.4 | 0.8 | 533 |  |
| Fz | 101 | 12.7 | 0.7 | 495 |  |
| F4 | 79 | 14.0 | 0.8 | 516 |  |
| F8 | 45 | 30.5 | 1.6 | 652 |  |
| F10 | 30 | 19.8 | 1.1 | 640 |  |
| M1 | 142 | 74.4 | 4.0 | 1646 |  |
| T7 | 181 | 23.6 | 1.3 | 995 |  |
| C3 | 177 | 13.7 | 0.7 | 574 |  |
| C4 | 1965 | 28.4 | 1.5 | 575 | **yes** |
| T8 | 72 | 17.3 | 0.9 | 867 |  |
| M2 | 1857 | 61.4 | 3.3 | 781 | **yes** |
| Cz | 6539 | 266.3 | 14.4 | 2958 | **yes** |
| P7 | 538 | 30.4 | 1.6 | 1291 |  |
| P3 | 89 | 13.5 | 0.7 | 617 |  |
| Pz | 142 | 12.2 | 0.7 | 491 |  |
| P4 | 313 | 16.3 | 0.9 | 575 |  |
| P8 | 262 | 17.5 | 0.9 | 1014 |  |
| Oz | 21 | 13.8 | 0.7 | 534 |  |
| O1 | 77 | 13.4 | 0.7 | 555 |  |
| O2 | 86 | 15.6 | 0.8 | 514 |  |

- Step jumps > 2000 µV/sample on any good channel: 157 samples, of which 0 after the first 8 s (at EEG-relative s: []). Epochs overlapping these (±0.25 s) are rejected.

## Filters

- All offline filtering is zero-phase (scipy sosfiltfilt / filtfilt).
- SSVEP: 60 Hz + 120 Hz IIR notch (Q = 30), 4th-order Butterworth band-pass 5–45 Hz; FBCCA sub-bands [5,50], [13,50], [21,50], [29,50] Hz.
- Brake ERPs / classifier: 4th-order Butterworth band-pass 0.5–30 Hz (60 Hz is outside the pass band); press-locked spectra: 4–40 Hz Morlet.
- Per-channel mean removed (DC offsets of −47 000…+63 000 µV); the first 8 s of each recording are excluded (amplifier settling).
- Re-reference: average of the good non-mastoid channels (default). Linked mastoids are not usable: M2 is bad in both sessions (187 kOhm / 1857 kOhm, 1–40 Hz std 7–8× the median), so the 'mastoid' option is M1 alone.
- Epoch rejection: step jump inside epoch (±0.25 s margin), epoch outside the recording, peak-to-peak threshold (brake: 150 µV on classifier channels).

## cnt-based loader (wc_io.load_cnt_session)

- Session A: 522.6 s, 178 native-trigger annotations, 178 CSV-derived annotations; CSV-mapped minus trigger: median 2 ms, min -310 ms, max 426 ms over 178 events.
- Session B: 454.7 s, 353 native-trigger annotations, 353 CSV-derived annotations; CSV-mapped minus trigger: median -12 ms, min -294 ms, max 204 ms over 348 events.