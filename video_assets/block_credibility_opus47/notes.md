# block_credibility_opus47 — editor notes

**Duration:** 45.5s @ 30fps · 1920×1080 · libx264 yuv420p crf 18.

## Six beats

| # | Name | Dur | Sources |
|---|---|---|---|
| 1 | title           | 7s | static — framing line |
| 2 | delta_panel     | 8s | `demo_assets/final_demo_pack/panels/opus47_delta_panel.png` |
| 3 | breadth         | 11s | `demo_assets/final_demo_pack/panels/breadth_montage.png` |
| 4 | grounding       | 8s | `demo_assets/grounding_gate/clean_recording/` |
| 5 | bench           | 8s | `black-box-bench/cases/` (9), `opus46_vs_opus47_20260425T182237Z.json`, `opus46_vs_opus47_20260425T183141Z.json` |
| 6 | outro           | 6s | `data/costs.jsonl` (live: $53.13, 283 calls) |

Crossfade: 0.5s between beats.

## What this clip claims (and explicitly does NOT)

- **Tied** simple-post-mortem accuracy: 4.6 = 67%, 4.7 = 67%. Not "4.7 better at solving."
- **Calibrated abstention** on under-specified `rtk_heading_break_01`: 4.6 = 0/3, 4.7 = 3/3.
- **Brier under wrong-operator pressure:** 4.6 = 0.239, 4.7 = 0.162 (lower = better).
- **Fine-grain vision:** 10 pt token rendered at 3.84 MP — 4.6 = 0/3, 4.7 = 3/3.
- **Latency:** ~30% faster on 4.7 telemetry/text path.

## How to re-render

```bash
.venv/bin/python scripts/build_opus47_panel.py
.venv/bin/python scripts/build_breadth_montage.py
.venv/bin/python scripts/render_block_credibility_opus47.py
```

## No-final-UI guarantee

This block uses zero `src/black_box/ui/` artifacts. All visuals are generated
from bench JSON + grounding-gate JSON + cost ledger + pre-rendered panels.
