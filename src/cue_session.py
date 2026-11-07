"""Run the recording protocol: speaks/prints/beeps each cue and sends LSL markers (stream type 'Markers').
src/record_lsl.py saves those markers with the EEG, so labels are timestamped on the same clock.

Markers: '<label>_start' at the cue, '<label>_end' when the hold window closes, plus block_<name>_start/_end.

Usage:
  python src/cue_session.py --auto --speak       # full universal protocol, hands-free (about 18 min)
  python src/cue_session.py --blocks sync baseline blink clench hands imagery
  python src/cue_session.py --speed 20 --mute    # dry run at 20x speed (testing only)
Blocks: see BLOCKS below.
"""
import argparse
import csv
import random
import subprocess
import sys
import time
from pathlib import Path

from pylsl import StreamInfo, StreamOutlet

try:
    import winsound
except ImportError:  # non-Windows
    winsound = None


def rep(label, say, n):
    return [(label, say)] * n


PASSAGE_A = ("Read this silently, at a normal pace, eyes moving across the lines but head still. "
             "The octopus has three hearts and blue blood. Two hearts pump blood through the gills, "
             "and the third pumps it to the rest of the body. When the octopus swims, the heart that "
             "serves the body actually stops beating, which is why these animals prefer to crawl.")
PASSAGE_B = ("Keep reading silently and do NOT react to anything at the edge of your vision. "
             "Honey never spoils. Archaeologists have found pots of honey in ancient tombs that are "
             "thousands of years old and still perfectly edible, because honey is so low in water that "
             "bacteria cannot grow in it.")

# name -> dict(title, trials=[(label, say)], hold, rest, shuffle, note)
BLOCKS = {
    "sync": dict(title="SYNC: three HARD jaw clenches", trials=rep("sync_clench", "clench hard", 3), hold=1, rest=2),
    "baseline": dict(title="BASELINE: relaxed, upright, eyes on a far object, no talking, no moving",
                     trials=[("baseline_open", "Relax. Eyes open on the far object. Stay still.")], hold=60, rest=0),
    "baseline_closed": dict(title="BASELINE: eyes CLOSED, relaxed",
                            trials=[("baseline_closed", "Close your eyes and relax.")], hold=30, rest=0),
    "blink": dict(title="BLINKS (eyes on far object)",
                  trials=rep("blink_single", "blink", 10) + rep("blink_double", "double blink", 5)
                  + rep("blink_long", "slow long blink", 5), hold=1.5, rest=3),
    "drowsy": dict(title="EYES CLOSED 3 SECONDS (microsleep stand-in)",
                   trials=rep("eyes_closed_3s", "close your eyes for three seconds", 4), hold=3, rest=5),
    "clench": dict(title="JAW CLENCH", trials=rep("clench_short", "clench", 10) + rep("clench_long", "clench and hold", 5),
                   hold=2, rest=3),
    "face": dict(title="FACE: frown and smile",
                 trials=rep("frown", "frown", 5) + rep("smile", "smile", 5), hold=2, rest=3, shuffle=True),
    "eyes": dict(title="EYE DIRECTION: look, then back to center",
                 trials=rep("eyes_left", "look left", 5) + rep("eyes_right", "look right", 5), hold=2, rest=2, shuffle=True),
    "hands": dict(title="HAND SQUEEZE (random left/right)",
                  trials=rep("hand_R", "right hand squeeze", 8) + rep("hand_L", "left hand squeeze", 8),
                  hold=4, rest=6, shuffle=True),
    "bicep": dict(title="RIGHT BICEP, THREE EFFORT LEVELS: tense the bicep with the elbow bent, do not move the arm",
                  trials=rep("bicep_light", "light bicep contraction, about 25 percent", 5)
                  + rep("bicep_medium", "medium bicep contraction, about 50 percent", 5)
                  + rep("bicep_hard", "hard bicep contraction, about 80 percent", 5), hold=4, rest=6, shuffle=True),
    "imagery": dict(title="IMAGINED SQUEEZE: imagine the feeling, do NOT move",
                    trials=rep("imag_R", "imagine right squeeze", 8) + rep("imag_L", "imagine left squeeze", 8),
                    hold=4, rest=6, shuffle=True),
    "combined": dict(title="COMBINED: right squeeze with an artifact on purpose",
                     trials=rep("squeeze_clench", "right squeeze and clench your jaw", 6)
                     + rep("squeeze_blink", "right squeeze and blink twice", 6), hold=4, rest=6, shuffle=True),
    "workload": dict(title="MENTAL WORKLOAD: silent counting, eyes on far object, no lip or jaw movement",
                     trials=[("workload_easy", "Easy. Count up by ones, silently."),
                             ("workload_hard", "Hard. Count backward from five hundred by sevens, silently."),
                             ("workload_easy", "Easy. Count up by ones, silently."),
                             ("workload_hard", "Hard. Count backward from five hundred by sevens, silently.")],
                     hold=30, rest=5),
    "reading": dict(title="READING (eyes move, head still)", trials=[("reading", "Read the text on the screen silently.")],
                    hold=60, rest=3, note=PASSAGE_A),
    "reel": dict(title="DISTRACTION: operator shows a video at the edge of the subject's vision",
                 trials=[("reel_distraction", "Operator: show the video now. Subject: keep reading, do not react.")],
                 hold=30, rest=3, note=PASSAGE_B),
    # optional extras
    "arms": dict(title="ARM FLEX (random left/right)",
                 trials=rep("arm_R", "right arm flex", 8) + rep("arm_L", "left arm flex", 8), hold=4, rest=6, shuffle=True),
    "legs": dict(title="LEG PRESS (seated, random left/right)",
                 trials=rep("leg_R", "right leg press", 8) + rep("leg_L", "left leg press", 8), hold=4, rest=6, shuffle=True),
    "focus": dict(title="MIND-MUSCLE FOCUS: same squeeze, attention differs",
                  trials=rep("focus_muscle", "right squeeze, think only about the muscle", 8)
                  + rep("focus_distract", "right squeeze while counting backward by threes", 8), hold=4, rest=6, shuffle=True),
}
DEFAULT = ["sync", "baseline", "baseline_closed", "blink", "drowsy", "clench", "face", "eyes", "hands", "bicep", "imagery",
           "combined", "workload", "reading", "reel"]
