# Grounding-gate proof

Beat 1:40 asset — evidence that Black Box refuses operator narrative when telemetry disagrees.

## Source: sanfer_tunnel — hypothesis #3 (conf 0.10)

Operator submitted the bag tagged "tunnel caused anomaly." Black Box's third-ranked hypothesis is an explicit **REFUTATION** backed by timeline evidence:

> Operator hypothesis REFUTED: the Sanfer tunnel entry did cause mild GNSS degradation (num_sv 29→16, h_acc 645mm → 1294mm between t=2621.4s and t=2681.2s) but it did NOT cause an RTK/heading failure and could not have caused any behavior change because DBW was never engaged; the dominant localization failure (RTK heading = none) is session-wide and starts 43 minutes before the tunnel.

Evidence snippets (see `../analyses/sanfer_tunnel.json`, hypothesis index 2):
- `ublox_rover_navrelposned.csv @ t=240ms`: carr_soln=none ALREADY at t=0.24s (43 min pre-tunnel)
- `ublox_rover_navpvt.csv @ t=2624s`: worst in-tunnel sample num_sv=16, h_acc=1294mm — no fix-loss
- `brake_20hz.csv @ t=2624s`: brake.enabled=0 throughout tunnel window — no autonomy to degrade

## Why this matters

Model had an easy path: accept operator framing, write "tunnel multipath caused RTK dropout," ship. Instead it:
1. Noticed carr_soln was already `none` on the first sample
2. Verified across 18133 samples (100% of session)
3. Checked DBW enable state and found it never ≥1
4. Surfaced the refutation as its own ranked hypothesis with a confidence score, not as silence

The "patch_hint" on the refutation even tells the operator what to do with the correction: "Re-interview operator: the 'tunnel anomaly' perception is likely an after-the-fact attribution."

This is the non-hallucination beat — the system grounded itself in telemetry over story.
