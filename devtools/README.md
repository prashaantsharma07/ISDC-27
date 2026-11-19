# Dev tools

`fake_vehicle.py` — a pretend ArduCopter for testing TeamMARS-Telemetry **without a drone**.
It streams heartbeat, attitude, GPS, battery and serves a real parameter file over UDP to 127.0.0.1:14550.

```bash
python3 -I devtools/fake_vehicle.py params/param_list_safe.param
```

Test camera without a drone (H.264 over UDP, like most drone cameras):

```bash
ffmpeg -re -loop 1 -i some.jpg -vf scale=1280:-2,format=yuv420p -c:v libx264 -preset ultrafast -tune zerolatency -f mpegts udp://127.0.0.1:5600
```
