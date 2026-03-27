"""Vision-side analysis: face / emotion detection and simple visual peaks.

This module is designed to degrade gracefully when heavy CV libraries or
pretrained models (e.g. deepface / fer) are not available. In the worst case
it falls back to a simple per-frame contrast-based "intensity" score.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..ingestion.ingestor import read_video_frames

logger = logging.getLogger(__name__)
_HAAR_FACE_DETECTOR = None

try:  # Optional heavy dependency
    from deepface import DeepFace  # type: ignore

    HAS_DEEPFACE = True
except Exception:  # pragma: no cover - optional path
    DeepFace = None  # type: ignore
    HAS_DEEPFACE = False

try:  # Optional dependency
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    HAS_OPENCV_NUMPY = True
except Exception:  # pragma: no cover - optional path
    cv2 = None  # type: ignore
    np = None  # type: ignore
    HAS_OPENCV_NUMPY = False


class VisionAnalyzer:
    """Analyze video frames to produce vision events.

    Events are simple dictionaries with keys:

    - ``time``: time in seconds (float)
    - ``type``: e.g. ``"vision_emotion_angry"`` or ``"vision_intensity_peak"``
    - ``modality``: always ``"vision"`` here
    - ``score``: confidence / intensity in ``[0, 1]``
    - ``details``: backend-specific extra information
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.frame_stride: int = int(self.config.get("frame_stride", 10))
        self.emotion_threshold: float = float(self.config.get("emotion_threshold", 0.6))
        self.intensity_threshold: float = float(self.config.get("intensity_threshold", 0.2))
        self.use_deepface: bool = bool(self.config.get("use_deepface", False))

        if self.use_deepface and not HAS_DEEPFACE:
            logger.warning("DeepFace requested in config but not installed. Falling back to placeholder analyzer.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(self, video_path: str) -> List[Dict[str, Any]]:
        """Run vision analysis on a video and return a list of events."""
        events: List[Dict[str, Any]] = []

        if self.use_deepface and HAS_DEEPFACE:
            events.extend(self._analyze_with_deepface(video_path))
        else:
            events.extend(self._analyze_with_placeholder(video_path))

        logger.info("VisionAnalyzer produced %d events", len(events))
        return events

    # ------------------------------------------------------------------
    # Implementations
    # ------------------------------------------------------------------
    def _analyze_with_deepface(self, video_path: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not HAS_OPENCV_NUMPY:
            logger.warning("OpenCV or NumPy missing, cannot run DeepFace analysis. Falling back to placeholder.")
            return self._analyze_with_placeholder(video_path)

        for ts, frame in read_video_frames(video_path, frame_stride=self.frame_stride):
            try:
                result = DeepFace.analyze(  # type: ignore[operator]
                    frame,
                    actions=["emotion"],
                    enforce_detection=False,
                    prog_bar=False,
                )
            except Exception as exc:  # pragma: no cover - model issues
                logger.debug("DeepFace analyze failed at %.3fs: %s", ts, exc)
                continue

            if not result:
                continue

            # DeepFace may return a list or dict depending on version
            r = result[0] if isinstance(result, list) else result
            dom = r.get("dominant_emotion")
            emotions = r.get("emotion") or {}
            score = float(emotions.get(dom, 0.0)) if dom else 0.0

            if dom and score >= self.emotion_threshold:
                events.append(
                    {
                        "time": float(ts),
                        "type": f"vision_emotion_{dom}",
                        "modality": "vision",
                        "score": min(score / 100.0, 1.0),  # DeepFace scores are often 0-100
                        "details": {
                            "backend": "deepface",
                            "raw_emotions": emotions,
                        },
                    }
                )

        return events

    def _analyze_with_placeholder(self, video_path: str) -> List[Dict[str, Any]]:
        """Fallback analysis based on simple frame contrast.

        This does not require any external CV model and is guaranteed to run
        as long as OpenCV + NumPy are available. Frames with high contrast
        are treated as "intense" and used as weak vision cues.
        """
        events: List[Dict[str, Any]] = []
        if not HAS_OPENCV_NUMPY:
            logger.warning("OpenCV / NumPy unavailable, skipping vision analysis.")
            return events

        for ts, frame in read_video_frames(video_path, frame_stride=self.frame_stride):
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]
            # Standard deviation as a rough contrast proxy
            std = float(gray.std())
            score = min(std / 64.0, 1.0)  # heuristic scaling
            if score >= self.intensity_threshold:
                events.append(
                    {
                        "time": float(ts),
                        "type": "vision_intensity_peak",
                        "modality": "vision",
                        "score": score,
                        "details": {
                            "std": std,
                        },
                    }
                )

        return events


def _get_haar_face_detector() -> Any:
    if not HAS_OPENCV_NUMPY:
        return None
    global _HAAR_FACE_DETECTOR
    try:
        cached = _HAAR_FACE_DETECTOR  # type: ignore[name-defined]
    except Exception:
        cached = None
    if cached is not None:
        return cached
    try:
        cascade_path = getattr(cv2.data, "haarcascades", "")  # type: ignore[attr-defined]
        if not cascade_path:
            return None
        detector = cv2.CascadeClassifier(cascade_path + "haarcascade_frontalface_default.xml")  # type: ignore[attr-defined]
        if detector.empty():  # type: ignore[attr-defined]
            return None
        _HAAR_FACE_DETECTOR = detector  # type: ignore[name-defined]
        return detector
    except Exception:
        return None


def _extract_face_embedding(gray_face: Any, size: int = 64) -> Any:
    if not HAS_OPENCV_NUMPY:
        return None
    try:
        face = cv2.resize(gray_face, (size, size))  # type: ignore[attr-defined]
        vec = face.astype("float32").reshape(-1)
        norm = float(np.linalg.norm(vec))  # type: ignore[attr-defined]
        if norm <= 1e-6:
            return None
        return vec / norm
    except Exception:
        return None


def _cosine_sim(a: Any, b: Any) -> float:
    if not HAS_OPENCV_NUMPY or a is None or b is None:
        return 0.0
    try:
        return float(np.dot(a, b))  # type: ignore[attr-defined]
    except Exception:
        return 0.0


class FaceIdentityAssigner:
    def __init__(self, sim_threshold: float = 0.92):
        self.sim_threshold = float(sim_threshold)
        self._centroids: List[Any] = []
        self._counts: List[int] = []

    def assign(self, embedding: Any) -> str:
        if embedding is None:
            pid = len(self._centroids) + 1
            self._centroids.append(None)
            self._counts.append(1)
            return f"p{pid:02d}"

        best_idx = -1
        best_sim = -1.0
        for i, c in enumerate(self._centroids):
            if c is None:
                continue
            s = _cosine_sim(embedding, c)
            if s > best_sim:
                best_sim = s
                best_idx = i

        if best_idx >= 0 and best_sim >= self.sim_threshold:
            n = self._counts[best_idx]
            c = self._centroids[best_idx]
            new_c = (c * n + embedding) / float(n + 1)
            norm = float(np.linalg.norm(new_c))  # type: ignore[attr-defined]
            if norm > 1e-6:
                new_c = new_c / norm
            self._centroids[best_idx] = new_c
            self._counts[best_idx] = n + 1
            return f"p{best_idx + 1:02d}"

        pid = len(self._centroids) + 1
        self._centroids.append(embedding)
        self._counts.append(1)
        return f"p{pid:02d}"


def detect_faces_on_frame(frame: Any, max_faces: int = 5) -> List[Dict[str, Any]]:
    if not HAS_OPENCV_NUMPY:
        return []
    detector = _get_haar_face_detector()
    if detector is None:
        return []
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))  # type: ignore[attr-defined]
        results: List[Dict[str, Any]] = []
        for (x, y, w, h) in faces:
            results.append({"bbox": [int(x), int(y), int(w), int(h)]})
        results.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
        return results[: int(max_faces)]
    except Exception:
        return []


