"""Action mapping: map triggers to concrete editing placeholders.

For this PoC we only implement freeze-frame image extraction. Audio
operations (BGM ducking, whoosh/stinger) are represented as metadata in
``triggers.json`` and left as TODOs for downstream pipelines.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Sequence

logger = logging.getLogger(__name__)

try:  # Optional dependency
    import cv2  # type: ignore

    HAS_CV2 = True
except Exception:  # pragma: no cover - optional path
    cv2 = None  # type: ignore
    HAS_CV2 = False


class ActionMapper:
    """Map fused triggers to concrete editing actions.

    Currently supported actions:

    - Freeze frame extraction to ``frames`` directory.
    - JSON manifest with triggers and high-level audio placeholder actions.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        freeze_cfg = self.config.get("freeze_frame", {})
        self.freeze_enabled: bool = bool(freeze_cfg.get("enabled", True))

    # ------------------------------------------------------------------
    def generate_freeze_frames(
        self,
        video_path: str,
        triggers: Sequence[Dict[str, Any]],
        frames_dir: str,
    ) -> List[str]:
        """Generate freeze-frame images for triggers.

        Returns a list of generated image file paths.
        """
        if not self.freeze_enabled:
            logger.info("Freeze frame generation is disabled by config.")
            return []

        if not HAS_CV2:
            logger.warning("OpenCV not available, cannot generate freeze frames.")
            return []

        os.makedirs(frames_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)  # type: ignore[attr-defined]
        if not cap.isOpened():
            logger.error("Failed to open video for freeze frames: %s", video_path)
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        generated: List[str] = []

        try:
            for idx, trig in enumerate(triggers):
                t = float(trig.get("time", 0.0))
                frame_index = int(t * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = cap.read()
                if not ret:
                    continue
                out_name = f"frame_{idx:04d}_{int(t * 1000):06d}.jpg"
                out_path = os.path.join(frames_dir, out_name)
                ok = cv2.imwrite(out_path, frame)  # type: ignore[attr-defined]
                if ok:
                    generated.append(out_path)
        finally:
            cap.release()

        logger.info("Generated %d freeze-frame images", len(generated))
        return generated

    # ------------------------------------------------------------------
    @staticmethod
    def save_triggers_json(triggers: Sequence[Dict[str, Any]], out_path: str) -> None:
        """Persist triggers into a JSON file."""
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(triggers, f, ensure_ascii=False, indent=2)

