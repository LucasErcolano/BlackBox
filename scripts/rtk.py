"""Rust Token Killer (RTK) — terminal-output filter (Python impl).

Sits between shell commands and any Claude-facing transcript. Three jobs:

1. Strip ANSI escape sequences (colors, cursor moves, title sets).
2. Collapse runs of identical lines into `<line> (repeated N×)`.
3. Deduplicate Python-style stack frame blocks across retries (same
   filename+lineno+func seen more than once → later copies elided).
4. Hard-cap total output at a configurable byte budget (default 16 KB).

Can be used as a library (``from rtk import filter_text, run``) or CLI
(``python scripts/rtk.py -- cmd args``). Every wrapped subprocess call
appends a record to ``data/costs.jsonl`` with ``stdout_bytes_saved`` so
savings are auditable alongside Claude call costs.

Opt-out: pass ``--no-rtk`` to the CLI or ``apply_filter=False`` to the
library ``run()`` helper. Filter is pure-Python, no deps.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

DEFAULT_BUDGET_BYTES = 16 * 1024  # 16 KB
TRUNCATION_NOTICE = "\n... [rtk: truncated to {budget} B of {orig} B]"

# ANSI CSI/OSC/escape sequences. Covers color codes, cursor moves, title sets.
_ANSI_RE = re.compile(
    r"""
    \x1B           # ESC
    (?:            # either...
        \[ [0-?]* [ -/]* [@-~]          # CSI ... final byte
      | \] .*? (?: \x07 | \x1B\\ )      # OSC ... BEL or ST
      | [@-Z\\-_]                        # single-char escape (C1 7-bit)
    )
    """,
    re.VERBOSE,
)

# Python traceback frame: `  File "path", line N, in func`
_PY_FRAME_RE = re.compile(r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<fn>\S+)')


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@dataclass
class FilterStats:
    """Byte accounting for a single filter invocation."""
    stdout_bytes_original: int
    stdout_bytes_filtered: int
    lines_original: int
    lines_filtered: int
    repeated_runs_collapsed: int
    frames_deduped: int
    truncated: bool

    @property
    def stdout_bytes_saved(self) -> int:
        return max(0, self.stdout_bytes_original - self.stdout_bytes_filtered)

    @property
    def reduction_ratio(self) -> float:
        if self.stdout_bytes_original == 0:
            return 0.0
        return self.stdout_bytes_saved / self.stdout_bytes_original


# ---------------------------------------------------------------------------
# Core filter
# ---------------------------------------------------------------------------


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from `text`."""
    return _ANSI_RE.sub("", text)


def _normalize_for_dedupe(line: str) -> str:
    """Dedupe key for consecutive-line collapse.

    Trims trailing whitespace only — preserving leading indent so tracebacks
    don't fold into each other. Timestamps and PID-style tokens are NOT
    normalized here: if the caller wants fuzzy dedupe, it can pre-process.
    """
    return line.rstrip()


def _collapse_repeats(lines: Sequence[str]) -> tuple[list[str], int]:
    """Fold consecutive duplicate lines. Returns (out_lines, runs_collapsed)."""
    out: list[str] = []
    runs = 0
    i = 0
    n = len(lines)
    while i < n:
        key = _normalize_for_dedupe(lines[i])
        j = i + 1
        while j < n and _normalize_for_dedupe(lines[j]) == key:
            j += 1
        if j - i >= 3:
            # Keep one representative, annotate remainder.
            out.append(lines[i])
            out.append(f"    (repeated {j - i}x)")
            runs += 1
        else:
            out.extend(lines[i:j])
        i = j
    return out, runs


