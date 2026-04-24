# SPDX-License-Identifier: MIT
"""Session discovery across a messy field-capture folder.

Operators rarely hand over a single file. They hand over a folder like:

    /mnt/hdd/sanfer_sanisidro/
    ├── 2_cam-lidar.bag          (364 GB)
    ├── 2_dataspeed.bag
    ├── 2_diagnostics.bag
    ├── 2_sensors.bag
    ├── 2_audio.wav               (same `2_` prefix — still session)
    ├── 2026-02-03-*.webm         (older videos, different mtime)
    ├── chrony/                   (NTP logs — scoped if mtime matches)
    └── ros_logs/log/<uuid>/...   (historical, filter by mtime)

`discover_session_assets(root)` returns a typed asset bundle grouped by
session prefix, filtering peripheral assets by mtime proximity to the
picked bag set. Nothing is opened yet — this is pure filesystem triage.

Design:

- "Session key" = numeric prefix `\d+_` on bag filenames (robotic convention).
  If present, we pick the heaviest group (by total bytes) as the session.
- Non-bag files/dirs at top level and one level deep are bucketed by
  extension. We keep them if their mtime falls inside [session_min - pad,
  session_max + pad]; `pad` defaults to 1 day to survive copy-skew.
- ROS2 bag dirs (metadata.yaml + *.db3/*.mcap) are returned as a single
  bag path in the bag bucket.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


# --- RTK wrapper -------------------------------------------------------------
# Token-Killer subprocess wrapper. Defined here so that any shell-out this
# module grows later automatically logs stdout-byte savings to
# data/costs.jsonl. See scripts/rtk.py for the full implementation.
_RTK_MODULE: Any = None


def _load_rtk() -> Any:
    """Lazy-import scripts/rtk.py (outside the `src/` package tree)."""
    global _RTK_MODULE
    if _RTK_MODULE is not None:
        return _RTK_MODULE
    repo_root = Path(__file__).resolve().parents[3]
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import rtk as _rtk  # type: ignore[import-not-found]
    _RTK_MODULE = _rtk
    return _rtk


def rtk_run(cmd: Sequence[str] | str, *, apply_filter: bool = True, **kwargs: Any):
    """Shell-out helper used by ingestion code paths. Filters + logs stdout.

    Thin proxy over `scripts.rtk.run` so call sites in this module (and its
    users) do not have to reach into the scripts/ dir directly. Pass
    `apply_filter=False` for the `--no-rtk` debug path.
    """
    rtk = _load_rtk()
    return rtk.run(cmd, apply_filter=apply_filter, **kwargs)


_PREFIX_RE = re.compile(r"^(?P<prefix>\d+)_")

_AUDIO_EXT = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
_LOG_EXT = {".log", ".txt"}

_FNAME_DATE_RE = re.compile(r"(?P<y>20\d{2})[-_](?P<m>\d{2})[-_](?P<d>\d{2})")


def _uuid1_epoch(name: str) -> float | None:
    """If `name` is a UUID v1, return its embedded unix epoch; else None."""
    try:
        from uuid import UUID
        u = UUID(name)
        if u.version != 1:
            return None
        return (u.time - 0x01b21dd213814000) / 1e7
    except Exception:
        return None


def _filename_epoch(name: str) -> float | None:
    m = _FNAME_DATE_RE.search(name)
    if not m:
        return None
    import datetime as _dt
    try:
        return _dt.datetime(int(m["y"]), int(m["m"]), int(m["d"])).timestamp()
    except Exception:
        return None


# -------- helpers -----------------------------------------------------------


def _is_ros2_bag_dir(p: Path) -> bool:
    if not p.is_dir():
        return False
    if (p / "metadata.yaml").exists():
        return True
    return any(p.glob("*.db3")) or any(p.glob("*.mcap"))


def _session_prefix(name: str) -> str | None:
    m = _PREFIX_RE.match(name)
    return m.group("prefix") if m else None


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


# -------- asset bundle ------------------------------------------------------


@dataclass
class SessionAssets:
    root: Path
    session_key: str | None
    bags: list[Path] = field(default_factory=list)
    audio: list[Path] = field(default_factory=list)
    video: list[Path] = field(default_factory=list)
    logs: list[Path] = field(default_factory=list)
    chrony: list[Path] = field(default_factory=list)
    ros_logs: list[Path] = field(default_factory=list)
    other: list[Path] = field(default_factory=list)
    mtime_window: tuple[float, float] | None = None

    def summary(self) -> str:
        lines = [f"session_key={self.session_key!r}  root={self.root}"]
        if self.mtime_window:
            lo, hi = self.mtime_window
            import datetime as _dt
            lines.append(
                f"mtime_window={_dt.datetime.fromtimestamp(lo):%Y-%m-%d %H:%M} "
                f"..{_dt.datetime.fromtimestamp(hi):%Y-%m-%d %H:%M}"
            )
        buckets = [
            ("bags", self.bags), ("audio", self.audio), ("video", self.video),
            ("logs", self.logs), ("chrony", self.chrony),
            ("ros_logs", self.ros_logs), ("other", self.other),
        ]
        for name, items in buckets:
            if not items:
                continue
            total_mb = sum(_file_bytes(p) for p in items) / (1024 * 1024)
            lines.append(f"  {name}: {len(items)} items, {total_mb:,.0f} MB")
            for p in items[:6]:
                lines.append(f"    - {p.relative_to(self.root) if self.root in p.parents or p == self.root else p}")
            if len(items) > 6:
                lines.append(f"    ... +{len(items)-6} more")
        return "\n".join(lines)


def _file_bytes(p: Path) -> int:
    try:
        if p.is_file():
            return p.stat().st_size
        if p.is_dir():
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0
    return 0


# -------- bag grouping ------------------------------------------------------


def _collect_bag_candidates(root: Path) -> list[Path]:
    """Top-level .bag files + ROS2 bag dirs at top or one level deep."""
    if root.is_file() and root.suffix == ".bag":
        return [root]

    cands: list[Path] = []
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if p.is_file() and p.suffix == ".bag":
                cands.append(p)
            elif _is_ros2_bag_dir(p):
                cands.append(p)
        # One level deep (e.g. foo/run1/bag.bag)
        for sub in root.iterdir():
            if sub.is_dir() and not _is_ros2_bag_dir(sub) and sub.name not in {"chrony", "ros_logs"}:
                for p in sub.iterdir():
                    if p.is_file() and p.suffix == ".bag":
                        cands.append(p)
                    elif _is_ros2_bag_dir(p):
                        cands.append(p)
    return cands


def _pick_session(bags: list[Path], forced_key: str | None) -> tuple[str | None, list[Path]]:
    if not bags:
        return None, []
    groups: dict[str, list[Path]] = defaultdict(list)
    for b in bags:
        groups[_session_prefix(b.name) or ""].append(b)
    if forced_key is not None:
        return forced_key, sorted(groups.get(forced_key, []))
    if len(groups) == 1:
        k = next(iter(groups))
        return (k or None), sorted(groups[k])

    def _weight(item):
        k, v = item
        return (sum(_file_bytes(p) for p in v), k)
    best_key, best = max(groups.items(), key=_weight)
    return (best_key or None), sorted(best)


# -------- peripheral assets -------------------------------------------------


def _mtime_window(paths: Iterable[Path], pad_s: float) -> tuple[float, float] | None:
    ts = [_mtime(p) for p in paths if _mtime(p) > 0]
    if not ts:
        return None
    return (min(ts) - pad_s, max(ts) + pad_s)


def _bucket_peripheral(
    root: Path,
    session_key: str | None,
    window: tuple[float, float] | None,
    max_depth: int = 3,
    include_ros_logs: bool = False,
    ros_log_pad_s: float = 7200.0,
) -> dict[str, list[Path]]:
    buckets: dict[str, list[Path]] = {
        "audio": [], "video": [], "logs": [], "chrony": [],
        "ros_logs": [], "other": [],
    }
    if not root.is_dir():
        return buckets

    def _in_window(p: Path, w: tuple[float, float] | None = None) -> bool:
        w = w if w is not None else window
        if w is None:
            return True
        t = _mtime(p)
        return w[0] <= t <= w[1]

    def _belongs_to_session(p: Path) -> bool:
        """Filename date + mtime must both fall in window (when both present).

        Defeats copy-time false positives: webm files carry the original
        date in the filename, even if mtime reflects the later copy.
        """
        if session_key is not None and p.name.startswith(f"{session_key}_"):
            return True
        fname_t = _filename_epoch(p.name)
        if window is not None and fname_t is not None:
            # Require a tighter fit when filename is date-stamped.
            day_s = 86400
            if not (window[0] - day_s <= fname_t <= window[1] + day_s):
                return False
        return _in_window(p)

    # chrony/  -> scoped dir, keep if any file sits in window
    chrony_dir = root / "chrony"
    if chrony_dir.is_dir() and any(_in_window(c) for c in chrony_dir.iterdir() if c.is_file()):
        buckets["chrony"] = sorted(p for p in chrony_dir.iterdir() if p.is_file() and _in_window(p))

    # ros_logs/ -> opt-in. Filter by UUID v1 timestamp (mtime is useless
    # here: every launch dir was re-stamped by the copy). Scope tight.
    ros_logs_dir = root / "ros_logs"
    if include_ros_logs and ros_logs_dir.is_dir() and window is not None:
        log_root = ros_logs_dir / "log"
        tight = (window[0] - ros_log_pad_s, window[1] + ros_log_pad_s)
        if log_root.is_dir():
            kept: list[Path] = []
            for sub in log_root.iterdir():
                if not sub.is_dir():
                    continue
                uuid_t = _uuid1_epoch(sub.name)
                if uuid_t is None:
                    continue
                if tight[0] <= uuid_t <= tight[1]:
                    kept.append(sub)
            buckets["ros_logs"] = sorted(kept)

    # Walk top level + limited depth for audio/video/logs.
    def _walk(p: Path, depth: int):
        if depth > max_depth:
            return
        for child in sorted(p.iterdir()):
            if child.name in {"chrony", "ros_logs"}:
                continue
            if child.is_dir():
                _walk(child, depth + 1)
                continue
            if child.suffix == ".bag":
                continue  # bags handled separately
            if _is_ros2_bag_dir(child):
                continue
            ext = child.suffix.lower()
            if not _belongs_to_session(child):
                continue
            if ext in _AUDIO_EXT:
                buckets["audio"].append(child)
            elif ext in _VIDEO_EXT:
                buckets["video"].append(child)
            elif ext in _LOG_EXT:
                buckets["logs"].append(child)
            else:
                buckets["other"].append(child)

    _walk(root, 0)
    for k in buckets:
        buckets[k] = sorted(set(buckets[k]))
    return buckets


# -------- public API --------------------------------------------------------


def discover_session_assets(
    path: str | Path,
    session_key: str | None = None,
    mtime_pad_s: float = 3600.0,
    include_ros_logs: bool = False,
) -> SessionAssets:
    """Walk `path`, pick the bag session, bucket peripheral assets.

    - `session_key`: force a specific prefix like "2"; otherwise pick the
      heaviest group by total bag size.
    - `mtime_pad_s`: slack on either side of the bag mtime range when
      filtering peripheral files. Default 1 day (covers copy-skew).
    """
    root = Path(path)
    if not root.exists():
        return SessionAssets(root=root, session_key=None)

    # Single bag or ROS2 bag dir shortcut — no need to bucket peripherals.
    if (root.is_file() and root.suffix == ".bag") or _is_ros2_bag_dir(root):
        if root.is_file():
            prefix = _session_prefix(root.name)
            siblings = sorted(
                p for p in root.parent.glob(f"{prefix}_*.bag")
                if p.is_file()
            ) if prefix else [root]
            assets = SessionAssets(root=root.parent, session_key=prefix, bags=siblings or [root])
        else:
            assets = SessionAssets(root=root.parent, session_key=None, bags=[root])
        assets.mtime_window = _mtime_window(assets.bags, mtime_pad_s)
        return assets

    # Full folder handling.
    bags_all = _collect_bag_candidates(root)
    key, session_bags = _pick_session(bags_all, session_key)
    window = _mtime_window(session_bags, mtime_pad_s)
    peripheral = _bucket_peripheral(root, key, window, include_ros_logs=include_ros_logs)

    return SessionAssets(
        root=root,
        session_key=key,
        bags=session_bags,
        audio=peripheral["audio"],
        video=peripheral["video"],
        logs=peripheral["logs"],
        chrony=peripheral["chrony"],
        ros_logs=peripheral["ros_logs"],
        other=peripheral["other"],
        mtime_window=window,
    )


def discover_session_bags(path: str | Path, session_key: str | None = None) -> list[Path]:
    """Back-compat: just the bags. Use `discover_session_assets` for more."""
    return discover_session_assets(path, session_key=session_key).bags


def describe_session(paths: list[Path]) -> str:
    if not paths:
        return "(empty)"
    total_mb = sum(_file_bytes(p) for p in paths) / (1024 * 1024)
    return f"{len(paths)} bag(s), {total_mb:,.0f} MB: " + ", ".join(p.name for p in paths)
