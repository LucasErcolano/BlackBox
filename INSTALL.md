# Install — Black Box

For evaluators. One-command install from a release artifact, then a smoke run.

## From a release tag

```bash
# 1. Download the wheel from the GitHub release page for tag vX.Y.Z.
gh release download vX.Y.Z --pattern '*.whl' --dir dist/

# 2. Create a clean venv and install.
python3 -m venv .venv && source .venv/bin/activate
pip install dist/*.whl

# 3. Smoke check.
python -m black_box --version
blackbox bench --case-dir black-box-bench/cases   # offline plumbing, no API key needed
```

## From source (development)

```bash
git clone https://github.com/LucasErcolano/BlackBox.git
cd BlackBox
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=src/black_box --cov-report=term
```

## Live run (requires API key)

```bash
export ANTHROPIC_API_KEY=sk-...
blackbox bench --use-claude          # tier-3 eval over the public benchmark
python scripts/run_opus_bench.py --budget-usd 20
```

## Reproducibility notes

- Pinned floors are declared in `pyproject.toml` (`>=` constraints, not pinned exacts; CVE patches still flow).
- `pip-audit` runs in CI on every PR; release builds depend on it passing.
- CI builds the sdist+wheel on every `vX.Y.Z` tag push and uploads as a workflow artifact.
- `python -m black_box --version` reports the installed package version (resolved from package metadata; falls back to `0.0.0+local` for editable installs without metadata).

## What if pip-audit flags a vulnerability?

Open a PR upgrading the pinned floor for the offending dependency. Do **not** silence findings with `--ignore-vuln` unless the upstream fix is unavailable; document the reason in the PR if you do.
