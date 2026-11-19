#!/usr/bin/env python3
"""Dev/test only: a pretend ArduCopter that streams MAVLink to a ground station on this PC.

Lets us check TeamMARS-Telemetry's connected-state screens without a real drone.
Sends heartbeat, status, attitude, GPS, position, HUD and battery; serves a real parameter
file on request; answers mission and version requests. Never talks to real hardware.

    python fake_vehicle.py params/param_list_safe.param [--udp 127.0.0.1:14550]
"""

import argparse
import math
import time

from pymavlink import mavutil

M = mavutil.mavlink


def load_params(path):
    params = []
    for ln in open(path):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        n, v = ln.replace("\t", ",").split(",")[:2]
        params.append((n.strip(), float(v)))
    return params


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("params")
    ap.add_argument("--udp", default="127.0.0.1:14550")
    ap.add_argument("--lat", type=float, default=-35.363261)  # ArduPilot SITL default site (CMAC)
    ap.add_argument("--lon", type=float, default=149.165230)
    a = ap.parse_args()

    params = load_params(a.params)
    index = {n: i for i, (n, _) in enumerate(params)}
    mav = mavutil.mavlink_connection(f"udpout:{a.udp}", source_system=1, source_component=1)
    mav.mav.srcSystem, mav.mav.srcComponent = 1, 1
    print(f"fake ArduCopter -> udp {a.udp}, {len(params)} params")

    pending_params = []
    t0 = time.time()
    last_1hz = last_10hz = 0.0
    while True:
        now = time.time()
        t = now - t0
        # ---- incoming requests from the ground station
        while True:
            msg = mav.recv_match(blocking=False)
            if msg is None:
                break
            mt = msg.get_type()
            if mt == "PARAM_REQUEST_LIST":
                pending_params = list(range(len(params)))
            elif mt == "PARAM_REQUEST_READ":
                i = msg.param_index if msg.param_index >= 0 else index.get(msg.param_id, -1)
                if 0 <= i < len(params):
                    pending_params.insert(0, i)
            elif mt == "PARAM_SET":
                pid = msg.param_id
                if pid in index:
                    params[index[pid]] = (pid, msg.param_value)
                    pending_params.insert(0, index[pid])
            elif mt == "MISSION_REQUEST_LIST":
                mav.mav.mission_count_send(msg.get_srcSystem(), msg.get_srcComponent(), 0, msg.mission_type)
            elif mt == "COMMAND_LONG":
                if msg.command == M.MAV_CMD_REQUEST_MESSAGE and int(msg.param1) == M.MAVLINK_MSG_ID_AUTOPILOT_VERSION:
                    mav.mav.autopilot_version_send(
                        M.MAV_PROTOCOL_CAPABILITY_MAVLINK2 | M.MAV_PROTOCOL_CAPABILITY_PARAM_FLOAT | M.MAV_PROTOCOL_CAPABILITY_MISSION_INT,
                        (4 << 24) | (5 << 16) | (7 << 8) | 255, 0, 0, 0, b"\0" * 8, b"\0" * 8, b"\0" * 8, 0, 0, 0)
                mav.mav.command_ack_send(msg.command, M.MAV_RESULT_ACCEPTED)
        # ---- parameter download (fast but paced)
        for _ in range(min(40, len(pending_params))):
            i = pending_params.pop(0)
            n, v = params[i]
            mav.mav.param_value_send(n.encode(), v, M.MAV_PARAM_TYPE_REAL32, len(params), i)
        # ---- 1 Hz
        if now - last_1hz >= 1:
            last_1hz = now
            mav.mav.heartbeat_send(M.MAV_TYPE_QUADROTOR, M.MAV_AUTOPILOT_ARDUPILOTMEGA,
                                   M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | M.MAV_MODE_FLAG_STABILIZE_ENABLED, 5, M.MAV_STATE_STANDBY)
            sensors = 0x3FFFFFF
            mav.mav.sys_status_send(sensors, sensors, sensors, 120, 15900, 820, 92, 0, 0, 0, 0, 0, 0)
            mav.mav.gps_raw_int_send(int(now * 1e6), 3, int(a.lat * 1e7), int(a.lon * 1e7), 250000, 80, 120, 0, 0, 14)
            mav.mav.battery_status_send(0, M.MAV_BATTERY_FUNCTION_ALL, M.MAV_BATTERY_TYPE_LIPO, 2500,
                                        [3975, 3975, 3975, 3975] + [65535] * 6, 820, -1, -1, 92)
        # ---- 10 Hz
        if now - last_10hz >= 0.1:
            last_10hz = now
            roll, pitch, yaw = 0.08 * math.sin(t / 2), 0.05 * math.sin(t / 3), (t / 20) % (2 * math.pi)
            mav.mav.attitude_send(int(t * 1000), roll, pitch, yaw, 0, 0, 0.05)
            mav.mav.global_position_int_send(int(t * 1000), int(a.lat * 1e7), int(a.lon * 1e7), 250000, 0, 0, 0, 0,
                                             int(math.degrees(yaw) * 100))
            mav.mav.vfr_hud_send(0, 0, int(math.degrees(yaw)) % 360, 0, 0, 0)
        time.sleep(0.01)


if __name__ == "__main__":
    main()
