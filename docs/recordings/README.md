# Terminal recordings

Asciinema v2 casts of the runner. These are committed for evaluators who want a credible terminal artifact without spinning up a live run.

## `offline_batch.cast`

- **Provenance:** offline (deterministic stub predictor; no Anthropic call).
- **What it shows:** startup banner, per-case progress, results table, cost ticker (always $0.00 in this offline cut), guardrail beat documenting the cost-ceiling behavior.
- **Reproducer:**

```bash
python scripts/record_batch_asciicast.py
# Plays back with:
asciinema play docs/recordings/offline_batch.cast
# (or open at https://asciinema.org/a/<id> after `asciinema upload`)
```

The cast header carries `"provenance": "offline"`. Anyone playing back sees the offline runner; nothing in this cast is implied to be model output.

## How to capture a *live* cast

Asciinema must be installed locally (`pip install asciinema` or distro package). With an `ANTHROPIC_API_KEY` set:

```bash
asciinema rec docs/recordings/live_batch.cast \
    --command 'python -m black_box.eval.runner --tier 3 \
               --case-dir black-box-bench/cases --use-claude'
```

A live cast that crossed `--cost-ceiling-usd` would show `aborted_cap` rows for the remaining cases — the offline cast above documents the shape with a synthetic line so reviewers know what to look for.
