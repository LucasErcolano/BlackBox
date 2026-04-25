"""Regression: cached blocks must exceed Anthropic's per-block cache threshold.

Opus/Sonnet require ~1024 tokens minimum per cached block, otherwise the
cache_control hint is silently ignored. We pad DOMAIN_CONTEXT_AV with stable
forensic content so back-to-back runs hit the cache and `data/costs.jsonl`
records non-zero `cached_input_tokens`. If a future edit shrinks the block
below the threshold, this test fails before billing does.
"""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from black_box.analysis import prompts_v2

# Conservative char->token proxy (~4 chars per token for English).
# Threshold 1024 tokens => ~4096 chars; we require 1.25x headroom.
MIN_CHARS = 5120


def test_domain_context_above_cache_threshold():
    assert len(prompts_v2.DOMAIN_CONTEXT_AV) >= MIN_CHARS, (
        "DOMAIN_CONTEXT_AV shrank below the prompt-cache eligibility "
        "threshold. cache_control will be ignored and cached_input_tokens "
        "will stay zero on subsequent runs."
    )


def test_visual_mining_cached_blocks_total_above_threshold():
    p = prompts_v2.visual_mining_prompt()
    total = sum(len(b["text"]) for b in p["cached_blocks"])
    assert total >= MIN_CHARS, (
        f"visual_mining cached blocks total {total} chars; below cache threshold."
    )


def test_window_summary_cached_block_above_threshold():
    p = prompts_v2.window_summary_prompt()
    total = sum(len(b["text"]) for b in p["cached_blocks"])
    assert total >= MIN_CHARS, (
        f"window_summary cached block total {total} chars; below cache threshold."
    )
