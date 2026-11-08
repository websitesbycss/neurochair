"""Brain-controlled wheelchair - recording session (NC State BCI Hackathon, ANT track, Team 2).

One program, two tasks, interleaved so a cut-short session still has both:
  * SSVEP destination choice: 4 flickering corner targets (Bathroom / Kitchen / Bed / Door)
    plus "look at center" trials (= no selection).
  * Brain brake: a top-down hallway; objects appear and either turn INTO the chair's path
    (danger -> press SPACE as fast as possible) or keep going alongside (harmless -> ignore).

Every event goes to an LSL marker stream ("WheelchairMarkers") and to CSV. With --record-eeg
the ANT EEG LSL stream is recorded on this laptop on the same clock as the markers.

Default block order (~18 min):
  sync, rest, brake, ssvep, brake, ssvep, artifacts, sync

Run (from ~/Documents/StillHere):
  .venv/bin/python wheelchair_record.py --list-streams
  .venv/bin/python wheelchair_record.py --subject S1 --record-eeg
  .venv/bin/python wheelchair_record.py --check-display          # 10 s flicker/refresh check, no recording

Keys:  SPACE = brake (brake blocks only)   P = pause/resume   ESC = abort (data so far is saved)
"""
import argparse
import csv
import json
import math
import os
import random
import sys
import time
from datetime import datetime

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np
import pygame
from pylsl import StreamInfo, StreamOutlet, local_clock, resolve_streams

from stillhere_record import EEGRecorder, Voice, pick_eeg_stream

DEFAULT_BLOCKS = ["sync", "rest", "brake", "ssvep", "brake", "ssvep", "artifacts", "sync"]
VALID_BLOCKS = {"sync", "rest", "brake", "ssvep", "artifacts"}
TARGETS = ["Bathroom", "Kitchen", "Bed", "Door"]          # corner order: TL, TR, BL, BR
DEFAULT_FREQS = [12.0, 8.57, 7.5, 6.67]                    # Hz, frame-locked; reassigned after analysis
LOGICAL = (1280, 800)                                      # drawing size; scaled to the full screen

BG = (18, 18, 24)
FG = (235, 235, 235)
DIM = (120, 120, 130)
YELLOW = (250, 210, 70)
GREEN = (90, 220, 120)
RED = (235, 80, 80)
ORANGE = (245, 160, 60)


