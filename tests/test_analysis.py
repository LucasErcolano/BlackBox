"""Offline tests for Black Box analysis module. All Anthropic calls mocked."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from black_box.analysis import (
    ClaudeClient,
    CostLog,
    Evidence,
    Hypothesis,
    PostMortemReport,
    ScenarioMiningReport,
    TimelineEvent,
)
from black_box.analysis.prompts import (
    post_mortem_prompt,
    scenario_mining_prompt,
    synthetic_qa_prompt,
)
from black_box.analysis.schemas import SyntheticQAReport


class TestSchemasRoundtrip:
    """Test that schemas serialize/deserialize correctly."""

    def test_postmortem_roundtrip(self):
        """Construct PostMortemReport, JSON dump+load, validate."""
        evidence = Evidence(
            source="telemetry",
            topic_or_file="motor.log",
            t_ns=1000000,
            snippet="PWM: 100%",
        )
        hypothesis = Hypothesis(
            bug_class="pid_saturation",
            confidence=0.95,
            summary="Test hypothesis",
            evidence=[evidence],
            patch_hint="Add integral clamping",
        )
        timeline = TimelineEvent(t_ns=0, label="start", cross_view=False)
        report = PostMortemReport(
            timeline=[timeline],
            hypotheses=[hypothesis],
            root_cause_idx=0,
            patch_proposal="diff --git a/pid.cpp",
        )

        # Serialize
        json_str = report.model_dump_json()
        data = json.loads(json_str)

        # Deserialize
        restored = PostMortemReport.model_validate(data)
        assert restored.root_cause_idx == 0
        assert len(restored.hypotheses) == 1
        assert restored.hypotheses[0].bug_class == "pid_saturation"

    def test_scenario_mining_empty_moments(self):
        """Empty moments list should validate."""
        report = ScenarioMiningReport(moments=[], rationale="All nominal")
        json_str = report.model_dump_json()
        data = json.loads(json_str)
        restored = ScenarioMiningReport.model_validate(data)
        assert len(restored.moments) == 0


class TestPromptCachingStructure:
    """Test that prompts include cache_control on the three blocks."""

    def test_post_mortem_cache_structure(self):
        """Post-mortem has system + 2 cached blocks."""
        spec = post_mortem_prompt()
        assert "system" in spec
        assert "cached_blocks" in spec
        assert len(spec["cached_blocks"]) == 2
        # Each block should have cache_control
        for block in spec["cached_blocks"]:
            assert "cache_control" in block
            assert block["cache_control"]["type"] == "ephemeral"

    def test_scenario_mining_cache_structure(self):
        """Scenario mining has system + 2 cached blocks."""
        spec = scenario_mining_prompt()
        assert "system" in spec
        assert "cached_blocks" in spec
        assert len(spec["cached_blocks"]) == 2
        for block in spec["cached_blocks"]:
            assert "cache_control" in block
            assert block["cache_control"]["type"] == "ephemeral"

    def test_synthetic_qa_cache_structure(self):
        """Synthetic QA has system + 2 cached blocks."""
        spec = synthetic_qa_prompt()
        assert "system" in spec
        assert "cached_blocks" in spec
        assert len(spec["cached_blocks"]) == 2
        for block in spec["cached_blocks"]:
            assert "cache_control" in block
            assert block["cache_control"]["type"] == "ephemeral"

    def test_prompt_templates_have_placeholders(self):
        """User templates contain expected placeholders."""
        pm = post_mortem_prompt()
        assert "{bag_summary}" in pm["user_template"]
        assert "{synced_frames_description}" in pm["user_template"]
        assert "{code_snippets}" in pm["user_template"]

        sm = scenario_mining_prompt()
        assert "{bag_summary}" in sm["user_template"]
        assert "{synced_frames_description}" in sm["user_template"]

        sqa = synthetic_qa_prompt()
        assert "{bag_summary}" in sqa["user_template"]
        assert "{ground_truth_bug}" in sqa["user_template"]


class TestCostCalculation:
    """Test USD cost calculation with mocked usage."""

    def test_cost_calculation_no_cache(self):
        """Test cost math: 1M input, 0 cache, 1K output."""
        with patch("black_box.analysis.claude_client.Anthropic") as mock_anthropic:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Mock the client and response
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client

                # Construct usage object
                mock_usage = MagicMock()
                mock_usage.input_tokens = 1000000
                mock_usage.cache_read_input_tokens = 0
                mock_usage.cache_creation_input_tokens = 0
                mock_usage.output_tokens = 1000

                mock_content = MagicMock()
                mock_content.text = '{"timeline": [], "hypotheses": [], "root_cause_idx": 0, "patch_proposal": ""}'

                mock_response = MagicMock()
                mock_response.content = [mock_content]
                mock_response.usage = mock_usage
                mock_client.messages.create.return_value = mock_response

                # Patch the repo root finder
                with patch.object(
                    ClaudeClient,
                    "_find_repo_root",
                    return_value=Path(tmpdir),
                ):
                    client = ClaudeClient()

                    # Manually set pricing for clarity
                    client.pricing = {
                        "input": 15.0,
                        "cache_write": 18.75,
                        "cache_read": 1.50,
                        "output": 75.0,
                    }

                    spec = post_mortem_prompt()
                    spec["name"] = "test_post_mortem"

                    result, cost = client.analyze(
                        spec, user_fields={"bag_summary": "", "synced_frames_description": "", "code_snippets": ""}
                    )

                    # Expected: (1M * 15 / 1M) + (1K * 75 / 1M) = 15 + 0.075 = 15.075
                    expected_cost = (1000000 * 15.0 + 1000 * 75.0) / 1e6
                    assert abs(cost.usd_cost - expected_cost) < 1e-6

    def test_cost_calculation_with_cache(self):
        """Test cost math with cache reads and writes."""
        with patch("black_box.analysis.claude_client.Anthropic") as mock_anthropic:
            with tempfile.TemporaryDirectory() as tmpdir:
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client

                mock_usage = MagicMock()
                mock_usage.input_tokens = 100000  # uncached only (Anthropic API semantics)
                mock_usage.cache_read_input_tokens = 400000
                mock_usage.cache_creation_input_tokens = 0
                mock_usage.output_tokens = 2000

                mock_content = MagicMock()
                mock_content.text = '{"moments": [], "rationale": "all nominal"}'

                mock_response = MagicMock()
                mock_response.content = [mock_content]
                mock_response.usage = mock_usage
                mock_client.messages.create.return_value = mock_response

                with patch.object(
                    ClaudeClient,
                    "_find_repo_root",
                    return_value=Path(tmpdir),
                ):
                    client = ClaudeClient()
                    client.pricing = {
                        "input": 15.0,
                        "cache_write": 18.75,
                        "cache_read": 1.50,
                        "output": 75.0,
                    }

                    spec = scenario_mining_prompt()
                    spec["name"] = "test_scenario"

                    result, cost = client.analyze(
                        spec,
                        user_fields={"bag_summary": "", "synced_frames_description": ""},
                    )

                    # Expected: (100K * 15 + 400K * 1.5) / 1M + (2K * 75) / 1M
                    # = (1.5M + 600K) / 1M + 0.15
                    # = 2.1M / 1M + 0.15 = 2.25
                    expected_cost = (
                        (100000 * 15.0 + 400000 * 1.50 + 0) / 1e6
                        + (2000 * 75.0) / 1e6
                    )
                    assert abs(cost.usd_cost - expected_cost) < 1e-6


class TestJsonRetryOnValidationError:
    """Test that client retries once on JSON/validation errors."""

    def test_retry_on_invalid_json_first_attempt(self):
        """First call returns invalid JSON; second returns valid."""
        with patch("black_box.analysis.claude_client.Anthropic") as mock_anthropic:
            with tempfile.TemporaryDirectory() as tmpdir:
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client

                # First response: invalid JSON
                mock_usage_1 = MagicMock()
                mock_usage_1.input_tokens = 100
                mock_usage_1.cache_read_input_tokens = 0
                mock_usage_1.cache_creation_input_tokens = 0
                mock_usage_1.output_tokens = 50

                mock_content_1 = MagicMock()
                mock_content_1.text = "{ invalid json }"

                mock_response_1 = MagicMock()
                mock_response_1.content = [mock_content_1]
                mock_response_1.usage = mock_usage_1

                # Second response: valid JSON
                mock_usage_2 = MagicMock()
                mock_usage_2.input_tokens = 150
                mock_usage_2.cache_read_input_tokens = 0
                mock_usage_2.cache_creation_input_tokens = 0
                mock_usage_2.output_tokens = 100

                mock_content_2 = MagicMock()
                mock_content_2.text = '{"moments": [], "rationale": "fixed"}'

                mock_response_2 = MagicMock()
                mock_response_2.content = [mock_content_2]
                mock_response_2.usage = mock_usage_2

                mock_client.messages.create.side_effect = [
                    mock_response_1,
                    mock_response_2,
                ]

                with patch.object(
                    ClaudeClient,
                    "_find_repo_root",
                    return_value=Path(tmpdir),
                ):
                    client = ClaudeClient()

                    spec = scenario_mining_prompt()
                    spec["name"] = "test_retry"

                    result, cost = client.analyze(
                        spec,
                        user_fields={"bag_summary": "", "synced_frames_description": ""},
                    )

                    # Should succeed on second attempt
                    assert isinstance(result, ScenarioMiningReport)
                    assert len(result.moments) == 0
                    assert result.rationale == "fixed"

                    # Should have called messages.create twice
                    assert mock_client.messages.create.call_count == 2


class TestImageHandling:
    """Test image resizing and encoding."""

    def test_image_resizing_thumb(self):
        """Thumb resolution resizes to 800px max."""
        # Create a 2000x1000 test image
        img = Image.new("RGB", (2000, 1000), color="red")

        with patch("black_box.analysis.claude_client.Anthropic"):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(
                    ClaudeClient,
                    "_find_repo_root",
                    return_value=Path(tmpdir),
                ):
                    client = ClaudeClient()
                    resized = client._resize_image(img, 800)

                    assert max(resized.size) == 800
                    assert resized.size[1] == 400  # Aspect ratio preserved

    def test_image_resizing_hires(self):
        """Hires resolution resizes to 1920px max."""
        img = Image.new("RGB", (4000, 2000), color="blue")

        with patch("black_box.analysis.claude_client.Anthropic"):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(
                    ClaudeClient,
                    "_find_repo_root",
                    return_value=Path(tmpdir),
                ):
                    client = ClaudeClient()
                    resized = client._resize_image(img, 1920)

                    assert max(resized.size) == 1920
                    assert resized.size[1] == 960  # Aspect ratio preserved


class TestCostsFile:
    """Test costs.jsonl tracking."""

    def test_costs_jsonl_append_and_read(self):
        """CostLogs are appended and total_spent_usd() sums correctly."""
        with patch("black_box.analysis.claude_client.Anthropic"):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(
                    ClaudeClient,
                    "_find_repo_root",
                    return_value=Path(tmpdir),
                ):
                    client = ClaudeClient()

                    # Manually append cost logs
                    log1 = CostLog(
                        cached_input_tokens=0,
                        uncached_input_tokens=1000,
                        cache_creation_tokens=0,
                        output_tokens=100,
                        usd_cost=0.02,
                        wall_time_s=1.5,
                        model="claude-opus-4-7",
                        prompt_kind="test1",
                    )
                    log2 = CostLog(
                        cached_input_tokens=500,
                        uncached_input_tokens=500,
                        cache_creation_tokens=0,
                        output_tokens=200,
                        usd_cost=0.03,
                        wall_time_s=2.0,
                        model="claude-opus-4-7",
                        prompt_kind="test2",
                    )

                    client._append_cost_log(log1)
                    client._append_cost_log(log2)

                    # Read back
                    total = client.total_spent_usd()
                    assert abs(total - 0.05) < 1e-6

    def test_total_spent_usd_empty_file(self):
        """Empty costs.jsonl returns 0."""
        with patch("black_box.analysis.claude_client.Anthropic"):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(
                    ClaudeClient,
                    "_find_repo_root",
                    return_value=Path(tmpdir),
                ):
                    client = ClaudeClient()
                    assert client.total_spent_usd() == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
