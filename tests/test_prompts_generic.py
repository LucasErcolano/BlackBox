"""Tests for platform-agnostic prompts + Manifest integration.

Mocked-only: no Anthropic calls. Verifies:
  - Manifest classification by msgtype (camera/lidar/imu/gnss/odom/cmd).
  - Generic prompt injects manifest + operator hypothesis.
  - Environmental correlation (tunnel/overpass) is NOT blacklisted.
  - Autonomy is not assumed; operator hint can confirm.
  - New schema fields parse and clean-window still allowed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from black_box.analysis.prompts_generic import (
    MiningReport,
    WindowSummary,
    visual_mining_prompt,
    window_summary_prompt,
)
from black_box.ingestion.manifest import (
    Manifest,
    TopicInfo,
    manifest_to_prompt_block,
)


def _make_manifest(**overrides) -> Manifest:
    defaults = dict(
        root=Path("/tmp/session"),
        session_key="2",
        bags=[Path("/tmp/session/2_cam.bag")],
        duration_s=600.0,
        t_start_ns=0,
        t_end_ns=600_000_000_000,
    )
    defaults.update(overrides)
    return Manifest(**defaults)


class TestManifestClassification:
    def test_autonomy_unknown_without_cmd_or_user_prompt(self):
        m = _make_manifest()
        assert "unknown" in m.autonomy_signal()

    def test_autonomy_manual_from_user_prompt(self):
        m = _make_manifest(user_prompt="this was manually driven through the tunnel")
        assert m.autonomy_signal().startswith("manual")

    def test_autonomy_autonomous_from_user_prompt(self):
        m = _make_manifest(user_prompt="run was in auto mode, no operator intervention")
        assert m.autonomy_signal().startswith("autonomous")

    def test_has_telemetry_false_when_only_cameras(self):
        m = _make_manifest(cameras=[TopicInfo(topic="/cam1", msgtype="sensor_msgs/Image", kind="camera")])
        assert m.has_telemetry() is False
        assert m.has_cameras() is True

    def test_manifest_to_prompt_block_enumerates_sensors(self):
        m = _make_manifest(
            cameras=[TopicInfo(topic="/cam1/image_raw", msgtype="sensor_msgs/Image", count=300, kind="camera")],
            gnss=[TopicInfo(topic="/gps/fix", msgtype="sensor_msgs/NavSatFix", count=60, kind="gnss")],
            user_prompt="gps falla bajo el tunel",
        )
        block = manifest_to_prompt_block(m)
        assert "/cam1/image_raw" in block
        assert "/gps/fix" in block
        assert "manual" in block or "unknown" in block


class TestGenericPromptAssembly:
    def test_operator_hypothesis_is_injected_into_cached_blocks(self):
        m = _make_manifest(user_prompt="el gps falla debajo del tunel")
        spec = visual_mining_prompt(manifest=m, user_prompt=m.user_prompt)
        joined = "\n".join(b["text"] for b in spec["cached_blocks"])
        assert "el gps falla debajo del tunel" in joined
        assert "hypothesis not truth" in joined.lower()

    def test_manifest_block_included_when_manifest_provided(self):
        m = _make_manifest(
            cameras=[TopicInfo(topic="/cam_front", msgtype="sensor_msgs/Image", kind="camera")],
        )
        spec = window_summary_prompt(manifest=m)
        joined = "\n".join(b["text"] for b in spec["cached_blocks"])
        assert "/cam_front" in joined
        assert "Session capability manifest" in joined

    def test_no_manifest_no_operator_still_works(self):
        spec = visual_mining_prompt()
        assert spec["name"] == "visual_mining_generic"
        assert len(spec["cached_blocks"]) >= 1

    def test_system_prompt_does_not_assume_platform(self):
        spec = visual_mining_prompt()
        sys = spec["system"].lower()
        assert "any platform" in sys or "do not assume the platform" in sys
        assert "do not assume autonomy" in sys


class TestNoEnvironmentalBlacklist:
    def test_tunnel_correlation_is_explicitly_allowed(self):
        spec = visual_mining_prompt(manifest=_make_manifest())
        joined = "\n".join(b["text"] for b in spec["cached_blocks"]).lower()
        # The key regression: tunnel/overpass must NOT be in a
        # "not a finding" blacklist. We check the opposite instruction
        # exists: environmental transitions + correlation is a finding.
        assert "environmental" in joined
        assert "tunnel" in joined
        # And the anti-pattern from prompts_v2 must be absent:
        assert "brief sensor exposure change when entering or exiting a tunnel" not in joined


class TestSchemaAcceptsOperatorVerdict:
    def test_mining_report_parses_empty(self):
        payload = {"moments": [], "rationale": "Clean window."}
        r = MiningReport.model_validate(payload)
        assert r.moments == []
        assert r.operator_hypothesis_verdict == ""

    def test_mining_report_parses_with_hypothesis_status(self):
        payload = {
            "moments": [
                {
                    "t_ns": 123,
                    "label": "RTK invalid from t=0",
                    "cameras": {"shows": [], "misses": []},
                    "evidence": [
                        {"source": "telemetry", "channel": "/gps/navrelposned",
                         "t_ns": 0, "snippet": "carr_soln=0 throughout"}
                    ],
                    "why_review": "Fused localization never publishes.",
                    "confidence": 0.95,
                    "inferred_ego_motion": "",
                    "hypothesis_status": "contradicts_operator",
                }
            ],
            "rationale": "Structural RTK failure predates tunnel.",
            "operator_hypothesis_verdict": "partially confirmed: tunnel shows GNSS degradation but does not explain session-wide RTK break at t=0",
        }
        r = MiningReport.model_validate(payload)
        assert len(r.moments) == 1
        assert r.moments[0].hypothesis_status == "contradicts_operator"
        assert "partially confirmed" in r.operator_hypothesis_verdict

    def test_window_summary_uses_per_channel(self):
        payload = {
            "per_channel": {"/cam1": "clean", "/gps/fix": "RTK invalid whole window"},
            "overall": "localization broken",
            "interesting": True,
            "reason": "GNSS never valid",
        }
        s = WindowSummary.model_validate(payload)
        assert s.interesting is True
        assert "/gps/fix" in s.per_channel
