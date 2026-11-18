#!/bin/bash
# Build TeamMARS-PID-tuner(DRONE) as a single Linux AppImage.
# Mirrors upstream CI (.github/workflows/build_windows_macos.yml, job build_linux) with TeamMARS branding.
# Usage: cd ~/MethodicConfigurator && teammars/build_appimage.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
APP=ardupilot_methodic_configurator
VERSION=$($PY -c "import ardupilot_methodic_configurator as m; print(m.__version__)")
OUT_NAME="TeamMARS-PID-tuner_${VERSION}_x86_64.AppImage"
APPDIR=teammars/build/AppDir
OUTDIR=teammars/dist

echo "== deps"; $PY -m pip install -q ".[linux_dist]"
git rev-parse HEAD | tr -d '\n' > git_hash.txt

echo "== PyInstaller"; PATH="$PWD/.venv/bin:$PATH" pyinstaller --noconfirm --clean linux/$APP.spec
echo "== verify frozen modules"; $PY scripts/verify_packaged_modules.py build/$APP/PYZ-00.pyz
echo "== smoke test"; (cd /tmp && MAVLINK_DIALECT=common env -u DISPLAY "$OLDPWD/dist/$APP/$APP" --version)

echo "== AppDir"; rm -rf "$APPDIR"; mkdir -p "$APPDIR" "$OUTDIR"
cp -R "dist/$APP" "$APPDIR/"
cp $APP/images/TeamMARS_icon.png "$APPDIR/teammars-pid-tuner.png"
cp linux/AppRun "$APPDIR/AppRun"; chmod +x "$APPDIR/AppRun"
cat > "$APPDIR/teammars-pid-tuner.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=TeamMARS-PID-tuner(DRONE)
Comment=TeamMARS ArduPilot configuration and PID tuning (based on ArduPilot Methodic Configurator)
Exec=$APP
Icon=teammars-pid-tuner
Categories=Utility;Science;
StartupWMClass=teamMARSPIDTuner
DESK

TOOL=teammars/build/appimagetool
if [ ! -x "$TOOL" ]; then
  wget -q "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage" -O "$TOOL"
  chmod +x "$TOOL"
fi
echo "== appimagetool"; ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUTDIR/$OUT_NAME"
ls -la "$OUTDIR/$OUT_NAME"; sha256sum "$OUTDIR/$OUT_NAME" | tee "$OUTDIR/$OUT_NAME.sha256"
