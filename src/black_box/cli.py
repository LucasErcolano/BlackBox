# SPDX-License-Identifier: MIT
"""``blackbox`` command-line entry point.

Subcommands:

    analyze <bag> --mode ...    run the forensic pipeline on a recording
    serve                       start the FastAPI UI (uvicorn)
    bench [--use-claude]        run the tier-3 eval
    synth materialize           generate synthetic bench cases
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


# --- analyze ----------------------------------------------------------------
def _cmd_analyze(args: argparse.Namespace) -> int:
    bag = Path(args.bag)
    if not bag.exists():
        print(f"error: {bag} not found", file=sys.stderr)
        return 2
    # TODO(pipeline): wire ingestion -> claude_client -> reporting.
    print(f"[analyze] mode={args.mode} bag={bag}")
    print("[analyze] real pipeline not wired yet; use `blackbox serve` for the stub UI.")
    return 0


# --- serve ------------------------------------------------------------------
def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn  # type: ignore
    except Exception as e:
        print(f"error: uvicorn not installed ({e!r})", file=sys.stderr)
        return 2
    uvicorn.run(
        "black_box.ui.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


# --- bench ------------------------------------------------------------------
def _cmd_bench(args: argparse.Namespace) -> int:
    from black_box.eval.runner import main as eval_main

    argv: list[str] = []
    if args.case_dir:
        argv += ["--case-dir", str(args.case_dir)]
    if args.use_claude:
        argv.append("--use-claude")
    if args.case:
        argv += ["--case", args.case]
    return eval_main(argv)


# --- synth ------------------------------------------------------------------
def _cmd_synth(args: argparse.Namespace) -> int:
    if args.synth_cmd == "materialize":
        try:
            # Parallel agent owns this module; import lazily.
            from black_box.synthesis import materialize  # type: ignore
        except Exception as e:
            print(f"[synth] synthesis.materialize not available yet: {e!r}")
            print("[synth] TODO: wire once synthesis module lands.")
            return 0
        out = materialize()  # type: ignore[call-arg]
        print(f"[synth] materialized -> {out}")
        return 0
    print(f"unknown synth subcommand: {args.synth_cmd}", file=sys.stderr)
    return 2


# --- main -------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    from black_box import __version__

    p = argparse.ArgumentParser(prog="blackbox", description="Black Box CLI")
    p.add_argument("--version", action="version", version=f"black-box {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("analyze", help="analyze a recording")
    pa.add_argument("bag")
    pa.add_argument(
        "--mode",
        choices=["post_mortem", "scenario_mining", "synthetic_qa"],
        default="post_mortem",
    )
    pa.set_defaults(func=_cmd_analyze)

    ps = sub.add_parser("serve", help="run the FastAPI UI")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8000)
    ps.add_argument("--reload", action="store_true")
    ps.set_defaults(func=_cmd_serve)

    pb = sub.add_parser("bench", help="run the tier-3 eval")
    pb.add_argument("--case-dir", type=Path, default=None)
    pb.add_argument("--use-claude", action="store_true")
    pb.add_argument("--case", default=None)
    pb.set_defaults(func=_cmd_bench)

    psy = sub.add_parser("synth", help="synthetic bench tools")
    psy.add_argument("synth_cmd", choices=["materialize"])
    psy.set_defaults(func=_cmd_synth)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
