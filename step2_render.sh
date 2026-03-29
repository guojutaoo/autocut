#!/bin/bash
set -e

VIDEO_PATH="/Users/bytedance/Downloads/01.mp4"
OUT_DIR="outputs/autocut_project"

python3 -m src.cli.xhs_autocut \
  --video "$VIDEO_PATH" \
  --out "$OUT_DIR" \
  --freeze-effect camera_click \
  --verbose \
  --render
