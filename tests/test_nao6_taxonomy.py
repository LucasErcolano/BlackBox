"""Tests for the NAO6-specific bug taxonomy and its mapping to the global set."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from black_box.platforms.nao6.taxonomy import (
    NAO6_TAXONOMY,
    NAO6BugClass,
    by_slug,
    to_global,
)

ALLOWED_GLOBAL = {
    "pid_saturation",
    "sensor_timeout",
    "state_machine_deadlock",
    "bad_gain_tuning",
    "missing_null_check",
    "calibration_drift",
    "latency_spike",
    "other",
}


def test_taxonomy_has_five_entries() -> None:
    assert len(NAO6_TAXONOMY) == 5


def test_every_global_class_is_allowed() -> None:
    for entry in NAO6_TAXONOMY:
        assert entry.global_class in ALLOWED_GLOBAL, entry.slug


def test_all_slugs_unique() -> None:
    slugs = [e.slug for e in NAO6_TAXONOMY]
    assert len(slugs) == len(set(slugs))


def test_expected_slugs_present() -> None:
    expected = {
        "joint_pid_saturation",
        "com_estimation_drift",
        "fall_recovery_deadlock",
        "bad_gait_gains",
        "contact_sensor_timeout",
    }
    assert {e.slug for e in NAO6_TAXONOMY} == expected


def test_by_slug_hit() -> None:
    entry = by_slug("joint_pid_saturation")
    assert entry is not None
    assert entry.slug == "joint_pid_saturation"
    assert entry.global_class == "pid_saturation"
    assert entry.display_name == "Joint PID Saturation"


def test_by_slug_miss_returns_none() -> None:
    assert by_slug("nonexistent") is None


def test_to_global_hit() -> None:
    assert to_global("com_estimation_drift") == "calibration_drift"
    assert to_global("fall_recovery_deadlock") == "state_machine_deadlock"
    assert to_global("bad_gait_gains") == "bad_gain_tuning"
    assert to_global("contact_sensor_timeout") == "sensor_timeout"


def test_to_global_miss_raises_key_error() -> None:
    with pytest.raises(KeyError):
        to_global("bogus")


def test_each_entry_has_two_plus_signals_and_nontrivial_description() -> None:
    for entry in NAO6_TAXONOMY:
        assert len(entry.example_signals) >= 2, entry.slug
        for sig in entry.example_signals:
            assert sig.strip(), entry.slug
        assert len(entry.description.strip()) >= 40, entry.slug


def test_pydantic_rejects_invalid_global_class() -> None:
    with pytest.raises(ValidationError):
        NAO6BugClass(
            slug="made_up",
            display_name="Made Up",
            global_class="not_a_real_class",  # type: ignore[arg-type]
            description="intentionally invalid entry for validation test",
            example_signals=["signal a", "signal b"],
        )


def test_display_names_nonempty_and_capitalized() -> None:
    for entry in NAO6_TAXONOMY:
        name = entry.display_name
        assert name, entry.slug
        assert name[0].isupper(), entry.slug
