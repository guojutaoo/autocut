"""Subtitle-based story segmentation utilities.

This module turns a flat list of :class:`SubtitleLine` objects into
higher-level "story segments" that are more suitable for narration and
highlight selection.

Design goals:

* Pure-Python and offline-friendly.
* Light-weight scoring based on keyword weights (shared with text triggers).
* Configurable temporal gap threshold between segments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

from ..ingestion.ingestor import SubtitleLine


@dataclass
class StorySegment:
    """A contiguous group of subtitle lines.

    Attributes:
        id: Integer identifier within the current video.
        start: Start time of the segment in seconds.
        end: End time of the segment in seconds.
        lines: List of :class:`SubtitleLine` objects belonging to the segment.
        score: Segment-level score based on keyword weights.
        keyword_hits: Mapping from keyword pattern to accumulated weight.
    """

    id: int
    start: float
    end: float
    lines: List[SubtitleLine] = field(default_factory=list)
    score: float = 0.0
    keyword_hits: Dict[str, float] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def _build_segments_from_subtitles(
    subtitles: Sequence[SubtitleLine], gap_threshold: float
) -> List[List[SubtitleLine]]:
    """Group subtitles into raw segments by temporal gaps.

    A new segment is started whenever the gap between the *end* of the previous
    line and the *start* of the current line is strictly greater than
    ``gap_threshold`` seconds.
    """

    if not subtitles:
        return []

    sorted_lines = sorted(subtitles, key=lambda s: (s.start, s.end))
    groups: List[List[SubtitleLine]] = []
    current: List[SubtitleLine] = []
    prev_end: float | None = None

    for line in sorted_lines:
        if prev_end is None:
            current = [line]
        else:
            gap = line.start - prev_end
            if gap > gap_threshold:
                if current:
                    groups.append(current)
                current = [line]
            else:
                current.append(line)
        prev_end = line.end

    if current:
        groups.append(current)

    return groups


def _score_segment(
    lines: Iterable[SubtitleLine], keywords: Sequence[Dict[str, float]]
) -> Dict[str, float]:
    """Compute a simple keyword-based score map for a group of lines.

    ``keywords`` is expected to be a sequence of
    ``{"pattern": str, "weight": float}``-like dicts.
    """

    hits: Dict[str, float] = {}
    if not keywords:
        return hits

    for line in lines:
        text = line.text or ""
        for kw in keywords:
            pattern = str(kw.get("pattern", "")).strip()
            if not pattern:
                continue
            weight = float(kw.get("weight", 0.0))
            if pattern in text:
                hits[pattern] = hits.get(pattern, 0.0) + max(0.0, weight)

    return hits


def segment_subtitles(
    subtitles: Sequence[SubtitleLine],
    gap_threshold: float = 6.0,
    keywords: Sequence[Dict[str, float]] | None = None,
) -> List[StorySegment]:
    """Turn subtitle lines into scored story segments.

    Args:
        subtitles: Flat list of subtitle lines.
        gap_threshold: Maximum allowed gap (in seconds) between adjacent lines
            within a segment. Gaps larger than this value will start a new
            segment.
        keywords: Optional list of keyword configurations, usually taken from
            ``TextTriggerExtractor.keywords``.

    Returns:
        A list of :class:`StorySegment` objects sorted by start time.
    """

    groups = _build_segments_from_subtitles(subtitles, gap_threshold=gap_threshold)
    segments: List[StorySegment] = []

    for idx, lines in enumerate(groups):
        start = min(line.start for line in lines)
        end = max(line.end for line in lines)
        hit_map = _score_segment(lines, keywords or [])
        score = sum(hit_map.values()) if hit_map else 0.0
        segments.append(
            StorySegment(
                id=idx,
                start=float(start),
                end=float(end),
                lines=list(lines),
                score=float(score),
                keyword_hits=hit_map,
            )
        )

    # Ensure stable ordering by time.
    segments.sort(key=lambda s: (s.start, s.end))
    return segments
