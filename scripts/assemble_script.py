import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _sec_to_hms(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class Modification:
    index: int
    change_type: str
    text: str


def _load_skeleton(skeleton_path: str) -> Tuple[float, List[Dict[str, Any]]]:
    payload = _read_json(skeleton_path) or {}
    if isinstance(payload, list):
        segments = payload
        video_dur = 0.0
    else:
        segments = payload.get("segments") or []
        video_dur = float(payload.get("video_duration") or payload.get("video_duration_sec") or 0.0)
    if not isinstance(segments, list):
        segments = []
    out: List[Dict[str, Any]] = []
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        idx = int(seg.get("index", i))
        out.append({"index": idx, **seg})
    out.sort(key=lambda x: float(x.get("start", 0.0)))
    return float(video_dur), out


def _load_narrations(narr_dir: str) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    if not narr_dir or not os.path.isdir(narr_dir):
        return out
    for name in os.listdir(narr_dir):
        if not name.endswith(".json"):
            continue
        path = os.path.join(narr_dir, name)
        try:
            payload = _read_json(path) or {}
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        idx = payload.get("index")
        if idx is None:
            base = os.path.splitext(name)[0]
            if base.startswith("seg_"):
                try:
                    idx = int(base.split("_", 1)[1])
                except Exception:
                    idx = None
        if idx is None:
            continue
        try:
            idx_i = int(idx)
        except Exception:
            continue
        out[idx_i] = payload
    return out


def _load_polish(polish_path: Optional[str]) -> List[Modification]:
    if not polish_path:
        return []
    if not os.path.exists(polish_path):
        return []
    payload = _read_json(polish_path) or {}
    mods = payload.get("modifications") if isinstance(payload, dict) else None
    if not isinstance(mods, list):
        return []
    out: List[Modification] = []
    for it in mods:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("index"))
        except Exception:
            continue
        change_type = str(it.get("change_type") or "").strip().lower()
        text = str(it.get("text") or "")
        if change_type not in ("prepend", "append", "replace", "clear"):
            continue
        out.append(Modification(index=idx, change_type=change_type, text=text))
    return out


def _apply_modifications(segments: List[Dict[str, Any]], mods: List[Modification]) -> None:
    by_idx: Dict[int, Dict[str, Any]] = {int(s.get("index")): s for s in segments if isinstance(s, dict)}
    for m in mods:
        seg = by_idx.get(int(m.index))
        if not seg:
            continue
        cur = str(seg.get("narration_text") or "")
        if m.change_type == "clear":
            seg["narration_text"] = ""
        elif m.change_type == "replace":
            seg["narration_text"] = m.text
        elif m.change_type == "prepend":
            seg["narration_text"] = (m.text + cur) if cur else m.text
        elif m.change_type == "append":
            seg["narration_text"] = (cur + m.text) if cur else m.text


