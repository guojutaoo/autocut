import argparse
import json
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


def write_synopsis(
    segments: Sequence[Segment],
    transcript_path: str,
    out_path: str,
    max_lines: int = 50,
    total_duration: float = 0.0,
) -> None:
    lines: List[str] = []
    base = os.path.basename(transcript_path)
    last_end = 0.0
    for s in segments:
        last_end = max(last_end, s.end)
    if not segments:
        last_end = float(total_duration or 0.0)
    lines.append("# 全片摘要")
    lines.append(f"transcript：{base}")
    lines.append(f"全片时长：{_sec_to_hms(last_end)}")
    lines.append(f"候选段落数：{len(segments)}")
    lines.append("")
    if len(segments) > max_lines:
        ordered = sorted(segments, key=lambda x: (x.score, x.end - x.start), reverse=True)[:max_lines]
        ordered = sorted(ordered, key=lambda x: x.start)
    else:
        ordered = list(segments)
    for s in ordered:
        preview = " / ".join([d.text for d in s.lines[:3] if d.text])
        if len(s.lines) > 3:
            preview = f"{preview} ...（共{len(s.lines)}句）"
        kw = ",".join(s.keywords) if s.keywords else ""
        ppl = ",".join(s.people_in_shot) if s.people_in_shot else ""
        part = (
            f"[{_sec_to_hms(s.start)} - {_sec_to_hms(s.end)}] "
            f"“{preview}”"
            f" / score={s.score:.2f}"
        )
        if kw:
            part += f" / keywords=[{kw}]"
        if s.vision_tag:
            part += f" / 视觉：{s.vision_tag}"
        if s.audio_tag:
            part += f" / 听觉：{s.audio_tag}"
        if s.density_tag:
            part += f" / 台词密度：{s.density_tag}"
        if ppl:
            part += f" / 出镜人物：{ppl}"
        lines.append(part)
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
    segments = build_segments(groups, visions, keywords=keywords, people_pad_sec=5.0)
    synopsis_path = os.path.join(out_dir, "synopsis.txt")
    total_duration = max([float(l.t1) for l in all_lines], default=0.0)
    write_synopsis(segments, transcript_path=transcript_path, out_path=synopsis_path, total_duration=total_duration)
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
    p.add_argument("--gap-threshold", type=float, default=6.0)
    p.add_argument("--context-window", type=float, default=30.0)
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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
