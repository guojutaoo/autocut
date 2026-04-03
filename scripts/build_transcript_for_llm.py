import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class SrtLine:
    start_ts: str
    end_ts: str
    text: str


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


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


def parse_srt(path: str) -> List[SrtLine]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f]
    out: List[SrtLine] = []
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
            out.append(SrtLine(start_ts=start_s.replace(".", ","), end_ts=end_s.replace(".", ","), text=txt))
        i += 1
    return out


def load_faces_index(path: str) -> Dict[float, Tuple[int, List[str]]]:
    by_t: Dict[float, List[str]] = {}
    counts: Dict[float, int] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                r = json.loads(raw)
            except Exception:
                continue
            t = r.get("t_sec")
            try:
                t_sec = float(t)
            except Exception:
                continue
            t_key = round(t_sec, 3)
            pid = r.get("person_id")
            if isinstance(pid, str) and pid and pid.startswith("p"):
                by_t.setdefault(t_key, []).append(pid)
            counts[t_key] = counts.get(t_key, 0) + 1
    out: Dict[float, Tuple[int, List[str]]] = {}
    for t_key in sorted(counts.keys()):
        ppl = sorted(set(by_t.get(t_key, [])))
        out[t_key] = (int(counts.get(t_key, 0)), ppl)
    return out


def build_transcript(
    srt_path: str,
    faces_index_path: str,
    out_path: str,
    tag_density: str,
) -> None:
    srt_lines = parse_srt(srt_path)
    faces = load_faces_index(faces_index_path)
    buf: List[str] = []
    buf.append("# Vision Events (3s sampling, only on change)")
    last_sig: Optional[Tuple[int, Tuple[str, ...]]] = None
    for t_sec, (face_count, ppl) in faces.items():
        sig = (int(face_count), tuple(ppl))
        if last_sig == sig:
            continue
        buf.append(f"[{_sec_to_ts_mmm(float(t_sec))}] 人物：face_count={int(face_count)} | people_in_shot={ppl}")
        last_sig = sig
    buf.append("")
    for s in srt_lines:
        buf.append(f'[{s.start_ts} - {s.end_ts}] 台词：“{s.text}” | 【台词密度：{tag_density}】')
    _ensure_dir(os.path.dirname(out_path) or ".")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(buf).rstrip() + "\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--srt", required=True)
    ap.add_argument("--faces-index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--density", default="无")
    args = ap.parse_args(argv)

    build_transcript(
        srt_path=str(args.srt),
        faces_index_path=str(args.faces_index),
        out_path=str(args.out),
        tag_density=str(args.density),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
