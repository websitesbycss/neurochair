"""Spoken object alerts for blind and low-vision users: camera -> YOLO -> "person ahead".

Reads frames from a webcam (the GoPro in USB webcam mode shows up as one), runs a small YOLO detector,
and speaks newly seen objects with a rough direction (left / ahead / right).

Setup:   .venv/Scripts/python -m pip install -r requirements-assist.txt
Usage:
    python src/app/vision_assist.py --list           # which camera indices work
    python src/app/vision_assist.py --webcam 1       # live camera (GoPro webcam is usually not 0)
    python src/app/vision_assist.py --image pic.jpg  # one image, saves pic_detected.jpg
    python src/app/vision_assist.py --gopro          # GoPro Wi-Fi preview (laptop on the GoPro's Wi-Fi)
    add --no-voice to print instead of speaking
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

    voice = None
    if not a.no_voice:
        import pyttsx3
        voice = pyttsx3.init()
    if a.gopro:
        import requests
        requests.get("http://10.5.5.9:8080/gopro/camera/stream/start", timeout=5)
        cap = cv2.VideoCapture("udp://@0.0.0.0:8554", cv2.CAP_FFMPEG)
    else:
        cap = cv2.VideoCapture(a.webcam if a.webcam is not None else 0, cv2.CAP_DSHOW)

    last_said = {}
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue
        res = model(frame, verbose=False, conf=a.conf)[0]
        for p in phrases(res, frame.shape[1]):
            if time.time() - last_said.get(p, 0) > REPEAT_S:
                last_said[p] = time.time()
                print(p, flush=True)
                if voice:
                    voice.say(p)
                    voice.runAndWait()
        cv2.imshow("vision assist (q to quit)", res.plot())
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
