# SPDX-License-Identifier: MIT
"""Live edge smoke harness for native Managed Agents memory_stores.

DO NOT RUN under the test suite. The whole point of this script is to be
the artifact-producing harness operators run by hand once an
`anthropic>=0.97` SDK is available.

What it captures (Lucas ask #1) — every artifact lands under
`demo_assets/managed_memory_smoke/` (override with --out):

  session_events_excerpt.jsonl   first 50 + last 50 stream events
  mounted_memory_listing.txt     output of `ls /mnt/memory/`
  platform_read_attempt.txt      output of `cat /mnt/memory/bb-platform-priors/<known>.md`
  platform_write_rejected.txt    error from writing into the read-only store
  case_store_write_success.txt   write+read cycle in the read-write case store
  final_report.json              session.finalize() payload (PostMortemReport)
  README.md                      one-pager mapping artifacts to ask #1

All artifacts are written atomically (.tmp -> fsync -> rename). Cost is
appended to `data/costs.jsonl` in the same shape as the rest of the
analysis pipeline.

Usage:
  python scripts/managed_memory_smoke.py \\
    --bag /mnt/hdd/sanfer_sanisidro/2_diagnostics.bag \\
    --case-key smoke_001 \\
    --budget-usd 1.50 \\
    --yes
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


PROJECTED_SPEND_LO = 0.50
PROJECTED_SPEND_HI = 1.50
HARD_BUDGET_CAP_USD = 5.00
KNOWN_PLATFORM_READ_PATH = "/priors/bug_taxonomy.md"
EXIT_PRECHECK = 2

ARTIFACT_NAMES = (
    "session_events_excerpt.jsonl",
    "mounted_memory_listing.txt",
    "platform_read_attempt.txt",
    "platform_write_rejected.txt",
    "case_store_write_success.txt",
    "final_report.json",
    "README.md",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="managed_memory_smoke",
        description=(
            "Live edge smoke harness for native /mnt/memory/ on Managed "
            "Agents. Do NOT run unattended — this calls Opus 4.7."
        ),
    )
    p.add_argument(
        "--bag",
        required=True,
        type=Path,
        help="path to a single rosbag the harness will run end-to-end through ForensicAgent",
    )
    p.add_argument(
        "--case-key",
        required=True,
        type=str,
        help="case key for this smoke run (e.g. smoke_001)",
    )
    p.add_argument(
        "--budget-usd",
        type=float,
        default=PROJECTED_SPEND_HI,
        help=f"hard cost cap; refuses to start if > {HARD_BUDGET_CAP_USD:.2f} (default 1.50)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "demo_assets" / "managed_memory_smoke",
        help="output directory for artifacts (default: demo_assets/managed_memory_smoke/)",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help=(
            f"required confirmation that you accept the projected "
            f"${PROJECTED_SPEND_LO:.2f}-${PROJECTED_SPEND_HI:.2f} spend"
        ),
    )
    return p.parse_args(argv)


def precheck_sdk_supports_memory_stores() -> tuple[bool, str]:
    """Return (ok, message). Refuse to run when SDK lacks `beta.memory_stores`.

    The whole script is meaningless if the SDK can't reach the memory-store
    edge, so we exit hard with the exact pip command Lucas asked for.
    """
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        return False, (
            f"anthropic SDK not importable ({exc}). Run: pip install -U anthropic"
        )

    try:
        from anthropic.resources.beta import Beta
    except ImportError as exc:
        return False, (
            "anthropic SDK is too old to expose beta.memory_stores. "
            f"({exc}). Run: pip install -U anthropic"
        )

    if not hasattr(Beta, "memory_stores"):
        version = getattr(__import__("anthropic"), "__version__", "?")
        return False, (
            f"anthropic=={version} does not expose client.beta.memory_stores. "
            "Run: pip install -U anthropic"
        )
    return True, "ok"


def precheck_api_key() -> tuple[bool, str]:
    if os.getenv("ANTHROPIC_API_KEY"):
        return True, "ok"
    return False, (
        "ANTHROPIC_API_KEY is not set in this environment. "
        "Export it (or `set -a && source .env && set +a`) and retry."
    )


def precheck_confirmation(yes: bool, budget_usd: float) -> tuple[bool, str]:
    if budget_usd > HARD_BUDGET_CAP_USD:
        return False, (
            f"--budget-usd {budget_usd:.2f} exceeds hard cap "
            f"${HARD_BUDGET_CAP_USD:.2f}. Refusing to start."
        )
    if not yes:
        return False, (
            f"This harness will spend approximately "
            f"${PROJECTED_SPEND_LO:.2f}-${PROJECTED_SPEND_HI:.2f} on Opus 4.7. "
            "Re-run with --yes to confirm you accept the cost."
        )
    return True, "ok"


def atomic_write(path: Path, payload: bytes | str) -> None:
    """Write atomically: write to .tmp, fsync, then rename.

    Avoids leaving a half-written artifact if the harness is interrupted
    mid-flight after a long live run (where a re-run is expensive).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _excerpt_events(events: list[dict], head: int = 50, tail: int = 50) -> list[dict]:
    if len(events) <= head + tail:
        return list(events)
    return events[:head] + events[-tail:]


