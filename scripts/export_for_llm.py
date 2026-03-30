import argparse
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import cv2  # type: ignore

    _HAS_CV2 = True
except Exception:
    cv2 = None  # type: ignore
    _HAS_CV2 = False

try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except Exception:
    np = None  # type: ignore
    _HAS_NUMPY = False

try:
    import jieba  # type: ignore
    import jieba.posseg as pseg  # type: ignore

    _HAS_JIEBA = True
except Exception:
    jieba = None  # type: ignore
    pseg = None  # type: ignore
    _HAS_JIEBA = False

try:
    from src.ingestion.ingestor import get_audio_rms_profile  # type: ignore

    _HAS_AUDIO_PROFILE = True
except Exception:
    get_audio_rms_profile = None  # type: ignore
    _HAS_AUDIO_PROFILE = False


_TS_RE = r"\d\d:\d\d:\d\d[,.]\d\d\d"
_RE_VISION = re.compile(
    rf"^\[(?P<ts>{_TS_RE})\]\s+人物：face_count=(?P<face_count>\d+)\s+\|\s+people_in_shot=(?P<people>\[.*\])$"
)
_RE_DIALOGUE_MM = re.compile(
    rf'^\[(?P<start>{_TS_RE})\s*-\s*(?P<end>{_TS_RE})\]\s+台词：["“](?P<text>.*?)["”]\s*\|\s*(?P<tags>.*)$'
)
_RE_DIALOGUE_PLAIN = re.compile(
    rf"^\[(?P<start>{_TS_RE})\s*-\s*(?P<end>{_TS_RE})\]\s*(?P<text>.*)$"
)
_RE_TAG = {
    "vision": re.compile(r"【视觉：([^】]+)】"),
    "audio": re.compile(r"【听觉：([^】]+)】"),
    "density": re.compile(r"【台词密度：([^】]+)】"),
}
_RE_PXX = re.compile(r"\bp\d{2}\b")
_RE_SPEAKER = re.compile(r"^\s*([^:：]{1,8})[:：]\s*(.+)$")
_RE_TOKEN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}")

_DEFAULT_GAP_THRESHOLD = 2.5
_DEFAULT_MAX_SEG_SECONDS = 180.0
_DEFAULT_MAX_SEG_LINES = 80

_DEFAULT_STOPWORDS = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "就",
    "都",
    "而",
    "也",
    "还",
    "很",
    "又",
    "啊",
    "呀",
    "吗",
    "呢",
    "吧",
    "这个",
    "那个",
    "我们",
    "你们",
    "他们",
    "她们",
    "自己",
    "一个",
    "没有",
    "不是",
}


def _ts_to_sec(ts: str) -> float:
    h, m, s_ms = ts.split(":")
    if "," in s_ms:
        s, ms = s_ms.split(",", 1)
    else:
        s, ms = s_ms.split(".", 1)
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _sec_to_hms(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _sec_to_ts_mmm(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000.0))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


@dataclass
class VisionEvent:
    t: float
    face_count: int
    people: List[str]
    raw: str


@dataclass
class DialogueLine:
    start: float
    end: float
    text: str
    tags: str
    raw: str


@dataclass
class TranscriptLine:
    t0: float
    t1: float
    kind: str
    raw: str


@dataclass
class Segment:
    index: int
    start: float
    end: float
    lines: List[DialogueLine]
    keywords: List[str]
    score: float
    vision_tag: str
    audio_tag: str
    density_tag: str
    people_in_shot: List[str]


def _default_keywords() -> List[Tuple[str, float]]:
    return [
        ("圣旨", 1.0),
        ("兵权", 1.0),
        ("夺嫡", 1.0),
        ("太子", 0.9),
        ("年羹尧", 1.0),
        ("四阿哥", 0.9),
        ("八阿哥", 0.9),
        ("黄河", 0.8),
        ("决堤", 1.0),
        ("抄家", 0.9),
        ("逼宫", 1.0),
        ("赐死", 1.0),
        ("造反", 1.0),
    ]


