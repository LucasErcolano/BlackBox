# BlackBox demo · production ledger (hybrid v3)

## Date
2026-04-26 ~20:58 EST

## Working directory
`demo_assets/final_video_competition/20260426_2058/`

## Sources (preserved, not modified)
- v2 baseline (preferred): `demo_assets/final_demo_pack/final_video_v2/blackbox_demo_final_v2.mp4` — 179.77s, 1920x1080@30, h264+aac. Already passes hard gates per `final_video_v2/before_after_report.md`.
- v2 trimmed clips: `demo_assets/final_demo_pack/trimmed_clips/block_*.mp4`
- v2 panels: `demo_assets/final_demo_pack/panels/{operator_vs_blackbox,opus47_delta_panel,breadth_montage}.png`
- Approach-1 raw UI/camera clips: `demo_assets/editor_raw_footage_pack/clips/{01..20}_*.mp4`

## Agents dispatched
1. **Asset Archaeologist** (Explore subagent, opus). Probed all 31 candidate clips. Output: `archaeology/asset_catalog.md`.
2. **QA-Judge** (this agent). Extracted 60 frames every 3s + 6x10 contact sheet from v2. Findings:
   - 51s of static designed-panel screen-time (28% runtime) is the visible weakness.
   - No text overlap, no clipping, no black/freeze frames detected in v2.
   - Two surgical swap candidates identified that increase realism without breaking visual language.
3. **Visual Language Director** (this agent). Spec at `visual_lang/visual_language.md`.
4. **Editor C — Hybrid Director** (this agent). Renders cut at `drafts/hybrid/blackbox_demo_hybrid.mp4`.

## Decisions
- Editor A (final_demo_pack_refined) and Editor B (evidence-heavy) drafts collapsed into a single Editor-C hybrid: v2 already passes all hard gates and was specifically called out as the preferred baseline. Doing a cleanroom re-cut would regress the documented v2 fixes (transition pipeline, layout-safe panels, freeze-trim). Hybrid keeps every v2 fix and only swaps two segments.
- Two swaps selected, both replacing designed surfaces with real UI captures of the same palette:
  - **Swap A** at 1:43–1:57 beat: `block_08_money_shot.mp4` (11.5s composite) → `06_patch_diff_ui.mp4` (13.4s real /report deep-scroll).
  - **Swap B** at 2:11–2:25 beat: `breadth_montage.png` still (17s) → `07_cases_archive_ui.mp4` (13.4s real /cases archive UI).
- No new captions burned. No new panels rebuilt. Operator-vs-blackbox panel preserved verbatim — it is the climax beat and was specifically called out as load-bearing.
- All swap candidates ffprobe'd to confirm 1920x1080@30 h264, identical to v2 mezzanine. No re-encode mismatch risk.

## Render command
```
.venv/bin/python demo_assets/final_video_competition/20260426_2058/build_hybrid.py
```

## Outputs (target paths)
- `drafts/hybrid/blackbox_demo_hybrid.mp4`         (final hybrid with silent AAC)
- `drafts/hybrid/blackbox_demo_hybrid_no_audio.mp4`
- `drafts/hybrid/timeline.json`
- `final/blackbox_demo_final.mp4`                  (= hybrid, copied at delivery)
- `final/timeline_final.json`
- `final/scorecard_final.md`
- `final/visual_qa_report.md`
- `final/README.md`