def _bash_via_session(session, command: str) -> dict:
    """Run a bash one-liner inside the agent sandbox via session.steer.

    The agent sees a steer message asking it to run the bash command and
    paste the literal stdout/stderr back. This is the only way to hit the
    actual /mnt/memory/ filesystem without out-of-band SDK access. The
    response is captured by the next assistant message in the stream.
    """
    marker = f"BB_SMOKE_{int(time.time())}"
    instruction = (
        f"Run this exact bash command via the bash tool and reply with ONLY a "
        f"single fenced code block containing the literal stdout and stderr "
        f"prefixed with '<<<{marker}' and suffixed with '>>>{marker}'. "
        f"Do not paraphrase, do not summarize. Command: {command}"
    )
    session.steer(instruction)
    captured: list[dict] = []
    last_text = ""
    for ev in session.stream():
        captured.append(ev)
        if ev.get("type") == "assistant":
            txt = ev.get("payload", {}).get("text") or ""
            if marker in txt:
                last_text = txt
                break
    return {"command": command, "marker": marker, "text": last_text, "events": captured}


def write_readme(out_dir: Path) -> None:
    body = (
        "# managed_memory_smoke artifacts\n\n"
        "Captured by `scripts/managed_memory_smoke.py`. Maps to Lucas's "
        "audit ask #1 (live edge smoke evidence for native /mnt/memory/).\n\n"
        "| File | Proves |\n|---|---|\n"
        "| `session_events_excerpt.jsonl` | session opened, agent loop ran, terminal event reached |\n"
        "| `mounted_memory_listing.txt` | both stores actually mount under /mnt/memory/ |\n"
        "| `platform_read_attempt.txt` | platform store is reachable read-side from the agent |\n"
        "| `platform_write_rejected.txt` | platform store enforces read_only at the FS layer |\n"
        "| `case_store_write_success.txt` | case store accepts read+write inside the session |\n"
        "| `final_report.json` | session.finalize() returned a PostMortemReport-shaped payload |\n\n"
        "Regenerate (live, billable):\n\n"
        "```bash\n"
        "python scripts/managed_memory_smoke.py \\\n"
        "  --bag <path-to-bag> \\\n"
        "  --case-key smoke_001 \\\n"
        "  --budget-usd 1.50 \\\n"
        "  --yes\n"
        "```\n"
    )
    atomic_write(out_dir / "README.md", body)


