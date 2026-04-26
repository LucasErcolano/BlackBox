#!/usr/bin/env bash
# Final demo render v2.
#
# Fixes vs v1 (build_final_video.sh):
#   1. xfade between every adjacent segment (no more hard cuts).
#   2. Per-block tail trim: drop the held lockup frames that read as "freeze".
#   3. setsar=1 + identical x264 params for every segment so concat-decode
#      doesn't stall at boundaries.
#
# Net runtime stays inside the 2:50–3:00 envelope.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACK="$ROOT/demo_assets/final_demo_pack"
CLIPS="$PACK/clips"
PANELS="$PACK/panels"
TMP="/tmp/bb_tl_v2"; rm -rf "$TMP"; mkdir -p "$TMP"
OUTDIR="$PACK/final_video"; mkdir -p "$OUTDIR"

VF_STD="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,fps=30,format=yuv420p,setsar=1"

norm_clip() { # in_file out_file dur
  ffmpeg -y -hide_banner -loglevel error -i "$1" -an \
    -vf "$VF_STD" -t "$3" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
    -movflags +faststart "$2"
}

norm_still() { # png out dur
  ffmpeg -y -hide_banner -loglevel error -loop 1 -t "$3" -i "$1" \
    -vf "$VF_STD" -r 30 \
    -c:v libx264 -preset medium -tune stillimage -crf 20 -pix_fmt yuv420p \
    -movflags +faststart "$2"
}

# ---------- per-block trimmed durations ----------
# Trims chosen to drop the held "lockup" frame at the end of each PIL clip.
D01=10.7  ; echo "[1/12] hook"      ; norm_clip  "$CLIPS/block_01_hook.mp4"             "$TMP/01.mp4" $D01
D02=13.5  ; echo "[2/12] problem"   ; norm_clip  "$CLIPS/block_02_problem.mp4"          "$TMP/02.mp4" $D02
D03=18.1  ; echo "[3/12] setup"     ; norm_clip  "$CLIPS/block_03_setup.mp4"            "$TMP/03.mp4" $D03
D04=19.6  ; echo "[4/12] live UI"   ; norm_clip  "$CLIPS/block_04_analysis_live_v2.mp4" "$TMP/04.mp4" $D04
D05=18.9  ; echo "[5/12] second"    ; norm_clip  "$CLIPS/block_06_second_moment.mp4"    "$TMP/05.mp4" $D05
D06=14.0  ; echo "[6/12] operator"  ; norm_still "$PANELS/operator_vs_blackbox.png"     "$TMP/06.mp4" $D06
D07=14.1  ; echo "[7/12] money"     ; norm_clip  "$CLIPS/block_08_money_shot.mp4"       "$TMP/07.mp4" $D07
D08=14.0  ; echo "[8/12] opus47"    ; norm_still "$PANELS/opus47_delta_panel.png"       "$TMP/08.mp4" $D08
D09=13.0  ; echo "[9/12] breadth"   ; norm_still "$PANELS/breadth_montage.png"          "$TMP/09.mp4" $D09
D10=17.0  ; echo "[10/12] grounding"; norm_clip  "$CLIPS/block_07_grounding.mp4"        "$TMP/10.mp4" $D10
D11=12.4  ; echo "[11/12] punch"    ; norm_clip  "$CLIPS/block_09_punchline.mp4"        "$TMP/11.mp4" $D11
D12=9.2   ; echo "[12/12] outro"    ; norm_clip  "$CLIPS/block_10_outro.mp4"            "$TMP/12.mp4" $D12

DURS=($D01 $D02 $D03 $D04 $D05 $D06 $D07 $D08 $D09 $D10 $D11 $D12)
N=${#DURS[@]}
XF=0.35

# ---------- xfade chain ----------
INPUTS=()
for i in 01 02 03 04 05 06 07 08 09 10 11 12; do
  INPUTS+=( -i "$TMP/$i.mp4" )
done

FC=""
prev="[0:v]"
cum=0
for ((k=1; k<N; k++)); do
  cum=$(awk -v a="$cum" -v b="${DURS[$((k-1))]}" 'BEGIN{printf "%.4f", a+b}')
  off=$(awk -v c="$cum" -v x="$XF" -v i="$k" 'BEGIN{printf "%.4f", c - x*i}')
  FC+="${prev}[${k}:v]xfade=transition=fade:duration=${XF}:offset=${off}[v${k}];"
  prev="[v${k}]"
done
FC="${FC%;}"
LAST=$((N-1))

OUT_NOAUD="$OUTDIR/blackbox_demo_final_3min_v2_no_audio.mp4"
OUT_FULL="$OUTDIR/blackbox_demo_final_3min_v2.mp4"

echo "[xfade] composite ($N segments, $XF s crossfade each)"
ffmpeg -y -hide_banner -loglevel error "${INPUTS[@]}" \
  -filter_complex "$FC" -map "[v${LAST}]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -movflags +faststart "$OUT_NOAUD"

TOTAL=$(awk -v xf=$XF -v n=$N 'BEGIN{s=0; for (i=1;i<=n;i++){getline x; s+=x}; printf "%.3f", s - xf*(n-1)}' < <(printf "%s\n" "${DURS[@]}"))

echo "[mux] +silent AAC (total ${TOTAL}s)"
ffmpeg -y -hide_banner -loglevel error -i "$OUT_NOAUD" \
  -f lavfi -t "$TOTAL" -i "anullsrc=channel_layout=stereo:sample_rate=48000" \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT_FULL"

ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_name -of default=nw=1 "$OUT_FULL"
du -h "$OUT_NOAUD" "$OUT_FULL"
echo "done: $OUT_FULL"
