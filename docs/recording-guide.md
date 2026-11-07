# Recording guide (30-minute rotation)

## Before the session
- Soak the net 5 to 15 minutes (see `docs/cap-setup.md` if present, or the waveguard guide). Connectors stay dry.
- Laptop on the same network as ANT's laptop, `lsl_api.cfg` has ANT's IP (see `HACKATHON.md` notes). Firewall allows Python.
- Check the stream shows up: `.venv/Scripts/python src/live_reader.py`.
- Operator laptop has speakers on. One person is the operator (reads cues aloud), one is the subject, one watches signal quality.

## Timeline (30 min)
| Min | What |
|---|---|
| 0-5 | Cap on, impedance under 50 kOhm everywhere (GND/REF under 20), notch filter on in eego if available |
| 5 | Start ONE continuous eego recording (no pausing; pauses cause artifacts) and enable annotations. Then start our recorder: `.venv/Scripts/python src/record_lsl.py session1` |
| 5-28 | Universal protocol (about 23 min), hands-free: `.venv/Scripts/python src/cue_session.py --auto --speak`. Blocks: sync, baseline (open/closed), blinks, eyes-closed 3 s, jaw clench, frown/smile, eye direction, hand squeeze L/R, right bicep light/medium/hard, imagined squeeze L/R, squeeze with clench/blink on purpose, mental workload (easy vs hard counting), reading, reading with a video distraction |
| 28-30 | Buffer or repeat anything that went badly (`--blocks <names>`; extras: focus, arms, legs) |

Covers every idea: blink/clench/eye control, hand intent (L/R, executed vs imagined), drowsiness (long closures), workload/overload, reading and distraction, and an artifact-vs-engagement test set.

The laptop speaks each cue and beeps; the beep is the marker time. Operator only has to (a) show a short video at the edge of the subject's vision during the "distraction" block and (b) keep the subject still. The reading passages open in a full-screen big-text window (Esc closes it; it also closes on its own). Stop anytime with Ctrl+C.

## Subject rules
- Upright, seated, hands on thighs, feet flat, head still. Eyes on one far object unless told otherwise.
- No talking, no head turns, no fidgeting during trials.
- Squeeze, flex or press at about 70 percent effort, hold for the whole hold window, then relax fully.
- Imagery block: imagine the squeeze (kinesthetic, feel the muscle) and do NOT move.

## After
- Ctrl+C the recorder (saves `data/session1.npz`). Export from eego as EDF+ or BrainVision as well.
- Note anything odd (loose electrode, subject sneezed, a trial the subject missed) with the approximate time.

## Algorithm plan (artifact gating, then engagement)
1. **Gate artifacts first.** Flag windows with a blink (Fp1/Fp2 1 to 8 Hz, large in-phase deflection), jaw/face muscle (25 to 45 Hz power up on frontal/temporal channels), or whole-head movement (large slow jumps on many channels). Do not score engagement in flagged windows.
2. **Optional cleanup.** Try ICA or regression using Fp1/Fp2 as an eye proxy to remove blinks instead of dropping windows.
3. **Engagement features.** Mu (8 to 12 Hz) and beta (13 to 30 Hz) power drop over C3, Cz and C4, relative to that person's baseline. Compare left versus right (C4 right-brain for the left hand). Stay at or below 30 Hz so muscle noise isn't mistaken for brain activity.
4. **Baseline model.** CSP plus LDA on left vs right trials. Split by trial, never by sample.
5. **Report with a quality flag.** Output engagement plus a signal-quality state; say "can't tell" when the window is contaminated.
6. The combined block (squeeze with deliberate jaw clench or blink) is the test set for whether the gate works.
