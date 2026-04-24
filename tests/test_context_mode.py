"""Tests for the Context-Mode SQLite sandbox.

Covers: schema creation, record_edit idempotency, FTS5 recall ordering,
prompt-integration block injection, and graceful degradation on misses.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from black_box.analysis import context_mode
from black_box.analysis.context_mode import (
    Hunk,
    clear,
    format_hunks_for_prompt,
    init_db,
    recall,
    recall_block,
    record_edit,
)


# ---------------------------------------------------------------------------
# Fixture: isolated sandbox per test
# ---------------------------------------------------------------------------

@pytest.fixture()
def sandbox_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the module at a fresh per-test SQLite file."""
    db = tmp_path / "context_mode.sqlite"
    monkeypatch.setenv(context_mode._DEFAULT_DB_ENV, str(db))
    # Wipe the module-level connection cache so env override takes effect.
    context_mode._conn_cache.clear()
    init_db(db)
    yield db
    context_mode._conn_cache.clear()


# ---------------------------------------------------------------------------
# Schema / storage
# ---------------------------------------------------------------------------

class TestSchema:
    def test_init_creates_expected_tables(self, sandbox_db: Path) -> None:
        conn = sqlite3.connect(str(sandbox_db))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','index','trigger')"
                )
            }
        finally:
            conn.close()
        assert "hunks" in tables
        assert "hunks_fts" in tables
        assert "idx_hunks_path" in tables
        assert "hunks_ai" in tables  # insert trigger

    def test_columns_match_spec(self, sandbox_db: Path) -> None:
        conn = sqlite3.connect(str(sandbox_db))
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(hunks)")}
        finally:
            conn.close()
        # Issue #58 mandates these exact columns.
        for required in ("path", "sha", "mtime", "snippet_start", "snippet_end", "text"):
            assert required in cols, f"missing column: {required}"


# ---------------------------------------------------------------------------
# record_edit
# ---------------------------------------------------------------------------

