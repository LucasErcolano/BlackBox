#!/usr/bin/env bash
# v3: v1 stretched 03/05 + v2 xfade 0.5s.
set -euo pipefail

ROOT="/home/hz/Desktop/BlackBox"
OUT="$ROOT/data/demo"
BLK_V0="$OUT/blocks"
BLK_V1="$OUT/blocks_v1"

ORDER=(block_01_hook block_02_problem block_03_setup block_04_analysis_live_v2 \
       block_05_first_moment block_06_second_moment block_07_grounding \
       block_08_money_shot block_09_punchline block_10_outro)

XF=0.5
ACF_C1="${ACF_C1:-tri}"
ACF_C2="${ACF_C2:-tri}"
OUTNAME="${OUTNAME:-demo_v3_nopad_xfade.mp4}"

dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

INPUTS=()
DURS=()
for n in "${ORDER[@]}"; do
  if [[ -f "$BLK_V1/${n}.mp4" ]]; then f="$BLK_V1/${n}.mp4"; else f="$BLK_V0/${n}.mp4"; fi
  INPUTS+=(-i "$f")
  DURS+=($(dur "$f"))
done

N=${#ORDER[@]}
VFILT=""; AFILT=""
prev_v="[0:v]"; prev_a="[0:a]"
for ((i=1;i<N;i++)); do
  cum=0
  for ((k=0;k<i;k++)); do
    cum=$(awk -v a="$cum" -v b="${DURS[$k]}" 'BEGIN{printf "%.6f", a+b}')
  done
  off=$(awk -v c="$cum" -v x="$XF" -v i="$i" 'BEGIN{printf "%.6f", c - x*i}')
  VFILT+="${prev_v}[${i}:v]xfade=transition=fade:duration=${XF}:offset=${off}[v${i}];"
  AFILT+="${prev_a}[${i}:a]acrossfade=d=${XF}:c1=${ACF_C1}:c2=${ACF_C2}[a${i}];"
  prev_v="[v${i}]"
  prev_a="[a${i}]"
done
VFILT="${VFILT%;}"; AFILT="${AFILT%;}"
FC="${VFILT};${AFILT}"
LAST=$((N-1))

ffmpeg -y -hide_banner -loglevel warning \
  "${INPUTS[@]}" \
  -filter_complex "$FC" \
  -map "[v${LAST}]" -map "[a${LAST}]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  "$OUT/$OUTNAME"

echo "done: $OUT/$OUTNAME"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$OUTNAME"