def _extract_tag(tag_type: str, tags: str) -> Optional[str]:
    pat = _RE_TAG.get(tag_type)
    if not pat:
        return None
    m = pat.search(tags)
    if not m:
        return None
    return str(m.group(1)).strip()


def _mode(values: Sequence[str]) -> str:
    vals = [v for v in values if v]
    if not vals:
        return ""
    c = Counter(vals)
    return c.most_common(1)[0][0]


def parse_transcript(transcript_path: str) -> Tuple[List[TranscriptLine], List[VisionEvent], List[DialogueLine]]:
    all_lines: List[TranscriptLine] = []
    visions: List[VisionEvent] = []
    dialogues: List[DialogueLine] = []
    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            m1 = _RE_VISION.match(line.strip())
            if m1:
                t = _ts_to_sec(m1.group("ts"))
                face_count = int(m1.group("face_count"))
                ppl = _RE_PXX.findall(m1.group("people"))
                visions.append(VisionEvent(t=t, face_count=face_count, people=sorted(set(ppl)), raw=line))
                all_lines.append(TranscriptLine(t0=t, t1=t, kind="vision", raw=line))
                continue
            m2 = _RE_DIALOGUE_MM.match(line.strip())
            if m2:
                t0 = _ts_to_sec(m2.group("start"))
                t1 = _ts_to_sec(m2.group("end"))
                txt = str(m2.group("text")).strip()
                tags = str(m2.group("tags") or "").strip()
                dlg = DialogueLine(start=t0, end=t1, text=txt, tags=tags, raw=line)
                dialogues.append(dlg)
                all_lines.append(TranscriptLine(t0=t0, t1=t1, kind="dialogue", raw=line))
                continue
            m3 = _RE_DIALOGUE_PLAIN.match(line.strip())
            if m3:
                t0 = _ts_to_sec(m3.group("start"))
                t1 = _ts_to_sec(m3.group("end"))
                txt = str(m3.group("text") or "").strip()
                dlg = DialogueLine(start=t0, end=t1, text=txt, tags="", raw=line)
                dialogues.append(dlg)
                all_lines.append(TranscriptLine(t0=t0, t1=t1, kind="dialogue", raw=line))
                continue
    dialogues.sort(key=lambda x: (x.start, x.end))
    visions.sort(key=lambda x: x.t)
    all_lines.sort(key=lambda x: (x.t0, x.t1))
    return all_lines, visions, dialogues


def segment_dialogues(dialogues: Sequence[DialogueLine], gap_threshold: float) -> List[List[DialogueLine]]:
    groups: List[List[DialogueLine]] = []
    buf: List[DialogueLine] = []
    prev_end: Optional[float] = None
    for d in dialogues:
        if prev_end is None:
            buf = [d]
            prev_end = d.end
            continue
        gap = float(d.start) - float(prev_end)
        if gap > float(gap_threshold):
            if len(buf) >= 2:
                groups.append(buf)
            buf = [d]
        else:
            buf.append(d)
        prev_end = d.end
    if len(buf) >= 2:
        groups.append(buf)
    return groups


def split_dialogue_group(
    group: Sequence[DialogueLine],
    max_seconds: float = _DEFAULT_MAX_SEG_SECONDS,
    max_lines: int = _DEFAULT_MAX_SEG_LINES,
) -> List[List[DialogueLine]]:
    items = list(group)
    if not items:
        return []
    out: List[List[DialogueLine]] = []
    i = 0
    n = len(items)
    max_lines = max(1, int(max_lines))
    max_seconds = max(1.0, float(max_seconds))
    while i < n:
        start = float(items[i].start)
        best_j = i
        j = i
        while j < n:
            end = float(items[j].end)
            dur = end - start
            line_count = j - i + 1
            if dur <= max_seconds and line_count <= max_lines:
                best_j = j
                j += 1
                continue
            break
        if best_j < i:
            best_j = i
        out.append(items[i : best_j + 1])
        i = best_j + 1
    return out


