"""Synthetic forensic cases for Black Box."""

from .cases import SyntheticCase, build_all_cases, materialize_case
from .telemetry_gen import (
    gen_bad_gain,
    gen_pid_saturation,
    gen_sensor_timeout,
    save_npz,
)
from .video_prompts import video_prompt_for

__all__ = [
    "SyntheticCase",
    "build_all_cases",
    "materialize_case",
    "gen_pid_saturation",
    "gen_sensor_timeout",
    "gen_bad_gain",
    "save_npz",
    "video_prompt_for",
]
