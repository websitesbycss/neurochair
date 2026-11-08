# Project ideas (Team 2, ANT Neuro track)

Status: **chosen: idea 18, the Sphero-driven wheelchair** (with idea 19, camera and sound awareness, as a stretch goal). Logged in `docs/decisions.md`. The decoder -> driver message format still needs to go in the interface section of `CLAUDE.md`.

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

### 4c. Meta Ray-Ban glasses as the output and sensing side (extension to idea 1)
EEG blink/clench is the control; the glasses are the eyes, ears and voice. Ideas: (a) **audio scanning** over the glasses' open-ear speakers (options read aloud, blink selects), so a blind or low-vision user needs no screen; (b) **"what's in front of me"** on a blink: glasses camera frame goes to a vision model and the answer is spoken; (c) glasses mic detects a noisy environment, and combined with an EEG overload signal the app lowers the load.
- Developer access: Meta's Wearables Device Access Toolkit is a developer preview (late-2025 sources; check current status). It is for iOS/Android mobile apps, gives camera access, and uses Bluetooth for mic/speakers. Full access may depend on country and sign-up. A Mock Device Kit allows testing without glasses.
- Risks: needs a phone app bridge (EEG is on the laptop); we may not have glasses. Cheapest version needs no SDK: treat the glasses as a Bluetooth speaker for spoken output.
- Fits the track: movement (blink/clench) is the control; strong inclusivity angle for blind and low-vision users.

### 5. Hands-free computer or smart-home control
Eye movement moves a cursor, a clench clicks, blinks run lights or TV. Same detection code as idea 1.

### 6. Hand-grip control
Left vs right grip toggles music or lights, using mu/beta. Well understood, and the safe fallback if other detection underperforms. Needs per-person training.

### 7. Workload-aware app during everyday tasks
Workload gauge while someone does a simple task, with a harder condition (e.g. counting backward by 7) raising it. Matches the brief's own example. Keep the task seated, since walking and cooking corrupt EEG badly.

### 8. Walking or cooking monitoring
Sounds good, high risk. Real full-body motion ruins the signal. Future-work slide only.

### 9. Adaptive instrument / game for creative access
Blink, clench and eye movement play music or a game, with software that keeps any input musical (scale snapping, auto-harmony, adaptive difficulty). For kids and adults with limited movement who are shut out of music and play. Movement is the control; no LLM needed. Risk: latency must feel instant.

### 10. Reading aid from eye movements (dyslexia, ADHD)
Frontal channels pick up eye movement. Detect re-reading and stalling, then adapt the text (spacing, focus line, read-aloud). Unique because the activity is everyday reading. Risk: coarse without a real eye tracker; test early.
- Controlled-distraction extension: add timed distractions to see how reading changes. Frame as a **reading-support insight tool for students and teachers** ("here's where reading slowed or broke down"), NOT a diagnosis. EEG and eye-movement data can't diagnose dyslexia, ADHD or autism, and claiming to would need clinical validation. Suggest a professional evaluation when patterns persist.

### 11. Freezing-of-gait cueing (Parkinson's)
A motion sensor (e.g. on the Arduino UNO Q) detects a freeze while walking and fires a rhythmic audio or buzz cue, a known intervention. EEG optional (movement preparation). Risk: needs real walking data we can't get; keep to a demo and don't claim clinical benefit.

### 12. Attempted-movement mirror therapy (paralysis, stroke)
When the person tries to move a limb, motor cortex mu/beta drops; that triggers an on-screen or game limb. Reliable signal, strong rehab rationale. Risk: overlaps idea 4b; could be framed as its patient-facing mode.

