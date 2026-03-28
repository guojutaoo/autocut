"""End-to-end XHS-oriented auto-cut CLI.

Running this module produces all key assets needed for a Xiaohongshu
(vertical short-video) post from a single command:

* Story segmentation based on subtitles (fallback to simple visual
  intensity anchors when no subtitles are available);
* Per-segment Chinese narration text and TTS audio;
* A 9:16 portrait render plan and, when ``ffmpeg`` is available,
  an actual ``compose_xhs.mp4``;
* A cover frame image ``cover.jpg``;
* Caption text file ``xhs_caption.txt`` / ``caption.txt``（标题 + 话题 + 摘要）。

Example usage::

    python -m src.cli.xhs_autocut \
      --video outputs/sample_input/sample.avi \
      --out outputs/xhs_demo \
      --target-duration 300 \
      --portrait 1080x1920 \
      --title-prefix "雍正王朝权谋解析" \
      --hashtags "#雍正王朝 #权谋 #历史"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import wave
from typing import Any, Dict, List, Optional, Sequence

from ..ingestion.ingestor import SubtitleLine, load_subtitles_for_video
from ..narrative.narrative_templates import build_segment_summary, generate_narration
from ..segment.segmenter import StorySegment, segment_subtitles
from ..text.text_triggers import TextTriggerExtractor
from ..tts.tts_edge import synthesize
from ..render.ffmpeg_compose import (
    compose_segments_xhs,
    _get_wav_duration_sec,  # type: ignore
    _get_video_duration,
    _has_ffmpeg,  # type: ignore
)

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(name)s: %(message)s")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "One-shot Xiaohongshu-style auto-cut: video -> segments -> narration -> "
            "9:16 plan and assets"
        )
    )
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument("--subtitle", help="Path to input subtitle file (optional, defaults to same name as video)")
    parser.add_argument("--out", required=True, help="Output directory for XHS assets")

    parser.add_argument(
        "--target-duration",
        type=float,
        default=300.0,
        help=(
            "Target duration in seconds for the final highlight reel. "
            "0 or negative means no explicit limit (use all segments)."
        ),
    )
    parser.add_argument(
        "--portrait",
        default="1080x1920",
        help="Portrait resolution, e.g. 1080x1920 (width x height).",
    )
    parser.add_argument(
        "--title-prefix",
        default="",
        help="Recommended title prefix, e.g. 雍正王朝权谋解析",
    )
    parser.add_argument(
        "--hashtags",
        default="",
        help="Hashtags string to append in caption, e.g. '#雍正王朝 #权谋 #历史'",
    )

    parser.add_argument(
        "--skip-start",
        type=float,
        default=30.0,
        help="Skip initial seconds of the video (e.g. to avoid opening theme).",
    )
    parser.add_argument(
        "--skip-end",
        type=float,
        default=30.0,
        help="Skip final seconds of the video (e.g. to avoid ending theme).",
    )

    parser.add_argument(
        "--gap-threshold",
        type=float,
        default=6.0,
        help="Gap threshold in seconds when grouping subtitles into story segments.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging for debugging"
    )
    parser.add_argument(
        "--render", action="store_true", help="Perform TTS synthesis and video rendering (heavy tasks)."
    )
    parser.add_argument(
        "--from-plan", help="Path to an existing compose_plan.json to render from."
    )
    parser.add_argument(
        "--freeze-effect",
        default=None,
        help=(
            "Freeze effect preset name: 'weibo_pop', 'cinematic', 'dramatic', 'subtle', or 'none'. "
            "When set, applies white flash + zoom-in + stinger audio to all freeze segments."
        ),
    )
    return parser


def _load_keywords_for_scoring() -> List[Dict[str, float]]:
    """Reuse TextTriggerExtractor's keyword config for scoring segments."""

    extractor = TextTriggerExtractor(config={})
    # ``keywords`` is a list of dicts; we only care about ``pattern`` and ``weight``.
    keywords: List[Dict[str, float]] = []
    for kw in extractor.keywords:
        pattern = str(kw.get("pattern", "")).strip()
        if not pattern:
            continue
        weight = float(kw.get("weight", 0.0))
        keywords.append({"pattern": pattern, "weight": weight})
    return keywords


def _probe_high_intensity_anchors(
    video_path: str,
    max_anchors: int = 30,
    frame_stride: int = 15,
    min_spacing_sec: float = 15.0,
) -> List[Dict[str, float]]:
    """Fallback: use simple visual intensity to pick anchor timestamps.

    Returns a list of dicts: [{"time": float, "intensity": float}, ...]
    """

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning(
            "OpenCV/numpy not available, cannot compute visual intensity anchors: %s",
            exc,
        )
        return []

    from ..ingestion.ingestor import read_video_frames

    scores: List[tuple[float, float]] = []  # (std, ts)
    for ts, frame in read_video_frames(video_path, frame_stride=frame_stride):
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            std = float(np.std(gray))
        except Exception:  # pragma: no cover - decoding issues
            continue
        scores.append((std, ts))

    if not scores:
        return []

    # Sort by standard deviation descending
    scores.sort(key=lambda x: x[0], reverse=True)
    
    selected: List[Dict[str, float]] = []
    for std, ts in scores:
        if len(selected) >= max_anchors:
            break
        # Simple non-maximum suppression: skip if too close to already selected anchors
        if any(abs(ts - a["time"]) < min_spacing_sec for a in selected):
            continue
        selected.append({"time": ts, "intensity": std})
        
    selected.sort(key=lambda x: x["time"])
    logger.info("Fallback anchors (visual intensity, NMS applied): %d points", len(selected))
    return selected


