"""Fusion engine: combine multi-modal events into stable triggers.

This module implements a simple rule-based fusion with smoothing, hysteresis
and cooldown. It is intentionally lightweight and fully configurable via a
Python dict (typically loaded from YAML).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence


@dataclass
class FusionConfig:
    weights_vision: float = 0.5
    weights_audio: float = 0.3
    weights_text: float = 0.2
    threshold_on: float = 0.7
    threshold_off: float = 0.4
    cooldown_sec: float = 3.0
    half_life_sec: float = 2.0


class FusionEngine:
    """Fuse vision / audio / text events into editing triggers.

    Input events must be dict-like with fields:

    - ``time`` (float seconds)
    - ``modality`` ("vision"/"audio"/"text")
    - ``score`` (0-1)
    - ``type`` / ``details`` (opaque payload)

    Output triggers are dictionaries:

    - ``time``: trigger timestamp (seconds)
    - ``type``: high-level action type, e.g. ``"freeze_frame"``
    - ``score``: fused score at trigger time
    - ``sources``: list of contributing events around that moment
    """

    def __init__(self, config_dict: Dict[str, Any]):
        cfg = FusionConfig(
            weights_vision=float(config_dict.get("weights", {}).get("vision", 0.5)),
            weights_audio=float(config_dict.get("weights", {}).get("audio", 0.3)),
            weights_text=float(config_dict.get("weights", {}).get("text", 0.2)),
            threshold_on=float(config_dict.get("threshold_on", 0.7)),
            threshold_off=float(config_dict.get("threshold_off", 0.4)),
            cooldown_sec=float(config_dict.get("cooldown_sec", 3.0)),
            half_life_sec=float(config_dict.get("half_life_sec", 2.0)),
        )
        self.cfg = cfg

    # ------------------------------------------------------------------
    def fuse(self, events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not events:
            return []

        ordered = sorted(events, key=lambda e: float(e.get("time", 0.0)))

        v_score = 0.0
        a_score = 0.0
        t_score = 0.0
        last_time = float(ordered[0].get("time", 0.0))
        active = False
        last_trigger_time = -1e9
        triggers: List[Dict[str, Any]] = []

        # For bookkeeping of recent events per trigger
        recent_events: List[Dict[str, Any]] = []

        def decay_factor(dt: float) -> float:
            if dt <= 0 or self.cfg.half_life_sec <= 0:
                return 1.0
            return 0.5 ** (dt / self.cfg.half_life_sec)

        for ev in ordered:
            t = float(ev.get("time", 0.0))
            dt = max(0.0, t - last_time)
            d = decay_factor(dt)

            v_score *= d
            a_score *= d
            t_score *= d

            modality = ev.get("modality")
            score = float(ev.get("score", 0.0))

            if modality == "vision":
                v_score = max(v_score, score)
            elif modality == "audio":
                a_score = max(a_score, score)
            elif modality == "text":
                t_score = max(t_score, score)

            fused = (
                self.cfg.weights_vision * v_score
                + self.cfg.weights_audio * a_score
                + self.cfg.weights_text * t_score
            )

            # Maintain a small window of recent events around potential triggers
            recent_events.append(ev)
            recent_events = [e for e in recent_events if t - float(e.get("time", 0.0)) <= 2.0]

            if not active:
                if (
                    fused >= self.cfg.threshold_on
                    and t - last_trigger_time >= self.cfg.cooldown_sec
                ):
                    active = True
                    last_trigger_time = t
                    triggers.append(
                        {
                            "time": t,
                            "type": "freeze_frame",
                            "score": fused,
                            "sources": list(recent_events),
                        }
                    )
            else:
                if fused <= self.cfg.threshold_off:
                    active = False

            last_time = t

        return triggers
