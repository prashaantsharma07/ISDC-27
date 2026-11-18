# QGroundControl Migration Log (replacing Mission Planner)

Machine: Ubuntu 24.04.5 LTS, x86_64, GNOME on Wayland. User is already in the `dialout` group, so serial/USB telemetry works.

---

## Step 1: Choose the version (2026-11-17)

- Checked https://github.com/mavlink/qgroundcontrol/releases.
- Stable tags: v5.0.4 … v5.1.5, plus a rolling `daily` build.
- **Chosen: v5.1.5**, the latest *stable* release.
  - We skipped `daily` because untested builds have no place on a flying vehicle.
  - The `QGroundControl-x86_64.AppImage` asset matches this machine (x86_64, glibc on Ubuntu 24.04).
  - QGC 5.x fully supports ArduPilot (ArduCopter/ArduPlane) over MAVLink, so it can take over from Mission Planner.

## Step 2: Download to home

```bash
mkdir -p ~/QGroundControl
cd ~/QGroundControl
curl -fL -o QGroundControl-x86_64.AppImage \
  https://github.com/mavlink/qgroundcontrol/releases/download/v5.1.5/QGroundControl-x86_64.AppImage
chmod +x QGroundControl-x86_64.AppImage
```

- Size: 195,332,600 bytes
- SHA-256: `9a47e4cf269d9e4f897f582f6b19aa7ebf1e9e67c9d68a532a45b541354bc344`
- AppImage needs FUSE 2. `libfuse2t64` was already installed.

## Step 3: Taskbar (dock) icon

1. Copied the official icon out of the AppImage: `~/QGroundControl/QGroundControl.svg`
2. Created the launcher `~/.local/share/applications/org.mavlink.qgroundcontrol.desktop`:
   ```ini
   [Desktop Entry]
   Type=Application
   Name=QGroundControl
   GenericName=Ground Control Station
   Icon=/home/prashaant/QGroundControl/QGroundControl.svg
   Exec=/home/prashaant/QGroundControl/QGroundControl-x86_64.AppImage
   Terminal=false
   Categories=Utility;
   StartupWMClass=QGroundControl
   ```
3. Pinned it to the GNOME dock by appending it to `org.gnome.shell favorite-apps` with `gsettings`.

## Step 4: First launch check

- Ran the AppImage for 12 seconds. It started normally (output saved in `first-launch.log`).
- The only warning was `Error loading ... localization for "en_IN"`. This is harmless: QGC falls back to English.

## Step 5: Get the source for the custom build

The UI is compiled into the binary as Qt resources, so a visual rework needs a build from source. We used the exact same tag (v5.1.5) as the AppImage.

```bash
cd ~/QGroundControl
git clone --depth 1 --branch v5.1.5 --recurse-submodules --shallow-submodules \
  https://github.com/mavlink/qgroundcontrol.git src
```

## Step 6: Toolchain

- **Qt 6.11.1** (the version pinned in `src/.github/build-config.json`) was installed per-user with aqtinstall into `~/QGroundControl/Qt` (1.9 GB):
  ```bash
  python3 -m venv ~/QGroundControl/.venv
  ~/QGroundControl/.venv/bin/pip install aqtinstall ninja
  ~/QGroundControl/.venv/bin/aqt install-qt linux desktop 6.11.1 linux_gcc_64 -O ~/QGroundControl/Qt \
    -m qtgraphs qtlocation qtpositioning qtspeech qtmultimedia qtserialport qtimageformats \
       qtshadertools qtconnectivity qtquick3d qtsensors qtscxml qtwebsockets qthttpserver
  ```
- **System build libraries** (needs sudo: X11/xcb headers, GStreamer dev and plugins for video, ninja, mold, ccache, patchelf):
  ```bash
  sudo apt-get install -y libatspi2.0-dev libgtk-3-dev libxcb-cursor-dev libxcb-glx0-dev \
    libxcb-icccm4-dev libxcb-image0-dev libxcb-keysyms1-dev libxcb-present-dev \
    libxcb-render-util0-dev libxcb-shape0-dev libxcb-sync-dev libxcb-util-dev \
    libxcb-xfixes0-dev libxcb-xinerama0-dev libxcb-xkb-dev libxkbcommon-x11-dev \
    libgstreamer1.0-dev libgstreamer-plugins-bad1.0-dev libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    gstreamer1.0-rtsp gstreamer1.0-qt6 libpipewire-0.3-dev ninja-build mold ccache patchelf
  ```
