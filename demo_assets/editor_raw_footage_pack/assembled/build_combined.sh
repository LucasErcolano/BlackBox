#!/usr/bin/env bash
# Assemble a ~3-min silent demo from Lucas's editor raw footage pack.
set -euo pipefail
CLIPS="/tmp/bb_editor_pack/demo_assets/editor_raw_footage_pack/clips"
TMP="/tmp/bb_combined/work"; rm -rf "$TMP"; mkdir -p "$TMP"
OUT_DIR="/tmp/bb_combined"
OUT="$OUT_DIR/blackbox_demo_combined_silent.mp4"

# Each entry: source_clip target_duration_seconds
# Total target ~ 172s
declare -a SLOTS=(
  "13_sanfer_real_camera_broll.mp4 10.0"        # 1. hook: real robot footage
  "01_intake_upload_ui.mp4         10.0"        # 2. operator intake
  "02_live_analysis_ui.mp4         14.0"        # 3. analysis running
  "03_managed_agent_stream_ui.mp4  12.0"        # 4. managed agent
  "04_report_overview_ui.mp4       13.0"        # 5. verdict reveal
  "09_operator_refutation_report.mp4 11.0"      # 6. operator vs BB refutation
  "10_rtk_root_cause_charts.mp4    13.0"        # 7. root-cause evidence
  "06_patch_diff_ui.mp4            12.0"        # 8. scoped patch
  "17_opus47_delta_doc_scroll.mp4  14.0"        # 9. model delta
  "20_vision_ab_artifact.mp4       8.0"         # 10. vision A/B
  "07_cases_archive_ui.mp4         12.0"        # 11. breadth
  "16_other_car_run_broll.mp4      9.0"         # 12. second car
  "15_boat_report_broll.mp4        9.0"         # 13. boat case
  "08_grounding_gate_ui.mp4        10.0"        # 14. refuses to invent
  "19_opus47_delta_panel_real_capture.mp4 6.5"  # 15. close
)

norm() {
  local src="$1" dst="$2" dur="$3"
  ffmpeg -y -hide_banner -loglevel error -i "$src" -an \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,fps=30,format=yuv420p" \
    -t "$dur" -c:v libx264 -preset veryfast -crf 18 -movflags +faststart "$dst"
}

i=1
for entry in "${SLOTS[@]}"; do
  read -r name dur <<<"$entry"
  printf "[%02d/%d] %-40s -> %4ss\n" "$i" "${#SLOTS[@]}" "$name" "$dur"
  norm "$CLIPS/$name" "$TMP/$(printf '%02d' $i).mp4" "$dur"
  i=$((i+1))
done

LIST="$TMP/list.txt"; : > "$LIST"
for f in "$TMP"/*.mp4; do
  [[ "$f" == "$LIST" ]] && continue
  echo "file '$f'" >> "$LIST"
done

echo "[concat]"
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$LIST" \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT"

dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")
size=$(du -h "$OUT" | cut -f1)
printf "\nOK -> %s\n  duration: %ss\n  size:     %s\n" "$OUT" "$dur" "$size"
