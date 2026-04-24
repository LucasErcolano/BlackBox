# SPDX-License-Identifier: MIT
"""Self-improving policy advisor backed by the 4-layer memory stack.

The memory substrate (L1..L4) has been shipped for a while; this module is
the visible policy loop that actually *consumes* it:

- **L2 priors -> prime the prompt.** ``prime_prompt_block(platform, k)``
  returns a short, cache-friendly snippet of the top-k highest-confidence
  signature->bug_class mappings for the current platform.
- **L3 frequency -> tie-break.** ``apply_tie_break(hypotheses)`` breaks
  near-ties in model confidence by global L3 frequency. A clear winner
  is left alone; ties shift to the historically more common class.
- **L4 accuracy -> regression alarm.** ``regression_alarms()`` surfaces
  bug classes whose per-class accuracy has fallen below a threshold with
  enough samples, so the agent can flag a suspected regression in its
  own finalize payload.

The advisor is stateless beyond the memory stack it reads from, so it is
safe to construct once per session.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..memory import MemoryStack, PlatformPrior


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Duck-typed attr/item accessor for dicts, pydantic models, dataclasses."""
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


@dataclass
class RegressionAlarm:
    bug_class: str
    accuracy: float
    n_samples: int
    threshold: float


class PolicyAdvisor:
    """Reads memory, writes nothing. Callers fold its output into prompts/reports."""

    def __init__(
        self,
        memory: MemoryStack,
        platform: str | None = None,
        tie_delta: float = 0.1,
        regression_threshold: float = 0.6,
        regression_min_samples: int = 3,
    ) -> None:
        self.memory = memory
        self.platform = platform
        self.tie_delta = tie_delta
        self.regression_threshold = regression_threshold
        self.regression_min_samples = regression_min_samples

    # ------------------------------------------------------------------
    # L2: prime the prompt with platform priors
    # ------------------------------------------------------------------
    def prime_prompt_block(self, top_k: int = 5) -> str:
        """Return a prompt fragment describing the top-k L2 priors.

        Empty string when no platform is set or the platform has no priors.
        The format is designed to be appended to the cached system preamble
        without breaking prompt cache boundaries.
        """
        if not self.platform:
            return ""
        priors = self.memory.platform.top_signatures(self.platform, k=top_k)
        if not priors:
            return ""
        return _render_priors(self.platform, priors)

    # ------------------------------------------------------------------
    # L3: break near-ties with global frequency
    # ------------------------------------------------------------------
    def apply_tie_break(self, hypotheses: list[Any]) -> list[Any]:
        """Reorder hypotheses when the top-2 are within ``tie_delta`` in confidence.

        Only the top-2 are inspected. If they are a clear pair (Δ >= tie_delta)
        the list is returned sorted by confidence, unchanged semantics. If
        they are near-tied, the hypothesis whose bug_class has the higher
        L3 global count is promoted; the other drops to second. All other
        hypotheses follow in descending confidence order.
        """
        if len(hypotheses) < 2:
            return list(hypotheses)

        ordered = sorted(
            hypotheses,
            key=lambda h: float(_get(h, "confidence", 0.0) or 0.0),
            reverse=True,
        )
        top = ordered[0]
        runner = ordered[1]

        c_top = float(_get(top, "confidence", 0.0) or 0.0)
        c_run = float(_get(runner, "confidence", 0.0) or 0.0)
        if c_top - c_run >= self.tie_delta:
            return ordered  # clear winner, no tie-break needed

        totals = self.memory.taxonomy.totals_by_class()
        top_freq = totals.get(str(_get(top, "bug_class", "") or ""), 0)
        run_freq = totals.get(str(_get(runner, "bug_class", "") or ""), 0)
        if run_freq > top_freq:
            return [runner, top] + ordered[2:]
        return ordered

    # ------------------------------------------------------------------
    # L4: raise alarms when per-class accuracy regresses
    # ------------------------------------------------------------------
    def regression_alarms(self) -> list[RegressionAlarm]:
        """Return per-class regressions below the configured threshold.

        A class is reported only when it has at least
        ``regression_min_samples`` eval rows; one-off misses don't alarm.
        """
        by_class = self.memory.eval.accuracy_by_bug_class()
        records = self.memory.eval.all()
        counts: dict[str, int] = {}
        for r in records:
            counts[r.ground_truth_bug] = counts.get(r.ground_truth_bug, 0) + 1

        alarms: list[RegressionAlarm] = []
        for bug_class, acc in by_class.items():
            n = counts.get(bug_class, 0)
            if n >= self.regression_min_samples and acc < self.regression_threshold:
                alarms.append(
                    RegressionAlarm(
                        bug_class=bug_class,
                        accuracy=acc,
                        n_samples=n,
                        threshold=self.regression_threshold,
                    )
                )
        alarms.sort(key=lambda a: (a.accuracy, a.bug_class))
        return alarms


# ---------------------------------------------------------------------------
# Rendering helpers. Kept as module-level functions so tests can snapshot the
# exact string shape without constructing an advisor + memory stack.
# ---------------------------------------------------------------------------
def _render_priors(platform: str, priors: list[PlatformPrior]) -> str:
    lines = [f"Historical priors for platform `{platform}` (top {len(priors)}):"]
    for p in priors:
        lines.append(
            f"- signature `{p.signature}` -> `{p.bug_class}` "
            f"(confidence {p.confidence:.2f}, {p.hits} hit{'s' if p.hits != 1 else ''})"
        )
    lines.append(
        "Treat these as weak evidence only. Do not match a hypothesis to a prior "
        "without independent telemetry + frame corroboration in the current case."
    )
    return "\n".join(lines)
