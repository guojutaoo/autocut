"""Text-side triggers: simple keyword and sentiment-like cues.

This module operates on subtitle lines if available. It does not depend on
external NLP libraries and is intentionally lightweight for offline PoC.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..ingestion.ingestor import SubtitleLine

logger = logging.getLogger(__name__)


class TextTriggerExtractor:
    """Extract text-based trigger events from subtitles.

    Events follow the common structure:

    - ``time``: mid-point of the subtitle interval
    - ``type``: ``"text_keyword"``
    - ``modality``: ``"text"``
    - ``score``: keyword weight in ``[0, 1]``
    - ``details``: ``{"keyword": ..., "text": ...}``
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        # Example keyword config structure:
        # {"keywords": [{"pattern": "圣旨", "weight": 1.0}, ...]}
        self.keywords = self.config.get("keywords") or [
            {"pattern": "圣旨", "weight": 1.0},
            {"pattern": "皇上", "weight": 0.8},
            {"pattern": "夺嫡", "weight": 1.0},
            {"pattern": "交接兵权", "weight": 1.0},
            {"pattern": "反转", "weight": 0.9},
        ]

    def extract(self, subtitles: List[SubtitleLine]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not subtitles:
            logger.info("No subtitles provided, skipping text triggers.")
            return events

        for line in subtitles:
            text = line.text
            t_mid = (line.start + line.end) / 2.0
            for kw in self.keywords:
                pattern = str(kw.get("pattern", "")).strip()
                if not pattern:
                    continue
                weight = float(kw.get("weight", 1.0))
                if pattern in text:
                    events.append(
                        {
                            "time": float(t_mid),
                            "type": "text_keyword",
                            "modality": "text",
                            "score": max(0.0, min(weight, 1.0)),
                            "details": {
                                "keyword": pattern,
                                "text": text,
                            },
                        }
                    )

        logger.info("TextTriggerExtractor produced %d events", len(events))
        return events
