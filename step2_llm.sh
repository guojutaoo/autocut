#!/bin/sh
set -e

VIDEO_PATH="${VIDEO_PATH:-/Users/bytedance/Downloads/01.mp4}"
TRANSCRIPT_PATH="${TRANSCRIPT_PATH:-outputs/autocut_project/transcript_for_llm.txt}"
SYNOPSIS_PATH="${SYNOPSIS_PATH:-}"
SKILL1_PATH="${SKILL1_PATH:-outputs/step2.json}"
OUT_DIR="${OUT_DIR:-}"
NO_FRAMES=0
CONTEXT_WINDOW="${CONTEXT_WINDOW:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --video)
      VIDEO_PATH="$2"
      shift 2
      ;;
    --transcript)
      TRANSCRIPT_PATH="$2"
      shift 2
      ;;
    --synopsis)
      SYNOPSIS_PATH="$2"
      shift 2
      ;;
    --skill1)
      SKILL1_PATH="$2"
      shift 2
      ;;
    --out)
      OUT_DIR="$2"
      shift 2
      ;;
    --context-window)
      CONTEXT_WINDOW="$2"
      shift 2
      ;;
    --no-frames)
      NO_FRAMES=1
      shift 1
      ;;
    *)
      echo "unknown arg: $1"
      exit 2
      ;;
  esac
done

if [ -z "$VIDEO_PATH" ]; then
  echo "missing: --video"
  exit 2
fi
if [ -z "$TRANSCRIPT_PATH" ]; then
  echo "missing: --transcript"
  exit 2
fi
if [ -z "$SKILL1_PATH" ]; then
  echo "missing: --skill1"
  exit 2
fi

if [ ! -f "$TRANSCRIPT_PATH" ]; then
  echo "missing: $TRANSCRIPT_PATH"
  echo "Hint: 你的 transcript_for_llm.txt 可能只有 Vision Events 没有台词。"
  echo "      请提供 --subtitle SRT 或先跑 xhs_autocut --transcribe 生成字幕。"
  exit 2
fi
if [ ! -f "$SKILL1_PATH" ]; then
  echo "missing: $SKILL1_PATH"
  exit 2
fi
if [ -n "$SYNOPSIS_PATH" ] && [ ! -f "$SYNOPSIS_PATH" ]; then
  echo "missing: $SYNOPSIS_PATH"
  exit 2
fi
if [ ! -f "$VIDEO_PATH" ] && [ "$NO_FRAMES" -ne 1 ]; then
  echo "missing: $VIDEO_PATH"
  exit 2
fi

if [ -z "$OUT_DIR" ]; then
  VIDEO_BASENAME="$(basename "$VIDEO_PATH")"
  VIDEO_STEM="${VIDEO_BASENAME%.*}"
  OUT_DIR="outputs/step2/${VIDEO_STEM}"
fi

set -- python3 scripts/export_step2.py --transcript "$TRANSCRIPT_PATH" --video "$VIDEO_PATH" --skill1 "$SKILL1_PATH" --out "$OUT_DIR"
if [ -n "$SYNOPSIS_PATH" ]; then
  set -- "$@" --synopsis "$SYNOPSIS_PATH"
fi
if [ -n "$CONTEXT_WINDOW" ]; then
  set -- "$@" --context-window "$CONTEXT_WINDOW"
fi
if [ "$NO_FRAMES" -eq 1 ]; then
  set -- "$@" --no-frames
fi

"$@"

echo "step2_out: $OUT_DIR"
