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

## Step 11: Build result and launchers

- The build finished with 0 errors: `~/QGroundControl/build/Release/QGroundControl`.
- First launch was clean, with no QML errors from the glass files (log: `custom-launch.log`).
- QGC is single-instance, so close one copy before opening the other.
- Launchers:
  - **QGroundControl Glass** (`~/.local/share/applications/qgroundcontrol-glass.desktop`) runs the custom build and **is now pinned in the dock**.
  - **QGroundControl (stock)** (`org.mavlink.qgroundcontrol.desktop`) is the original AppImage. It stays in the app menu as a fallback.
- The custom build loads Qt from `~/QGroundControl/Qt`, so don't delete that folder.
- To change the UI later: edit the QML in `~/QGroundControl/src`, then run `cmake --build ~/QGroundControl/build -j10` (incremental, takes a few minutes).

## Step 12: Drone backup and diff (read-only)

- Flight controller: Holybro Pixhawk 6C on `/dev/ttyACM0` (USB, 115200), sysid 1, ArduCopter. Confirmed **DISARMED**.
- Tool: `~/QGroundControl/tools/param_sync.py` (pymavlink in `~/QGroundControl/.venv`).
  - `backup` mode only reads.
  - `apply` writes only the params named in `--only`, refuses if the vehicle is armed, and verifies each write by read-back.
- Full backup of all 1030 drone params: `~/QGroundControl/param-backups/backup-backup-20261117-223826.param`.
- **Finding:** the file differs from the drone in **48** params, not 3. It's an older or other snapshot, not the drone's current state.

| Group | Params | Verdict |
|---|---|---|
| Sensor calibration | `INS_GYR*OFFS_*`, `INS_GYR*_CALTEMP`, `AHRS_TRIM_X/Y` | **Never write.** These would replace this board's current calibration and level trim with stale values (drift, hover tilt) |
| RC calibration | `RC1–4_MIN/MAX/TRIM` | **Never write.** They would replace the measured stick ranges with generic 1000/2000. The throttle low point would be wrong, which affects arming and the throttle failsafe |
| Learned hover throttle | `MOT_THST_HOVER` 0.479 → 0.246 | **Don't write.** It would halve the learned hover value, so altitude hold sags or surges until it relearns |
| Serial port | `SERIAL5_PROTOCOL` 2 → -1 | **Don't write.** It would switch off a live MAVLink port (115200) the drone currently uses |
| Battery failsafe | `BATT_FS_VOLTSRC` 1 → 0, `BATT_CRT_MAH` 675 → 0 | **Don't write.** These would switch from sag-compensated voltage to raw voltage and remove the mAh critical failsafe. Both weaken protection |
| Safety fixes | `BATT_FS_LOW_ACT` 0 → 2, `BATT_ARM_VOLT` 13.6 → 14.8, `FENCE_ALT_MAX` 7 → 20 | **Write** |
| Flight behaviour | `LOIT_SPEED_MS` 6 → 12.5, `LAND_ALT_LOW_M` 2 → 10, `LAND_SPD_HIGH_MS` 6 → 0 | Your choice. Loiter speed doubles; final landing descent starts higher |
| Telemetry rates | `MAV1_*` → 0, `MAV3_*` → 2–4 Hz | Your choice. QGC requests its own rates anyway |
| Declination | `COMPASS_DEC` → 0 | Harmless. `COMPASS_AUTODEC`=1 recomputes it from GPS |

## Step 13: Write approved params (done 2026-11-17)

You chose: safety fixes + flight behaviour. Telemetry rates, declination and **all calibration were left untouched**.

```bash
cd ~/QGroundControl
.venv/bin/python -I tools/param_sync.py apply param_list_safe.param \
  --only BATT_FS_LOW_ACT,BATT_ARM_VOLT,FENCE_ALT_MAX,LOIT_SPEED_MS,LAND_ALT_LOW_M,LAND_SPD_HIGH_MS
```

| Param | Before | After | Read-back |
|---|---|---|---|
| `BATT_ARM_VOLT` | 13.6 | 14.8 | OK |
| `BATT_FS_LOW_ACT` | 0 | 2 (RTL) | OK |
| `FENCE_ALT_MAX` | 7 | 20 | OK |
| `LAND_ALT_LOW_M` | 2 | 10 | OK |
| `LAND_SPD_HIGH_MS` | 6 | 0 (uses `WP_SPD_DN`) | OK |
| `LOIT_SPEED_MS` | 6 | 12.5 | OK |

