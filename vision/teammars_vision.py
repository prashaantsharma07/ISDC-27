#!/usr/bin/env python3
"""
TeamMARS Vision — optional AI overlay for the drone camera, shown in TeamMARS-Telemetry's camera panel.

Reads any camera stream (RTSP / UDP / HTTP / USB / file), runs YOLO object detection or a light
OpenCV filter, and serves the annotated picture as MJPEG on http://127.0.0.1:8090/stream.mjpg —
the default URL of camera panel 2.

It runs as its own process on purpose: heavy AI work can never freeze the ground station,
the map or telemetry. Close it and the panel just shows "Connecting…".

    python teammars_vision.py --source rtsp://192.168.144.25:8554/main.264            # YOLO (default)
    python teammars_vision.py --source udp://0.0.0.0:5600 --mode motion               # OpenCV motion boxes
    python teammars_vision.py --source 0 --mode edges                                 # USB webcam, edge view
    python teammars_vision.py --source test                                           # built-in test pattern

Modes:  yolo (objects, needs `ultralytics`) | motion (moving things) | edges | none (pass-through)
"""

from __future__ import annotations

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

BOTTLE = (78, 106, 0)  # BGR of #006A4E
VERMILION = (52, 66, 227)  # BGR of #E34234
BONE = (201, 218, 227)


# ------------------------------------------------------------------ capture (always the newest frame)
class LatestFrameReader:
    """Reads frames on a thread and keeps only the newest one, so processing never builds up lag."""

    def __init__(self, source: str):
        self.source = source
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.connected = False
        threading.Thread(target=self._run, daemon=True).start()

    def _open(self):
        if self.source == "test":
            return None
        src = int(self.source) if self.source.isdigit() else self.source
        if isinstance(src, str) and src.startswith("udp://") and "?" not in src:
            # big receive buffer: keyframes arrive in bursts and would otherwise be dropped
            src += "?fifo_size=5000000&overrun_nonfatal=1&buffer_size=8388608"
        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG) if isinstance(src, str) else cv2.VideoCapture(src)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _test_frame(self, t: float):
        img = np.zeros((480, 640, 3), np.uint8)
        img[:] = (40, 60, 30)
        x = int(320 + 220 * np.sin(t))
        cv2.circle(img, (x, 240), 60, BONE, -1)
        cv2.putText(img, "TeamMARS test pattern", (150, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, BONE, 2)
        return img

    def _run(self):
        cap = None
        while self.running:
            if self.source == "test":
                frame = self._test_frame(time.time())
                time.sleep(1 / 30)
            else:
                if cap is None or not cap.isOpened():
                    self.connected = False
                    cap = self._open()
                    if not cap.isOpened():
                        time.sleep(2)  # camera not up yet: retry
                        continue
                ok, frame = cap.read()
                if not ok:
                    cap.release()
                    cap = None
                    continue
            self.connected = True
            with self.lock:
                self.frame = frame

    def latest(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()


# ------------------------------------------------------------------ processors
class YoloProcessor:
    def __init__(self, model: str, conf: float, imgsz: int):
        from ultralytics import YOLO  # imported only when YOLO mode is used

        self.model = YOLO(model)
        self.conf = conf
        self.imgsz = imgsz

    def __call__(self, frame):
        res = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        names = res.names
        counts: dict[str, int] = {}
        for box in res.boxes:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            name = names[int(box.cls[0])]
            counts[name] = counts.get(name, 0) + 1
            label = f"{name} {float(box.conf[0]):.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), VERMILION, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 6, y1), VERMILION, -1)
            cv2.putText(frame, label, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return frame, ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "no objects"


class MotionProcessor:
    def __init__(self):
        self.bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=32, detectShadows=False)

    def __call__(self, frame):
        mask = self.bg.apply(frame)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        n = 0
        min_area = frame.shape[0] * frame.shape[1] * 0.002
        for c in contours:
            if cv2.contourArea(c) < min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), VERMILION, 2)
            n += 1
        return frame, f"{n} moving"


def edges(frame):
    e = cv2.Canny(cv2.GaussianBlur(frame, (5, 5), 0), 60, 140)
    out = frame // 3
    out[e > 0] = BONE
    return out, "edges"


def passthrough(frame):
    return frame, ""


# ------------------------------------------------------------------ MJPEG server
class Stream:
    jpeg: bytes | None = None
    cond = threading.Condition()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):
        if self.path not in ("/", "/stream.mjpg"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                with Stream.cond:
                    Stream.cond.wait(timeout=2)
                    data = Stream.jpeg
                if data is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n")
                self.wfile.write(data)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="rtsp://, udp://, http://, file path, USB index (0) or 'test'")
    ap.add_argument("--mode", choices=["yolo", "motion", "edges", "none"], default="yolo")
    ap.add_argument("--model", default="yolo11n.pt", help="YOLO weights (downloaded on first use)")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--imgsz", type=int, default=480, help="YOLO input size (smaller = faster)")
    ap.add_argument("--width", type=int, default=960, help="output width (keeps aspect)")
    ap.add_argument("--fps", type=float, default=20, help="max processing rate")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    a = ap.parse_args()

    proc = {"yolo": lambda: YoloProcessor(a.model, a.conf, a.imgsz), "motion": MotionProcessor,
            "edges": lambda: edges, "none": lambda: passthrough}[a.mode]()
    reader = LatestFrameReader(a.source)

    server = ThreadingHTTPServer((a.host, a.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"TeamMARS Vision: {a.mode} on {a.source} -> http://{a.host}:{a.port}/stream.mjpg")

    period = 1.0 / a.fps
    fps_avg, last = 0.0, time.time()
    while True:
        t0 = time.time()
        frame = reader.latest()
        if frame is None:
            time.sleep(0.05)
            continue
        h, w = frame.shape[:2]
        scale = min(1.0, a.width / w)
        # sizes in multiples of 16: GPU (VA-API) JPEG decoders in the viewer mis-decode odd sizes
        nw, nh = max(16, int(w * scale) // 16 * 16), max(16, int(h * scale) // 16 * 16)
        if (nw, nh) != (w, h):
            frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
        t_inf = time.time()
        frame, info = proc(frame)
        infer_ms = (time.time() - t_inf) * 1000
        now = time.time()
        fps_avg = 0.9 * fps_avg + 0.1 * (1.0 / max(now - last, 1e-3))
        last = now
        hud = f"TeamMARS {a.mode.upper()}  {fps_avg:4.1f} fps  {infer_ms:4.0f} ms  {info}"
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 26), BOTTLE, -1)
        cv2.putText(frame, hud, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, BONE, 1, cv2.LINE_AA)
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            with Stream.cond:
                Stream.jpeg = jpg.tobytes()
                Stream.cond.notify_all()
        time.sleep(max(0.0, period - (time.time() - t0)))


if __name__ == "__main__":
    main()
