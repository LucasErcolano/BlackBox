"""Central Anthropic client factory.

Every SDK instance used by ``black_box.analysis`` must be built here so the
``anthropic-beta: managed-agents-2026-04-01`` header is injected on every
outbound request. Missing the header causes the Managed Agents edge to reject
the call; the failure is invisible to schema tests because it lives in the
transport layer.
"""
from __future__ import annotations

import os
from typing import Iterable

from anthropic import Anthropic


MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"

# Other beta flags currently in use by black_box.analysis. Extend here when a
# new beta is adopted so the factory remains the single source of truth.
_DEFAULT_BETAS: tuple[str, ...] = (MANAGED_AGENTS_BETA,)


def _format_beta_header(betas: Iterable[str]) -> str:
    # Anthropic accepts a comma-separated list in a single ``anthropic-beta``
    # header; preserve order while deduping.
    return ",".join(dict.fromkeys(b for b in betas if b))


def default_headers(extra_betas: Iterable[str] | None = None) -> dict[str, str]:
    """Return the header dict every analysis client must carry."""
    betas = list(_DEFAULT_BETAS)
    if extra_betas:
        betas.extend(extra_betas)
    return {"anthropic-beta": _format_beta_header(betas)}


def build_client(
    *,
    api_key: str | None = None,
    extra_betas: Iterable[str] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Anthropic:
    """Build an Anthropic client with the managed-agents beta header wired in.

    This is the only sanctioned way to instantiate ``anthropic.Anthropic``
    inside ``black_box.analysis``. A repo-wide grep enforces that every other
    call-site imports from here.
    """
    headers = default_headers(extra_betas)
    if extra_headers:
        headers = {**headers, **extra_headers}
    return Anthropic(
        api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
        default_headers=headers,
    )


__all__ = ["MANAGED_AGENTS_BETA", "build_client", "default_headers"]
