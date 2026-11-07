"""Connect to any LSL EEG stream (ANT's live eego one, or stream_replay.py) and
print a rolling band-power readout. Swap `process` for the real app logic.

Usage: python src/live_reader.py [stream_name]
"""
import sys
import time
from collections import deque

import numpy as np
from pylsl import StreamInlet, resolve_byprop

from dsp.features import BETA, MU, band_power

WINDOW_S = 2.0


def process(buf, fs, names):
    """Mu (8-12 Hz) vs beta (13-30 Hz) power: both drop over motor cortex during movement."""
    mu = band_power(buf, fs, *MU).mean()
    beta = band_power(buf, fs, *BETA).mean()
    return f"mu={mu:8.2f}  beta={beta:8.2f}"


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else None
    streams = resolve_byprop("name", name, timeout=10) if name else resolve_byprop("type", "EEG", timeout=10)
    if not streams:
        sys.exit("No LSL EEG stream found (are you on the ANT network / is the replay running?)")
    inlet = StreamInlet(streams[0], max_buflen=10)
    info = inlet.info()
    fs, n = info.nominal_srate(), info.channel_count()
    ch = info.desc().child("channels").child("channel")
    names = []
    for _ in range(n):
        names.append(ch.child_value("label")); ch = ch.next_sibling()
    print(f"Connected: {info.name()} | {n} ch @ {fs} Hz")
    buf = deque(maxlen=int(WINDOW_S * fs))
    last = time.time()
    while True:
        chunk, _ = inlet.pull_chunk(timeout=1.0)
        buf.extend(chunk)
        if len(buf) == buf.maxlen and time.time() - last > 0.5:
            last = time.time()
            print(process(np.asarray(buf), fs, names))


if __name__ == "__main__":
    main()
