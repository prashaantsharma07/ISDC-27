# TeamMARS-PID-tuner(DRONE) (ArduPilot Methodic Configurator 5.1.1)

`amc/` mirrors the ArduPilot Methodic Configurator source tree but holds **only the files we changed**
(plus our new files). The first commit adds the untouched upstream versions, so `git log -p pid-tuner/amc`
shows every change we made, in order.

Setup: `pid-tuner/build.sh` (clones tag `v5.1.1`, copies `amc/` over it, installs into a venv).

Rules we kept: backend untouched (MAVLink, uploads, parameter files, configuration sequence);
safety field colours keep their meaning; original authors credited (GPL-3.0).
