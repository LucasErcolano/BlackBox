# demo_assets/ — DEMO_SCRIPT beat mapping

Consolidated at commit time below — all assets live in-tree under `demo_assets/`.
Benchmark fixtures live in the sibling repo `black-box-bench` (see bottom).

## Beat → asset mapping

| beat | what happens | primary asset | secondary |
|-----:|--------------|---------------|-----------|
| 0:00 | cold open — "forensic copilot for robots" | — | — |
| 0:15 | upload widget | (live UI — record from browser) | `streaming/README.md` |
| 0:30 | job kicks off — progress bar + streaming reasoning | `streaming/replay_sanfer_tunnel.mp4` (to record locally) | `streaming/replay_mid.png` |
| 1:10 | NTSB-style PDF reveal — sanfer | `pdfs/sanfer_tunnel.pdf` + `pdfs/sanfer_tunnel/page-*.png` | — |
| 1:25 | timeline + top hypothesis bullet | `analyses/TOP_FINDINGS.md` (sanfer row) | `analyses/sanfer_tunnel.json` |
| 1:40 | **grounding gate** — refuses operator narrative | `grounding_gate/README.md` | `analyses/sanfer_tunnel.json` (hyp idx 2, conf 0.10) |
| 1:55 | proposed fix — side-by-side diff | `diff_viewer/moving_base_rover.png` | `diff_viewer/moving_base_rover_2x.png` (zoom), `diff_viewer/moving_base_rover.html` (live) |
| 2:15 | breadth — boat_lidar (Tier-2) + car_1 (Tier-2) | `pdfs/boat_lidar.pdf` + `pdfs/car_1.pdf` | `analyses/boat_lidar.json`, `analyses/car_1.json` |
| 2:35 | benchmark — `black-box-bench` public repo | (see `black-box-bench/` sibling repo URL in `bench_repo.txt`) | `streams/` jsonl fixtures |
| 2:50 | memory/taxonomy bonus | `memory_snapshot/L3_counts.txt` | `memory_snapshot/L1_case.jsonl`, `L3_taxonomy.jsonl` |

## Tree

```
demo_assets/
├── INDEX.md                          (this file)
├── streaming/
│   ├── README.md                     (local-record instructions — ffmpeg+headless not viable here)
│   └── replay_mid.png                (115 KB — offline composite of mid-run UI)
├── diff_viewer/
│   ├── moving_base_rover.html        ( 22 KB — live NTSB-style side-by-side)
│   ├── moving_base_rover.png         (216 KB — 1920×1080)
│   └── moving_base_rover_2x.png      (820 KB — 3840×2160 Lanczos upscale for zoom)
├── pdfs/
│   ├── sanfer_tunnel.pdf             ( 16 KB, 6 pages)
│   ├── sanfer_tunnel/page-{1..6}.png (150 dpi raster)
│   ├── boat_lidar.pdf                (  9 KB, 4 pages)
│   ├── boat_lidar/page-{1..4}.png
│   ├── car_1.pdf                     (  8 KB, 3 pages)
│   └── car_1/page-{1..3}.png
├── streams/
│   ├── sanfer_tunnel.jsonl           (138 events, 711.98 s span)
│   ├── boat_lidar.jsonl
│   └── car_1.jsonl
├── analyses/
│   ├── sanfer_tunnel.json
│   ├── boat_lidar.json
│   ├── car_1.json
│   └── TOP_FINDINGS.md               (table: case | t_ns | bug_class | conf | evidence | patch)
├── grounding_gate/
│   └── README.md                     (beat 1:40 proof — sanfer hyp #3 refutes operator)
└── memory_snapshot/
    ├── L1_case.jsonl
    ├── L3_taxonomy.jsonl
    └── L3_counts.txt                 (visual dump for beat 2:50)
```

## What was NOT consolidated and why

- `streaming/replay_sanfer_tunnel.mp4` — NOT recorded. Headless screencast path is not viable in this sandbox (no X display, Chromium not installed, Firefox headless cannot screencast, ffmpeg x11grab needs a live display). `streaming/README.md` has exact local repro steps to record on host w/ Tella/OBS in ~2 min.
- `data/final_runs/sanfer_tunnel/bundle/` frames + per-topic CSVs (~6.4 MB) — NOT copied. These are raw ingestion bundles, not demo-visible. Already in repo under `data/final_runs/`; pointing at the source path avoids duplication.
- `car_0` run — NOT included. The `data/final_runs/car_0/` dir only contains `bundle/` (ingestion artifacts, no analysis.json/report.pdf). Not a demo case.
- `black-box-bench` public repo — NOT YET created. Under the user's gh account `LucasErcolano` no such repo exists. Creation is a shared-state action; confirming before `gh repo create` — see bottom.

## Sizes

Run `du -sh demo_assets/*` for current totals. Expected ballpark ≈ 3-4 MB (no video).

## Benchmark repo

See `bench_repo.txt` for the decision on `black-box-bench`. If you OK the push, it will
land at `https://github.com/LucasErcolano/black-box-bench`.
