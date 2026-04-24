---
name: Bug report
about: Report a defect in Black Box (ingestion, analysis, grounding gate, UI, eval, reporting)
title: "[BUG] "
labels: bug
assignees: ''
---

## Summary
One sentence describing the defect.

## Environment
- Black Box commit / branch:
- Python version:
- OS:
- Mode (forensic / scenario mining / synthetic QA):
- Platform adapter (nao6 / other):

## Reproduce
Steps to reproduce the behavior. Include the exact command(s) run.

```bash
# paste command(s) here
```

## Expected vs actual
**Expected:**

**Actual:**

## Session / bag identifiers
Give enough for a maintainer to re-run or triage.

- Session folder or case key:
- Bag file(s) (numeric prefix + name, for example `2_camera_front.bag`):
- Recording timestamp / duration:
- Public-data case id (if from `black-box-bench/`):

## Cost log excerpt
Paste the relevant lines from `data/costs.jsonl` (cached_input_tokens, uncached_input_tokens, output_tokens, USD). This is critical for reproducing token-budget regressions.

```jsonl
# paste cost-log lines here
```

## Evidence / artifacts
Attach or link: screenshots of UI, PDF report, grounding-gate verdict, diff HTML, telemetry plot PNGs, tracebacks.

## Additional context
Anything else the maintainer should know (recent changes, related issues, suspected area of code).
