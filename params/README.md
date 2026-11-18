# Drone parameters (Holybro Pixhawk 6C, ArduCopter)

| File | What |
|---|---|
| `param_list_current.param` | The parameter list we were given |
| `param_list_safe.param` | Same list with 3 safety fixes (RTL on low battery, 14.8 V arming, 20 m fence ceiling) |
| `tools/param_sync.py` | Safe sync: checks DISARMED, backs up all params, writes only `--only` names, verifies read-back |

```bash
python3 -I tools/param_sync.py backup param_list_safe.param                 # read-only: backup + diff
python3 -I tools/param_sync.py apply  param_list_safe.param --only A,B,C    # write just these
```

Calibration and hardware-specific values (gyro offsets, RC ranges, hover throttle, device IDs) are never written.
Backups of the live drone stay on the ground-station PC (`~/QGroundControl/param-backups/`), not in git.
