# WheelchairBCI

Recording script and offline decoding analysis for the EEG-controlled wheelchair (subject S1, 2026-11-07).

- `wheelchair_record.py`: stimulus + recording script (SSVEP direction targets, "brain brake" hallway game,
  artifact and sync blocks). Usage in `RUN_ME.txt`, dependencies in `requirements.txt`.
- `analysis/`: loaders, eego `.cnt` to LSL alignment, preprocessing, SSVEP decoder, brake decoder.
- `analysis/out/REPORT.md`: results and the real-time recommendation. Figures and tables are next to it.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt -r requirements-analysis.txt
```

## Data (not in git)

Put the recording files in `WheelchairBCI/data/` (the folder is git-ignored):

- `S1_20261107_182835_wc_eeg.npz`, `_events.csv`, `_config.json` (session A, SSVEP)
- `S1_20261107_183742_wc_eeg.npz`, `_events.csv`, `_config.json` (session B, brake)
- exactly one eego recording: `<name>.cnt`, `<name>.evt`, `<name>.seg`

## Run

```bash
PYTHONUTF8=1 .venv/Scripts/python analysis/run_all.py     # about 15 min, writes analysis/out/
.venv/Scripts/python -m pytest tests                       # fast checks, no data needed
```
