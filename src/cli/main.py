"""Command-line entry point for the yongzheng_autocut PoC.

Example:
    python -m src.cli.main --video sample.mp4 --config configs/default.yaml --out outputs/demo_run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any, Dict, List

import yaml  # type: ignore

from ..actions.actions import ActionMapper
from ..audio.bgm_emotion import AudioAnalyzer
from ..fusion.fusion_engine import FusionEngine
from ..ingestion.ingestor import extract_audio_to_wav, load_subtitles_for_video
from ..text.text_triggers import TextTriggerExtractor
from ..vision.face_emotion import VisionAnalyzer


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(name)s: %(message)s",
    )


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yongzheng auto-cut PoC")
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--out", required=True, help="Output directory for artifacts")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser


def main(argv: Any = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    logger = logging.getLogger("cli")

    video_path = args.video
    cfg_path = args.config
    out_dir = args.out

    if not os.path.exists(video_path):
        logger.error("Input video does not exist: %s", video_path)
        raise SystemExit(1)

    if not os.path.exists(cfg_path):
        logger.error("Config file does not exist: %s", cfg_path)
        raise SystemExit(1)

    os.makedirs(out_dir, exist_ok=True)

    config = load_config(cfg_path)

    vision_cfg = config.get("vision", {})
    audio_cfg = config.get("audio", {})
    text_cfg = config.get("text", {})
    fusion_cfg = config.get("fusion", {})
    actions_cfg = config.get("actions", {})

    logger.info("Loaded config from %s", cfg_path)

    # Ingestion: subtitles and audio extraction
    subtitles = load_subtitles_for_video(video_path)

    audio_source = video_path
    if audio_cfg.get("enabled", True):
        audio_wav = extract_audio_to_wav(video_path, os.path.join(out_dir, "tmp"))
        audio_source = audio_wav or video_path

    # Vision / audio / text analysis
    vision_analyzer = VisionAnalyzer(vision_cfg)
    audio_analyzer = AudioAnalyzer(audio_cfg)
    text_extractor = TextTriggerExtractor(text_cfg)

    all_events: List[Dict[str, Any]] = []

    logger.info("Running vision analysis...")
    vision_events = vision_analyzer.analyze(video_path)
    all_events.extend(vision_events)

    if audio_cfg.get("enabled", True):
        logger.info("Running audio analysis...")
        audio_events = audio_analyzer.analyze(audio_source)
        all_events.extend(audio_events)
    else:
        logger.info("Audio analysis disabled by config.")

    if text_cfg.get("enabled", True):
        logger.info("Running text trigger extraction...")
        text_events = text_extractor.extract(subtitles)
        all_events.extend(text_events)
    else:
        logger.info("Text triggers disabled by config.")

    logger.info("Total %d raw events from all modalities", len(all_events))

    # Fusion
    fusion_engine = FusionEngine(fusion_cfg)
    triggers = fusion_engine.fuse(all_events)

    logger.info("Fusion engine produced %d triggers", len(triggers))

    # Actions
    frames_dir = os.path.join(out_dir, "frames")
    action_mapper = ActionMapper(actions_cfg)

    logger.info("Generating freeze-frame images...")
    frame_paths = action_mapper.generate_freeze_frames(video_path, triggers, frames_dir)

    triggers_path = os.path.join(out_dir, "triggers.json")
    ActionMapper.save_triggers_json(triggers, triggers_path)

    summary = {
        "video": os.path.abspath(video_path),
        "config": os.path.abspath(cfg_path),
        "out_dir": os.path.abspath(out_dir),
        "triggers_path": os.path.abspath(triggers_path),
        "num_triggers": len(triggers),
        "num_frames": len(frame_paths),
    }
    summary_path = os.path.join(out_dir, "run_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("Run complete. Triggers: %s", triggers_path)
    logger.info("Freeze frames: %s", frames_dir)


if __name__ == "__main__":  # pragma: no cover
    main()
