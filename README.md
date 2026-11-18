<p align="center"><img src="brand/MARS_logo_256.png" width="160" alt="TeamMARS logo"></p>

# ISDC-27 — TeamMARS ground software

Two TeamMARS apps for our drone (Holybro Pixhawk 6C, ArduCopter), built on open-source ArduPilot tools
with a liquid-glass UI in **bottle green, bone and a hint of vermilion**.

## Download

**➡ [Latest release](https://github.com/prashaantsharma07/ISDC-27/releases/latest)** — Linux x86_64, Ubuntu 24.04 or newer.

| App | File | Based on |
|---|---|---|
| **TeamMARS-Telemetry** — ground control & telemetry | `TeamMARS-Telemetry_5.1.5_x86_64.AppImage` | QGroundControl 5.1.5 |
| **TeamMARS-PID-tuner(DRONE)** — setup & PID tuning | `TeamMARS-PID-tuner_5.1.1_x86_64.AppImage` | ArduPilot Methodic Configurator 5.1.1 |

Run: download → right-click → Properties → Permissions → *Allow executing file as program* → double-click.
Details and fixes for common problems: [`share/HOW_TO_RUN.txt`](share/HOW_TO_RUN.txt).

## What we changed (and what we did not)

- **Changed:** app names, MARS team logo as icon, glass look and colours.
- **Not changed:** flight logic, MAVLink, parameter uploads, configuration steps, status/warning colours.
  The "Disconnected" bar is neutral charcoal so it can never look like green "Ready to fly".
- **Drone:** 6 safety/behaviour parameters set after review — see [`params/`](params/) and SETUP_LOG Steps 9–13.

## Repository layout

| Folder | Contents |
|---|---|
| [`telemetry/qgc/`](telemetry/qgc/) | Only the QGroundControl files we changed or added |
| [`pid-tuner/amc/`](pid-tuner/amc/) | Only the Methodic Configurator files we changed or added |
| [`params/`](params/) | Parameter lists and the safe sync tool |
| [`brand/`](brand/) | MARS logo, original and round icon sizes |
| [`share/`](share/) | Instructions shipped with the downloads |
| [`SETUP_LOG.md`](SETUP_LOG.md) | Every step, in order |

The first commit for each app adds the **untouched upstream files**, so each later commit's diff shows
exactly what we changed. Read the history with `git log --reverse -p`.

## Rebuild from source

```bash
telemetry/build.sh            # APPIMAGE=1 telemetry/build.sh to also package it
pid-tuner/build.sh            # APPIMAGE=1 pid-tuner/build.sh to also package it
./install_launchers.sh        # dock / app-menu launchers
```

## Credits and licence

- [QGroundControl](https://github.com/mavlink/qgroundcontrol) — Dronecode / QGroundControl developers (GPL-3.0 option of its dual licence)
- [ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator) — Amilcar do Carmo Lucas and ArduPilot.org (GPL-3.0)

Our changes are released under the same GPL-3.0 terms — see [`LICENSE`](LICENSE).
