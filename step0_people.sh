#!/bin/bash
set -e

VIDEO_PATH="/Users/bytedance/Downloads/01.mp4"
OUT_DIR="outputs/autocut_project"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

export AUTOCUT_ASR_MODEL="${AUTOCUT_ASR_MODEL:-medium}"
export AUTOCUT_ASR_LANG="${AUTOCUT_ASR_LANG:-zh}"

rm -rf "$OUT_DIR/faces"

BASE_NAME="$(basename "$VIDEO_PATH")"
VIDEO_STEM="${BASE_NAME%.*}"
SRT_PATH="$OUT_DIR/transcription/${VIDEO_STEM}.srt"

if [ ! -f "$SRT_PATH" ]; then
  mkdir -p "$OUT_DIR/transcription"
  python3 scripts/transcribe_video.py \
    --input "$VIDEO_PATH" \
    --out-dir "$OUT_DIR/transcription" \
    --model "$AUTOCUT_ASR_MODEL" \
    --language "$AUTOCUT_ASR_LANG" \
    --format "srt"
fi

python3 -m src.cli.xhs_autocut \
  --video "$VIDEO_PATH" \
  --out "$OUT_DIR" \
  --subtitle "$SRT_PATH" \
  --transcribe \
  --skip-start 60 \
  --skip-end 60

python3 - <<'PY'
import json, os
out_dir = os.path.abspath("outputs/autocut_project")
names_path = os.path.abspath("people_names.json")
src_names_path = os.path.join(out_dir, "people_names.json")
try:
    with open(names_path, "r", encoding="utf-8") as f:
        existing = json.load(f) or {}
except Exception:
    existing = {}
if not isinstance(existing, dict):
    existing = {}
try:
    with open(src_names_path, "r", encoding="utf-8") as f:
        src = json.load(f) or {}
except Exception:
    src = {}
if isinstance(src, dict):
    for k, v in src.items():
        if isinstance(k, str) and k.startswith("p"):
            existing.setdefault(k, v if isinstance(v, str) else "")
with open(names_path, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
print("people_names.json updated:", names_path, "pids=", len([k for k in existing.keys() if isinstance(k, str) and k.startswith('p')]))
PY
