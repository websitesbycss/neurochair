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

## Interface contract (fill in once the movement + app are chosen)
- Model -> app: TBD, e.g. a class label plus confidence per 0.5 s window.
- Target movement: TBD. Record decisions in `docs/decisions.md`.
