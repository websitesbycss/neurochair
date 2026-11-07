# NC State Neurotech Hackathon 2026: Team 2 Cheat Sheet

## Us
- **Team 2, ANT Neuro track**, hacking room **2232**
- Members: Sampath Kasina (NCSU CSC), Anirudh Bhaskar (NCSU ECE), Cameron Sheppard (NCSU CSC), Danil Bogdanov de Carvalho (Durham Tech, Eng), Tyler Richman (Duke BME), Ethan McMillan (UNCC Psych/Org Mgmt)
- Location: Engineering Building 3, 1840 Entrepreneur Dr, Raleigh. Discord: https://discord.gg/7ufV353jV

## The challenge (ANT Neuro track)
Build a **scalable, everyday-life application that uses movement, tracked through EEG, as its core input**, and make it respond in real time.
- "Scalable" is a judging theme: show how it extends to more headsets, more users, different movements, and wider deployment.
- Final deliverable: a **3-minute in-person presentation with a live demo** covering both the technical side and the impact.

## Hardware
- 4× ANT Neuro **eego 24-channel** systems (eego amplifier EE-5xx/EE-511 + waveguard net cap)
- 24 referential EEG channels, 24-bit, sampling up to 4096 Hz. Software default is **500 Hz**, filters 0.3–30 Hz, impedance limits 20/200 kΩ.
- 2-bit TTL trigger input (DB25/BNC). Only rising edges count, and a pulse must last at least 2–3 sample periods. We probably won't need this unless we want hardware event markers.

## Data flow
1. **First rotation (required): record a dataset** of our target movement. It's exported from the eego software and handed over on a flash drive or by email.
   - Export formats: EEProbe .cnt (the default), Neuroscan .cnt, BrainVision .eeg, **EDF+ .edf**. **Ask for EDF+ or BrainVision.** Both are easy to load with MNE (`mne.io.read_raw_edf` / `read_raw_brainvision`).
   - Make sure the events/annotations (when each movement happened) are in the export. Plan the movement protocol before we go: e.g. 5 s rest / 5 s movement × N trials, with someone marking events.
2. **Build offline** with that dataset.
3. **Later rotations: live test.** The eego laptop streams over **LSL** on ANT's router. We join their network with our laptop and read the stream with `pylsl`.
   - ⚠️ **The ANT network may have no internet. Install pylsl and all other dependencies BEFORE the rotation.**
   - Tip: write a small script that replays our recorded file as a fake LSL stream, so the whole real-time pipeline can be built and tested without the headset.

## Our rotation slots (ANT track room 2201), 30 min each
| Day | Time |
|---|---|
| Sat | **1:00–1:30 PM** (first: data collection) |
| Sat | 2:00–2:30 PM |
| Sat | 3:30–4:00 PM |
| Sat | 4:30–5:00 PM |
| Sat | 6:00–6:30 PM |
| Sat | 7:00–7:30 PM |
| Sun | 9:30–10:00 AM |
| Sun | 10:30–11:00 AM |

## Schedule
**Sat Nov 7**: 9:00 check-in (lobby) · 9:45 kickoff (main room) · 10:30 track briefing (2201) · 11:00 hacking starts · 12:15 lunch (main room) · 1:00–8:30 rotations · 10:00 PM doors close
**Sun Nov 8**: 8:00 breakfast · 9:30 rotations open · **11:45 AM SUBMISSION DEADLINE (no exceptions)** · 12:00–1:15 lunch + judging (teams called to track room 2201) · 1:30 closing ceremony · 2:30 end

Main room: the itinerary says 2124, the floor map says 2142. It's the big lecture hall on the west end.

## Submission (by Sun 11:45 AM)
Form: https://docs.google.com/forms/d/e/1FAIpQLSep3uOVS9iSlW1UeKqp8RPBXBrWM58bF04POD1qgqX0Cg9r1Q/viewform
- Team number (2) and team name
- **Public** GitHub repo link (this repo: https://github.com/websitesbycss/neurotech; make sure it's public)
- Presentation as a downloaded **.pptx** file

## Resources
- Track resources folder: https://drive.google.com/drive/folders/1VrsfhE6BqlDHC5rqQ4ELRUuzplYYQmDb
- Waveguard onboarding videos: https://vimeo.com/showcase/10746202 (pw `wg-neuro-2023`)
- eego onboarding videos: https://vimeo.com/showcase/10746258 (pw `eego-neuro-2023`)
- pylsl: https://pypi.org/project/pylsl/

## Dev setup (offline-safe)
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt   # do this on every teammate's laptop BEFORE rotations
.venv/Scripts/python src/stream_replay.py                  # terminal 1: fake 24ch/500Hz LSL stream (or pass an .edf/.vhdr to replay real data)
.venv/Scripts/python src/live_reader.py                    # terminal 2: reads any LSL EEG stream, prints mu/beta power
```
`src/live_reader.py` works unchanged against ANT's live stream at the station. Put app logic in `process()`.
