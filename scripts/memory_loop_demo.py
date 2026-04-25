#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Visible self-improving memory loop demo (#76).

Deterministic two-run sequence proving memory is read-and-applied:

    run 1 — clean case ``rtk_alpha`` lands hypothesis 'sensor_timeout' as
            the top class. Priors written to L2 and L3.

    run 2 — paired case ``rtk_beta`` lands a near-tie between
            'sensor_timeout' and 'calibration_drift' (Δ confidence < tie_delta).
            PolicyAdvisor.apply_tie_break uses run-1's L3 frequency to
            promote 'sensor_timeout'. The delta is captured in a
            "memory used" panel JSON the reporting layer consumes.

Runs offline (no Anthropic call). Idempotent — purges its own scratch
memory dir on each invocation. Output JSON at:
    data/memory_loop_demo/run1_summary.json
    data/memory_loop_demo/run2_summary.json
    data/memory_loop_demo/memory_used_panel.json

Use as a pre-recorded beat in the demo script.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from black_box.analysis.policy import PolicyAdvisor
from black_box.memory import (
    CaseRecord,
    MemoryStack,
    PlatformPrior,
    TaxonomyCount,
)


def _seed_run1(memory: MemoryStack, platform: str = "rover_av") -> dict:
    case_key = "rtk_alpha"
    memory.case.log(CaseRecord(case_key=case_key, kind="hypothesis", payload={"bug_class": "sensor_timeout", "confidence": 0.91}))
    memory.platform.log(PlatformPrior(
        platform=platform,
        signature="rtk_carr_soln_none_persistent",
        bug_class="sensor_timeout",
        confidence=0.91,
        hits=4,
        source_case=case_key,
    ))
    memory.taxonomy.log(TaxonomyCount(
        bug_class="sensor_timeout",
        signature="rtk_carr_soln_none_persistent",
        count=4,
    ))
    return {
        "case_key": case_key,
        "top_hypothesis": "sensor_timeout",
        "confidence": 0.91,
        "wrote_priors": ["L1.case", "L2.platform", "L3.taxonomy"],
    }


def _run2_with_advisor(memory: MemoryStack, platform: str = "rover_av") -> dict:
    advisor = PolicyAdvisor(memory=memory, platform=platform, tie_delta=0.1)

    pre_tie_break = [
        {"bug_class": "calibration_drift", "confidence": 0.71},
        {"bug_class": "sensor_timeout", "confidence": 0.69},
    ]
    post = advisor.apply_tie_break(list(pre_tie_break))

    primed = advisor.prime_prompt_block(top_k=3)
    return {
        "case_key": "rtk_beta",
        "pre_tie_break": pre_tie_break,
        "post_tie_break": post,
        "tie_break_applied": pre_tie_break != post,
        "promoted": post[0]["bug_class"] if post else None,
        "primed_prompt_block": primed,
    }


def _memory_used_panel(run1: dict, run2: dict) -> dict:
    return {
        "title": "Memory used",
        "subtitle": "How priors from a prior session shaped this run.",
        "evidence_chain": [
            {
                "from_case": run1["case_key"],
                "prior_kind": "L3 taxonomy frequency + L2 platform prior",
                "signature": "rtk_carr_soln_none_persistent → sensor_timeout",
                "effect": (
                    f"Tie-break promoted sensor_timeout over calibration_drift "
                    f"(Δ confidence {run2['pre_tie_break'][0]['confidence']-run2['pre_tie_break'][1]['confidence']:+.2f}, "
                    f"under tie_delta=0.10)."
                ),
            }
        ],
        "delta_summary": {
            "without_memory_top": run2["pre_tie_break"][0]["bug_class"],
            "with_memory_top": run2["post_tie_break"][0]["bug_class"],
            "changed": run2["tie_break_applied"],
        },
        "primed_prompt_block_preview": run2["primed_prompt_block"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/memory_loop_demo"))
    args = parser.parse_args(argv)

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    mem_root = out / "_memory"
    memory = MemoryStack.open(mem_root)

    run1 = _seed_run1(memory)
    (out / "run1_summary.json").write_text(json.dumps(run1, indent=2), encoding="utf-8")

    run2 = _run2_with_advisor(memory)
    (out / "run2_summary.json").write_text(json.dumps(run2, indent=2), encoding="utf-8")

    panel = _memory_used_panel(run1, run2)
    (out / "memory_used_panel.json").write_text(json.dumps(panel, indent=2), encoding="utf-8")

    print(json.dumps({"run1": run1, "run2": run2, "panel": panel}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