- The script re-checked DISARMED right before writing. A second pre-write backup is at `param-backups/backup-apply-20261117-223928.param`.
- No reboot was needed for these params. ArduPilot saves them as soon as they're set.
- **Undo** (restores the exact pre-change values):
  ```bash
  .venv/bin/python -I tools/param_sync.py apply param-backups/backup-backup-20261117-223826.param \
    --only BATT_FS_LOW_ACT,BATT_ARM_VOLT,FENCE_ALT_MAX,LOIT_SPEED_MS,LAND_ALT_LOW_M,LAND_SPD_HIGH_MS
  ```
- Before flying: you need a pack charged above **14.8 V** to arm. On the first flight, check that Loiter at 12.5 m/s feels controllable.

## Pending

- [ ] Optional: `sudo apt remove modemmanager`, so the flight controller's USB port is free immediately on plug-in
- [ ] Later, for sharper flight response: set up the harmonic notch filter, then run AutoTune

---

## Step 14 — PID tuner: ArduPilot Methodic Configurator (2026-11-18)

- Tried PIDscope 26.10.1 first, then **removed it** (it is a Betaflight blackbox analyser, not for ArduPilot). Deleted `~/PIDscope`, its launcher and its dock pin.
- Chose **ArduPilot Methodic Configurator v5.1.1**: official ArduPilot project, GPL-3.0, pure Python, supports Pixhawk 6C / ArduCopter and walks through the full tuning sequence (notch filter → initial PIDs → AutoTune) with a backup at every step.
- Installed **from source** so it can be modified:
  ```bash
  git clone --depth 1 --branch v5.1.1 https://github.com/ArduPilot/MethodicConfigurator.git ~/MethodicConfigurator
  cd ~/MethodicConfigurator && python3 -m venv .venv && .venv/bin/pip install -e .
  ```
  Editable install: changes to `~/MethodicConfigurator/ardupilot_methodic_configurator/*.py` take effect on next launch, no rebuild.
- Launcher `~/.local/share/applications/ardupilot-methodic-configurator.desktop` ("ArduPilot Tuner", `StartupWMClass=arduPilotMethodicConfigurator`), pinned to the dock after QGroundControl Glass.
- Test launch OK (Workflow window opened). No parameters were read or written.
- Note: close QGC before connecting — only one program can hold `/dev/ttyACM0`.

---

## Step 15 — Rebrand + liquid-glass UI: TeamMARS-PID-tuner(DRONE) (2026-11-18)

All work is on git branch `teammars-glass` in `~/MethodicConfigurator` (base: upstream tag `v5.1.1`). Details: `~/MethodicConfigurator/teammars/README.md`.

1. **Name** → `TeamMARS-PID-tuner(DRONE)` in every window title, dialog text, About box, window class (`teamMARSPIDTuner`) and launcher. Original authors still credited in About (GPL requirement).
2. **New theme** `frontend_tkinter_glass_theme.py` replaces the old grey `alt` theme everywhere (4 call sites):
   - bottle green `#006A4E` glass buttons, caption chips, table headings, selected tab;
   - bone `#E3DAC9` surface with rounded glass cards (white rim + top sheen);
   - vermilion `#E34234` only as a hint: keyboard-focus rim, selected-tab underline, progress bars;
   - frosted `#FBF8F2` fields and lists; hyperlinks bottle green.
3. **Safety kept**: parameter field colours (default / below-limit / above-limit / calibration / read-only) keep their meaning; fields are not image-based so they always show.
4. **Speed kept**: no blur or transparency — glass images are rendered once at start-up.
5. **Backend untouched**: no change to MAVLink, uploads, parameter files or the configuration sequence.
6. New icon `images/TeamMARS_icon.png` (glass tile with a PID step-response curve); launcher `teammars-pid-tuner.desktop` replaces the old one in the dock.
7. Tests updated for the new name/icon; test suite run (screenshot-based GUI tests skipped: need `gnome-screenshot`).
8. Undo (reversible): `cd ~/MethodicConfigurator && git stash -u` — bring back with `git stash pop`. Changes are not committed yet.

---

## Step 16 — Tests + shareable Linux AppImage (2026-11-18)

