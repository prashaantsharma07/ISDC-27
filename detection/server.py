#!/usr/bin/env python3
"""
TeamMARS object detection — local server.

The browser shows the camera itself (zero added latency); this server only receives small
JPEG snapshots over a WebSocket, runs the detector and answers with boxes, colours and hints.
One frame in flight per client, so detections never queue up and never lag the video.

    python server.py            -> open http://127.0.0.1:8765
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text())
DATASET = ROOT / "dataset" / "raw"


# ------------------------------------------------------------------ colour naming
_HUES = [(10, "red"), (22, "orange"), (34, "yellow"), (78, "green"), (96, "teal"), (130, "blue"), (150, "purple"), (170, "pink"), (180, "red")]


def colour_of(crop: np.ndarray) -> dict:
    """Dominant colour of the object (centre of the box, where the object is most likely to be)."""
    h, w = crop.shape[:2]
    if h < 4 or w < 4:
        return {"name": "unknown", "hex": "#888888"}
    c = crop[int(h * 0.25): int(h * 0.75), int(w * 0.25): int(w * 0.75)]
    small = cv2.resize(c, (32, 32), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
    k = 3
    _, labels, centers = cv2.kmeans(small, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    bgr = centers[int(np.argmax(counts))]
    hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0, 0]
    hue, sat, val = int(hsv[0]), int(hsv[1]), int(hsv[2])
    if val < 50:
        name = "black"
    elif sat < 40:
        name = "white" if val > 200 else "grey" if val > 110 else "dark grey"
    elif hue in range(8, 25) and val < 150:
        name = "brown"
    else:
        name = next(n for limit, n in _HUES if hue <= limit)
        if val < 110:
            name = "dark " + name
    b, g, r = (int(x) for x in bgr)
    return {"name": name, "hex": f"#{r:02x}{g:02x}{b:02x}"}


def condition_hint(target: str, box: list[float], conf: float, frame_w: int, frame_h: int) -> str:
    """Cheap, honest hints only — the operator confirms the real condition."""
    x1, y1, x2, y2 = box
    w, h = (x2 - x1) * frame_w, (y2 - y1) * frame_h
    hints = []
    if target in ("Marker flag", "Tripod") and h > 0 and w / h > 1.6:
        hints.append("may be lying down / fallen")
    if x1 < 0.01 or y1 < 0.01 or x2 > 0.99 or y2 > 0.99:
        hints.append("partly out of view")
    if conf < 0.4:
        hints.append("low confidence — get closer")
    return "; ".join(hints)


# ------------------------------------------------------------------ detector
class Detector:
    def __init__(self):
        self.lock = threading.Lock()
        self.model = None
        self.mode = "none"
        self.map: dict[int, str] = {}
        self.load()

    def load(self):
        from ultralytics import YOLO, YOLOWorld

        models = ROOT / "models"
        custom = ROOT / CFG["custom_model"]
        targets = [t["name"] for t in CFG["targets"]]
        if custom.exists():
            ov = custom.with_name(custom.stem + "_openvino_model")
            m = YOLO(str(ov), task="detect") if ov.exists() else YOLO(str(custom))
            self.backend = "openvino" if ov.exists() else "pytorch"
            self.map = {i: n for i, n in m.names.items()}
            self.mode = "custom"
        else:
            prompts, owner = [], []
            for t in CFG["targets"]:
                for p in t["prompts"]:
                    prompts.append(p)
                    owner.append(t["name"])
            self.map = dict(enumerate(owner))
            self.mode = "starter"
            # OpenVINO build of the starter model for exactly these prompts (~5x faster on Intel CPUs)
            key = hashlib.sha1(json.dumps([CFG["starter_model"], prompts, CFG["imgsz"]]).encode()).hexdigest()[:10]
            ov = models / f"starter_{key}_openvino_model"
            m, self.backend = None, "pytorch"
            if ov.exists():
                m, self.backend = YOLO(str(ov), task="detect"), "openvino"
            else:
                w = models / CFG["starter_model"]
                world = YOLOWorld(str(w) if w.exists() else CFG["starter_model"])
                world.set_classes(prompts)
                m = world
                try:
                    import openvino  # noqa: F401, PLC0415
                    print("Building the fast (OpenVINO) starter model once — about a minute…")
                    out = Path(world.export(format="openvino", imgsz=CFG["imgsz"]))
                    out.rename(ov)
                    m, self.backend = YOLO(str(ov), task="detect"), "openvino"
                except Exception as e:  # stays on PyTorch: slower but works
                    print("OpenVINO not used:", e)
        self.model = m
        self.targets = targets
        dummy = np.zeros((CFG["imgsz"], CFG["imgsz"], 3), np.uint8)
        m.predict(dummy, imgsz=CFG["imgsz"], verbose=False)  # warm-up

    def detect(self, img: np.ndarray, conf: float, imgsz: int, enabled: set[str] | None):
        with self.lock:
            t0 = time.perf_counter()
            r = self.model.predict(img, imgsz=imgsz, conf=conf, verbose=False)[0]
            infer_ms = (time.perf_counter() - t0) * 1000
        H, W = img.shape[:2]
        best: dict[tuple, dict] = {}
        out = []
        for b in r.boxes:
            target = self.map.get(int(b.cls[0]), r.names[int(b.cls[0])])
            if enabled and target not in enabled:
                continue
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
            c = float(b.conf[0])
            crop = img[max(0, int(y1)): int(y2), max(0, int(x1)): int(x2)]
            box = [x1 / W, y1 / H, x2 / W, y2 / H]
            out.append({"target": target, "conf": round(c, 3), "box": [round(v, 4) for v in box],
                        "colour": colour_of(crop), "hint": condition_hint(target, box, c, W, H)})
        # several prompts can hit the same object: keep the strongest per target+location
        out.sort(key=lambda d: -d["conf"])
        for d in out:
            key = (d["target"], round(d["box"][0], 1), round(d["box"][1], 1))
            best.setdefault(key, d)
        return list(best.values()), infer_ms


app = FastAPI(title=CFG["app_name"])
detector: Detector | None = None


@app.on_event("startup")
async def _startup():
    global detector
    detector = await asyncio.to_thread(Detector)
    print(f"{CFG['app_name']}: model ready ({detector.mode}, {detector.backend}) -> http://{CFG['host']}:{CFG['port']}")


@app.get("/api/status")
async def status():
    counts = {d.name: len(list(d.glob("*.jpg"))) for d in DATASET.glob("*") if d.is_dir()} if DATASET.exists() else {}
    return {"app": CFG["app_name"], "mode": detector.mode if detector else "loading", "backend": detector.backend if detector else "",
            "targets": [t["name"] for t in CFG["targets"]], "conf": CFG["conf"], "imgsz": CFG["imgsz"], "dataset": counts}


@app.websocket("/ws/detect")
async def ws_detect(ws: WebSocket):
    await ws.accept()
    conf, imgsz, enabled = CFG["conf"], CFG["imgsz"], None
    try:
        while True:
            msg = await ws.receive()
            if msg.get("text"):
                s = json.loads(msg["text"])
                conf = float(s.get("conf", conf))
                imgsz = int(s.get("imgsz", imgsz))
                enabled = set(s["enabled"]) if s.get("enabled") else None
                continue
            data = msg.get("bytes")
            if not data:
                if msg.get("type") == "websocket.disconnect":
                    break
                continue
            seq = int.from_bytes(data[:4], "little")
            img = cv2.imdecode(np.frombuffer(data[4:], np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            dets, ms = await asyncio.to_thread(detector.detect, img, conf, imgsz, enabled)
            await ws.send_text(json.dumps({"seq": seq, "ms": round(ms, 1), "mode": detector.mode, "dets": dets}))
    except WebSocketDisconnect:
        pass


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


@app.post("/api/capture")
async def capture(target: str = Form(...), image: UploadFile = File(...)):
    """Save a full-resolution frame for training the custom model."""
    if target not in [t["name"] for t in CFG["targets"]]:
        return JSONResponse({"error": "unknown target"}, 400)
    d = DATASET / _slug(target)
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{datetime.now():%Y%m%d-%H%M%S-%f}.jpg"
    f.write_bytes(await image.read())
    return {"saved": f.name, "count": len(list(d.glob("*.jpg")))}


_ocr = None


@app.post("/api/inspect")
async def inspect(image: UploadFile = File(...)):
    """Read text/logos on a close-up crop (optional: needs `pip install easyocr`)."""
    global _ocr
    try:
        import easyocr  # noqa: PLC0415
    except ImportError:
        return {"text": [], "brand": None, "note": "Label reading is off: run `pip install easyocr` in the app's venv."}
    if _ocr is None:
        _ocr = await asyncio.to_thread(easyocr.Reader, ["en"], gpu=False, verbose=False)
    img = cv2.imdecode(np.frombuffer(await image.read(), np.uint8), cv2.IMREAD_COLOR)
    res = await asyncio.to_thread(_ocr.readtext, img)
    words = [t for _, t, p in res if p > 0.3]
    joined = " ".join(words).lower()
    brand = next((b for b in CFG["brands"] if b.lower().replace("+", "") in joined.replace("+", "")), None)
    return {"text": words, "brand": brand, "note": "" if words else "No readable text — get closer or steadier."}


@app.get("/")
async def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "web"), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=CFG["host"], port=CFG["port"], log_level="warning")