def extract_face_vision_at_time(
    cap: Any,
    t_sec: float,
    assigner: FaceIdentityAssigner,
    max_faces: int = 5,
    min_face_area: int = 40 * 40,
) -> Dict[str, Any]:
    if not HAS_OPENCV_NUMPY:
        return {"faces": [], "face_count": 0, "people_in_shot": []}
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t_sec) * 1000.0)  # type: ignore[attr-defined]
        ok, frame = cap.read()
        if not ok or frame is None:
            return {"faces": [], "face_count": 0, "people_in_shot": []}
        faces = detect_faces_on_frame(frame, max_faces=max_faces)
        if not faces:
            return {"faces": [], "face_count": 0, "people_in_shot": []}

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]
        out_faces: List[Dict[str, Any]] = []
        for f in faces:
            x, y, w, h = f["bbox"]
            area = int(w) * int(h)
            if area < int(min_face_area):
                continue
            crop = gray[y : y + h, x : x + w]
            emb = _extract_face_embedding(crop)
            pid = assigner.assign(emb)
            out_faces.append({"bbox": f["bbox"], "person_id": pid})

        out_faces.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
        people = []
        for f in out_faces:
            if f["person_id"] not in people:
                people.append(f["person_id"])
        dominant = out_faces[0]["person_id"] if out_faces else None
        return {
            "faces": out_faces,
            "face_count": len(out_faces),
            "people_in_shot": people,
            "dominant_person_id": dominant,
        }
    except Exception:
        return {"faces": [], "face_count": 0, "people_in_shot": []}


def extract_face_vision_on_frame(
    frame: Any,
    assigner: FaceIdentityAssigner,
    max_faces: int = 5,
    min_face_area: int = 40 * 40,
) -> Dict[str, Any]:
    if not HAS_OPENCV_NUMPY or frame is None:
        return {"faces": [], "face_count": 0, "people_in_shot": []}
    try:
        faces = detect_faces_on_frame(frame, max_faces=max_faces)
        if not faces:
            return {"faces": [], "face_count": 0, "people_in_shot": []}
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]
        out_faces: List[Dict[str, Any]] = []
        for f in faces:
            x, y, w, h = f["bbox"]
            area = int(w) * int(h)
            if area < int(min_face_area):
                continue
            crop = gray[y : y + h, x : x + w]
            emb = _extract_face_embedding(crop)
            pid = assigner.assign(emb)
            out_faces.append({"bbox": f["bbox"], "person_id": pid})
        out_faces.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
        people: List[str] = []
        for f in out_faces:
            pid = f.get("person_id")
            if isinstance(pid, str) and pid and pid not in people:
                people.append(pid)
        dominant = out_faces[0]["person_id"] if out_faces else None
        return {
            "faces": out_faces,
            "face_count": len(out_faces),
            "people_in_shot": people,
            "dominant_person_id": dominant,
        }
    except Exception:
        return {"faces": [], "face_count": 0, "people_in_shot": []}
