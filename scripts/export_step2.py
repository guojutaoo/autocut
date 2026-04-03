import argparse
import json
import os
import shutil
import sys
import re
import base64
import mimetypes
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import cv2  # type: ignore

    _HAS_CV2 = True
except Exception:
    cv2 = None  # type: ignore
    _HAS_CV2 = False

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.render.ffmpeg_compose import _get_video_duration  # type: ignore


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: Any) -> None:
    _ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _parse_hms(ts: Optional[str]) -> Optional[float]:
    if ts is None:
        return None
    s = str(ts).strip()
    if not s:
        return None
    if "," in s or "." in s:
        h, m, s_ms = s.split(":")
        if "," in s_ms:
            sec_s, ms_s = s_ms.split(",", 1)
        else:
            sec_s, ms_s = s_ms.split(".", 1)
        return int(h) * 3600 + int(m) * 60 + int(sec_s) + int(ms_s) / 1000.0
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


_TS_RE = r"\d\d:\d\d:\d\d(?:[,.]\d\d\d)?"
_RE_BRACKET_RANGE = re.compile(
    rf"^\[(?P<start>{_TS_RE})\s*(?:-|->|—|–|-->)\s*(?P<end>{_TS_RE})\]\s*(?P<rest>.*)$"
)
_RE_QUOTED = re.compile(r'台词：["“](?P<text>.*?)["”]')


@dataclass
class DialogueLine:
    start: float
    end: float
    text: str


def _ts_to_sec(ts: str) -> float:
    s = str(ts).strip()
    if "," in s:
        h, m, s_ms = s.split(":")
        sec_s, ms_s = s_ms.split(",", 1)
        return int(h) * 3600 + int(m) * 60 + int(sec_s) + int(ms_s) / 1000.0
    if "." in s:
        h, m, s_ms = s.split(":")
        sec_s, ms_s = s_ms.split(".", 1)
        return int(h) * 3600 + int(m) * 60 + int(sec_s) + int(ms_s) / 1000.0
    h, m, sec_s = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec_s)


def _parse_srt_dialogues(transcript_path: str) -> List[DialogueLine]:
    out: List[DialogueLine] = []
    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.isdigit():
            i += 1
            if i >= len(lines):
                break
            line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        try:
            start_s, end_s = [p.strip() for p in line.split("-->", 1)]
            t0 = _ts_to_sec(start_s)
            t1 = _ts_to_sec(end_s)
        except Exception:
            i += 1
            continue
        i += 1
        buf: List[str] = []
        while i < len(lines) and lines[i].strip():
            buf.append(lines[i].strip())
            i += 1
        txt = " ".join(buf).strip()
        if txt:
            out.append(DialogueLine(start=t0, end=t1, text=txt))
        i += 1
    out.sort(key=lambda x: (x.start, x.end))
    return out


def _parse_bracket_dialogues(transcript_path: str) -> List[DialogueLine]:
    out: List[DialogueLine] = []
    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n").strip()
            if not line:
                continue
            m = _RE_BRACKET_RANGE.match(line)
            if not m:
                continue
            try:
                t0 = _ts_to_sec(m.group("start"))
                t1 = _ts_to_sec(m.group("end"))
            except Exception:
                continue
            rest = str(m.group("rest") or "").strip()
            text = rest
            mq = _RE_QUOTED.search(rest)
            if mq:
                text = str(mq.group("text") or "").strip()
            else:
                if rest.startswith("台词："):
                    text = rest[len("台词：") :].strip()
            if "|" in text:
                text = text.split("|", 1)[0].strip()
            if not text:
                continue
            out.append(DialogueLine(start=float(t0), end=float(t1), text=text))
    out.sort(key=lambda x: (x.start, x.end))
    return out


