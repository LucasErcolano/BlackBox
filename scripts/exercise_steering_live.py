# SPDX-License-Identifier: MIT
"""Live exercise of the steering consumer (#129).

Boots the FastAPI app on a private port, kicks off a real /analyze
against a chosen bag (default: the sanfer hero bag), waits for the
analyzing stage, posts a steer message, then watches the reasoning
buffer for the corresponding ``[steer] -> agent`` line.

This is the operator-on-API-budget verification that the consumer side
of #105 works end-to-end. Unit tests already prove the wire (see
``tests/test_steer_consumer.py``); this script is for the demo capture.

Usage
-----
    export ANTHROPIC_API_KEY=...
    python scripts/exercise_steering_live.py \
        --bag data/bags/1_cam-lidar.bag \
        --message "focus on RTK degradation window before the tunnel"

Cost ceiling: bounded by the live worker's task budget (default 7 min)
times Opus 4.7 list. Empirically <$5 on the sanfer hero. Abort with
Ctrl-C is honoured — the worker drops to the ``failed`` stage cleanly.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_up(base: str, timeout: float = 30.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(base + "/", timeout=1.0) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.4)
    raise TimeoutError(f"uvicorn did not come up at {base}")


def _post_form(url: str, fields: dict[str, str]) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10.0) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bag", type=Path, default=ROOT / "data" / "bags" / "1_cam-lidar.bag")
    p.add_argument(
        "--message",
        default="focus on RTK degradation window before the tunnel",
        help="The steer message to inject mid-stream.",
    )
    p.add_argument("--steer-after-s", type=float, default=20.0,
                   help="Seconds to wait after analyze before posting the steer.")
    p.add_argument("--watch-window-s", type=float, default=180.0,
                   help="Seconds to watch the reasoning buffer for confirmation.")
    args = p.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set; this script is the live exercise.", file=sys.stderr)
        return 2
    if not args.bag.exists():
        print(f"ERROR: bag not found: {args.bag}", file=sys.stderr)
        return 2

    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["BLACKBOX_REAL_PIPELINE"] = "1"

    cmd = [
        sys.executable, "-m", "uvicorn",
        "black_box.ui.app:app",
        "--host", "127.0.0.1", "--port", str(port),
        "--log-level", "warning",
    ]
    proc = subprocess.Popen(cmd, env=env, cwd=str(ROOT))
    try:
        _wait_up(base)
        job_id = "exercise" + uuid.uuid4().hex[:6]

        # Multipart upload via stdlib
        boundary = "----steerexercise"
        body = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{args.bag.name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        body += args.bag.read_bytes()
        body += f"\r\n--{boundary}\r\n".encode()
        body += b"Content-Disposition: form-data; name=\"mode\"\r\n\r\npost_mortem\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"{base}/analyze?job_id={job_id}", data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(req, timeout=120.0) as r:
            print(f"analyze posted: status={r.status} job_id={job_id}")

        print(f"sleeping {args.steer_after_s:.0f}s before posting steer...")
        time.sleep(args.steer_after_s)
        code, _ = _post_form(f"{base}/steer/{job_id}", {"message": args.message})
        print(f"steer posted: status={code} message={args.message!r}")

        deadline = time.time() + args.watch_window_s
        seen = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{base}/status/{job_id}.json" if False else f"{base}/status/{job_id}",
                                            timeout=5.0) as r:
                    body = r.read().decode("utf-8", errors="replace")
                if f"[steer] -> agent: {args.message}" in body:
                    seen = True
                    print(f"CONFIRMED: steer line surfaced in /status after "
                          f"{int(time.time() - deadline + args.watch_window_s)}s")
                    break
            except Exception as e:
                print(f"poll error: {e!r}")
            time.sleep(3.0)

        if not seen:
            print("FAILED: steer line never surfaced — drop the steering claim from the video.")
            return 1
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
