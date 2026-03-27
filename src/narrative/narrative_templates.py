"""Narrative templates for Chinese commentary over story segments.

The goal of this module is not to be *smart*, but to provide a
rule-based, deterministic way to turn a :class:`StorySegment` into a
Chinese narration text with a clear structure:

    引入 → 点明核心 → 分析 → 升华

The templates are lightweight and offline-friendly, and they can be
replaced by more advanced LLM-based generation later without changing
call sites.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from ..segment.segmenter import StorySegment


def _pick_top_keywords(
    segment: StorySegment, max_keywords: int = 3
) -> List[str]:
    if not segment.keyword_hits:
        return []
    # Sort by accumulated weight (desc), then lexicographically for stability.
    items = sorted(
        segment.keyword_hits.items(), key=lambda kv: (-float(kv[1]), kv[0])
    )
    return [k for k, _ in items[:max_keywords]]


def _shorten(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def build_segment_summary(lines: Iterable[str], max_len: int = 40) -> str:
    """Build a short summary sentence from raw subtitle texts."""

    joined = " ".join([t.strip() for t in lines if t.strip()])
    if not joined:
        return "这一段是剧情推进中的一个关键桥段。"
    return _shorten(joined, max_len=max_len)


def generate_narration(
    segment: StorySegment,
    title_prefix: Optional[str] = None,
    global_theme: str = "剧情推进",
) -> str:
    """Generate a placeholder Chinese narration that includes the selection reason.

    The output provides a basic structure that should be refined by a 
    higher-level LLM (e.g., via the Video Script Expert skill).
    """

    start = segment.start
    end = segment.end
    summary = build_segment_summary([line.text for line in segment.lines])

    # 1. Parse Selection Reasons from segment metadata
    reasons = []
    
    # Text Keywords
    keywords = [k for k in segment.keyword_hits.keys() if not k.startswith("__")]
    if keywords:
        top_k = sorted(keywords, key=lambda k: segment.keyword_hits[k], reverse=True)[:3]
        reasons.append("台词命中关键词({})".format(", ".join(top_k)))
    
    # Visual Intensity
    if "__visual_intensity__" in segment.keyword_hits:
        v_std = segment.keyword_hits["__visual_intensity__"]
        reasons.append("画面光影剧烈变动(std:{:.1f})".format(v_std))
        
    # Audio Intensity (Volume)
    if "__audio_intensity__" in segment.keyword_hits:
        a_peak = segment.keyword_hits["__audio_intensity__"]
        reasons.append("音量突然增大/检测到声效峰值(RMS:{:.2f})".format(a_peak))

    reason_str = " | ".join(reasons) if reasons else "常规剧情推进"

    # 2. Build the Draft Narration
    intro = "[系统选取理由：{}]。".format(reason_str)
    content = "本段内容：{}。".format(summary)
    
    # 3. Placeholder for LLM refinement
    placeholder = (
        "提示：此段解说词由基础模板生成，建议调用 'Video Script Expert' Skill "
        "基于全片上下文进行深度创作，以匹配《{}》的主题风格。"
    ).format(title_prefix if title_prefix else "本视频")

    return "".join([intro, content, placeholder])