def _parse_dialogues(transcript_path: str) -> List[DialogueLine]:
    lower = str(transcript_path).lower()
    if lower.endswith(".srt"):
        return _parse_srt_dialogues(transcript_path)
    out = _parse_bracket_dialogues(transcript_path)
    if out:
        return out
    return _parse_srt_dialogues(transcript_path)


def _probe_for_subtitle_candidates(transcript_path: str, video_path: str) -> List[str]:
    candidates: List[str] = []
    vp = str(video_path or "").strip()
    if vp:
        base = os.path.splitext(os.path.basename(vp))[0]
        same_name = os.path.splitext(vp)[0] + ".srt"
        candidates.append(same_name)
        candidates.append(os.path.join(os.path.dirname(transcript_path), "transcription", f"{base}.srt"))
        candidates.append(os.path.join(os.path.dirname(transcript_path), f"{base}.srt"))
    return [c for c in candidates if c and os.path.exists(c)]


def _sec_to_hms(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


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


def _pick_dialogues(
    dialogues: Sequence[DialogueLine],
    t0: float,
    t1: float,
    mode: str,
) -> List[DialogueLine]:
    out: List[DialogueLine] = []
    for d in dialogues:
        if d.end < t0:
            continue
        if d.start > t1:
            break
        if mode == "pre":
            if d.end <= t1 and d.end >= t0:
                out.append(d)
        elif mode == "post":
            if d.start >= t0 and d.start <= t1:
                out.append(d)
        else:
            if not (d.end < t0 or d.start > t1):
                out.append(d)
    return out


def _format_context_line(prefix: str, d: DialogueLine) -> str:
    return f"{prefix}[{_sec_to_hms(d.start)} -> {_sec_to_hms(d.end)}]  {d.text}".rstrip()


def _write_context_file(
    out_path: str,
    start_hms: str,
    end_hms: str,
    render_type: str,
    bridge_note: str,
    anchor_time: Optional[str],
    dialogues: Sequence[DialogueLine],
    context_window: float,
) -> None:
    core0 = float(_parse_hms(start_hms) or 0.0)
    core1 = float(_parse_hms(end_hms) or 0.0)
    pre0 = max(0.0, core0 - float(context_window))
    pre1 = core0
    post0 = core1
    post1 = core1 + float(context_window)
    pre = _pick_dialogues(dialogues, pre0, pre1, mode="pre")
    core = _pick_dialogues(dialogues, core0, core1, mode="core")
    post = _pick_dialogues(dialogues, post0, post1, mode="post")

    buf: List[str] = []
    buf.append(f"# 核心范围: [{start_hms} — {end_hms}]")
    buf.append(f"# render_type = {render_type}")
    buf.append(f"# bridge_note = {bridge_note}")
    buf.append(f"# anchor_time = {anchor_time if anchor_time is not None else 'null'}")
    buf.append("")
    for d in pre:
        buf.append(_format_context_line("  ", d))
    for d in core:
        buf.append(_format_context_line("▶ ", d))
    for d in post:
        buf.append(_format_context_line("  ", d))
    _ensure_dir(os.path.dirname(out_path) or ".")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(buf).rstrip() + "\n")


def _write_segment_bundle_md(
    out_dir: str,
    order: int,
    one_line_summary: str,
    context_file: str,
    frame_files: Sequence[str],
) -> str:
    bundle_file = f"seg_{order:02d}_bundle.md"
    bundle_path = os.path.join(out_dir, bundle_file)
    ctx_path = os.path.join(out_dir, context_file)
    try:
        with open(ctx_path, "r", encoding="utf-8", errors="ignore") as f:
            ctx = f.read().rstrip()
    except Exception:
        ctx = ""

    buf: List[str] = []
    buf.append(f"# Seg {order:02d}")
    if one_line_summary:
        buf.append("")
        buf.append(one_line_summary)
    buf.append("")
    buf.append("## Frames")
    for i, fn in enumerate(frame_files, start=1):
        name = os.path.basename(str(fn))
        buf.append(f"### frame_{i}")
        buf.append(f"![{name}](./{name})")
        buf.append("")
    buf.append("## Context")
    buf.append("```text")
    if ctx:
        buf.append(ctx)
    buf.append("```")
    _ensure_dir(os.path.dirname(bundle_path) or ".")
    with open(bundle_path, "w", encoding="utf-8") as f:
        f.write("\n".join(buf).rstrip() + "\n")
    return bundle_file