### 13. Condition research: where EEG actually helps (summary of what we found)
- **Good EEG fit:** epilepsy (seizure detection; see idea 4), stroke/paralysis (attempted movement, ideas 4b and 12), Parkinson's freezing of gait (research EEG biomarkers such as midfrontal beta; mostly offline studies, no real-time detection found), ADHD (an EEG theta/beta device is FDA-cleared only as an aid alongside clinical evaluation, ages 6 to 17; neurofeedback evidence is mixed and contradictory).
- **Weak EEG fit:** insomnia, chronic pain, tinnitus (neurofeedback evidence poor). Don't build on these.
- **Asthma:** EEG doesn't read breathing. A separate asthma idea would be a **breathing coach** using phone camera chest-motion, a chest motion sensor (UNO Q) or phone mic. Research exists (a UK app combining chest motion and breath sounds is in development; camera respiratory-rate apps lack clinical validation). Mostly non-EEG, so it fits the track poorly. No diagnosis or inhaler claims.

### 14. Brainstorm: not condition-specific (all use movement as control; none chosen)
- **Assistive robot arm:** jaw clench or blink drives a small tabletop arm (servos on the Arduino UNO Q) to bring a cup or spoon. Strong physical demo. Risk: build time, safety (small, slow, low force).
- **Alertness guard (drowsy driving):** blink duration and rate (Fp1/Fp2) plus head movement flag drowsiness and trigger a warning. Established markers; scalable to any headband. Camera-only version (webcam or GoPro + pose/eye-closure model) works without a headset. Demo: laptop driving game, with eye closure acted on cue (we can't safely induce real drowsiness, so no claim of validated detection).
- **Auto-rewind study aid:** detects attention drifting and rewinds the last 30 seconds of a lecture video. Risk: attention detection is only moderately reliable.
- **Hands-busy mode:** cooks, mechanics and surgeons clench or blink to advance step-by-step instructions while a camera and AI identify where they are. Situational need, easy to explain.
- **Silent remote:** discreet input where hands and voice are out (meetings, classrooms, noisy sites). Gimmicky but a good way to run our own presentation slides.
- **Drone or RC car control:** eye and jaw movements steer it. Cool, but needs a clearer "useful" angle.

### 15. Phantom-squeeze yes/no for people who can't move or speak (coma, brain injury)
Imagined left-hand squeeze = "yes", right-hand = "no" (motor imagery: mu/beta drop over C4 or C3). Aimed at people who may understand but can't move or speak. Research exists on detecting awareness this way, but it's hard and high-stakes.
- Risks: untrained users are often only about 70 to 80% accurate, patients likely lower; we can only test on healthy volunteers; our first pilot recording showed nothing clear at C3/C4 (unlabelled, noisy). Needs many trials and a confidence score, never a single answer. Frame as a research prototype; never claim it measures consciousness or replace a clinician.
- Needs a proper cued left/right imagery dataset (about 20 trials per hand) from the next rotation.

### 16. Assistive smart glove (tendon glove driven by servos)
Gardening glove with fishing-line "tendons" to the fingers, pulled by servos at the wrist (UNO Q drives them), to help elderly people with weakened grip close the hand when they try to squeeze. Frame as grip assistance, not treatment.
- Trigger: attempted-grip EEG is the weakest signal we have; start with a reliable trigger (jaw clench or blink) and swap in attempted grip if it works.
- Safety: low-torque servos, force and speed limits, user can always overpower it, instant stop. Never let a noisy classifier drive a strong pull.
- Parts: servos and fishing line are not in the library list (buy); 3D printer (Prusa), soldering station and multimeter are available; power bank for portable power.
- Ties to 15: same core signal (left/right hand intent); the glove closing is also movement feedback for the user.

### 17. Cheap hardware options (no purchases; borrow from Hunt/Hill)
Servo glove was judged too expensive and difficult (about $30 to $40 per servo plus build). Alternatives using borrowed gear and the Arduino UNO Q:
- **Bedside call and yes/no beacon:** blink or clench patterns (triple blink = call, left/right = yes/no) show on the UNO Q's LED matrix and sound on a borrowed Bluetooth speaker. For someone who can't reach a call button. No parts to buy. Verify the UNO Q matrix and how it connects before committing.
- **Sphero BOLT steering:** blink, clench or hand intent drives a borrowed robotic ball through its Python library. Easy and visual; weaker "useful" angle (frame as remote errands or mobility proxy). Check library support for BOLT.
- **Page turner:** SK Remote Controlled Page Turner (Hill) triggered by the UNO Q wired across its remote button. Medium difficulty, needs soldering; software-only fallback is blink/clench flipping pages on a laptop PDF or Kindle app.
- **Camera-only drowsy-driving alert:** webcam or GoPro, no extra hardware.

### 18. Sphero-driven wheelchair (CHOSEN; main build)
**Status: chosen as the team's project.** A 3D-printed tabletop power wheelchair whose two front "wheels" are Sphero BOLTs. EEG chooses where it goes (SSVEP) and stops it (brake); idea 19 adds camera and sound awareness. Only the **main** chair is being built (the one-BOLT mini is shelved). Design, STLs, print and assembly plan: `cad/` (`cad/README.md`, model generated by `cad/wheelchair.py` in Blender).

**Pitch framing: a supervised AI autopilot for wheelchairs (shared control).** The user is the pilot; the AI is a co-pilot that can slow down or stop, but never starts moving or picks a destination on its own ("the AI can say no, never yes"). Precedent: brain-controlled wheelchairs with shared control already exist in research (Millán's group: the BCI gives coarse commands, the chair handles obstacles; a 2022 study had three people with tetraplegia drive a real wheelchair through a hospital obstacle course). Ours puts that on cheap hardware with added sound and vision awareness.
- Priority order (highest wins):
  1. User brake: EEG brake signal or a manual STOP key stops both balls immediately.
  2. AI safety stop: camera sees a person/obstacle ahead, or a sound alert (alarm, siren) fires: slow or stop, and tell the user why (spoken + on screen).
  3. User intent: SSVEP destination choice; the AI drives the route.
  4. "Hands on the wheel": the chair keeps moving only while the user keeps confirming (e.g. a jaw clench or a glance at a "continue" target every few seconds), like a driver-attention check. No confirmation: it pauses.
- Demo script: user picks "Kitchen" with SSVEP -> chair drives; a teammate steps in front -> "person ahead", chair stops; a doorbell plays -> on-screen alert, chair pauses; user brake -> immediate stop.
- Keep the AI to stop/slow/pause. Don't let it steer around obstacles: one forward camera gives no distances, can't see beside/behind the chair, doesn't recognise walls or the table edge (an AI that swerves could drive off the table), and the chair's own position drifts. A wrong stop is safe; a wrong swerve isn't. Instead: **stop and ask** ("obstacle ahead: left or right?"), and the user answers with SSVEP or a clench.
- Which AI does what:
  - Destination (SSVEP): CCA / filter-bank CCA (little or no training) or TRCA if there's enough calibration data. Teammates' decoder.
  - Brake/danger: small classifier (e.g. LDA) on the brake-task data. Teammates' decoder.
  - What's ahead: YOLOv8n (working on the GoPro). What's heard: YAMNet (working, needs the Windows mic setting).
  - The autopilot decision itself: **plain rules, not a model** (brake > safety stop > user intent > attention check). Predictable, explainable, instant and offline.
- No big language model in the driving loop: replies take 0.5 s to several seconds (too late to brake), answers aren't guaranteed to be the same twice, and it needs internet. If wanted later, use one only as a talking co-pilot outside the loop (scene description for blind users from a GoPro frame, "route blocked, go left?" suggestions the user confirms, trip summaries), with YOLO labels as the offline fallback. Pitch line: "Rules keep it safe; AI makes it understandable."
- Wording: "supervised autopilot" or "shared control", like a car's lane-keeping assist. Comparing it directly to Tesla Autopilot invites questions about that system's safety record. Say clearly it's a research prototype, not a medical device.

**Hardware**
- Sphero BOLT: 73 mm ball, about 200 g, top speed 7.2 km/h. Sphero publishes no payload figure; its BOLT Chariot accessory (a cart of about 226 g) suggests one ball can move roughly 200 g on wheels on a flat floor.
- Each ball sits under a printed cone "ring" that touches it on a thin circle 50 degrees down from its top. It must slide, not grip: the top of a rolling ball moves at twice the ball's speed. Rub pencil graphite on the cone if it drags.
- Rear: two swivel casters (40 mm wheels) on octagonal pins, so the chair can go forward, back, sideways and turn.
- Printed weight about 190 g; roughly 2/3 rests on the balls (about 65 g per ball).
- Printing: on a friend's Bambu Lab A1 (PLA, 0.4 nozzle), 3 plates, about 5 to 6 h, about 200 g. Plate 1 (side frame, both rings, casters) prints first so the push test can happen before the seat/back plate. Glue-only assembly (gel CA), steps in `cad/README.md`.

**Geometry for the driving software** (chair frame: x right, y forward, origin on the floor under the seat centre; mm)
- Left BOLT centre (-75, +50), right BOLT centre (+75, +50): track 150 mm.
- Caster pivots (+/-75, -80); wheels trail 20 mm behind, so caster contact is about y = -100. Front-to-rear base about 150 mm.
- Footprint about 223 x 236 x 258 mm, seat height 158 mm.

**How it moves (control notes)**
- Each BOLT is an omnidirectional drive point: you command a heading (degrees) and a speed (0-255); the casters just follow. For a chair motion with forward speed v, sideways speed u and turn rate w, each ball's ground velocity is (u - w*y_i, v + w*x_i), using the ball positions above.
  - Forward/back: both balls, same heading, same speed.
  - Sideways: both balls heading 90 degrees off chair-forward (the casters swing round).
  - Spin in place: balls drive in opposite directions along y; the chair pivots about the point between them.
- Heading is in each BOLT's own gyro frame, fixed in the world, not the chair. Before driving, "aim" both balls so heading 0 = chair forward. After the chair turns, add the turned angle to later headings (track it open-loop by integrating w, or re-aim).
- Software (verified Sat night on Cameron's laptop): the unofficial `spherov2` Python library + `bleak` (now in requirements.txt). Both BOLTs found by Bluetooth scan: **SB-0A38** (left, lit blue "L") and **SB-61AA** (right, lit red "R"). **Both connect at once from one laptop** (about 12 s to connect) using `SpheroEduAPI`; LEDs and matrix work. Driving not tested yet. Only one app can hold a ball at a time: close the Sphero Edu app / phone Bluetooth before running Python.
- Always have a big STOP key and a low speed cap (start around 40-60 out of 255).
- **Driver built: `src/app/chair_drive.py`.** Arrow-key backup control plus decoder commands over LSL (`ChairCommands`, format in CLAUDE.md). Aim mode at startup (back lights to the back of the chair), Space = brake, speed cap 50 by default, tandem kinematics unit-tested (`tests/test_chair_drive.py`), connects to both BOLTs. Not yet driven on the real chair; routes in `ROUTES` are placeholders to tune on the table.

**EEG side (from the teammates' recording)**
- Recording: `data/Danil_Bogdanov_2026-11-07_18-28-42.cnt` (16.3 min, 24 ch, 500 Hz, 531 markers from an LSL stream named `WheelchairMarkers`). Local only: `data/` is gitignored, so get the file from whoever recorded it. Read it with `mne.io.read_raw_ant` (needs `antio`, in requirements.txt). Channel names are partly lowercase (`c3`, `oz`, ...): match them case-insensitively.
- Task 1, SSVEP destination choice: five flickering targets, Bed, Door, Kitchen, Bathroom, Center (10 trials each; markers cue / flicker_on / flicker_off with frame counts). Uses the occipital channels o1, o2, oz.
- Task 2, brake: danger vs harmless objects (person, ball, cart) with brake_press and outcome markers.
- Suggested interface (decoder -> driver): `{"cmd": "go", "dest": "Kitchen"}` or `{"cmd": "brake"}`, for example as an LSL marker stream. The driver maps each destination to a fixed tabletop route; brake always wins and stops both balls immediately. Exact format is up to the decoder owner; record it in `docs/decisions.md` and in the CLAUDE.md interface section.

**Integration status (Sat night, branch `cameron/live-ssvep`, built on Sampath's `sampath/wheelchair-bci`)**
- Sampath's analysis (`WheelchairBCI/analysis/out/REPORT.md`): SSVEP 4-target choice 87.5 % at 4 s with training-free CCA, 90-92.5 % with TRCA / extended CCA after a ~3 min calibration. EEG brake not ready (pre-press AUC 0.67, ~30 % false alarms): **brake stays on the keyboard**. All residual SSVEP errors land on 12 Hz (Bathroom), next to the subject's 11.25 Hz alpha; the report suggests 15/20 Hz targets next time.
- `src/app/ssvep_live.py`: live picker using the same stimulus and decoder settings, causal filters; **85 % on the recorded session** (`--offline-check`). Flicker only when armed (SPACE), two agreeing 4 s windows (0.5 s apart) before sending `{"cmd": "go", "dest": ...}`.
- Decoder -> driver link rehearsed in simulation: `chair_drive.py --sim --lsl` received go / brake / resume and ignored an unknown destination.
- `src/stream_replay.py` now replays eego `.cnt` recordings as a live LSL stream (prints the recorded markers as they pass).
- **Supervised autopilot built:** `vision_assist.py --chair` sends a hold while a close obstacle (person, dog, chair, bag...) is in the middle third of the view; `sound_assist.py --chair` sends a 3 s hold on alarms, sirens, doorbell, knocking etc. The driver stops while held, pauses the route and resumes it afterwards; priority brake > keyboard > hold > route; tested (unit tests + simulation with decoder and camera senders at once). Not yet tried on the real chair.
- Judge-facing `README.md` and `docs/pitch.md` (3-minute plan, video storyboard, likely questions) drafted.

**Risks and checks**
- Push test before the heavy plate: a light board with about 150 g resting on both balls (plus something rolling at the back), then drive forward. If the balls spin or wobble in place instead of rolling, the chair needs to get lighter.
- Ring friction against the ball shell (graphite helps; it may scuff the clear shell).
- Two BOLTs over Bluetooth at once, and keeping their headings aligned with the chair.
- Nothing has been printed or driven yet; the part clearances are standard but unverified.

### 19. Camera and sound awareness on the wheelchair (stretch goal, after driving works)
Object detection spoken aloud for blind and low-vision users, and big visual sound alerts for deaf and hard-of-hearing users. Code is in `src/app/`; the extra packages are in `requirements-assist.txt` (large download: `.venv/Scripts/python -m pip install -r requirements-assist.txt`).

**Object detection (`src/app/vision_assist.py`): working with the GoPro over USB**
- Run `python src/app/vision_assist.py --gopro-usb`. Quit the GoPro Webcam app first (it grabs the video port and only shows a placeholder picture). The script finds the GoPro's USB network, starts webcam mode at 720p (`--res 12` for 1080p), keeps the camera awake and reconnects if the feed stalls.
- YOLOv8n on the laptop CPU; it speaks "person ahead" / "chair on the left" (no repeat within 4 s) and runs smoothly at roughly 10+ fps. `--no-voice` prints instead; `--image pic.jpg` tests one picture; `--list` shows cameras.
- Tested on a sample photo (a bus and three people) and on the live GoPro feed.

**Sound alerts (`src/app/sound_assist.py`): laptop microphone + YAMNet**
- Big coloured alert window for smoke/fire alarm, siren, car alarm, horn, doorbell, knocking, phone ringing, baby crying, shouting/screaming, dog barking, glass breaking and beeping. `--threshold` (default 0.3) sets sensitivity; `--console` prints instead; `--selftest` checks the model.
- Tested: a 1 kHz tone is classified "Beep, bleep" (0.89) and silence as "Silence". The live mic returned pure zeros on Cameron's laptop: turn on Settings > Privacy & security > Microphone > "Let desktop apps access your microphone", then test with sound clips played from a phone.
- GoPro audio isn't used: its preview and webcam streams carry no audio (only its RTMP livestream does, with seconds of delay).

**Putting the GoPro on the moving chair**
- Mount: the GoPro adhesive mount on the rear of the seat pan, facing forward. It weighs about 154 g; at the rear most of that goes to the casters (about 20 g extra per ball). Never mount it at the front.
- Wireless (planned, untested): a cheap USB Wi-Fi adapter on the laptop joins the GoPro's own Wi-Fi while the built-in Wi-Fi stays on the EEG network; then use `--gopro` mode (Wi-Fi preview, about 0.2-0.3 s latency per GoPro's docs). Turning on the GoPro's Wi-Fi may need the GoPro Quik app or a Bluetooth command once.
- Fallback: a long USB cable held up from above so it never drags the chair (the BOLTs can't pull a cable).
- No Arduino UNO Q needed: it would add the board plus a battery pack, and it can't run the detector.
- Streaming drains the GoPro battery: charge it fully before the demo.
- Priority: only after the chair drives and the print is assembled.

## Things AI has made newly possible (pitch framing: "this wasn't feasible 10 years ago")
- **LLM-boosted communication** (idea 2): older word prediction was simple statistics; LLMs can expand abbreviations and propose whole replies (Google SpeakFaster, ALS eye-gaze users).
- **Phone-camera form tracking** (4b): real-time pose estimation on a phone, where this used to need Kinect or motion-capture hardware.
- **LLM coaching and reports** (4b): turning raw session data into plain-language feedback and therapist summaries.
- **On-device vision for blind/low-vision users** (4c): scene description that can run on a phone without internet (vendor claims, unverified).
- **EEG foundation models** (LaBraM, CBraMod): pretrained on thousands of hours of EEG to need less per-user training. Cross-subject variability is still the open problem; no live zero-calibration result found, so don't rely on it this weekend.
- **LLM-assisted speech neuroprostheses:** implant-based systems reached 62 words per minute for an ALS patient in 2023. Implants only; useful for a "where this is heading" slide, not for scalp EEG.

## Cross-cutting
- **Scalable story:** LSL means any headset works. Input can later swap to a cheap headband, EMG band or webcam. Calibration is about a minute per person. Open source.
- **Pitch lines:** "nothing about us without us" (talk to people who use these tools if possible), brain data stays local, built on a research system but designed for consumer devices.
- **Limitations to say out loud:** demoing on able-bodied volunteers, small sample, research prototype and not a medical device, people with advanced ALS may lose eye control (needs a fallback input), EEG caps fit some hair types worse (affects equity, which the headset-free version partly answers).
- **Testing:** add synthetic blinks and clenches to `src/stream_replay.py` so detectors have an answer key, like the mu-drop test.

## Suggested direction (superseded: the team chose idea 18, the Sphero wheelchair)
Blink and clench detection → two-switch scanning board with speech (Switch mode) → AI-suggested ranked replies with confirmation → emergency alert → Hands-free mode as a profile on the same engine if time allows. Overload overlay (idea 3) as the "calm" command and a future extension. Seizure idea (4) only if there's slack.

## First-rotation recording plan
About 7 minutes per team. Ask ANT before the rotation how to put event markers into the recording and which export format keeps them. If markers don't survive, time the blocks with a stopwatch.
- Blinks: single, double, long/deliberate (several each).
- Jaw clenches: several, short and long.
- Eye left/right/up/down.
- Resting baseline, plus a typing or screen task.
- Everyday movements that must not trigger anything (reach, head turn, talk, chew).
