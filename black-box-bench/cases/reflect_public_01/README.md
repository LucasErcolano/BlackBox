# reflect_public_01

Public-dataset case. Source: [REFLECT](https://github.com/real-stanford/reflect) — Stanford's Robot Execution Failure benchmark (manipulation-domain failures annotated with ground-truth labels).

## Why this case

Demonstrates Black Box's Tier-2 pipeline against a third-party corpus with pre-existing failure labels. The loader does not require us to inject a bug — the dataset ships annotated failures.

## Status

`skeleton_awaiting_bag` — structure committed, bag fetched on demand by `src/black_box/eval/public_data.py :: download_reflect_manifest`. Full loader TODO (`src/black_box/eval/public_data.py:39`).

## Expected artifacts after loader fills it in

- `bag/` or `episode.pkl` — REFLECT episode bundle (RGB-D + robot state trajectory).
- `ground_truth.json` — populated with the REFLECT failure label, patch target kept null for public cases where source is not redistributable.

## Scoring note

Patch score is not meaningful for this case (source is out of repo). `score.py` returns 0.0 for the patch axis automatically when `patch_target.file` is null — contributes up to 1.5/2.0 max (bug match + window IoU).
