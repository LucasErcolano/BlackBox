"""Final forensic pipeline — runs all 5 demo bags end-to-end.

Per bag: extract minimal artifacts -> managed-agents session -> stream events
-> parse report -> render PDF. Writes everything under data/final_runs/<bag>/.

Designed to be idempotent per bag: if <bag>/analysis.json already exists the
bag is skipped. Override with FORCE=1.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
from dotenv import load_dotenv

load_dotenv()

ROOT = Path("/home/hz/Desktop/BlackBox")
OUT_ROOT = ROOT / "data" / "final_runs"
MEMORY_DIR = OUT_ROOT / ".memory"
OUT_ROOT.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "src"))

from anthropic import Anthropic  # noqa: E402
from rosbags.highlevel import AnyReader  # noqa: E402

from black_box.analysis.managed_agent import (  # noqa: E402
    ForensicAgent,
    ForensicAgentConfig,
    _strip_json_fences,
    _extract_text,
)
from black_box.analysis.schemas import PostMortemReport  # noqa: E402
from black_box.memory import MemoryStack  # noqa: E402
from black_box.reporting.pdf_report import build_report  # noqa: E402

try:
    import cv2
except Exception:
    cv2 = None

# Global budget
GLOBAL_BUDGET_USD = 20.0
PER_BAG_WALL_CLOCK_S = 15 * 60
FRAME_MAX_W = 800
FRAME_MAX_H = 600


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Cost tracking (reads data/costs.jsonl tail)
# ---------------------------------------------------------------------------
COSTS_FILE = ROOT / "data" / "costs.jsonl"


def cost_file_pos() -> int:
    return COSTS_FILE.stat().st_size if COSTS_FILE.exists() else 0


def cost_since(pos: int) -> float:
    if not COSTS_FILE.exists():
        return 0.0
    total = 0.0
    with open(COSTS_FILE, "rb") as f:
        f.seek(pos)
        for line in f:
            try:
                entry = json.loads(line)
                total += float(entry.get("usd_cost", 0.0) or 0.0)
            except Exception:
                pass
    return total


# ---------------------------------------------------------------------------
# Image resize helper
# ---------------------------------------------------------------------------
def _resize_and_jpeg(img: np.ndarray, max_w: int = FRAME_MAX_W, max_h: int = FRAME_MAX_H) -> bytes | None:
    if cv2 is None or img is None:
        return None
    h, w = img.shape[:2]
    scale = min(max_w / max(w, 1), max_h / max(h, 1), 1.0)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    return buf.tobytes() if ok else None


# ---------------------------------------------------------------------------
# Telemetry CSV writer helpers
# ---------------------------------------------------------------------------
def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# Bag extraction recipes
# ---------------------------------------------------------------------------
def extract_sanfer(out_dir: Path) -> dict:
    """Sanfer: 3 small bags (sensors/diagnostics/dataspeed) + sparse frames from cam-lidar.

    Pull full RTK telemetry, full GPS, subsampled IMU + throttle + steering,
    all diagnostic status strings. Frames: ~1 fps across the 1hr session.
    """
    base = Path("/mnt/hdd/sanfer_sanisidro")
    sensors = base / "2_sensors.bag"
    diag = base / "2_diagnostics.bag"
    dataspeed = base / "2_dataspeed.bag"
    camlidar = base / "2_cam-lidar.bag"

    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    artifacts: list[str] = []

    # ---- 2_sensors.bag: ublox RTK + IMU ---------------------------------
    log("  extracting RTK telemetry from 2_sensors.bag ...")
    ublox_rover_navpvt: list[list] = []
    ublox_rover_navstatus: list[list] = []
    ublox_rover_navrelpos: list[list] = []
    ublox_mb_navpvt: list[list] = []
    ublox_mb_navstatus: list[list] = []
    imu_rows: list[list] = []  # heavy subsampled

    with AnyReader([sensors]) as r:
        start_ns = int(r.start_time)
        wanted_topics = {
            "/ublox_rover/navpvt",
            "/ublox_rover/navstatus",
            "/ublox_rover/navrelposned",
            "/ublox_moving_base/navpvt",
            "/ublox_moving_base/navstatus",
            "/imu/data",
        }
        wanted_conns = [c for c in r.connections if c.topic in wanted_topics]
        imu_step = 0
        for conn, t_ns, raw in r.messages(connections=wanted_conns):
            try:
                msg = r.deserialize(raw, conn.msgtype)
            except Exception:
                continue
            rel_s = (t_ns - start_ns) / 1e9
            if conn.topic == "/ublox_rover/navpvt":
                ublox_rover_navpvt.append([
                    f"{rel_s:.3f}",
                    getattr(msg, "fixType", ""),
                    getattr(msg, "flags", ""),
                    getattr(msg, "numSV", ""),
                    f"{getattr(msg, 'lat', 0)/1e7:.7f}",
                    f"{getattr(msg, 'lon', 0)/1e7:.7f}",
                    getattr(msg, "hAcc", ""),
                    getattr(msg, "vAcc", ""),
                ])
            elif conn.topic == "/ublox_rover/navstatus":
                ublox_rover_navstatus.append([
                    f"{rel_s:.3f}",
                    getattr(msg, "gpsFix", ""),
                    getattr(msg, "flags", ""),
                    getattr(msg, "fixStat", ""),
                    getattr(msg, "flags2", ""),
                ])
            elif conn.topic == "/ublox_rover/navrelposned":
                flags = int(getattr(msg, "flags", 0))
                rel_pos_valid = bool(flags & 0x04)
                carr_soln_mask = flags & 0x18  # bits 3-4
                if carr_soln_mask == 0x10:
                    carr_soln = "fixed"
                elif carr_soln_mask == 0x08:
                    carr_soln = "float"
                else:
                    carr_soln = "none"
                rel_pos_heading_valid = bool(flags & 0x100)
                gnss_fix_ok = bool(flags & 0x01)
                diff_soln = bool(flags & 0x02)
                ublox_rover_navrelpos.append([
                    f"{rel_s:.3f}",
                    flags,
                    int(gnss_fix_ok),
                    int(diff_soln),
                    int(rel_pos_valid),
                    carr_soln,
                    int(rel_pos_heading_valid),
                    getattr(msg, "relPosHeading", 0),
                    getattr(msg, "accHeading", 0),
                ])
            elif conn.topic == "/ublox_moving_base/navpvt":
                ublox_mb_navpvt.append([
                    f"{rel_s:.3f}",
                    getattr(msg, "fixType", ""),
                    getattr(msg, "flags", ""),
                    getattr(msg, "numSV", ""),
                ])
            elif conn.topic == "/ublox_moving_base/navstatus":
                ublox_mb_navstatus.append([
                    f"{rel_s:.3f}",
                    getattr(msg, "gpsFix", ""),
                    getattr(msg, "flags", ""),
                ])
            elif conn.topic == "/imu/data":
                imu_step += 1
                if imu_step % 100 != 0:  # 100Hz -> 1Hz
                    continue
                try:
                    a = msg.angular_velocity
                    l = msg.linear_acceleration
                    o = msg.orientation
                    imu_rows.append([
                        f"{rel_s:.3f}",
                        f"{a.x:.4f}", f"{a.y:.4f}", f"{a.z:.4f}",
                        f"{l.x:.4f}", f"{l.y:.4f}", f"{l.z:.4f}",
                        f"{o.x:.4f}", f"{o.y:.4f}", f"{o.z:.4f}", f"{o.w:.4f}",
                    ])
                except Exception:
                    pass

    _write_csv(
        out_dir / "ublox_rover_navrelposned.csv",
        ["t_s", "flags_raw", "gnss_fix_ok", "diff_soln", "rel_pos_valid",
         "carr_soln", "rel_pos_heading_valid", "rel_pos_heading_deg1e-5",
         "acc_heading_deg1e-5"],
        ublox_rover_navrelpos,
    )
    _write_csv(
        out_dir / "ublox_rover_navpvt.csv",
        ["t_s", "fix_type", "flags", "num_sv", "lat_deg", "lon_deg", "h_acc", "v_acc"],
        ublox_rover_navpvt,
    )
    _write_csv(
        out_dir / "ublox_rover_navstatus.csv",
        ["t_s", "gps_fix", "flags", "fix_stat", "flags2"],
        ublox_rover_navstatus,
    )
    _write_csv(
        out_dir / "ublox_moving_base_navpvt.csv",
        ["t_s", "fix_type", "flags", "num_sv"],
        ublox_mb_navpvt,
    )
    _write_csv(
        out_dir / "ublox_moving_base_navstatus.csv",
        ["t_s", "gps_fix", "flags"],
        ublox_mb_navstatus,
    )
    _write_csv(
        out_dir / "imu_1hz.csv",
        ["t_s", "ang_x", "ang_y", "ang_z", "lin_x", "lin_y", "lin_z", "ox", "oy", "oz", "ow"],
        imu_rows,
    )
    artifacts += [
        "ublox_rover_navrelposned.csv", "ublox_rover_navpvt.csv",
        "ublox_rover_navstatus.csv", "ublox_moving_base_navpvt.csv",
        "ublox_moving_base_navstatus.csv", "imu_1hz.csv",
    ]

    # ---- diagnostics ----------------------------------------------------
    log("  extracting diagnostics ...")
    diag_rows: list[list] = []
    rosout_rows: list[list] = []
    with AnyReader([diag]) as r:
        start_ns = int(r.start_time)
        for conn, t_ns, raw in r.messages():
            rel_s = (t_ns - start_ns) / 1e9
            if conn.topic == "/diagnostics":
                try:
                    msg = r.deserialize(raw, conn.msgtype)
                    for s in msg.status[:8]:
                        if s.level > 0:  # OK=0, WARN=1, ERROR=2, STALE=3
                            diag_rows.append([
                                f"{rel_s:.2f}",
                                int(s.level),
                                getattr(s, "name", "")[:80],
                                getattr(s, "message", "")[:120],
                            ])
                except Exception:
                    pass
            elif conn.topic == "/rosout":
                try:
                    msg = r.deserialize(raw, conn.msgtype)
                    level = getattr(msg, "level", 0)
                    if level >= 4:  # WARN/ERR/FATAL
                        rosout_rows.append([
                            f"{rel_s:.2f}", int(level),
                            getattr(msg, "name", "")[:40],
                            getattr(msg, "msg", "")[:200],
                        ])
                except Exception:
                    pass

    # dedupe diagnostics (often repeats every 1s)
    def _dedup(rows, key=lambda x: (x[1], x[2], x[3])):
        seen = set()
        out = []
        for row in rows:
            k = key(row)
            if k not in seen:
                seen.add(k)
                out.append(row)
        return out

    diag_unique = _dedup(diag_rows)
    rosout_unique = _dedup(rosout_rows, key=lambda x: (x[1], x[2], x[3][:80]))
    _write_csv(out_dir / "diagnostics_nonzero_unique.csv",
               ["t_s", "level", "name", "message"], diag_unique[:400])
    _write_csv(out_dir / "rosout_warnings.csv",
               ["t_s", "level", "node", "msg"], rosout_unique[:200])
    artifacts += ["diagnostics_nonzero_unique.csv", "rosout_warnings.csv"]

    # ---- dataspeed: gps fix + steering + throttle + twist --------------
    log("  extracting dataspeed (gps/steering/throttle/twist) ...")
    gps_fix_rows: list[list] = []
    steer_rows: list[list] = []
    twist_rows: list[list] = []
    throttle_rows: list[list] = []
    brake_rows: list[list] = []
    with AnyReader([dataspeed]) as r:
        start_ns = int(r.start_time)
        want = {
            "/vehicle/gps/fix", "/vehicle/steering_report", "/vehicle/twist",
            "/vehicle/throttle_report", "/vehicle/brake_report",
        }
        wanted_conns = [c for c in r.connections if c.topic in want]
        step_counters: dict[str, int] = {}
        for conn, t_ns, raw in r.messages(connections=wanted_conns):
            try:
                msg = r.deserialize(raw, conn.msgtype)
            except Exception:
                continue
            rel_s = (t_ns - start_ns) / 1e9
            n = step_counters.get(conn.topic, 0) + 1
            step_counters[conn.topic] = n
            if conn.topic == "/vehicle/gps/fix":
                gps_fix_rows.append([
                    f"{rel_s:.3f}",
                    getattr(msg, "status", None).status if hasattr(msg, "status") else "",
                    f"{getattr(msg, 'latitude', 0):.7f}",
                    f"{getattr(msg, 'longitude', 0):.7f}",
                    f"{getattr(msg, 'altitude', 0):.3f}",
                ])
            elif conn.topic == "/vehicle/steering_report":
                if n % 5 != 0:  # 100Hz -> 20Hz
                    continue
                steer_rows.append([
                    f"{rel_s:.3f}",
                    f"{getattr(msg, 'steering_wheel_angle', 0):.3f}",
                    f"{getattr(msg, 'steering_wheel_torque', 0):.3f}",
                    f"{getattr(msg, 'speed', 0):.3f}",
                ])
            elif conn.topic == "/vehicle/twist":
                if n % 5 != 0:
                    continue
                twist_rows.append([
                    f"{rel_s:.3f}",
                    f"{getattr(msg.twist.linear, 'x', 0):.3f}",
                    f"{getattr(msg.twist.linear, 'y', 0):.3f}",
                    f"{getattr(msg.twist.angular, 'z', 0):.3f}",
                ])
            elif conn.topic == "/vehicle/throttle_report":
                if n % 5 != 0:
                    continue
                throttle_rows.append([
                    f"{rel_s:.3f}",
                    f"{getattr(msg, 'pedal_input', 0):.3f}",
                    f"{getattr(msg, 'pedal_output', 0):.3f}",
                    int(getattr(msg, 'enabled', 0)),
                ])
            elif conn.topic == "/vehicle/brake_report":
                if n % 5 != 0:
                    continue
                brake_rows.append([
                    f"{rel_s:.3f}",
                    f"{getattr(msg, 'pedal_input', 0):.3f}",
                    f"{getattr(msg, 'pedal_output', 0):.3f}",
                    int(getattr(msg, 'enabled', 0)),
                ])

    _write_csv(out_dir / "gps_fix.csv",
               ["t_s", "status", "lat", "lon", "alt"], gps_fix_rows)
    _write_csv(out_dir / "steering_20hz.csv",
               ["t_s", "sw_angle", "sw_torque", "speed_mps"], steer_rows)
    _write_csv(out_dir / "twist_20hz.csv",
               ["t_s", "lin_x", "lin_y", "ang_z"], twist_rows)
    _write_csv(out_dir / "throttle_20hz.csv",
               ["t_s", "pedal_in", "pedal_out", "enabled"], throttle_rows)
    _write_csv(out_dir / "brake_20hz.csv",
               ["t_s", "pedal_in", "pedal_out", "enabled"], brake_rows)
    artifacts += ["gps_fix.csv", "steering_20hz.csv", "twist_20hz.csv",
                  "throttle_20hz.csv", "brake_20hz.csv"]

    # ---- frames from 2_cam-lidar.bag: ~1 fps across whole session -----
    # If frames already present (pre-extracted out-of-band), reuse them.
    # Opening the 364GB cam-lidar bag via rosbags takes ~27 min for index
    # build, so we favor the pre-extracted path.
    frame_count = 0
    existing = sorted(frames_dir.glob("frame_*.jpg"))
    if existing:
        for p in existing:
            artifacts.append(f"frames/{p.name}")
        frame_count = len(existing)
        log(f"  reusing {frame_count} pre-extracted cam1 frames from {frames_dir}")
    elif os.environ.get("SANFER_FRAMES") == "1" and camlidar.exists():
        try:
            with AnyReader([camlidar]) as r:
                start_ns = int(r.start_time)
                end_ns = int(r.end_time)
                # Find one image topic
                image_conns = [
                    c for c in r.connections
                    if c.msgtype in ("sensor_msgs/msg/CompressedImage", "sensor_msgs/CompressedImage",
                                     "sensor_msgs/msg/Image", "sensor_msgs/Image")
                ]
                # prefer compressed + front camera
                image_conns.sort(key=lambda c: (
                    0 if "compressed" in c.msgtype.lower() else 1,
                    0 if "front" in c.topic.lower() else 1,
                    c.topic,
                ))
                if image_conns:
                    chosen = image_conns[0]
                    log(f"    chosen camera topic: {chosen.topic} ({chosen.msgtype})")
                    # Iterate messages for chosen conn only; pick 1/s
                    last_kept_s = -999.0
                    target_dt_s = 30.0  # every 30 seconds = ~120 frames across hour
                    max_frames = 60
                    frame_deadline = time.monotonic() + 240.0  # 4 min bail
                    for conn, t_ns, raw in r.messages(connections=[chosen]):
                        if time.monotonic() > frame_deadline:
                            log(f"    frame-extract timeout reached ({frame_count} frames kept)")
                            break
                        rel_s = (t_ns - start_ns) / 1e9
                        if rel_s - last_kept_s < target_dt_s:
                            continue
                        try:
                            msg = r.deserialize(raw, conn.msgtype)
                        except Exception:
                            continue
                        if "compressed" in chosen.msgtype.lower():
                            buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                            if cv2 is None:
                                break
                            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                        else:
                            # raw image
                            h, w = int(msg.height), int(msg.width)
                            data = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                            if data.size == h * w * 3:
                                img = data.reshape(h, w, 3)
                                if "rgb" in getattr(msg, "encoding", "").lower():
                                    img = img[:, :, ::-1].copy()
                            else:
                                continue
                        if img is None:
                            continue
                        jpg = _resize_and_jpeg(img)
                        if not jpg:
                            continue
                        fname = f"frame_{int(rel_s):04d}s.jpg"
                        (frames_dir / fname).write_bytes(jpg)
                        artifacts.append(f"frames/{fname}")
                        last_kept_s = rel_s
                        frame_count += 1
                        if frame_count >= max_frames:
                            break
        except Exception as e:
            log(f"  camlidar frame extraction failed: {e}")
    log(f"  total frames: {frame_count}")

    # ---- topics.txt & summary -----------------------------------------
    # NOTE: skipping camlidar enumeration — opening its 363GB index stalls.
    # User already has its topic list from the operator description.
    topics_lines = []
    for bag in [sensors, diag, dataspeed]:
        if not bag.exists():
            continue
        topics_lines.append(f"\n=== {bag.name} ===")
        try:
            with AnyReader([bag]) as r:
                topics_lines.append(f"duration_s={(r.end_time - r.start_time)/1e9:.1f} "
                                    f"start_ns={r.start_time}")
                for c in r.connections:
                    topics_lines.append(f"  {c.topic:55s} {c.msgtype:45s} n={c.msgcount}")
        except Exception as e:
            topics_lines.append(f"  (enumeration failed: {e})")
    topics_lines.append("\n=== 2_cam-lidar.bag ===")
    topics_lines.append("# (skipped enumeration — 363GB cam-lidar bag indexing is slow)")
    topics_lines.append("# Contains /cam[1-6]/image_raw/compressed + /velodyne_points; "
                        "frames not decoded for this run.")
    (out_dir / "topics.txt").write_text("\n".join(topics_lines))

    summary = {
        "case": "sanfer_tunnel",
        "session_duration_s": 3626.8,
        "vehicle_platform": "Lincoln MKZ drive-by-wire, dual-antenna u-blox RTK",
        "artifacts": artifacts,
        "csv_schemas_hint": {
            "ublox_rover_navrelposned.csv": (
                "RTK relative-position solution between rover antenna and moving-base antenna. "
                "flags (uint32) bitfield: bit0=gnssFixOk, bit1=diffSoln, bit2=relPosValid, "
                "bits3-4=carrSoln (0=none,1=float,2=fixed), bit8=relPosHeadingValid. "
                "carr_soln column already decoded."
            ),
            "ublox_rover_navpvt.csv": "fix_type: 0=no fix,2=2D,3=3D,4=GNSS+dead-reckon,5=time-only",
            "diagnostics_nonzero_unique.csv": "Only non-OK diagnostic statuses, deduped by (level,name,message).",
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    artifacts.append("summary.json")
    artifacts.append("topics.txt")

    # bytes sanity
    return {
        "bundle_dir": out_dir,
        "duration_s": 3626.8,
        "artifacts": artifacts,
        "notes": f"5 bags combined, {frame_count} frames, sparse 1/30s across 1hr session",
    }


def extract_boat(out_dir: Path) -> dict:
    """Boat bag is corrupted — build text-only manifest from metadata.yaml."""
    src = Path("/mnt/ssd_boat/rosbag2_2025_09_17-14_01_14")
    meta = (src / "metadata.yaml").read_text()
    (out_dir / "metadata.yaml").write_text(meta)

    # Try AnyReader; if fails write the recovery notice
    topics_txt: list[str] = ["# Boat ROS2 bag — sqlite3 format"]
    reader_ok = False
    try:
        with AnyReader([src]) as r:
            reader_ok = True
            topics_txt.append(f"duration_s={(r.end_time - r.start_time)/1e9:.1f}")
            for c in r.connections:
                topics_txt.append(f"  {c.topic:55s} {c.msgtype:45s} n={c.msgcount}")
    except Exception as e:
        topics_txt.append(f"# AnyReader unable to open: {e}")
        topics_txt.append("# Falling back to metadata.yaml (see attached).")
        topics_txt.append("# Known topics from metadata.yaml: /lidar_points n=4168, "
                          "/lidar_imu n=0, /rosout n=9, /parameter_events n=0, "
                          "/events/write_split n=0")
        topics_txt.append("# Duration: 416.76 seconds (~7 min)")

    (out_dir / "topics.txt").write_text("\n".join(topics_txt))

    summary = {
        "case": "boat_lidar",
        "duration_s": 416.76,
        "platform": "unmanned surface vessel (USV), LIDAR-only",
        "sensors": {
            "/lidar_points": {"type": "sensor_msgs/PointCloud2", "msg_count": 4168,
                              "approx_hz": 10.0},
            "/lidar_imu": {"type": "sensor_msgs/Imu", "msg_count": 0,
                           "note": "IMU topic declared but NEVER published during session"},
        },
        "analysis_mode": "scenario_mining (telemetry-absent, lidar-only)",
        "operational_context": (
            "Vessel operated autonomously on open water for ~7 min. "
            "Only LIDAR pointclouds were recorded; the companion IMU "
            "stream published zero messages for the entire session. "
            "No GPS, no encoders, no camera. Infer anything from the "
            "absence of the IMU stream and the LIDAR msg cadence."
        ),
        "bag_recovery_note": (
            "The primary sqlite3 file is malformed and rosbags can't open it. "
            "The recovery SQL dump is too large to upload. The operator has "
            "provided metadata.yaml (attached) listing topics and counts. "
            "The reviewer should reason from metadata alone: what can be "
            "inferred when only topic counts + IMU silence are visible?"
        ),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    artifacts = ["metadata.yaml", "topics.txt", "summary.json"]
    return {
        "bundle_dir": out_dir,
        "duration_s": 416.76,
        "artifacts": artifacts,
        "notes": "bag corrupted, metadata-only analysis",
    }


def extract_camlidar_generic(bag_path: Path, case_name: str, out_dir: Path,
                             target_dt_s: float = 30.0, max_frames: int = 40) -> dict:
    """Generic extractor for huge car cam-lidar bags — topics + sparse frames.

    If frames/frame_*.jpg already exist (e.g. pre-extracted via
    scripts/extract_session_frames.py with telemetry-anchored windows),
    reuses them instead of re-sampling uniformly. Topics + summary are
    still regenerated from the bag.
    """
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    artifacts: list[str] = []
    topics_txt: list[str] = [f"# {bag_path.name}"]
    frame_count = 0
    duration_s = 0.0

    existing_frames = sorted(frames_dir.glob("frame_*.jpg"))
    reuse = bool(existing_frames)
    if reuse:
        log(f"  reusing {len(existing_frames)} pre-extracted frames from {frames_dir}")

    with AnyReader([bag_path]) as r:
        start_ns = int(r.start_time)
        end_ns = int(r.end_time)
        duration_s = (end_ns - start_ns) / 1e9
        topics_txt.append(f"duration_s={duration_s:.1f}")
        for c in r.connections:
            topics_txt.append(f"  {c.topic:55s} {c.msgtype:45s} n={c.msgcount}")
        image_conns = [
            c for c in r.connections
            if c.msgtype in ("sensor_msgs/msg/CompressedImage", "sensor_msgs/CompressedImage",
                             "sensor_msgs/msg/Image", "sensor_msgs/Image")
        ]
        image_conns.sort(key=lambda c: (
            0 if "compressed" in c.msgtype.lower() else 1,
            0 if "front" in c.topic.lower() else 1,
            c.topic,
        ))
        if image_conns:
            chosen = image_conns[0]
            topics_txt.append(f"# chosen frame topic: {chosen.topic}")
        if reuse:
            for p in existing_frames:
                artifacts.append(f"frames/{p.name}")
            frame_count = len(existing_frames)
        elif image_conns:
            chosen = image_conns[0]
            last_kept_s = -999.0
            frame_deadline = time.monotonic() + 240.0
            for conn, t_ns, raw in r.messages(connections=[chosen]):
                if time.monotonic() > frame_deadline:
                    break
                rel_s = (t_ns - start_ns) / 1e9
                if rel_s - last_kept_s < target_dt_s:
                    continue
                try:
                    msg = r.deserialize(raw, conn.msgtype)
                except Exception:
                    continue
                if "compressed" in chosen.msgtype.lower():
                    buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                    if cv2 is None:
                        break
                    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                else:
                    h, w = int(msg.height), int(msg.width)
                    data = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                    if data.size == h * w * 3:
                        img = data.reshape(h, w, 3)
                        if "rgb" in getattr(msg, "encoding", "").lower():
                            img = img[:, :, ::-1].copy()
                    else:
                        continue
                if img is None:
                    continue
                jpg = _resize_and_jpeg(img)
                if not jpg:
                    continue
                fname = f"frame_{int(rel_s):04d}s.jpg"
                (frames_dir / fname).write_bytes(jpg)
                artifacts.append(f"frames/{fname}")
                last_kept_s = rel_s
                frame_count += 1
                if frame_count >= max_frames:
                    break

    (out_dir / "topics.txt").write_text("\n".join(topics_txt))
    summary = {
        "case": case_name,
        "bag": bag_path.name,
        "duration_s": duration_s,
        "frames_extracted": frame_count,
        "analysis_mode": "scenario_mining (no telemetry, camera+lidar only)",
        "operational_context": (
            "Vehicle (Lincoln MKZ or similar) operating autonomously. "
            "Only sensor streams recorded (no control telemetry). "
            "Reviewer must infer motion patterns from visual evidence "
            "in sparsely-sampled frames."
        ),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    artifacts += ["summary.json", "topics.txt"]
    return {
        "bundle_dir": out_dir,
        "duration_s": duration_s,
        "artifacts": artifacts,
        "notes": f"{frame_count} frames @ {target_dt_s}s spacing",
    }


# ---------------------------------------------------------------------------
# Per-case prompts
# ---------------------------------------------------------------------------
SANFER_PROMPT = """Operator narrative: suspected GPS anomaly at tunnel entry caused behavior degradation. Confirm, refute, or refine this hypothesis using the evidence available. Do not assume the operator is correct.