def split_dialogue_groups(
    groups: Sequence[Sequence[DialogueLine]],
    max_seconds: float = _DEFAULT_MAX_SEG_SECONDS,
    max_lines: int = _DEFAULT_MAX_SEG_LINES,
) -> List[List[DialogueLine]]:
    out: List[List[DialogueLine]] = []
    for g in groups:
        out.extend(split_dialogue_group(g, max_seconds=max_seconds, max_lines=max_lines))
    return out


def build_segments(
    dialogue_groups: Sequence[Sequence[DialogueLine]],
    visions: Sequence[VisionEvent],
    keywords: Sequence[Tuple[str, float]],
    people_pad_sec: float = 5.0,
) -> List[Segment]:
    segments: List[Segment] = []
    for i, grp in enumerate(dialogue_groups):
        start = float(min(d.start for d in grp))
        end = float(max(d.end for d in grp))
        text_all = "".join(d.text for d in grp)
        hit = []
        score = 0.0
        for kw, w in keywords:
            if kw and kw in text_all:
                hit.append(kw)
                score += float(w)
        vision_vals = []
        audio_vals = []
        density_vals = []
        for d in grp:
            vt = _extract_tag("vision", d.tags)
            at = _extract_tag("audio", d.tags)
            dt = _extract_tag("density", d.tags)
            if vt:
                vision_vals.append(vt)
            if at:
                audio_vals.append(at)
            if dt:
                density_vals.append(dt)
        ppl = set()
        t0 = start - float(people_pad_sec)
        t1 = end + float(people_pad_sec)
        for ve in visions:
            if ve.t < t0:
                continue
            if ve.t > t1:
                break
            for p in ve.people:
                ppl.add(p)
        segments.append(
            Segment(
                index=i,
                start=start,
                end=end,
                lines=list(grp),
                keywords=sorted(hit),
                score=float(score),
                vision_tag=_mode(vision_vals),
                audio_tag=_mode(audio_vals),
                density_tag=_mode(density_vals),
                people_in_shot=sorted(ppl),
            )
        )
    return segments


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _count_chars(text: str) -> int:
    if not text:
        return 0
    s = re.sub(r"\s+", "", text)
    return len(s)


def _density_label(rate: float) -> str:
    if rate < 2.0:
        return "稀疏"
    if rate > 4.0:
        return "密集"
    return "正常"


def _extract_speakers(lines: Sequence[DialogueLine]) -> List[str]:
    speakers: List[str] = []
    seen = set()
    for d in lines:
        txt = (d.text or "").strip()
        m = _RE_SPEAKER.match(txt)
        if not m:
            continue
        name = str(m.group(1)).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        speakers.append(name)
    return speakers


def _load_stopwords(path: str) -> set[str]:
    out = set(_DEFAULT_STOPWORDS)
    if not path:
        return out
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                w = raw.strip()
                if w:
                    out.add(w)
    except Exception:
        pass
    return out


def _load_people_names(path: str) -> Dict[str, str]:
    if not path:
        return {}
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not k:
            continue
        if v is None:
            continue
        if isinstance(v, str):
            name = v.strip()
        else:
            name = str(v).strip()
        if name:
            out[k] = name
    return out


