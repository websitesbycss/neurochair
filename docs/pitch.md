# Pitch plan (3 minutes total, video included)

Working title: **"Supervised autopilot for brain-controlled wheelchairs"**. One-line promise: *you choose where to go with your eyes; the co-pilot keeps you safe; you are always the pilot.*

## Timing and slides
| Time | Slide | Say (short version) |
|---|---|---|
| 0:00-0:20 | 1. Problem | People with ALS, high spinal-cord injury or severe cerebral palsy often can't use a joystick. Brain-controlled wheelchairs exist in research labs, but they're slow, expensive and hard to trust. |
| 0:20-0:40 | 2. Our idea | A supervised autopilot. You pick a destination by looking at it; the chair drives; a camera and microphone co-pilot can stop it. Rule: **the AI can say no, never yes**: it can stop or pause, never start or choose where to go. |
| 0:40-1:10 | 3. Video (20-30 s) | Let it play. Talk over it only to name what's happening. |
| 1:10-1:45 | 4. How it works | EEG: 4 flickering targets, CCA decoder on 8 back-of-head channels: **87.5 % with no calibration** (chance 25 %), 90-92.5 % with a 3-minute calibration, 85 % running live. Chair: 3D-printed, two Sphero balls as drive wheels. Co-pilot: YOLO object detection ("person ahead"), YAMNet sound alerts for deaf users. Brake always wins. |
| 1:45-2:15 | 5. What we learned (honest science) | The brain brake isn't ready: before the hand moves, EEG only weakly separates danger from harmless (AUC 0.67), so the brake stays on a key. The 12 Hz target sits next to this subject's alpha rhythm, which is where every decoder error landed; next version moves it to 15/20 Hz. |
| 2:15-2:45 | 6. Why it scales | Works with any LSL headset; training-free decoder; same control software would drive a real power chair; co-pilot also serves blind and deaf users. Cheap parts: a printed frame, two toy robots, a GoPro, a laptop. |
| (in slide 6) | Full-size render | Show `cad/renders/power_chair_hero.png` / `_rear.png`: "the real version is a retrofit kit for the standard wheelchair people already own: hub-motor wheels, a battery, a controller, a camera, an E-stop." |
| 2:45-3:00 | 7. Close + team | "You choose. It keeps you safe." Team names, repo link. |

## Video storyboard (20-30 s)
Film several takes of each shot, keep the best; phone in landscape, steady, close to table height.
1. (3 s) Subject in the EEG cap looking at the flicker screen; the "Kitchen" target highlighted.
2. (6 s) Chair rolls toward the "Kitchen" sign on the table.
3. (5 s) A hand / teammate steps in front: GoPro view with "person ahead" box; chair stops.
4. (4 s) Doorbell plays: the sound-alert window flashes DOORBELL.
5. (3 s) Brake press: chair stops dead.
6. (3 s) End card: name of the project.
Backup if the headset path fails: same shots with arrow-key control; say "keyboard stands in for the EEG here" on the slide.

## Likely judge questions
- **Why not let the AI drive?** Language models are too slow and not guaranteed to answer the same way twice; a stop must be instant and certain. Rules drive; models see and hear.
- **How accurate is it really?** One subject, one session: 87.5 % (no calibration), 90-92.5 % calibrated, 85 % live on the recorded data. 4-5 s per decision.
- **What about false selections when the user isn't choosing?** Targets only flicker when the user arms the picker, and two consecutive windows must agree before the chair moves.
- **Does it work for other people?** Not shown yet; one healthy subject. CCA needs no per-person training, which is promising, but it needs testing on more users, including people who'd actually use it.
- **Why Spheros?** A cheap, safe tabletop stand-in for a power chair's drive wheels; the same command layer would send to a real chair's motor controller.
- **Is it a medical device?** No, a research prototype.
