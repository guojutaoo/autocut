"""CLI entry point for freeze-frame + narration composition.

Example:
    python -m src.cli.compose \
        --video outputs/sample_input/sample.avi \
        --triggers outputs/demo_run2/triggers.json \
        --out outputs/final_5min \
        --narration "这一段是权谋博弈的核心转折，皇上宣旨导致兵权重新分配。" \
        --target-duration 300
"""
from __future__ import annotations

import argparse
import logging
import os
from typing import Any, Optional

from ..render.ffmpeg_compose import ComposeResult, compose_from_triggers
from ..tts.tts_edge import synthesize


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(name)s: %(message)s")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compose freeze-frame highlight clips with optional TTS narration"
        )
    )
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument(
        "--triggers",
        required=True,
        help="Path to triggers.json produced by the analysis pipeline",
    )
    parser.add_argument("--out", required=True, help="Output directory for artifacts")

    parser.add_argument(
        "--narration",
        help=(
            "Optional narration text to synthesize and overlay on freeze segments; "
            "if omitted, only original audio is used."
        ),
    )
    parser.add_argument(
        "--voice",
        default="zh-CN-XiaoxiaoNeural",
        help="edge-tts voice name (default: zh-CN-XiaoxiaoNeural)",
    )
    parser.add_argument(
        "--rate",
        default="0%",
        help="Relative speech rate for edge-tts, e.g. +10%% / -20%% / 0%%",
    )
    parser.add_argument(
        "--volume",
        default="0%",
        help="Relative volume for edge-tts, e.g. +0%% / -10%%",
    )
    parser.add_argument(
        "--target-duration",
        type=float,
        default=0.0,
        help=(
            "Target composed video duration in seconds; "
            "0 means no explicit target and all segments are used."
        ),
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser


def main(argv: Any = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    logger = logging.getLogger("compose_cli")

    video_path = args.video
    triggers_path = args.triggers
    out_dir = args.out

    if not os.path.exists(video_path):
        logger.error("Input video does not exist: %s", video_path)
        raise SystemExit(1)

    if not os.path.exists(triggers_path):
        logger.error("Triggers file does not exist: %s", triggers_path)
        raise SystemExit(1)

    os.makedirs(out_dir, exist_ok=True)

    narration_audio: Optional[str] = None
    if args.narration:
        tts_out = os.path.join(out_dir, "narration.mp3")
        logger.info("Synthesizing narration TTS to %s", tts_out)
        narration_audio = synthesize(
            text=args.narration,
            out_path=tts_out,
            voice=args.voice,
            rate=args.rate,
            volume=args.volume,
        )
        logger.info("Narration audio ready at %s", narration_audio)
    else:
        logger.info("No narration text provided; composing without TTS overlay.")

    logger.info("Composing highlights from triggers...")
    result: ComposeResult = compose_from_triggers(
        video_path=video_path,
        triggers_path=triggers_path,
        out_dir=out_dir,
        narration_audio=narration_audio,
        target_duration_sec=float(getattr(args, "target_duration", 0.0)),
    )

    if result.ffmpeg_available and result.output_video:
        logger.info("Compose video generated at %s", result.output_video)
    elif not result.ffmpeg_available:
        logger.info("ffmpeg not available; compose.mp4 could not be generated.")
    else:
        logger.warning(
            "ffmpeg was available but compose.mp4 could not be generated; "
            "see logs above for details.",
        )


if __name__ == "__main__":  # pragma: no cover
    main()
