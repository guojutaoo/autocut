#!/bin/bash
VIDEO_PATH="/Users/bytedance/Downloads/01.mp4"
OUT_DIR="outputs/autocut_project"

export AUTOCUT_ASR_MODEL="tiny"
export AUTOCUT_ASR_LANG="zh"

python3 -m src.cli.xhs_autocut \
  --video "$VIDEO_PATH" \
  --out "$OUT_DIR" \
  --target-duration 300 \
  --portrait 1080x1920 \
  --title-prefix '雍正王朝权谋解析' \
  --hashtags '#雍正王朝 #权谋 #历史' \
  --skip-start 60 \
  --skip-end 60 \
  --verbose
