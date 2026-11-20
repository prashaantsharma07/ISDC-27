#!/bin/bash
# Start TeamMARS object detection and open it in the browser (Linux / macOS).
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "Run ./setup.sh first"; exit 1; }
URL="http://127.0.0.1:8765"
( for i in $(seq 1 120); do curl -s "$URL/api/status" >/dev/null 2>&1 && break; sleep 1; done
  if command -v xdg-open >/dev/null; then xdg-open "$URL"; else open "$URL"; fi ) >/dev/null 2>&1 &
exec "$PY" -I server.py