ALL = DEFAULT + ["focus", "arms", "legs"]


class Speaker:
    """Persistent PowerShell speech synthesizer so cues have low latency. Silent no-op if unavailable."""
    def __init__(self, enabled):
        self.p = None
        if not enabled:
            return
        script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$s.Rate = 1; while (($l = [Console]::In.ReadLine()) -ne $null) { $s.SpeakAsync($l) | Out-Null }")
        try:
            self.p = subprocess.Popen(["powershell", "-NoProfile", "-Command", script], stdin=subprocess.PIPE,
                                      text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self.p = None

    def say(self, text):
        if self.p and self.p.stdin:
            try:
                self.p.stdin.write(text.replace("\n", " ") + "\n"); self.p.stdin.flush()
            except OSError:
                pass

    def close(self):
        if self.p:
            self.p.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", nargs="+", choices=list(BLOCKS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--mute", action="store_true", help="no beeps")
    ap.add_argument("--no-window", action="store_true", help="don't open the big-text window for reading blocks")
    ap.add_argument("--speak", action="store_true", help="speak each cue aloud (Windows)")
    ap.add_argument("--auto", action="store_true", help="no Enter between blocks; uses --gap seconds instead")
    ap.add_argument("--gap", type=float, default=8.0, help="seconds between blocks in --auto mode")
    a = ap.parse_args()
    order = a.blocks or (ALL if a.all else DEFAULT)
    beeps = (lambda f, ms: winsound.Beep(f, ms)) if (winsound and not a.mute) else (lambda f, ms: None)
    voice = Speaker(a.speak)

    outlet = StreamOutlet(StreamInfo("cues", "Markers", 1, 0, "string", "cues-001"))
    Path("data").mkdir(exist_ok=True)
    logf = open(Path("data") / time.strftime("cues_%Y%m%d_%H%M%S.csv"), "w", newline="")
    log = csv.writer(logf)
    log.writerow(["wall_time", "marker"])
    rng = random.Random(1)

    def mark(text):
        outlet.push_sample([text]); log.writerow([time.time(), text]); logf.flush()

    total = sum(len(BLOCKS[b]["trials"]) * (BLOCKS[b]["hold"] + BLOCKS[b]["rest"]) + (a.gap if a.auto else 0) + 3
                for b in order) / 60
    print(f"Blocks: {order}\nEstimated {total / a.speed:.1f} min. Start the recorder FIRST (src/record_lsl.py).", flush=True)
    voice.say("Starting the session. Sit upright and stay still.")
    time.sleep(3 / a.speed)
    try:
        for b in order:
            blk = BLOCKS[b]
            trials = list(blk["trials"])
            if blk.get("shuffle"):
                rng.shuffle(trials)
            print(f"\n=== {b.upper()}: {blk['title']} ({len(trials)} trials) ===", flush=True)
            if blk.get("note"):
                print(f"\n{blk['note']}\n", flush=True)
            if a.auto:
                voice.say("Next: " + blk["title"].split(":")[0].lower())
                time.sleep(a.gap / a.speed)
            else:
                input("Subject ready? Press Enter to start (3-second countdown)...")
            for s in (3, 2, 1):
                print(s, flush=True); beeps(500, 100); time.sleep(1 / a.speed)
            mark(f"block_{b}_start")
            for i, (label, say) in enumerate(trials, 1):
                print(f"[{i}/{len(trials)}] SAY: {say.upper()}   ({label})", flush=True)
                beeps(1000, 150); mark(f"{label}_start"); voice.say(say)
                win = None
                if blk.get("note") and not a.no_window:
                    win = subprocess.Popen([sys.executable, str(Path(__file__).with_name("show_text.py")),
                                            blk["note"], str(blk["hold"] / a.speed)])
                time.sleep(blk["hold"] / a.speed)
                if win and win.poll() is None:
                    win.terminate()
                mark(f"{label}_end"); beeps(600, 100)
                time.sleep(blk["rest"] / a.speed)
            mark(f"block_{b}_end")
        voice.say("Session complete. Thank you.")
        print("\nDone. Stop the recorder with Ctrl+C.", flush=True)
        time.sleep(3 / a.speed)
    finally:
        voice.close(); logf.close()


if __name__ == "__main__":
    main()
