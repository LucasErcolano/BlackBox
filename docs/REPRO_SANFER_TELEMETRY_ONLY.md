# Sanfer telemetry-only E2E repro

Proves the hero case end-to-end without the 356 GB `2_cam-lidar.bag`.
Telemetry only: `2_dataspeed.bag`, `2_diagnostics.bag`, `2_sensors.bag`.
No frame extraction, no cross-view vision pass, no stage-4 camera open.

**Hero finding to reproduce**

- `rover carr_soln = NONE` for 100% of NAV-PVT samples (session-wide).
- `REL_POS_VALID` (bit 2 of `navrelposned.flags`) never asserted (0% of 18133 samples).
- `relPosLength` / `relPosHeading` / `accLength` all identically zero for the full 3626.8 s run.
- `DIFF_SOLN` (bit 1) set on only 15.0% of samples → base→rover RTCM link mostly absent.
- Moving-base is healthy (FLOAT 63.6%, FIXED 30.7%) — proves sky / antenna fine, only the inter-receiver link is broken.
- Operator "tunnel caused the anomaly" hypothesis must be **refuted** with confidence ≤ 0.2 (failure is session-wide, predates any tunnel transit).

## Prerequisites

```
python3.10+
git clone https://github.com/LucasErcolano/BlackBox.git
cd BlackBox
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # or echo ANTHROPIC_API_KEY=sk-... > .env
```

Verify:
```
.venv/bin/python -c "from black_box.analysis import ClaudeClient; print('ok')"
```

## Bags needed vs skipped

| bag                | size     | used | reason |
|--------------------|---------:|:----:|--------|
| `2_cam-lidar.bag`  | ~356 GB  | no   | cameras + lidar only; telemetry path skips it |
| `2_dataspeed.bag`  | ~few MB  | yes  | `/vehicle/throttle_report`, `/brake_report` (DBW never engaged) |
| `2_diagnostics.bag`| ~few MB  | yes  | `/diagnostics` (ekf_se_map, ublox TMODE3 warnings) |
| `2_sensors.bag`    | ~500 MB  | yes  | `/ublox_rover/*`, `/ublox_moving_base/navpvt`, IMU |

Place the three kept bags in a single folder — the session prefix `2_` is the key that `discover_session_assets()` groups on.

```
/path/to/sanfer_sanisidro_telemetry/
├── 2_dataspeed.bag
├── 2_diagnostics.bag
└── 2_sensors.bag
```

## Single command (telemetry-only end-to-end)

Option A — one-shot against the pre-extracted bench fixture (no raw bags
needed; telemetry already on disk as `telemetry.npz`):

```
.venv/bin/python scripts/run_rtk_heading_case.py
```

Writes report JSON to `black-box-bench/runs/sample/rtk_heading_break_01.json`.

Option B — full pipeline over the three telemetry bags (skips stage 4
automatically because no bag exceeds `BIG_BAG_BYTES = 10 GiB`):

```
.venv/bin/python scripts/run_session.py \
    /path/to/sanfer_sanisidro_telemetry \
    --prompt "We think the GPS fails when the car drives through a tunnel." \
    --out data/bench_runs/sanfer_telemetry_2026-04-24
```

Stage 4 (frames) prints `no cam connections found — nothing to extract`
when the cam-lidar bag is absent; stage 5 (vision) becomes a no-op;
stage 6 writes the markdown forensic report from telemetry-derived
windows alone. Grounding gate enforces the refutation exit on the
operator's tunnel claim.

## Expected runtime + cost

| path                           | wall time        | API cost       |
|--------------------------------|-----------------:|---------------:|
| Option A (`run_rtk_heading_case.py`) | ~45 s     | $0.04 – $0.10  |
| Option B (`run_session.py`, tel-only)| 3 – 7 min | $0.10 – $0.40  |

Both stay well under 1% of the $500 project cap. Reference point: the
full camera+telemetry hero run (`managed_agent_postmortem` on
`sanfer_tunnel`) costs $1.68 – $5.88 per session (see `data/costs.jsonl`).

## Output locations

Option A:
```
black-box-bench/runs/sample/rtk_heading_break_01.json   # pydantic ForensicReport
data/costs.jsonl                                        # appended cost row
```

Option B:
```
data/bench_runs/sanfer_telemetry_2026-04-24/
├── input.json
├── session.json
├── manifest.json
├── windows.json
├── frames_index.json   # empty, cam-lidar bag absent
├── vision.json         # empty, no frames to analyze
└── report.md
```

## Verifying the hero finding

Grep the report JSON for the canonical signatures:

```
jq '.hypotheses[0].summary, .hypotheses[0].evidence[].snippet' \
    black-box-bench/runs/sample/rtk_heading_break_01.json \
    | grep -E "CARR_NONE|REL_POS_VALID|DIFF_SOLN|moving[-_ ]base"
```

Expect to see:
- `CARR_NONE=100.0%` (or equivalent `carr_soln=none` phrasing)
- `FLAGS_REL_POS_VALID set on 0.0%`
- `DIFF_SOLN set on only 15.0%`
- moving-base contrast (`FLOAT 63.6% / FIXED 30.7%`)

Grounding gate check — the operator hypothesis must be rejected, not
confirmed. Look for:

```
jq '.hypotheses[] | select(.confidence <= 0.2) | .summary' \
    black-box-bench/runs/sample/rtk_heading_break_01.json
```

Expect a tunnel-hypothesis refutation with confidence ≤ 0.2, or absence
of any tunnel hypothesis in the ranked output (silence-exit is also
valid grounding behavior per `src/black_box/analysis/grounding.py`).

Cost audit:

```
tail -n 5 data/costs.jsonl | jq '{prompt_kind, usd_cost, case_key}'
```

## Why this is honest

- Telemetry-only — no frames → the doc can't accidentally depend on the
  356 GB bag. The pipeline is the same code path; the big-bag branch is
  skipped by `stage_frames()` when no bag exceeds `BIG_BAG_BYTES`.
- The bench case `rtk_heading_break_01` is the same sanfer session
  pre-extracted to `telemetry.npz`, so Option A is a deterministic
  replay you can run without any real bag on disk.
- The reference output committed at
  `data/bench_runs/sanfer_telemetry_2026-04-24/rtk_heading_break_01.json`
  is the artifact the acceptance criteria can verify against.
