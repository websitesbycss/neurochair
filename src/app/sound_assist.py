"""Sound alerts for deaf and hard-of-hearing users: laptop microphone -> YAMNet -> big visual alert.

YAMNet (Google, AudioSet) scores 521 sound classes on ~1 s of 16 kHz audio. We watch a short list of
classes that matter for safety and daily life (alarms, sirens, doorbell, knocking, phone, baby, shouting)
and show a large coloured alert when one is heard.

Setup:   .venv/Scripts/python -m pip install -r requirements-assist.txt
Usage:
    python src/app/sound_assist.py                 # live microphone, alert window
    python src/app/sound_assist.py --console       # live microphone, print only
    python src/app/sound_assist.py --list          # list audio input devices
    python src/app/sound_assist.py --device 2 --threshold 0.25
    python src/app/sound_assist.py --file test.wav # classify a WAV file
    python src/app/sound_assist.py --selftest      # synthetic 1 kHz tone, should come back as "Sine wave"
The first run downloads the YAMNet model (needs internet once; then cached).
"""
import argparse
import csv
import queue
import threading
import time
from fractions import Fraction

import numpy as np

SR = 16000
WIN = 15600            # 0.975 s, YAMNet's analysis window
HOP_S = 0.5            # classify twice a second
HOLD_S = 3.0           # keep an alert on screen this long after the last detection

# (keyword in the YAMNet class name, alert text, colour). First match wins, so specific ones go first.
ALERTS = [
    ("smoke detector", "SMOKE ALARM", "#c1121f"), ("fire alarm", "FIRE ALARM", "#c1121f"),
    ("car alarm", "CAR ALARM", "#c1121f"), ("alarm clock", "ALARM CLOCK", "#e85d04"),
    ("siren", "SIREN", "#c1121f"), ("alarm", "ALARM", "#c1121f"),
    ("vehicle horn", "CAR HORN", "#e85d04"), ("doorbell", "DOORBELL", "#1d4ed8"),
    ("ding-dong", "DOORBELL", "#1d4ed8"), ("knock", "KNOCKING", "#1d4ed8"),
    ("telephone", "PHONE RINGING", "#1d4ed8"), ("ringtone", "PHONE RINGING", "#1d4ed8"),
    ("baby cry", "BABY CRYING", "#7c3aed"), ("screaming", "SCREAMING", "#c1121f"),
    ("shout", "SOMEONE SHOUTING", "#e85d04"), ("yell", "SOMEONE SHOUTING", "#e85d04"),
    ("bark", "DOG BARKING", "#7c3aed"), ("shatter", "GLASS BREAKING", "#c1121f"),
    ("beep, bleep", "BEEPING", "#e85d04"),
]


def load_yamnet():
    import tensorflow as tf
    import tensorflow_hub as hub
    model = hub.load("https://tfhub.dev/google/yamnet/1")
    path = model.class_map_path().numpy().decode()
    with tf.io.gfile.GFile(path) as f:
        names = [row["display_name"] for row in csv.DictReader(f)]
    return model, names


def alert_table(names):
    """For every YAMNet class index, the (text, colour) alert it triggers, or None."""
    table = []
    for n in names:
        low = n.lower()
        table.append(next(((txt, col) for key, txt, col in ALERTS if key in low), None))
    return table


def classify(model, wav):
    """Mean class scores for a float32 mono 16 kHz waveform in [-1, 1]."""
    scores, _, _ = model(np.asarray(wav, dtype=np.float32))
    return scores.numpy().mean(axis=0)


def pick_alert(scores, table, threshold):
    best = None
    for i in np.argsort(-scores)[:25]:
        if scores[i] < threshold:
            break
        if table[i]:
            best = (table[i][0], table[i][1], float(scores[i]))
            break
    return best


def to_16k(x, sr_in):
    if sr_in == SR:
        return x
    from scipy.signal import resample_poly
    r = Fraction(SR, int(sr_in)).limit_denominator(1000)
    return resample_poly(x, r.numerator, r.denominator).astype(np.float32)


