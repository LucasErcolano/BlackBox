# SPDX-License-Identifier: MIT
"""THE Black Box pipeline. Input: (path, optional prompt). Output: report.

Handles file or folder. Auto-discovers session assets, builds a platform-
agnostic manifest, picks suspicious windows from telemetry, extracts
frames only inside those windows, triages with a cheap vision pass, and
deep-mines only the windows flagged interesting.

Usage:
    python3 scripts/run_session.py <path> [--prompt TEXT] [--out DIR]
                                          [--force-deep]
                                          [--reuse-frames]

Stages (each idempotent; intermediate JSON kept in out/):
    1. discover   → session.json      (bag list + peripherals)
    2. manifest   → manifest.json     (sensor inventory, autonomy unknown)
    3. windows    → windows.json      (telemetry-derived anomaly windows)
    4. frames     → frames/           (baseline + dense-in-windows per cam)
    5. vision     → vision.json       (window_summary → visual_mining)
    6. report     → report.md         (markdown forensic write-up)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from PIL import Image
from rosbags.highlevel import AnyReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")

import rtk  # noqa: E402  (Rust Token Killer — stdout filter)

from black_box.analysis import ClaudeClient  # noqa: E402
from black_box.analysis.prompts_generic import (  # noqa: E402
    visual_mining_prompt,
    window_summary_prompt,
)
from black_box.analysis.windows import (  # noqa: E402
    Window,
    from_flag_transitions,
    from_gaps,
    merge_overlapping,
    top_k,
)
from black_box.ingestion.manifest import (  # noqa: E402
    Manifest,
    TopicInfo,
    build_manifest,
)
from black_box.ingestion.session import (  # noqa: E402
    SessionAssets,
    discover_session_assets,
)
from black_box.reporting import build_report  # noqa: E402


# ---------------------------------------------------------------------------
# Stage 1+2: discover + manifest
# ---------------------------------------------------------------------------


BIG_BAG_BYTES = 10 * 1024**3  # 10 GB — avoid opening this bag in stage 2


def stage_discover_and_manifest(path: Path, user_prompt: str | None,
                                out_dir: Path) -> tuple[SessionAssets, Manifest]:
    print(f"[1] discover: {path}", flush=True)
    assets = discover_session_assets(path)
    (out_dir / "session.json").write_text(json.dumps({
        "root": str(assets.root),
        "session_key": assets.session_key,
        "bags": [str(b) for b in assets.bags],
        "audio": [str(p) for p in assets.audio],
        "video": [str(p) for p in assets.video],
        "logs": [str(p) for p in assets.logs],
    }, indent=2))
    print(f"    bags={len(assets.bags)} "
          f"audio={len(assets.audio)} video={len(assets.video)} "
          f"logs={len(assets.logs)}", flush=True)

    # Split bags: small (for manifest + telemetry scan) vs. big (deferred to
    # stage 4 frame extraction). Opening a 364 GB ROS1 bag takes ~45 min —
    # we do it at most once per run, inside the frame-extraction pass.
    small_bags = [b for b in assets.bags
                  if b.exists() and b.stat().st_size < BIG_BAG_BYTES]
    big_bags = [b for b in assets.bags
                if b.exists() and b.stat().st_size >= BIG_BAG_BYTES]
    if big_bags:
        print(f"    deferring {len(big_bags)} big bag(s) to stage 4: "
              f"{[b.name for b in big_bags]}", flush=True)

    manifest_assets = SessionAssets(
        root=assets.root, session_key=assets.session_key,
        bags=small_bags or assets.bags,  # fallback if everything is big
        audio=assets.audio, video=assets.video, logs=assets.logs,
        chrony=assets.chrony, ros_logs=assets.ros_logs, other=assets.other,
        mtime_window=assets.mtime_window,
    )
    print(f"[2] manifest: scanning {len(manifest_assets.bags)} small bag(s) ...",
          flush=True)
    t0 = time.time()
    manifest = build_manifest(manifest_assets, user_prompt=user_prompt,
                              count_messages=True)
    # Patch bag list so downstream knows about the deferred big bags.
    manifest.bags = list(assets.bags)
    print(f"    manifest built in {time.time()-t0:.1f}s", flush=True)
    (out_dir / "manifest.json").write_text(json.dumps({
        "root": str(manifest.root),
        "session_key": manifest.session_key,
        "duration_s": manifest.duration_s,
        "t_start_ns": manifest.t_start_ns,
        "t_end_ns": manifest.t_end_ns,
        "autonomy": manifest.autonomy_signal(),
        "user_prompt": manifest.user_prompt,
        "cameras": [asdict(t) for t in manifest.cameras],
        "gnss": [asdict(t) for t in manifest.gnss],
        "imus": [asdict(t) for t in manifest.imus],
        "cmd": [asdict(t) for t in manifest.cmd],
        "odom": [asdict(t) for t in manifest.odom],
        "lidars": [asdict(t) for t in manifest.lidars],
    }, indent=2, default=str))
    for line in manifest.summary_lines():
        print(f"    {line}", flush=True)
    return assets, manifest


# ---------------------------------------------------------------------------
# Stage 3: windows
# ---------------------------------------------------------------------------


def _slice_session(t_start_ns: int, t_end_ns: int, n: int, span_s: float,
                   label: str, priority: float) -> list[Window]:
    """N windows evenly spread across the session (for session-wide anomalies)."""
    dur = (t_end_ns - t_start_ns) / 1e9
    if dur <= 0:
        return []
    n = max(1, min(n, max(1, int(dur // span_s))))
    if n == 1:
        return [Window(center_ns=(t_start_ns + t_end_ns) // 2,
                       span_s=min(span_s, max(5.0, dur - 2)),
                       label=label, priority=priority)]
    xs = np.linspace(span_s + 2, dur - span_s - 2, n)
    return [Window(center_ns=int(t_start_ns + x * 1e9),
                   span_s=span_s, label=f"{label} [t={x:.0f}s]",
                   priority=priority) for x in xs]


def _threshold_windows(t_arr: np.ndarray, v_arr: np.ndarray,
                       cmp: str, thresh: float, min_run_s: float,
                       label: str, span_s: float, priority: float,
                       max_n: int = 4) -> list[Window]:
    """Find runs where value violates threshold for >= min_run_s seconds."""
    if len(t_arr) < 2:
        return []
    if cmp == ">":
        bad = v_arr > thresh
    elif cmp == "<":
        bad = v_arr < thresh
    elif cmp == "==":
        bad = v_arr == thresh
    else:
        return []
    runs: list[tuple[int, int, float]] = []  # (i0, i1, dur_s)
    i = 0
    n = len(bad)
    while i < n:
        if not bad[i]:
            i += 1; continue
        j = i
        while j < n and bad[j]:
            j += 1
        dur = (t_arr[j - 1] - t_arr[i]) / 1e9
        if dur >= min_run_s:
            runs.append((i, j - 1, dur))
        i = j
    runs.sort(key=lambda r: -r[2])
    out: list[Window] = []
    for i0, i1, dur in runs[:max_n]:
        mid = int((t_arr[i0] + t_arr[i1]) // 2)
        out.append(Window(center_ns=mid,
                          span_s=max(span_s, min(dur, 60.0)),
                          label=f"{label} ({dur:.0f}s)",
                          priority=priority))
    return out


def _scan_gnss_and_gaps(bags: list[Path], gnss_topics: list[str],
                        camera_topics: list[str],
                        t_start_ns: int | None = None,
                        t_end_ns: int | None = None) -> list[Window]:
    """Full telemetry anomaly scan.

    Detects, per gnss topic:
      - fixType transitions + stuck-bad (fixType < 3 for whole session)
      - flags transitions + stuck-bad bit patterns (ublox: carrSoln bits 6-7
        stuck at 0 = no RTK; bit 0 gnssFixOK stuck at 0)
      - RELPOSNED.flags bit 2 (relPosValid) stuck at 0
      - accuracy excursions: hAcc > 5m, vAcc > 5m for >= 10s runs
      - satellite count: numSV < 6 for >= 10s runs
    Plus camera-topic silent gaps (where cam bag is scanned).
    """
    wins: list[Window] = []
    if not bags:
        return wins
    with AnyReader(bags) as reader:
        bag_start = int(reader.start_time) if t_start_ns is None else t_start_ns
        bag_end = int(reader.end_time) if t_end_ns is None else t_end_ns
        wanted = [c for c in reader.connections
                  if c.topic in gnss_topics or c.topic in camera_topics]
        if not wanted:
            return wins

        fix_by_topic: dict[str, list[tuple[int, int]]] = {t: [] for t in gnss_topics}
        flags_by_topic: dict[str, list[tuple[int, int]]] = {t: [] for t in gnss_topics}
        hacc_by_topic: dict[str, list[tuple[int, float]]] = {t: [] for t in gnss_topics}
        vacc_by_topic: dict[str, list[tuple[int, float]]] = {t: [] for t in gnss_topics}
        numsv_by_topic: dict[str, list[tuple[int, int]]] = {t: [] for t in gnss_topics}
        msgtype_by_topic: dict[str, str] = {}
        cam_ts: dict[str, list[int]] = {t: [] for t in camera_topics}

        for conn, t_ns, raw in reader.messages(connections=wanted):
            if conn.topic in camera_topics:
                cam_ts[conn.topic].append(int(t_ns))
                continue
            msgtype_by_topic[conn.topic] = conn.msgtype
            try:
                msg = reader.deserialize(raw, conn.msgtype)
            except Exception:
                continue
            fix = getattr(msg, "fixType", None)
            if fix is None:
                fix = getattr(msg, "gpsFix", None)
            if fix is None:
                st = getattr(msg, "status", None)
                if st is not None and hasattr(st, "status"):
                    fix = st.status
            flags = getattr(msg, "flags", None)
            hacc = getattr(msg, "hAcc", None)
            vacc = getattr(msg, "vAcc", None)
            numsv = getattr(msg, "numSV", None)
            try:
                if fix is not None:
                    fix_by_topic[conn.topic].append((int(t_ns), int(fix)))
                if flags is not None:
                    flags_by_topic[conn.topic].append((int(t_ns), int(flags)))
                if hacc is not None:
                    hacc_by_topic[conn.topic].append((int(t_ns), float(hacc)))
                if vacc is not None:
                    vacc_by_topic[conn.topic].append((int(t_ns), float(vacc)))
                if numsv is not None:
                    numsv_by_topic[conn.topic].append((int(t_ns), int(numsv)))
            except Exception:
                pass

        def _arrs(series):
            t = np.array([s[0] for s in series], dtype=np.int64)
            v = np.array([s[1] for s in series])
            return t, v

        # --- per-topic detectors ---
        for topic in gnss_topics:
            msgtype = msgtype_by_topic.get(topic, "")
            fseries = fix_by_topic[topic]
            flseries = flags_by_topic[topic]

            # fixType transitions
            if len(fseries) >= 2:
                t, v = _arrs(fseries)
                wins.extend(from_flag_transitions(
                    t, v, label_prefix=f"{topic} fixType",
                    span_s=30.0, priority=0.85, max_transitions=4,
                ))
                # stuck-bad fix (<3 for full session)
                if (v < 3).all():
                    wins.extend(_slice_session(
                        int(t[0]), int(t[-1]), n=3, span_s=25.0,
                        label=f"{topic} fixType stuck <3", priority=0.9,
                    ))
                # low-numSV excursions
                nseries = numsv_by_topic[topic]
                if len(nseries) > 5:
                    tn, vn = _arrs(nseries)
                    wins.extend(_threshold_windows(
                        tn, vn.astype(np.float64), "<", 6.0, 10.0,
                        label=f"{topic} numSV<6", span_s=25.0,
                        priority=0.75, max_n=3,
                    ))
                # accuracy excursions (hAcc is in mm for ublox; 5m = 5000)
                hseries = hacc_by_topic[topic]
                if len(hseries) > 5:
                    th, vh = _arrs(hseries)
                    unit_scale = 1000.0 if "ublox" in msgtype.lower() else 1.0
                    thresh = 5.0 * unit_scale
                    wins.extend(_threshold_windows(
                        th, vh.astype(np.float64), ">", thresh, 10.0,
                        label=f"{topic} hAcc>5m", span_s=25.0,
                        priority=0.75, max_n=3,
                    ))

            # flags transitions + stuck-bad bit patterns
            if len(flseries) >= 2:
                t, v = _arrs(flseries)
                wins.extend(from_flag_transitions(
                    t, v, label_prefix=f"{topic} flags",
                    span_s=25.0, priority=0.8, max_transitions=4,
                ))
                # ublox NavPVT flags: bit 0 gnssFixOK, bits 6-7 carrSoln
                if "navpvt" in msgtype.lower():
                    fix_ok = (v & 0x01) != 0
                    carr = (v >> 6) & 0x03
                    if (~fix_ok).all() or not fix_ok.any():
                        wins.extend(_slice_session(
                            int(t[0]), int(t[-1]), n=3, span_s=25.0,
                            label=f"{topic} gnssFixOK never set", priority=0.9))
                    if (carr == 0).all():
                        wins.extend(_slice_session(
                            int(t[0]), int(t[-1]), n=4, span_s=25.0,
                            label=f"{topic} carrSoln=NONE full session",
                            priority=0.95))
                # ublox RELPOSNED flags: bit 2 relPosValid
                if "relposned" in msgtype.lower():
                    rel_valid = (v & 0x04) != 0
                    if not rel_valid.any():
                        wins.extend(_slice_session(
                            int(t[0]), int(t[-1]), n=3, span_s=25.0,
                            label=f"{topic} relPosValid never set",
                            priority=0.95))

        # camera-topic gaps
        for topic, ts in cam_ts.items():
            if len(ts) < 10:
                continue
            arr = np.array(sorted(ts), dtype=np.int64)
            wins.extend(from_gaps(
                arr, min_gap_s=3.0, label=f"{topic} silent",
                span_s=25.0, priority=0.6, max_gaps=3,
            ))
    return wins


def _uniform_fallback(t_start_ns: int, t_end_ns: int,
                      span_s: float = 20.0, n: int = 3) -> list[Window]:
    dur = (t_end_ns - t_start_ns) / 1e9
    if dur <= span_s * 3:
        return [Window(center_ns=(t_start_ns + t_end_ns) // 2,
                       span_s=min(span_s, max(5.0, dur - 2)),
                       label="fallback full-session",
                       priority=0.5)]
    xs = np.linspace(span_s + 5, dur - span_s - 5, n)
    return [Window(center_ns=int(t_start_ns + x * 1e9),
                   span_s=span_s,
                   label=f"fallback t={x:.0f}s",
                   priority=0.5) for x in xs]


def stage_windows(manifest: Manifest, assets: SessionAssets,
                  out_dir: Path, max_windows: int = 8) -> list[Window]:
    print(f"[3] windows: scanning telemetry + camera gaps ...", flush=True)
    t0 = time.time()
    gnss_topics = [t.topic for t in manifest.gnss]
    cam_topics = [t.topic for t in manifest.cameras]
    # Use the bags that actually carry GNSS / cams.
    bags = [Path(b) for b in assets.bags]
    wins: list[Window] = []
    if gnss_topics:
        # Scan only small bags (we never want to open the 45 min camera bag
        # for window detection). Cam gaps are not detected here.
        small_bags = [b for b in bags
                      if b.exists() and b.stat().st_size < BIG_BAG_BYTES]
        if small_bags:
            wins.extend(_scan_gnss_and_gaps(small_bags, gnss_topics, []))
    if not wins:
        if manifest.t_start_ns and manifest.t_end_ns:
            wins = _uniform_fallback(manifest.t_start_ns, manifest.t_end_ns)

    wins = merge_overlapping(wins, merge_gap_s=5.0) if len(wins) > 1 else wins
    wins = top_k(wins, max_windows) if len(wins) > max_windows else wins

    (out_dir / "windows.json").write_text(json.dumps(
        [w.to_dict() for w in wins], indent=2, default=str))
    print(f"    selected {len(wins)} windows in {time.time()-t0:.1f}s", flush=True)
    for w in wins:
        rel_s = (w.center_ns - (manifest.t_start_ns or 0)) / 1e9
        print(f"      t_rel={rel_s:7.1f}s  span={w.span_s:.0f}s  "
              f"prio={w.priority:.2f}  {w.label}", flush=True)
    return wins


# ---------------------------------------------------------------------------
# Stage 4: multi-camera frame extraction inside windows (one pass)
# ---------------------------------------------------------------------------


def stage_frames(manifest: Manifest, assets: SessionAssets, windows: list[Window],
                 out_dir: Path, reuse: bool) -> dict:
    """Extract frames per camera per window. Returns index dict."""
    frames_dir = out_dir / "frames"
    index_path = out_dir / "frames_index.json"
    if reuse and index_path.exists():
        print(f"[4] frames: reusing {index_path}", flush=True)
        return json.loads(index_path.read_text())

    import cv2

    if not windows:
        print(f"[4] frames: no windows — skip", flush=True)
        index_path.write_text("{}")
        return {}

    # The largest bag typically carries cameras. Open it ONCE: enumerate
    # image connections (stage 2 skipped this bag), then extract.
    bags = sorted([Path(b) for b in assets.bags],
                  key=lambda p: p.stat().st_size if p.exists() else 0,
                  reverse=True)
    if not bags:
        return {}
    big_bag = bags[0]
    print(f"[4] frames: opening {big_bag.name} "
          f"({big_bag.stat().st_size / 1e9:.1f} GB; "
          f"may take ~45 min for first open) ...", flush=True)

    import cv2
    frames_dir.mkdir(parents=True, exist_ok=True)
    dense_stride_s = 2.0
    t0 = time.time()

    _IMG_MSGTYPES = {"sensor_msgs/msg/CompressedImage",
                     "sensor_msgs/CompressedImage",
                     "sensor_msgs/msg/Image", "sensor_msgs/Image"}

    with AnyReader([big_bag]) as reader:
        open_s = time.time() - t0
        print(f"    opened in {open_s:.1f}s", flush=True)
        start_ns = int(reader.start_time)
        end_ns = int(reader.end_time)
        # Discover camera topics FROM this bag. Augment manifest.
        img_conns = [c for c in reader.connections if c.msgtype in _IMG_MSGTYPES]
        discovered = sorted({c.topic for c in img_conns})
        print(f"    discovered {len(discovered)} image topics: "
              f"{discovered}", flush=True)
        known_cam_topics = {t.topic for t in manifest.cameras}
        for c in img_conns:
            if c.topic not in known_cam_topics:
                manifest.cameras.append(TopicInfo(
                    topic=c.topic, msgtype=c.msgtype, count=0, kind="camera"))
                known_cam_topics.add(c.topic)
        cam_topics = sorted(known_cam_topics)
        conns = [c for c in reader.connections if c.topic in cam_topics]
        if not conns:
            print(f"    no cam connections found — nothing to extract",
                  flush=True)
            index_path.write_text("{}")
            return {"windows": {}, "cam_topics": []}
        print(f"    {len(conns)} cam connections, bag_start_ns={start_ns}",
              flush=True)

        index: dict = {"windows": {}, "cam_topics": cam_topics}
        # Build per-window target lists.
        for wi, w in enumerate(windows):
            win_name = f"w{wi:02d}"
            w_start = max(int(reader.start_time), w.start_ns)
            w_end = min(int(reader.end_time), w.end_ns)
            if w_end <= w_start:
                continue
            n_targets = max(2, int((w_end - w_start) / (dense_stride_s * 1e9)))
            target_ts = np.linspace(w_start, w_end, n_targets, dtype=np.int64).tolist()
            per_cam: dict[str, list[dict]] = {t: [] for t in cam_topics}
            # Messages in this window for cam topics
            next_target_i = {t: 0 for t in cam_topics}
            for conn, t_ns, raw in reader.messages(connections=conns,
                                                   start=w_start, stop=w_end):
                topic = conn.topic
                if next_target_i[topic] >= len(target_ts):
                    continue
                if t_ns < target_ts[next_target_i[topic]]:
                    continue
                try:
                    msg = reader.deserialize(raw, conn.msgtype)
                except Exception:
                    next_target_i[topic] += 1
                    continue
                if "compressed" in conn.msgtype.lower():
                    arr = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                else:
                    h, wd = int(msg.height), int(msg.width)
                    data = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                    if data.size == h * wd * 3:
                        img = data.reshape(h, wd, 3)
                    else:
                        img = None
                if img is None:
                    next_target_i[topic] += 1
                    continue
                # Save big (800x600) + small (400x300)
                big = cv2.resize(img, (800, 600), interpolation=cv2.INTER_AREA)
                small = cv2.resize(img, (400, 300), interpolation=cv2.INTER_AREA)
                safe_topic = topic.replace("/", "_")
                i = next_target_i[topic]
                fb = f"{win_name}__{safe_topic}_{i:02d}_t{t_ns}.jpg"
                fs = f"{win_name}__{safe_topic}_{i:02d}_t{t_ns}_small.jpg"
                cv2.imwrite(str(frames_dir / fb), big,
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
                cv2.imwrite(str(frames_dir / fs), small,
                            [cv2.IMWRITE_JPEG_QUALITY, 82])
                per_cam[topic].append({"t_ns": int(t_ns),
                                       "file_big": fb, "file_small": fs})
                next_target_i[topic] += 1
            index["windows"][win_name] = {
                "start_ns": w_start,
                "stop_ns": w_end,
                "label": w.label,
                "priority": w.priority,
                "saved": per_cam,
            }
            n_saved = sum(len(v) for v in per_cam.values())
            print(f"    {win_name}: {n_saved} frames across {len(cam_topics)} cams "
                  f"[{w.label[:60]}]", flush=True)
    index_path.write_text(json.dumps(index, indent=2, default=str))
    # Re-persist manifest.json so reuse-from can hydrate cam topics
    # discovered during this extraction pass.
    (out_dir / "manifest.json").write_text(json.dumps({
        "root": str(manifest.root),
        "session_key": manifest.session_key,
        "duration_s": manifest.duration_s,
        "t_start_ns": manifest.t_start_ns,
        "t_end_ns": manifest.t_end_ns,
        "autonomy": manifest.autonomy_signal(),
        "user_prompt": manifest.user_prompt,
        "cameras": [asdict(t) for t in manifest.cameras],
        "gnss": [asdict(t) for t in manifest.gnss],
        "imus": [asdict(t) for t in manifest.imus],
        "cmd": [asdict(t) for t in manifest.cmd],
        "odom": [asdict(t) for t in manifest.odom],
        "lidars": [asdict(t) for t in manifest.lidars],
    }, indent=2, default=str))
    print(f"    frames done in {time.time()-t0:.1f}s", flush=True)
    return index


# ---------------------------------------------------------------------------
# Stage 5: vision (summary triage → deep)
# ---------------------------------------------------------------------------


def _images_for_window(frames_dir: Path, win_meta: dict, use_small: bool,
                       cam_topics: list[str], max_per_cam: int = 8):
    files = []
    lines = []
    order = 0
    for topic in cam_topics:
        saved = win_meta["saved"].get(topic, [])
        step = max(1, len(saved) // max_per_cam)
        chosen = saved[::step][:max_per_cam]
        lines.append(f"  {topic}: {len(chosen)} frames at img#{order}:")
        for f in chosen:
            lines.append(f"    img#{order}: t_ns={f['t_ns']}")
            files.append(f["file_small"] if use_small else f["file_big"])
            order += 1
    return files, "\n".join(lines)


def stage_vision(client: ClaudeClient, manifest: Manifest, frames_index: dict,
                 out_dir: Path, force_deep: bool) -> dict:
    print(f"[5] vision: triage + deep ...", flush=True)
    frames_dir = out_dir / "frames"
    cam_topics = frames_index.get("cam_topics", [])
    user_prompt = manifest.user_prompt

    per_window = {}
    all_moments = []
    total_cost = 0.0
    for win_name, meta in frames_index.get("windows", {}).items():
        dur_s = (meta["stop_ns"] - meta["start_ns"]) / 1e9
        files, idx_text = _images_for_window(frames_dir, meta, use_small=True,
                                             cam_topics=cam_topics, max_per_cam=4)
        if not files:
            print(f"    {win_name}: no frames, skip", flush=True)
            per_window[win_name] = {"summary": None, "deep": None,
                                    "summary_cost": 0, "deep_cost": 0}
            continue
        images = [Image.open(frames_dir / p).convert("RGB") for p in files]
        spec = window_summary_prompt(manifest=manifest, user_prompt=user_prompt)
        print(f"    [summary] {win_name}: {len(images)} imgs", flush=True)
        try:
            summary_obj, cost = client.analyze(
                prompt_spec=spec, images=images,
                user_fields={"window_len_s": f"{dur_s:.1f}",
                             "frames_index": idx_text},
                resolution="thumb", max_tokens=800,
            )
            summary = summary_obj.model_dump()
            c1 = cost.usd_cost
        except Exception as e:
            print(f"    [summary] {win_name} FAIL: {e}", flush=True)
            summary = {"per_channel": {}, "overall": f"failed: {e}",
                       "interesting": True,
                       "reason": "summary failed → deep fallback"}
            c1 = 0.0
        total_cost += c1
        print(f"    [summary] {win_name}: interesting="
              f"{summary.get('interesting')}  cost=${c1:.4f}  "
              f"reason={str(summary.get('reason',''))[:100]}", flush=True)

        entry: dict = {"summary": summary, "summary_cost": c1,
                       "label": meta["label"]}
        do_deep = bool(summary.get("interesting")) or force_deep
        if do_deep:
            files_big, idx_big = _images_for_window(
                frames_dir, meta, use_small=False, cam_topics=cam_topics,
                max_per_cam=8)
            images_big = [Image.open(frames_dir / p).convert("RGB")
                          for p in files_big]
            spec_d = visual_mining_prompt(manifest=manifest, user_prompt=user_prompt)
            print(f"    [deep] {win_name}: {len(images_big)} imgs",
                  flush=True)
            try:
                deep_obj, cost_d = client.analyze(
                    prompt_spec=spec_d, images=images_big,
                    user_fields={"n_images": len(images_big),
                                 "frames_index": idx_big,
                                 "window_info": f"window={win_name} "
                                 f"start_ns={meta['start_ns']} "
                                 f"stop_ns={meta['stop_ns']} "
                                 f"duration_s={dur_s:.1f} "
                                 f"label={meta['label']}"},
                    resolution="thumb", max_tokens=3000,
                )
                deep = deep_obj.model_dump()
                c2 = cost_d.usd_cost
            except Exception as e:
                print(f"    [deep] {win_name} FAIL: {e}", flush=True)
                deep = {"moments": [], "rationale": f"failed: {e}",
                        "operator_hypothesis_verdict": ""}
                c2 = 0.0
            total_cost += c2
            entry["deep"] = deep
            entry["deep_cost"] = c2
            for m in deep.get("moments", []):
                m2 = dict(m)
                m2["window"] = win_name
                all_moments.append(m2)
            print(f"    [deep] {win_name}: moments={len(deep.get('moments',[]))}"
                  f"  cost=${c2:.4f}", flush=True)
        else:
            entry["deep"] = None
            entry["deep_cost"] = 0.0
        per_window[win_name] = entry

    out = {"per_window": per_window, "all_moments": all_moments,
           "total_cost_usd": total_cost}
    (out_dir / "vision.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"    vision stage cost=${total_cost:.4f}  "
          f"moments={len(all_moments)}", flush=True)
    return out


# ---------------------------------------------------------------------------
# Stage 6: report
# ---------------------------------------------------------------------------


def stage_report(manifest: Manifest, vision: dict, frames_index: dict,
                 out_dir: Path, case_key: str) -> Path:
    print(f"[6] report: building ...", flush=True)
    timeline = []
    for m in vision.get("all_moments", []):
        timeline.append({
            "t_ns": int(m.get("t_ns", 0) or 0),
            "label": f"[{m['window']}] {m['label']}",
            "cross_view": len(m.get("cameras", {}).get("shows", [])) >= 2,
        })
    if vision.get("all_moments"):
        top = max(vision["all_moments"], key=lambda m: m.get("confidence", 0.0))
        hyps = [{
            "bug_class": "other",
            "confidence": float(top.get("confidence", 0.5)),
            "summary": (f"{len(vision['all_moments'])} visual moments of interest "
                        f"flagged across windows."),
            "evidence": [
                {"source": e.get("source", "camera"),
                 "topic_or_file": e.get("channel", "?"),
                 "t_ns": e.get("t_ns"),
                 "snippet": str(e.get("snippet", ""))[:200]}
                for m in vision["all_moments"] for e in m.get("evidence", [])
            ][:30],
            "patch_hint": "Review flagged moments manually; confirm against source data.",
        }]
    else:
        hyps = [{
            "bug_class": "other", "confidence": 0.0,
            "summary": "No anomalies detected.",
            "evidence": [],
            "patch_hint": "Nominal operation.",
        }]

    patch_lines = []
    for w_name, pw in vision.get("per_window", {}).items():
        summ = pw.get("summary") or {}
        patch_lines.append(f"[{w_name}] {summ.get('overall','')}")
        if pw.get("deep"):
            verd = pw["deep"].get("operator_hypothesis_verdict", "")
            if verd:
                patch_lines.append(f"  operator_verdict: {verd}")
    pdf_dict = {
        "timeline": timeline,
        "hypotheses": hyps,
        "root_cause_idx": 0,
        "patch_proposal": "\n".join(patch_lines),
    }
    out_pdf = out_dir / "report.md"
    result = build_report(
        report_json=pdf_dict,
        artifacts={"frames": [], "plots": [], "code_diff": ""},
        out_pdf=out_pdf,
        case_meta={
            "case_key": case_key,
            "bag_path": str(manifest.bags[0]) if manifest.bags else "",
            "duration_s": float(manifest.duration_s or 0.0),
            "mode": "run_session_v1",
        },
    )
    print(f"    report -> {result}", flush=True)
    return result


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run(path: Path, out_dir: Path, user_prompt: str | None = None,
        force_deep: bool = False, reuse_frames: bool = False,
        reuse_from: Path | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "input.json").write_text(json.dumps({
        "path": str(path), "user_prompt": user_prompt,
        "force_deep": force_deep, "reuse_frames": reuse_frames,
        "reuse_from": str(reuse_from) if reuse_from else None,
    }, indent=2))

    # Optionally hydrate the out_dir from a prior run's extraction caches
    # (manifest.json + windows.json + frames_index.json + frames/). Saves
    # the 364 GB bag re-scan when running the same session twice.
    if reuse_from and reuse_from.exists():
        import shutil as _sh
        for fname in ("session.json", "manifest.json", "windows.json",
                      "frames_index.json"):
            src = reuse_from / fname
            if src.exists() and not (out_dir / fname).exists():
                _sh.copy2(src, out_dir / fname)
        src_frames = reuse_from / "frames"
        dst_frames = out_dir / "frames"
        if src_frames.exists() and not dst_frames.exists():
            dst_frames.symlink_to(src_frames.resolve())
        reuse_frames = True
        print(f"[0] hydrated extraction cache from {reuse_from}", flush=True)

    # If manifest cache exists, skip stage 1+2 (loads from JSON).
    manifest_cache = out_dir / "manifest.json"
    windows_cache = out_dir / "windows.json"
    if reuse_frames and manifest_cache.exists() and windows_cache.exists():
        print(f"[1+2] manifest/windows: reusing cached JSON", flush=True)
        mj = json.loads(manifest_cache.read_text())
        manifest = Manifest(
            root=Path(mj["root"]), session_key=mj.get("session_key"),
            bags=[], duration_s=mj.get("duration_s"),
            t_start_ns=mj.get("t_start_ns"), t_end_ns=mj.get("t_end_ns"),
            cameras=[TopicInfo(**t) for t in mj.get("cameras", [])],
            gnss=[TopicInfo(**t) for t in mj.get("gnss", [])],
            imus=[TopicInfo(**t) for t in mj.get("imus", [])],
            cmd=[TopicInfo(**t) for t in mj.get("cmd", [])],
            odom=[TopicInfo(**t) for t in mj.get("odom", [])],
            lidars=[TopicInfo(**t) for t in mj.get("lidars", [])],
            user_prompt=user_prompt,
        )
        # Load bags from session.json if present
        sj = out_dir / "session.json"
        if sj.exists():
            manifest.bags = [Path(b) for b in json.loads(sj.read_text()).get("bags", [])]
        windows = [Window(**{k: v for k, v in w.items() if k in
                             {"center_ns", "span_s", "label", "priority"}})
                   for w in json.loads(windows_cache.read_text())]
        assets = SessionAssets(root=manifest.root,
                               session_key=manifest.session_key,
                               bags=manifest.bags)
    else:
        assets, manifest = stage_discover_and_manifest(path, user_prompt, out_dir)
        windows = stage_windows(manifest, assets, out_dir)
    frames_index = stage_frames(manifest, assets, windows, out_dir, reuse_frames)
    client = ClaudeClient()
    vision = stage_vision(client, manifest, frames_index, out_dir, force_deep)
    case_key = f"{Path(path).name}" + ("__prompted" if user_prompt else "__no_prompt")
    report = stage_report(manifest, vision, frames_index, out_dir, case_key)

    total = client.total_spent_usd()
    print(f"[done] report={report}  session_spend=${total:.4f}", flush=True)
    return {
        "report": str(report),
        "vision_cost_usd": vision.get("total_cost_usd", 0.0),
        "session_spend_usd": total,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path, help="file (.bag) or folder")
    ap.add_argument("--prompt", type=str, default=None,
                    help="Optional operator hypothesis / free text")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output dir (default: data/runs/<name>[_prompted])")
    ap.add_argument("--force-deep", action="store_true",
                    help="Run deep stage on every window regardless of triage")
    ap.add_argument("--reuse-frames", action="store_true",
                    help="Reuse existing frames_index.json + frames/ dir")
    ap.add_argument("--reuse-from", type=Path, default=None,
                    help="Hydrate manifest/windows/frames from prior run dir")
    ap.add_argument("--no-rtk", action="store_true",
                    help="Disable Rust Token Killer stdout filter (debug).")
    args = ap.parse_args()

    # Publish RTK opt-out to any subprocess-wrapping helper that reads env.
    os.environ["BB_RTK_DISABLED"] = "1" if args.no_rtk else "0"

    user_prompt = args.prompt or os.environ.get("BB_USER_PROMPT")
    out_dir = args.out
    if out_dir is None:
        tag = "prompted" if user_prompt else "no_prompt"
        out_dir = ROOT / "data" / "runs" / f"{args.path.name}__{tag}"
    run(args.path, out_dir, user_prompt=user_prompt,
        force_deep=args.force_deep, reuse_frames=args.reuse_frames,
        reuse_from=args.reuse_from)
    return 0


if __name__ == "__main__":
    sys.exit(main())
