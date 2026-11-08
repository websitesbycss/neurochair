"""Live SSVEP destination picker -> wheelchair (ideas.md #18).

Shows the same four flickering corner targets as WheelchairBCI/wheelchair_record.py
(Bathroom top-left 12 Hz, Kitchen top-right 8.57 Hz, Bed bottom-left 7.5 Hz, Door bottom-right 6.67 Hz
at 60 Hz refresh), decodes the live eego LSL stream with CCA, and sends {"cmd": "go", "dest": ...} on the
LSL marker stream "ChairCommands", which src/app/chair_drive.py --lsl turns into movement.

Decoder settings follow WheelchairBCI/analysis/out/REPORT.md (training-free method, 87.5 % at 4 s offline):
8 occipito-parietal channels (O1 Oz O2 P3 Pz P4 P7 P8), average reference over good non-mastoid channels,
60/120 Hz notch, 5-45 Hz band-pass (causal here, so it can run live), CCA with 3 harmonics, 4 s window.
Safety rules from the same report: flicker and decode only while armed (alpha makes rest look like 12 Hz),
a destination needs two consecutive agreeing windows, and braking stays on the keyboard because the
EEG brake isn't reliable yet.

Usage:
    python src/app/ssvep_live.py --offline-check data/<recording>.cnt   # replay the recorded trials
    python src/app/ssvep_live.py                     # live: headset on LSL, chair_drive.py --lsl running
    options: --bads Cz,C4,M2  --refresh 60  --fullscreen  --eeg-name <part of stream name>
Keys (live): SPACE arm (flicker until a destination is confirmed, max 12 s)   B brake   R resume   ESC quit
"""
import argparse
import json
import math
import threading
import time
from collections import deque

import numpy as np
from scipy import linalg, signal

TARGETS = ["Bathroom", "Kitchen", "Bed", "Door"]            # corner order: TL, TR, BL, BR
FRAMES_AT_60 = {"Bathroom": 5, "Kitchen": 7, "Bed": 8, "Door": 9}
OCC = ["O1", "Oz", "O2", "P3", "Pz", "P4", "P7", "P8"]
MASTOIDS = ["M1", "M2"]
STANDARD = ["Fp1", "Fp2", "F9", "F7", "F3", "Fz", "F4", "F8", "F10", "M1", "T7", "C3", "C4", "T8", "M2", "Cz",
            "P7", "P3", "Pz", "P4", "P8", "Oz", "O1", "O2", "T9", "T10", "P9", "P10"]
FS = 500.0
WIN_S, DELAY_S, STEP_S, NH, AGREE, ARM_MAX_S = 4.0, 0.14, 0.5, 3, 2, 12.0


def freqs_for(refresh):
    """Actual flicker frequencies for a display refresh rate (periods are whole frames)."""
    return {t: refresh / max(2, round(refresh / (60.0 / n))) for t, n in FRAMES_AT_60.items()}


def canon(names):
    lut = {s.lower(): s for s in STANDARD}
    return [lut.get(n.lower(), n) for n in names]


# ------------------------------------------------------------------ decoder core (same maths as analysis/ssvep.py)
def refs(f, n, nh, fs=FS):
    t = np.arange(n) / fs
    return np.vstack([fn(2 * np.pi * k * f * t) for k in range(1, nh + 1) for fn in (np.sin, np.cos)])


def cca_rho(X, Y, reg=1e-6):
    X = X - X.mean(1, keepdims=True)
    Y = Y - Y.mean(1, keepdims=True)
    n = X.shape[1]
    Cxx, Cyy, Cxy = X @ X.T / n, Y @ Y.T / n, X @ Y.T / n
    Cxx += reg * np.trace(Cxx) / len(Cxx) * np.eye(len(Cxx))
    Cyy += reg * np.trace(Cyy) / len(Cyy) * np.eye(len(Cyy))
    Kx = linalg.inv(linalg.cholesky(Cxx, lower=True))
    Ky = linalg.inv(linalg.cholesky(Cyy, lower=True))
    return float(linalg.svd(Kx @ Cxy @ Ky.T, compute_uv=False)[0])


