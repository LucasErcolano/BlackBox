#!/usr/bin/env bash
# v1: regenerate blocks 03 & 05 with video slowdown to match audio (eliminate freeze).
# All other blocks reuse v0 normalized clips from data/demo/blocks/.
set -euo pipefail

ROOT="/home/hz/Desktop/BlackBox"
VID="$ROOT/video_assets"
AUD="/tmp/demo_audio"
OUT="$ROOT/data/demo"
BLK_V0="$OUT/blocks"
BLK_V1="$OUT/blocks_v1"
mkdir -p "$BLK_V1"

dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

# stretched blocks: video slowed via setpts to audio duration
stretch_block() {
  local name="$1" vfile="$2" afile="$3"
  local vd ad ratio out
  vd=$(dur "$vfile"); ad=$(dur "$afile")
  # setpts multiplier = target_dur / source_dur
  ratio=$(awk -v a="$ad" -v b="$vd" 'BEGIN{printf "%.6f", a/b}')
  out="$BLK_V1/${name}.mp4"
  echo ">> $name  v=${vd} a=${ad}  setpts*=${ratio}"
  ffmpeg -y -hide_banner -loglevel warning \
    -i "$vfile" -i "$afile" \
    -filter_complex "[0:v]setpts=${ratio}*PTS,fps=30,scale=1920:1080,setsar=1,trim=duration=${ad},setpts=PTS-STARTPTS[v];[1:a]apad,atrim=duration=${ad},asetpts=PTS-STARTPTS[a]" \
    -map "[v]" -map "[a]" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -ar 48000 -ac 2 \
    -t "$ad" \
    "$out"
}

stretch_block block_03_setup \
  "$VID/block_03_setup/clip.mp4" \
  "$AUD/[0:30–0:45] SETUP.mp3"

stretch_block block_05_first_moment \
  "$VID/block_05_first_moment/clip.mp4" \
  "$AUD/[1:15–1:35] FIRST MOMENT — [FINDING_1].mp3"

# build concat list: v1 stretched versions for 03+05, v0 for rest
ORDER=(block_01_hook block_02_problem block_03_setup block_04_analysis_live_v2 \
       block_05_first_moment block_06_second_moment block_07_grounding \
       block_08_money_shot block_09_punchline block_10_outro)

: > "$OUT/concat_v1.txt"
for name in "${ORDER[@]}"; do
  if [[ -f "$BLK_V1/${name}.mp4" ]]; then
    echo "file '$BLK_V1/${name}.mp4'" >> "$OUT/concat_v1.txt"
  else
    echo "file '$BLK_V0/${name}.mp4'" >> "$OUT/concat_v1.txt"
  fi
done

ffmpeg -y -hide_banner -loglevel warning \
  -f concat -safe 0 -i "$OUT/concat_v1.txt" \
  -c copy "$OUT/demo_v1_nopad.mp4"

echo "done: $OUT/demo_v1_nopad.mp4"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/demo_v1_nopad.mp4"
