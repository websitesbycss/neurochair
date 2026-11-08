"""Spoken object alerts for blind and low-vision users: camera -> YOLO -> "person ahead".

Reads frames from a webcam (the GoPro in USB webcam mode shows up as one), runs a small YOLO detector,
and speaks newly seen objects with a rough direction (left / ahead / right).

Setup:   .venv/Scripts/python -m pip install -r requirements-assist.txt
Usage:
    python src/app/vision_assist.py --list           # which camera indices work
    python src/app/vision_assist.py --webcam 1       # live camera (GoPro webcam is usually not 0)
    python src/app/vision_assist.py --image pic.jpg  # one image, saves pic_detected.jpg
    python src/app/vision_assist.py --gopro-usb      # GoPro over USB directly (quit the GoPro Webcam app first)
    python src/app/vision_assist.py --gopro          # GoPro Wi-Fi preview (laptop on the GoPro's Wi-Fi)
    add --no-voice to print instead of speaking
    add --chair to send safety holds to chair_drive.py --lsl (close obstacle in the middle of the view)
The first run downloads the YOLO model weights (needs internet once).

GoPro over Wi-Fi (Open GoPro HTTP API; check the docs for your firmware):
    start preview: GET http://10.5.5.9:8080/gopro/camera/stream/start  -> video on udp://@0.0.0.0:8554
"""
import argparse
import time

# Objects worth announcing, and how to say them.
ALERT = {"person": "person", "chair": "chair", "bench": "bench", "bicycle": "bike", "car": "car",
         "motorcycle": "motorcycle", "bus": "bus", "truck": "truck", "dog": "dog", "cat": "cat",
         "potted plant": "plant", "dining table": "table", "couch": "couch", "bed": "bed",
         "toilet": "toilet", "suitcase": "suitcase", "backpack": "backpack", "stop sign": "stop sign"}
REPEAT_S = 4.0  # don't repeat the same phrase more often than this


def where(x_center, width):
    third = width / 3
    return "on the left" if x_center < third else "on the right" if x_center > 2 * third else "ahead"


def phrases(res, width):
    out = []
    for box in res.boxes:
        name = res.names[int(box.cls)]
        if name in ALERT:
            x0, _, x1, _ = box.xyxy[0].tolist()
            out.append(f"{ALERT[name]} {where((x0 + x1) / 2, width)}")
    return out


# Things that should stop the chair when they're close and in its path (--chair).
OBSTACLES = {"person", "dog", "cat", "chair", "bench", "bicycle", "backpack", "suitcase", "potted plant", "couch"}
CLOSE_FRAC = 0.35   # box at least this tall (fraction of the frame height) counts as close
HOLD_S = 1.0        # each hold lasts this long; resent while the obstacle stays


def box_list(res):
    return [(res.names[int(b.cls)], *b.xyxy[0].tolist()) for b in res.boxes]


def obstacle_ahead(boxes, width, height, close_frac=CLOSE_FRAC):
    """boxes: [(name, x0, y0, x1, y1)]. Returns e.g. "person ahead" when an obstacle is close and in the
    middle third of the view (the chair's path), else None."""
    for name, x0, y0, x1, y1 in boxes:
        if name in OBSTACLES and where((x0 + x1) / 2, width) == "ahead" and (y1 - y0) >= close_frac * height:
            return f"{ALERT.get(name, name)} ahead"
    return None


def find_gopro_usb_ip():
    """The GoPro's USB network gives the laptop 172.2X.1YZ.5x; the camera is .51 on that subnet."""
    import re
    import subprocess
    out = subprocess.run(["ipconfig"], capture_output=True, text=True).stdout
    for ip in re.findall(r"IPv4 Address[ .]*: (172\.2\d\.1\d\d\.\d+)", out):
        return ip.rsplit(".", 1)[0] + ".51"
    raise SystemExit("No GoPro USB network found. Is the GoPro plugged in and switched on?")


def start_gopro_usb(ip, res):
    """Start webcam mode over USB and keep the camera awake. Video arrives on udp://@0.0.0.0:8554."""
    import os
    import threading
    import requests
    ip = find_gopro_usb_ip() if ip == "auto" else ip
    base = f"http://{ip}:8080/gopro"
    requests.get(f"{base}/webcam/stop", timeout=5)
    time.sleep(1)
    r = requests.get(f"{base}/webcam/start", params={"res": res, "fov": 0}, timeout=5).json()
    print(f"GoPro at {ip}: webcam start -> {r}", flush=True)
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "fflags;nobuffer|flags;low_delay")

    def keep_alive():
        while True:
            try:
                requests.get(f"{base}/camera/keep_alive", timeout=3)
            except Exception:
                pass
            time.sleep(2.5)
    threading.Thread(target=keep_alive, daemon=True).start()


def start_gopro_wifi(ip="10.5.5.9"):
    """Laptop joined the GoPro's own Wi-Fi: start the preview stream and keep the camera awake.
    Video arrives on udp://@0.0.0.0:8554 (Open GoPro preview stream, no audio)."""
    import os
    import threading
    import requests
    base = f"http://{ip}:8080/gopro"
    try:
        requests.get(f"{base}/camera/stream/stop", timeout=5)
    except Exception:
        pass
    time.sleep(0.5)
    r = requests.get(f"{base}/camera/stream/start", timeout=5)
    print(f"GoPro Wi-Fi preview start -> HTTP {r.status_code}", flush=True)
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "fflags;nobuffer|flags;low_delay")

    def keep_alive():
        while True:
            try:
                requests.get(f"{base}/camera/keep_alive", timeout=3)
            except Exception:
                pass
            time.sleep(2.5)
    threading.Thread(target=keep_alive, daemon=True).start()