def assemble(
    skeleton_path: str,
    narrations_dir: str,
    polish_path: Optional[str],
    video_duration: float,
) -> Tuple[Dict[str, Any], str]:
    skel_video_dur, segments = _load_skeleton(skeleton_path)
    video_dur = float(video_duration or skel_video_dur or 0.0)
    narrs = _load_narrations(narrations_dir)
    for seg in segments:
        idx = int(seg.get("index"))
        n = narrs.get(idx) or {}
        if isinstance(n, dict):
            if "narration_text" in n:
                seg["narration_text"] = n.get("narration_text") or ""
            if "bridge_note" in n and n.get("bridge_note") is not None:
                seg["bridge_note"] = n.get("bridge_note")
            if "anchor_time" in n and n.get("anchor_time") is not None:
                seg["anchor_time"] = n.get("anchor_time")
            if "render_type" in n and n.get("render_type"):
                seg["render_type"] = n.get("render_type")
    mods = _load_polish(polish_path)
    _apply_modifications(segments, mods)
    script = {"version": 1, "video_duration_sec": video_dur, "segments": segments}
    report = validate(script)
    return script, report


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def validate(script: Dict[str, Any]) -> str:
    segs = script.get("segments") or []
    if not isinstance(segs, list):
        segs = []
    video_dur = float(script.get("video_duration_sec") or 0.0)
    buf: List[str] = []
    ok_all = True

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok_all
        if not passed:
            ok_all = False
        status = "PASS" if passed else "FAIL"
        if detail:
            buf.append(f"[{status}] {name}: {detail}")
        else:
            buf.append(f"[{status}] {name}")

    buf.append("# validation_report")

    last_end = 0.0
    for s in segs:
        if not isinstance(s, dict):
            continue
        try:
            last_end = max(last_end, float(s.get("end") or 0.0))
        except Exception:
            pass
    if video_dur > 0:
        cov = last_end / video_dur if video_dur else 0.0
        check("全片覆盖率", cov > 0.8, f"last_end={_sec_to_hms(last_end)} / video={_sec_to_hms(video_dur)} ({_pct(cov)})")
    else:
        check("全片覆盖率", False, "缺少 --video-duration 或 skeleton 内 video_duration")

    counts: Dict[str, int] = {}
    for s in segs:
        if not isinstance(s, dict):
            continue
        rt = str(s.get("render_type") or "freeze").strip().lower()
        counts[rt] = counts.get(rt, 0) + 1
    total = sum(counts.values()) or 0
    if total > 0:
        freeze_ratio = counts.get("freeze", 0) / total
        overdub_ratio = counts.get("overdub", 0) / total
        pure_ratio = counts.get("pure_audio", 0) / total
        passed = 0.5 <= freeze_ratio <= 0.6 and 0.2 <= overdub_ratio <= 0.3 and 0.1 <= pure_ratio <= 0.2
        check(
            "render_type 分布",
            passed,
            f"freeze={_pct(freeze_ratio)} overdub={_pct(overdub_ratio)} pure_audio={_pct(pure_ratio)} (total={total})",
        )
    else:
        check("render_type 分布", False, "segments 为空")

    segs_sorted = [s for s in segs if isinstance(s, dict)]
    segs_sorted.sort(key=lambda x: float(x.get("start") or 0.0))
    jump_issues: List[str] = []
    for prev, cur in zip(segs_sorted, segs_sorted[1:]):
        try:
            gap = float(cur.get("start") or 0.0) - float(prev.get("end") or 0.0)
        except Exception:
            continue
        if gap <= 600.0:
            continue
        bridge = str(cur.get("bridge_note") or prev.get("bridge_note") or "").strip()
        if not bridge:
            jump_issues.append(
                f"gap={int(gap)}s prev={_sec_to_hms(float(prev.get('end') or 0.0))} cur={_sec_to_hms(float(cur.get('start') or 0.0))} idx={prev.get('index')}->{cur.get('index')}"
            )
    check("段间跳跃", len(jump_issues) == 0, "; ".join(jump_issues) if jump_issues else "")

    length_issues: List[str] = []
    for s in segs_sorted:
        rt = str(s.get("render_type") or "freeze").strip().lower()
        txt = str(s.get("narration_text") or "")
        n = len(txt)
        if rt == "freeze" and n > 100:
            length_issues.append(f"freeze idx={s.get('index')} chars={n}")
        if rt == "overdub" and n > 200:
            length_issues.append(f"overdub idx={s.get('index')} chars={n}")
        if rt == "pure_audio" and txt.strip():
            length_issues.append(f"pure_audio idx={s.get('index')} narration_not_empty")
    check("旁白字数/空旁白", len(length_issues) == 0, "; ".join(length_issues) if length_issues else "")

    anchor_issues: List[str] = []
    for s in segs_sorted:
        try:
            start = float(s.get("start") or 0.0)
            anchor = float(s.get("anchor_time") or 0.0)
        except Exception:
            continue
        if anchor - start < 2.0:
            anchor_issues.append(f"idx={s.get('index')} prep={(anchor-start):.2f}s")
    check("anchor 铺垫时间", len(anchor_issues) == 0, "; ".join(anchor_issues) if anchor_issues else "")

    buf.append("")
    buf.append("overall: " + ("PASS" if ok_all else "FAIL"))
    return "\n".join(buf)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--skeleton", required=True)
    p.add_argument("--narrations", required=True)
    p.add_argument("--polish", default="")
    p.add_argument("--video-duration", type=float, default=0.0)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    out_path = str(args.out)
    script, report = assemble(
        skeleton_path=str(args.skeleton),
        narrations_dir=str(args.narrations),
        polish_path=str(args.polish or "").strip() or None,
        video_duration=float(args.video_duration or 0.0),
    )
    _write_json(out_path, script)
    report_path = os.path.join(os.path.dirname(out_path) or ".", "validation_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