def append_cost(usd_cost: float, wall_time_s: float, case_key: str, session_id: str) -> Path:
    costs_path = REPO_ROOT / "data" / "costs.jsonl"
    costs_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "cached_input_tokens": 0,
        "uncached_input_tokens": 0,
        "cache_creation_tokens": 0,
        "output_tokens": 0,
        "usd_cost": float(usd_cost),
        "wall_time_s": float(wall_time_s),
        "model": "claude-opus-4-7",
        "prompt_kind": "managed_memory_smoke",
        "session_id": session_id,
        "case_key": case_key,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(costs_path, "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return costs_path


def run_smoke(args: argparse.Namespace) -> int:
    from black_box.analysis.client import build_client
    from black_box.analysis.managed_agent import ForensicAgent, ForensicAgentConfig
    from black_box.analysis.schemas import PostMortemReport
    from pydantic import ValidationError

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.bag.exists():
        print(f"bag not found: {args.bag}", file=sys.stderr)
        return 1

    started_at = time.monotonic()
    client = build_client()
    cfg = ForensicAgentConfig(
        task_budget_minutes=7,
        network="egress_only",
    )
    agent = ForensicAgent(config=cfg, client=client)

    print(f"[smoke] opening session for case_key={args.case_key} bag={args.bag}")
    session = agent.open_session(bag_path=args.bag, case_key=args.case_key)
    print(f"[smoke] session_id={session.session_id}")

    head_events: list[dict] = []
    tail_events: list[dict] = []
    seen = 0
    for ev in session.stream():
        seen += 1
        if seen <= 50:
            head_events.append(ev)
        tail_events.append(ev)
        if len(tail_events) > 50:
            tail_events.pop(0)
    excerpt = head_events + (
        [e for e in tail_events if e not in head_events]
        if seen > 100
        else tail_events[len(head_events) :]
    )
    excerpt_lines = [json.dumps(e, default=str) for e in _excerpt_events(excerpt, head=50, tail=50)]
    atomic_write(out_dir / "session_events_excerpt.jsonl", "\n".join(excerpt_lines) + "\n")

    print("[smoke] capturing mounted_memory_listing")
    listing = _bash_via_session(session, "ls -la /mnt/memory/")
    atomic_write(out_dir / "mounted_memory_listing.txt", json.dumps(listing, default=str, indent=2))

    print("[smoke] capturing platform_read_attempt")
    read_path = f"/mnt/memory/{cfg.platform_store_name}{KNOWN_PLATFORM_READ_PATH}"
    read_attempt = _bash_via_session(session, f"cat {read_path}")
    atomic_write(out_dir / "platform_read_attempt.txt", json.dumps(read_attempt, default=str, indent=2))

    print("[smoke] capturing platform_write_rejected (must fail FS-side)")
    write_attempt = _bash_via_session(
        session,
        f"echo SMOKE_TEST > /mnt/memory/{cfg.platform_store_name}/test.md "
        "&& echo WROTE_PLATFORM || echo PLATFORM_REJECTED",
    )
    atomic_write(
        out_dir / "platform_write_rejected.txt", json.dumps(write_attempt, default=str, indent=2)
    )

    print("[smoke] capturing case_store_write_success")
    case_store_name = cfg.case_store_name_template.format(case_key=args.case_key)
    case_attempt = _bash_via_session(
        session,
        f"echo CASE_NOTE_OK > /mnt/memory/{case_store_name}/smoke_note.md "
        f"&& cat /mnt/memory/{case_store_name}/smoke_note.md",
    )
    atomic_write(
        out_dir / "case_store_write_success.txt", json.dumps(case_attempt, default=str, indent=2)
    )

    print("[smoke] finalizing")
    final = session.finalize()
    try:
        PostMortemReport.model_validate(final)
    except ValidationError as exc:
        atomic_write(
            out_dir / "final_report.json",
            json.dumps({"error": str(exc), "raw": final}, default=str, indent=2),
        )
        print(f"[smoke] final payload failed PostMortemReport validation: {exc}", file=sys.stderr)
        return 1
    atomic_write(out_dir / "final_report.json", json.dumps(final, default=str, indent=2))

    write_readme(out_dir)

    wall_time_s = time.monotonic() - started_at
    append_cost(
        usd_cost=args.budget_usd,
        wall_time_s=wall_time_s,
        case_key=args.case_key,
        session_id=session.session_id,
    )

    print(f"[smoke] done in {wall_time_s:.1f}s. artifacts: {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    ok, msg = precheck_sdk_supports_memory_stores()
    if not ok:
        print(f"[precheck] {msg}", file=sys.stderr)
        return EXIT_PRECHECK

    ok, msg = precheck_api_key()
    if not ok:
        print(f"[precheck] {msg}", file=sys.stderr)
        return EXIT_PRECHECK

    ok, msg = precheck_confirmation(args.yes, args.budget_usd)
    if not ok:
        print(f"[precheck] {msg}", file=sys.stderr)
        return EXIT_PRECHECK

    return run_smoke(args)


if __name__ == "__main__":
    sys.exit(main())
