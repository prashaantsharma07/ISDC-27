# TeamMARS-Telemetry (QGroundControl 5.1.5)

`qgc/` mirrors the QGroundControl source tree but holds **only the files we changed** (plus our new files).
The first commit that touches a file adds the untouched upstream version, so `git log -p telemetry/qgc`
shows every change we made, in order.

Build: `telemetry/build.sh` (clones tag `v5.1.5`, copies `qgc/` over it, builds with CMake/Ninja).

Rules we kept: no change to flight logic, MAVLink, parameters or safety colours — only name, icon and look.