def _build_fallback_segments_from_anchors(
    anchors: Sequence[Dict[str, float]], pre_window: float = 5.0, post_window: float = 3.0
) -> List[StorySegment]:
    segments: List[StorySegment] = []
    for idx, item in enumerate(anchors):
        t = item["time"]
        std = item["intensity"]
        start = max(0.0, float(t) - pre_window)
        end = float(t) + post_window
        seg = StorySegment(
            id=idx,
            start=start,
            end=end,
            lines=[],
            score=std / 100.0,  # Normalize std dev roughly
            keyword_hits={},
        )
        # Store metadata for reason generation
        seg.keyword_hits["__visual_intensity__"] = std
        segments.append(seg)
    return segments


def _extract_cover_frame(video_path: str, time_sec: float, out_path: str) -> Optional[str]:
    """Extract a single frame around ``time_sec`` as cover.jpg.

    Prefer using OpenCV to keep behaviour consistent with the rest of the PoC.
    """

    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("OpenCV not available, cannot extract cover frame: %s", exc)
        return None

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():  # pragma: no cover - IO issues
        logger.warning("Failed to open video for cover extraction: %s", video_path)
        return None

    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(time_sec)) * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            # Fallback to very first frame
            cap.set(cv2.CAP_PROP_POS_MSEC, 0.0)
            ret, frame = cap.read()
        if not ret or frame is None:
            logger.warning("Failed to grab frame for cover from %s", video_path)
            return None
        cv2.imwrite(out_path, frame)
        return out_path
    finally:
        cap.release()


def _synthesize_all_narrations(
    segments: Sequence[StorySegment],
    out_dir: str,
    title_prefix: str,
) -> tuple[List[str], List[str], List[float]]:
    """Generate narration text + TTS audio for each segment.

    Returns ``(texts, audio_paths, freeze_durations)``.
    """

    texts: List[str] = []
    audio_paths: List[str] = []
    freeze_durations: List[float] = []

    narr_dir = os.path.join(out_dir, "narrations")
    os.makedirs(narr_dir, exist_ok=True)

    for idx, seg in enumerate(segments):
        # Use existing narration_text if present (e.g., from loaded JSON plan)
        # otherwise generate a fallback draft narration.
        text = seg.narration_text if seg.narration_text else generate_narration(seg, title_prefix=title_prefix or None)
        texts.append(text)

        out_path = os.path.join(narr_dir, f"narration_{idx:02d}.wav")
        logger.info("Synthesizing narration for segment %d to %s", idx, out_path)
        audio_path = synthesize(text=text, out_path=out_path)
        audio_paths.append(audio_path)

        # Derive freeze duration from audio length (with a minimal padding to avoid gaps).
        dur = _get_wav_duration_sec(audio_path) or 0.5
        freeze = max(1.0, min(60.0, dur + 0.1))
        freeze_durations.append(freeze)

    return texts, audio_paths, freeze_durations


def _select_segments_for_target(
    segments: Sequence[StorySegment],
    freeze_durations: Sequence[float],
    target_duration_sec: float,
) -> List[int]:
    """Select a subset of segments to approach the target duration.

    Selection is score-first: segments are sorted by ``score`` descending, and
    then picked greedily until reaching ``target_duration_sec`` (allowed to
    exceed by up to 10%). The final order of selected indices is chronological
    by ``segment.start``.
    """

    n = len(segments)
    if n == 0:
        return []

    if len(freeze_durations) != n:  # pragma: no cover - defensive
        logger.warning(
            "freeze_durations length (%d) != segments length (%d); clipping.",
            len(freeze_durations),
            n,
        )
        freeze_durations = list(freeze_durations)[:n]

    highlight_durs: List[float] = []
    for i, seg in enumerate(segments):
        seg_dur = max(0.0, seg.duration)
        freeze = max(0.0, freeze_durations[i])
        highlight_durs.append(seg_dur + freeze)

    if target_duration_sec <= 0:
        # Use all segments, ordered by time.
        return sorted(range(n), key=lambda idx: segments[idx].start)

    scored_indices = sorted(range(n), key=lambda idx: segments[idx].score, reverse=True)
    selected: List[int] = []
    cumulative = 0.0
    target = float(target_duration_sec)
    allowed_max = target * 1.1

    for idx in scored_indices:
        seg_len = highlight_durs[idx]
        if seg_len <= 0:
            continue
        if cumulative + seg_len > allowed_max:
            continue
        selected.append(idx)
        cumulative += seg_len
        if cumulative >= target:
            break

    if not selected:
        # Always pick at least one segment as a fallback.
        selected = scored_indices[:1]

    selected.sort(key=lambda idx: segments[idx].start)
    logger.info(
        "Selected %d segments for target %.1fs (approx total %.1fs)",
        len(selected),
        target_duration_sec,
        sum(highlight_durs[idx] for idx in selected),
    )
    return selected


