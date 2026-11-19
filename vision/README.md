# TeamMARS Vision — AI on the drone camera

Optional helper for **TeamMARS-Telemetry**. It reads the drone camera, runs **YOLO object detection**
(or a light **OpenCV** filter) and streams the annotated picture to **camera panel 2**.

| Mode | What it shows | Cost |
|---|---|---|
| `yolo` (default) | boxes + labels for 80 object classes (people, cars, trucks, boats, animals…) | YOLO11n: **27 ms/frame, ~18.6 fps on an i7-10750H CPU** (measured) |
| `motion` | boxes around anything moving (OpenCV background subtraction) | very light |
| `edges` | edge outline view (OpenCV Canny) — helps in haze / low contrast | very light |
| `none` | pass-through | — |

**Why a separate process?** AI is heavy. Running it outside the ground station means it can never freeze
telemetry, the map or the controls. If it stops, panel 2 just shows "Connecting…" and keeps retrying.

## Use

```bash
./setup.sh            # once (~1.6 GB: CPU PyTorch + Ultralytics + OpenCV)
./run_vision.sh       # YOLO on Camera 1's URL from TeamMARS-Telemetry
```

Then in TeamMARS-Telemetry press **Cameras**; panel 2 already points at `http://127.0.0.1:8090/stream.mjpg`.

Notes
- **USB capture adapters** (FPV receiver / HDMI grabber): use the device number, e.g. `./run_vision.sh --source 2` for
  `/dev/video2`. A USB device can only be opened by one program — let the helper have it and watch panel 2.
- Best with **RTSP** cameras (several viewers can share one stream). A UDP stream can only be received by one
  program: give the helper the camera and use panel 2 for the picture.
- The YOLO model `yolo11n.pt` (~5 MB) downloads automatically on first run.
