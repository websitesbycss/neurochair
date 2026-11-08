"""StillHere - EEG recording protocol for the ANT Neuro eego (NC State BCI Hackathon, Team 2).

Plays spoken commands, sends an LSL marker stream ("StillHereMarkers"), logs every
event to CSV, and (with --record-eeg) records the ANT LSL EEG stream on this laptop
so EEG and markers share one clock.

Blocks (default order, ~14 min):
  sync      3 jaw clenches (alignment backup for the eego export)
  baseline  60 s eyes closed rest + 30 s eyes open rest
  commands  8 right-hand + 8 left-hand "move" blocks (10 s), each followed by 10 s "stop"
  control   4 pairs: same commands, subject IGNORES them and counts back by 7s
  blinkyn   6 questions answered with blinks (double blink = yes, keep still = no), 5 s window
  call      5 cued sustained "call" squeezes (6 s) separated by 10-20 s rest
  yesno     8 questions, 10 s answer window (squeeze = yes, rest = no)
  artifacts 6 each: jaw clench, neck/shoulder tension, hard blinks
  sync      3 jaw clenches

Usage (run with the project venv):
  .venv/bin/python stillhere_record.py --subject S1 --name Tyler --record-eeg
  .venv/bin/python stillhere_record.py --list-streams
  .venv/bin/python stillhere_record.py --subject S2 --blocks sync,baseline,commands,control,sync

Keys during the run: SPACE pause/resume, ESC abort (data saved so far is kept).
"""
import argparse
import csv
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np
import pygame
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_streams, local_clock, proc_clocksync, proc_dejitter

ALL_BLOCKS = ["sync", "baseline", "commands", "control", "blinkyn", "call", "yesno", "artifacts", "sync"]


# ---------------------------------------------------------------- audio
class Voice:
    """Pre-renders every phrase to WAV with macOS `say` so playback starts instantly
    and the marker timestamp matches speech onset. Falls back to silent text."""

    def __init__(self, rate=22050):
        self.dir = tempfile.mkdtemp(prefix="stillhere_tts_")
        self.cache = {}
        self.has_say = shutil.which("say") is not None  # macOS only; elsewhere cues are text + beeps
        pygame.mixer.init(frequency=rate, size=-16, channels=1)
        self.rate = rate

    def prepare(self, phrases):
        if not self.has_say:
            return
        for p in set(phrases):
            if p in self.cache:
                continue
            path = os.path.join(self.dir, f"{len(self.cache)}.wav")
            subprocess.run(["say", "-o", path, f"--data-format=LEI16@{self.rate}", p], check=True)
            self.cache[p] = pygame.mixer.Sound(path)

    def say(self, phrase):
        snd = self.cache.get(phrase)
        if snd:
            snd.play()
            return snd.get_length()
        return 0.0

    def beep(self, freq=880, dur=0.15):
        t = np.arange(int(self.rate * dur)) / self.rate
        wave = (0.4 * 32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)
        channels = pygame.mixer.get_init()[2]  # mixer may already be stereo if pygame.init() ran first
        if channels > 1:
            wave = np.repeat(wave[:, None], channels, axis=1)
        pygame.sndarray.make_sound(np.ascontiguousarray(wave)).play()


# ---------------------------------------------------------------- EEG recorder
class EEGRecorder(threading.Thread):
    """Pulls the ANT EEG LSL stream into memory; timestamps are converted to this
    laptop's LSL clock (same clock as the markers)."""

    def __init__(self, stream_info):
        super().__init__(daemon=True)
        self.inlet = StreamInlet(stream_info, max_buflen=360, processing_flags=proc_clocksync | proc_dejitter)
        info = self.inlet.info()
        self.fs = info.nominal_srate()
        self.name = info.name()
        self.labels = []
        ch = info.desc().child("channels").child("channel")
        for _ in range(info.channel_count()):
            self.labels.append(ch.child_value("label") or f"ch{len(self.labels)}")
            ch = ch.next_sibling()
        self.chunks, self.stamps = [], []
        self.running = True

    def run(self):
        while self.running:
            data, ts = self.inlet.pull_chunk(timeout=0.2)
            if ts:
                self.chunks.append(np.asarray(data, dtype=np.float32))
                self.stamps.append(np.asarray(ts))

    def save(self, path):
        self.running = False
        self.join(timeout=2)
        if not self.chunks:
            print("!! No EEG samples were received.")
            return
        X = np.concatenate(self.chunks)
        t = np.concatenate(self.stamps)
        np.savez_compressed(path, data=X, timestamps=t, fs=self.fs, labels=np.array(self.labels), stream=self.name)
        print(f"EEG saved: {path}  ({X.shape[0]} samples x {X.shape[1]} ch, {X.shape[0] / max(self.fs, 1):.0f} s)")


