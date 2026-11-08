# Demo video plan (15-20 s, goes inside the 3-minute pitch)

Concept: **"inside the user's head."** We hear the user's thoughts as a soft, roomy inner voice while we see what they see and what the chair does. Ends on the full-size render.

## Shot list (film in this order; landscape, 1080p, 60 fps if the phone allows, steady on a tripod or a stack of books)
| File name | What to film | Length |
|---|---|---|
| `C01_cap.mp4` | Close-up of the subject's head in the EEG cap, eyes open, calm. Slow push-in if you can. | 3 s |
| `C02_pov_screen.mp4` | Over-the-shoulder "POV" of the flickering destination screen (`ssvep_live.py`), the subject looking at the **Kitchen** target, then "Going to Kitchen". | 4 s |
| `C03_chair_go.mp4` | Table-level shot: the chair starts rolling toward a little "Kitchen" sign. | 3 s |
| `C04_person_ahead.mp4` | Screen recording of the GoPro window: box around a hand/person, "CHAIR STOPPED: person ahead" (Win + Alt + R records a window with the Xbox Game Bar). | 2 s |
| `C05_chair_stops.mp4` | Real camera: a hand steps in front of the chair, chair stops. | 2 s |
| `C06_doorbell.mp4` | Screen recording: sound-alert window flashes DOORBELL (play a doorbell clip from a phone). | 2 s |
| `C07_chair_turn.mp4` | Chair turns right and rolls on. | 3 s |

Tips: film each shot 3-5 times and keep the best. The flicker squares may look odd on a phone camera (they flicker faster than the camera's frame rate); that's fine, it reads as "brain interface". If the chair is driven with the arrow keys for a shot, that's OK for the video, but say so on the slide ("keyboard stands in for EEG in this clip") unless it was really EEG.

## Voiceover (the inner voice)
Record in a quiet room, phone 15-20 cm from the mouth, calm, slightly breathy, one take per line, 1 s of silence before and after. Save as `VO1.m4a` ... `VO4.m4a` (or .wav).
| Line | When | Text |
|---|---|---|
| VO1 | over C01-C02 | "Kitchen." |
| VO2 | over C03 | "Okay... let's go." |
| VO3 | over C04-C05 | "Whoa, someone's there." |
| VO4 | over C07 | "Right." |
The laptop's own spoken alert ("Stopping, person ahead") can stay in C04 as the co-pilot's voice, so there are two voices: the user's thoughts and the chair's.

## Edit (done in Premiere Pro)
- 1920 x 1080, 16:9 for the slides, about 18 s, exported as H.264 .mp4.
- Inner-voice sound: reverb + softened highs on the VO, a little louder in the middle of the mix; a low hum bed under the "inside the head" parts.
- Text: a title card ("What if you could move just by looking?"), small labels ("EEG decodes: KITCHEN", "Co-pilot: person ahead", "Sound alert: DOORBELL"), end card with the project name, "You choose. It keeps you safe.", and the full-size render `cad/renders/power_chair_hero.png`.
- Small animations: slow zoom-ins, quick fades/cuts, labels sliding/fading in.

## Hand-off
Put every clip and VO file in `C:\Coding Projects\neurotech\video\raw\` (git-ignored, too big for the repo) and open Premiere Pro with the MCP plugin running, then tell Claude "clips are in".
