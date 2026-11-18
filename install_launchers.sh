#!/bin/bash
# Install the desktop launchers from this repo into ~/.local/share/applications (fills in your home path).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DEST="$HOME/.local/share/applications"
mkdir -p "$DEST"
for f in "$HERE"/telemetry/launchers/*.desktop "$HERE"/pid-tuner/launchers/*.desktop; do
  [ -e "$f" ] || continue
  sed "s#@HOME@#$HOME#g" "$f" > "$DEST/$(basename "$f")"
  echo "installed $(basename "$f")"
done
update-desktop-database "$DEST" 2>/dev/null || true