class TestRecordEdit:
    def test_record_edit_returns_rowid(self, sandbox_db: Path) -> None:
        rowid = record_edit("src/pid.cpp", "integral = clamp(integral, -100, 100);")
        assert rowid >= 1

    def test_record_edit_skips_empty(self, sandbox_db: Path) -> None:
        assert record_edit("x.py", "") == -1
        assert record_edit("x.py", "   \n\n") == -1

    def test_record_edit_rejects_bad_inputs(self, sandbox_db: Path) -> None:
        with pytest.raises(ValueError):
            record_edit("", "body")
        with pytest.raises(TypeError):
            record_edit("x.py", None)  # type: ignore[arg-type]

    def test_unified_diff_header_populates_range(self, sandbox_db: Path) -> None:
        diff = (
            "@@ -40,3 +42,5 @@\n"
            "-integral += error;\n"
            "+integral += error;\n"
            "+integral = clamp(integral, -LIMIT, LIMIT);\n"
        )
        rid = record_edit("src/pid.cpp", diff)
        conn = sqlite3.connect(str(sandbox_db))
        try:
            row = conn.execute(
                "SELECT snippet_start, snippet_end FROM hunks WHERE id=?", (rid,)
            ).fetchone()
        finally:
            conn.close()
        assert row == (42, 46)

    def test_line_count_fallback(self, sandbox_db: Path) -> None:
        body = "line1\nline2\nline3\n"
        rid = record_edit("f.py", body)
        conn = sqlite3.connect(str(sandbox_db))
        try:
            row = conn.execute(
                "SELECT snippet_start, snippet_end FROM hunks WHERE id=?", (rid,)
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == 1
        assert row[1] >= 3


# ---------------------------------------------------------------------------
# recall (the core acceptance test for issue #58)
# ---------------------------------------------------------------------------

class TestRecall:
    def test_seeded_query_returns_correct_hunk(self, sandbox_db: Path) -> None:
        """Seed three hunks; query for a distinctive token; top result wins."""
        record_edit(
            "src/pid.cpp",
            "integral = std::clamp(integral, -WINDUP_LIMIT, WINDUP_LIMIT);",
            snippet_start=40,
            snippet_end=40,
        )
        record_edit(
            "src/state_machine.cpp",
            "if (state == State::DEADLOCKED) { recover(); }",
            snippet_start=80,
            snippet_end=80,
        )
        record_edit(
            "src/sensor.cpp",
            "if (now - last_reading > TIMEOUT_MS) { use_fallback(); }",
            snippet_start=12,
            snippet_end=12,
        )

        hits = recall("pid integral windup saturation", k=3)
        assert len(hits) >= 1
        top = hits[0]
        assert top.path == "src/pid.cpp"
        assert "WINDUP_LIMIT" in top.text
        assert top.snippet_start == 40

    def test_recall_respects_k(self, sandbox_db: Path) -> None:
        for i in range(6):
            record_edit(f"f{i}.py", f"def foo{i}(): return shared_token_alpha")
        hits = recall("shared_token_alpha", k=2)
        assert len(hits) == 2

    def test_recall_on_empty_db_returns_empty(self, sandbox_db: Path) -> None:
        assert recall("anything", k=3) == []

    def test_recall_on_missing_db_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.sqlite"
        assert recall("anything", k=3, db_path=missing) == []

    def test_recall_with_no_tokens_returns_empty(self, sandbox_db: Path) -> None:
        record_edit("f.py", "some useful code here")
        # Pure punctuation / short tokens produce no FTS query.
        assert recall("!!! ?? .", k=3) == []

    def test_recall_path_filter(self, sandbox_db: Path) -> None:
        record_edit("a.py", "calibration drift detected in sensor_a")
        record_edit("b.py", "calibration drift detected in sensor_b")
        hits = recall("calibration drift", k=3, path_filter="b.py")
        assert len(hits) == 1
        assert hits[0].path == "b.py"

    def test_clear_wipes_everything(self, sandbox_db: Path) -> None:
        record_edit("x.py", "unique_sentinel_token_zeta")
        assert recall("unique_sentinel_token_zeta", k=1)
        clear(sandbox_db)
        assert recall("unique_sentinel_token_zeta", k=1) == []


# ---------------------------------------------------------------------------
# Prompt formatting + integration
# ---------------------------------------------------------------------------

class TestPromptFormatting:
    def test_format_hunks_respects_max_chars(self) -> None:
        big = Hunk(
            id=1, path="x.py", sha="abc123", mtime=0.0,
            snippet_start=1, snippet_end=10,
            text="x" * 10_000, created_at=0.0,
        )
        out = format_hunks_for_prompt([big], max_chars=500)
        # The single oversized hunk should be dropped, not truncated mid-block.
        assert out == ""

    def test_format_hunks_emits_header(self) -> None:
        h = Hunk(
            id=1, path="src/pid.cpp", sha="deadbeef" * 5, mtime=0.0,
            snippet_start=40, snippet_end=42,
            text="integral = clamp(...)", created_at=0.0,
        )
        out = format_hunks_for_prompt([h])
        assert "src/pid.cpp:40-42" in out
        assert "deadbeef" in out

    def test_recall_block_empty_on_miss(self, sandbox_db: Path) -> None:
        assert recall_block("no such token", k=3) == ""

    def test_recall_block_populated_on_hit(self, sandbox_db: Path) -> None:
        record_edit("src/pid.cpp", "integral windup guard", snippet_start=40, snippet_end=40)
        block = recall_block("windup guard", k=3)
        assert "src/pid.cpp" in block
        assert "integral windup guard" in block


class TestPromptIntegration:
    """Verify prompts.py surfaces recalled hunks as a cached block."""

    def test_post_mortem_without_query_has_two_blocks(self, sandbox_db: Path) -> None:
        from black_box.analysis.prompts import post_mortem_prompt

        spec = post_mortem_prompt()
        assert len(spec["cached_blocks"]) == 2

    def test_post_mortem_with_query_appends_context_block(self, sandbox_db: Path) -> None:
        from black_box.analysis.prompts import post_mortem_prompt

        record_edit(
            "src/pid.cpp",
            "integral = clamp(integral, -WINDUP_LIMIT, WINDUP_LIMIT);",
            snippet_start=40,
            snippet_end=40,
        )
        spec = post_mortem_prompt(context_query="pid windup")
        assert len(spec["cached_blocks"]) == 3
        ctx = spec["cached_blocks"][-1]
        assert ctx["cache_control"]["type"] == "ephemeral"
        assert "Prior Edits" in ctx["text"]
        assert "src/pid.cpp" in ctx["text"]

    def test_post_mortem_with_empty_sandbox_skips_block(self, sandbox_db: Path) -> None:
        from black_box.analysis.prompts import post_mortem_prompt

        spec = post_mortem_prompt(context_query="nothing recorded")
        # Miss => no extra block, clean cache prefix preserved.
        assert len(spec["cached_blocks"]) == 2

    def test_scenario_mining_and_synthetic_qa_also_support_context(
        self, sandbox_db: Path
    ) -> None:
        from black_box.analysis.prompts import (
            scenario_mining_prompt,
            synthetic_qa_prompt,
        )

        record_edit(
            "src/fsm.cpp",
            "state_machine_deadlock recovery path",
            snippet_start=80,
            snippet_end=85,
        )
        sm = scenario_mining_prompt(context_query="state_machine_deadlock")
        sqa = synthetic_qa_prompt(context_query="state_machine_deadlock")
        assert len(sm["cached_blocks"]) == 3
        assert len(sqa["cached_blocks"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
