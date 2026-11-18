#!/bin/bash
# Build TeamMARS-Telemetry: fetch QGroundControl v5.1.5, copy our changed files over it, build.
# Needs Qt 6.11.1 (gcc_64) and the QGC build dependencies — see SETUP_LOG.md Steps 5-6.
#   WORK=~/QGroundControl QT=~/QGroundControl/Qt/6.11.1/gcc_64 telemetry/build.sh
#   APPIMAGE=1 telemetry/build.sh     # also package an AppImage
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$HOME/QGroundControl}
QT=${QT:-$WORK/Qt/6.11.1/gcc_64}
[ -d "$WORK/src/.git" ] || git clone --depth 1 --branch v5.1.5 https://github.com/mavlink/qgroundcontrol.git "$WORK/src"
cp -r "$HERE/qgc/." "$WORK/src/"
cmake -S "$WORK/src" -B "$WORK/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$QT"
cmake --build "$WORK/build" -j"$(nproc)"
if [ "${APPIMAGE:-0}" = 1 ]; then
  APPIMAGE_EXTRACT_AND_RUN=1 cmake --install "$WORK/build" --config Release
  ls -la "$WORK"/build/*.AppImage
fi
