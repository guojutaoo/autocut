from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    HAS_CV2 = True
except Exception:
    cv2 = None  # type: ignore
    np = None  # type: ignore
    HAS_CV2 = False

from ..ingestion.ingestor import read_video_frames
from ..vision.face_emotion import FaceIdentityAssigner, detect_faces_on_frame, extract_face_vision_on_frame


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(name)s: %(message)s")


def _ts_to_sec(ts: str) -> float:
    h, m, s_ms = ts.split(":")
    s, ms = s_ms.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _sec_to_ts(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _parse_people_from_transcript(transcript_path: str) -> Dict[str, Any]:
    if not os.path.exists(transcript_path):
        return {"events": [], "people_counts": {}, "people_set": [], "first_seen": {}, "last_seen": {}}
    pat = re.compile(
        r"^\[(\d\d:\d\d:\d\d,\d\d\d)\]\s+人物：face_count=(\d+)\s+\|\s+people_in_shot=(\[.*\])$"
    )
    events: List[Tuple[float, int, List[str]]] = []
    people_counts: Dict[str, int] = {}
    first_seen: Dict[str, float] = {}
    last_seen: Dict[str, float] = {}
    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            m = pat.match(line)
            if not m:
                continue
            t = _ts_to_sec(m.group(1))
            fc = int(m.group(2))
            try:
                ppl = ast.literal_eval(m.group(3))
            except Exception:
                ppl = []
            if not isinstance(ppl, list):
                ppl = []
            ppl = [p for p in ppl if isinstance(p, str) and p]
            events.append((t, fc, ppl))
            for p in ppl:
                people_counts[p] = int(people_counts.get(p, 0)) + 1
                if p not in first_seen or float(t) < float(first_seen[p]):
                    first_seen[p] = float(t)
                if p not in last_seen or float(t) > float(last_seen[p]):
                    last_seen[p] = float(t)
    people_set = sorted(people_counts.keys())
    return {
        "events": events,
        "people_counts": people_counts,
        "people_set": people_set,
        "first_seen": first_seen,
        "last_seen": last_seen,
    }


def _get_video_fps(video_path: str) -> float:
    if not HAS_CV2:
        return 30.0
    try:
        cap = cv2.VideoCapture(video_path)  # type: ignore[attr-defined]
        if not cap.isOpened():
            return 30.0
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)  # type: ignore[attr-defined]
        cap.release()
        if fps > 0.1:
            return fps
    except Exception:
        return 30.0
    return 30.0


def _load_names_map(path: str) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        return {}
    if isinstance(data, dict):
        out: Dict[str, str] = {}
        for k, v in data.items():
            if not isinstance(k, str) or not k:
                continue
            if v is None:
                out[k] = ""
            elif isinstance(v, str):
                out[k] = v.strip()
            else:
                out[k] = str(v).strip()
        return out
    if isinstance(data, list):
        out = {}
        for it in data:
            if not isinstance(it, dict):
                continue
            pid = it.get("person_id")
            name = it.get("name")
            if isinstance(pid, str) and pid:
                out[pid] = (name or "").strip() if isinstance(name, str) else ""
        return out
    return {}


def _write_names_template(path: str, person_ids: List[str]) -> Dict[str, str]:
    existing = _load_names_map(path)
    for pid in person_ids:
        if pid not in existing:
            existing[pid] = ""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return existing


def _quality_score(bgr: Any) -> float:
    if not HAS_CV2 or bgr is None:
        return 0.0
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]
        v = cv2.Laplacian(gray, cv2.CV_64F).var()  # type: ignore[attr-defined]
        return float(v)
    except Exception:
        return 0.0


def _safe_crop(frame: Any, bbox: List[int]) -> Optional[Any]:
    if not HAS_CV2 or frame is None:
        return None
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    try:
        h, w = frame.shape[:2]
        x, y, bw, bh = [int(v) for v in bbox]
        x0 = max(0, min(w - 1, x))
        y0 = max(0, min(h - 1, y))
        x1 = max(0, min(w, x + bw))
        y1 = max(0, min(h, y + bh))
        if x1 <= x0 or y1 <= y0:
            return None
        return frame[y0:y1, x0:x1].copy()
    except Exception:
        return None


