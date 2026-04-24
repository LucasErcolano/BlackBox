<!--
Thanks for contributing to Black Box. Please read CLAUDE.md before opening.
Keep the description terse. No preamble.
-->

## Summary
One paragraph on what changed and why.

Closes #

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup
- [ ] Docs
- [ ] CI / infra
- [ ] Benchmark / eval

## Checklist
- [ ] Tests added or updated (unit / eval / smoke).
- [ ] `data/costs.jsonl` impact noted below (token / USD delta, or "none").
- [ ] Bug taxonomy unchanged (the closed 7-class set in `CLAUDE.md` is not modified).
- [ ] No new heavy deps (no ROS 2 runtime, no LangChain / AutoGen / LlamaIndex, no vector DB, no ComfyUI / Wan / Nano Banana runtime, no training frameworks).
- [ ] Grounding gate thresholds (`GroundingThresholds`) not silently relaxed.
- [ ] Model still `claude-opus-4-7`. No silent downgrade.
- [ ] Docs / README updated if user-visible behavior changed.

## Cost impact
Expected delta on `data/costs.jsonl` per case:

- cached_input_tokens: 
- uncached_input_tokens: 
- output_tokens: 
- USD per case: 

If the change adds Claude calls or frames, justify the budget.

## Testing
How this was verified. Commands, smoke scripts, bench cases, UI paths touched.

```bash
# paste commands and key output here
```

## Screenshots / artifacts
Attach PDF report snippet, diff HTML, UI screenshots, or grounding-gate verdicts if UI-facing or report-facing.

## Reviewer notes
Anything the reviewer should look at first. Known follow-ups.