def list_cameras():
    import cv2
    for i in range(6):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        print(f"camera {i}: " + (f"OK {frame.shape[1]}x{frame.shape[0]}" if ok else "not available"))
        cap.release()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--webcam", type=int)
    ap.add_argument("--image")
    ap.add_argument("--gopro", action="store_true")
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--gopro-usb", nargs="?", const="auto", default=None,
                    help="read the GoPro directly over USB (quit the GoPro Webcam app first); optional camera IP")
    ap.add_argument("--res", type=int, default=7, help="GoPro webcam resolution: 4=480p, 7=720p, 12=1080p")
    ap.add_argument("--chair", action="store_true", help="send safety holds to chair_drive.py --lsl")
    ap.add_argument("--record", help="save the annotated view to this .mp4 (stop with q)")
    a = ap.parse_args()

    if a.list:
        return list_cameras()

    import cv2
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")  # smallest model; downloads on first run

    if a.image:
        img = cv2.imread(a.image)
        res = model(img, verbose=False, conf=a.conf)[0]
        print("\n".join(phrases(res, img.shape[1])) or "nothing to announce")
        out = a.image.rsplit(".", 1)[0] + "_detected.jpg"
        cv2.imwrite(out, res.plot())
        print("saved", out)
        return

    if a.gopro:
        start_gopro_wifi()
    if a.gopro_usb:
        start_gopro_usb(a.gopro_usb, a.res)

    def open_cap():
        if a.gopro or a.gopro_usb:
            return cv2.VideoCapture("udp://@0.0.0.0:8554", cv2.CAP_FFMPEG)
        cap = cv2.VideoCapture(a.webcam if a.webcam is not None else 0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    cam = LatestFrame(open_cap)
    voice = None if a.no_voice else Speaker()
    last_said, t_prev = {}, time.time()
    outlet, last_hold, writer = None, 0.0, None
    if a.chair:
        from pylsl import StreamInfo, StreamOutlet
        outlet = StreamOutlet(StreamInfo("ChairCommands", "Markers", 1, 0, "string", "chair-cmd-vision"))
        print("Co-pilot: sending safety holds to the chair (ChairCommands)", flush=True)
    try:
        while True:
            frame, age = cam.get()
            if frame is None:
                time.sleep(0.02)
                continue
            if age > 3.0:                       # feed stalled: reconnect instead of freezing
                print("camera feed stalled, reconnecting...", flush=True)
                cam.restart()
                continue
            res = model(frame, verbose=False, conf=a.conf, imgsz=640)[0]
            blocked = obstacle_ahead(box_list(res), frame.shape[1], frame.shape[0]) if outlet else None
            if blocked and time.time() - last_hold > 0.3:
                import json
                if time.time() - last_hold > 2.0:          # newly blocked: say why we're stopping
                    print(f"HOLD: {blocked}", flush=True)
                    if voice:
                        voice.say(f"Stopping, {blocked}")
                outlet.push_sample([json.dumps({"cmd": "hold", "reason": blocked, "seconds": HOLD_S})])
                last_hold = time.time()
            for p in phrases(res, frame.shape[1]):
                if time.time() - last_said.get(p, 0) > REPEAT_S:
                    last_said[p] = time.time()
                    print(p, flush=True)
                    if voice:
                        voice.say(p)
            view = res.plot()
            now = time.time()
            cv2.putText(view, f"{1 / max(now - t_prev, 1e-3):4.1f} fps", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 255, 0), 2)
            t_prev = now
            if blocked:
                cv2.putText(view, f"CHAIR STOPPED: {blocked}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 140, 255), 3)
            if a.record:
                if writer is None:
                    import os
                    os.makedirs(os.path.dirname(os.path.abspath(a.record)), exist_ok=True)
                    writer = cv2.VideoWriter(a.record, cv2.VideoWriter_fourcc(*"mp4v"), 12,
                                             (view.shape[1], view.shape[0]))
                    print(f"recording to {a.record}", flush=True)
                writer.write(view)
            cv2.imshow("vision assist (q to quit)", view)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        if writer is not None:
            writer.release()
            print(f"saved {a.record}", flush=True)
        cam.stop()
        cv2.destroyAllWindows()


class LatestFrame:
    """Reads the camera on a background thread and keeps only the newest frame, so a slow detector
    never makes the video fall behind. Reports how old the newest frame is so stalls can be caught."""

    def __init__(self, opener):
        import threading
        self.opener, self.lock, self.running = opener, threading.Lock(), True
        self.frame, self.stamp = None, 0.0
        self.cap = opener()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        black_since = None
        while self.running:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue
            if frame.mean() < 3:                # all-black frames count as a stall
                black_since = black_since or time.time()
                if time.time() - black_since > 2:
                    continue
            else:
                black_since = None
            with self.lock:
                self.frame, self.stamp = frame, time.time()

    def get(self):
        with self.lock:
            if self.frame is None:
                return None, 0.0
            return self.frame, time.time() - self.stamp

    def restart(self):
        with self.lock:
            self.cap.release()
            self.cap = self.opener()
            self.frame, self.stamp = None, 0.0

    def stop(self):
        self.running = False
        self.thread.join(timeout=1)
        self.cap.release()


class Speaker:
    """Speaks on its own thread so the video never waits for speech. Drops stale phrases."""

    def __init__(self):
        import queue
        import threading
        self.q = queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    def say(self, text):
        while not self.q.empty():               # only the newest announcement matters
            try:
                self.q.get_nowait()
            except Exception:
                break
        self.q.put(text)

    def _loop(self):
        import pyttsx3
        engine = pyttsx3.init()                  # pyttsx3 must live on the thread that uses it
        while True:
            engine.say(self.q.get())
            engine.runAndWait()


if __name__ == "__main__":
    main()
