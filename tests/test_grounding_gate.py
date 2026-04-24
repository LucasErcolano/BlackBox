"""Grounding-gate regression tests.

Guards RISKS.md P0 #3: the tool MUST return an empty finding on a genuinely
clean window, and the downstream schemas + consumers MUST NOT synthesize
anomalies when the model responds empty.

All Anthropic calls are mocked. A live companion script lives at
scripts/grounding_gate_live.py for optional end-to-end regression against a
real clean-window fixture.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from black_box.analysis.prompts_v2 import (
    VisualMiningReport,
    WindowSummary,
    visual_mining_prompt,
    window_summary_prompt,
)


def _mock_response(text: str, input_tokens: int = 2000, output_tokens: int = 50):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=1500,
    )
    return resp


class TestCleanWindowParsing:
    def test_window_summary_clean_parses_not_interesting(self):
        payload = {
            "per_camera": {
                "front_left": "Residential street in daylight, parked cars on right, no pedestrians.",
                "front_right": "Same street, clear lane markings, empty oncoming lane.",
                "right": "Row of parked cars, nothing moving.",
                "rear": "Empty road behind ego.",
                "left": "Parked cars on left side, no motion.",
            },
            "overall": "Uneventful daylight residential drive.",
            "interesting": False,
            "reason": "No unusual road users, no margin concerns, no weather or occlusion issues.",
        }
        result = WindowSummary.model_validate(payload)
        assert result.interesting is False
        assert "daylight" in result.per_camera["front_left"].lower()

    def test_visual_mining_empty_moments_is_valid(self):
        payload = {"moments": [], "rationale": "No anomalies detected in window."}
        result = VisualMiningReport.model_validate(payload)
        assert result.moments == []
        assert "no anomalies" in result.rationale.lower()


class TestClaudeClientGroundingGate:
    def test_claude_client_does_not_fabricate_on_empty_response(self):
        from black_box.analysis import ClaudeClient

        with patch("black_box.analysis.client.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response(
                json.dumps(
                    {
                        "moments": [],
                        "rationale": "Clean window, nothing notable.",
                    }
                )
            )
            c = ClaudeClient()
            spec = visual_mining_prompt()
            result, _cost = c.analyze(
                spec,
                images=[],
                user_fields={
                    "n_images": 5,
                    "frames_index": "cam1 t=0, cam3 t=0, cam4 t=0, cam5 t=0, cam6 t=0",
                    "window_info": "clean residential drive, 2s",
                },
                resolution="thumb",
            )
            assert isinstance(result, VisualMiningReport)
            assert len(result.moments) == 0, (
                "Grounding gate violated: agent produced moments when model said clean."
            )

    def test_window_summary_gate_propagates_not_interesting(self):
        from black_box.analysis import ClaudeClient

        with patch("black_box.analysis.client.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client
            mock_client.messages.create.return_value = _mock_response(
                json.dumps(
                    {
                        "per_camera": {
                            "front_left": "a",
                            "front_right": "a",
                            "right": "a",
                            "rear": "a",
                            "left": "a",
                        },
                        "overall": "Routine.",
                        "interesting": False,
                        "reason": "Nothing unusual.",
                    }
                )
            )
            c = ClaudeClient()
            spec = window_summary_prompt()
            result, _cost = c.analyze(
                spec,
                images=[],
                user_fields={
                    "window_len_s": 2.0,
                    "frames_index": "cam1 t=0",
                },
                resolution="thumb",
            )
            assert isinstance(result, WindowSummary)
            assert result.interesting is False


class TestGatePromptDiscipline:
    """Guards that the prompt text itself still instructs conservative behavior."""

    def test_system_prompt_forbids_fabrication(self):
        spec = visual_mining_prompt()
        sys = spec["system"].lower()
        assert "do not fabricate" in sys
        assert "conservative" in sys

    def test_empty_moments_is_allowed_in_cached_block(self):
        spec = visual_mining_prompt()
        joined = "\n".join(b["text"] for b in spec["cached_blocks"]).lower()
        assert "empty moments array is a valid answer" in joined
