"""Drive the Sphero wheelchair: two BOLTs moving together as one chair (ideas.md #18).

Control priority (highest first): BRAKE  >  keyboard (the user)  >  decoder/autopilot commands.
The arrow keys are the backup if the headset path isn't ready; the decoder can send commands over LSL.

Usage:
    python src/app/chair_drive.py               # both BOLTs, keyboard window
    python src/app/chair_drive.py --sim         # no robots: shows what each ball would do
    python src/app/chair_drive.py --lsl         # also accept decoder commands (LSL marker stream "ChairCommands")
    options: --left SB-0A38 --right SB-61AA --max-speed 50 --turn 0.4

Startup = AIM mode (do this with the chair on the table, balls in their rings):
    each ball's small blue BACK light must point to the BACK of the chair.
    Left/Right arrows rotate the selected ball 10 deg (Shift = 2 deg), Tab switches ball,
    Enter = done (sets heading 0 = chair forward). Press T while driving to come back here.
DRIVE mode keys:
    Up/Down forward/back   Left/Right turn in place   A/D slide sideways
    Space BRAKE (press again to release)   +/- speed cap   R reset forward (chair facing straight)
    T redo the back-light alignment (stops both balls)
    Esc quit (always stops both balls first)

Decoder commands (JSON strings on an LSL marker stream named "ChairCommands"):
    {"cmd": "forward"|"back"|"left"|"right"|"slide_left"|"slide_right", "seconds": 1.0}
    {"cmd": "go", "dest": "Kitchen"}      runs a route from ROUTES
    {"cmd": "stop"} / {"cmd": "brake"} / {"cmd": "resume"}
"""
import argparse
import json
import math
import time

TRACK_MM = 150.0            # distance between the two ball centres (cad/wheelchair.py MAIN)
MM_S_PER_UNIT = 2000 / 255  # BOLT top speed ~2 m/s at 255 (assumption; only used to track turning)
TICK_S = 0.1

# Fixed tabletop routes for SSVEP destinations: list of (forward v, sideways u, turn w, seconds), v/u/w in -1..1.
# Placeholders: tune on the real table.
ROUTES = {
    "Kitchen": [(1, 0, 0, 1.5)],
    "Bathroom": [(0, 0, 0.5, 0.6), (1, 0, 0, 1.2)],
    "Bed": [(0, 0, -0.5, 0.6), (1, 0, 0, 1.2)],
    "Door": [(1, 0, 0, 0.8), (0, 1, 0, 0.8)],
    "Center": [(-1, 0, 0, 0.8)],
}
MOVES = {"forward": (1, 0, 0), "back": (-1, 0, 0), "left": (0, 0, 1), "right": (0, 0, -1),
         "slide_left": (0, -1, 0), "slide_right": (0, 1, 0), "stop": (0, 0, 0)}


def ball_commands(v, u, w, yaw_deg, max_speed):
    """Chair motion -> per-ball (heading, signed speed) for (left, right).

    v forward, u sideways (+ = right), w turn rate (+ = left / counter-clockwise), each -1..1 of max_speed.
    The chair turns about the midpoint between the balls, so turning moves each ball straight forward/back.
    Headings are in the balls' shared world frame (0 = chair forward at aim time, 90 = right), folded into
    -90..90 with a negative speed for reverse, so a ball never has to swing its heading round 180 degrees.
    """
    out = []
    for x in (-1.0, 1.0):                       # left ball, right ball
        vx, vy = u, v + w * x
        mag = min(1.0, math.hypot(vx, vy))
        if mag < 1e-6:
            out.append((round(yaw_deg) % 360, 0))
            continue
        local = math.degrees(math.atan2(vx, vy))
        sign = 1
        if local > 90:
            local, sign = local - 180, -1
        elif local < -90:
            local, sign = local + 180, -1
        out.append((round(yaw_deg + local) % 360, int(round(sign * mag * max_speed))))
    return out


def apply_command(st, text):
    """Apply one decoder/autopilot JSON command to the drive state. Returns a short description, or None."""
    try:
        c = json.loads(text)
    except (TypeError, ValueError):
        return None
    cmd = c.get("cmd")
    if cmd == "brake":
        st.update(brake=True, auto=[])
    elif cmd == "resume":
        st["brake"] = False
    elif cmd == "go" and c.get("dest") in ROUTES:
        st["auto"] = [list(step) for step in ROUTES[c["dest"]]]
        st["auto_until"] = 0.0
    elif cmd in MOVES:
        st["auto"] = [[*MOVES[cmd], float(c.get("seconds", 1.0))]]
        st["auto_until"] = 0.0
    else:
        return None
    st["source"] = f"decoder: {text}"
    return st["source"]


