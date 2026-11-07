"""Record every sample of an LSL EEG stream to data/<name>.npz as a backup of the eego export.

Saves: data (samples x channels), ts (LSL timestamps), labels, trigger events.
Prints any nonzero value on the 'Trigger' channel (eego annotation keys, if forwarded over LSL).

Usage: python src/record_lsl.py [out_name] [seconds]   (Ctrl+C stops and saves)
"""
import sys
import time
from pathlib import Path

import numpy as np
from pylsl import StreamInlet, resolve_byprop


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else time.strftime("rec_%Y%m%d_%H%M%S")
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else None
    streams = resolve_byprop("type", "EEG", timeout=10)
    if not streams:
        sys.exit("No LSL EEG stream found")
    inlet = StreamInlet(streams[0], max_buflen=360)
    info = inlet.info()
    ch = info.desc().child("channels").child("channel")
    labels = []
    for _ in range(info.channel_count()):
        labels.append(ch.child_value("label")); ch = ch.next_sibling()
    trig = labels.index("Trigger") if "Trigger" in labels else None
    print(f"Recording {info.name()} ({len(labels)} ch @ {info.nominal_srate()} Hz). Ctrl+C to stop.", flush=True)
    rows, stamps, events = [], [], []
    mk_inlet, mk_times, mk_text, next_try = None, [], [], 0.0
    t0, last = time.time(), 0.0
    try:
        while limit is None or time.time() - t0 < limit:
            if mk_inlet is None and time.time() > next_try:
                found = resolve_byprop("type", "Markers", timeout=0.2)
                next_try = time.time() + 3
                if found:
                    mk_inlet = StreamInlet(found[0]); print("Connected to marker stream:", found[0].name(), flush=True)
            if mk_inlet is not None:
                m, mt = mk_inlet.pull_chunk(timeout=0.0)
                for v, t in zip(m, mt):
                    mk_times.append(t); mk_text.append(v[0]); print(f"marker {v[0]}", flush=True)
            chunk, ts = inlet.pull_chunk(timeout=0.2)
            if not ts:
                continue
            rows.extend(chunk); stamps.extend(ts)
            if trig is not None:
                for v, t in zip(np.asarray(chunk)[:, trig], ts):
                    if v != 0 and v != last:
                        events.append((t, v)); print(f"trigger {v:g} at t={t - stamps[0]:.2f}s", flush=True)
                    last = v
    except KeyboardInterrupt:
        pass
    out = Path("data"); out.mkdir(exist_ok=True)
    path = out / f"{name}.npz"
    np.savez(path, data=np.asarray(rows, dtype=np.float32), ts=np.asarray(stamps), labels=np.asarray(labels),
             events=np.asarray(events), marker_ts=np.asarray(mk_times), marker_text=np.asarray(mk_text))
    dur = (stamps[-1] - stamps[0]) if stamps else 0
    print(f"Saved {len(rows)} samples, {dur:.1f}s, {len(events)} trigger events, {len(mk_text)} cue markers -> {path}", flush=True)


if __name__ == "__main__":
    main()