def _map_people_ids(people_ids: Sequence[str], names_map: Dict[str, str]) -> List[str]:
    if not people_ids:
        return []
    out: List[str] = []
    seen = set()
    for pid in people_ids:
        key = str(pid)
        name = names_map.get(key)
        val = name if name else key
        if val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def _top_terms(text: str, top_k: int, stopwords: set[str]) -> List[str]:
    top_k = max(1, int(top_k))
    if not text:
        return []
    counter: Counter[str] = Counter()
    if _HAS_JIEBA and pseg is not None:
        try:
            for w in pseg.cut(text):
                word = str(getattr(w, "word", "") or "").strip()
                flag = str(getattr(w, "flag", "") or "").strip()
                if not word or word in stopwords:
                    continue
                if len(word) < 2:
                    continue
                if not (flag.startswith("n") or flag.startswith("v")):
                    continue
                counter[word] += 1
        except Exception:
            counter = Counter()
    if not counter:
        for m in _RE_TOKEN.finditer(text):
            tok = m.group(0)
            if tok in stopwords:
                continue
            counter[tok] += 1
    return [w for w, _ in counter.most_common(top_k)]


def _compute_frame_diff_mean(video_path: str, start: float, end: float, sample_sec: float = 1.0) -> Optional[float]:
    if not _HAS_CV2 or cv2 is None:
        return None
    if not video_path or not os.path.exists(video_path):
        return None
    dur = max(0.0, float(end) - float(start))
    if dur <= 0.05:
        return 0.0
    sample_sec = float(sample_sec)
    if dur <= 20.0:
        sample_sec = min(sample_sec, 0.5)
    elif dur >= 120.0:
        sample_sec = max(sample_sec, 1.5)
    sample_sec = max(0.2, min(2.0, sample_sec))
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    diffs: List[float] = []
    prev = None
    t = float(start)
    try:
        while t <= float(end) + 1e-6:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                t += sample_sec
                continue
            if prev is not None:
                try:
                    diff = cv2.absdiff(prev, frame)
                    diffs.append(float(diff.mean()) / 255.0)
                except Exception:
                    pass
            prev = frame
            t += sample_sec
    finally:
        try:
            cap.release()
        except Exception:
            pass
    if not diffs:
        return 0.0
    return float(sum(diffs) / float(len(diffs)))


def _db_std_from_profile(profile: Optional[Dict[str, Any]], start: float, end: float) -> Tuple[Optional[float], Optional[float]]:
    if not profile or not _HAS_NUMPY or np is None:
        return None, None
    try:
        times = profile.get("times")
        rms = profile.get("rms")
        if times is None or rms is None:
            return None, None
        t0 = float(start)
        t1 = float(end)
        mask = (times >= t0) & (times <= t1)  # type: ignore[operator]
        seg = rms[mask]  # type: ignore[index]
        if seg is None or len(seg) == 0:
            return 0.0, 0.0
        seg = np.asarray(seg)
        seg_max = float(seg.max())
        eps = 1e-8
        db = 20.0 * np.log10(np.maximum(seg, eps))
        return float(np.std(db)), float(seg_max)
    except Exception:
        return None, None


