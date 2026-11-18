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
