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

## Step 7: Liquid-glass UI changes (visual only)

Design rules we followed:
- **No live blur or shader effects.** A real backdrop blur would re-blur the moving map and video every frame and cost responsiveness. The glass look comes from translucency, a specular gradient, a bright 1px rim and a bottom inner shadow, all plain Rectangles with near-zero GPU cost.
- **Safety colors are untouched.** Red, yellow, green and orange (warnings, failsafes, battery, GPS status) and alert colors are unchanged.
- **Nothing outside the UI changed.** No MAVLink, vehicle, parameter or flight-logic code was touched.

Files changed in `~/QGroundControl/src` (`git diff` shows everything):

| File | Change |
|---|---|
| `src/QmlControls/GlassBackground.qml` (new) | Reusable glass panel: tinted translucent body, top sheen, bright rim, bottom inner shadow |
| `src/QmlControls/CMakeLists.txt` | Registers `GlassBackground.qml` in the `QGroundControl.Controls` module |
| `src/QmlControls/QGCPalette.cc` | Glass palette. Dark ("Indoor") theme: deep-navy smoked glass (`#0e1626`, 70% translucent panels), sky-cyan accent (`#38bdf8`). Light ("Outdoor") theme: frosted white glass, cyan accent (`#0ea5e9`) |
| `src/Toolbar/FlyViewToolBar.qml` | One continuous glass strip behind the toolbar; the purple branding block now fades into the glass |
| `src/QmlControls/ToolStrip.qml` | Left tool strip gets a glass body |
| `src/FlyView/TelemetryValuesBar.qml` | Telemetry bar uses glass instead of a flat 75% box |
| `src/QmlControls/DropPanel.qml` | Pop-out panels use glass at 93% opacity so forms stay readable over the map |
| `src/QmlControls/QGCButton.qml` | Glossy sheen on all buttons |

Tip: the glass look is strongest in **Application Settings → General → Color Scheme → Indoor** (dark). Use **Outdoor** in direct sunlight.

## Step 8: Build

```bash
cd ~/QGroundControl
export PATH=$HOME/QGroundControl/.venv/bin:$PATH
cmake -S src -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH=$HOME/QGroundControl/Qt/6.11.1/gcc_64
cmake --build build -j10
```

## Step 9: Parameter file safety review

File: `~/Downloads/param_list_current.param` (Mission Planner format, 1019 params, ArduCopter quad X with 4S battery).
It was checked against the official ArduCopter 4.8 parameter metadata that QGC bundles (ranges, read-only flags, enum values).

**Automatic checks**
- 1018/1019 names are known. `GND_EFFECT_COMP` is not in the 4.8 metadata, and QGC will skip it if your firmware doesn't have it.
- 28 read-only or hardware-specific params are never written by QGC: sensor `*_DEV_ID`/`*_ID`, `BARO*_GND_PRESS`, `STAT_*`, `MIS_TOTAL`. That's correct: they belong to the board.
- "Out of range" hits are all **0 = disabled** defaults (`ATC_RAT_*_FF`, `*_FLTE`, `PSC_*_FLTD/FLTT`, `PSC_NE_VEL_FF`, `BRD_VSERVO_MIN`, `EK3_DRAG_BCOEF_Y`, `FENCE_TOTAL`, unused 3rd-IMU scales), plus ArduPilot's own default `ATC_RAT_YAW_FLTE=2`. They're harmless. The one real exception is `FENCE_ALT_MAX` (below).

**Safety flags (values left as-is; your call)**

| Param | Value | Why it matters | Suggested |
|---|---|---|---|
| `BATT_FS_LOW_ACT` | 0 (no action) | At 13.6 V (3.4 V/cell) nothing happens; only the critical level (13.2 V) forces a Land | 2 (RTL) |
| `BATT_ARM_VOLT` | 13.2 | Same as the critical voltage, so you can arm on a nearly empty 4S pack | ~14.8 |
| `FENCE_ALT_MAX` | 7 m | Below the documented minimum (10). Fence is off now, but if enabled it would breach at 7 m while `RTL_ALT_M` = 15 m, and RTL would climb straight into the fence | ≥ 20 m if you ever enable the fence |
| `FLTMODE1/2` | 9 (Land) | Low switch position is LAND, and Copter won't arm in Land, so you must switch to Loiter or AltHold to arm. That may be intentional | Info only |
| `FS_GCS_ENABLE` | 0 | Losing the QGC link does nothing. OK because the RC failsafe (`FS_THR_ENABLE`=3, Land) is on. Turn it on if you fly missions without RC | Info only |
| Rate PIDs | 0.135 defaults, `INS_HNTCH_ENABLE`=0 | Never autotuned, and no harmonic notch. This is the real way to get a sharper response, not GCS settings | Notch + AutoTune later |

Good: `ARMING_SKIPCHK`=0 (all checks on), EKF / vibration / crash / RC failsafes enabled, `SCHED_LOOP_RATE`=400, `BRD_SAFETY_DEFLT`=1.

**How to load it in QGC (with the drone connected)**
1. Connect over USB (SERIAL0, 115200) or the radio (SERIAL1, 57600). Wait for "Parameters loaded".
2. **Back up first:** Vehicle Configuration → Parameters → Tools → *Save to file* → `~/QGroundControl/params-backup-YYYY-MM-DD.params`.
3. Tools → *Load from file for review...* → choose `param_list_current.param`.
4. QGC shows **only the params that differ** from the drone, each with a checkbox. Review, untick anything you don't want, then *Apply*.
5. Reboot the flight controller (Tools → Reboot Vehicle) so INS, serial, CAN and similar settings take effect.

## Step 10: Safe parameter copy

`~/QGroundControl/param_list_safe.param` is identical to `~/Downloads/param_list_current.param` (left untouched) except:

| Param | Original | Safe copy |
|---|---|---|
| `BATT_FS_LOW_ACT` | 0 | 2 (RTL at low battery, 13.6 V) |
| `BATT_ARM_VOLT` | 13.2 | 14.8 (no arming on a nearly flat 4S pack) |
| `FENCE_ALT_MAX` | 7 | 20 (fence still disabled; no longer below `RTL_ALT_M` = 15) |

```bash
sed -e 's/^BATT_FS_LOW_ACT,.*/BATT_FS_LOW_ACT,2/' \
    -e 's/^BATT_ARM_VOLT,.*/BATT_ARM_VOLT,14.8/' \
    -e 's/^FENCE_ALT_MAX,.*/FENCE_ALT_MAX,20/' \
    ~/Downloads/param_list_current.param > ~/QGroundControl/param_list_safe.param
```