def _dedupe_py_frames(lines: Sequence[str]) -> tuple[list[str], int]:
    """Elide later occurrences of identical Python stack frames.

    A "frame" = the `File "...", line N, in fn` line plus its immediate
    indented code line (if present). We keep the FIRST full occurrence of
    each (file, lineno, fn); subsequent copies within the stream collapse
    to a one-line marker so retried tracebacks don't balloon the transcript.
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[str] = []
    deduped = 0
    i = 0
    n = len(lines)
    while i < n:
        m = _PY_FRAME_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        key = (m["file"], m["line"], m["fn"])
        # Frame line plus optional next-line code body (leading 4-space indent).
        has_body = (
            i + 1 < n
            and lines[i + 1].startswith("    ")
            and not _PY_FRAME_RE.match(lines[i + 1])
        )
        if key in seen:
            out.append(f'  File "{key[0]}", line {key[1]}, in {key[2]} (deduped)')
            i += 2 if has_body else 1
            deduped += 1
            continue
        seen.add(key)
        out.append(lines[i])
        if has_body:
            out.append(lines[i + 1])
            i += 2
        else:
            i += 1
    return out, deduped


def _apply_budget(text: str, budget_bytes: int) -> tuple[str, bool]:
    """Truncate `text` to at most `budget_bytes` (UTF-8). Returns (text, truncated)."""
    raw = text.encode("utf-8")
    if len(raw) <= budget_bytes:
        return text, False
    notice = TRUNCATION_NOTICE.format(budget=budget_bytes, orig=len(raw))
    notice_bytes = notice.encode("utf-8")
    head_room = max(0, budget_bytes - len(notice_bytes))
    head = raw[:head_room].decode("utf-8", errors="ignore")
    return head + notice, True


def filter_text(text: str, budget_bytes: int = DEFAULT_BUDGET_BYTES) -> tuple[str, FilterStats]:
    """Run the full RTK pipeline on `text`.

    Stages: ANSI strip → collapse repeats → dedupe Python frames → budget cap.
    Returns filtered text and byte-accounting stats.
    """
    orig_bytes = len(text.encode("utf-8"))
    orig_line_count = text.count("\n") + (0 if text.endswith("\n") or not text else 1)

    stripped = strip_ansi(text)
    trailing_nl = stripped.endswith("\n")
    lines = stripped.split("\n")
    if trailing_nl:
        lines = lines[:-1]

    collapsed, runs = _collapse_repeats(lines)
    deduped, dedup_count = _dedupe_py_frames(collapsed)

    joined = "\n".join(deduped)
    if trailing_nl and joined:
        joined += "\n"

    capped, truncated = _apply_budget(joined, budget_bytes)
    final_bytes = len(capped.encode("utf-8"))
    final_line_count = capped.count("\n") + (0 if capped.endswith("\n") or not capped else 1)

    return capped, FilterStats(
        stdout_bytes_original=orig_bytes,
        stdout_bytes_filtered=final_bytes,
        lines_original=orig_line_count,
        lines_filtered=final_line_count,
        repeated_runs_collapsed=runs,
        frames_deduped=dedup_count,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Cost log
# ---------------------------------------------------------------------------


def _find_repo_root(start: Path | None = None) -> Path:
    """Walk up until pyproject.toml is found."""
    current = (start or Path(__file__)).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return (start or Path(__file__)).resolve().parent


def _costs_path() -> Path:
    root = _find_repo_root()
    costs_dir = root / "data"
    costs_dir.mkdir(parents=True, exist_ok=True)
    return costs_dir / "costs.jsonl"


def log_filter_stats(
    command: str,
    stats: FilterStats,
    wall_time_s: float,
    stream: str = "stdout",
    costs_file: Path | None = None,
) -> None:
    """Append an RTK record to data/costs.jsonl.

    Record is distinguishable from Claude-call records by `kind="rtk"` and
    carries the `stdout_bytes_saved` field required by issue #57.
    """
    path = costs_file or _costs_path()
    record = {
        "kind": "rtk",
        "command": command,
        "stream": stream,
        "stdout_bytes_original": stats.stdout_bytes_original,
        "stdout_bytes_filtered": stats.stdout_bytes_filtered,
        "stdout_bytes_saved": stats.stdout_bytes_saved,
        "reduction_ratio": round(stats.reduction_ratio, 4),
        "lines_original": stats.lines_original,
        "lines_filtered": stats.lines_filtered,
        "repeated_runs_collapsed": stats.repeated_runs_collapsed,
        "frames_deduped": stats.frames_deduped,
        "truncated": stats.truncated,
        "wall_time_s": wall_time_s,
        "ts": time.time(),
    }
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------


@dataclass
class RTKResult:
    returncode: int
    stdout: str
    stderr: str
    stats_stdout: FilterStats
    stats_stderr: FilterStats
    wall_time_s: float


def run(
    cmd: Sequence[str] | str,
    *,
    apply_filter: bool = True,
    budget_bytes: int = DEFAULT_BUDGET_BYTES,
    log: bool = True,
    check: bool = False,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    text: bool = True,
) -> RTKResult:
    """Run `cmd` via subprocess, capture+filter stdout/stderr, log savings.

    When `apply_filter=False` (the `--no-rtk` debug path), raw output is
    returned but a zero-savings log record is still written so the audit
    trail is complete.
    """
    shell = isinstance(cmd, str)
    display = cmd if isinstance(cmd, str) else " ".join(cmd)

    t0 = time.time()
    proc = subprocess.run(
        cmd,
        shell=shell,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=text,
        check=False,
    )
    elapsed = time.time() - t0

    raw_out = proc.stdout or ("" if text else b"")
    raw_err = proc.stderr or ("" if text else b"")
    if not text:
        raw_out = raw_out.decode("utf-8", errors="replace")
        raw_err = raw_err.decode("utf-8", errors="replace")

    if apply_filter:
        filt_out, stats_out = filter_text(raw_out, budget_bytes=budget_bytes)
        filt_err, stats_err = filter_text(raw_err, budget_bytes=budget_bytes)
    else:
        orig_o = len(raw_out.encode("utf-8"))
        orig_e = len(raw_err.encode("utf-8"))
        filt_out, filt_err = raw_out, raw_err
        stats_out = FilterStats(
            orig_o, orig_o, raw_out.count("\n"), raw_out.count("\n"), 0, 0, False,
        )
        stats_err = FilterStats(
            orig_e, orig_e, raw_err.count("\n"), raw_err.count("\n"), 0, 0, False,
        )

    if log:
        log_filter_stats(display, stats_out, wall_time_s=elapsed, stream="stdout")
        if raw_err:
            log_filter_stats(display, stats_err, wall_time_s=elapsed, stream="stderr")

    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, output=filt_out, stderr=filt_err,
        )

    return RTKResult(
        returncode=proc.returncode,
        stdout=filt_out,
        stderr=filt_err,
        stats_stdout=stats_out,
        stats_stderr=stats_err,
        wall_time_s=elapsed,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rtk",
        description="Filter subprocess stdout/stderr before it reaches a model.",
    )
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET_BYTES,
                   help=f"Byte cap per stream (default {DEFAULT_BUDGET_BYTES}).")
    p.add_argument("--no-rtk", action="store_true",
                   help="Debug opt-out: pass raw stdout/stderr through unchanged.")
    p.add_argument("--no-log", action="store_true",
                   help="Skip data/costs.jsonl append (for tests/local experiments).")
    p.add_argument("--stdin", action="store_true",
                   help="Read text from stdin and filter it (no subprocess).")
    p.add_argument("argv", nargs=argparse.REMAINDER,
                   help="Command to run (prefix with --).")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.stdin:
        text = sys.stdin.read()
        if args.no_rtk:
            sys.stdout.write(text)
            return 0
        filtered, stats = filter_text(text, budget_bytes=args.budget)
        sys.stdout.write(filtered)
        if not args.no_log:
            log_filter_stats("<stdin>", stats, wall_time_s=0.0, stream="stdout")
        sys.stderr.write(
            f"[rtk] bytes {stats.stdout_bytes_original} -> {stats.stdout_bytes_filtered} "
            f"(saved {stats.stdout_bytes_saved}, "
            f"{stats.reduction_ratio * 100:.1f}%)\n"
        )
        return 0

    # Strip leading "--" separator if argparse left it in.
    cmd = list(args.argv)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        parser.error("no command given (usage: rtk.py [opts] -- cmd args)")

    result = run(
        cmd,
        apply_filter=not args.no_rtk,
        budget_bytes=args.budget,
        log=not args.no_log,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.stderr.write(
        f"[rtk] stdout {result.stats_stdout.stdout_bytes_original} -> "
        f"{result.stats_stdout.stdout_bytes_filtered} B "
        f"(saved {result.stats_stdout.stdout_bytes_saved}, "
        f"{result.stats_stdout.reduction_ratio * 100:.1f}%)  "
        f"runs_collapsed={result.stats_stdout.repeated_runs_collapsed}  "
        f"frames_deduped={result.stats_stdout.frames_deduped}  "
        f"truncated={result.stats_stdout.truncated}\n"
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
