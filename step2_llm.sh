#!/bin/bash
set -e

VIDEO_PATH="/Users/bytedance/Downloads/01.mp4"
OUT_DIR="outputs/autocut_project"
LLM_DIR="$OUT_DIR/llm_input"

SKELETON="$LLM_DIR/skeleton.json"
NARR_DIR="$LLM_DIR/narrations"
POLISH="$LLM_DIR/polish.json"
SCRIPT_OUT="$LLM_DIR/script.json"

if [ ! -f "$SKELETON" ]; then
  echo "missing: $SKELETON"
  exit 2
fi
if [ ! -d "$NARR_DIR" ]; then
  echo "missing: $NARR_DIR"
  exit 2
fi

VIDEO_DURATION="$(python3 - <<PY
from src.render.ffmpeg_compose import _get_video_duration
print(_get_video_duration("$VIDEO_PATH"))
PY
)"

python3 scripts/assemble_script.py \
  --skeleton "$SKELETON" \
  --narrations "$NARR_DIR" \
  --polish "$POLISH" \
  --video-duration "$VIDEO_DURATION" \
  --out "$SCRIPT_OUT"

echo "script: $SCRIPT_OUT"
echo "report: $LLM_DIR/validation_report.txt"

