"""Context-Mode sandbox: local SQLite log of agent edits with FTS5 recall.

Zero external deps. Stdlib + sqlite3 only. No embeddings, no vector DB, no RAG.

Why this exists: long multi-step forensic sessions otherwise re-read whole files
on every prompt. This module lets the agent loop record the hunks it actually
changed and recall just the relevant snippet on the next pass.

Public API:
    - record_edit(path, hunk) -> int         append a changed hunk, return rowid
    - recall(query, k=3) -> list[Hunk]       FTS5 similarity search
    - init_db(db_path=None) -> Path          create/upgrade schema (called lazily)
    - clear(db_path=None) -> None            wipe the sandbox (tests only)

Storage schema:
    hunks(id, path, sha, mtime, snippet_start, snippet_end, text, created_at)
    hunks_fts VIRTUAL TABLE USING fts5(path, text, content='hunks', content_rowid='id')

FTS5 is used because SQLite ships it in CPython's bundled build, it is stdlib by
the `sqlite3` binding, and tokenization is good enough for code-ish retrieval.
No external services, no network calls.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Paths + singletons
# ---------------------------------------------------------------------------

_DEFAULT_DB_ENV = "BLACK_BOX_CONTEXT_DB"
_DEFAULT_REL_PATH = "data/context_mode.sqlite"

_conn_lock = threading.Lock()
_conn_cache: dict[str, sqlite3.Connection] = {}


def _find_repo_root(start: Optional[Path] = None) -> Path:
    """Walk upward looking for pyproject.toml; fall back to cwd."""
    cur = (start or Path(__file__).resolve()).parent
    for _ in range(8):
        if (cur / "pyproject.toml").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return Path.cwd()


def _default_db_path() -> Path:
    override = os.environ.get(_DEFAULT_DB_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return _find_repo_root() / _DEFAULT_REL_PATH


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    sha TEXT NOT NULL,
    mtime REAL NOT NULL,
    snippet_start INTEGER NOT NULL,
    snippet_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hunks_path ON hunks(path);
CREATE INDEX IF NOT EXISTS idx_hunks_sha  ON hunks(sha);

CREATE VIRTUAL TABLE IF NOT EXISTS hunks_fts USING fts5(
    path,
    text,
    content='hunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS hunks_ai AFTER INSERT ON hunks BEGIN
    INSERT INTO hunks_fts(rowid, path, text) VALUES (new.id, new.path, new.text);
END;

CREATE TRIGGER IF NOT EXISTS hunks_ad AFTER DELETE ON hunks BEGIN
    INSERT INTO hunks_fts(hunks_fts, rowid, path, text) VALUES('delete', old.id, old.path, old.text);
END;
"""


def init_db(db_path: Optional[Path] = None) -> Path:
    """Create parent dir, open/create DB, install schema. Idempotent."""
    path = Path(db_path) if db_path else _default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn(path)
    with conn:
        conn.executescript(_SCHEMA)
    return path


def _get_conn(db_path: Path) -> sqlite3.Connection:
    key = str(db_path)
    with _conn_lock:
        conn = _conn_cache.get(key)
        if conn is None:
            conn = sqlite3.connect(key, check_same_thread=False, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            _conn_cache[key] = conn
    return conn


def clear(db_path: Optional[Path] = None) -> None:
    """Wipe all rows. Intended for tests / fresh runs."""
    path = Path(db_path) if db_path else _default_db_path()
    if not path.exists():
        return
    conn = _get_conn(path)
    with conn:
        conn.execute("DELETE FROM hunks")
        conn.execute("INSERT INTO hunks_fts(hunks_fts) VALUES('rebuild')")


# ---------------------------------------------------------------------------
# Public record_edit / recall
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Hunk:
    id: int
    path: str
    sha: str
    mtime: float
    snippet_start: int
    snippet_end: int
    text: str
    created_at: float
    score: float = 0.0  # bm25 rank (lower = better); 0.0 when not scored


def _hunk_sha(path: str, text: str) -> str:
    h = hashlib.sha1()
    h.update(path.encode("utf-8", errors="replace"))
    h.update(b"\0")
    h.update(text.encode("utf-8", errors="replace"))
    return h.hexdigest()


def _estimate_line_range(
    hunk: str,
    snippet_start: Optional[int],
    snippet_end: Optional[int],
) -> tuple[int, int]:
    """Prefer caller-provided range; otherwise count lines in hunk text."""
    if snippet_start is not None and snippet_end is not None:
        return int(snippet_start), int(snippet_end)
    # Parse unified-diff-style @@ hunks when present.
    m = re.search(r"@@\s*-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s*@@", hunk)
    if m:
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) else 1
        return start, start + max(count - 1, 0)
    n = hunk.count("\n") + (0 if hunk.endswith("\n") else 1)
    return 1, max(n, 1)


