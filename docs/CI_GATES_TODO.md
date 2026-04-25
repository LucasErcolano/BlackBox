# CI gates pending workflow-scope authorization

Per #94, `.github/workflows/ci.yml` should add coverage + audit + release jobs. The current automation OAuth scope cannot push workflow file changes; this doc captures the diff so a maintainer with the `workflow` scope can apply it in a follow-up commit.

## Patch to apply on `.github/workflows/ci.yml`

Replace the existing **Test** step with the block below, then append the two new jobs.

```yaml
      - name: Test with coverage
        run: |
          pytest --cov=src/black_box --cov-report=xml --cov-report=term

      - name: Coverage gate (analysis + ingestion)
        if: matrix.python-version == '3.11'
        run: |
          python -m coverage report \
            --include='src/black_box/analysis/*,src/black_box/ingestion/*' \
            --fail-under=70

      - name: Coverage gate (overall, lenient)
        if: matrix.python-version == '3.11'
        run: |
          python -m coverage report --fail-under=40

      - name: Upload coverage artifact
        if: matrix.python-version == '3.11'
        uses: actions/upload-artifact@v4
        with:
          name: coverage-xml
          path: coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: pyproject.toml
      - name: Install + audit
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
          pip-audit --strict || pip-audit

  release:
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    needs: [test, security]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Build sdist + wheel
        run: |
          python -m pip install --upgrade pip build
          python -m build
      - name: Upload release artifact
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/*
```

## Why split out

The PR that introduces `pytest-cov`, `pip-audit`, version reporting, and `INSTALL.md` was authored under an OAuth scope that lacks `workflow` write. All package-side changes ship together; this single workflow patch is the only manual follow-up. Once applied, delete this doc.