@dataclass
class _SavedFace:
    person_id: str
    path: str
    time_sec: float
    bbox: List[int]
    area: int
    sharpness: float
    score: float


def _write_contact_sheet(
    image_paths: List[str],
    out_path: str,
    thumb_size: int = 160,
    cols: int = 6,
    pad: int = 6,
) -> bool:
    if not HAS_CV2:
        return False
    imgs: List[Any] = []
    for p in image_paths:
        try:
            img = cv2.imread(p)  # type: ignore[attr-defined]
            if img is None:
                continue
            imgs.append(img)
        except Exception:
            continue
    if not imgs:
        return False
    n = len(imgs)
    cols = max(1, int(cols))
    rows = int((n + cols - 1) // cols)
    w = cols * thumb_size + (cols + 1) * pad
    h = rows * thumb_size + (rows + 1) * pad
    canvas = np.zeros((h, w, 3), dtype=np.uint8)  # type: ignore[attr-defined]
    canvas[:] = (16, 16, 16)
    for i, img in enumerate(imgs):
        r = i // cols
        c = i % cols
        x0 = pad + c * (thumb_size + pad)
        y0 = pad + r * (thumb_size + pad)
        try:
            thumb = cv2.resize(img, (thumb_size, thumb_size))  # type: ignore[attr-defined]
            canvas[y0 : y0 + thumb_size, x0 : x0 + thumb_size] = thumb
        except Exception:
            continue
    try:
        return bool(cv2.imwrite(out_path, canvas))  # type: ignore[attr-defined]
    except Exception:
        return False


def build_people_library(
    video_path: str,
    out_dir: str,
    sample_sec: float = 3.0,
    max_faces_per_frame: int = 5,
    min_face_area: int = 40 * 40,
    max_images_per_person: int = 30,
    only_people: Optional[List[str]] = None,
    max_people: int = 0,
    transcript_events: Optional[List[Tuple[float, int, List[str]]]] = None,
    transcript_counts: Optional[Dict[str, int]] = None,
    transcript_first: Optional[Dict[str, float]] = None,
    transcript_last: Optional[Dict[str, float]] = None,
    include_images: bool = False,
    names_path: str = "",
) -> Dict[str, Any]:
    if not HAS_CV2:
        raise RuntimeError("OpenCV is required to build people library.")
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"video not found: {video_path}")
    _safe_mkdir(out_dir)
    crops_dir = os.path.join(out_dir, "crops")
    sheets_dir = os.path.join(out_dir, "sheets")
    if include_images:
        _safe_mkdir(crops_dir)
        _safe_mkdir(sheets_dir)

    fps = _get_video_fps(video_path)
    stride = max(1, int(round(float(fps) * float(sample_sec))))

    allow: Optional[set[str]] = None
    if only_people:
        allow = set([p for p in only_people if isinstance(p, str) and p])

    assigner = FaceIdentityAssigner()

    seen_counts: Dict[str, int] = {}
    first_seen: Dict[str, float] = {}
    last_seen: Dict[str, float] = {}

    saved: Dict[str, List[_SavedFace]] = {}
    kept_people: List[str] = []

    if transcript_counts:
        seen_counts.update({str(k): int(v) for k, v in transcript_counts.items()})
    if transcript_first:
        first_seen.update({str(k): float(v) for k, v in transcript_first.items()})
    if transcript_last:
        last_seen.update({str(k): float(v) for k, v in transcript_last.items()})

    frame_idx = 0
    if transcript_events:
        logger.info("Sampling frames by transcript events: %d", len(transcript_events))
        if not include_images:
            for t, fc, ppl in transcript_events:
                if not ppl:
                    continue
                if allow is not None:
                    ppl = [p for p in ppl if p in allow]
                    if not ppl:
                        continue
                for pid in ppl:
                    if max_people > 0 and pid not in saved and len(saved) >= int(max_people):
                        continue
                    if pid not in saved:
                        saved[pid] = []
                        kept_people.append(pid)
                    seen_counts[pid] = int(seen_counts.get(pid, 0)) + 1
                    first_seen[pid] = min(float(first_seen.get(pid, t) or t), float(t))
                    last_seen[pid] = max(float(last_seen.get(pid, t) or t), float(t))
        else:
            cap = cv2.VideoCapture(video_path)  # type: ignore[attr-defined]
            if not cap.isOpened():
                raise RuntimeError(f"failed to open video: {video_path}")
            try:
                for t, fc, ppl in transcript_events:
                    if not ppl:
                        continue
                    if allow is not None:
                        ppl = [p for p in ppl if p in allow]
                        if not ppl:
                            continue
                    frame_idx += 1
                    cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000.0)  # type: ignore[attr-defined]
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue
                    faces = detect_faces_on_frame(frame, max_faces=int(max_faces_per_frame))
                    faces = [f for f in faces if int(f["bbox"][2]) * int(f["bbox"][3]) >= int(min_face_area)]
                    if not faces:
                        continue
                    faces = sorted(faces, key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
                    for idx, f in enumerate(faces):
                        if idx >= len(ppl):
                            break
                        pid = ppl[idx]
                        if max_people > 0 and pid not in saved and len(saved) >= int(max_people):
                            continue
                        bbox = f.get("bbox")
                        crop = _safe_crop(frame, bbox if isinstance(bbox, list) else [])
                        if crop is None:
                            continue
                        area = int(crop.shape[0] * crop.shape[1]) if hasattr(crop, "shape") else 0
                        sharp = _quality_score(crop)
                        score = float(area) * 0.001 + float(sharp)
                        pid_dir = os.path.join(crops_dir, pid)
                        if pid not in saved:
                            _safe_mkdir(pid_dir)
                            saved[pid] = []
                            kept_people.append(pid)
                        keep_list = saved[pid]
                        fname = f"{pid}_{frame_idx:06d}_{_sec_to_ts(float(t)).replace(':','-').replace(',','.')}.jpg"
                        out_path = os.path.join(pid_dir, fname)
                        if len(keep_list) < int(max_images_per_person):
                            ok = False
                            try:
                                ok = bool(cv2.imwrite(out_path, crop))  # type: ignore[attr-defined]
                            except Exception:
                                ok = False
                            if not ok:
                                continue
                            keep_list.append(
                                _SavedFace(
                                    person_id=pid,
                                    path=out_path,
                                    time_sec=float(t),
                                    bbox=[int(v) for v in (bbox or [0, 0, 0, 0])],
                                    area=int(area),
                                    sharpness=float(sharp),
                                    score=float(score),
                                )
                            )
                            continue
                        worst_idx = -1
                        worst_score = float("inf")
                        for i, it in enumerate(keep_list):
                            if float(it.score) < worst_score:
                                worst_score = float(it.score)
                                worst_idx = i
                        if worst_idx < 0 or float(score) <= float(worst_score):
                            continue
                        ok = False
                        try:
                            ok = bool(cv2.imwrite(out_path, crop))  # type: ignore[attr-defined]
                        except Exception:
                            ok = False
                        if not ok:
                            continue
                        old = keep_list[worst_idx]
                        try:
                            if old.path and os.path.exists(old.path):
                                os.remove(old.path)
                        except Exception:
                            pass
                        keep_list[worst_idx] = _SavedFace(
                            person_id=pid,
                            path=out_path,
                            time_sec=float(t),
                            bbox=[int(v) for v in (bbox or [0, 0, 0, 0])],
                            area=int(area),
                            sharpness=float(sharp),
                            score=float(score),
                        )
            finally:
                cap.release()
    else:
        logger.info("Sampling frames with stride=%d (fps=%.2f, sample_sec=%.2f)", stride, fps, sample_sec)
        for t, frame in read_video_frames(video_path, frame_stride=stride):
            frame_idx += 1
            vision = extract_face_vision_on_frame(
                frame,
                assigner,
                max_faces=int(max_faces_per_frame),
                min_face_area=int(min_face_area),
            )
            faces = vision.get("faces") or []
            for f in faces:
                pid = f.get("person_id")
                bbox = f.get("bbox")
                if not isinstance(pid, str) or not pid:
                    continue
                if allow is not None and pid not in allow:
                    continue
                if max_people > 0 and pid not in saved and len(saved) >= int(max_people):
                    continue
                seen_counts[pid] = int(seen_counts.get(pid, 0)) + 1
                first_seen[pid] = min(float(first_seen.get(pid, t) or t), float(t))
                last_seen[pid] = max(float(last_seen.get(pid, t) or t), float(t))
                if not include_images:
                    if pid not in saved:
                        saved[pid] = []
                        kept_people.append(pid)
                    continue
                crop = _safe_crop(frame, bbox if isinstance(bbox, list) else [])
                if crop is None:
                    continue
                area = int(crop.shape[0] * crop.shape[1]) if hasattr(crop, "shape") else 0
                sharp = _quality_score(crop)
                score = float(area) * 0.001 + float(sharp)
                pid_dir = os.path.join(crops_dir, pid)
                if pid not in saved:
                    _safe_mkdir(pid_dir)
                    saved[pid] = []
                    kept_people.append(pid)
                keep_list = saved[pid]
                fname = f"{pid}_{frame_idx:06d}_{_sec_to_ts(float(t)).replace(':','-').replace(',','.')}.jpg"
                out_path = os.path.join(pid_dir, fname)
                if len(keep_list) < int(max_images_per_person):
                    ok = False
                    try:
                        ok = bool(cv2.imwrite(out_path, crop))  # type: ignore[attr-defined]
                    except Exception:
                        ok = False
                    if not ok:
                        continue
                    keep_list.append(
                        _SavedFace(
                            person_id=pid,
                            path=out_path,
                            time_sec=float(t),
                            bbox=[int(v) for v in (bbox or [0, 0, 0, 0])],
                            area=int(area),
                            sharpness=float(sharp),
                            score=float(score),
                        )
                    )
                    continue
                worst_idx = -1
                worst_score = float("inf")
                for i, it in enumerate(keep_list):
                    if float(it.score) < worst_score:
                        worst_score = float(it.score)
                        worst_idx = i
                if worst_idx < 0 or float(score) <= float(worst_score):
                    continue
                ok = False
                try:
                    ok = bool(cv2.imwrite(out_path, crop))  # type: ignore[attr-defined]
                except Exception:
                    ok = False
                if not ok:
                    continue
                old = keep_list[worst_idx]
                try:
                    if old.path and os.path.exists(old.path):
                        os.remove(old.path)
                except Exception:
                    pass
                keep_list[worst_idx] = _SavedFace(
                    person_id=pid,
                    path=out_path,
                    time_sec=float(t),
                    bbox=[int(v) for v in (bbox or [0, 0, 0, 0])],
                    area=int(area),
                    sharpness=float(sharp),
                    score=float(score),
                )

    people: List[Dict[str, Any]] = []
    if not names_path:
        names_path = os.path.join(out_dir, "people_names.json")
    person_ids = sorted(saved.keys())
    names_map = _write_names_template(names_path, person_ids)
    for pid in person_ids:
        name = names_map.get(pid, "").strip()
        if not include_images:
            people.append(
                {
                    "person_id": pid,
                    "name": name,
                    "name_is_hint": True,
                    "events": int(seen_counts.get(pid, 0)),
                    "first_seen": _sec_to_ts(float(first_seen.get(pid, 0.0) or 0.0)),
                    "last_seen": _sec_to_ts(float(last_seen.get(pid, 0.0) or 0.0)),
                }
            )
            continue
        items = saved.get(pid) or []
        items_sorted = sorted(items, key=lambda x: float(x.score), reverse=True)
        img_paths = [it.path for it in items_sorted if it.path and os.path.exists(it.path)]
        sheet_path = os.path.join(sheets_dir, f"{pid}.jpg")
        _write_contact_sheet(img_paths[: int(max_images_per_person)], sheet_path)
        people.append(
            {
                "person_id": pid,
                "name": name,
                "name_is_hint": True,
                "events": int(seen_counts.get(pid, 0)),
                "first_seen": _sec_to_ts(float(first_seen.get(pid, 0.0) or 0.0)),
                "last_seen": _sec_to_ts(float(last_seen.get(pid, 0.0) or 0.0)),
                "sheet": os.path.abspath(sheet_path) if os.path.exists(sheet_path) else None,
                "images": [
                    {
                        "path": os.path.abspath(it.path),
                        "time": _sec_to_ts(float(it.time_sec)),
                        "bbox": it.bbox,
                        "area": int(it.area),
                        "sharpness": float(it.sharpness),
                        "score": float(it.score),
                    }
                    for it in items_sorted
                    if it.path and os.path.exists(it.path)
                ],
            }
        )

    out_json = {
        "video": os.path.abspath(video_path),
        "out_dir": os.path.abspath(out_dir),
        "names_file": os.path.abspath(names_path) if names_path else None,
        "names_hint_note": "people_names.json 提供 person_id -> name 的人工映射，仅供参考；极少数情况下 person_id 可能在不同时间段对应到其他人，LLM 可将 name 作为弱约束提示而非强事实。",
        "sample_sec": float(sample_sec),
        "stride_frames": int(stride),
        "min_face_area": int(min_face_area),
        "max_faces_per_frame": int(max_faces_per_frame),
        "max_images_per_person": int(max_images_per_person) if include_images else 0,
        "include_images": bool(include_images),
        "people": people,
    }
    with open(os.path.join(out_dir, "people.json"), "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    return out_json


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a face-based people library (pXX) from a video.")
    p.add_argument("--video", help="Input video path")
    p.add_argument("--out", help="Output directory (default: <cwd>/people_library)")
    p.add_argument("--sample-sec", type=float, default=3.0)
    p.add_argument("--max-faces", type=int, default=5)
    p.add_argument("--min-face-area", type=int, default=40 * 40)
    p.add_argument("--max-images-per-person", type=int, default=30)
    p.add_argument("--top-people", type=int, default=0)
    p.add_argument("--full", action="store_true", help="Include images/sheets and detailed fields in people.json")
    p.add_argument("--names", help="Path to people_names.json (default: <out>/people_names.json)")
    p.add_argument("--transcript", help="Optional transcript_for_llm.txt to restrict people ids")
    p.add_argument("--verbose", action="store_true")
    return p


def main(argv: Any = None) -> None:
    args = build_arg_parser().parse_args(argv)
    setup_logging(bool(args.verbose))

    video_path = str(args.video or "").strip()
    if not video_path:
        logger.error("--video is required.")
        raise SystemExit(2)

    out_dir = str(args.out or "").strip()
    if not out_dir:
        out_dir = os.path.join(os.getcwd(), "people_library")

    only_people: Optional[List[str]] = None
    transcript_events: Optional[List[Tuple[float, int, List[str]]]] = None
    transcript_counts: Optional[Dict[str, int]] = None
    transcript_first: Optional[Dict[str, float]] = None
    transcript_last: Optional[Dict[str, float]] = None
    transcript_path = str(args.transcript or "").strip()
    if transcript_path:
        parsed = _parse_people_from_transcript(transcript_path)
        people_counts = parsed.get("people_counts") or {}
        transcript_events = parsed.get("events") or []
        transcript_counts = people_counts if isinstance(people_counts, dict) else None
        transcript_first = parsed.get("first_seen") or None
        transcript_last = parsed.get("last_seen") or None
        if isinstance(people_counts, dict) and people_counts:
            items = sorted(people_counts.items(), key=lambda kv: int(kv[1]), reverse=True)
            top_n = int(args.top_people or 0)
            if top_n > 0:
                only_people = [str(k) for k, _ in items[:top_n]]
            else:
                only_people = [str(k) for k, _ in items]
            logger.info("Loaded %d people ids from transcript: %s", len(only_people), transcript_path)

    names_path = str(getattr(args, "names", "") or "").strip()
    if not names_path:
        names_path = os.path.join(out_dir, "people_names.json")

    build_people_library(
        video_path=video_path,
        out_dir=out_dir,
        sample_sec=float(args.sample_sec),
        max_faces_per_frame=int(args.max_faces),
        min_face_area=int(args.min_face_area),
        max_images_per_person=int(args.max_images_per_person),
        only_people=only_people,
        max_people=int(args.top_people or 0),
        transcript_events=transcript_events,
        transcript_counts=transcript_counts,
        transcript_first=transcript_first,
        transcript_last=transcript_last,
        include_images=bool(getattr(args, "full", False)),
        names_path=names_path,
    )
    logger.info("People library written to %s", out_dir)


if __name__ == "__main__":
    main()