You are analyzing a ~1 hour autonomous-vehicle session (sanfer_sanisidro run 2). Artifacts under /mnt/session/uploads/:
  * Per-topic telemetry CSVs — u-blox RTK rover + moving-base, GPS fix, IMU (1Hz subsampled), vehicle steering/twist/throttle/brake (20Hz).
  * diagnostics_nonzero_unique.csv — every non-OK diagnostic status that appeared.
  * rosout_warnings.csv — WARN/ERROR/FATAL log lines.
  * frames/frame_XXXXs.jpg — sparse camera thumbnails (~one every 30s) across the entire session for visual context.
  * summary.json — column schemas for the ublox telemetry (decode flags etc).
  * topics.txt — full topic listing with message counts for all 4 source bags.

Start by listing /mnt/session/uploads/ and reading summary.json + topics.txt. Then open the RTK CSVs (these are the smallest and most information-dense). Cross-check what you find against the operator narrative. A session-wide pattern should be treated as very different evidence from a localized event.

Respond with a single JSON object that validates against the PostMortemReport schema:
{"timeline": [{"t_ns": <int ns since bag start>, "label": "<short>", "cross_view": <bool>}],
 "hypotheses": [{"bug_class": "<one of: pid_saturation|sensor_timeout|state_machine_deadlock|bad_gain_tuning|missing_null_check|calibration_drift|latency_spike|other>",
                 "confidence": <0..1>, "summary": "<one sentence>",
                 "evidence": [{"source": "<camera|telemetry|code|timeline>",
                               "topic_or_file": "<path or topic>",
                               "t_ns": <int or null>, "snippet": "<short>"}],
                 "patch_hint": "<scoped fix idea>"}],
 "root_cause_idx": <int index>, "patch_proposal": "<unified-diff-style text or pseudo-patch>"}