def write_synopsis(
    segments: Sequence[Segment],
    transcript_path: str,
    out_path: str,
    max_lines: int = 50,
    total_duration: float = 0.0,
    video_path: Optional[str] = None,
    keyword_total: int = 0,
    audio_profile: Optional[Dict[str, Any]] = None,
    stopwords_path: str = "",
    people_names: Optional[Dict[str, str]] = None,
    gap_threshold: float = _DEFAULT_GAP_THRESHOLD,
    max_seg_seconds: float = _DEFAULT_MAX_SEG_SECONDS,
    max_seg_lines: int = _DEFAULT_MAX_SEG_LINES,
) -> None:
    lines: List[str] = []
    base = os.path.basename(transcript_path)
    last_end = 0.0
    for s in segments:
        last_end = max(last_end, s.end)
    if not segments:
        last_end = float(total_duration or 0.0)
    lines.append("# 全片字段概览（code-only）")
    lines.append(f"transcript={base}")
    lines.append(f"full_duration={_sec_to_hms(last_end)}")
    lines.append(f"segment_count={len(segments)}")
    lines.append(f"gap_threshold={float(gap_threshold):.3f}")
    lines.append(f"max_seg_seconds={float(max_seg_seconds):.1f}")
    lines.append(f"max_seg_lines={int(max_seg_lines)}")
    lines.append("")
    if len(segments) > max_lines:
        ordered = sorted(segments, key=lambda x: (x.score, x.end - x.start), reverse=True)[:max_lines]
        ordered = sorted(ordered, key=lambda x: x.start)
    else:
        ordered = list(segments)
    stopwords = _load_stopwords(stopwords_path)
    people_names = people_names or {}
    people_freq: Counter[str] = Counter()
    high_score: List[Tuple[float, Segment]] = []
    audio_peaks: List[Tuple[float, Segment]] = []
    for s in ordered:
        duration = float(s.end) - float(s.start)
        line_count = len(s.lines)
        first_line = (s.lines[0].text if s.lines else "").strip()
        last_line = (s.lines[-1].text if s.lines else "").strip()
        text_all = "\n".join([d.text for d in s.lines if d.text])
        char_count = _count_chars(text_all)
        speech_rate = (float(char_count) / duration) if duration > 1e-6 else 0.0
        density_label = _density_label(speech_rate)
        hit_count = len(s.keywords)
        denom = int(keyword_total) if int(keyword_total) > 0 else 1
        score = float(hit_count) / float(denom)
        speakers = _extract_speakers(s.lines)
        people_ids = speakers if speakers else list(s.people_in_shot or [])
        people_names_list = _map_people_ids(people_ids, people_names) if people_names else list(people_ids)
        for p in people_ids:
            people_freq[p] += 1
        high_score.append((score, s))
        top_terms = _top_terms(text_all, top_k=6, stopwords=stopwords)
        frame_diff_mean = _compute_frame_diff_mean(video_path or "", s.start, s.end) if video_path else None
        db_std, rms_max = _db_std_from_profile(audio_profile, s.start, s.end)
        if rms_max is not None:
            audio_peaks.append((float(rms_max), s))
        vision_fmt = ""
        if frame_diff_mean is not None:
            vision_label = "动态" if float(frame_diff_mean) >= 0.06 else "静态"
            vision_fmt = f"{vision_label}(帧差={frame_diff_mean:.3f})"
        audio_fmt = f"dB_std={db_std:.2f}" if db_std is not None else ""
        part = (
            f"[{_sec_to_hms(s.start)} - {_sec_to_hms(s.end)}]"
            f" duration={duration:.2f}"
            f" lines={line_count}"
            f" score={score:.3f}({hit_count}/{denom})"
            f" first={_safe_json(first_line)}"
            f" last={_safe_json(last_line)}"
            f" top_terms={_safe_json(top_terms)}"
            f" people={_safe_json(people_names_list)}"
        )
        if people_names:
            part += f" people_pid={_safe_json(list(people_ids))}"
        if s.keywords:
            part += f" keywords_hit={_safe_json(list(s.keywords))}"
        if vision_fmt:
            part += f" vision={_safe_json(vision_fmt)}"
        if audio_fmt:
            part += f" audio={_safe_json(audio_fmt)}"
        part += f" speech_rate={speech_rate:.2f}"
        part += f" density={_safe_json(density_label)}"
        lines.append(part)

    lines.append("")
    lines.append("# 统计")
    durations = [float(s.end) - float(s.start) for s in ordered]
    if durations:
        lines.append(f"duration_min={min(durations):.2f}")
        lines.append(f"duration_avg={(sum(durations)/len(durations)):.2f}")
        lines.append(f"duration_max={max(durations):.2f}")
    top_scored = sorted(high_score, key=lambda x: x[0], reverse=True)[:10]
    lines.append("top_score_segments=" + _safe_json([
        {"start": _sec_to_hms(s.start), "end": _sec_to_hms(s.end), "score": round(sc, 3)}
        for sc, s in top_scored
    ]))
    lines.append("top_people=" + _safe_json(people_freq.most_common(20)))
    if audio_peaks:
        top_peaks = sorted(audio_peaks, key=lambda x: x[0], reverse=True)[:10]
        lines.append("top_audio_peaks=" + _safe_json([
            {"start": _sec_to_hms(s.start), "end": _sec_to_hms(s.end), "rms_max": round(v, 6)}
            for v, s in top_peaks
        ]))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _collect_context_lines(
    all_lines: Sequence[TranscriptLine],
    t0: float,
    t1: float,
) -> List[TranscriptLine]:
    out: List[TranscriptLine] = []
    for l in all_lines:
        if l.t1 < t0:
            continue
        if l.t0 > t1:
            break
        out.append(l)
    return out