def _read_image_as_data_uri(path: str) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "image/jpeg"
    try:
        with open(path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def _escape_html(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _write_segment_bundle_html(
    out_dir: str,
    order: int,
    one_line_summary: str,
    context_file: str,
    frame_files: Sequence[str],
) -> str:
    bundle_file = f"seg_{order:02d}_bundle.html"
    bundle_path = os.path.join(out_dir, bundle_file)
    ctx_path = os.path.join(out_dir, context_file)
    try:
        with open(ctx_path, "r", encoding="utf-8", errors="ignore") as f:
            ctx = f.read().rstrip()
    except Exception:
        ctx = ""

    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="zh-CN"><head><meta charset="utf-8" />')
    parts.append(f"<title>Seg {order:02d}</title>")
    parts.append(
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;"
        "margin:24px;line-height:1.5;color:#111}"
        "h1{margin:0 0 8px 0}"
        ".summary{margin:0 0 16px 0;color:#333}"
        ".grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}"
        ".card{border:1px solid #ddd;border-radius:8px;padding:12px}"
        "img{max-width:100%;height:auto;border-radius:6px;display:block}"
        "pre{white-space:pre-wrap;background:#0b1020;color:#e7e7e7;padding:12px;border-radius:8px;overflow:auto}"
        "</style></head><body>"
    )
    parts.append(f"<h1>Seg {order:02d}</h1>")
    if one_line_summary:
        parts.append(f'<p class="summary">{_escape_html(one_line_summary)}</p>')
    parts.append("<h2>Frames</h2>")
    parts.append('<div class="grid">')
    for i, fn in enumerate(frame_files, start=1):
        name = os.path.basename(str(fn))
        img_path = os.path.join(out_dir, name)
        uri = _read_image_as_data_uri(img_path)
        parts.append('<div class="card">')
        parts.append(f"<h3>frame_{i}</h3>")
        if uri:
            parts.append(f'<img src="{uri}" alt="{_escape_html(name)}" />')
        else:
            parts.append(f"<p>missing: {_escape_html(name)}</p>")
        parts.append("</div>")
    parts.append("</div>")
    parts.append("<h2>Context</h2>")
    parts.append(f"<pre>{_escape_html(ctx)}</pre>")
    parts.append("</body></html>")
    with open(bundle_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts).rstrip() + "\n")
    return bundle_file


def _write_all_bundles_md(out_dir: str, episode: str, segs: Sequence[Dict[str, Any]]) -> str:
    out_name = "step2_all.md"
    out_path = os.path.join(out_dir, out_name)
    buf: List[str] = []
    buf.append(f"# {episode or 'Step2'}")
    buf.append("")
    for s in segs:
        order = int(s.get("order") or 0)
        if order <= 0:
            continue
        bundle = str(s.get("bundle_file") or "").strip()
        summary = str(s.get("one_line_summary") or "").strip()
        start = str(s.get("start") or "").strip()
        end = str(s.get("end") or "").strip()
        title = f"Seg {order:02d} [{start} — {end}]"
        buf.append(f"## {title}")
        if summary:
            buf.append("")
            buf.append(summary)
        if bundle:
            buf.append("")
            buf.append(f"[打开 bundle]({bundle})")
        buf.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(buf).rstrip() + "\n")
    return out_name