def _build_compose_segments(
    segments: Sequence[StorySegment],
    freeze_durations: Sequence[float],
    selected_indices: Sequence[int],
) -> List[Dict[str, Any]]:
    """Convert selected story segments into ffmpeg-friendly segment dicts."""

    compose_segments: List[Dict[str, Any]] = []

    for order, idx in enumerate(selected_indices):
        seg = segments[idx]
        freeze_duration = float(freeze_durations[idx]) if idx < len(freeze_durations) else 1.5

        start = float(seg.start)
        end = float(seg.end)
        if end <= start:
            end = start + max(freeze_duration + 0.5, 2.0)
        
        # Use the end of the segment as the anchor to avoid cutting off spoken words mid-sentence
        anchor = end

        pre_start = max(0.0, start)
        pre_duration = max(0.0, anchor - pre_start)
        post_start = anchor
        post_duration = 2.0 # 2 seconds of post-freeze playback

        compose_segments.append(
            {
                "trigger_index": order,
                "trigger_time": anchor,
                "pre": {"start": pre_start, "duration": pre_duration},
                "freeze": {"time": anchor, "duration": freeze_duration},
                "post": {"start": post_start, "duration": post_duration},
            }
        )

    return compose_segments


def _build_caption(
    title_prefix: str,
    hashtags: str,
    segments: Sequence[StorySegment],
    selected_indices: Sequence[int],
) -> tuple[str, str]:
    """Build XHS title and full caption text."""

    summary = "这一条视频浓缩了几处关键的权谋博弈场景。"
    if selected_indices:
        idx0 = selected_indices[0]
        seg0 = segments[idx0]
        if seg0.lines:
            summary = build_segment_summary([line.text for line in seg0.lines])

    title_prefix = title_prefix.strip()
    if title_prefix:
        title = f"{title_prefix}｜{summary}"
    else:
        title = summary

    hashtags_str = hashtags.strip()
    lines: List[str] = [title]
    if hashtags_str:
        lines.append(hashtags_str)
    lines.append(f"摘要：{summary}")
    caption = "\n".join(lines)
    return title, caption


def _get_selection_reason(seg: StorySegment) -> str:
    """Generate a human-readable reason for why this segment was selected."""
    reasons = []
    
    # 1. Keywords
    keywords = [k for k in seg.keyword_hits.keys() if not k.startswith("__")]
    if keywords:
        top_k = sorted(keywords, key=lambda k: seg.keyword_hits[k], reverse=True)[:3]
        reasons.append(f"台词中命中了关键信息: {', '.join(top_k)}")
        
    # 2. Visual Intensity
    if "__visual_intensity__" in seg.keyword_hits:
        intensity = seg.keyword_hits["__visual_intensity__"]
        reasons.append(f"画面视觉对比度/强度较高 (std dev: {intensity:.1f})，通常意味着画面剧烈变化或高潮")
        
    if not reasons:
        return "常规剧情片段"
        
    return " | ".join(reasons)


def _get_multimodal_tags(
    start: float,
    end: float,
    subtitles: List[SubtitleLine],
    video_path: str,
    audio_profile: Optional[Dict[str, Any]] = None,
    visual_scores: Optional[List[tuple[float, float]]] = None
) -> str:
    """Map physical features to discrete text tags for LLM."""
    # 1. Visual Vibe
    visual_tag = "静态/平稳"
    if visual_scores:
        # Find max std in this range
        relevant = [s[0] for s in visual_scores if start <= s[1] <= end]
        if relevant:
            max_v = max(relevant)
            if max_v > 60: visual_tag = "剧烈晃动/高能"
            elif max_v < 20: visual_tag = "静态/阴暗"

    # 2. Audio Vibe
    audio_tag = "正常/对话"
    if audio_profile:
        import numpy as np
        times = audio_profile["times"]
        rms = audio_profile["rms"]
        mask = (times >= start) & (times <= end)
        relevant_rms = rms[mask]
        if len(relevant_rms) > 0:
            max_a = np.max(relevant_rms)
            if max_a > 0.15: audio_tag = "能量爆发/嘈杂"
            elif max_a < 0.01: audio_tag = "死寂/压抑"

    # 3. Speech Pace & Density
    pace_tag = "正常/平稳"
    density_tag = "稀疏"
    
    # Check a slightly wider window (e.g. +/- 2 seconds) to determine local density
    window_start = max(0.0, start - 2.0)
    window_end = end + 2.0
    context_subs = [s for s in subtitles if s.start < window_end and s.end > window_start]
    
    if not context_subs:
        density_tag = "无台词"
    else:
        # Calculate how much time in the window is covered by speech
        speech_time = sum(min(s.end, window_end) - max(s.start, window_start) for s in context_subs)
        window_duration = window_end - window_start
        if window_duration > 0:
            density_ratio = speech_time / window_duration
            if density_ratio > 0.6:
                density_tag = "密集"
            elif density_ratio < 0.2:
                density_tag = "稀疏"
            else:
                density_tag = "适中"

    segment_subs = [s for s in subtitles if s.start >= start and s.end <= end]
    if segment_subs:
        text = "".join(s.text for s in segment_subs)
        duration = end - start
        if duration > 0:
            cps = len(text) / duration
            if cps > 6: pace_tag = "语速极快/紧张"
            elif cps < 2: pace_tag = "语速迟缓/沉重"

    return f"特征：【视觉：{visual_tag}】 | 【听觉：{audio_tag}】 | 【节奏：{pace_tag}】 | 【台词密度：{density_tag}】"


