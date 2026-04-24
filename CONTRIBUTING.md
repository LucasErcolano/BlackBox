# Contributing

Solo hackathon project. External contributions are welcome post-submission. Keep PRs small, scoped, and boring.

## Dev setup

```bash
git clone https://github.com/LucasErcolano/BlackBox.git
cd BlackBox
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # if present; otherwise export ANTHROPIC_API_KEY manually
```

Python 3.10+. See `pyproject.toml` for runtime and dev extras.

## Tests

```bash
PYTHONPATH=src pytest -q
```

Full suite must stay green before you push. Add a test with every behavior change. Fixtures live under `tests/`.

## Lint

```bash
ruff check src tests scripts
```

Line length is 100. Target `py310`.

## PR etiquette

- One concern per PR. Docs, refactors, features go in separate PRs.
- Title format: `<type>(<scope>): <summary>` (for example `feat(ingestion): dual-antenna frame sync`).
- Reference closed issues with `closes #NN`.
- Keep diffs under ~400 lines where you can. If larger, explain why in the body.
- No force-push to `master`. Rebase your own branch freely.

## Code style

- Terse, no preamble comments. Only comment the non-obvious "why."
- Type hints on public functions.
- Pydantic v2 for any structured output.
- SPDX header on every new `*.py` in `src/black_box/` and `scripts/`: `# SPDX-License-Identifier: MIT` (line 1, or line 2 after a shebang).
- No emojis in code or docs. No em dashes in prose. NTSB voice: terse, factual, no hedge.

## Hard rules (inherited from CLAUDE.md)

- No ROS 2 runtime install. `rosbags` library only.
- No LangChain / AutoGen / LlamaIndex / vector DBs / RAG. Flat code.
- No training. Inference-only over `claude-opus-4-7`.
- Patches emitted by the agent are scoped (clamps, timeouts, null checks, gains). Architectural rewrites are refused.