def _write_all_bundles_html(out_dir: str, episode: str, segs: Sequence[Dict[str, Any]]) -> str:
    out_name = "step2_all.html"
    out_path = os.path.join(out_dir, out_name)
    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="zh-CN"><head><meta charset="utf-8" />')
    parts.append(f"<title>{_escape_html(episode or 'Step2')}</title>")
    parts.append(
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;margin:24px;line-height:1.5}"
        "a{color:#0b57d0;text-decoration:none}"
        "a:hover{text-decoration:underline}"
        "li{margin:8px 0}"
        "</style></head><body>"
    )
    parts.append(f"<h1>{_escape_html(episode or 'Step2')}</h1>")
    parts.append("<ul>")
    for s in segs:
        order = int(s.get("order") or 0)
        if order <= 0:
            continue
        bundle = str(s.get("bundle_html") or "").strip()
        start = str(s.get("start") or "").strip()
        end = str(s.get("end") or "").strip()
        summary = str(s.get("one_line_summary") or "").strip()
        label = f"Seg {order:02d} [{start} — {end}]"
        parts.append("<li>")
        if bundle:
            parts.append(f'<a href="{_escape_html(bundle)}">{_escape_html(label)}</a>')
        else:
            parts.append(_escape_html(label))
        if summary:
            parts.append(f"<div>{_escape_html(summary)}</div>")
        parts.append("</li>")
    parts.append("</ul></body></html>")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts).rstrip() + "\n")
    return out_name


def _write_step2_bundle_html(out_dir: str, episode: str, segs: Sequence[Dict[str, Any]]) -> str:
    out_name = "step2_bundle.html"
    out_path = os.path.join(out_dir, out_name)
    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="zh-CN"><head><meta charset="utf-8" />')
    parts.append(f"<title>{_escape_html(episode or 'Step2 Bundle')}</title>")
    parts.append(
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;margin:24px;line-height:1.5;color:#111}"
        "h1{margin:0 0 12px 0}"
        "h2{margin:28px 0 10px 0;padding-top:8px;border-top:1px solid #eee}"
        ".meta{color:#444;margin:0 0 12px 0}"
        ".summary{margin:6px 0 14px 0;color:#333}"
        ".grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}"
        ".card{border:1px solid #ddd;border-radius:8px;padding:12px}"
        "img{max-width:100%;height:auto;border-radius:6px;display:block}"
        "pre{white-space:pre-wrap;background:#0b1020;color:#e7e7e7;padding:12px;border-radius:8px;overflow:auto}"
        "</style></head><body>"
    )
    parts.append(f"<h1>{_escape_html(episode or 'Step2 Bundle')}</h1>")
    parts.append('<p class="meta">包含全部段落的截图与台词上下文（图片已内嵌，可单文件转发）。</p>')

    for s in segs:
        order = int(s.get("order") or 0)
        if order <= 0:
            continue
        start = str(s.get("start") or "").strip()
        end = str(s.get("end") or "").strip()
        summary = str(s.get("one_line_summary") or "").strip()
        context_file = str(s.get("context_file") or "").strip()
        frame_files = list(s.get("frame_files") or [])
        title = f"Seg {order:02d} [{start} — {end}]"
        parts.append(f"<h2>{_escape_html(title)}</h2>")
        if summary:
            parts.append(f'<div class="summary">{_escape_html(summary)}</div>')
        parts.append("<h3>Frames</h3>")
        parts.append('<div class="grid">')
        for i, fn in enumerate(frame_files, start=1):
            name = os.path.basename(str(fn))
            img_path = os.path.join(out_dir, name)
            uri = _read_image_as_data_uri(img_path)
            parts.append('<div class="card">')
            parts.append(f"<h4>frame_{i}</h4>")
            if uri:
                parts.append(f'<img src="{uri}" alt="{_escape_html(name)}" />')
            else:
                parts.append(f"<p>missing: {_escape_html(name)}</p>")
            parts.append("</div>")
        parts.append("</div>")
        parts.append("<h3>Context</h3>")
        ctx_path = os.path.join(out_dir, context_file)
        try:
            with open(ctx_path, "r", encoding="utf-8", errors="ignore") as f:
                ctx = f.read().rstrip()
        except Exception:
            ctx = ""
        parts.append(f"<pre>{_escape_html(ctx)}</pre>")

    parts.append("</body></html>")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts).rstrip() + "\n")
    return out_name


