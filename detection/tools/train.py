#!/usr/bin/env python3
"""Train the TeamMARS detector (YOLO11n) on dataset/yolo/ and install it into the app.

    python tools/train.py                 # ~60 epochs on CPU (works on any laptop, takes a while)
    python tools/train.py --epochs 100 --device 0    # on an NVIDIA GPU (much faster)

Result: models/teammars.pt (+ OpenVINO build). Restart the app: the badge turns "TeamMARS model".
Tip: no GPU? Zip dataset/yolo/, train in Google Colab (free GPU) with the same command, copy best.pt back
to models/teammars.pt and run `python tools/train.py --export-only`.
"""

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dataset" / "yolo" / "data.yaml"
DEST = ROOT / "models" / "teammars.pt"


def export(pt: Path, imgsz: int):
    target = pt.with_name(pt.stem + "_openvino_model")
    shutil.rmtree(target, ignore_errors=True)  # old build out of the way first
    out = Path(YOLO(str(pt)).export(format="openvino", imgsz=imgsz))
    if out.resolve() != target.resolve():
        out.rename(target)
    print("OpenVINO build:", target)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=480)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--export-only", action="store_true")
    a = ap.parse_args()

    if not a.export_only:
        if not DATA.exists():
            raise SystemExit("No dataset yet: capture photos with the app's Train button, then run tools/autolabel.py")
        model = YOLO("yolo11n.pt")  # small + fast: ~25-30 ms per frame on a laptop CPU
        r = model.train(data=str(DATA), epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device,
                        patience=20, project=str(ROOT / "runs"), name="teammars", exist_ok=True,
                        # drone views: objects seen from any side, any rotation, varying light
                        fliplr=0.5, flipud=0.5, degrees=180, scale=0.5, hsv_v=0.5, mosaic=1.0)
        best = Path(r.save_dir) / "weights" / "best.pt"
        DEST.parent.mkdir(exist_ok=True)
        shutil.copy(best, DEST)
        print("Installed:", DEST)
    export(DEST, a.imgsz)
    print("Restart the app to use your model.")


if __name__ == "__main__":
    main()
