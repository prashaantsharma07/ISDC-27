#!/bin/bash
# Start TeamMARS Vision. With no --source it uses Camera 1's URL from TeamMARS-Telemetry's settings.
#   ./run_vision.sh                          # YOLO on camera 1
#   ./run_vision.sh --mode motion            # OpenCV motion detection instead
#   ./run_vision.sh --source rtsp://...      # any other stream
# Output: http://127.0.0.1:8090/stream.mjpg  (= default URL of camera panel 2)
cd "$(dirname "$0")"
if [[ " $* " != *" --source "* ]]; then
  INI="$HOME/.config/TeamMARS/TeamMARS-Telemetry.ini"
  URL=$(awk -F= '/^\[TeamMARSCameras\]/{s=1;next} /^\[/{s=0} s && $1=="url1"{print substr($0, index($0,"=")+1)}' "$INI" 2>/dev/null)
  if [ -z "$URL" ]; then
    echo "No --source given and Camera 1 has no URL in TeamMARS-Telemetry. Example: ./run_vision.sh --source rtsp://192.168.144.25:8554/main.264"
    exit 1
  fi
  # camera panels store USB cameras as usb:/dev/videoN -> OpenCV wants the number N
  case "$URL" in usb:/dev/video*) URL="${URL#usb:/dev/video}" ;; /dev/video*) URL="${URL#/dev/video}" ;; esac
  set -- --source "$URL" "$@"
fi
exec .venv/bin/python -I teammars_vision.py "$@"