- **Tests**: 9,462 passed. 20 failures investigated: tests expecting the old name/theme were updated; theme code hardened so it never crashes on test stand-ins; 2 failed only when run in parallel (pass serially); 4 fail identically on untouched upstream v5.1.1 (component-inference acceptance tests, PyInstaller-archive test) — not caused by our changes.
- **Build**: `cd ~/MethodicConfigurator && teammars/build_appimage.sh` (same recipe as upstream CI: PyInstaller → frozen-module check → smoke test → appimagetool 1.9.1), with TeamMARS name, icon and window class.
- **Output**: `~/TeamMARS-share/` — `TeamMARS-PID-tuner_5.1.1_x86_64.AppImage` (67 MB), its `.sha256`, and `HOW_TO_RUN.txt` for teammates. Send the whole folder (Drive / pen drive / Telegram).
- Verified: AppImage launches standalone with the glass theme and TeamMARS title.
- Works on Ubuntu 24.04+ (built on 24.04). Teammates on older Linux or Windows need a build on GitHub Actions instead.
- GPL: whoever receives the app may ask for the source — share `~/MethodicConfigurator` (branch `teammars-glass`) if asked.

---

## Step 17 — TeamMARS-Telemetry (rebranded glass QGC) (2026-11-18)

Same QGroundControl 5.1.5 code and behaviour; only name, icon and colours changed. Git branch `teammars-telemetry` in `~/QGroundControl/src` (uncommitted).

| Change | Where |
|---|---|
| Name `TeamMARS-Telemetry`, org `TeamMARS`, package `com.teammars.telemetry` | `cmake/CustomOptions.cmake` |
| Stable build ON (drops "Daily" from the name, same as the official release) | `cmake/CustomOptions.cmake` |
| MARS team logo (round, transparent) as window icon, toolbar logo and dock icon | `resources/TeamMARS/`, `qgcresources.qrc`, `QGCApplication.cc`, 3 toolbar QML files |
| Toolbar logo button can show a PNG logo | `QGCToolBarButton.qml` |
| Palette: bone surfaces, bottle-green buttons/highlights, vermilion tool-strip hover | `QGCPalette.cc` |

Kept on purpose: all status/warning colours (green/yellow/orange/red, alerts, map trajectory). "Disconnected" toolbar colour is neutral charcoal so it can never be mistaken for green "Ready to fly".

- Build: `cmake --build build -j10` → `~/QGroundControl/build/Release/TeamMARS-Telemetry`.
- Settings carried over from the glass QGC to `~/.config/TeamMARS/TeamMARS-Telemetry.ini`; logs/missions now save to `~/Documents/TeamMARS-Telemetry`.
- Dock: `teammars-telemetry.desktop` replaces `qgroundcontrol-glass.desktop`. Stock QGC AppImage still in the app menu.
- Logo files: `~/TeamMARS-brand/` (original + round PNGs 32–512 px).
- Test: launched, MARS logo in toolbar and window, colours applied; not yet connected to the drone.

---

## Step 18 — MARS logo on the PID tuner too (2026-11-18)

- `ardupilot_methodic_configurator/images/TeamMARS_icon.png` replaced with the round MARS logo (old generated icon kept as `teammars/old_generated_icon.png`). Window icon and dock icon both use it.
- AppImage rebuilt and `~/TeamMARS-share/` refreshed (new `.sha256`). Re-send this version to the team.

---

## Step 19 — TeamMARS-Telemetry AppImage for the team (2026-11-18)

- Scalable icon: `resources/TeamMARS/TeamMARSLogo.svg` (MARS logo) replaces the QGC SVG in the package.
- Packaged with QGC's own recipe (linuxdeploy + appimagetool, pinned SHA-256 downloads):
  ```bash
  cd ~/QGroundControl && cmake --build build -j10 && cmake --install build --config Release
  ```
  → `build/TeamMARS-Telemetry-x86_64.AppImage` (186 MB, Qt and libraries bundled).
- Tested standalone: starts, MARS logo in toolbar, TeamMARS colours.
- `~/TeamMARS-share/` now holds both apps + `.sha256` files + `HOW_TO_RUN.txt` (242 MB total) — send the whole folder.
- Works on Ubuntu 24.04+ (built on 24.04).

---

## Step 20 — PID tuner dock icon fix (2026-11-18)

GNOME caches launcher icons by file path, so overwriting `TeamMARS_icon.png` in place kept showing the old icon.
The launcher now points to a new file, `~/TeamMARS-brand/teammars-pid-tuner-icon.png` (MARS logo), and was re-pinned.

---

## Step 21 — GitHub repository ISDC-27 (2026-11-18)

