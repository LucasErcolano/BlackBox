# SPDX-License-Identifier: MIT
"""Helpers for pulling public robotics / incident datasets.

These are deliberately *stubs*: we want to demonstrate which corpora
Black Box plugs into without pulling gigabytes during CI or a demo.
"""
from __future__ import annotations

from typing import Any

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