class Session:
    def __init__(self, args):
        self.args = args
        self.ts = args.time_scale
        pygame.init()
        self.screen, self.vsync = self._open_display()
        pygame.display.set_caption("Wheelchair BCI recording")
        pygame.mouse.set_visible(False)
        self.W, self.H = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.SysFont("helvetica", 54, bold=True)
        self.f_med = pygame.font.SysFont("helvetica", 32, bold=True)
        self.f_small = pygame.font.SysFont("helvetica", 22)
        self.refresh, self.jitter_ms = self._measure_refresh()
        self.voice = Voice()
        self.voice.prepare(PHRASES)

        # flicker periods in whole frames
        self.freqs_req = args.freqs
        self.periods = [max(2, round(self.refresh / f)) for f in self.freqs_req]
        self.freqs = [self.refresh / n for n in self.periods]
        if len(set(self.periods)) < len(self.periods):
            sys.exit(f"Flicker frequencies collide at {self.refresh:.1f} Hz refresh: {self.freqs_req}")

        self.outlet = StreamOutlet(StreamInfo("WheelchairMarkers", "Markers", 1, 0, "string", f"wc_{args.subject}"))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(args.outdir, exist_ok=True)
        self.base = os.path.join(args.outdir, f"{args.subject}_{stamp}_wc")
        self.csv_file = open(self.base + "_events.csv", "w", newline="")
        self.csv = csv.writer(self.csv_file)
        self.csv.writerow(["lsl_time", "wall_time", "block", "event", "detail"])
        self.block = "session"
        self.run_idx = {"brake": 0, "ssvep": 0}
        self.pending = []
        self.score = 0
        self._save_config()

    # ------------------------------------------------------------ display
    def _open_display(self):
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.args.fullscreen else 0)
        try:
            return pygame.display.set_mode(LOGICAL, flags, vsync=1), True
        except pygame.error:
            print("!! vsync unavailable - falling back to timed frames (flicker less precise)")
            return pygame.display.set_mode(LOGICAL, flags), False

    def _measure_refresh(self):
        stamps = []
        for i in range(100):
            for _ in pygame.event.get():
                pass
            self.screen.fill(BG)
            pygame.display.flip()
            stamps.append(time.perf_counter())
        d = np.diff(stamps[20:])
        period = float(np.median(d))
        if period < 0.004:  # flips are not blocking -> no real vsync
            self.vsync = False
            hz = float(self.args.refresh)
            print(f"!! Display flips are not vsynced; pacing frames at {hz:.0f} Hz with a timer.")
            return hz, float("nan")
        hz = 1.0 / period
        # snap to common refresh rates
        for nominal in (60.0, 120.0, 59.94, 50.0, 144.0, 100.0):
            if abs(hz - nominal) < 1.5:
                hz = nominal
                break
        jit = float(np.std(d) * 1000)
        print(f"Display refresh ~{hz:.2f} Hz (frame jitter {jit:.2f} ms)")
        if jit > 2.0:
            print("!! Frame timing is jittery. Set System Settings > Displays > Refresh rate = 60 Hz, "
                  "plug in the charger, close other apps.")
        return hz, jit

    def flip(self):
        pygame.display.flip()
        if not self.vsync:
            self.clock.tick_busy_loop(self.refresh)
        t = local_clock()
        for event, detail in self.pending:  # markers for what just appeared on screen
            self._push(event, detail, t)
        self.pending = []
        return t

    # ------------------------------------------------------------ markers / logging
    def _push(self, event, detail, t):
        self.outlet.push_sample([f"{self.block}|{event}|{detail}"], t)
        self.csv.writerow([f"{t:.6f}", datetime.now().isoformat(timespec="milliseconds"), self.block, event, detail])
        self.csv_file.flush()

    def mark(self, event, detail=""):
        """Marker stamped now (use for key presses and non-visual events)."""
        t = local_clock()
        self._push(event, detail, t)
        return t

    def mark_on_flip(self, event, detail=""):
        """Marker stamped at the next screen flip (use for visual onsets)."""
        self.pending.append((event, detail))

    def _save_config(self):
        cfg = {
            "subject": self.args.subject, "refresh_hz": self.refresh, "vsync": self.vsync,
            "frame_jitter_ms": None if math.isnan(self.jitter_ms) else self.jitter_ms,
            "targets": TARGETS, "freqs_requested": self.freqs_req, "freqs_actual": self.freqs,
            "periods_frames": self.periods, "corner_order": ["TL", "TR", "BL", "BR"],
            "ssvep": {"cue_s": 1.0, "flicker_s": self.args.flicker_s, "rest_s": 2.0,
                      "per_target_per_run": self.args.ssvep_per_target},
            "brake": {"per_type_per_run": self.args.brake_per_type, "pre_split_s": PRE_SPLIT,
                      "split_to_impact_s": SPLIT_TO_IMPACT, "turn_s": TURN_S},
            "blocks": self.args.blocks, "time_scale": self.ts, "autopilot": self.args.autopilot,
        }
        with open(self.base + "_config.json", "w") as f:
            json.dump(cfg, f, indent=2)
        self.mark("config", json.dumps({"freqs": dict(zip(TARGETS, [round(x, 3) for x in self.freqs])),
                                        "refresh": self.refresh}))

    # ------------------------------------------------------------ loop helpers
    def text(self, s, font, color, center):
        img = font.render(s, True, color)
        self.screen.blit(img, img.get_rect(center=center))

    def footer(self):
        self.text(f"{self.args.subject} | {self.block}   P pause  ESC abort", self.f_small, (70, 70, 80),
                  (self.W // 2, self.H - 18))

    def pause(self):
        t0 = time.perf_counter()
        self.mark("pause")
        while True:
            self.screen.fill(BG)
            self.text("PAUSED", self.f_big, YELLOW, (self.W // 2, self.H // 2 - 20))
            self.text("press P to resume", self.f_small, DIM, (self.W // 2, self.H // 2 + 40))
            self.flip()
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    raise KeyboardInterrupt
                if e.type == pygame.KEYDOWN and e.key == pygame.K_p:
                    self.mark("resume")
                    return time.perf_counter() - t0

    def loop(self, seconds, draw, on_key=None, scaled=True):
        """Frame-locked loop. draw(t, frame) draws one frame; return True from draw to end early.
        on_key(key, lsl_time, t) handles key presses. t is seconds since the loop started."""
        dur = seconds * (self.ts if scaled else 1.0)
        start = time.perf_counter()
        frame = 0
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    raise KeyboardInterrupt
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        raise KeyboardInterrupt
                    if e.key == pygame.K_p:
                        start += self.pause()
                    elif on_key:
                        on_key(e.key, local_clock(), (time.perf_counter() - start) / self.ts)
            t = time.perf_counter() - start
            if t >= dur:
                return frame
            if draw(t / (self.ts if scaled else 1.0), frame):
                return frame
            self.flip()
            frame += 1

    def message(self, title, sub="", seconds=3.0, color=FG, say=None):
        if say:
            self.voice.say(say)

        def draw(t, f):
            self.screen.fill(BG)
            self.text(title, self.f_big, color, (self.W // 2, self.H // 2 - 30))
            if sub:
                self.text(sub, self.f_small, DIM, (self.W // 2, self.H // 2 + 35))
            self.footer()
        self.loop(seconds, draw)

    def intro(self, title, lines, say, seconds=7.0):
        self.mark("instructions")
        dur = self.voice.say(say)

        def draw(t, f):
            self.screen.fill(BG)
            self.text(title, self.f_big, YELLOW, (self.W // 2, self.H // 2 - 110))
            for i, ln in enumerate(lines):
                self.text(ln, self.f_small, FG, (self.W // 2, self.H // 2 - 30 + 36 * i))
            self.footer()
        self.loop(max(seconds, dur + 1.0), draw)

    # ============================================================ blocks
    def b_sync(self):
        self.intro("Sync", ["Clench your jaw hard on each beep."], "Sync. Clench your jaw hard on each beep.", 5)
        for i in range(3):
            self.voice.beep(1000)
            self.mark("jaw_clench_cue", str(i + 1))
            self.message("CLENCH", f"{i + 1} / 3", 1.5, RED)
        self.message("relax", "", 1.5)

    def b_rest(self):
        self.intro("Rest", ["Eyes open on the dot for 1 minute, then eyes closed for 1 minute.",
                            "Stay relaxed and still."],
                   "Rest. Keep your eyes on the dot and relax.", 6)

        def dot(t, f):
            self.screen.fill(BG)
            pygame.draw.circle(self.screen, FG, (self.W // 2, self.H // 2), 6)
            self.footer()
        self.mark_on_flip("eyes_open_start")
        self.loop(60, dot)
        self.mark("eyes_open_end")
        self.voice.say("Close your eyes until you hear the beep.")
        self.message("Close your eyes", "until the beep", 3)
        self.mark("eyes_closed_start")
        self.message("Eyes closed", "", 60, DIM)
        self.mark("eyes_closed_end")
        self.voice.beep(660, 0.3)
        self.message("Open your eyes", "", 2)

    def b_artifacts(self):
        self.intro("Artifacts", ["Do each action when it appears, then relax."],
                   "Artifact check. Do each action when it appears, then relax.", 5)
        kinds = [("blink", "BLINK HARD x3"), ("jaw_clench", "CLENCH JAW"),
                 ("look_left", "LOOK LEFT then back"), ("look_right", "LOOK RIGHT then back")]
        trials = [k for k in kinds for _ in range(self.args.artifacts)]
        random.shuffle(trials)
        for kind, label in trials:
            self.voice.beep(880)
            self.mark_on_flip("artifact", kind)
            arrow = -1 if kind == "look_left" else (1 if kind == "look_right" else 0)

            def draw(t, f, label=label, arrow=arrow):
                self.screen.fill(BG)
                self.text(label, self.f_big, ORANGE, (self.W // 2, self.H // 2))
                if arrow:
                    x = self.W // 2 + arrow * (self.W // 2 - 40)
                    pygame.draw.circle(self.screen, ORANGE, (x, self.H // 2), 14)
                self.footer()
            self.loop(2.0, draw)
            self.message("relax", "", 1.5, DIM)

    # ------------------------------------------------------------ SSVEP
    def _corner_rects(self):
        s, m = 170, 40
        return [pygame.Rect(m, m, s, s), pygame.Rect(self.W - m - s, m, s, s),
                pygame.Rect(m, self.H - m - s - 30, s, s), pygame.Rect(self.W - m - s, self.H - m - s - 30, s, s)]

    def _draw_ssvep(self, frame=None, cue=None, flicker=False):
        self.screen.fill(BG)
        rects = self._corner_rects()
        for i, (r, name) in enumerate(zip(rects, TARGETS)):
            if flicker:
                n = self.periods[i]
                on = (frame % n) < math.ceil(n / 2)
                pygame.draw.rect(self.screen, (255, 255, 255) if on else (0, 0, 0), r)
            else:
                pygame.draw.rect(self.screen, (70, 70, 80), r)
            if cue == name:
                pygame.draw.rect(self.screen, YELLOW, r.inflate(16, 16), 6)
            self.text(name, self.f_med, YELLOW if cue == name else DIM, (r.centerx, r.bottom + 22))
        cc = YELLOW if cue == "center" else (110, 110, 120)
        cx, cy = self.W // 2, self.H // 2
        pygame.draw.line(self.screen, cc, (cx - 18, cy), (cx + 18, cy), 4)
        pygame.draw.line(self.screen, cc, (cx, cy - 18), (cx, cy + 18), 4)
        self.footer()

    def b_ssvep(self):
        self.run_idx["ssvep"] += 1
        run = self.run_idx["ssvep"]
        self.intro(f"Look to choose  (run {run})",
                   ["A corner (or the center cross) will light up yellow.",
                    "When the squares flash, stare at the yellow one until they stop.",
                    "Keep your head still. Blink only between trials."],
                   "Destination choice. Stare at the yellow target while the squares flash.", 8)
        trials = TARGETS * self.args.ssvep_per_target + ["center"] * self.args.ssvep_per_target
        random.shuffle(trials)
        self.mark("run_start", str(run))
        for k, tgt in enumerate(trials):
            self.mark_on_flip("cue", tgt)
            self.loop(1.0, lambda t, f, tgt=tgt: self._draw_ssvep(cue=tgt))
            self.mark_on_flip("flicker_on", tgt)
            nf = self.loop(self.args.flicker_s, lambda t, f, tgt=tgt: self._draw_ssvep(frame=f, cue=tgt, flicker=True))
            expected = round(self.args.flicker_s * self.ts * self.refresh)
            if abs(nf - expected) > 2:
                print(f"!! flicker trial {k + 1}: drew {nf} frames, expected {expected} (dropped frames)")
            self.mark_on_flip("flicker_off", f"{tgt}|frames={nf}|expected={expected}")
            self.loop(2.0, lambda t, f: self._draw_ssvep())
        self.mark("run_end", str(run))

    # ------------------------------------------------------------ brake
    def b_brake(self):
        self.run_idx["brake"] += 1
        run = self.run_idx["brake"]
        self.intro(f"Brain brake  (run {run})",
                   ["Keep your eyes on the dot in the middle of the hallway.",
                    "If something turns INTO your path: press SPACE as fast as you can.",
                    "If it stays at the side: do nothing."],
                   "Brain brake. Press space as fast as you can when something comes into your path. "
                   "Ignore things that stay at the side.", 9)
        n = self.args.brake_per_type
        kinds = ["person", "ball", "cart"]
        trials = [("danger", s) for s in (-1, 1) for _ in range(n // 2)] + \
                 [("harmless", s) for s in (-1, 1) for _ in range(n // 2)]
        if n % 2:
            trials += [("danger", random.choice((-1, 1))), ("harmless", random.choice((-1, 1)))]
        random.shuffle(trials)
        self.mark("run_start", str(run))
        self.scroll = 0.0
        self._hallway_idle(2.0)
        for k, (cond, side) in enumerate(trials):
            self._brake_trial(cond, side, random.choice(kinds), k + 1, len(trials))
            self._hallway_idle(random.uniform(1.0, 3.5))
        self.mark("run_end", f"{run}|score={self.score}")
        self.message(f"Run {run} done", f"score {self.score}", 3, GREEN)

    # hallway geometry
    def _geom(self):
        cx = self.W // 2
        half = int(self.W * 0.24)
        return cx, cx - half, cx + half, int(self.H * 0.80)

    def _draw_hallway(self, extra=None, msg=None, msg_color=FG, shake=0, flash=None):
        cx, left, right, chair_y = self._geom()
        ox = random.randint(-shake, shake) if shake else 0
        self.screen.fill(flash or BG)
        pygame.draw.rect(self.screen, (40, 40, 52), (left + ox, 0, right - left, self.H))
        pygame.draw.line(self.screen, (150, 150, 165), (left + ox, 0), (left + ox, self.H), 5)
        pygame.draw.line(self.screen, (150, 150, 165), (right + ox, 0), (right + ox, self.H), 5)
        gap = 80
        for y in range(-gap, self.H + gap, gap):  # floor marks scroll down = chair moves forward
            yy = int((y + self.scroll) % (self.H + gap)) - gap
            pygame.draw.line(self.screen, (70, 70, 85), (left + 12 + ox, yy), (left + 40 + ox, yy), 3)
            pygame.draw.line(self.screen, (70, 70, 85), (right - 40 + ox, yy), (right - 12 + ox, yy), 3)
        if extra:
            extra(ox)
        # chair
        pygame.draw.rect(self.screen, (90, 150, 230), (cx - 34 + ox, chair_y - 30, 68, 60), border_radius=12)
        pygame.draw.circle(self.screen, (30, 30, 30), (cx - 40 + ox, chair_y + 10), 14)
        pygame.draw.circle(self.screen, (30, 30, 30), (cx + 40 + ox, chair_y + 10), 14)
        pygame.draw.circle(self.screen, FG, (cx + ox, int(self.H * 0.45)), 6)  # fixation dot
        self.text(f"score {self.score}", self.f_small, DIM, (self.W - 90, 24))
        if msg:
            self.text(msg, self.f_med, msg_color, (cx, int(self.H * 0.30)))
        self.footer()

    def _hallway_idle(self, seconds):
        speed = 260.0

        def draw(t, f):
            self.scroll += speed / max(self.refresh, 1)
            self._draw_hallway()
        self.loop(seconds, draw)

    def _brake_trial(self, cond, side, kind, idx, total):
        cx, left, right, chair_y = self._geom()
        y0 = int(self.H * 0.10)
        x0 = cx + side * int(self.W * 0.12)
        x_wall = cx + side * int(self.W * 0.21)  # harmless objects veer away, toward the wall
        speed = 260.0
        state = {"pressed_t": None, "outcome": None, "rt": None, "end_at": None, "split_sent": False,
                 "frozen_at": None}
        T = PRE_SPLIT + SPLIT_TO_IMPACT

        def pos(t):
            tt = min(t, T)
            y = y0 + (chair_y - 40 - y0) * tt / T
            x = x0
            if tt > PRE_SPLIT:
                u = min(1.0, (tt - PRE_SPLIT) / TURN_S)
                sm = u * u * (3 - 2 * u)  # smoothstep
                x = x0 + ((cx if cond == "danger" else x_wall) - x0) * sm  # into the path vs away from it
            return int(x), int(y)

        def draw_obj(t, ox):
            x, y = pos(t)
            x += ox
            col = (225, 185, 120)
            if kind == "person":
                pygame.draw.circle(self.screen, col, (x, y - 22), 13)
                pygame.draw.rect(self.screen, col, (x - 15, y - 8, 30, 36), border_radius=8)
            elif kind == "ball":
                pygame.draw.circle(self.screen, col, (x, y), 22)
            else:
                pygame.draw.rect(self.screen, col, (x - 26, y - 20, 52, 40), border_radius=6)
                pygame.draw.circle(self.screen, (30, 30, 30), (x - 16, y + 22), 6)
                pygame.draw.circle(self.screen, (30, 30, 30), (x + 16, y + 22), 6)

        def finish(outcome, t):
            state["outcome"], state["end_at"] = outcome, t + 0.9
            self.mark("outcome", f"{cond}|{outcome}|{kind}|{side}")

        def on_key(key, lsl_t, t):
            if key != pygame.K_SPACE or state["outcome"]:
                return
            self.mark("brake_press", f"{cond}|{kind}|{side}")
            if t < PRE_SPLIT:
                self.score -= 1
                finish("early", t)
            elif cond == "danger":
                state["rt"] = t - PRE_SPLIT
                self.score += 2
                state["frozen_at"] = t
                self.mark("rt", f"{state['rt'] * 1000:.0f}")
                finish("stopped", t)
            else:
                self.score -= 1
                state["frozen_at"] = t
                finish("false_stop", t)

        def draw(t, f):
            if self.args.autopilot and not state["outcome"]:
                p = 0.42 + random.uniform(-0.05, 0.1)
                if (cond == "danger" and t >= PRE_SPLIT + p) or (cond == "harmless" and t >= PRE_SPLIT + 0.5
                                                                  and random.random() < 0.002):
                    on_key(pygame.K_SPACE, local_clock(), t)
            if not state["split_sent"] and t >= PRE_SPLIT:
                state["split_sent"] = True
                self.mark_on_flip("split", f"{cond}|{kind}|{side}")
            if not state["outcome"] and t >= T:
                if cond == "danger":
                    self.score -= 2
                    self.voice.beep(200, 0.35)
                    finish("crash", t)
                else:
                    finish("passed", t)
            if state["end_at"] and t >= state["end_at"]:
                return True
            frozen = state["frozen_at"] is not None or state["outcome"] == "crash"
            if not frozen:
                self.scroll += speed / max(self.refresh, 1)
            tt = state["frozen_at"] if state["frozen_at"] is not None else t
            msg, colr, shake, flash = None, FG, 0, None
            o = state["outcome"]
            if o == "stopped":
                msg, colr = f"STOPPED  {state['rt'] * 1000:.0f} ms", GREEN
            elif o == "false_stop":
                msg, colr = "unnecessary stop", ORANGE
            elif o == "early":
                msg, colr = "too early", ORANGE
            elif o == "crash":
                msg, colr, shake, flash = "CRASH", RED, 10, (70, 20, 20)
            self._draw_hallway(lambda ox: draw_obj(tt, ox) if o != "passed" else None, msg, colr, shake, flash)

        self.mark_on_flip("appear", f"{cond}|{kind}|{side}|{idx}/{total}")
        self.loop(T + 2.0, draw, on_key)

    # ------------------------------------------------------------ main sequence
    def run(self, blocks):
        self.block = "session"
        self.mark("session_start", ",".join(blocks))
        self.message("Wheelchair BCI", "starting...", 2)
        for b in blocks:
            self.block = b
            self.mark("block_start")
            getattr(self, f"b_{b}")()
            self.mark("block_end")
        self.block = "session"
        self.voice.say("Recording complete. Thank you.")
        self.message("Done", f"final score {self.score}", 3, GREEN)
        self.mark("session_end")

    def check_display(self):
        """10 s of flicker so you can eyeball it and read the refresh estimate."""
        msg = f"refresh {self.refresh:.1f} Hz  vsync={self.vsync}  freqs " + \
              ", ".join(f"{n} {f:.2f}" for n, f in zip(TARGETS, self.freqs))
        print(msg)

        def draw(t, f):
            self._draw_ssvep(frame=f, flicker=True)
            self.text(msg, self.f_small, FG, (self.W // 2, self.H // 2 + 60))
        self.loop(10, draw, scaled=False)

    def close(self):
        self.csv_file.close()
        pygame.quit()


PRE_SPLIT = 0.7          # s the object travels before it turns in (danger) or not (harmless)
SPLIT_TO_IMPACT = 1.2    # s from the turn to reaching the chair -> response window
TURN_S = 0.35            # s for the veer (danger: into the path; harmless: toward the wall)
PHRASES = [
    "Sync. Clench your jaw hard on each beep.",
    "Rest. Keep your eyes on the dot and relax.",
    "Close your eyes until you hear the beep.",
    "Artifact check. Do each action when it appears, then relax.",
    "Destination choice. Stare at the yellow target while the squares flash.",
    "Brain brake. Press space as fast as you can when something comes into your path. "
    "Ignore things that stay at the side.",
    "Recording complete. Thank you.",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", default="S1")
    ap.add_argument("--blocks", default=",".join(DEFAULT_BLOCKS), help="comma list, in order")
    ap.add_argument("--ssvep-per-target", type=int, default=5, help="trials per target (and center) per SSVEP run")
    ap.add_argument("--flicker-s", type=float, default=4.0)
    ap.add_argument("--freqs", type=lambda s: [float(x) for x in s.split(",")], default=DEFAULT_FREQS,
                    help="4 flicker Hz for Bathroom,Kitchen,Bed,Door")
    ap.add_argument("--brake-per-type", type=int, default=20, help="danger AND harmless trials per brake run")
    ap.add_argument("--artifacts", type=int, default=5)
    ap.add_argument("--refresh", type=float, default=60.0, help="assumed refresh if vsync is unavailable")
    ap.add_argument("--record-eeg", action="store_true")
    ap.add_argument("--eeg-name", default="")
    ap.add_argument("--list-streams", action="store_true")
    ap.add_argument("--check-display", action="store_true", help="show the flicker for 10 s and exit")
    ap.add_argument("--fullscreen", action="store_true", help="fullscreen (windowed is default; it had steadier timing)")
    ap.add_argument("--windowed", action="store_true", help=argparse.SUPPRESS)  # kept for old commands
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    ap.add_argument("--time-scale", type=float, default=1.0, help=argparse.SUPPRESS)   # testing only
    ap.add_argument("--autopilot", action="store_true", help=argparse.SUPPRESS)        # testing only
    args = ap.parse_args()
    if len(args.freqs) != 4:
        sys.exit("--freqs needs exactly 4 values")

    if args.list_streams:
        found = resolve_streams(wait_time=5)
        print("No LSL streams found." if not found else "\n".join(
            f"- {s.name()}  type={s.type()}  ch={s.channel_count()}  fs={s.nominal_srate()}  host={s.hostname()}"
            for s in found))
        return

    blocks = [b.strip() for b in args.blocks.split(",") if b.strip()]
    bad = [b for b in blocks if b not in VALID_BLOCKS]
    if bad:
        sys.exit(f"Unknown block(s): {bad}. Valid: {sorted(VALID_BLOCKS)}")
    args.blocks = blocks

    if args.check_display:
        args.outdir = os.path.join(args.outdir, "display_checks")
        s = Session(args)
        try:
            s.check_display()
        except KeyboardInterrupt:
            pass
        s.close()
        return

    rec = None
    if args.record_eeg:
        info = pick_eeg_stream(args.eeg_name)
        if info is None:
            sys.exit("No EEG LSL stream found. Are you on the ANT network? (or run without --record-eeg)")
        rec = EEGRecorder(info)
        print(f"Recording EEG '{rec.name}': {len(rec.labels)} ch @ {rec.fs} Hz -> {rec.labels}")
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
        print(f"Events: {sess.base}_events.csv\nConfig: {sess.base}_config.json")


if __name__ == "__main__":
    main()
