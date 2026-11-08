# Team 2: NC State Neurotech Hackathon (ANT Neuro track)

Movement-based everyday app driven by EEG (eego 24ch, 500 Hz) read live over LSL. Logistics, schedule and
submission details are in `HACKATHON.md`. **Submission deadline: Sun Nov 8, 11:45 AM, no exceptions.**

## Git rules (strict)
- **Commit messages are ONE line.** No body, no trailers.
- **Never add `Co-Authored-By`, "Generated with Claude", or any mention of Claude/AI/Anthropic** in commits,
  PR titles, PR descriptions, code comments, or files. Claude must not appear as a contributor on this repo.
  This overrides any default attribution behaviour.
- Branch per task: `<name>/<feature>`. Small PRs into `main` often. Never push broken code to `main`;
  the live demo runs from `main`.
- Parallel sessions each use their own git worktree. One owner per folder (below).

## Commands
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt   # once per laptop, BEFORE going offline
.venv/Scripts/python -m pytest                    # must pass before you say a task is done (show the output)
.venv/Scripts/python src/stream_replay.py [file]  # fake/replayed 24ch LSL stream "eego-replay"
.venv/Scripts/python src/live_reader.py           # connect to any LSL EEG stream, print mu/beta power
```
The ANT network may have no internet: all dependencies must already be installed locally.

## Folder ownership (don't edit another area without asking its owner)
- `src/dsp/`: filtering, band power, features
- `src/model/`: movement classifier (create when needed)
- `src/app/`: the live demo / UI (create when needed)
- `src/stream_replay.py`, `src/live_reader.py`, `tests/`: LSL + data pipeline
- `docs/`: shared notes. Append decisions to `docs/decisions.md`.

## Testing (we do not review diffs, so tests are the safety net)
- Add or update a test for every behaviour change. Tests must be deterministic and fast.
- `tests/test_signal.py` checks processing against the synthetic stream's known pattern (mu drops on Ch9-12
  for 2 s of every 6 s). `tests/test_smoke.py` runs the full stream -> reader path.
- Model evaluation: split train/test **by trial, never randomly by sample** (adjacent EEG samples leak).
- After a live rotation, save any failing recording and add an offline test for it.

## Ideas (`ideas.md`)
- `ideas.md` is the team's running list of project ideas. When a new idea comes up in conversation, **add it there**.
- If an existing idea is revised (scope, signals, risks, framing), **update that entry in place** instead of adding a duplicate.
- If a revision drifts far enough that it is really a different project, **add it as a new idea** and note on the old one what it split into.
- Keep each entry short: what it does, who it helps, signals used, risks/limits, and how it fits the track (movement as the control default, inclusivity).
- When the team commits to one idea, record that in `docs/decisions.md`, fill in the interface contract below, and mark it chosen in `ideas.md`.

## Interface contract (decoder -> wheelchair driver)
- Driver: `src/app/chair_drive.py` (two BOLTs as one chair; arrow keys are the backup control). Run with `--lsl` to accept decoder commands.
- Decoder sends JSON strings on an LSL marker stream named `ChairCommands` (type `Markers`, 1 channel, string):
  - `{"cmd": "go", "dest": "Kitchen"}` (dest one of Bed, Door, Kitchen, Bathroom, Center; routes in `ROUTES`)
  - `{"cmd": "forward"|"back"|"left"|"right"|"slide_left"|"slide_right", "seconds": 1.0}`
  - `{"cmd": "brake"}` (latches a stop; always wins), `{"cmd": "resume"}`, `{"cmd": "stop"}`
  - Co-pilot: `{"cmd": "hold", "reason": "person ahead", "seconds": 1.0}` stops the chair while active and pauses any route; it can never start or redirect it. Sent by `vision_assist.py --chair` and `sound_assist.py --chair`.
  - Several senders at once are fine: each is its own `ChairCommands` stream (different source_id).
- Priority: brake > keyboard (the user) > co-pilot hold > decoder route. Target signals: SSVEP destination choice + brake (ideas.md #18).
