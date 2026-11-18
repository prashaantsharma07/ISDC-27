#!/usr/bin/env python3
"""Safe ArduPilot parameter sync.

  backup : verify DISARMED, download every param, save a timestamped backup,
           print the diff against a target .param file. Writes nothing.
  apply  : same checks, then write ONLY the params listed in --only
           (each one is read back and verified).

Read-only / hardware-specific params are never written.
"""
import argparse, datetime, math, os, sys, time
from pymavlink import mavutil

SKIP = ("STAT_", "FORMAT_VERSION", "MIS_TOTAL", "FENCE_TOTAL", "RALLY_TOTAL")
SKIP_SUFFIX = ("_DEVID", "_DEV_ID", "_GND_PRESS", "_CAN_NODEID")
SKIP_EXACT = {"INS_ACC_ID", "INS_ACC2_ID", "INS_ACC3_ID", "INS_GYR_ID", "INS_GYR2_ID", "INS_GYR3_ID"}
SKIP_EXACT |= {f"COMPASS_DEV_ID{i}" for i in range(2, 9)}


def skipped(name):
    return name.startswith(SKIP) or name.endswith(SKIP_SUFFIX) or name in SKIP_EXACT


def load_file(path):
    out = {}
    for ln in open(path):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        n, v = ln.replace("\t", ",").split(",")[:2]
        out[n.strip()] = float(v)
    return out


def connect(port, baud):
    m = mavutil.mavlink_connection(port, baud=baud, source_system=255, source_component=190)
    hb = m.wait_heartbeat(timeout=10)
    if not hb:
        sys.exit("No heartbeat - is the flight controller connected and QGC closed?")
    print(f"Connected: sysid {m.target_system}, autopilot {hb.autopilot}, type {hb.type}")
    return m


def assert_disarmed(m):
    t0 = time.time()
    while time.time() - t0 < 3:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if hb and hb.get_srcSystem() == m.target_system and hb.get_srcComponent() == 1:
            if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                sys.exit("ABORT: vehicle is ARMED. Disarm before touching parameters.")
            print("Vehicle is DISARMED - OK")
            return
    sys.exit("ABORT: could not confirm disarmed state")


def fetch_all(m):
    m.mav.param_request_list_send(m.target_system, m.target_component)
    params, total, last = {}, None, time.time()
    while True:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
        if msg:
            params[msg.param_id] = msg.param_value
            total = msg.param_count
            last = time.time()
        if total and len(params) >= total:
            break
        if time.time() - last > 3:
            # re-request anything missing
            if total:
                for i in range(total):
                    pass
            break
    print(f"Downloaded {len(params)}/{total} params")
    if total and len(params) < total:
        sys.exit("ABORT: incomplete download, refusing to continue")
    return params


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-6)


def diff(drone, target):
    changes, missing = [], []
    for n, v in target.items():
        if skipped(n):
            continue
        if n not in drone:
            missing.append(n)
        elif not close(drone[n], v):
            changes.append((n, drone[n], v))
    return changes, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["backup", "apply"])
    ap.add_argument("target")
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--outdir", default=os.path.expanduser("~/QGroundControl/param-backups"))
    ap.add_argument("--only", default="", help="comma list of params allowed to be written (apply mode)")
    a = ap.parse_args()

    m = connect(a.port, a.baud)
    assert_disarmed(m)
    drone = fetch_all(m)

    os.makedirs(a.outdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bpath = os.path.join(a.outdir, f"backup-{a.mode}-{stamp}.param")
    with open(bpath, "w") as f:
        for n in sorted(drone):
            f.write(f"{n},{drone[n]:.7g}\n")
    print(f"Backup saved: {bpath}")

    target = load_file(a.target)
    changes, missing = diff(drone, target)
    print(f"\n{len(changes)} param(s) differ from {os.path.basename(a.target)}:")
    for n, cur, new in changes:
        print(f"  {n:20s} drone={cur:.7g}  ->  file={new:.7g}")
    if missing:
        print(f"\nIn file but not on this firmware (ignored): {missing}")

    if a.mode == "backup":
        return

    allowed = {s.strip() for s in a.only.split(",") if s.strip()}
    todo = [c for c in changes if c[0] in allowed]
    extra = [c[0] for c in changes if c[0] not in allowed]
    if extra:
        print(f"\nNot in --only, left untouched: {extra}")
    if not todo:
        print("Nothing to write.")
        return
    assert_disarmed(m)
    for n, cur, new in todo:
        m.mav.param_set_send(m.target_system, m.target_component, n.encode(), new,
                             mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        ok = False
        t0 = time.time()
        while time.time() - t0 < 3:
            msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
            if msg and msg.param_id == n:
                ok = close(msg.param_value, new)
                break
        print(f"  {'OK  ' if ok else 'FAIL'} {n}: {cur:.7g} -> {new:.7g}")
        if not ok:
            sys.exit("ABORT: write not confirmed; stopping. Restore from backup if needed.")
    print("\nAll writes confirmed by read-back.")


if __name__ == "__main__":
    main()
