"""Ingestion utilities: read video frames, extract audio, load subtitles.

All functions are best-effort and degrade gracefully when optional
libraries or codecs are unavailable.
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass
from typing import Generator, Iterable, List, Optional, Tuple

try:  # Optional dependency
    import cv2  # type: ignore
    HAS_CV2 = True
except Exception:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore
    HAS_CV2 = False

try:  # Optional dependency
    from pydub import AudioSegment  # type: ignore
    HAS_PYDUB = True
except Exception:  # pragma: no cover - optional dependency
    AudioSegment = None  # type: ignore
    HAS_PYDUB = False

try:  # Optional dependency
    import librosa  # type: ignore
    import numpy as np  # type: ignore
    HAS_AUDIO_ANALYSIS = True
except Exception:  # pragma: no cover
    librosa = None
    np = None
    HAS_AUDIO_ANALYSIS = False

logger = logging.getLogger(__name__)


def get_audio_rms_profile(video_path: str, hop_length: int = 512) -> Optional[Dict[str, Any]]:
    """Compute the RMS energy profile of the audio track."""
    if not HAS_AUDIO_ANALYSIS:
        return None
    try:
        y, sr = librosa.load(video_path, sr=16000, mono=True)
        if len(y) == 0:
            return None
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
        return {"times": times, "rms": rms}
    except Exception as exc:
        logger.warning("Audio analysis failed: %s", exc)
        return None


@dataclass
class SubtitleLine:
    """Simple subtitle line representation.

    Attributes:
        start: Start time in seconds.
        end: End time in seconds.
        text: Text content of the subtitle line.
    """

    start: float
    end: float
    text: str


def read_video_frames(
    video_path: str,
    frame_stride: int = 5,
) -> Generator[Tuple[float, "cv2.Mat"], None, None]:
    """Yield frames from a video at a fixed stride.

    Args:
        video_path: Path to the input video file.
        frame_stride: Read one frame every ``frame_stride`` frames.

    Yields:
        Tuples of (timestamp_sec, frame_bgr).
    """
    if not HAS_CV2:
        logger.warning("OpenCV not available, vision pipeline is disabled.")
        return

    if not os.path.exists(video_path):
        logger.error("Video file does not exist: %s", video_path)
        return

    cap = cv2.VideoCapture(video_path)  # type: ignore[attr-defined]
    if not cap.isOpened():
        logger.error("Failed to open video: %s", video_path)
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_index = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_index % frame_stride == 0:
                ts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                yield ts_ms / 1000.0, frame
            frame_index += 1
    finally:
        cap.release()


def extract_audio_to_wav(video_path: str, out_dir: str) -> Optional[str]:
    """Extract audio track from ``video_path`` into a WAV file.

    This uses :mod:`pydub` if available. If extraction fails for any reason,
    ``None`` is returned and callers should gracefully skip audio features.

    Args:
        video_path: Input video file path.
        out_dir: Directory to place the extracted audio file.

    Returns:
        Path to the generated WAV file, or ``None`` if extraction failed.
    """
    os.makedirs(out_dir, exist_ok=True)

    if not HAS_PYDUB:
        logger.warning("pydub not available, skipping audio extraction.")
        return None

    if not os.path.exists(video_path):
        logger.error("Video file does not exist: %s", video_path)
        return None

    try:
        audio = AudioSegment.from_file(video_path)  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - codec issues
        logger.warning("Failed to decode audio from video: %s", exc)
        return None

    out_path = os.path.join(out_dir, "audio_track.wav")
    try:
        audio.export(out_path, format="wav")  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to export audio wav: %s", exc)
        return None

    return out_path


_SRT_TIME_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})",
)


def _parse_srt_timestamp(ts: str) -> float:
    match = _SRT_TIME_RE.match(ts.strip())
    if not match:
        return 0.0
    h = int(match.group("h"))
    m = int(match.group("m"))
    s = int(match.group("s"))
    ms = int(match.group("ms"))
    return h * 3600 + m * 60 + s + ms / 1000.0


def load_subtitles_for_video(video_path: str) -> List[SubtitleLine]:
    """Load an ``.srt`` subtitle file.

    If ``video_path`` ends with ``.srt``, it's used directly.
    Otherwise, the function looks for a file with the same basename as ``video_path``
    and ``.srt`` extension.
    """
    if video_path.lower().endswith(".srt"):
        srt_path = video_path
    else:
        base, _ = os.path.splitext(video_path)
        srt_path = base + ".srt"

    if not os.path.exists(srt_path):
        logger.info("No subtitle file found at: %s", srt_path)
        return []

    lines: List[SubtitleLine] = []
    try:
        with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read().splitlines()
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to read subtitle file: %s", exc)
        return []

    idx = 0
    while idx < len(raw):
        # Skip index line
        if raw[idx].strip().isdigit():
            idx += 1
        if idx >= len(raw):
            break
        if "-->" not in raw[idx]:
            idx += 1
            continue

        time_line = raw[idx]
        idx += 1
        try:
            start_str, end_str = [p.strip() for p in time_line.split("-->")]
            start = _parse_srt_timestamp(start_str)
            end = _parse_srt_timestamp(end_str)
        except Exception:  # pragma: no cover
            continue

        text_lines: List[str] = []
        while idx < len(raw) and raw[idx].strip():
            text_lines.append(raw[idx].strip())
            idx += 1
        # Skip blank line
        idx += 1

        if text_lines:
            lines.append(SubtitleLine(start=start, end=end, text=" ".join(text_lines)))

    logger.info("Loaded %d subtitle lines from %s", len(lines), srt_path)
    return lines