def write_segment_contexts(
    segments: Sequence[Segment],
    all_lines: Sequence[TranscriptLine],
    out_dir: str,
    context_window: float,
) -> None:
    seg_dir = os.path.join(out_dir, "segments")
    _ensure_dir(seg_dir)
    for s in segments:
        ctx0 = max(0.0, float(s.start) - float(context_window))
        ctx1 = float(s.end) + float(context_window)
        ctx_lines = _collect_context_lines(all_lines, ctx0, ctx1)
        p = os.path.join(seg_dir, f"seg_{s.index:02d}_context.txt")
        buf: List[str] = []
        buf.append("【骨架信息】")
        buf.append(f"index: {s.index}")
        buf.append(f"start: {s.start:.3f}")
        buf.append(f"end: {s.end:.3f}")
        buf.append("anchor_time: （待填入）")
        buf.append("render_type: （待填入）")
        buf.append("one_line_summary: （待填入）")
        buf.append("bridge_note: （待填入）")
        buf.append("")
        buf.append("【上一段解说词】")
        buf.append("（待填入）")
        buf.append("")
        buf.append(f"【Vision Events（{_sec_to_hms(ctx0)} ~ {_sec_to_hms(ctx1)}）】")
        for l in ctx_lines:
            if l.kind != "vision":
                continue
            buf.append(l.raw)
        buf.append("")
        buf.append(f"【本段素材（{_sec_to_hms(ctx0)} ~ {_sec_to_hms(ctx1)}）】")
        core0 = float(s.start)
        core1 = float(s.end)
        for l in ctx_lines:
            if l.kind != "dialogue":
                continue
            in_core = not (l.t1 < core0 or l.t0 > core1)
            prefix = "▶ " if in_core else "  "
            buf.append(prefix + l.raw)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(buf))


def _extract_frame(video_path: str, t_sec: float, out_path: str) -> bool:
    if not _HAS_CV2 or cv2 is None:
        return False
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t_sec) * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            return False
        _ensure_dir(os.path.dirname(out_path) or ".")
        return bool(cv2.imwrite(out_path, frame))
    finally:
        try:
            cap.release()
        except Exception:
            pass


