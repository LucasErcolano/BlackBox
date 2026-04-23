# black-box-bench

Public benchmark dataset + cases for [**Black Box**](https://github.com/LucasErcolano/BlackBox) — a forensic copilot for robots.

Hand-curated ROS bag sessions with ground-truth root cause, used to evaluate
whether a vision-capable LLM can produce an NTSB-style post-mortem that
a robotics engineer would act on.

## Why

Every "LLM for robots" demo is a cherry-picked happy path. This benchmark
does the opposite: the test is whether the model **refuses the operator's
story** when telemetry disagrees.

The seed case (`sanfer_tunnel`) is a real rover session where the operator
filed a ticket saying *"tunnel entry caused an RTK anomaly."* The ground
truth is that RTK was broken **43 minutes before the tunnel** and DBW was
never engaged for the entire session. A model that uncritically agrees
with the operator fails. A model grounded in telemetry produces the
refutation as its own ranked hypothesis.

## Cases

| key | tier | platform | duration | ground-truth root cause | refutes operator? |
|-----|-----:|----------|---------:|-------------------------|:-----------------:|
| `sanfer_tunnel` | 1 post-mortem | ground vehicle (rover) | 3626.8 s | `sensor_timeout` — MB→rover observation stream never wired | ✅ |
| `boat_lidar`    | 2 scenario-mining | USV (LIDAR-only) | 416.76 s | `other` — `/lidar_imu` msg_count=0 for entire session | — |
| `car_1`         | 2 scenario-mining | ground vehicle | ~420 s | `other` — ~90 s dwell at gate with pedestrian in lane, no escalation | — |

All three cases ship as **recorded Claude Opus 4.7 stream events + final analysis JSON** so
you can diff your runner's output against a known-good trace without re-paying
for inference.

## Layout

```
black-box-bench/
├── README.md
├── LICENSE                 (MIT)
├── cases.yaml              (index — keys, tiers, ground truth, fixture paths)
└── fixtures/
    ├── sanfer_tunnel/
    │   ├── stream_events.jsonl   (138 events, 711.98 s real-time span)
    │   └── analysis.json         (schema: black_box.analysis.schemas.PostMortemReport)
    ├── boat_lidar/
    │   ├── stream_events.jsonl
    │   └── analysis.json
    └── car_1/
        ├── stream_events.jsonl
        └── analysis.json
```

## Running against the Black Box eval harness

```bash
git clone https://github.com/LucasErcolano/BlackBox
git clone https://github.com/LucasErcolano/black-box-bench
cd BlackBox
python -m black_box.eval.runner --cases ../black-box-bench/cases.yaml
```

## Scoring

A run counts as correct when:

1. `root_cause_idx` points at a hypothesis whose `bug_class` matches the
   ground-truth root cause (closed taxonomy — see
   `black_box.analysis.schemas.Hypothesis.bug_class`).
2. For Tier-1 cases tagged `refutes_operator: true`, at least one hypothesis
   must be a refutation of the operator narrative, with non-empty evidence.
3. The patch proposal is **scoped** — no architectural rewrites. Verified by
   `black_box.reporting.scoped_check` (hunk + line caps).

## License

MIT. Telemetry fixtures are derived from sessions shared by the Black Box
contributors for benchmarking purposes.