def top_text(scores, names, k=3):
    return "   ".join(f"{names[i]} {scores[i]:.2f}" for i in np.argsort(-scores)[:k])


def run_selftest(model, names):
    t = np.arange(SR * 2) / SR
    tone = 0.5 * np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    s = classify(model, tone)
    print("1 kHz tone ->", top_text(s, names))
    print("silence    ->", top_text(classify(model, np.zeros(SR * 2, np.float32)), names))


def run_file(model, names, table, path, threshold):
    from scipy.io import wavfile
    sr, x = wavfile.read(path)
    x = x.astype(np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if np.abs(x).max() > 1.5:              # integer PCM
        x /= np.abs(x).max()
    x = to_16k(x, sr)
    for start in range(0, max(1, len(x) - WIN + 1), int(SR * HOP_S)):
        s = classify(model, x[start:start + WIN])
        a = pick_alert(s, table, threshold)
        print(f"{start / SR:6.1f}s  {top_text(s, names)}" + (f"   >>> {a[0]}" if a else ""))


def mic_worker(model, names, table, device, threshold, out_q, stop):
    import sounddevice as sd
    info = sd.query_devices(device, "input")
    sr_in = int(info["default_samplerate"])
    buf = np.zeros(int(sr_in * 1.2), dtype=np.float32)
    lock = threading.Lock()

    def cb(indata, frames, t, status):
        nonlocal buf
        with lock:
            buf = np.concatenate([buf[frames:], indata[:, 0]])

    with sd.InputStream(device=device, channels=1, samplerate=sr_in, dtype="float32", callback=cb):
        out_q.put(("info", f"Listening on: {info['name']} ({sr_in} Hz)"))
        while not stop.is_set():
            time.sleep(HOP_S)
            with lock:
                x = buf.copy()
            x = to_16k(x, sr_in)[-WIN:]
            level = float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9))
            s = classify(model, x)
            out_q.put(("scores", top_text(s, names), pick_alert(s, table, threshold), level))


def run_console(out_q):
    while True:
        msg = out_q.get()
        if msg[0] == "info":
            print(msg[1], flush=True)
        else:
            _, top, alert, level = msg
            print(f"[{level:6.1f} dB] {top}" + (f"   >>> {alert[0]}" if alert else ""), flush=True)


def run_window(out_q, stop):
    import tkinter as tk
    root = tk.Tk()
    root.title("Sound alerts")
    root.geometry("900x500")
    big = tk.Label(root, text="Listening...", font=("Segoe UI", 64, "bold"), fg="white", bg="#222")
    big.pack(fill="both", expand=True)
    small = tk.Label(root, text="", font=("Consolas", 12), fg="#ddd", bg="#111", anchor="w", justify="left")
    small.pack(fill="x")
    state = {"until": 0.0}

    def poll():
        while not out_q.empty():
            msg = out_q.get()
            if msg[0] == "info":
                small.config(text=msg[1])
                continue
            _, top, alert, level = msg
            small.config(text=f"level {level:5.1f} dB   hearing: {top}")
            if alert:
                big.config(text=alert[0], bg=alert[1])
                state["until"] = time.time() + HOLD_S
        if time.time() > state["until"]:
            big.config(text="Listening...", bg="#222")
        root.after(100, poll)

    root.protocol("WM_DELETE_WINDOW", lambda: (stop.set(), root.destroy()))
    root.after(100, poll)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--device", type=int, default=None)
    ap.add_argument("--threshold", type=float, default=0.3)
    ap.add_argument("--console", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.list:
        import sounddevice as sd
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(f"{i:3d}  {d['name']}  ({int(d['default_samplerate'])} Hz)")
        return

    print("Loading YAMNet...", flush=True)
    model, names = load_yamnet()
    table = alert_table(names)
    if a.selftest:
        return run_selftest(model, names)
    if a.file:
        return run_file(model, names, table, a.file, a.threshold)

    out_q, stop = queue.Queue(), threading.Event()
    threading.Thread(target=mic_worker, args=(model, names, table, a.device, a.threshold, out_q, stop),
                     daemon=True).start()
    try:
        run_console(out_q) if a.console else run_window(out_q, stop)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
