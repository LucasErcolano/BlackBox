# SPDX-License-Identifier: MIT
"""NAO6 ingestion adapter.

Converts NAO6 onboard artifacts (CameraTop/CameraBottom MP4s, ALMemory CSV,
controller source) into the canonical analysis-input dict consumed by the
Black Box pipeline.

Canonical output dict keys (see brief / split C):
    case_key, platform, duration_s, frames, frame_timestamps_ns,
    time_series, code_blobs, metadata

Dual-camera handling: frames from top + bottom cameras are merged into a
single time-ordered list. A parallel list `metadata["camera_order"]` tags
each frame with its source ("top" or "bottom"). This keeps the canonical
shape flat (one `frames`, one `frame_timestamps_ns`) while preserving the
cross-view information for downstream multi-view reasoning.
"""

from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


class NAO6Adapter:
    """Ingest NAO6 artifacts and emit the canonical pipeline input dict."""

    def ingest(
        self,
        *,
        case_key: str,
        top_video: Path | None = None,
        bottom_video: Path | None = None,
        telemetry_csv: Path | None = None,
        controller_source: Path | None = None,
        max_frames_per_camera: int = 24,
        sample_stride_ms: int = 100,
        synthetic: bool = False,
    ) -> dict:
        frames: list[Image.Image] = []
        frame_ts_ns: list[int] = []
        camera_order: list[str] = []
        cameras_used: list[str] = []
        frame_count_per_camera: dict[str, int] = {}

        max_duration_s = 0.0

        for cam_label, cam_path in (("top", top_video), ("bottom", bottom_video)):
            if cam_path is None:
                continue
            cam_path = Path(cam_path)
            if not cam_path.exists():
                continue
            cam_frames, cam_ts, cam_dur = _decode_video(
                cam_path,
                stride_ms=sample_stride_ms,
                max_frames=max_frames_per_camera,
            )
            if not cam_frames:
                continue
            cameras_used.append(cam_label)
            frame_count_per_camera[cam_label] = len(cam_frames)
            max_duration_s = max(max_duration_s, cam_dur)
            frames.extend(cam_frames)
            frame_ts_ns.extend(cam_ts)
            camera_order.extend([cam_label] * len(cam_frames))

        # Time-order the merged stream (stable sort keeps per-camera order on ties)
        if frames:
            order = sorted(range(len(frames)), key=lambda i: frame_ts_ns[i])
            frames = [frames[i] for i in order]
            frame_ts_ns = [frame_ts_ns[i] for i in order]
            camera_order = [camera_order[i] for i in order]

        time_series = _parse_telemetry_csv(telemetry_csv) if telemetry_csv else {}
        code_blobs = _load_controller_source(controller_source) if controller_source else {}

        # Duration preference: span of telemetry if present, else video duration
        duration_s = max_duration_s
        if time_series:
            span_ns = 0
            for series in time_series.values():
                if len(series) >= 2:
                    span_ns = max(span_ns, series[-1][0] - series[0][0])
            if span_ns > 0:
                duration_s = max(duration_s, span_ns / 1e9)

        metadata = {
            "platform": "nao6",
            "frame_count_per_camera": frame_count_per_camera,
            "cameras_used": cameras_used,
            "sample_stride_ms": sample_stride_ms,
            "synthetic": synthetic,
            "camera_order": camera_order,
            "timestamp_origin": "synthesized_monotonic_from_fps",
        }

        return {
            "case_key": case_key,
            "platform": "nao6",
            "duration_s": float(duration_s),
            "frames": frames,
            "frame_timestamps_ns": frame_ts_ns,
            "time_series": time_series,
            "code_blobs": code_blobs,
            "metadata": metadata,
        }


# ---- helpers ---------------------------------------------------------------


def _decode_video(
    path: Path, *, stride_ms: int, max_frames: int
) -> tuple[list[Image.Image], list[int], float]:
    """Decode a video, sample frames every stride_ms, return PIL frames + t_ns + duration.

    Timestamps are synthesized monotonically from FPS when absolute timestamps
    are absent (they typically are for plain MP4 captures).
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return [], [], 0.0

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0 or total <= 0:
        cap.release()
        return [], [], 0.0

    frame_period_ms = 1000.0 / fps
    # stride in source frames (at least 1)
    stride = max(1, int(round(stride_ms / frame_period_ms)))

    frames: list[Image.Image] = []
    ts_ns: list[int] = []
    idx = 0
    while len(frames) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, bgr = cap.read()
        if not ok or bgr is None:
            break
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        frames.append(Image.fromarray(rgb))
        t_ns = int(round(idx * frame_period_ms * 1_000_000))
        ts_ns.append(t_ns)
        idx += stride
        if idx >= total:
            break

    duration_s = total / fps
    cap.release()
    return frames, ts_ns, duration_s


def _parse_telemetry_csv(path: Path) -> dict[str, list[tuple[int, float]]]:
    """Parse ALMemory-style dump: columns `t_ns,key,value`.

    Non-float values are silently skipped per the spec (e.g., string state
    keys like `BalanceController/State`).
    """
    out: dict[str, list[tuple[int, float]]] = {}
    path = Path(path)
    if not path.exists():
        return out
    with path.open("r", newline="") as f:
        reader = csv.reader(f)
        header: list[str] | None = None
        for row in reader:
            if not row:
                continue
            if header is None:
                # Allow a header row or no header — detect by trying to parse t_ns.
                try:
                    int(row[0])
                    header = ["t_ns", "key", "value"]  # assume default order
                    # fall through and process this row
                except ValueError:
                    header = [c.strip() for c in row]
                    continue
            if len(row) < 3:
                continue
            try:
                t_ns = int(row[0])
            except (ValueError, TypeError):
                continue
            key = row[1]
            try:
                val = float(row[2])
            except (ValueError, TypeError):
                continue
            out.setdefault(key, []).append((t_ns, val))
    for k in out:
        out[k].sort(key=lambda p: p[0])
    return out


def _load_controller_source(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    if path.is_file():
        try:
            return {path.name: path.read_text(encoding="utf-8", errors="replace")}
        except OSError:
            return {}
    blobs: dict[str, str] = {}
    for py in sorted(path.rglob("*.py")):
        try:
            rel = py.relative_to(path).as_posix()
            blobs[rel] = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return blobs
