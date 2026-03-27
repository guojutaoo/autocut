"""Audio-side analysis: extract simple beat / intensity features.

If a trained emotion classifier is not available, we only return onset and
RMS-based intensity cues as audio events, which can still be fused with
vision/text triggers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:  # Optional dependency
    import librosa  # type: ignore
    import numpy as np  # type: ignore

    HAS_LIBROSA = True
except Exception:  # pragma: no cover - optional path
    librosa = None  # type: ignore
    np = None  # type: ignore
    HAS_LIBROSA = False


class AudioAnalyzer:
    """Analyze audio for beat / intensity features.

    Public events are dictionaries with keys:

    - ``time``: time in seconds
    - ``type``: e.g. ``"audio_beat"`` or ``"audio_intensity_peak"``
    - ``modality``: always ``"audio"`` here
    - ``score``: confidence / intensity in ``[0, 1]``
    - ``details``: backend-specific extra data
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.min_intensity: float = float(self.config.get("min_intensity", 0.3))
        self.min_onset_strength: float = float(self.config.get("min_onset_strength", 0.3))

    def analyze(self, audio_source_path: str) -> List[Dict[str, Any]]:
        """Run audio analysis on the given file path.

        Args:
            audio_source_path: Path to an audio-capable file (wav/mp3/mp4).
        """
        events: List[Dict[str, Any]] = []

        if not HAS_LIBROSA:
            logger.warning("librosa not available, skipping audio analysis.")
            return events

        try:
            y, sr = librosa.load(audio_source_path, sr=None, mono=True)  # type: ignore[call-arg]
        except Exception as exc:  # pragma: no cover - codec issues
            logger.warning("Failed to load audio for analysis: %s", exc)
            return events

        if y.size == 0:  # type: ignore[union-attr]
            return events

        # Onset (beat) detection
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)  # type: ignore[arg-type]
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        except Exception as exc:  # pragma: no cover
            logger.debug("Onset detection failed: %s", exc)
            onset_times = []  # type: ignore[assignment]

        # RMS-based intensity
        try:
            hop_length = 512
            frame_length = 2048
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            rms_times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)
            max_rms = float(rms.max()) if rms.size else 1.0
        except Exception as exc:  # pragma: no cover
            logger.debug("RMS computation failed: %s", exc)
            rms_times = []  # type: ignore[assignment]
            rms = None  # type: ignore[assignment]
            max_rms = 1.0

        # Create beat events
        for t in onset_times:
            events.append(
                {
                    "time": float(t),
                    "type": "audio_beat",
                    "modality": "audio",
                    "score": 1.0,
                    "details": {},
                }
            )

        # Create intensity peaks (simple thresholding)
        if rms is not None and len(rms_times) == len(rms):
            for t, v in zip(rms_times, rms):
                norm = float(v) / max_rms if max_rms > 0 else 0.0
                if norm >= self.min_intensity:
                    events.append(
                        {
                            "time": float(t),
                            "type": "audio_intensity_peak",
                            "modality": "audio",
                            "score": norm,
                            "details": {
                                "rms": float(v),
                            },
                        }
                    )

        logger.info("AudioAnalyzer produced %d events", len(events))
        return events