# ---------------------------------------------------------------- session
class Session:
    def __init__(self, args):
        self.args = args
        pygame.init()
        flags = 0 if args.windowed else pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((1000, 650) if args.windowed else (0, 0), flags)
        pygame.display.set_caption("StillHere recording")
        self.W, self.H = self.screen.get_size()
        self.big = pygame.font.SysFont("helvetica", 64, bold=True)
        self.small = pygame.font.SysFont("helvetica", 28)
        self.voice = Voice()
        self.outlet = StreamOutlet(StreamInfo("StillHereMarkers", "Markers", 1, 0, "string", f"stillhere_{args.subject}"))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(args.outdir, exist_ok=True)
        self.base = os.path.join(args.outdir, f"{args.subject}_{stamp}")
        self.csv_file = open(self.base + "_events.csv", "w", newline="")
        self.csv = csv.writer(self.csv_file)
        self.csv.writerow(["lsl_time", "wall_time", "block", "event", "detail"])
        self.block = ""
        self.paused = False

    # --- helpers
    def mark(self, event, detail=""):
        t = local_clock()
        self.outlet.push_sample([f"{self.block}|{event}|{detail}"], t)
        self.csv.writerow([f"{t:.6f}", datetime.now().isoformat(timespec="milliseconds"), self.block, event, detail])
        self.csv_file.flush()
        return t

    def show(self, title, sub="", color=(235, 235, 235)):
        self.screen.fill((15, 15, 20))
        txt = self.big.render(title, True, color)
        self.screen.blit(txt, txt.get_rect(center=(self.W // 2, self.H // 2 - 30)))
        if sub:
            s = self.small.render(sub, True, (160, 160, 170))
            self.screen.blit(s, s.get_rect(center=(self.W // 2, self.H // 2 + 50)))
        tag = self.small.render(f"{self.args.subject}  |  block: {self.block}", True, (90, 90, 100))
        self.screen.blit(tag, (20, self.H - 45))
        pygame.display.flip()

    def wait(self, seconds):
        """Sleep while staying responsive; SPACE pauses, ESC aborts."""
        end = time.perf_counter() + seconds
        while time.perf_counter() < end:
            for e in pygame.event.get():
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    raise KeyboardInterrupt
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                    self.paused = True
                    self.mark("pause")
                    self.show("PAUSED", "press SPACE to resume", (240, 200, 80))
                    while self.paused:
                        for e2 in pygame.event.get():
                            if e2.type == pygame.KEYDOWN and e2.key == pygame.K_SPACE:
                                self.paused = False
                            if e2.type == pygame.KEYDOWN and e2.key == pygame.K_ESCAPE:
                                raise KeyboardInterrupt
                        time.sleep(0.02)
                    self.mark("resume")
                    end = time.perf_counter() + seconds  # restart the interval cleanly
            time.sleep(0.005)

    def speak(self, phrase, show_title=None, sub=""):
        self.show(show_title or phrase, sub)
        return self.voice.say(phrase)

    def intro(self, text, seconds=6):
        self.mark("instructions")
        dur = self.speak(text, "Get ready", text)
        self.wait(max(seconds, dur + 1.5))

    # --- blocks
    def b_sync(self):
        self.intro("Sync. Clench your jaw hard on each beep.", 5)
        for i in range(3):
            self.show("CLENCH", f"{i + 1} / 3", (240, 120, 120))
            self.voice.beep(1000)
            self.mark("jaw_clench_cue", str(i + 1))
            self.wait(1.5)
        self.show("relax")
        self.wait(2)

    def b_baseline(self):
        self.intro("Baseline. Close your eyes and relax. Stay still.", 6)
        self.mark("rest_eyes_closed_start")
        self.show("Eyes closed - relax", "60 s")
        self.wait(60)
        self.voice.beep(660)
        self.say_and_mark("Open your eyes. Look at the cross and relax.", "rest_eyes_open_start", "+")
        self.wait(30)
        self.mark("rest_end")

    def say_and_mark(self, phrase, event, title=None, detail=""):
        dur = self.speak(phrase, title)
        self.mark(event, detail)
        return dur

    def command_pair(self, hand, control=False):
        move = f"Keep opening and closing your {hand} hand."
        self.say_and_mark(move, "move_start", f"MOVE {hand.upper()}" if not control else f"(ignore) {hand}", hand)
        self.wait(self.args.block_s)
        self.say_and_mark("Stop. Relax.", "stop_start", "stop", hand)
        self.wait(self.args.block_s + random.uniform(0, 1.0))

    def b_commands(self):
        self.intro("Command blocks. Eyes closed. When told, keep squeezing and releasing that hand "
                   "against the strap. When told to stop, relax completely.", 10)
        order = ["right"] * self.args.pairs + ["left"] * self.args.pairs
        random.shuffle(order)
        for i, hand in enumerate(order):
            self.mark("pair", f"{i + 1}/{len(order)}")
            self.command_pair(hand)

    def b_control(self):
        self.intro("Control blocks. IGNORE the commands. Keep your hands still and count backward "
                   "by sevens from one thousand in your head.", 10)
        order = ["right", "left"] * (self.args.control_pairs // 2) + ["right"] * (self.args.control_pairs % 2)
        random.shuffle(order)
        for hand in order:
            self.command_pair(hand, control=True)

    def b_blinkyn(self):
        n = self.args.name
        qs = [(f"Is your name {n}?", "yes"), ("Is snow black?", "no"), ("Is water wet?", "yes"),
              ("Do fish ride bicycles?", "no"), ("Is it daytime?", "yes"), ("Is one bigger than ten?", "no")]
        random.shuffle(qs)
        self.voice.prepare([q for q, _ in qs])
        self.intro("Blink answers. Eyes open. After each question, blink twice for YES. Keep your eyes still for NO.", 8)
        for q, ans in qs:
            dur = self.say_and_mark(q, "question", q, ans)
            self.wait(dur + 0.3)
            self.say_and_mark("Answer now.", "blink_answer_start", "BLINK ANSWER  (2 blinks = yes / still = no)", ans)
            self.wait(5)
            self.say_and_mark("Stop.", "blink_answer_end", "stop", ans)
            self.wait(3 + random.uniform(0, 1))

    def b_call(self):
        self.intro("Nurse call practice. Rest. When you hear call now, squeeze and HOLD until you hear release.", 8)
        for i in range(self.args.calls):
            self.show("rest")
            self.wait(random.uniform(10, 20))
            self.say_and_mark("Call now.", "call_start", "CALL - hold the squeeze", str(i + 1))
            self.wait(6)
            self.say_and_mark("Release.", "call_end", "release", str(i + 1))
        self.wait(3)

    def b_yesno(self):
        n = self.args.name
        qs = [(f"Is your name {n}?", "yes"), ("Is the sky green?", "no"), ("Are we in Raleigh?", "yes"),
              ("Is two plus two equal to five?", "no"), ("Are you at a hackathon?", "yes"),
              ("Are you underwater right now?", "no"), ("Do people have two hands?", "yes"),
              ("Is ice hot?", "no")]
        random.shuffle(qs)
        self.voice.prepare([q for q, _ in qs])
        self.intro("Yes or no. After each question, squeeze for YES or stay relaxed for NO, until you hear stop.", 8)
        for q, ans in qs:
            dur = self.say_and_mark(q, "question", q, ans)
            self.wait(dur + 0.3)
            self.say_and_mark("Answer now.", "answer_start", "ANSWER  (squeeze = yes / rest = no)", ans)
            self.wait(self.args.block_s)
            self.say_and_mark("Stop.", "answer_end", "stop", ans)
            self.wait(5 + random.uniform(0, 1.5))

    def b_artifacts(self):
        self.intro("Artifact trials. Do each action when shown, then relax.", 6)
        acts = [("jaw_clench", "Clench your jaw"), ("neck_tension", "Tense your neck and shoulders"),
                ("blinks", "Blink hard three times")] * self.args.artifacts
        random.shuffle(acts)
        for key, phrase in acts:
            self.say_and_mark(phrase, "artifact_start", phrase.upper(), key)
            self.wait(3)
            self.mark("artifact_end", key)
            self.show("relax")
            self.wait(3 + random.uniform(0, 1))

    # --- run
    def run(self, blocks):
        phrases = ["Sync. Clench your jaw hard on each beep.",
                   "Baseline. Close your eyes and relax. Stay still.",
                   "Open your eyes. Look at the cross and relax.",
                   "Keep opening and closing your right hand.", "Keep opening and closing your left hand.",
                   "Stop. Relax.", "Call now.", "Release.", "Answer now.", "Stop.",
                   "Clench your jaw", "Tense your neck and shoulders", "Blink hard three times",
                   "Command blocks. Eyes closed. When told, keep squeezing and releasing that hand "
                   "against the strap. When told to stop, relax completely.",
                   "Control blocks. IGNORE the commands. Keep your hands still and count backward "
                   "by sevens from one thousand in your head.",
                   "Nurse call practice. Rest. When you hear call now, squeeze and HOLD until you hear release.",
                   "Yes or no. After each question, squeeze for YES or stay relaxed for NO, until you hear stop.",
                   "Artifact trials. Do each action when shown, then relax.", "Recording complete. Thank you.",
                   "Blink answers. Eyes open. After each question, blink twice for YES. Keep your eyes still for NO."]
        self.show("Preparing audio...")
        self.voice.prepare(phrases)
        self.show("StillHere recording ready", "press SPACE to start   |   ESC to abort")
        waiting = True
        while waiting:
            for e in pygame.event.get():
                if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                    waiting = False
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    raise KeyboardInterrupt
            time.sleep(0.02)
        self.block = "session"
        self.mark("session_start", ",".join(blocks))
        for b in blocks:
            self.block = b
            self.mark("block_start")
            getattr(self, f"b_{b}")()
            self.mark("block_end")
        self.block = "session"
        self.speak("Recording complete. Thank you.", "Done")
        self.mark("session_end")
        self.wait(2)

    def close(self):
        self.csv_file.close()
        pygame.quit()


def pick_eeg_stream(name_hint, timeout=5):
    streams = [s for s in resolve_streams(wait_time=timeout) if s.type().upper() != "MARKERS"]
    if name_hint:
        streams = [s for s in streams if name_hint.lower() in s.name().lower()]
    eeg = [s for s in streams if s.type().upper() == "EEG"] or streams
    return eeg[0] if eeg else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", default="S1", help="subject ID, e.g. S1 (main), S2, S3")
    ap.add_argument("--name", default="Tyler", help="subject's first name, for the yes/no questions")
    ap.add_argument("--blocks", default=",".join(ALL_BLOCKS), help="comma list of blocks to run, in order")
    ap.add_argument("--pairs", type=int, default=8, help="move/stop pairs PER HAND in the command block")
    ap.add_argument("--control-pairs", type=int, default=4)
    ap.add_argument("--calls", type=int, default=5)
    ap.add_argument("--artifacts", type=int, default=6, help="repetitions of each artifact type")
    ap.add_argument("--block-s", type=float, default=10.0, help="seconds per move/stop/answer window")
    ap.add_argument("--record-eeg", action="store_true", help="also record the ANT EEG LSL stream on this laptop")
    ap.add_argument("--eeg-name", default="", help="substring of the EEG stream name if several exist")
    ap.add_argument("--list-streams", action="store_true", help="list visible LSL streams and exit")
    ap.add_argument("--windowed", action="store_true", help="run in a window instead of full screen")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    args = ap.parse_args()

    if args.list_streams:
        found = resolve_streams(wait_time=5)
        print("No LSL streams found." if not found else "\n".join(
            f"- {s.name()}  type={s.type()}  ch={s.channel_count()}  fs={s.nominal_srate()}  host={s.hostname()}" for s in found))
        return

    blocks = [b.strip() for b in args.blocks.split(",") if b.strip()]
    bad = [b for b in blocks if b not in set(ALL_BLOCKS)]
    if bad:
        sys.exit(f"Unknown block(s): {bad}. Valid: {sorted(set(ALL_BLOCKS))}")

    rec = None
    if args.record_eeg:
        info = pick_eeg_stream(args.eeg_name)
        if info is None:
            sys.exit("No EEG LSL stream found. Check you are on the ANT network, or run without --record-eeg.")
        rec = EEGRecorder(info)
        print(f"Recording EEG stream '{rec.name}': {len(rec.labels)} ch @ {rec.fs} Hz -> {rec.labels}")
        rec.start()

    sess = Session(args)
    try:
        sess.run(blocks)
    except KeyboardInterrupt:
        sess.mark("aborted")
        print("Aborted - saving what was recorded.")
    finally:
        sess.close()
        if rec:
            rec.save(sess.base + "_eeg.npz")
        print(f"Events saved: {sess.base}_events.csv")


if __name__ == "__main__":
    main()
