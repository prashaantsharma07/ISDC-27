#!/usr/bin/env python3
"""Auto-label the photos captured with the app's Train button.

Each item's photos are in dataset/raw/<item>/ (the app puts them there), so the label is already known.
Grounding DINO (a large open-vocabulary detector, too slow for live video but accurate) only has to
find WHERE the item is. Output: a YOLO dataset in dataset/yolo/ + review sheets in dataset/review/.

    python tools/autolabel.py              # label everything
    python tools/autolabel.py --box 0.30   # stricter box threshold
"""

import argparse
import json
import random
import re
import shutil
from pathlib import Path

import torch
from PIL import Image, ImageDraw
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text())
RAW, OUT, REVIEW = ROOT / "dataset" / "raw", ROOT / "dataset" / "yolo", ROOT / "dataset" / "review"


def slug(n):
    return re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", type=float, default=0.25, help="minimum box score")
    ap.add_argument("--val", type=float, default=0.15, help="share of photos kept for validation")
    ap.add_argument("--model", default="IDEA-Research/grounding-dino-tiny")
    a = ap.parse_args()

    names = [t["name"] for t in CFG["targets"]]  # class ids follow config.json order
    prompts = {t["name"]: t["prompts"] for t in CFG["targets"]}
    proc = AutoProcessor.from_pretrained(a.model)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(a.model).eval()

    shutil.rmtree(OUT, ignore_errors=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    random.seed(7)
    total, skipped = 0, []
    for cid, name in enumerate(names):
        photos = sorted((RAW / slug(name)).glob("*.jpg"))
        if not photos:
            continue
        text = ". ".join(prompts[name]) + "."
        sheet = []
        for i, f in enumerate(photos):
            im = Image.open(f).convert("RGB")
            inp = proc(images=im, text=text, return_tensors="pt")
            with torch.no_grad():
                out = model(**inp)
            res = proc.post_process_grounded_object_detection(out, inp.input_ids, threshold=a.box, text_threshold=0.2, target_sizes=[im.size[::-1]])[0]
            if len(res["scores"]) == 0:
                skipped.append(f.name)
                continue
            k = int(torch.argmax(res["scores"]))  # one item per photo: keep the best box
            x1, y1, x2, y2 = res["boxes"][k].tolist()
            W, H = im.size
            split = "val" if random.random() < a.val else "train"
            (OUT / "images" / split).mkdir(parents=True, exist_ok=True)
            (OUT / "labels" / split).mkdir(parents=True, exist_ok=True)
            shutil.copy(f, OUT / "images" / split / f"{slug(name)}_{f.name}")
            (OUT / "labels" / split / f"{slug(name)}_{f.stem}.txt").write_text(
                f"{cid} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} {(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}\n")
            total += 1
            t = im.copy()
            t.thumbnail((240, 240))
            k2 = t.width / W
            ImageDraw.Draw(t).rectangle([x1 * k2, y1 * k2, x2 * k2, y2 * k2], outline=(90, 110, 151), width=3)
            sheet.append(t)
            print(f"{name}: {i + 1}/{len(photos)}  score {float(res['scores'][k]):.2f}")
        if sheet:  # contact sheet: check the boxes at a glance, delete bad photos and re-run
            cols = 8
            rows = (len(sheet) + cols - 1) // cols
            cs = Image.new("RGB", (cols * 244, rows * 244), (239, 232, 220))
            for j, t in enumerate(sheet):
                cs.paste(t, ((j % cols) * 244 + 2, (j // cols) * 244 + 2))
            cs.save(REVIEW / f"{slug(name)}.jpg", quality=85)

    (OUT / "data.yaml").write_text(
        f"path: {OUT}\ntrain: images/train\nval: images/val\nnames:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(names)))
    print(f"\nLabelled {total} photos -> {OUT}\nReview the boxes: {REVIEW}")
    if skipped:
        print(f"No box found (left out): {len(skipped)} photos, e.g. {skipped[:5]}")


if __name__ == "__main__":
    main()
