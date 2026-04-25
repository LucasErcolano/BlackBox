#!/usr/bin/env bash
# Assemble final 2:55 demo. Re-encode every segment to a normalized intermediate
# (1920x1080, 30fps, yuv420p, libx264 CRF18, silent), then concat-demuxer.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACK="$ROOT/demo_assets/final_demo_pack"
CLIPS="$PACK/clips"
PANELS="$PACK/panels"
TMP="/tmp/bb_tl"; rm -rf "$TMP"; mkdir -p "$TMP"
OUTDIR="$PACK/final_video"; mkdir -p "$OUTDIR"

# ---------- normalize a video clip ----------
norm_clip() { # in_file out_file dur
  ffmpeg -y -hide_banner -loglevel error -i "$1" -an \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,fps=30,format=yuv420p" \
    -t "$3" -c:v libx264 -preset veryfast -crf 18 -movflags +faststart "$2"
}

# ---------- still PNG → static mp4 (no zoompan: too slow on 3840x2160) ----------
norm_still() { # png out dur _unused
  ffmpeg -y -hide_banner -loglevel error -loop 1 -t "$3" -i "$1" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,fps=30,format=yuv420p" \
    -c:v libx264 -preset veryfast -tune stillimage -crf 20 -r 30 -movflags +faststart "$2"
}

echo "[1/12] hook"      ; norm_clip  "$CLIPS/block_01_hook.mp4"             "$TMP/01.mp4" 11.0
echo "[2/12] problem"   ; norm_clip  "$CLIPS/block_02_problem.mp4"          "$TMP/02.mp4" 14.5
echo "[3/12] setup"     ; norm_clip  "$CLIPS/block_03_setup.mp4"            "$TMP/03.mp4" 18.6
echo "[4/12] live UI"   ; norm_clip  "$CLIPS/block_04_analysis_live_v2.mp4" "$TMP/04.mp4" 21.0
echo "[5/12] second"    ; norm_clip  "$CLIPS/block_06_second_moment.mp4"    "$TMP/05.mp4" 19.4
echo "[6/12] operator"  ; norm_still "$PANELS/operator_vs_blackbox.png"     "$TMP/06.mp4" 14.0 in
echo "[7/12] money"     ; norm_clip  "$CLIPS/block_08_money_shot.mp4"       "$TMP/07.mp4" 14.5
echo "[8/12] opus47"    ; norm_still "$PANELS/opus47_delta_panel.png"       "$TMP/08.mp4" 14.0 out
echo "[9/12] breadth"   ; norm_still "$PANELS/breadth_montage.png"          "$TMP/09.mp4" 13.0 in
echo "[10/12] grounding"; norm_clip  "$CLIPS/block_07_grounding.mp4"        "$TMP/10.mp4" 17.5
echo "[11/12] punch"    ; norm_clip  "$CLIPS/block_09_punchline.mp4"        "$TMP/11.mp4" 12.5
echo "[12/12] outro"    ; norm_clip  "$CLIPS/block_10_outro.mp4"            "$TMP/12.mp4" 9.5

# ---------- concat ----------
LIST="$TMP/list.txt"; : > "$LIST"
for i in 01 02 03 04 05 06 07 08 09 10 11 12; do
  echo "file '$TMP/$i.mp4'" >> "$LIST"
done

OUT_NOAUD="$OUTDIR/blackbox_demo_final_3min_no_audio.mp4"
OUT_FULL="$OUTDIR/blackbox_demo_final_3min.mp4"

echo "[concat] no-audio master"
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$LIST" \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT_NOAUD"

echo "[concat] +silent AAC track for downstream NLEs"
ffmpeg -y -hide_banner -loglevel error -i "$OUT_NOAUD" \
  -f lavfi -t 179.5 -i "anullsrc=channel_layout=stereo:sample_rate=48000" \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT_FULL"

ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_name -of default=nw=1 "$OUT_FULL"
du -h "$OUT_NOAUD" "$OUT_FULL"
