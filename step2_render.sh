#!/bin/bash
python3 -m src.cli.xhs_autocut \
  --video /Users/bytedance/Downloads/01.mp4 \
  --out outputs/autocut_project \
  --from-plan outputs/autocut_project/video_script_expert_output.json \
  --freeze-effect camera_click \
  --verbose
