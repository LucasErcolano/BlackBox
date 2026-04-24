#!/usr/bin/env bash
# v2: crossfade 0.5s between v0 normalized blocks.
set -euo pipefail

ROOT="/home/hz/Desktop/BlackBox"
OUT="$ROOT/data/demo"
BLK="$OUT/blocks"

ORDER=(block_01_hook block_02_problem block_03_setup block_04_analysis_live_v2 \
       block_05_first_moment block_06_second_moment block_07_grounding \
       block_08_money_shot block_09_punchline block_10_outro)

XF=0.5  # crossfade seconds

dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

# build ffmpeg input args + filter chain
INPUTS=()
DURS=()
for n in "${ORDER[@]}"; do
  f="$BLK/${n}.mp4"
  INPUTS+=(-i "$f")
  DURS+=($(dur "$f"))
done

N=${#ORDER[@]}

# compute offsets: offset_i = sum(durs[0..i]) - (i+1)*XF  for i>=1
# video chain uses xfade; audio uses acrossfade chained
VFILT=""
AFILT=""
prev_v="[0:v]"
prev_a="[0:a]"
acc=0
for ((i=1;i<N;i++)); do
  # offset for xfade_i = (cumulative duration of prev chain) - XF*i
  # cumulative of blocks 0..i-1
  cum=0
  for ((k=0;k<i;k++)); do
    cum=$(awk -v a="$cum" -v b="${DURS[$k]}" 'BEGIN{printf "%.6f", a+b}')
  done
  off=$(awk -v c="$cum" -v x="$XF" -v i="$i" 'BEGIN{printf "%.6f", c - x*i}')
  VFILT+="${prev_v}[${i}:v]xfade=transition=fade:duration=${XF}:offset=${off}[v${i}];"
  AFILT+="${prev_a}[${i}:a]acrossfade=d=${XF}:c1=tri:c2=tri[a${i}];"
  prev_v="[v${i}]"
  prev_a="[a${i}]"
done

# drop trailing semicolons, set final labels
VFILT="${VFILT%;}"
AFILT="${AFILT%;}"

FC="${VFILT};${AFILT}"

LAST=$((N-1))
ffmpeg -y -hide_banner -loglevel warning \
  "${INPUTS[@]}" \
  -filter_complex "$FC" \
  -map "[v${LAST}]" -map "[a${LAST}]" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  "$OUT/demo_v2_xfade.mp4"

echo "done: $OUT/demo_v2_xfade.mp4"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/demo_v2_xfade.mp4"