def yaw_rate_deg(w, max_speed):
    """Estimated chair turn rate (deg/s, clockwise-positive like Sphero headings) for turn command w."""
    tangential = w * max_speed * MM_S_PER_UNIT
    return -math.degrees(tangential / (TRACK_MM / 2))


class Balls:
    """Both BOLTs (or a simulator). Sends headings for both first, then speeds, so they start together."""

    def __init__(self, left, right, sim):
        self.sim, self.apis, self.last = sim, [], [None, None]
        if sim:
            return
        from spherov2 import scanner
        from spherov2.sphero_edu import SpheroEduAPI
        toys = [scanner.find_toy(toy_name=n, timeout=15) for n in (left, right)]
        self._ctx = [SpheroEduAPI(t) for t in toys]
        self.apis = [c.__enter__() for c in self._ctx]

    def light(self, rgb_l, rgb_r):
        if self.sim:
            return
        from spherov2.types import Color
        for api, rgb in zip(self.apis, (rgb_l, rgb_r)):
            api.set_main_led(Color(*rgb))

    def aim_light(self, on):
        if not self.sim:
            for api in self.apis:
                api.set_back_led(255 if on else 0)

    def rotate(self, i, heading):
        if not self.sim:
            self.apis[i].set_heading(heading)

    def reset_aim(self):
        if not self.sim:
            for api in self.apis:
                api.reset_aim()

    def drive(self, cmds):
        if cmds == self.last:
            return
        if not self.sim:
            for api, (h, _) in zip(self.apis, cmds):
                api.set_heading(h)
            for api, (_, s) in zip(self.apis, cmds):
                api.set_speed(s)
        self.last = list(cmds)

    def stop(self):
        if not self.sim:
            for api in self.apis:
                try:
                    api.set_speed(0)
                except Exception:
                    pass
        self.last = [None, None]

    def close(self):
        self.stop()
        if not self.sim:
            for c in self._ctx:
                try:
                    c.__exit__(None, None, None)
                except Exception:
                    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--left", default="SB-0A38")
    ap.add_argument("--right", default="SB-61AA")
    ap.add_argument("--max-speed", type=int, default=50)
    ap.add_argument("--turn", type=float, default=0.4, help="turn-in-place strength for the arrow keys")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--lsl", action="store_true")
    a = ap.parse_args()

    import tkinter as tk
    print("Connecting..." if not a.sim else "Simulation mode (no robots)", flush=True)
    balls = Balls(a.left, a.right, a.sim)
    balls.light((0, 0, 255), (255, 0, 0))
    balls.aim_light(True)

    lsl = {"inlet": None, "next_try": 0.0}
    if a.lsl:
        print("LSL: listening for the ChairCommands stream (keys work meanwhile)", flush=True)

    st = dict(mode="AIM", sel=0, aim=[0, 0], keys=set(), brake=False, yaw=0.0, max=a.max_speed,
              auto=[], auto_until=0.0, source="-")

    root = tk.Tk()
    root.title("Sphero wheelchair")
    root.geometry("760x420")
    big = tk.Label(root, font=("Segoe UI", 34, "bold"), fg="white", bg="#1d4ed8")
    big.pack(fill="x")
    info = tk.Label(root, font=("Consolas", 13), justify="left", anchor="w")
    info.pack(fill="both", expand=True, padx=12, pady=8)

    def key_down(e):
        k = e.keysym
        if k == "Escape":
            return quit_()
        if st["mode"] == "AIM":
            if k in ("Left", "Right"):
                step = 2 if e.state & 0x0001 else 10        # Shift = fine 2-degree steps
                st["aim"][st["sel"]] = (st["aim"][st["sel"]] + (-step if k == "Left" else step)) % 360
                balls.rotate(st["sel"], st["aim"][st["sel"]])
            elif k == "Tab":
                st["sel"] = 1 - st["sel"]
            elif k == "Return":
                balls.reset_aim()
                balls.aim_light(False)
                st.update(mode="DRIVE", yaw=0.0)
            return "break"
        if k == "space":
            st["brake"] = not st["brake"]
            st["auto"] = []
        elif k in ("plus", "equal", "KP_Add"):
            st["max"] = min(150, st["max"] + 10)
        elif k in ("minus", "KP_Subtract"):
            st["max"] = max(20, st["max"] - 10)
        elif k in ("r", "R"):
            st["yaw"] = 0.0
        elif k in ("t", "T"):                               # back to AIM without restarting
            balls.stop()
            balls.aim_light(True)
            st.update(mode="AIM", sel=0, aim=[0, 0], keys=set(), auto=[])
        else:
            st["keys"].add(k)

    def key_up(e):
        st["keys"].discard(e.keysym)

    def read_lsl():
        if not a.lsl:
            return
        if lsl["inlet"] is None:                       # keep looking, so start order doesn't matter
            if time.time() < lsl["next_try"]:
                return
            from pylsl import StreamInlet, resolve_byprop
            found = resolve_byprop("name", "ChairCommands", timeout=0.1)
            lsl["next_try"] = time.time() + 2.0
            if not found:
                return
            lsl["inlet"] = StreamInlet(found[0])
            print("LSL: connected to ChairCommands", flush=True)
        msgs, _ = lsl["inlet"].pull_chunk(timeout=0.0)
        for (m,) in msgs:
            got = apply_command(st, m)
            print(f"received {m}" + ("" if got else "  (ignored)"), flush=True)

    def tick():
        read_lsl()
        if st["mode"] == "AIM":
            big.config(text="AIM: back lights to the BACK", bg="#1d4ed8")
            info.config(text=f"Selected ball: {'LEFT (blue)' if st['sel'] == 0 else 'RIGHT (red)'}\n"
                             f"Left/Right = rotate it 10 deg (Shift: 2 deg)   Tab = other ball   Enter = done\n"
                             f"headings now: left {st['aim'][0]}  right {st['aim'][1]}")
            root.after(int(TICK_S * 1000), tick)
            return
        k = st["keys"]
        v = (1 if "Up" in k else 0) - (1 if "Down" in k else 0)
        u = (1 if ("d" in k or "D" in k) else 0) - (1 if ("a" in k or "A" in k) else 0)
        w = a.turn * ((1 if "Left" in k else 0) - (1 if "Right" in k else 0))
        if v or u or w:
            st["auto"], st["source"] = [], "keyboard"
        elif st["auto"]:
            now = time.time()
            if st["auto_until"] == 0.0:
                st["auto_until"] = now + st["auto"][0][3]
            if now >= st["auto_until"]:
                st["auto"].pop(0)
                st["auto_until"] = 0.0
            if st["auto"]:
                v, u, w = st["auto"][0][:3]
        if st["brake"]:
            v = u = w = 0
        cmds = ball_commands(v, u, w, st["yaw"], st["max"])
        if v == u == w == 0:
            balls.stop() if st["brake"] else balls.drive(cmds)
        else:
            balls.drive(cmds)
            st["yaw"] = (st["yaw"] + yaw_rate_deg(w, st["max"]) * TICK_S) % 360
        if st["brake"]:
            big.config(text="BRAKED (Space to release)", bg="#c1121f")
        elif v or u or w:
            big.config(text="MOVING", bg="#15803d")
        else:
            big.config(text="READY", bg="#374151")
        (hl, sl), (hr, sr) = cmds
        info.config(text=f"speed cap {st['max']} / 255     estimated chair turn {st['yaw']:5.0f} deg\n"
                         f"left ball  heading {hl:3d}  speed {sl:4d}\n"
                         f"right ball heading {hr:3d}  speed {sr:4d}\n"
                         f"last command from: {st['source']}\n\n"
                         f"Up/Down move  Left/Right turn  A/D slide  Space brake  +/- speed\n"
                         f"R reset forward  T re-align back lights  Esc quit")
        root.after(int(TICK_S * 1000), tick)

    def quit_():
        balls.close()
        root.destroy()

    root.bind("<KeyPress>", key_down)
    root.bind("<KeyRelease>", key_up)
    root.protocol("WM_DELETE_WINDOW", quit_)
    root.after(100, tick)
    try:
        root.mainloop()
    finally:
        balls.close()


if __name__ == "__main__":
    main()
