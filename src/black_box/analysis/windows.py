"""Suspicious-window extraction.

Drives the two-pass vision pipeline: cheap telemetry pass first, then the
agent (or generic detectors) nominate timestamps worth densifying frames
around. The ingestion frame-sampler takes these windows and decides where
to spend its image budget.

Design choices:

- A `Window` is (center_ns, span_s, label, priority). No dependency on a
  specific bag schema — the sampler does not care what produced the window.
- Detectors are small numpy helpers with no hidden state, easy to unit test.
- `from_timeline` pulls windows out of an already-produced analysis.json so
  we can feed the *same* agent timeline back in for a second, densified
  vision pass without re-reasoning on the whole telemetry from scratch.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


@dataclass
class Window:
    center_ns: int
    span_s: float
    label: str
    priority: float = 0.5  # 0..1, higher = worth more dense frames

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def start_ns(self) -> int:
        return int(self.center_ns - self.span_s * 1e9 / 2)

    @property
    def end_ns(self) -> int:
        return int(self.center_ns + self.span_s * 1e9 / 2)


# -------- detectors over raw telemetry --------------------------------------


def from_flag_transitions(
    t_ns: np.ndarray,
    values: np.ndarray,
    label_prefix: str,
    span_s: float = 30.0,
    priority: float = 0.7,
    max_transitions: int = 6,
) -> list[Window]:
    """Any change in a categorical/boolean sequence is a candidate window.

    Picks the first `max_transitions` transitions after the initial sample
    (the initial value is not a transition by itself — flagged elsewhere).
    """
    if len(t_ns) < 2 or len(t_ns) != len(values):
        return []
    # Identify indices where value changes vs previous sample.
    changes: list[int] = []
    prev = values[0]
    for i in range(1, len(values)):
        if values[i] != prev:
            changes.append(i)
            prev = values[i]
            if len(changes) >= max_transitions:
                break
    out: list[Window] = []
    for i in changes:
        out.append(Window(
            center_ns=int(t_ns[i]),
            span_s=span_s,
            label=f"{label_prefix} {values[i-1]!r}->{values[i]!r}",
            priority=priority,
        ))
    return out


def from_gaps(
    t_ns: np.ndarray,
    min_gap_s: float,
    label: str,
    span_s: float = 30.0,
    priority: float = 0.8,
    max_gaps: int = 5,
) -> list[Window]:
    """Stretches between consecutive samples exceeding `min_gap_s`."""
    if len(t_ns) < 2:
        return []
    dt_s = np.diff(t_ns).astype(np.float64) / 1e9
    idx = np.where(dt_s >= min_gap_s)[0]
    # Largest gaps first, up to max_gaps.
    idx = idx[np.argsort(-dt_s[idx])][:max_gaps]
    out: list[Window] = []
    for i in idx:
        # Center the window on the gap's midpoint.
        mid = int(t_ns[i]) + int(dt_s[i] * 1e9 / 2)
        out.append(Window(
            center_ns=mid,
            span_s=max(span_s, dt_s[i] + 10.0),
            label=f"{label} gap {dt_s[i]:.1f}s",
            priority=priority,
        ))
    return out


def from_error_bursts(
    t_ns: np.ndarray,
    bucket_s: float = 5.0,
    min_errors_per_bucket: int = 5,
    label: str = "error burst",
    span_s: float = 20.0,
    priority: float = 0.6,
    max_bursts: int = 5,
) -> list[Window]:
    """Given a list of error-event timestamps, find density peaks."""
    if len(t_ns) == 0:
        return []
    t_s = t_ns.astype(np.float64) / 1e9
    t0 = t_s[0]
    bucket_idx = ((t_s - t0) // bucket_s).astype(np.int64)
    # Count per bucket (numpy bincount on non-negative ints).
    bc = np.bincount(bucket_idx)
    hot = np.where(bc >= min_errors_per_bucket)[0]
    if hot.size == 0:
        return []
    # Take the densest `max_bursts`.
    hot = hot[np.argsort(-bc[hot])][:max_bursts]
    out: list[Window] = []
    for b in hot:
        center_s = t0 + (b + 0.5) * bucket_s
        out.append(Window(
            center_ns=int(center_s * 1e9),
            span_s=span_s,
            label=f"{label} ({int(bc[b])} evts/{bucket_s:.0f}s)",
            priority=priority,
        ))
    return out


# -------- entry point: from an existing analysis.json ----------------------


def from_timeline(
    analysis: dict,
    bag_start_ns: int = 0,
    default_span_s: float = 30.0,
    keep_cross_view_only: bool = False,
) -> list[Window]:
    """Lift the agent's own timeline bullets into Window objects.

    The analysis pipeline stores timeline entries as:
        {"t_ns": <relative ns from bag start>, "label": "...", "cross_view": bool}

    `bag_start_ns` is added so returned windows use absolute ns if caller
    needs it. Pass 0 to keep everything relative.
    """
    tl = analysis.get("timeline") or []
    out: list[Window] = []
    for entry in tl:
        if keep_cross_view_only and not entry.get("cross_view"):
            continue
        t_rel = int(entry.get("t_ns", 0))
        out.append(Window(
            center_ns=bag_start_ns + t_rel,
            span_s=float(entry.get("span_s") or default_span_s),
            label=str(entry.get("label", "")).strip()[:200],
            priority=0.7 if entry.get("cross_view") else 0.5,
        ))
    return out


# -------- deduplication ----------------------------------------------------


def merge_overlapping(
    windows: Sequence[Window], merge_gap_s: float = 5.0
) -> list[Window]:
    """Sort by center, merge any pair that overlaps (or is within merge_gap_s).

    When merging, keep the maximum priority and concatenate labels (truncated).
    """
    if not windows:
        return []
    ordered = sorted(windows, key=lambda w: w.center_ns)
    out: list[Window] = [ordered[0]]
    for w in ordered[1:]:
        last = out[-1]
        if w.start_ns - last.end_ns <= merge_gap_s * 1e9:
            new_start = min(last.start_ns, w.start_ns)
            new_end = max(last.end_ns, w.end_ns)
            merged = Window(
                center_ns=(new_start + new_end) // 2,
                span_s=(new_end - new_start) / 1e9,
                label=f"{last.label} | {w.label}"[:240],
                priority=max(last.priority, w.priority),
            )
            out[-1] = merged
        else:
            out.append(w)
    return out


def top_k(windows: Sequence[Window], k: int) -> list[Window]:
    return sorted(windows, key=lambda w: -w.priority)[:k]


# -------- convenience: dump / load -----------------------------------------


def dump(windows: Iterable[Window], path: Path) -> None:
    import json
    path.write_text(json.dumps([w.to_dict() for w in windows], indent=2))


def load(path: Path) -> list[Window]:
    import json
    return [Window(**d) for d in json.loads(Path(path).read_text())]