- https://github.com/prashaantsharma07/ISDC-27 — one commit per step, in the order the work was done.
- `telemetry/qgc/` and `pid-tuner/amc/` hold only the files we changed; the first commit for each adds the untouched
  upstream files, so every later diff shows exactly what we changed. Build scripts re-apply them to a fresh upstream clone.
- Downloads: GitHub Release with both AppImages and their `.sha256` files.
- Commits use the GitHub no-reply e-mail; drone parameter backups stay on this PC.

---

## Step 22 — Pilot-first Fly View layout (2026-11-19)

Requested: compass/heading on the left edge in the middle, connection bar at the bottom of the map,
takeoff/land just above it, and everything that appears after connecting re-placed so nothing feels off-centre.

| Element | Stock QGC | TeamMARS-Telemetry |
|---|---|---|
| Status / connection bar | top | **bottom** of the map |
| Takeoff / Land / RTL / Pause strip | vertical, top-left | **horizontal, centred just above the bar** |
| Attitude + compass | bottom-right | **left edge, vertically centred** |
| Telemetry values | bottom-right | **top, centred** |
| Map scale | next to the tool strip | top-left corner |
| Bar pop-ups (battery, GPS, flight modes, menu) | drop down | **open upwards** from the bar |
| Tool-strip pop-ups (Actions…) | open to the right | **open upwards**, centred on the button |
| Guided "slide to confirm" + hint | top bar | bottom bar, hint floats above the strip |

Files: `FlyView.qml`, `FlyViewWidgetLayer.qml`, `FlyViewToolBar.qml`, `ToolStrip.qml` (new horizontal mode),
`ToolStripDropPanel.qml` (opens upwards), `MainWindow.qml` (drawer direction), `FlightModeMenuIndicator.qml`.
Plan View is unchanged (bar on top, vertical tool strip). Checked connected and disconnected with a simulated
ArduCopter (`devtools/fake_vehicle.py`): mode list, battery pop-up, takeoff confirm, altitude slider.

---

## Step 23 — Optional dual camera panels (2026-11-19)

- New **Cameras** button in the tool strip toggles two camera boxes on the right edge (top + bottom). Off by default.
- Each box: any FFmpeg stream (`rtsp://`, `udp://`, `http://` MJPEG/HLS, files); **Flip** (upside-down), **Mirror**,
  **Swap** top/bottom, **Size** (3 sizes, double-click to enlarge), **URL** editor. All remembered.
- Low-latency playback, no audio, auto-reconnect every 3 s; vehicle panels and the altitude slider move aside.
- Uses Qt Multimedia, separate from QGC's GStreamer video, so it cannot disturb the main video or telemetry.
- Fix: Qt's VA-API path swapped red/blue on MJPEG (Intel GPU). Qt Multimedia now decodes in software
  (`main.cc`, override with `QT_FFMPEG_DECODING_HW_DEVICE_TYPES`). Whole app with both feeds live: ~30 % of one core.
- Settings: `[TeamMARSCameras]` in `~/.config/TeamMARS/TeamMARS-Telemetry.ini`.

---

## Step 24 — TeamMARS Vision: YOLO / OpenCV on the camera (2026-11-19)

- `~/TeamMARS-vision/` — `setup.sh` (CPU PyTorch + Ultralytics + OpenCV venv, ~1.6 GB), `run_vision.sh`
  (uses Camera 1's URL automatically), launcher "TeamMARS Vision (YOLO)".
- Modes: `yolo` (80 object classes), `motion`, `edges`, `none`. Output MJPEG on `http://127.0.0.1:8090/stream.mjpg`
  = camera panel 2's default.
- Measured on this laptop (i7-10750H, CPU only): **YOLO11n 27 ms/frame, ~18.6 fps**, test frame: 1 bus + 3 people.
- Separate process on purpose: AI can never freeze telemetry or the map.
- Tested end to end with an ffmpeg fake camera (H.264 over UDP) → panel 1 raw, panel 2 YOLO.

---

## Step 25 — Bigger camera feeds (v2.1, 2026-11-19)

- Each camera panel is now **half the map height** (CAM 1 top half, CAM 2 bottom half); width unchanged ("Size" still changes it).
- New per-panel **Fill / Fit** button: Fill (default) makes the picture fill the tall panel by trimming the sides; Fit shows the whole frame.
- Map compensation: the camera column counts as a full-height right inset, and the telemetry bar, Takeoff strip and
  vehicle warnings are centred in the map area **left of the cameras**.