def export_all(
    transcript_path: str,
    video_path: Optional[str],
    out_dir: str,
    gap_threshold: float,
    context_window: float,
    extract_frames: bool,
    keywords: Optional[Sequence[Tuple[str, float]]] = None,
    people_names_path: str = "",
) -> Dict[str, Any]:
    keywords = list(keywords) if keywords is not None else _default_keywords()
    _ensure_dir(out_dir)
    all_lines, visions, dialogues = parse_transcript(transcript_path)
    if not dialogues and visions:
        pseudo: List[DialogueLine] = []
        for ve in visions:
            ppl = ",".join(ve.people) if ve.people else "无"
            txt = f"(无字幕) 人物：{ppl} face_count={ve.face_count}"
            ts = _sec_to_ts_mmm(float(ve.t))
            raw = f'[{ts} - {ts}] 台词：“{txt}” | 【台词密度：无】'
            pseudo.append(DialogueLine(start=float(ve.t), end=float(ve.t), text=txt, tags="【台词密度：无】", raw=raw))
            all_lines.append(TranscriptLine(t0=float(ve.t), t1=float(ve.t), kind="dialogue", raw=raw))
        dialogues = pseudo
        all_lines.sort(key=lambda x: (x.t0, x.t1))
    groups = segment_dialogues(dialogues, gap_threshold=gap_threshold)
    groups = split_dialogue_groups(groups, max_seconds=_DEFAULT_MAX_SEG_SECONDS, max_lines=_DEFAULT_MAX_SEG_LINES)
    segments = build_segments(groups, visions, keywords=keywords, people_pad_sec=5.0)
    synopsis_path = os.path.join(out_dir, "synopsis.txt")
    total_duration = max([float(l.t1) for l in all_lines], default=0.0)
    audio_profile = None
    if _HAS_AUDIO_PROFILE and get_audio_rms_profile is not None and video_path and os.path.exists(video_path):
        audio_profile = get_audio_rms_profile(video_path)
    people_names = _load_people_names(people_names_path)
    write_synopsis(
        segments,
        transcript_path=transcript_path,
        out_path=synopsis_path,
        total_duration=total_duration,
        video_path=video_path,
        keyword_total=len(keywords),
        audio_profile=audio_profile,
        people_names=people_names,
        gap_threshold=gap_threshold,
        max_seg_seconds=_DEFAULT_MAX_SEG_SECONDS,
        max_seg_lines=_DEFAULT_MAX_SEG_LINES,
    )
    write_segment_contexts(segments, all_lines=all_lines, out_dir=out_dir, context_window=context_window)
    frame_dir = os.path.join(out_dir, "frames")
    if extract_frames and video_path and os.path.exists(video_path) and _HAS_CV2:
        _ensure_dir(frame_dir)
        for s in segments:
            mid = (float(s.start) + float(s.end)) / 2.0
            out_path = os.path.join(frame_dir, f"seg_{s.index:02d}_anchor.jpg")
            _extract_frame(video_path, mid, out_path)
    export_summary = {
        "version": 1,
        "transcript_path": os.path.abspath(transcript_path),
        "video_path": os.path.abspath(video_path) if video_path else None,
        "out_dir": os.path.abspath(out_dir),
        "gap_threshold": float(gap_threshold),
        "context_window": float(context_window),
        "extract_frames": bool(extract_frames and bool(video_path) and _HAS_CV2),
        "segment_count": len(segments),
        "segments": [
            {
                "index": s.index,
                "start": float(s.start),
                "end": float(s.end),
                "score": float(s.score),
                "keywords": list(s.keywords),
                "people_in_shot": list(s.people_in_shot),
                "vision_tag": s.vision_tag,
                "audio_tag": s.audio_tag,
                "density_tag": s.density_tag,
                "preview": " / ".join([d.text for d in s.lines[:3] if d.text]),
            }
            for s in segments
        ],
    }
    with open(os.path.join(out_dir, "export_summary.json"), "w", encoding="utf-8") as f:
        json.dump(export_summary, f, ensure_ascii=False, indent=2)
    return export_summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--transcript", required=True)
    p.add_argument("--video", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--gap-threshold", type=float, default=_DEFAULT_GAP_THRESHOLD)
    p.add_argument("--context-window", type=float, default=30.0)
    p.add_argument("--people-names", default="", help="Path to people_names.json for pXX -> real name mapping.")
    p.add_argument("--no-frames", action="store_true")
    args = p.parse_args(argv)
    transcript_path = str(args.transcript)
    video_path = str(args.video or "").strip() or None
    out_dir = str(args.out)
    extract_frames = not bool(args.no_frames)
    export_all(
        transcript_path=transcript_path,
        video_path=video_path,
        out_dir=out_dir,
        gap_threshold=float(args.gap_threshold),
        context_window=float(args.context_window),
        extract_frames=extract_frames,
        people_names_path=str(getattr(args, "people_names", "") or "").strip(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
