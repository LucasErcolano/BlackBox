"""Window-aware frame sampler.

Given a bag (or multi-bag session) and a list of `Window` objects from
`black_box.analysis.windows`, extract:

- a sparse "baseline" set of frames spread uniformly across the bag so a
  reviewer can always see context even outside flagged windows;
- a dense set of frames inside each window, at `dense_stride_s`.

One AnyReader pass — we do not re-open the bag per window. For the
364 GB sanfer cam-lidar bag the index build alone is ~27 min; opening
it twice is a 54 min regression we refuse to pay.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

from rosbags.highlevel import AnyReader

from ..analysis.windows import Window


def _log(cb: Callable[[str], None] | None, msg: str) -> None:
    if cb is not None:
        cb(msg)


def _targets_ns(
    start_ns: int,
    end_ns: int,
    windows: Sequence[Window],
    dense_stride_s: float,
    baseline_n: int,
    windows_relative: bool | None = None,
) -> list[tuple[int, str]]:
    """Return sorted list of (t_ns, label) targets.

    `windows_relative`:
    - True  -> window.center_ns is an offset from start_ns (e.g. from
      analysis.timeline entries, which store ns-since-bag-start).
    - False -> window.center_ns is absolute wall-clock ns.
    - None  -> autodetect: if every window's end_ns falls below start_ns,
      treat as relative. Bags are typically sized in days since epoch, so
      relative offsets (seconds-to-hours) are always < start_ns.
    """
    if windows_relative is None:
        windows_relative = all(w.end_ns < start_ns for w in windows) if windows else False

    pts: list[tuple[int, str]] = []
    if baseline_n > 0:
        for t in np.linspace(start_ns, end_ns, baseline_n, dtype=np.int64):
            pts.append((int(t), "baseline"))

    stride_ns = int(dense_stride_s * 1e9)
    offset = start_ns if windows_relative else 0
    for w in windows:
        abs_start = w.start_ns + offset
        abs_end = w.end_ns + offset
        lo = max(start_ns, abs_start)
        hi = min(end_ns, abs_end)
        if hi <= lo:
            continue
        n = max(2, int((hi - lo) / stride_ns) + 1)
        for t in np.linspace(lo, hi, n, dtype=np.int64):
            pts.append((int(t), f"win:{w.label[:60]}"))

    pts.sort(key=lambda x: x[0])
    dedup: list[tuple[int, str]] = []
    tol = stride_ns // 2 if stride_ns else int(1e8)
    for t, lab in pts:
        if dedup and abs(dedup[-1][0] - t) <= tol:
            if dedup[-1][1] == "baseline" and lab != "baseline":
                dedup[-1] = (t, lab)
            continue
        dedup.append((t, lab))
    return dedup


def sample_frames(
    bags: Sequence[Path],
    topic: str,
    windows: Sequence[Window],
    out_dir: Path,
    *,
    dense_stride_s: float = 2.0,
    baseline_n: int = 8,
    jpeg_quality: int = 88,
    mirror_to: Path | None = None,
    windows_relative: bool | None = None,
    log: Callable[[str], None] | None = None,
) -> list[dict]:
    """Extract baseline + window-dense frames in a single AnyReader pass.

    Returns a manifest: list of dicts with t_rel_s, path, label, size_bytes.
    Skips ROS1/ROS2 differences via rosbags; requires cv2 for decode.
    """
    if cv2 is None:
        raise RuntimeError("cv2 required for frame extraction")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if mirror_to is not None:
        Path(mirror_to).mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    manifest: list[dict] = []

    with AnyReader([Path(b) for b in bags]) as reader:
        conns = [c for c in reader.connections if c.topic == topic]
        if not conns:
            available = sorted({c.topic for c in reader.connections if "image" in c.topic.lower()})
            raise RuntimeError(
                f"topic {topic!r} not found; image-ish topics: {available}"
            )
        start_ns = int(reader.start_time)
        end_ns = int(reader.end_time)
        targets = _targets_ns(
            start_ns, end_ns, windows, dense_stride_s, baseline_n,
            windows_relative=windows_relative,
        )
        _log(log, f"sample_frames: {len(targets)} targets "
                   f"(baseline={baseline_n} dense_stride={dense_stride_s}s "
                   f"windows={len(windows)}) over {(end_ns-start_ns)/1e9:.1f}s")

        if not targets:
            return manifest

        next_i = 0
        last_progress = time.time()
        msgtype = conns[0].msgtype
        is_compressed = "compressed" in msgtype.lower()

        for conn, t_ns, raw in reader.messages(connections=conns):
            if next_i >= len(targets):
                break
            target_t, label = targets[next_i]
            if t_ns < target_t:
                if time.time() - last_progress > 30:
                    elapsed_s = (t_ns - start_ns) / 1e9
                    _log(log, f"  ... bag t={elapsed_s:6.1f}s "
                               f"wrote={len(manifest)}/{len(targets)} "
                               f"wall={time.time()-t0:.0f}s")
                    last_progress = time.time()
                continue
            try:
                msg = reader.deserialize(raw, conn.msgtype)
            except Exception:
                next_i += 1
                continue

            if is_compressed:
                buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            else:
                h, w = int(msg.height), int(msg.width)
                data = np.frombuffer(bytes(msg.data), dtype=np.uint8)
                encoding = getattr(msg, "encoding", "").lower()
                if data.size == h * w * 3:
                    img = data.reshape(h, w, 3)
                    if "rgb" in encoding:
                        img = img[:, :, ::-1].copy()
                elif data.size == h * w:
                    gray = data.reshape(h, w)
                    img = np.stack([gray] * 3, axis=-1)
                else:
                    img = None
            if img is None:
                next_i += 1
                continue

            t_rel_s = (t_ns - start_ns) / 1e9
            tag = "dense" if label != "baseline" else "base"
            name = f"frame_{t_rel_s:07.1f}s_{tag}.jpg"
            path = out_dir / name
            cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
            if mirror_to is not None:
                shutil.copy2(path, Path(mirror_to) / name)
            size = path.stat().st_size
            manifest.append({
                "t_rel_s": round(t_rel_s, 2),
                "t_ns": int(t_ns),
                "label": label,
                "path": str(path),
                "bytes": size,
                "wxh": f"{img.shape[1]}x{img.shape[0]}",
            })
            _log(log, f"  [{len(manifest):3d}/{len(targets)}] "
                       f"t={t_rel_s:7.1f}s  {img.shape[1]}x{img.shape[0]}  "
                       f"{size//1024}KB  {label}")
            next_i += 1

    _log(log, f"sample_frames: done, wrote {len(manifest)} frames in {time.time()-t0:.0f}s")
    return manifest