def _segment_frame_times(
    start_sec: float,
    end_sec: float,
    anchor_sec: Optional[float],
) -> List[float]:
    dur = max(0.0, float(end_sec) - float(start_sec))
    t1 = float(start_sec) + 0.5
    t2 = float(start_sec) + dur * 0.25
    t3 = float(anchor_sec) if anchor_sec is not None else float(start_sec) + dur * 0.5
    t4 = float(start_sec) + dur * 0.75
    t5 = float(end_sec) - 0.5
    lo = min(float(start_sec), float(end_sec))
    hi = max(float(start_sec), float(end_sec))
    return [_clip(t, lo, hi) for t in [t1, t2, t3, t4, t5]]


def export_step2(
    transcript_path: str,
    synopsis_path: str,
    video_path: str,
    skill1_path: str,
    out_dir: str,
    context_window: float,
    extract_frames: bool,
) -> None:
    if not os.path.exists(transcript_path):
        raise FileNotFoundError(transcript_path)
    if synopsis_path:
        if not os.path.exists(synopsis_path):
            raise FileNotFoundError(synopsis_path)
    if extract_frames and (not video_path or not os.path.exists(video_path)):
        raise FileNotFoundError(video_path)
    if extract_frames and not _HAS_CV2:
        raise RuntimeError("opencv-python 未安装，无法导出截图。可加 --no-frames 仅导出文本与 manifest。")
    if not os.path.exists(skill1_path):
        raise FileNotFoundError(skill1_path)

    _ensure_dir(out_dir)
    skill1_obj = _read_json(skill1_path)
    segments = list(skill1_obj.get("segments") or [])
    segments.sort(key=lambda x: int(x.get("order") or 0))

    dialogues = _parse_dialogues(transcript_path)
    if not dialogues:
        subtitle_candidates = _probe_for_subtitle_candidates(transcript_path, video_path)
        for srt_path in subtitle_candidates:
            dialogues = _parse_dialogues(srt_path)
            if dialogues:
                transcript_path = srt_path
                break
    if not dialogues:
        raise RuntimeError(
            "transcript 未解析到任何台词行。\n"
            f"- 当前传入: {transcript_path}\n"
            "- 你的 transcript_for_llm.txt 目前看起来只有 Vision Events（没有字幕/台词行），无法生成“前文/核心/后台词”。\n"
            "- 解决方式：提供字幕 SRT（--subtitle 或与视频同名 .srt），或先跑 xhs_autocut --transcribe 生成 transcription/*.srt。\n"
        )

    out_skill1 = os.path.join(out_dir, "skill1_output.json")
    if os.path.abspath(skill1_path) != os.path.abspath(out_skill1):
        shutil.copyfile(skill1_path, out_skill1)

    video_dur = float(_get_video_duration(video_path)) if (extract_frames and video_path) else 0.0
    if extract_frames and video_dur <= 0.0:
        video_dur = 10e9

    manifest_segments: List[Dict[str, Any]] = []
    for seg in segments:
        order = int(seg.get("order") or 0)
        start = str(seg.get("start") or "").strip()
        end = str(seg.get("end") or "").strip()
        if not start or not end or order <= 0:
            continue
        render_type = str(seg.get("render_type") or "").strip()
        anchor_time = seg.get("anchor_time", None)
        anchor_time_str = None if anchor_time is None else str(anchor_time).strip() or None
        bridge_note = str(seg.get("bridge_note") or "").strip()
        one_line_summary = str(seg.get("one_line_summary") or "").strip()
        duration = seg.get("duration", None)
        if duration is None:
            s0 = float(_parse_hms(start) or 0.0)
            s1 = float(_parse_hms(end) or 0.0)
            duration = max(0.0, s1 - s0)

        context_file = str(seg.get("context_file") or f"seg_{order:02d}_context.txt")
        frame_files = list(seg.get("frame_files") or [f"seg_{order:02d}_frame_{i}.jpg" for i in range(1, 6)])

        _write_context_file(
            out_path=os.path.join(out_dir, context_file),
            start_hms=start,
            end_hms=end,
            render_type=render_type,
            bridge_note=bridge_note,
            anchor_time=anchor_time_str,
            dialogues=dialogues,
            context_window=float(context_window),
        )

        if extract_frames:
            s0 = float(_parse_hms(start) or 0.0)
            s1 = float(_parse_hms(end) or 0.0)
            a0 = _parse_hms(anchor_time_str)
            times = _segment_frame_times(s0, s1, a0)
            for t, fn in zip(times, frame_files):
                t_clipped = _clip(float(t), 0.0, float(video_dur))
                out_path = os.path.join(out_dir, str(fn))
                ok = _extract_frame(video_path, t_clipped, out_path)
                if not ok:
                    raise RuntimeError(f"抽帧失败: t={t_clipped:.3f}s -> {out_path}")

        bundle_file = _write_segment_bundle_md(
            out_dir=out_dir,
            order=order,
            one_line_summary=one_line_summary,
            context_file=context_file,
            frame_files=frame_files,
        )
        bundle_html = _write_segment_bundle_html(
            out_dir=out_dir,
            order=order,
            one_line_summary=one_line_summary,
            context_file=context_file,
            frame_files=frame_files,
        )

        manifest_segments.append(
            {
                "order": int(order),
                "start": start,
                "end": end,
                "duration": float(duration),
                "render_type": render_type,
                "anchor_time": anchor_time_str,
                "bridge_note": bridge_note,
                "one_line_summary": one_line_summary,
                "context_file": context_file,
                "frame_files": frame_files,
                "bundle_file": bundle_file,
                "bundle_html": bundle_html,
            }
        )

    ep = str(skill1_obj.get("episode", "") or "")
    _write_all_bundles_md(out_dir, ep, manifest_segments)
    _write_all_bundles_html(out_dir, ep, manifest_segments)
    _write_step2_bundle_html(out_dir, ep, manifest_segments)
    manifest = {
        "episode": skill1_obj.get("episode", ""),
        "total_segments": int(skill1_obj.get("total_segments") or 0),
        "selected_segments": int(skill1_obj.get("selected_segments") or len(manifest_segments)),
        "segments": manifest_segments,
    }
    _write_json(os.path.join(out_dir, "step2_manifest.json"), manifest)


def _default_out_dir(video_path: str) -> str:
    base = os.path.basename(str(video_path).strip())
    stem = os.path.splitext(base)[0] if base else "video"
    return os.path.join("outputs", "step2", stem)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--transcript", required=True)
    p.add_argument("--synopsis", default="")
    p.add_argument("--video", default="")
    p.add_argument("--skill1", required=True)
    p.add_argument("--out", default="")
    p.add_argument("--context-window", type=float, default=30.0)
    p.add_argument("--no-frames", action="store_true")
    args = p.parse_args(argv)

    video_path = str(args.video or "").strip()
    out_dir = str(args.out or "").strip()
    if not out_dir:
        if not video_path:
            raise SystemExit("--out 未指定时，必须提供 --video，用于生成默认输出目录 outputs/step2/${video名字}")
        out_dir = _default_out_dir(video_path)

    export_step2(
        transcript_path=str(args.transcript),
        synopsis_path=str(args.synopsis),
        video_path=video_path,
        skill1_path=str(args.skill1),
        out_dir=out_dir,
        context_window=float(args.context_window),
        extract_frames=not bool(args.no_frames),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
