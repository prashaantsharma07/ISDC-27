#!/bin/bash
# One-time install of TeamMARS Vision (YOLO + OpenCV) into its own venv (~1.6 GB, CPU only).
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
.venv/bin/python -c "import cv2, ultralytics; print('TeamMARS Vision ready: OpenCV', cv2.__version__, '/ Ultralytics', ultralytics.__version__)"