Rank hypotheses highest-confidence first. Be precise about timestamps (use seconds*1e9 from bag start). Return JSON only, no fencing, no preamble.
"""

BOAT_PROMPT = """You are a forensic analyst for an unmanned surface vessel (USV) deployed on open water. Artifacts under /mnt/session/uploads/:
  * metadata.yaml — ROS2 bag manifest
  * topics.txt — topic listing with message counts
  * summary.json — operational context + known sensor-count anomaly

The underlying sqlite3 bag file is corrupted, so you cannot inspect raw LIDAR samples. You CAN reason about what the topic/message counts themselves tell you.

Perform conservative scenario mining. If the metadata alone reveals a notable condition (e.g., a sensor stream that should have data but doesn't), surface it. Do NOT fabricate moments from imagination — the task is grounded evidence only.

Respond with a single JSON object that validates against the PostMortemReport schema (same as post-mortem mode, but moments can be mapped into timeline + hypotheses):
{"timeline": [{"t_ns": <int>, "label": "<short>", "cross_view": false}],
 "hypotheses": [{"bug_class": "<closed-set>", "confidence": <0..1>,
                 "summary": "<one sentence>",
                 "evidence": [{"source": "telemetry", "topic_or_file": "<>",
                               "t_ns": null, "snippet": "<>"}],
                 "patch_hint": "<short>"}],
 "root_cause_idx": 0, "patch_proposal": "<short note or scoped fix>"}

If nothing is truly notable, return hypotheses=[] and say so in patch_proposal. Return JSON only.
"""


CAR_PROMPT_TEMPLATE = """You are performing scenario mining on a visual-only autonomous vehicle recording (__CASE__). Artifacts under /mnt/session/uploads/:
  * frames/frame_XXXXs.jpg — one camera thumbnail every ~30 seconds across a ~__DUR_MIN__-minute session.
  * topics.txt — topic listing with message counts (no decoded telemetry available).
  * summary.json — operational context.

Review a representative subset of the frames (don't need all — start with early/mid/late samples to gauge scene variability, then densify where needed). Identify up to 3 moments that would warrant operator review: scene-level oddities (stuck scene, sudden occlusion, weather change, near-miss visible, stopped traffic, abnormal ego pose). Be conservative — if nothing stands out, return an empty hypotheses list and say so explicitly.

Respond with a single JSON object matching PostMortemReport schema:
{"timeline": [{"t_ns": <int ns from bag start>, "label": "<short>", "cross_view": false}],
 "hypotheses": [{"bug_class": "<closed-set>", "confidence": <0..1>,
                 "summary": "<one sentence>",
                 "evidence": [{"source": "camera", "topic_or_file": "<frame file>",
                               "t_ns": <int or null>, "snippet": "<what you see>"}],
                 "patch_hint": "<short>"}],
 "root_cause_idx": 0, "patch_proposal": "<short note, or 'nothing anomalous detected'>"}

Return JSON only, no fencing, no preamble.
"""


def _fmt_car_prompt(case: str, dur_min: float) -> str:
    return (CAR_PROMPT_TEMPLATE
            .replace("__CASE__", case)
            .replace("__DUR_MIN__", f"{dur_min:.0f}"))


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------
@dataclass
class BagSpec:
    name: str
    extractor: Callable[[Path], dict]
    prompt: str
    cost_cap_usd: float
    extra_config: dict | None = None


_BUG_CLASS_REMAP = {
    # Closed-set taxonomy shim: models occasionally propose descriptive labels
    # that aren't in the enum. Map them rather than discarding the analysis.
    "stuck_planner": "state_machine_deadlock",
    "planner_stuck": "state_machine_deadlock",
    "sensor_exposure": "other",
    "ae_convergence": "other",
    "auto_exposure": "other",
    "overexposed": "other",
    "exposure_failure": "other",
    "gnss_dropout": "sensor_timeout",
    "rtk_failure": "sensor_timeout",
    "gps_dropout": "sensor_timeout",
    "tunnel_dropout": "sensor_timeout",
    "frozen_sensor": "missing_null_check",
    "stale_data": "sensor_timeout",
}


def _salvage_from_stream(stream_events_path: Path, case_name: str) -> dict | None:
    """Reconstruct a PostMortemReport from raw assistant text.

    When the model emits a response that contains the JSON but prepends a
    disclaimer or uses a bug_class outside the closed set, session.finalize
    rejects the whole payload. This helper:
      1. scans the stream events jsonl for assistant text blocks,
      2. picks the one with the largest JSON-looking substring,
      3. remaps non-enum bug_class values via _BUG_CLASS_REMAP (or 'other'),
      4. returns the parsed dict so the downstream reporter can use it.
    Returns None if nothing salvageable.
    """
    import re
    try:
        events = [json.loads(l) for l in open(stream_events_path)]
    except Exception:
        return None
    best: str | None = None
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        text = ev.get("payload", {}).get("text", "") or ""
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            continue
        cand = m.group(0)
        if best is None or len(cand) > len(best):
            best = cand
    if not best:
        return None
    try:
        data = json.loads(best)
    except Exception:
        return None
    if not isinstance(data, dict) or "hypotheses" not in data:
        return None

    valid = {"pid_saturation", "sensor_timeout", "state_machine_deadlock",
             "bad_gain_tuning", "missing_null_check", "calibration_drift",
             "latency_spike", "sensor_dropout", "config_error",
             "degraded_state_estimation", "communication_failure", "other"}
    for h in data.get("hypotheses", []):
        bc = h.get("bug_class", "other")
        if bc in valid:
            continue
        mapped = _BUG_CLASS_REMAP.get(bc, "other")
        h["bug_class"] = mapped
        notes = h.setdefault("notes", [])
        if isinstance(notes, list):
            notes.append(f"remapped_from={bc}")
        if "evidence" in h and "evidence_refs" not in h:
            h["evidence_refs"] = [
                e.get("topic_or_file") or e.get("source", "") for e in h["evidence"]
            ]
    log(f"[{case_name}] salvaged {len(data.get('hypotheses', []))} hypotheses")
    return data


def run_bag(spec: BagSpec, memory: MemoryStack, global_budget_remaining: float) -> dict:
    """Run extraction + managed-agent session for one bag. Returns result dict."""
    bag_out = OUT_ROOT / spec.name
    bag_out.mkdir(parents=True, exist_ok=True)

    analysis_json = bag_out / "analysis.json"
    if analysis_json.exists() and not os.environ.get("FORCE"):
        log(f"[{spec.name}] already done, skipping (set FORCE=1 to redo)")
        try:
            existing = json.loads(analysis_json.read_text())
        except Exception:
            existing = {}
        cost_data = {}
        cost_path = bag_out / "cost.json"
        if cost_path.exists():
            try:
                cost_data = json.loads(cost_path.read_text())
            except Exception:
                pass
        return {
            "name": spec.name,
            "status": "cached",
            "report": existing,
            "cost_usd": cost_data.get("total_usd", 0.0),
            "duration_s": cost_data.get("duration_s", 0.0),
        }

    # Extract
    extract_dir = bag_out / "bundle"
    extract_dir.mkdir(exist_ok=True)
    log(f"[{spec.name}] extracting ...")
    t0 = time.monotonic()
    try:
        extraction = spec.extractor(extract_dir)
    except Exception as e:
        log(f"[{spec.name}] EXTRACT FAILED: {e}")
        traceback.print_exc()
        return {"name": spec.name, "status": "extract_failed", "error": str(e),
                "cost_usd": 0.0, "duration_s": time.monotonic() - t0}
    log(f"[{spec.name}] extracted in {time.monotonic()-t0:.1f}s — {len(extraction['artifacts'])} files")

    # Write prompt.txt
    (bag_out / "prompt.txt").write_text(spec.prompt)

    # Build ForensicAgent with all bundle files as mounted
    bundle = extract_dir
    mounted = []
    for a in extraction["artifacts"]:
        p = bundle / a
        if p.exists() and p.is_file():
            mounted.append(p)
    # Cap upload set to keep upload time sane. Sanfer hero uses ~54 frames +
    # CSVs; generic cases stay under 40. 90 leaves headroom without runaway.
    _MOUNT_CAP = int(os.environ.get("BLACKBOX_MOUNT_CAP", "90"))
    if len(mounted) > _MOUNT_CAP:
        log(f"[{spec.name}] truncating mounted set from {len(mounted)} to {_MOUNT_CAP}")
        mounted = mounted[:_MOUNT_CAP]

    # Strip default seed; pass our own prompt via steer as first user message
    # Actually ForensicAgent.open_session sends a generic seed. We'll steer afterwards.
    cfg = ForensicAgentConfig(
        task_budget_minutes=10,
        system_prompt=(
            "You are Black Box, a forensic copilot for robot incidents. "
            "Uploaded artifacts are mounted under /mnt/session/uploads/. "
            "List that directory first. Return a single JSON object matching "
            "the PostMortemReport schema — no preamble, no markdown fencing."
        ),
        mounted_files=mounted,
        agent_name=f"blackbox-{spec.name}",
    )
    if spec.extra_config:
        for k, v in spec.extra_config.items():
            setattr(cfg, k, v)

    agent = ForensicAgent(cfg, memory=memory)

    # Track cost via costs.jsonl tail
    cost_pos_before = cost_file_pos()
    session_start = time.monotonic()

    session = None
    stream_events_path = bag_out / "stream_events.jsonl"
    events_f = open(stream_events_path, "w")
    event_count = 0

    report_payload: dict | None = None
    status = "ok"
    error_msg = None
    killed_for_budget = False
    killed_for_time = False

    try:
        log(f"[{spec.name}] opening session + uploading {len(mounted)} files ...")
        session = agent.open_session(
            bag_path=bundle / "__nonexistent__",
            case_key=spec.name,
        )
        log(f"[{spec.name}] session {session.session_id} open; sending task prompt")
        session.steer(spec.prompt)

        deadline = session_start + PER_BAG_WALL_CLOCK_S
        last_cost_check = 0.0
        bag_cost = 0.0

        for ev in session.stream():
            event_count += 1
            events_f.write(json.dumps(ev) + "\n")
            if event_count <= 500 and event_count % 20 == 0:
                events_f.flush()
                etype = ev.get("type", "?")
                state = ev.get("payload", {}).get("state") if etype == "status" else None
                name = ev.get("payload", {}).get("name") if etype == "tool_call" else None
                log(f"  [{spec.name}] ev #{event_count} {etype}"
                    + (f" name={name}" if name else "")
                    + (f" state={state}" if state else ""))

            # Wall-clock kill
            if time.monotonic() > deadline:
                log(f"[{spec.name}] WALL-CLOCK kill at {PER_BAG_WALL_CLOCK_S}s")
                killed_for_time = True
                break

            # Mid-stream cost check every 30s
            now = time.monotonic()
            if now - last_cost_check > 30.0:
                last_cost_check = now
                bag_cost = cost_since(cost_pos_before)
                if bag_cost > spec.cost_cap_usd:
                    log(f"[{spec.name}] COST CAP ${bag_cost:.2f} > ${spec.cost_cap_usd} — kill")
                    killed_for_budget = True
                    break

            # Cap event count
            if event_count >= 500:
                log(f"[{spec.name}] event count {event_count} cap — finalizing")
                break

        # Attempt finalize. If it fails because the last assistant message
        # wasn't JSON, steer once with an explicit "JSON only" nudge and
        # drain a short additional event burst before retrying.
        def _try_finalize():
            return session.finalize()

        try:
            report_payload = _try_finalize()
            log(f"[{spec.name}] finalize ok — {len(report_payload.get('hypotheses', []))} hypotheses")
        except Exception as e:
            msg = str(e)
            if "not valid JSON" in msg or "no assistant message" in msg:
                log(f"[{spec.name}] finalize failed ({msg[:120]}); steering JSON-only retry")
                try:
                    session.steer(
                        "Output ONLY the PostMortemReport JSON object now. "
                        "No preamble, no disclaimer, no markdown fences. "
                        "Start your response with '{' and end with '}'."
                    )
                    retry_ev_budget = 40
                    retry_deadline = time.monotonic() + 120.0
                    for ev in session.stream():
                        event_count += 1
                        events_f.write(json.dumps(ev) + "\n")
                        retry_ev_budget -= 1
                        if retry_ev_budget <= 0 or time.monotonic() > retry_deadline:
                            break
                    events_f.flush()
                    report_payload = _try_finalize()
                    log(f"[{spec.name}] finalize ok after retry — "
                        f"{len(report_payload.get('hypotheses', []))} hypotheses")
                except Exception as e2:
                    log(f"[{spec.name}] finalize still failed after retry: {e2}")
                    report_payload = _salvage_from_stream(stream_events_path, spec.name)
                    if report_payload is not None:
                        log(f"[{spec.name}] SALVAGED from stream — "
                            f"{len(report_payload.get('hypotheses', []))} hypotheses")
                        status = "salvaged_finalize_failure"
                    else:
                        status = "finalize_failed"
                        error_msg = str(e2)[:400]
            else:
                log(f"[{spec.name}] finalize failed: {e}")
                report_payload = _salvage_from_stream(stream_events_path, spec.name)
                if report_payload is not None:
                    log(f"[{spec.name}] SALVAGED from stream — "
                        f"{len(report_payload.get('hypotheses', []))} hypotheses")
                    status = "salvaged_finalize_failure"
                else:
                    status = "finalize_failed"
                    error_msg = msg[:400]
    except Exception as e:
        log(f"[{spec.name}] session exception: {e}")
        traceback.print_exc()
        status = "session_failed"
        error_msg = str(e)[:400]
    finally:
        events_f.close()
        # delete session
        if session is not None:
            try:
                Anthropic().beta.sessions.delete(session.session_id)
                log(f"[{spec.name}] session deleted")
            except Exception as e:
                log(f"[{spec.name}] session delete failed (ok): {e}")

    duration_s = time.monotonic() - session_start

    # Compute final cost from costs.jsonl tail
    total_cost = cost_since(cost_pos_before)

    cost_record = {
        "cached_input": 0,
        "uncached_input": 0,
        "cache_creation": 0,
        "output": 0,
        "total_usd": float(total_cost),
        "duration_s": float(duration_s),
        "event_count": event_count,
        "status": status,
        "killed_for_budget": killed_for_budget,
        "killed_for_time": killed_for_time,
    }
    # Fill token breakdown from costs.jsonl tail entries
    if COSTS_FILE.exists():
        with open(COSTS_FILE, "rb") as f:
            f.seek(cost_pos_before)
            for line in f:
                try:
                    e = json.loads(line)
                    cost_record["cached_input"] += int(e.get("cached_input_tokens", 0) or 0)
                    cost_record["uncached_input"] += int(e.get("uncached_input_tokens", 0) or 0)
                    cost_record["cache_creation"] += int(e.get("cache_creation_tokens", 0) or 0)
                    cost_record["output"] += int(e.get("output_tokens", 0) or 0)
                except Exception:
                    pass

    (bag_out / "cost.json").write_text(json.dumps(cost_record, indent=2))

    if report_payload is not None:
        (bag_out / "analysis.json").write_text(json.dumps(report_payload, indent=2))
        # Build PDF
        try:
            case_meta = {
                "case_key": spec.name,
                "mode": "post_mortem" if spec.name == "sanfer_tunnel" else "scenario_mining",
                "bag_path": extraction.get("notes", ""),
                "duration_s": extraction.get("duration_s"),
            }
            build_report(report_payload, artifacts={}, out_pdf=bag_out / "report.pdf",
                         case_meta=case_meta)
            log(f"[{spec.name}] report.pdf written")
        except Exception as e:
            log(f"[{spec.name}] PDF build failed: {e}")
    else:
        # save whatever we know
        (bag_out / "analysis_raw.json").write_text(json.dumps({
            "status": status, "error": error_msg,
        }, indent=2))

    # copy topics.txt to bag root
    src_topics = bundle / "topics.txt"
    if src_topics.exists():
        (bag_out / "topics.txt").write_bytes(src_topics.read_bytes())

    return {
        "name": spec.name,
        "status": status,
        "report": report_payload,
        "cost_usd": float(total_cost),
        "duration_s": float(duration_s),
        "killed_for_budget": killed_for_budget,
        "killed_for_time": killed_for_time,
        "error": error_msg,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("ANTHROPIC_API_KEY not set")
        return 1

    memory = MemoryStack.open(MEMORY_DIR)

    specs = [
        BagSpec(
            name="sanfer_tunnel",
            extractor=extract_sanfer,
            prompt=SANFER_PROMPT,
            cost_cap_usd=7.0,
        ),
        BagSpec(
            name="boat_lidar",
            extractor=extract_boat,
            prompt=BOAT_PROMPT,
            cost_cap_usd=5.0,
        ),
        BagSpec(
            name="car_0",
            extractor=lambda d: extract_camlidar_generic(
                Path("/mnt/hdd/0_cam-lidar.bag"), "car_0", d),
            prompt=_fmt_car_prompt("car_0", 30),
            cost_cap_usd=5.0,
        ),
        BagSpec(
            name="car_1",
            extractor=lambda d: extract_camlidar_generic(
                ROOT / "data" / "bags" / "1_cam-lidar.bag", "car_1", d),
            prompt=_fmt_car_prompt("car_1", 16),
            cost_cap_usd=5.0,
        ),
        BagSpec(
            name="car_3",
            extractor=lambda d: extract_camlidar_generic(
                Path("/mnt/hdd/3_cam-lidar.bag"), "car_3", d),
            prompt=_fmt_car_prompt("car_3", 20),
            cost_cap_usd=5.0,
        ),
    ]

    # Filter by argv if provided
    only = sys.argv[1:]
    if only:
        specs = [s for s in specs if s.name in only]
        log(f"filtering to: {[s.name for s in specs]}")

    all_results: list[dict] = []
    total_cost = 0.0

    cost_pos_global = cost_file_pos()
    log(f"GLOBAL BUDGET: ${GLOBAL_BUDGET_USD:.2f} — starting at cost pos={cost_pos_global}")

    for spec in specs:
        running_total = cost_since(cost_pos_global)
        log(f"=== {spec.name} === running_total=${running_total:.2f} / ${GLOBAL_BUDGET_USD:.2f}")
        if running_total >= GLOBAL_BUDGET_USD - 0.5:
            log(f"GLOBAL BUDGET nearly exhausted, skipping {spec.name}")
            all_results.append({"name": spec.name, "status": "skipped_budget",
                                "cost_usd": 0.0, "duration_s": 0.0})
            continue
        # Adjust cap if global remaining is tighter
        remaining = GLOBAL_BUDGET_USD - running_total
        effective_cap = min(spec.cost_cap_usd, remaining - 0.2)
        spec.cost_cap_usd = max(0.5, effective_cap)
        try:
            result = run_bag(spec, memory, remaining)
        except Exception as e:
            log(f"[{spec.name}] TOP-LEVEL CRASH: {e}")
            traceback.print_exc()
            result = {"name": spec.name, "status": "crashed", "error": str(e),
                      "cost_usd": 0.0, "duration_s": 0.0}
        all_results.append(result)

    # Final summary
    final_total = cost_since(cost_pos_global)
    summary_lines = ["# Black Box — Final Pipeline Summary\n"]
    summary_lines.append(f"Run at: {datetime.now(timezone.utc).isoformat()}")
    summary_lines.append(f"Global spend: ${final_total:.4f} / ${GLOBAL_BUDGET_USD:.2f}")
    summary_lines.append("")
    summary_lines.append("## Results")
    summary_lines.append("| bag | status | hypotheses | top_finding | cost_usd | time_s |")
    summary_lines.append("|-----|--------|-----------:|-------------|---------:|-------:|")
    for r in all_results:
        rep = r.get("report") or {}
        hyps = rep.get("hypotheses", []) if rep else []
        top = ""
        if hyps:
            top = (hyps[0].get("summary") or hyps[0].get("bug_class") or "")[:100]
        elif r.get("error"):
            top = f"ERROR: {r['error'][:80]}"
        summary_lines.append(
            f"| {r['name']} | {r.get('status','?')} | {len(hyps)} | {top} "
            f"| ${r.get('cost_usd',0):.2f} | {r.get('duration_s',0):.0f} |"
        )
    summary_lines.append("")
    summary_lines.append("## Sanfer verdict")
    sanfer_result = next((r for r in all_results if r["name"] == "sanfer_tunnel"), None)
    if sanfer_result and sanfer_result.get("report"):
        rep = sanfer_result["report"]
        idx = rep.get("root_cause_idx", 0)
        try:
            root_hyp = rep["hypotheses"][idx]
        except Exception:
            root_hyp = (rep.get("hypotheses") or [{}])[0]
        root_text = root_hyp.get("summary", "") + " | " + root_hyp.get("patch_hint", "")
        verdict = "(d) insufficient_evidence"
        # Concatenate all hypotheses' text for a richer match
        all_text = root_text
        for h in rep.get("hypotheses", []) or []:
            all_text += " " + (h.get("summary") or "") + " " + (h.get("patch_hint") or "")
        all_text += " " + (rep.get("patch_proposal") or "")
        low = all_text.lower()
        mentions_rtk = any(k in low for k in ["rtk", "carr_soln", "carrsoln", "rel_pos_valid",
                                              "relposvalid", "navrelposned", "moving base",
                                              "moving-base", "moving_base", "carrier-phase",
                                              "carrier phase", "moving-base observation",
                                              "rxm-rawx", "rtcm3", "sfrbx"])
        mentions_session_wide = any(k in low for k in [
            "session-wide", "session wide", "entire session", "throughout", "full session",
            "never achieved", "never set", "never valid", "never produces",
            "never produced", "never ingests", "never ingest", "never form",
            "never formed", "permanent wait", "all 18", "before tunnel",
            "preexisting", "pre-existing", "pre existing", "from the start",
            "from session start", "at bag start", "at session start", "0%", "100%",
            "not caused by the tunnel", "not tunnel", "not a tunnel",
        ])
        mentions_refuted = any(k in low for k in ["refute", "refuted", "refutes",
                                                  "not supported", "rejected", "wrong",
                                                  "misattribution", "mislabeled"])
        mentions_tunnel = "tunnel" in low
        if mentions_rtk and (mentions_session_wide or mentions_refuted):
            verdict = "(b) refuted_correctly_rtk_preexisting"
        elif mentions_tunnel and not mentions_rtk:
            verdict = "(a) confirmed_operator"
        elif not mentions_rtk and not mentions_tunnel:
            verdict = "(d) insufficient_evidence"
        elif mentions_rtk:
            verdict = "(c) refuted_hallucinated"
        summary_lines.append(f"* Root cause text: {root_text}")
        summary_lines.append(f"* Verdict: {verdict}")
    else:
        summary_lines.append("* Sanfer did not produce a report.")

    (OUT_ROOT / "SUMMARY.md").write_text("\n".join(summary_lines))
    (OUT_ROOT / "results.json").write_text(json.dumps(all_results, indent=2, default=str))

    print("\n\n" + "="*70)
    print("\n".join(summary_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
