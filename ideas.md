# Project ideas (Team 2, ANT Neuro track)

Status: brainstorming, nothing decided yet. Once the team picks one, record it in `docs/decisions.md` and fill in the interface section of `CLAUDE.md`.

## Track constraints that shape every idea
- The brief wants a scalable, everyday-life app, and the official outline says movement tracked through EEG is the core input. The briefing also says cognitive workload during everyday tasks is welcome and that we can propose our own idea. **Ask the ANT support person to confirm a workload-only project counts before committing to one.**
- Equipment: eego amplifier + 24-channel waveguard net, eego software, LSL streaming. Data comes from a required first rotation (short, scripted, shared with other teams).
- Inclusivity is a sub-goal (extra $100 prize; check the rubric). Movement should be the control default.
- Pitch: 3 minutes with a live demo. Scalability is judged.

## Signals and how reliable they are
| Signal | Where | Difficulty | Reliability |
|---|---|---|---|
| Blink (especially deliberate or double) | Frontal channels (Fp1/Fp2); confirm the net has them | Easy, threshold on a large spike | High |
| Jaw clench | Temporal channels, 20+ Hz muscle burst | Easy, high-frequency power | High |
| Eye left/right | Difference of frontal-side channels | Medium | Medium to high |
| Arm/hand movement (brain signal) | Motor cortex mu/beta drop | Hard, per-person training | Medium (roughly 70 to 85% for two classes, from general experience) |
| Cognitive load | Frontal theta up, parietal alpha down | Medium, needs per-person baseline, movement adds noise | Medium |
| Emotion | Whole scalp | Hard | Weak. Avoid claiming it |

## Ideas

### 1. Hands-free communication board with two modes (leading candidate)
Movement-controlled board of phrases and actions, and the laptop speaks the choice. Works offline. Revised from the original eye-only, single-switch version: that was too hard to design for this weekend, so the target is now anyone whose hands or speech aren't available, with locked-in ALS as one future user group.
- **Bring your own movement:** a short calibration finds which movements this person can do reliably (blink, jaw clench, eye direction, head nod) and maps the two or three that work to the controls.
- **Two switches, user-paced:** blink = select, jaw clench = move to the next option. This is faster than timer-based single-switch scanning, which makes the user wait. Eye left/right is an optional extra (one EEG paper reported only 70 to 80% for those).
- **Two modes, defined by what the person can do, not by a disability label.** Don't name modes "disabled" and "able-bodied"; people sit in between, and judges may notice the sorting.
  - **Switch mode:** large high-contrast screens, slow forgiving user-paced scanning, AI suggestions. For limited movement or minimal effort.
  - **Hands-free mode:** same controls plus shortcuts for frequent actions (timer, next recipe step, call back, mute). For situational use: cooking, driving a forklift, gloves, noisy places, holding a baby.
  - One shared engine; the modes differ only by profile (control mapping, speed, screen density, shortcuts). Build Switch mode first; cut Hands-free if time is short.
- **Pitch point:** universal design, the curb-cut effect. Say honestly that an able-bodied person with free hands would normally use a keyboard or voice; the value is situational, and greatest for people with no other reliable input.
- Add a **triple-blink or long-clench emergency alert** that notifies a caregiver.
- Add **AI-suggested replies/actions** (see idea 2).
- Best live demo: one volunteer shows Switch mode asking for water without hands, another shows Hands-free mode doing a task with their hands occupied.