def record_edit(
    path: str,
    hunk: str,
    *,
    snippet_start: Optional[int] = None,
    snippet_end: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Append a single changed hunk. Returns the new rowid.

    `path` is the file that was edited. `hunk` is the raw changed text
    (unified diff, patch, or the new region itself — all fine; FTS5 tokenizes
    it either way). `snippet_start/end` are 1-based inclusive line numbers
    when known; otherwise the function estimates them.
    """
    if not isinstance(path, str) or not path:
        raise ValueError("record_edit: path must be a non-empty string")
    if not isinstance(hunk, str):
        raise TypeError("record_edit: hunk must be a string")
    if not hunk.strip():
        # Empty / whitespace-only hunks add no signal; skip silently.
        return -1

    resolved_db = Path(db_path) if db_path else _default_db_path()
    init_db(resolved_db)

    start, end = _estimate_line_range(hunk, snippet_start, snippet_end)
    sha = _hunk_sha(path, hunk)
    try:
        mtime = os.path.getmtime(path)
    except (OSError, ValueError):
        mtime = time.time()

    conn = _get_conn(resolved_db)
    with conn:
        cur = conn.execute(
            "INSERT INTO hunks (path, sha, mtime, snippet_start, snippet_end, text, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (path, sha, mtime, start, end, hunk, time.time()),
        )
        return int(cur.lastrowid or -1)


# FTS5 MATCH syntax is strict. We build a safe OR-query from alphanumeric tokens.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


def _build_fts_query(query: str) -> str:
    tokens = _TOKEN_RE.findall(query or "")
    # de-dupe, preserve order, cap length so pathological inputs stay bounded
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tokens:
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        ordered.append(low)
        if len(ordered) >= 24:
            break
    return " OR ".join(ordered)


def recall(
    query: str,
    k: int = 3,
    *,
    db_path: Optional[Path] = None,
    path_filter: Optional[str] = None,
) -> list[Hunk]:
    """Return up to `k` hunks matching `query` by FTS5 bm25 rank.

    Falls back to an empty list if the DB is missing, empty, or the query has
    no usable tokens. This is by design: callers then `Read` the file fresh.
    """
    if k <= 0:
        return []
    resolved_db = Path(db_path) if db_path else _default_db_path()
    if not resolved_db.exists():
        return []

    fts_query = _build_fts_query(query)
    if not fts_query:
        return []

    conn = _get_conn(resolved_db)
    init_db(resolved_db)  # ensure schema in case file was pre-created empty

    sql = (
        "SELECT h.id, h.path, h.sha, h.mtime, h.snippet_start, h.snippet_end, "
        "       h.text, h.created_at, bm25(hunks_fts) AS score "
        "FROM hunks_fts "
        "JOIN hunks h ON h.id = hunks_fts.rowid "
        "WHERE hunks_fts MATCH ? "
    )
    params: list[object] = [fts_query]
    if path_filter:
        sql += "AND h.path = ? "
        params.append(path_filter)
    sql += "ORDER BY score ASC LIMIT ?"
    params.append(int(k))

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # Malformed FTS query or missing virtual table; treat as a miss.
        return []

    return [
        Hunk(
            id=int(r["id"]),
            path=str(r["path"]),
            sha=str(r["sha"]),
            mtime=float(r["mtime"]),
            snippet_start=int(r["snippet_start"]),
            snippet_end=int(r["snippet_end"]),
            text=str(r["text"]),
            created_at=float(r["created_at"]),
            score=float(r["score"]),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def format_hunks_for_prompt(hunks: Iterable[Hunk], *, max_chars: int = 6000) -> str:
    """Render hunks as a compact, cache-friendly text block for system prompts.

    Returns "" when no hunks — caller can then skip the whole context block.
    """
    lines: list[str] = []
    total = 0
    for h in hunks:
        header = f"# {h.path}:{h.snippet_start}-{h.snippet_end} (sha {h.sha[:8]})"
        body = h.text.rstrip("\n")
        chunk = f"{header}\n{body}\n"
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)
    return "\n".join(lines)


def recall_block(
    query: str,
    k: int = 3,
    *,
    db_path: Optional[Path] = None,
    max_chars: int = 6000,
) -> str:
    """Convenience: recall + format in one call. Empty string on miss."""
    hunks = recall(query, k=k, db_path=db_path)
    return format_hunks_for_prompt(hunks, max_chars=max_chars)


__all__ = [
    "Hunk",
    "init_db",
    "clear",
    "record_edit",
    "recall",
    "format_hunks_for_prompt",
    "recall_block",
]
