"""Pipeline smoke test: real fake-LSL stream -> connect -> pull -> process, end to end."""
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from pylsl import StreamInlet, resolve_byprop

from live_reader import process

SRC = Path(__file__).resolve().parent.parent / "src"


@pytest.fixture
def replay():
    p = subprocess.Popen([sys.executable, str(SRC / "stream_replay.py")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield p
    p.terminate()
    p.wait(timeout=5)


@pytest.mark.smoke
def test_stream_connects_and_processes(replay):
    streams = resolve_byprop("name", "eego-replay", timeout=15)
    assert streams, "replay stream never appeared"
    inlet = StreamInlet(streams[0])
    assert inlet.info().channel_count() == 24
    fs = inlet.info().nominal_srate()
    assert fs == 500

    rows, t0 = [], time.time()
    while time.time() - t0 < 5:
        chunk, _ = inlet.pull_chunk(timeout=0.5)
        rows.extend(chunk)
    # ~2500 expected; allow generous slack for startup/scheduling
    assert 1800 < len(rows) < 3000, f"got {len(rows)} samples in 5 s"

    out = process(np.asarray(rows[-1000:]), fs, [])
    assert "mu=" in out and "beta=" in out
