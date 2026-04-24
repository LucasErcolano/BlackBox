"""Regression: Opus 4.7 request payload must not carry legacy extended-thinking keys.

Opus 4.7 rejects `thinking={"type": "enabled", "budget_tokens": N}` with HTTP 400.
Adaptive Thinking is native and takes no client-side parameter. These tests lock that
invariant at both the call-site level (mocked Anthropic client) and the source level
(static sweep of `src/`).
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from black_box.analysis import ClaudeClient
from black_box.analysis.prompts import post_mortem_prompt


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"


def _make_mock_response() -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = 10
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    usage.output_tokens = 5

    content = MagicMock()
    content.text = (
        '{"timeline": [], "hypotheses": [], '
        '"root_cause_idx": 0, "patch_proposal": ""}'
    )

    response = MagicMock()
    response.content = [content]
    response.usage = usage
    return response


class TestClaudePayloadNoThinkingKey:
    """The real payload constructed by ClaudeClient.analyze must omit `thinking`."""

    def test_messages_create_kwargs_omit_thinking_and_budget(self):
        with patch("black_box.analysis.client.Anthropic") as mock_anthropic:
            with tempfile.TemporaryDirectory() as tmpdir:
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client
                mock_client.messages.create.return_value = _make_mock_response()

                with patch.object(
                    ClaudeClient, "_find_repo_root", return_value=Path(tmpdir)
                ):
                    client = ClaudeClient()
                    spec = post_mortem_prompt()
                    spec["name"] = "regression_payload"
                    client.analyze(
                        spec,
                        user_fields={
                            "bag_summary": "",
                            "synced_frames_description": "",
                            "code_snippets": "",
                        },
                        apply_grounding=False,
                    )

                assert mock_client.messages.create.called, (
                    "expected analyze() to invoke messages.create"
                )

                for call in mock_client.messages.create.call_args_list:
                    kwargs = call.kwargs
                    assert "thinking" not in kwargs, (
                        "legacy extended-thinking key `thinking` must not be sent "
                        "to Opus 4.7 (HTTP 400 trigger)"
                    )
                    assert "extended_thinking" not in kwargs
                    assert "budget_tokens" not in kwargs
                    for v in kwargs.values():
                        if isinstance(v, dict):
                            assert "budget_tokens" not in v
                            assert "thinking" not in v

    def test_model_is_opus_4_7(self):
        """Defense in depth: make sure we are actually targeting Opus 4.7."""
        with patch("black_box.analysis.client.Anthropic"):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(
                    ClaudeClient, "_find_repo_root", return_value=Path(tmpdir)
                ):
                    client = ClaudeClient()
                    assert client.model == "claude-opus-4-7"


class TestSourceTreeNoLegacyThinking:
    """Static sweep: no legacy extended-thinking keys anywhere under src/.

    Benign matches (e.g. the `agent.thinking` Managed Agents event-type string,
    and UI placeholder text) are not parameter payloads, so we only forbid the
    legacy *parameter* patterns.
    """

    LEGACY_PARAM_PATTERNS = [
        re.compile(r"\bbudget_tokens\b"),
        re.compile(r"\bextended_thinking\b"),
        re.compile(r"thinking\s*=\s*\{[^}]*(enabled|budget_tokens)"),
        re.compile(r"[\"']thinking[\"']\s*:\s*\{[^}]*(enabled|budget_tokens)"),
    ]

    def test_src_tree_has_no_legacy_thinking_payload(self):
        offenders: list[tuple[str, int, str]] = []
        for path in SRC_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for pat in self.LEGACY_PARAM_PATTERNS:
                    if pat.search(line):
                        offenders.append((str(path), lineno, line.strip()))
        assert not offenders, (
            "legacy extended-thinking payload found under src/:\n"
            + "\n".join(f"  {p}:{ln}: {src}" for p, ln, src in offenders)
        )
