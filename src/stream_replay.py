"""Publish EEG as a fake LSL stream so the app can be built without the headset.

Usage:
  python src/stream_replay.py                      # synthetic 24ch @ 500 Hz
  python src/stream_replay.py data/recording.edf   # replay a recorded file (loops)
"""
import sys
import time

import numpy as np
from pylsl import StreamInfo, StreamOutlet

N_CH, SRATE, CHUNK = 24, 500, 25


def synthetic():
    t = 0
    rng = np.random.default_rng(0)
    while True:
        ts = (t + np.arange(CHUNK)) / SRATE
        x = rng.normal(0, 5, (CHUNK, N_CH))
        x += 20 * np.sin(2 * np.pi * 10 * ts)[:, None]  # 10 Hz alpha-ish
        # 2 s "movement" burst every 6 s: suppress 10 Hz on the motor channels
        if (ts[0] % 6) > 4:
            x[:, 8:12] -= 15 * np.sin(2 * np.pi * 10 * ts)[:, None]
        t += CHUNK
        yield x, [f"Ch{i + 1}" for i in range(N_CH)]


def from_file(path):
    import mne
    raw = mne.io.read_raw_edf(path, preload=True, verbose=False) if path.endswith(".edf") \
        else mne.io.read_raw_brainvision(path.replace(".eeg", ".vhdr"), preload=True, verbose=False)
    raw.resample(SRATE, verbose=False)
    data = raw.get_data().T * 1e6  # volts -> microvolts
    names = raw.ch_names
    while True:
        for i in range(0, len(data) - CHUNK, CHUNK):
            yield data[i:i + CHUNK], names


def main():
    gen = from_file(sys.argv[1]) if len(sys.argv) > 1 else synthetic()
    first, names = next(gen)
    info = StreamInfo("eego-replay", "EEG", first.shape[1], SRATE, "float32", "replay-001")
    chans = info.desc().append_child("channels")
    for n in names:
        chans.append_child("channel").append_child_value("label", n)
    outlet = StreamOutlet(info, chunk_size=CHUNK)
    print(f"Streaming {first.shape[1]} ch @ {SRATE} Hz. Ctrl+C to stop.")
    outlet.push_chunk(first.tolist())
    nxt = time.perf_counter()
    for chunk, _ in gen:
        nxt += CHUNK / SRATE
        time.sleep(max(0, nxt - time.perf_counter()))
        outlet.push_chunk(chunk.tolist())


if __name__ == "__main__":
    main()
