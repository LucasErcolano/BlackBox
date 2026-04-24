#!/usr/bin/env bash
# Compose 10-block demo: video_assets/block_* + /tmp/demo_audio/*.mp3
# Per block: target_dur = max(video_dur, audio_dur). Pad shorter track.
set -euo pipefail

ROOT="/home/hz/Desktop/BlackBox"
VID="$ROOT/video_assets"
AUD="/tmp/demo_audio"
OUT="$ROOT/data/demo"
BLK="$OUT/blocks"
mkdir -p "$BLK"

# block_name : audio_file (block_04 uses v2 video)
declare -A MAP=(
  [block_01_hook]="[0:00–0:15] HOOK.mp3"
  [block_02_problem]="[0:15–0:30] PROBLEM.mp3"
  [block_03_setup]="[0:30–0:45] SETUP.mp3"
  [block_04_analysis_live_v2]="[0:45–1:15] ANALYSIS LIVE.mp3"
  [block_05_first_moment]="[1:15–1:35] FIRST MOMENT — [FINDING_1].mp3"
  [block_06_second_moment]="[1:35–1:55] SECOND MOMENT — [FINDING_2].mp3"
  [block_07_grounding]="[1:55–2:15] GROUNDING ／ CREDIBILITY.mp3"
  [block_08_money_shot]="[2:15–2:35] THE MONEY SHOT.mp3"
  [block_09_punchline]="[2:35–2:50] PUNCHLINE.mp3"
  [block_10_outro]="[2:50–3:00] OUTRO ／ CREDIBILITY ON SCREEN.mp3"
)

ORDER=(block_01_hook block_02_problem block_03_setup block_04_analysis_live_v2 \
       block_05_first_moment block_06_second_moment block_07_grounding \
       block_08_money_shot block_09_punchline block_10_outro)

dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
maxf() { awk -v a="$1" -v b="$2" 'BEGIN{print (a>b)?a:b}'; }

: > "$OUT/concat.txt"

for name in "${ORDER[@]}"; do
  v="$VID/$name/clip.mp4"
  a="$AUD/${MAP[$name]}"
  vd=$(dur "$v"); ad=$(dur "$a")
  td=$(maxf "$vd" "$ad")
  out="$BLK/${name}.mp4"
  echo ">> $name  v=${vd}s a=${ad}s  target=${td}s"
  ffmpeg -y -hide_banner -loglevel warning \
    -i "$v" -i "$a" \
    -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=${td},fps=30,scale=1920:1080,setsar=1,trim=duration=${td},setpts=PTS-STARTPTS[v];[1:a]apad,atrim=duration=${td},asetpts=PTS-STARTPTS[a]" \
    -map "[v]" -map "[a]" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -ar 48000 -ac 2 \
    -t "$td" \
    "$out"
  echo "file '$out'" >> "$OUT/concat.txt"
done

echo ">> concat"
ffmpeg -y -hide_banner -loglevel warning \
  -f concat -safe 0 -i "$OUT/concat.txt" \
  -c copy "$OUT/demo_final.mp4"

echo "done: $OUT/demo_final.mp4"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/demo_final.mp4"
