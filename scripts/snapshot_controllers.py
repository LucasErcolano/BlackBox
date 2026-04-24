# SPDX-License-Identifier: MIT
"""Freeze a copy of the NAO6 controllers at fall-trigger time.

Writes controller sources verbatim into an output directory along with a
manifest containing git SHA, timestamp, Python version, and per-file hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROLLERS_DIR = REPO_ROOT / "src" / "black_box" / "platforms" / "nao6" / "controllers"


def _git_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return "no-git"
    if result.returncode != 0:
        return "no-git"
    sha = result.stdout.strip()
    return sha or "no-git"


def _hash_file(path: Path) -> tuple[str, int, int]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    line_count = data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
    return digest, len(data), line_count


def snapshot(case_key: str, out_dir: Path) -> dict:
    if not CONTROLLERS_DIR.is_dir():
        print(
            f"error: controllers directory not found at {CONTROLLERS_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)

    out_dir = Path(out_dir)
    snapshot_dir = out_dir / "controllers_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    controllers = sorted(CONTROLLERS_DIR.glob("*.py"))
    entries: list[dict] = []
    for src in controllers:
        dest = snapshot_dir / src.name
        dest.write_bytes(src.read_bytes())
        digest, size, lines = _hash_file(dest)
        entries.append(
            {
                "filename": src.name,
                "sha256": digest,
                "size_bytes": size,
                "line_count": lines,
            }
        )

    sha = _git_sha(REPO_ROOT)
    manifest = {
        "case_key": case_key,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": sha,
        "python_version": sys.version.split()[0],
        "controllers": entries,
    }

    manifest_path = out_dir / "snapshot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    short = sha[:8] if sha != "no-git" else "no-git"
    print(f"snapshotted {len(entries)} controllers to {out_dir} (sha {short})")
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snapshot NAO6 controllers at fall-trigger time."
    )
    parser.add_argument(
        "--case-key",
        required=True,
        help="Case identifier (e.g. c1_faceplant)",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output directory for the snapshot",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    snapshot(args.case_key, args.out)