def cca_scores(X, freqs, nh=NH, fs=FS):
    """X: (channels, samples) already filtered. Returns one correlation per target, in TARGETS order."""
    return np.array([cca_rho(X, refs(freqs[t], X.shape[1], nh, fs)) for t in TARGETS])


class Pipeline:
    """Causal sample-by-sample preprocessing so it can run live: re-reference, notch, band-pass."""

    def __init__(self, ch, bads, fs=FS):
        self.ch = canon(ch)
        bads = set(canon(bads))
        self.ref_idx = [i for i, c in enumerate(self.ch) if c not in bads and c not in MASTOIDS]
        self.occ_idx = [self.ch.index(c) for c in OCC if c in self.ch and c not in bads]
        if len(self.occ_idx) < 3:
            raise SystemExit(f"Need occipital channels; stream has {self.ch}")
        secs = [signal.tf2sos(*signal.iirnotch(f, 30.0, fs)) for f in (60.0, 120.0) if f < fs / 2]
        secs.append(signal.butter(4, [5, 45], btype="band", fs=fs, output="sos"))
        self.sos = np.vstack(secs)
        self.zi = None

    def process(self, X):
        """X: (samples, channels) in microvolts -> (occ channels, samples) filtered."""
        X = np.asarray(X, float)
        Y = (X[:, self.occ_idx] - X[:, self.ref_idx].mean(1, keepdims=True)).T
        if self.zi is None:
            self.zi = signal.sosfilt_zi(self.sos)[:, None, :] * Y[:, :1][None, :, :].transpose(0, 1, 2)
        Y, self.zi = signal.sosfilt(self.sos, Y, axis=-1, zi=self.zi)
        return Y


class Decider:
    """A destination counts only when AGREE consecutive windows pick the same target."""

    def __init__(self, agree=AGREE):
        self.agree, self.hist = agree, []

    def update(self, label):
        self.hist = (self.hist + [label])[-self.agree:]
        return label if len(self.hist) == self.agree and len(set(self.hist)) == 1 else None

    def reset(self):
        self.hist = []


# ------------------------------------------------------------------ offline check on a recorded session
def offline_check(path, bads):
    import mne
    mne.set_log_level("ERROR")
    raw = mne.io.read_raw_ant(path, preload=True)
    fs = raw.info["sfreq"]
    pipe = Pipeline(raw.ch_names, bads, fs)
    Y = pipe.process(raw.get_data().T * 1e6)
    on = [(a["onset"], a["description"].split("|")[2].split("#")[0]) for a in raw.annotations
          if "ssvep|flicker_on|" in a["description"]]
    off = sorted(a["onset"] for a in raw.annotations if "ssvep|flicker_off|" in a["description"])
    freqs = freqs_for(60.0)
    win = int(WIN_S * fs)
    rows = []
    for t_on, label in on:
        nxt = [t for t in off if t > t_on]
        dur = (nxt[0] - t_on) if nxt else WIN_S + DELAY_S
        # first window = 0.14-4.14 s like the analysis; later windows only while the visual response lasts
        ends = [t_on + DELAY_S + WIN_S + k * STEP_S for k in range(4) if k == 0 or WIN_S + k * STEP_S <= dur + 1e-6]
        picks = []
        for t_end in ends:
            e = int(round(t_end * fs))
            picks.append(TARGETS[int(np.argmax(cca_scores(Y[:, e - win:e], freqs, NH, fs)))])
        d = Decider()
        confirmed = next((p for p in (d.update(p) for p in picks) if p), None)
        rows.append((label, picks[0] if picks else None, confirmed, dur))
    tgt = [r for r in rows if r[0] in TARGETS]
    cen = [r for r in rows if r[0] not in TARGETS]
    acc = np.mean([r[1] == r[0] for r in tgt])
    conf = [r for r in tgt if r[2]]
    print(f"{len(tgt)} target trials, {len(cen)} center trials, flicker lasted {np.median([r[3] for r in rows]):.1f} s")
    print(f"single 4 s window accuracy: {acc:.3f}   (analysis report: 0.875 with zero-phase filters)")
    if conf:
        print(f"two-window rule: decided {len(conf)}/{len(tgt)} targets, correct {np.mean([r[2] == r[0] for r in conf]):.3f}; "
              f"center trials that still produced a destination: {sum(1 for r in cen if r[2])}/{len(cen)}")
    else:
        print("two-window rule: flicker too short in this recording to evaluate two windows")
    return acc


