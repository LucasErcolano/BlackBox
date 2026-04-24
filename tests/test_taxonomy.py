"""Closed-set bug taxonomy enforcement tests.

The taxonomy is frozen at exactly 7 entries (see CLAUDE.md, README.md,
`src/black_box/analysis/schemas.py`, and the cached block in
`src/black_box/analysis/prompts.py`). These tests guard against silent drift
between the narrative contract and the Pydantic schema.
"""

from __future__ import annotations

import typing

import pytest
from pydantic import ValidationError

from black_box.analysis.prompts import BUG_TAXONOMY_DOC, post_mortem_prompt
from black_box.analysis.schemas import BugClass, Evidence, Hypothesis


CANONICAL_TAXONOMY: tuple[str, ...] = (
    "pid_saturation",
    "sensor_timeout",
    "state_machine_deadlock",
    "bad_gain_tuning",
    "missing_null_check",
    "calibration_drift",
    "latency_spike",
)


def _valid_evidence() -> list[Evidence]:
    return [
        Evidence(source="telemetry", topic_or_file="/imu", t_ns=1, snippet="e1"),
        Evidence(source="code", topic_or_file="pid.py:42", t_ns=None, snippet="e2"),
    ]


def test_bug_class_literal_has_exactly_seven_entries():
    """The `BugClass` alias is a `Literal` of precisely 7 strings — no more, no less."""
    args = typing.get_args(BugClass)
    assert len(args) == 7, f"BugClass must have 7 entries, got {len(args)}: {args}"
    assert set(args) == set(CANONICAL_TAXONOMY)


def test_bug_class_literal_order_matches_canonical():
    """Order is part of the contract so diffs against CLAUDE.md and README stay obvious."""
    args = typing.get_args(BugClass)
    assert tuple(args) == CANONICAL_TAXONOMY


@pytest.mark.parametrize("canonical", CANONICAL_TAXONOMY)
def test_each_canonical_label_accepted(canonical: str):
    h = Hypothesis(
        bug_class=canonical,  # type: ignore[arg-type]
        confidence=0.9,
        summary="s",
        evidence=_valid_evidence(),
        patch_hint="clamp",
    )
    assert h.bug_class == canonical


@pytest.mark.parametrize(
    "bad_label",
    [
        "other",                      # previously-accepted escape hatch — now rejected
        "sensor_dropout",             # previously-accepted synonym — now rejected
        "config_error",               # previously-accepted broad bucket — now rejected
        "degraded_state_estimation",  # previously-accepted alias — now rejected
        "communication_failure",      # previously-accepted alias — now rejected
        "PID_SATURATION",             # wrong case
        "pid saturation",             # wrong separator
        "",                           # empty
        "made_up_bug",                # hallucinated class
        None,                         # wrong type
        42,                           # wrong type
    ],
)
def test_non_canonical_label_raises_validation_error(bad_label):
    """Any value outside the closed 7-set must raise ValidationError — no silent coercion."""
    with pytest.raises(ValidationError) as exc:
        Hypothesis(
            bug_class=bad_label,  # type: ignore[arg-type]
            confidence=0.9,
            summary="s",
            evidence=_valid_evidence(),
            patch_hint="clamp",
        )
    # Pydantic's literal_error message should name the field so operators
    # can diagnose drift without reading the traceback.
    assert "bug_class" in str(exc.value)


def test_prompt_taxonomy_block_mentions_all_seven_labels_verbatim():
    """Prompt cache block must spell the 7 labels verbatim (contract alignment)."""
    for label in CANONICAL_TAXONOMY:
        assert label in BUG_TAXONOMY_DOC, f"prompt cache missing label: {label}"


def test_prompt_taxonomy_block_does_not_list_removed_catchall():
    """`other` is gone from the prompt — the model must not be told it is a valid label."""
    # The word "other" is a common English word, so we match the shape we
    # actually cared about: `### other` header or `- other:` bullet.
    assert "### other" not in BUG_TAXONOMY_DOC
    assert "- other:" not in BUG_TAXONOMY_DOC


def test_prompt_taxonomy_block_is_cached():
    """Closed-set taxonomy must travel as a `cache_control` block in every mode."""
    spec = post_mortem_prompt()
    cached_texts = [b["text"] for b in spec["cached_blocks"] if "cache_control" in b]
    # At least one cached block contains the taxonomy doc verbatim.
    assert any(BUG_TAXONOMY_DOC == t or BUG_TAXONOMY_DOC in t for t in cached_texts)
    # And the cache_control is ephemeral, matching the rest of the prompt layer.
    taxonomy_blocks = [b for b in spec["cached_blocks"] if b["text"] == BUG_TAXONOMY_DOC]
    assert taxonomy_blocks, "BUG_TAXONOMY_DOC is not referenced by post_mortem_prompt"
    assert taxonomy_blocks[0]["cache_control"]["type"] == "ephemeral"
