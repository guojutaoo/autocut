#!/bin/bash
set -e

VIDEO_PATH="/Users/bytedance/Downloads/01.mp4"
OUT_DIR="outputs/autocut_project"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

rm -rf "$OUT_DIR/faces"

python3 -m src.cli.xhs_autocut \
  --video "$VIDEO_PATH" \
  --out "$OUT_DIR" \
  --faces-only \
  --faces-sample-sec 3 \
  --skip-start 60 \
  --skip-end 60

python3 scripts/face_montage_by_person.py \
  --index "$OUT_DIR/faces/all_frames/index.jsonl" \
  --out-dir "$OUT_DIR/faces/montage" \
  --tiles 25 \
  --cols 5 \
  --tile-size 160x160 \
  --max-pids 40 \
  --no-include-unknown

python3 - <<'PY'
import json, os
out_dir = os.path.abspath("outputs/autocut_project")
index_path = os.path.join(out_dir, "faces", "all_frames", "index.jsonl")
names_path = os.path.abspath("people_names.json")
try:
    with open(names_path, "r", encoding="utf-8") as f:
        existing = json.load(f) or {}
except Exception:
    existing = {}
if not isinstance(existing, dict):
    existing = {}
people_ids = set()
with open(index_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            r = json.loads(line)
        except Exception:
            continue
        pid = r.get("person_id")
        if isinstance(pid, str) and pid and pid.startswith("p"):
            people_ids.add(pid)
for pid in sorted(people_ids):
    existing.setdefault(pid, "")
with open(names_path, "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
print("people_names.json updated:", names_path, "pids=", len(people_ids))
PY