### 2. AI-assisted selection (the speed-up layer)
Free-form translation of movement or EEG into words doesn't work. A 2024 critique found open-vocabulary EEG-to-text models scoring about the same on pure noise. Selection works: eye/blink spellers reach about 6 to 7 letters per minute at roughly 90 to 95% accuracy, and Google's SpeakFaster used LLMs to cut keystrokes for ALS eye-gaze typists.
- The AI proposes 4 to 6 likely phrases or actions from context (last message received, time of day, the user's frequent phrases) and **ranks the likeliest first**. With two switches, a right first guess is one blink; a second guess is one clench plus a blink. A typical phrase takes about 1 to 3 actions instead of dozens. Letter scanning with next-word prediction is the fallback.
- Confirmation: low-stakes output (speaking a phrase aloud) uses a 3-second countdown that fires unless a clench cancels it. Anything sent to another person or a device **requires a deliberate blink first**. Always keep an easy undo.
- Measure honestly: count actions per message with and without suggestions on our own prototype, against a letter-by-letter blink-scanning baseline. SpeakFaster's 29 to 60% was measured against fast eye-gaze typing, so it isn't comparable. Expect a multiple for our baseline, but don't put a number on a slide until we've measured it.
- Likely failure points: head motion causing false clenches and poor net fit. Test both early.
- Actions: check-in message, call for help, lights or TV, read or reply to a message.
- Don't claim specific speed-ups until we measure selections per message with and without suggestions on our own prototype.
- The ANT network may have no internet. Share a phone connection or use a second adapter, and keep an **offline fallback** of canned phrases and menus.
- "Meta Muse" is unclear: possibly the Muse EEG headband (4 channels, cheap) or an AI model. The agent is a swappable API call either way. A Muse headband would be a good scalability slide.

### 3. Sensory-overload overlay (adaptive interface)
Watches EEG for overload and calms the screen: stop flashing and animation, mute notifications, simplify layout, enlarge text, dim.
- Frame as **sensory/cognitive overload** (epilepsy, autism, ADHD, migraine, anxiety). **Do not claim it prevents seizures.** For photosensitive epilepsy, stopping flashing content is the evidence-backed part.
- Inclusive design: per-person baseline, user-defined profiles, suggestions with undo, no cloud, brain data stays on the device.
- Smooth and delay state changes. A flickering interface is itself overstimulating.
- **Headset-free version:** use our recordings to find which behaviour signals (typing slowdown, errors, mouse jitter) track overload, then run the overlay on those for people without a headset.
- Use standards: `prefers-reduced-motion`, high-contrast, flashing-content rules.
- Opt-in, aggregate classroom view is future work. Individual monitoring is a surveillance risk.
- **Gap with the track:** this measures mental state, not movement. Fix by making movement the control channel (blink or clench to dismiss or request calm) and the headset-free proxy (typing and mouse movement).

### 4. Seizure alert robust to everyday movement
Train a detector on a public seizure dataset (CHB-MIT, about 23 channels) and test it against our own everyday-movement recordings so ordinary movement doesn't cause false alarms.
- We can't record real seizures here, so the live demo would replay a seizure recording through the LSL stream.
- Per-patient results only. Not a medical device. Higher risk of overclaiming than the others.

### 4b. Mind-muscle connection feedback for physical therapy (and lifters)
Live feedback showing how strongly the motor cortex is engaging during a movement, so a patient (or lifter) can see whether they're activating the intended side. Movement is the core input. Inclusive angle: stroke and injury rehab, where re-engaging the brain's movement signal matters.
- Signal: mu/beta drop over motor cortex during real or attempted movement (the reliable movement signal). Per-person calibration, one limb at a time (e.g. left vs right grip or arm lift).
- Keep movements small and seated. Full lifts cause heavy motion artifacts that wreck EEG, so max-effort lifting is future work, not the demo.
- Demo: live bar or avatar that lights up with effort; a therapist view comparing sessions over time.
- Dual-pronged: therapist view (evaluate progress across sessions) and patient view (do exercises at home, see recovery over time). No medical guarantees or claims; the therapist sets the exercises and limits.
- AI layer: (1) turns raw session data into plain-language progress summaries for patient and therapist, (2) writes a short auto-generated therapist report, (3) flags trends (plateau, fatigue, uneven left/right engagement) for the therapist to review, (4) gives encouragement and next-exercise suggestions chosen only from the therapist's approved list. AI never diagnoses or changes the plan on its own.
- Works standalone or with a therapist. **Self-guided mode:** wellness/fitness framing, with an AI coach that explains the user's own data, motivates, and suggests exercises only from a vetted low-risk library. It does not diagnose, prescribe rehab for an injury, or replace a clinician. Red-flag symptoms (sharp pain, numbness, sudden weakness, etc.) trigger a "see a professional" message. **Therapist mode:** the clinical layer above. Check the legal wording before the pitch.
- Camera form check: laptop webcam + a pose-estimation model (e.g. MediaPipe/MoveNet) tracks joint angles, range of motion, rep count, tempo, left/right symmetry and compensation (trunk lean). Combined with EEG gives "brain engagement vs actual movement". The AI turns it into plain feedback. Needs no rental; a webcam is enough. Form checking is general feedback, not a clinical assessment.
- Form-check plan: pick 2 to 3 simple seated exercises; use MediaPipe landmarks to compute joint angles, rep count and range of motion; define "good form" as angle rules (e.g. elbow range, trunk lean limit); check the rules against teammates' recordings of correct and deliberately wrong reps (roughly 100 samples per pose per Google's guidance). Public rehab datasets exist (UI-PRMD, KIMORE, IntelliRehabDS) but use Kinect/Vicon skeletons, not phone-camera landmarks, so use them for ideas and thresholds, not direct training. A trained model is a later upgrade. No verified library of reference exercise animations found; show the user's own skeleton with a green target zone.
- Delivery: build it as a **web app** (browser-based pose model, works on laptop and phone, no installer). The EEG side stays on the laptop and sends results to the page over a local WebSocket. A **camera-only phone version** is the scalability/accessibility story (headset-free mode). An Arduino UNO Q (2 GB) is available but not needed for this pipeline; possible later as a cheap sensor hub.
- Hardware to borrow (check current stock on the Libraries' Technology Lending page; Hunt and Hill): cameras, tablets, Arduino boards, possibly VR gear.
- Limits: scalp EEG does not measure muscle force. Claim "brain engagement", not "exertion". Not a medical device.

### 5. Hands-free computer or smart-home control
Eye movement moves a cursor, a clench clicks, blinks run lights or TV. Same detection code as idea 1.

### 6. Hand-grip control
Left vs right grip toggles music or lights, using mu/beta. Well understood, and the safe fallback if other detection underperforms. Needs per-person training.

### 7. Workload-aware app during everyday tasks
Workload gauge while someone does a simple task, with a harder condition (e.g. counting backward by 7) raising it. Matches the brief's own example. Keep the task seated, since walking and cooking corrupt EEG badly.

### 8. Walking or cooking monitoring
Sounds good, high risk. Real full-body motion ruins the signal. Future-work slide only.

## Cross-cutting
- **Scalable story:** LSL means any headset works. Input can later swap to a cheap headband, EMG band or webcam. Calibration is about a minute per person. Open source.
- **Pitch lines:** "nothing about us without us" (talk to people who use these tools if possible), brain data stays local, built on a research system but designed for consumer devices.
- **Limitations to say out loud:** demoing on able-bodied volunteers, small sample, research prototype and not a medical device, people with advanced ALS may lose eye control (needs a fallback input), EEG caps fit some hair types worse (affects equity, which the headset-free version partly answers).
- **Testing:** add synthetic blinks and clenches to `src/stream_replay.py` so detectors have an answer key, like the mu-drop test.

## Suggested direction (not decided)
Blink and clench detection → two-switch scanning board with speech (Switch mode) → AI-suggested ranked replies with confirmation → emergency alert → Hands-free mode as a profile on the same engine if time allows. Overload overlay (idea 3) as the "calm" command and a future extension. Seizure idea (4) only if there's slack.

## First-rotation recording plan
About 7 minutes per team. Ask ANT before the rotation how to put event markers into the recording and which export format keeps them. If markers don't survive, time the blocks with a stopwatch.
- Blinks: single, double, long/deliberate (several each).
- Jaw clenches: several, short and long.
- Eye left/right/up/down.
- Resting baseline, plus a typing or screen task.
- Everyday movements that must not trigger anything (reach, head turn, talk, chew).
