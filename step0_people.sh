#!/bin/bash
set -e

VIDEO_PATH="/Users/bytedance/Downloads/01.mp4"
OUT_DIR="outputs/autocut_project"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

rm -rf "$OUT_DIR/people_library"
rm -rf "$OUT_DIR/transcription"

export AUTOCUT_ASR_MODEL="medium"
export AUTOCUT_ASR_LANG="zh"

python3 -m src.cli.xhs_autocut \
  --video "$VIDEO_PATH" \
  --out "$OUT_DIR" \
  --transcribe \
  --skip-start 60 \
  --skip-end 60

python3 -m src.cli.people_library \
  --video "$VIDEO_PATH" \
  --out "$OUT_DIR/people_library" \
  --full \
  --sample-sec 3 \
  --top-people 12 \
  --max-images-per-person 200 \
  --transcript "$OUT_DIR/transcript_for_llm.txt" \
  --names "$ROOT_DIR/people_names.json"
