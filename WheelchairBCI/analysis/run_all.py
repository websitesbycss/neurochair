"""Run the whole pipeline in order.  Usage (from the project folder):
    PYTHONUTF8=1 .venv/Scripts/python.exe analysis/run_all.py
Outputs go to analysis/out/ (figures, json, csv, markdown summaries)."""
import subprocess, sys, os, time
from pathlib import Path

HERE = Path(__file__).parent
STEPS = [
    "explore.py",             # first look at every file
    "align.py",               # cnt <-> npz alignment, segment structure, trigger timing
    "timing_check.py",        # which event-timing source is accurate (SSVEP phase coherence, VEPs)
    "preprocess_summary.py",  # channel quality, impedances, steps, filters
    "ssvep.py",               # direction decoder
    "brake.py",               # brain-brake decoder
]
env = dict(os.environ, PYTHONUTF8="1")
for s in STEPS:
    t0 = time.time()
    print(f"\n{'=' * 30} {s} {'=' * 30}", flush=True)
    r = subprocess.run([sys.executable, str(HERE / s)], env=env)
    print(f"--- {s} exit {r.returncode} in {time.time() - t0:.0f} s", flush=True)
    if r.returncode != 0:
        sys.exit(r.returncode)