# ------------------------------------------------------------------ live app
class Live:
    def __init__(self, a):
        from pylsl import StreamInfo, StreamInlet, StreamOutlet, resolve_byprop
        streams = [s for s in resolve_byprop("type", "EEG", timeout=10)
                   if not a.eeg_name or a.eeg_name.lower() in s.name().lower()]
        if not streams:
            raise SystemExit("No EEG stream on LSL (check the network / lsl_api.cfg / --eeg-name).")
        self.inlet = StreamInlet(streams[0], max_buflen=30)
        info = self.inlet.info()
        ch, c = [], info.desc().child("channels").child("channel")
        for _ in range(info.channel_count()):
            ch.append(c.child_value("label"))
            c = c.next_sibling()
        eeg_cols = [i for i, n in enumerate(ch) if n.lower() != "trigger"]
        self.cols, self.fs = eeg_cols, info.nominal_srate()
        self.pipe = Pipeline([ch[i] for i in eeg_cols], a.bads.split(","), self.fs)
        self.buf = deque(maxlen=int(self.fs * (WIN_S + 2)))
        self.out = StreamOutlet(StreamInfo("ChairCommands", "Markers", 1, 0, "string", "chair-cmd-ssvep"))
        self.freqs = None
        self.state, self.t_arm, self.msg, self.scores = "IDLE", 0.0, "", None
        self.decider = Decider()
        self.lock = threading.Lock()
        print(f"EEG: {streams[0].name()} ({len(eeg_cols)} ch @ {self.fs} Hz). Sending on LSL 'ChairCommands'.")
        threading.Thread(target=self.reader, daemon=True).start()

    def send(self, obj):
        self.out.push_sample([json.dumps(obj)])

    def reader(self):
        next_decode = 0.0
        while True:
            chunk, _ = self.inlet.pull_chunk(timeout=0.2)
            if chunk:
                Y = self.pipe.process(np.asarray(chunk)[:, self.cols])
                with self.lock:
                    self.buf.extend(Y.T)
            with self.lock:
                armed = self.state == "ARMED"
                t_arm = self.t_arm
            now = time.time()
            if not armed or now - t_arm < DELAY_S + WIN_S or now < next_decode or self.freqs is None:
                continue
            next_decode = now + STEP_S
            with self.lock:
                X = np.asarray(self.buf)[-int(WIN_S * self.fs):].T
            s = cca_scores(X, self.freqs, NH, self.fs)
            pick = TARGETS[int(np.argmax(s))]
            confirmed = self.decider.update(pick)
            with self.lock:
                self.scores = s
                if confirmed and self.state == "ARMED":
                    self.send({"cmd": "go", "dest": confirmed})
                    self.state, self.msg, self.t_arm = "DONE", f"Going to {confirmed}", now

    def run(self, a):
        import pygame
        pygame.init()
        flags = pygame.SCALED | (pygame.FULLSCREEN if a.fullscreen else 0)
        try:
            screen = pygame.display.set_mode((1280, 800), flags, vsync=1)
        except pygame.error:
            screen = pygame.display.set_mode((1280, 800), flags)
        pygame.display.set_caption("Wheelchair destination (SSVEP)")
        W, H = screen.get_size()
        big, small = pygame.font.SysFont("segoeui", 44, bold=True), pygame.font.SysFont("segoeui", 24)
        clock = pygame.time.Clock()
        refresh = a.refresh or self.measure_refresh(pygame, screen, clock)
        self.freqs = freqs_for(refresh)
        periods = [max(2, round(refresh / self.freqs[t])) for t in TARGETS]
        s, m = 170, 40
        rects = [pygame.Rect(m, m, s, s), pygame.Rect(W - m - s, m, s, s),
                 pygame.Rect(m, H - m - s - 30, s, s), pygame.Rect(W - m - s, H - m - s - 30, s, s)]
        print("Flicker: " + ", ".join(f"{t} {self.freqs[t]:.2f} Hz" for t in TARGETS) + f" (refresh {refresh:.0f} Hz)")
        frame = 0
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return
                if e.type == pygame.KEYDOWN:
                    with self.lock:
                        if e.key == pygame.K_SPACE and self.state != "ARMED":
                            self.decider.reset()
                            self.state, self.t_arm, self.msg = "ARMED", time.time(), ""
                        elif e.key == pygame.K_b:
                            self.send({"cmd": "brake"})
                            self.state, self.msg = "IDLE", "BRAKE sent"
                        elif e.key == pygame.K_r:
                            self.send({"cmd": "resume"})
                            self.msg = "resume sent"
            with self.lock:
                state, t_arm, msg, sc = self.state, self.t_arm, self.msg, self.scores
                if state == "ARMED" and time.time() - t_arm > ARM_MAX_S:
                    self.state, self.msg = "IDLE", "No destination chosen"
                if state == "DONE" and time.time() - t_arm > 3.0:
                    self.state = "IDLE"
            screen.fill((18, 18, 24))
            for i, (r, name) in enumerate(zip(rects, TARGETS)):
                if state == "ARMED":
                    on = (frame % periods[i]) < math.ceil(periods[i] / 2)
                    pygame.draw.rect(screen, (255, 255, 255) if on else (0, 0, 0), r)
                else:
                    pygame.draw.rect(screen, (70, 70, 80), r)
                lbl = small.render(name, True, (235, 235, 235))
                screen.blit(lbl, lbl.get_rect(center=(r.centerx, r.bottom + 18)))
            title = {"IDLE": "Press SPACE, then look at a destination", "ARMED": "Look at where you want to go",
                     "DONE": msg}[state]
            t = big.render(title, True, (255, 220, 0) if state == "DONE" else (235, 235, 235))
            screen.blit(t, t.get_rect(center=(W // 2, H // 2 - 20)))
            info = msg if state == "IDLE" else ""
            if sc is not None and state != "IDLE":
                info = "  ".join(f"{n} {v:.2f}" for n, v in zip(TARGETS, sc))
            txt = small.render(info + "    (B brake, R resume, ESC quit)", True, (160, 160, 170))
            screen.blit(txt, txt.get_rect(center=(W // 2, H // 2 + 40)))
            pygame.draw.circle(screen, (235, 235, 235), (W // 2, H // 2 + 90), 6)
            pygame.display.flip()
            clock.tick(refresh * 1.5)
            frame += 1

    @staticmethod
    def measure_refresh(pygame, screen, clock):
        t0, n = time.perf_counter(), 0
        while n < 120:
            pygame.event.pump()
            screen.fill((0, 0, 0))
            pygame.display.flip()
            n += 1
        hz = n / (time.perf_counter() - t0)
        return min((60, 75, 90, 100, 120, 144, 165, 240), key=lambda r: abs(r - hz))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline-check")
    ap.add_argument("--bads", default="Cz,C4,M2")
    ap.add_argument("--refresh", type=float, default=0)
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--eeg-name", default="")
    a = ap.parse_args()
    if a.offline_check:
        offline_check(a.offline_check, a.bads.split(","))
        return
    Live(a).run(a)


if __name__ == "__main__":
    main()
