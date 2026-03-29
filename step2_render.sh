#!/bin/bash
python3 -m src.cli.xhs_autocut \
  --video /Users/bytedance/Downloads/01.mp4 \
  --out outputs/autocut_project \
  --freeze-effect camera_click \
  --verbose \
  --render
