#!/usr/bin/env bash
# Assemble the final 3:00 visual-only BlackBox demo.
#
# Inputs (must already exist):
#   video_assets/block_sanfer_evidence/clip.mp4     (Batch A — 70s)
#   video_assets/block_credibility_opus47/clip.mp4  (Batch B — 45.5s)
#   video_assets/final_ui_capture/{clip,intake_ui,managed_agent_stream_ui,
#                                  patch_human_review_ui}.mp4
#   video_assets/ui_feature_inserts/evidence_trace_insert.mp4
#
# Output:
#   video_assets/final_demo/final_demo_3min_visual_only.mp4   (3:00.0 exact)
#   video_assets/final_demo/final_demo_3min_visual_only_preview.png
#
# Style: dark hook cards, 0.2s fade in/out per segment, no captions, silent.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d -t bb_final_demo.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
OUTDIR="video_assets/final_demo"; mkdir -p "$OUTDIR"

F_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG="0x0e0f0a"
INK="0xe8e3d4"
TODAY="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

ff() { ffmpeg -y -hide_banner -loglevel error "$@"; }

hook_card() { # text out dur fadein fadeout
  local TXT="$1" OUT="$2" DUR="$3" FIN="$4" FOUT="$5"
  local FOUT_ST; FOUT_ST=$(echo "$DUR - $FOUT" | bc -l)
  ff -f lavfi -i "color=c=${BG}:s=1920x1080:r=30:d=${DUR}" \
    -vf "drawtext=fontfile=${F_BOLD}:text='${TXT}':fontcolor=${INK}:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2,fade=t=in:st=0:d=${FIN},fade=t=out:st=${FOUT_ST}:d=${FOUT}" \
    -c:v libx264 -pix_fmt yuv420p -an "$OUT"
}

trim_fade() { # in ss t out
  local IN="$1" SS="$2" T="$3" OUT="$4"
  local FOUT_ST; FOUT_ST=$(echo "$T - 0.2" | bc -l)
  ff -ss "$SS" -i "$IN" -t "$T" \
    -vf "fps=30,scale=1920:1080,setsar=1,fade=t=in:st=0:d=0.2,fade=t=out:st=${FOUT_ST}:d=0.2" \
    -c:v libx264 -pix_fmt yuv420p -an "$OUT"
}

echo "[hook] dark slates"
hook_card "The operator blamed the tunnel."   "$TMP/01a.mp4" 4 0.4 0.3
hook_card "Black Box checked the recording."  "$TMP/01b.mp4" 4 0.3 0.2

echo "[02] product problem (intake)"
trim_fade video_assets/final_ui_capture/intake_ui.mp4                0  10 "$TMP/02a.mp4"
trim_fade video_assets/final_ui_capture/clip.mp4                     0   3 "$TMP/02b.mp4"
echo "[03] setup"
trim_fade video_assets/final_ui_capture/clip.mp4                     3  13 "$TMP/03.mp4"
echo "[04] live agent surface"
trim_fade video_assets/final_ui_capture/managed_agent_stream_ui.mp4  0  17 "$TMP/04.mp4"
echo "[05] visual mining"
trim_fade video_assets/block_sanfer_evidence/clip.mp4                0  13 "$TMP/05.mp4"
echo "[06] refutation (must-keep)"
trim_fade video_assets/block_sanfer_evidence/clip.mp4               13  27 "$TMP/06.mp4"
echo "[07] root cause (must-keep)"
trim_fade video_assets/block_sanfer_evidence/clip.mp4               40  20 "$TMP/07.mp4"
echo "[08] scoped patch + HITL UI (widened)"
trim_fade video_assets/block_sanfer_evidence/clip.mp4               60  10 "$TMP/08a.mp4"
trim_fade video_assets/final_ui_capture/patch_human_review_ui.mp4    0  10 "$TMP/08b.mp4"
echo "[09] Opus 4.7 delta"
trim_fade video_assets/block_credibility_opus47/clip.mp4             0  20 "$TMP/09.mp4"
echo "[10] vision/speed proof"
trim_fade video_assets/block_credibility_opus47/clip.mp4            20  11 "$TMP/10.mp4"
echo "[11] generalization montage"
trim_fade video_assets/block_credibility_opus47/clip.mp4            31   9 "$TMP/11.mp4"
echo "[12] grounding + close"
trim_fade video_assets/block_credibility_opus47/clip.mp4            40 5.5 "$TMP/12a.mp4"
trim_fade video_assets/ui_feature_inserts/evidence_trace_insert.mp4  0 3.5 "$TMP/12b.mp4"

LIST="$TMP/concat.txt"
{
  for f in 01a 01b 02a 02b 03 04 05 06 07 08a 08b 09 10 11 12a 12b; do
    echo "file '$TMP/$f.mp4'"
  done
} > "$LIST"

OUT="$OUTDIR/final_demo_3min_visual_only.mp4"
echo "[concat] -> $OUT"
ff -f concat -safe 0 -i "$LIST" \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -an \
  -metadata "creation_time=${TODAY}" \
  -metadata "title=BlackBox demo (visual only)" \
  -metadata "comment=git=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  "$OUT"

ff -ss 78 -i "$OUT" -frames:v 1 "$OUTDIR/final_demo_3min_visual_only_preview.png"
DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT")
echo "duration=${DUR}s"
