# SPDX-License-Identifier: MIT
"""Helpers for pulling public robotics / incident datasets.

The REFLECT manifest fetcher is shipped end-to-end (network call, parsed
list). The single-asset fetcher (``fetch_asset``) is also live — it is
the boundary we promised in #78. The FAA path is still a curation
placeholder until quarterly CSVs are in scope.
"""
from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

REFLECT_API = "https://api.github.com/repos/real-stanford/reflect/contents/"
FAA_URL = "https://www.faa.gov/data_research/accident_incident"


def download_reflect_manifest(timeout: float = 10.0) -> list[dict[str, Any]]:
    """List top-level entries in the REFLECT dataset repo.

    Does NOT fetch any large assets. Returns the parsed GitHub contents
    response so callers can decide what to pull next.
    """
    try:
        import requests  # type: ignore
    except Exception as e:  # pragma: no cover
        print(f"[reflect] requests unavailable: {e!r}")
        return []

    try:
        r = requests.get(REFLECT_API, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        print(f"[reflect] fetch failed: {e!r}")
        return []

    items = r.json() if isinstance(r.json(), list) else []
    print(f"[reflect] {len(items)} top-level entries at {REFLECT_API}")
    for it in items:
        name = it.get("name")
        typ = it.get("type")
        print(f"  - {typ:<4}  {name}")
    # TODO(reflect): implement selective case download (cases/<id>/*.bag)
    #                with size caps and resumable GETs via the git-lfs URL.
    return items


@dataclass
class PublicAsset:
    case_key: str
    url: str
    sha256: Optional[str] = None


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_asset(asset: PublicAsset, dest_root: Path, *, timeout: float = 60.0) -> Path:
    """Idempotent single-file fetcher. Returns the local path.

    Raises ``RuntimeError`` on hash mismatch (cached or downloaded).
    """
    out_dir = Path(dest_root) / asset.case_key
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = asset.url.rsplit("/", 1)[-1] or "asset.bin"
    out_path = out_dir / fname

    if out_path.exists():
        if asset.sha256 and _hash_file(out_path) != asset.sha256:
            raise RuntimeError(f"hash mismatch on cached {out_path}")
        return out_path

    with urllib.request.urlopen(asset.url, timeout=timeout) as resp:  # noqa: S310
        out_path.write_bytes(resp.read())
    if asset.sha256 and _hash_file(out_path) != asset.sha256:
        out_path.unlink()
        raise RuntimeError(f"hash mismatch after download: {asset.url}")
    return out_path


def download_faa_stub() -> None:
    """FAA drone-incident reports placeholder."""
    print(
        "FAA drone incident reports need manual curation; "
        f"see {FAA_URL}"
    )
    # TODO(faa): scrape quarterly CSVs, filter for UAS events, normalize to
    #            black-box-bench case schema.


if __name__ == "__main__":
    print("Black Box public data sources")
    print("-" * 40)
    download_reflect_manifest()
    print()
    download_faa_stub()