def _timecode_hhmmss_ms_to_seconds(tc: str) -> float:
    parts = tc.split(":")
    if len(parts) != 3:
        return 0.0
    h = int(parts[0])
    m = int(parts[1])
    s_ms = parts[2].split(",")
    s = int(s_ms[0])
    ms = int(s_ms[1]) if len(s_ms) > 1 else 0
    return float(h * 3600 + m * 60 + s) + float(ms) / 1000.0


def _parse_transcript_entries(transcript_path: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not os.path.exists(transcript_path):
        return entries
    pattern = re.compile(
        r'^\[(\d{2}:\d{2}:\d{2},\d{3}) - (\d{2}:\d{2}:\d{2},\d{3})\] 台词：“(.*)” \| (.*)$'
    )
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                m = pattern.match(line)
                if not m:
                    continue
                start_tc, end_tc, text, tags = m.group(1), m.group(2), m.group(3), m.group(4)
                entries.append(
                    {
                        "start": _timecode_hhmmss_ms_to_seconds(start_tc),
                        "end": _timecode_hhmmss_ms_to_seconds(end_tc),
                        "text": text,
                        "tags": tags,
                        "line": line,
                    }
                )
    except Exception:
        return entries
    return entries


def _build_transcript_window(
    entries: Sequence[Dict[str, Any]],
    start: float,
    end: float,
    window_sec: float,
    max_lines: int = 24,
) -> Dict[str, Any]:
    ws = max(0.0, float(start) - float(window_sec))
    we = float(end) + float(window_sec)
    picked: List[Dict[str, Any]] = []
    for e in entries:
        es = float(e.get("start", 0.0))
        ee = float(e.get("end", 0.0))
        if ee < ws:
            continue
        if es > we:
            break
        picked.append(e)
        if len(picked) >= int(max_lines):
            break

    quote_texts: List[str] = []
    anchors: List[str] = []
    for e in picked:
        t = str(e.get("text", "")).strip()
        if not t:
            continue
        quote_texts.append(t)
        compact = "".join(t.split())
        if len(compact) >= 6:
            a = compact[:6]
        else:
            a = compact
        if a and a not in anchors:
            anchors.append(a)
        if len(anchors) >= 6:
            break

    return {
        "window_sec": float(window_sec),
        "context_start": ws,
        "context_end": we,
        "context_lines": [e.get("line") for e in picked],
        "context_texts": quote_texts,
        "context_anchors": anchors,
    }


def _audit_llm_script_segments(
    segments_data: Sequence[Dict[str, Any]],
    transcript_path: str,
    out_dir: str,
) -> None:
    entries = _parse_transcript_entries(transcript_path)
    if not entries:
        return

    report: Dict[str, Any] = {
        "transcript_path": os.path.abspath(transcript_path),
        "issues": [],
    }

    for idx, s in enumerate(segments_data):
        try:
            start = float(s.get("start", 0.0))
            end = float(s.get("end", start))
        except Exception:
            continue

        narration_text = str(s.get("narration_text", "") or "")
        render_type = str(s.get("render_type", "") or "")
        if render_type == "pure_audio" or not narration_text.strip():
            continue

        win = _build_transcript_window(entries, start=start, end=end, window_sec=10.0, max_lines=60)
        anchors = win.get("context_anchors") or []
        anchors = [a for a in anchors if isinstance(a, str) and a]
        first_texts = win.get("context_texts") or []
        first_texts = [t for t in first_texts if isinstance(t, str) and t]

        hit = False
        for a in anchors[:4]:
            if a and a in narration_text:
                hit = True
                break

        if not hit and first_texts:
            report["issues"].append(
                {
                    "index": int(s.get("index", idx) or idx),
                    "start": start,
                    "end": end,
                    "problem": "narration_may_skip_segment_key_lines",
                    "hint": "解说与本段台词窗口的字面锚点重合度较低，容易跳过“新人物首次出场发言/关键铺垫”。建议在解说中先交代本段最早的关键台词再进入冲突点。",
                    "suggested_key_lines": first_texts[:3],
                    "suggested_anchors": anchors[:6],
                }
            )

    if report["issues"]:
        try:
            out_path = os.path.join(out_dir, "llm_script_audit.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.warning("LLM script audit found %d issue(s). Saved to %s", len(report["issues"]), out_path)
        except Exception:
            pass


def main(argv: Any = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    logger = logging.getLogger("xhs_autocut")

    video_path = args.video
    out_dir = args.out
    target_duration = float(args.target_duration)
    portrait = args.portrait
    title_prefix = args.title_prefix or ""
    hashtags = args.hashtags or ""
    gap_threshold = float(args.gap_threshold)
    skip_start = float(args.skip_start)
    skip_end = float(args.skip_end)
    render_now = bool(args.render)
    from_plan = args.from_plan
    freeze_effect = args.freeze_effect

    if not os.path.exists(video_path):
        logger.error("Input video does not exist: %s", video_path)
        raise SystemExit(1)

    os.makedirs(out_dir, exist_ok=True)

    if from_plan:


        # ===========================
        # 【LLM 文案驱动渲染模式】
        # ===========================
        #
        # 这是本仓库"LLM 文案 -> 成片"的主入口：
        # 1) LLM 输出 JSON 计划（通常是 outputs/.../video_script_expert_output.json）
        #    包含每段时间戳 + render_type + narration_text（+ 可选 freeze_duration）
        # 2) 本分支读取该 JSON，为每段合成 TTS 音频（pure_audio 除外），
        #    然后将计划翻译成 ffmpeg 渲染器能理解的 "compose_segments" 结构
        # 3) 最后调用 compose_segments_xhs(...)，逐段渲染为 mp4 并拼接成
        #    outputs/.../compose.mp4
        #
        # 链路中的关键文件：
        # - LLM 计划消费/编排：src/cli/xhs_autocut.py（本块）
        # - 片段渲染（裁剪/定格/慢放/叠字幕/混音）：src/render/ffmpeg_compose.py
        # - TTS 合成：src/tts/tts_edge.py
        if not os.path.exists(from_plan):
            logger.error("Plan file not found: %s", from_plan)
            raise SystemExit(1)
        
        with open(from_plan, 'r', encoding='utf-8') as f:
            plan_data = json.load(f)

            print('plan_data', plan_data)

        
        logger.info("Rendering from plan: %s", from_plan)
        plan_video = plan_data.get("source_video")

        print('plan_video',plan_video)
        if plan_video and os.path.exists(str(plan_video)):
            if os.path.abspath(str(plan_video)) != os.path.abspath(video_path):
                logger.warning(
                    "Plan source_video differs from --video; using plan source_video: %s",
                    plan_video,
                )
            video_path = str(plan_video)


        try:
            transcript_path = plan_data.get("full_transcript_path") or os.path.join(out_dir, "transcript_for_llm.txt")
            if transcript_path and os.path.exists(transcript_path):
                _audit_llm_script_segments(plan_data.get("segments", []), transcript_path, out_dir)
        except Exception:
            pass
        
        # 1) 从计划中重建片段数据
        # "segments_data" 是 LLM 输出（或后处理过的计划），包含：
        # - start/end: 源视频中的绝对时间戳
        # - anchor_time: [start,end] 区间内的关键时刻（定格聚焦或解析点）
        # - render_type: freeze / overdub / slow_mo / pure_audio
        # - narration_text: 该片段的解说文案（pure_audio 时为空）
        #
        # 保持此列表不变，构建并行的音频/文本数组，按索引对齐。
        segments_data = plan_data.get("segments", [])
        narration_texts = [s["narration_text"] for s in segments_data]
        
        # 2) 合成旁白音频
        # 对每个片段：
        # - 如果 render_type 是 pure_audio 或 narration_text 为空 -> 不生成 TTS
        # - 否则在 outputs/.../narrations/narration_XX.wav 合成 wav 文件
        #
        # 注意：freeze_durations 主要用于 render_type=freeze（定格持续多久）
        narration_audios: List[Optional[str]] = []
        freeze_durations: List[float] = []
        narr_dir = os.path.join(out_dir, "narrations")
        os.makedirs(narr_dir, exist_ok=True)
        
        for idx, text in enumerate(narration_texts):
            rt = str(segments_data[idx].get("render_type") or "freeze").strip().lower()
            if rt == "pure_audio" or not str(text or "").strip():
                narration_audios.append(None)
                freeze_durations.append(0.0)
                continue

            out_path = os.path.join(narr_dir, f"narration_{idx:02d}.wav")
            audio_path = synthesize(text=text, out_path=out_path)
            narration_audios.append(audio_path)
            dur = _get_wav_duration_sec(audio_path) or 0.5
            freeze = max(1.0, min(60.0, dur + 0.1))
            freeze_durations.append(freeze)
            logger.info("Narration %02d: audio=%s, dur=%.3fs -> freeze=%.3fs", idx, audio_path, dur, freeze)
            
        # 3) 构建合成片段
        # 将 LLM 计划翻译成渲染器友好的字典格式
        #
        # 支持两种格式：
        # - 非定格样式（overdub / slow_mo / pure_audio）：
        #   渲染器期望：{start,end,render_type,(speed)}
        # - 定格样式：
        #   渲染器期望：{pre:{start,duration}, freeze:{time,duration}, post:{start,duration}}
        #
        # 重要：start/end/anchor_time 保持为*源视频*的绝对时间
        compose_segments = []
        for idx, s in enumerate(segments_data):
            start = float(s.get("start", 0.0))
            end = float(s.get("end", start + 5.0))
            
            anchor = float(s.get("anchor_time", end))
            if anchor < start:
                anchor = start
            if anchor > end:
                anchor = end
            
            rt = str(s.get("render_type") or "freeze").strip().lower()
            if rt in ("overdub", "pure_audio", "slow_mo"):
                seg_dict: Dict[str, Any] = {
                    "trigger_index": idx,
                    "trigger_time": anchor,
                    "start": start,
                    "end": end,
                    "render_type": rt,
                }
                if rt == "slow_mo":
                    seg_dict["speed"] = float(s.get("speed", 0.5))
                compose_segments.append(
                    seg_dict
                )
                continue

            pre = {"start": start, "duration": max(0.0, anchor - start)}
            post = {"start": anchor, "duration": max(0.0, end - anchor)}
            freeze_dur = float(
                s.get("freeze_duration", freeze_durations[idx] if idx < len(freeze_durations) else 1.5)
            )

            compose_segments.append(
                {
                    "trigger_index": idx,
                    "trigger_time": anchor,
                    "start": start,
                    "end": end,
                    "render_type": "freeze",
                    "pre": pre,
                    "freeze": {"time": anchor, "duration": freeze_dur},
                    "post": post,
                }
            )
            
        # 4) 渲染
        # render_spec 控制 9:16 缩放/裁剪行为
        # compose_segments_xhs 是 ffmpeg "执行器"：
        # - 将每个片段渲染为临时 mp4 文件
        # - 叠加与旁白音频同步的字幕
        # - 混音：压低背景音（ducking）并混入旁白音频
        # - 将所有片段 mp4 拼接成单个 compose.mp4
        render_spec = plan_data.get("render", {
            "aspect": "9:16",
            "resolution": portrait,
            "mode": "crop_or_pad"
        })
        
        logger.info("Composing highlight video from plan...")

        output_video = compose_segments_xhs(
            video_path=video_path,
            segments=compose_segments,
            narration_audios=narration_audios,
            out_dir=out_dir,
            render=render_spec,
            output_basename="compose.mp4",
            narration_texts=narration_texts,
            freeze_effect=freeze_effect,
        )
        logger.info("Video generated at %s", output_video)
        return

    # 1) 摄入：优先使用字幕，回退到视觉锚点
    subtitles = []

    # 尝试加载已有字幕
    subtitle_path = args.subtitle or (os.path.splitext(video_path)[0] + ".srt")
    if os.path.exists(subtitle_path):
        subtitles = load_subtitles_for_video(subtitle_path)
    else:
        try:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            cached_srt = os.path.join(out_dir, "transcription", f"{base_name}.srt")
            if os.path.exists(cached_srt):
                subtitles = load_subtitles_for_video(cached_srt)
        except Exception:
            pass

    # 如果未找到字幕，尝试使用 faster-whisper 转录（借鉴自 short_video 项目）
    if not subtitles:
        logger.info("Subtitle file not found, attempting to transcribe video using faster-whisper...")
        try:
            # We run the transcription script as a subprocess to keep it clean
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Path to scripts/transcribe_video.py
            transcribe_script = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "scripts", "transcribe_video.py")
            
            if os.path.exists(transcribe_script):
                import subprocess
                base_name = os.path.splitext(os.path.basename(video_path))[0]
                # Output to a subdirectory in out_dir
                transcribe_out = os.path.join(out_dir, "transcription")
                os.makedirs(transcribe_out, exist_ok=True)
                
                subprocess.run([
                    "python3", transcribe_script,
                    "--input", video_path,
                    "--out-dir", transcribe_out,
                    "--model", "small",
                    "--language", "zh"
                ], check=True)
                
                new_srt = os.path.join(transcribe_out, f"{base_name}.srt")
                if os.path.exists(new_srt):
                    subtitles = load_subtitles_for_video(new_srt)
                    logger.info("Transcription completed successfully.")
            else:
                logger.warning("Transcription script not found at: %s", transcribe_script)
        except Exception as e:
            logger.warning("Transcription failed: %s. Falling back to visual anchors.", e)

    keywords = _load_keywords_for_scoring()

    if subtitles:
        logger.info("Loaded %d subtitle lines, building story segments...", len(subtitles))
        segments = segment_subtitles(
            subtitles=subtitles,
            gap_threshold=gap_threshold,
            keywords=keywords,
        )
    else:
        logger.info("No subtitles found, falling back to visual-intensity anchors.")
        anchors = _probe_high_intensity_anchors(video_path)
        segments = _build_fallback_segments_from_anchors(anchors)

    if not segments:
        logger.error("No segments could be constructed; aborting XHS pipeline.")
        raise SystemExit(1)

    # 1.5) Filter segments based on skip times.
    video_dur = _get_video_duration(video_path)
    valid_start = args.skip_start
    valid_end = video_dur - args.skip_end if video_dur > 0 else float("inf")

    filtered_segments = []
    for seg in segments:
        # If the segment's anchor (midpoint) is within the skip range, skip it.
        mid = (seg.start + seg.end) / 2.0
        if mid < valid_start or mid > valid_end:
            continue
        filtered_segments.append(seg)

    if not filtered_segments:
        logger.warning(
            "All %d segments were filtered out by skip-start (%.1fs) or skip-end (%.1fs). "
            "Using all segments instead.",
            len(segments), args.skip_start, args.skip_end
        )
    else:
        segments = filtered_segments
        logger.info(
            "Filtered to %d segments after skipping start (%.1fs) and end (%.1fs).",
            len(segments), args.skip_start, args.skip_end
        )

    # 1.6) Write full transcript for LLM
    from ..ingestion.ingestor import get_audio_rms_profile, read_video_frames
    import cv2
    import numpy as np
    from ..vision.face_emotion import FaceIdentityAssigner, extract_face_vision_at_time, extract_face_vision_on_frame
    
    logger.info("Extracting multimodal features for transcript...")
    audio_profile = get_audio_rms_profile(video_path)
    visual_scores = []
    for ts, frame in read_video_frames(video_path, frame_stride=30): # Faster sampling
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        visual_scores.append((float(np.std(gray)), ts))

    transcript_path = os.path.join(out_dir, "transcript_for_llm.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        fps = 30.0
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps_val = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                if fps_val > 0.1:
                    fps = fps_val
            cap.release()
        except Exception:
            pass

        stride_3s = max(1, int(round(fps * 3.0)))
        assigner = FaceIdentityAssigner()
        last_sig = None
        f.write("# Vision Events (3s sampling, only on change)\n")
        try:
            for ts, frame in read_video_frames(video_path, frame_stride=stride_3s):
                if ts < valid_start:
                    continue
                if ts > valid_end:
                    break
                vision = extract_face_vision_on_frame(frame, assigner)
                face_count = int(vision.get("face_count", 0) or 0)
                people = vision.get("people_in_shot") or []
                if not isinstance(people, list):
                    people = []
                people = [p for p in people if isinstance(p, str) and p]
                sig = (face_count, tuple(people))
                if sig != last_sig:
                    start_ts = f"{ts // 3600:02.0f}:{(ts % 3600) // 60:02.0f}:{ts % 60:06.3f}".replace('.', ',')
                    f.write(f"[{start_ts}] 人物：face_count={face_count} | people_in_shot={people}\n")
                    last_sig = sig
        except Exception:
            pass
        f.write("\n")
        if subtitles:
            for sub in subtitles:
                start_ts = f"{sub.start // 3600:02.0f}:{(sub.start % 3600) // 60:02.0f}:{sub.start % 60:06.3f}".replace('.', ',')
                end_ts = f"{sub.end // 3600:02.0f}:{(sub.end % 3600) // 60:02.0f}:{sub.end % 60:06.3f}".replace('.', ',')
                tags = _get_multimodal_tags(sub.start, sub.end, subtitles, video_path, audio_profile, visual_scores)
                f.write(f"[{start_ts} - {end_ts}] 台词：“{sub.text}” | {tags}\n")
        else:
            f.write("# No subtitle file provided. Using visual/audio anchors.\n\n")
            # (Fallback logic already handles segments generation below)
                
    logger.info("Multimodal transcript written to %s", transcript_path)

    # Always generate a plan for LLM feeding first
    transcript_entries = _parse_transcript_entries(transcript_path)
    plan_segments = []
    face_assigner = FaceIdentityAssigner()
    face_cap = cv2.VideoCapture(video_path)
    for i, seg in enumerate(segments):
        mid = (float(seg.start) + float(seg.end)) / 2.0
        if mid < valid_start or mid > valid_end:
            vision = {"faces": [], "face_count": 0, "people_in_shot": []}
        else:
            vision = (
                extract_face_vision_at_time(face_cap, mid, face_assigner)
                if face_cap.isOpened()
                else {"faces": [], "face_count": 0, "people_in_shot": []}
            )
        transcript_window = _build_transcript_window(
            transcript_entries,
            start=float(seg.start),
            end=float(seg.end),
            window_sec=10.0,
            max_lines=24,
        )
        plan_segments.append({
            "index": i,
            "start": float(seg.start),
            "end": float(seg.end),
            "score": float(seg.score),
            "selection_reason": _get_selection_reason(seg),
            "subtitle_texts": [line.text for line in seg.lines],
            "narration_text": generate_narration(seg, title_prefix=title_prefix or None),
            "vision": vision,
            "transcript_window": transcript_window,
        })
    try:
        face_cap.release()
    except Exception:
        pass
    
    light_plan = {
        "source_video": os.path.abspath(video_path),
        "segments": plan_segments,
        "full_transcript_path": os.path.abspath(transcript_path)
    }
    
    plan_path = os.path.join(out_dir, "compose_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(light_plan, f, ensure_ascii=False, indent=2)
        
    logger.info("Segmentation plan for LLM written to %s", plan_path)

    if not render_now:
        logger.info("Screening mode completed (no --render flag).")
        logger.info("Please use full_transcript.txt and compose_plan.json for LLM feeding.")
        return

    # 2) Narration: per-segment text + TTS.
    narration_texts, narration_audios, freeze_durations = _synthesize_all_narrations(
        segments, out_dir=out_dir, title_prefix=title_prefix
    )

    # 3) Select segments w.r.t. target duration.
    selected_indices = _select_segments_for_target(
        segments, freeze_durations, target_duration_sec=target_duration
    )

    selected_segments = [segments[i] for i in selected_indices]
    selected_audios = [narration_audios[i] for i in selected_indices]
    selected_freezes = [freeze_durations[i] for i in selected_indices]
    selected_narrations = [narration_texts[i] for i in selected_indices]

    # 4) Build compose segments for ffmpeg and plan.
    compose_segments = _build_compose_segments(
        selected_segments,
        selected_freezes,
        list(range(len(selected_segments))),  # local indices
    )
    for i, seg in enumerate(selected_segments):
        try:
            rt = str(getattr(seg, "render_type", "freeze") or "freeze").strip().lower()
        except Exception:
            rt = "freeze"
        if rt in ("overdub", "pure_audio", "slow_mo"):
            compose_segments[i]["render_type"] = rt
            compose_segments[i]["start"] = float(seg.start)
            compose_segments[i]["end"] = float(seg.end)
            if rt == "slow_mo":
                try:
                    compose_segments[i]["speed"] = float(getattr(seg, "speed", 0.5) or 0.5)
                except Exception:
                    compose_segments[i]["speed"] = 0.5
        else:
            compose_segments[i]["render_type"] = "freeze"

    render_spec: Dict[str, Any] = {
        "aspect": "9:16",
        "resolution": str(portrait),
        "mode": "crop_or_pad",
    }

    ffmpeg_available = _has_ffmpeg()
    output_video: Optional[str] = None
    if ffmpeg_available:
        logger.info("ffmpeg detected on PATH, composing highlight video...")
        output_video = compose_segments_xhs(
            video_path=video_path,
            segments=compose_segments,
            narration_audios=selected_audios,
            out_dir=out_dir,
            render=render_spec,
            output_basename="compose.mp4",
            narration_texts=selected_narrations,
            freeze_effect=freeze_effect,
        )
        if output_video:
            logger.info("Compose video generated at %s", output_video)
        else:
            logger.warning("ffmpeg is available but compose.mp4 could not be generated.")
    else:
        logger.warning(
            "ffmpeg not available; only compose_plan.json and audio assets will be generated."
        )

    # 5) Cover frame.
    first_seg = selected_segments[0]
    cover_time = (first_seg.start + first_seg.end) / 2.0
    cover_path = os.path.join(out_dir, "cover.jpg")
    cover_frame_path = _extract_cover_frame(video_path, cover_time, cover_path)

    # 6) Caption.
    title, caption_text = _build_caption(title_prefix, hashtags, segments, selected_indices)

    caption_path = os.path.join(out_dir, "caption.txt")
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(caption_text)

    # 7) Compose plan for XHS.
    plan_segments: List[Dict[str, Any]] = []
    for local_idx, idx in enumerate(selected_indices):
        seg = segments[idx]
        audio_path = narration_audios[idx]
        freeze_dur = selected_freezes[local_idx]
        comp_seg = compose_segments[local_idx]
        text = narration_texts[idx]
        subtitle_texts = [line.text for line in seg.lines]
        plan_segments.append(
            {
                "index": local_idx,
                "start": float(seg.start),
                "end": float(seg.end),
                "render_type": "freeze",
                "anchor_time": float(comp_seg["freeze"]["time"]),
                "score": float(seg.score),
                "subtitle_texts": subtitle_texts,
                "narration_text": text,
                "narration_audio": os.path.abspath(audio_path),
                "freeze_duration": float(freeze_dur),
                "pre": comp_seg["pre"],
                "freeze": comp_seg["freeze"],
                "post": comp_seg["post"],
            }
        )

    plan: Dict[str, Any] = {
        "source_video": os.path.abspath(video_path),
        "ffmpeg_available": ffmpeg_available,
        "output_video": os.path.abspath(output_video) if output_video else None,
        "render": render_spec,
        "target_duration_sec": float(target_duration),
        "segments": plan_segments,
        "cover": {
            "time_sec": float(cover_time),
            "frame_path": os.path.abspath(cover_frame_path) if cover_frame_path else None,
        },
        "title": title,
        "hashtags": hashtags,
        "caption": caption_text,
    }

    plan_path = os.path.join(out_dir, "compose_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    logger.info("Compose plan written to %s", plan_path)
    logger.info("Caption written to %s", caption_path)
    if cover_frame_path:
        logger.info("Cover frame written to %s", cover_frame_path)


if __name__ == "__main__":  # pragma: no cover
    main()
