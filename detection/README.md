<p align="center"><img src="web/mars.png" width="110" alt="TeamMARS logo"></p>

<h1 align="center">TeamMARS object detection</h1>
<p align="center"><b>Find, identify and report the competition items on the drone camera, with zero added video latency.</b><br>
Runs in any browser on Windows, macOS or Linux. Galaxy UI: black, shiny white and hazy orange, with stars that orbit your cursor.</p>

## Built for the task

> 3–5 dummy items on the surface — e.g. a cube like a sensor module, a small instrument box, hand tools such as a hammer,
> a marker flag, a short tripod stand. Locate each item, identify it and assess its condition.

| The task needs | What the app does |
|---|---|
| **Find the items that matter** | General model knows **601 object types** (Open Images V7: Hammer, Tripod, Flag, Box, Wrench, Screwdriver…). Mission items get an orange box; with **All** on, every other object gets a white dashed box |
| **Your own mission list** | ✎ in the Mission panel: add / rename / remove targets, each matched by any of the 601 types — saved instantly |
| **Identify** | Name + confidence on a glass label that glides with the object |
| **Colour** | Dominant colour of each item, read from its pixels (e.g. "red", "dark grey"), with a swatch |
| **Condition** | Hints (may be lying down, partly out of view, low confidence) + one-tap tags: Intact / Damaged / Tipped over / Dirty / Partly buried |
| **Company / brand** | "Read label / brand" on a close-up: reads printed text and matches known brands (only when the label is readable) |
| **Report for the judges** | Mission checklist fills itself (close-up + in-view snapshot per item); one click exports a self-contained HTML report |

## Why it is fast

- **The video never goes through the AI.** Camera → browser → GPU shader (LUT, flip, mirror, rotate, invert) → screen.
  Detection runs beside it on small snapshots, one at a time, so the picture is never delayed and nothing queues up.
- **OpenVINO on Intel CPUs** (built automatically): about **5× faster than plain PyTorch** in our tests on an i7-10750H.
  The 601-type model runs ~140 ms per frame at 480 px; a trained YOLO11n is much faster.
- Boxes ease between detections so they look smooth even at 10 detections per second.

## Your model: the important part

The general model finds many things (people, cameras, tripods, sometimes hammers) but **not reliably your exact dummy items**
from a drone's view. For the competition, train a small fast model on **your own items** — built into the app:

1. **Train → Burst 20**: one item in view, capture photos from the drone camera (heights, angles, light, backgrounds).
   Aim for 60–150 photos per item.
2. `python tools/autolabel.py`: Grounding DINO draws the boxes automatically (the item is known from the folder).
   Check `dataset/review/*.jpg`, delete bad photos, re-run.
3. `python tools/train.py`: trains YOLO11n and builds the OpenVINO version (CPU works; a GPU or free Google Colab is faster).
4. Restart: the badge turns **TeamMARS model** (your model for the mission items + the general model for everything else).

## Run it

```bash
./setup.sh      # once (Windows: setup.bat)   needs Python 3.10+, ~2 GB
./start.sh      # opens http://127.0.0.1:8765   (Windows: start.bat, macOS: start.command)
```

Pick the camera in **Settings**: USB capture adapters (FPV receivers / HDMI grabbers) and webcams appear by name.
One app per laptop and camera, as the team plans: front camera on one laptop, bottom camera on another.

| Control | |
|---|---|
| **Mirror / Flip / Rotate / Invert** | Fix any camera mounting (keys M, F, R, I) |
| **LUT** + strength | Clarity, Haze Cut, Low Light, Ground Contrast (mutes soil/grass so objects pop), Mono Detail, Neutral, or load any `.cube` |
| Exposure / contrast / saturation | Live, on the GPU |
| Detect · All · Snap · Train · Settings | D · A · S keys; confidence and detection size (480 / 640 for far objects) in Settings |
| Mission panel | › hides it (the video widens), the ‹ Mission tab on the right brings it back |

LUTs change colour and contrast to make the feed easier to read. They do not add frames.
Detection always uses the untouched camera picture.

## Files

| Path | |
|---|---|
| `server.py` | Local server: detector, colours, hints, label reading, training capture |
| `web/` | The app (HTML/CSS/JS, WebGL), `web/luts/` TeamMARS LUTs (CC0, from `tools/make_luts.py`) |
| `config.json` | Mission targets (name + object types), brands list, thresholds |
| `tools/autolabel.py` · `tools/train.py` | Training workflow |

Credits: [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) (AGPL-3.0) incl. the Open Images V7 model,
[Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) via Hugging Face Transformers, OpenVINO, OpenCV, FastAPI.
