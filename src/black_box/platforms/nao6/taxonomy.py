# SPDX-License-Identifier: MIT
"""NAO6-specific bug taxonomy.

Presentation-layer vocabulary for the NAO6 humanoid platform. Each entry
maps onto exactly one class from the global closed-set taxonomy in
`src/black_box/analysis/schemas.py`. When Claude emits a report, the
`global_class` is what flows into `schemas.Hypothesis.bug_class`; the
humanoid-specific slug is carried in the report summary or metadata.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

GlobalBugClass = Literal[
    "pid_saturation",
    "sensor_timeout",
    "state_machine_deadlock",
    "bad_gain_tuning",
    "missing_null_check",
    "calibration_drift",
    "latency_spike",
    "other",
]

_ALLOWED_GLOBAL: frozenset[str] = frozenset(
    {
        "pid_saturation",
        "sensor_timeout",
        "state_machine_deadlock",
        "bad_gain_tuning",
        "missing_null_check",
        "calibration_drift",
        "latency_spike",
        "other",
    }
)


class NAO6BugClass(BaseModel):
    """One NAO6-specific bug class mapped to a global taxonomy entry."""

    slug: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    global_class: GlobalBugClass
    description: str = Field(min_length=1)
    example_signals: list[str] = Field(min_length=1)


NAO6_TAXONOMY: list[NAO6BugClass] = [
    NAO6BugClass(
        slug="joint_pid_saturation",
        display_name="Joint PID Saturation",
        global_class="pid_saturation",
        description=(
            "A leg or arm joint PID integral term winds up during sustained "
            "load; the actuator torque command pins at the NAOqi stiffness "
            "limit and the joint can no longer track its reference."
        ),
        example_signals=[
            "LHipPitch integral term grows unbounded during sustained forward pitch; actuator torque command saturates at NAOqi stiffness limit 1.0",
            "Device/SubDeviceList/RAnklePitch/ElectricCurrent/Sensor/Value clipped at rated max for >800 ms while position error keeps increasing",
            "Motion/Walk commanded joint velocity exceeds joint_velocity_limit and ALMotionProxy logs 'torque saturation' on RKneePitch",
        ],
    ),
    NAO6BugClass(
        slug="com_estimation_drift",
        display_name="COM Estimation Drift",
        global_class="calibration_drift",
        description=(
            "The estimated center-of-mass slowly diverges from the true COM "
            "because IMU bias or foot-contact offsets were never "
            "re-calibrated; the walk engine issues ZMP targets that violate "
            "the real support polygon."
        ),
        example_signals=[
            "InertialSensor/AngleX/Sensor/Value shows a +0.04 rad steady-state bias vs horizon after stand-init",
            "Motion/Walk/ZmpError grows monotonically across steps while commanded ZMP stays nominal",
            "Device/SubDeviceList/LFoot/FSR/TotalWeight diverges from RFoot/FSR/TotalWeight by >20% on a level floor",
        ],
    ),
    NAO6BugClass(
        slug="fall_recovery_deadlock",
        display_name="Fall-Recovery Deadlock",
        global_class="state_machine_deadlock",
        description=(
            "ALRobotPosture's fall-manager enters getUp but a guard "
            "condition (e.g. torso angle or FSR contact) never flips, so the "
            "state machine loops between PreGetUp and GetUpBack instead of "
            "reaching Stand."
        ),
        example_signals=[
            "ALRobotPosture/Event/PostureChanged stuck emitting 'GetUpBack' for >6 s with no transition to 'Stand'",
            "ALMotion/FallManager/State oscillates PreGetUp -> GetUpBack -> PreGetUp at 1 Hz",
            "InertialSensor/AngleY remains >1.2 rad (prone) while robotHasFallen flag stays True indefinitely",
        ],
    ),
    NAO6BugClass(
        slug="bad_gait_gains",
        display_name="Bad Gait Gains",
        global_class="bad_gain_tuning",
        description=(
            "ALMotion walk parameters (step height, stiffness, or "
            "torso-sway) are set outside the stable envelope for the "
            "current surface, producing a growing lateral oscillation that "
            "ends in a side-fall within a few steps."
        ),
        example_signals=[
            "Motion/Walk/TorsoSwayY amplitude grows step-over-step from 0.03 rad to 0.11 rad over 4 strides",
            "setStiffnesses('LLeg', 0.4) called before ALMotion.moveTo — stiffness below 0.7 documented minimum for walk",
            "stepHeight=0.06 with maxStepFrequency=1.0 exceeds the stable region for the carpet-surface preset",
        ],
    ),
    NAO6BugClass(
        slug="contact_sensor_timeout",
        display_name="Contact Sensor Timeout",
        global_class="sensor_timeout",
        description=(
            "The foot FSR or bumper topic stops updating (DCM tick miss or "
            "USB bus stall) but the walk controller keeps consuming the "
            "last-seen value, so a swing foot is believed to be in contact "
            "and the next step is planned into empty space."
        ),
        example_signals=[
            "Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value timestamp frozen for 420 ms while DCM tick counter advances",
            "ALMemory key RFoot/Bumper/Right/Sensor/Value last-update age exceeds 200 ms ALMotion staleness threshold",
            "Motion/Walk/FootContact/Left remains True for 3 consecutive swing phases where ground-truth FSR is 0 N",
        ],
    ),
]


for _entry in NAO6_TAXONOMY:
    if _entry.global_class not in _ALLOWED_GLOBAL:
        raise RuntimeError(
            f"NAO6 taxonomy entry '{_entry.slug}' maps to "
            f"'{_entry.global_class}' which is not in the global closed set "
            f"{sorted(_ALLOWED_GLOBAL)}"
        )

_BY_SLUG: dict[str, NAO6BugClass] = {e.slug: e for e in NAO6_TAXONOMY}


def by_slug(slug: str) -> NAO6BugClass | None:
    """Return the NAO6BugClass for a slug, or None if unknown."""
    return _BY_SLUG.get(slug)


def to_global(slug: str) -> str:
    """Return the global taxonomy class for a NAO6 slug; KeyError if unknown."""
    entry = _BY_SLUG.get(slug)
    if entry is None:
        raise KeyError(f"Unknown NAO6 bug slug: {slug!r}")
    return entry.global_class
