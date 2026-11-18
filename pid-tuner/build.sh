#!/bin/bash
# Set up TeamMARS-PID-tuner: fetch ArduPilot Methodic Configurator v5.1.1, copy our changed files over it,
# install it in a venv (editable, so code changes apply on next launch).
#   WORK=~/MethodicConfigurator pid-tuner/build.sh
#   APPIMAGE=1 pid-tuner/build.sh     # also build the AppImage (teammars/build_appimage.sh)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$HOME/MethodicConfigurator}
[ -d "$WORK/.git" ] || git clone --depth 1 --branch v5.1.1 https://github.com/ArduPilot/MethodicConfigurator.git "$WORK"
cp -r "$HERE/amc/." "$WORK/"
cd "$WORK"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -e .
if [ "${APPIMAGE:-0}" = 1 ] && [ -x teammars/build_appimage.sh ]; then
  teammars/build_appimage.sh
fi
