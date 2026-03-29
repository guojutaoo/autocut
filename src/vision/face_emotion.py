"""Vision-side analysis: face / emotion detection and simple visual peaks.

This module is designed to degrade gracefully when heavy CV libraries or
pretrained models (e.g. deepface / fer) are not available. In the worst case
it falls back to a simple per-frame contrast-based "intensity" score.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import urllib.request
from typing import Any, Dict, List

from ..ingestion.ingestor import read_video_frames

logger = logging.getLogger(__name__)
_HAAR_FACE_DETECTORS: List[Any] | None = None
_YUNET_DETECTORS: Dict[tuple[int, int], Any] = {}
_DNN_FACE_NET: Any = None
_INSIGHTFACE_APP: Any = None

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

try:  # Optional heavy dependency
    from insightface.app import FaceAnalysis  # type: ignore

    HAS_INSIGHTFACE = True
except Exception:  # pragma: no cover - optional path
    FaceAnalysis = None  # type: ignore
    HAS_INSIGHTFACE = False

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


def _get_haar_face_detectors() -> List[Any]:
    if not HAS_OPENCV_NUMPY:
        return []
    global _HAAR_FACE_DETECTORS
    try:
        cached = _HAAR_FACE_DETECTORS  # type: ignore[name-defined]
    except Exception:
        cached = None
    if cached is not None:
        return cached
    try:
        cascade_path = getattr(cv2.data, "haarcascades", "")  # type: ignore[attr-defined]
        if not cascade_path:
            return []
        files = [
            "haarcascade_frontalface_default.xml",
            "haarcascade_frontalface_alt2.xml",
            "haarcascade_profileface.xml",
        ]
        dets: List[Any] = []
        for fn in files:
            path = os.path.join(cascade_path, fn)
            if not os.path.exists(path):
                continue
            det = cv2.CascadeClassifier(path)  # type: ignore[attr-defined]
            if getattr(det, "empty", lambda: True)():  # type: ignore[attr-defined]
                continue
            dets.append(det)
        _HAAR_FACE_DETECTORS = dets  # type: ignore[name-defined]
        return dets
    except Exception:
        return []


def _get_model_cache_dir() -> str:
    base = os.environ.get("AUTOCUT_MODEL_DIR") or os.path.join(
        os.path.expanduser("~"), "Library", "Caches", "autocut", "models"
    )
    os.makedirs(base, exist_ok=True)
    return base


def default_face_sim_threshold() -> float:
    try:
        v = os.environ.get("AUTOCUT_FACE_SIM_THRESH")
        if v is not None and str(v).strip() != "":
            return float(v)
    except Exception:
        pass
    return 0.60 if HAS_INSIGHTFACE else 0.92


def default_face_sim_margin() -> float:
    try:
        v = os.environ.get("AUTOCUT_FACE_SIM_MARGIN")
        if v is not None and str(v).strip() != "":
            return float(v)
    except Exception:
        pass
    return 0.05 if HAS_INSIGHTFACE else 0.0


def default_min_quality_to_update() -> float:
    try:
        v = os.environ.get("AUTOCUT_FACE_MIN_QUALITY")
        if v is not None and str(v).strip() != "":
            return float(v)
    except Exception:
        pass
    return 0.35 if HAS_INSIGHTFACE else 0.0


def _ensure_yunet_model() -> str | None:
    if not HAS_OPENCV_NUMPY:
        return None
    if not hasattr(cv2, "FaceDetectorYN"):  # type: ignore[attr-defined]
        return None
    model_dir = _get_model_cache_dir()
    model_path = os.path.join(model_dir, "face_detection_yunet_2023mar.onnx")
    if os.path.exists(model_path) and os.path.getsize(model_path) > 100_000:
        return model_path
    url = "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    try:
        os.makedirs(model_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="yunet_", suffix=".onnx", dir=model_dir)
        os.close(fd)
        urllib.request.urlretrieve(url, tmp_path)
        if os.path.getsize(tmp_path) <= 100_000:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return None
        os.replace(tmp_path, model_path)
        return model_path
    except Exception:
        return None

def _get_yunet_detector(frame_w: int, frame_h: int) -> Any:
    if not HAS_OPENCV_NUMPY:
        return None
    model_path = _ensure_yunet_model()
    if not model_path:
        return None
    key = (int(frame_w), int(frame_h))
    det = _YUNET_DETECTORS.get(key)
    if det is not None:
        return det
    try:
        det = cv2.FaceDetectorYN.create(model_path, "", (int(frame_w), int(frame_h)))  # type: ignore[attr-defined]
        _YUNET_DETECTORS[key] = det
        return det
    except Exception:
        return None

def _ensure_dnn_ssd_models() -> tuple[str, str] | None:
    if not HAS_OPENCV_NUMPY:
        return None
    if not hasattr(cv2, "dnn"):  # type: ignore[attr-defined]
        return None
    model_dir = _get_model_cache_dir()
    proto_path = os.path.join(model_dir, "deploy.prototxt")
    model_path = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")
    if os.path.exists(proto_path) and os.path.getsize(proto_path) > 1000 and os.path.exists(model_path) and os.path.getsize(model_path) > 1_000_000:
        return proto_path, model_path
    proto_url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
    model_url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/res10_300x300_ssd_iter_140000.caffemodel"
    try:
        os.makedirs(model_dir, exist_ok=True)
        if not (os.path.exists(proto_path) and os.path.getsize(proto_path) > 1000):
            fd, tmp_proto = tempfile.mkstemp(prefix="dnn_proto_", suffix=".prototxt", dir=model_dir)
            os.close(fd)
            urllib.request.urlretrieve(proto_url, tmp_proto)
            if os.path.getsize(tmp_proto) > 1000:
                os.replace(tmp_proto, proto_path)
            else:
                try:
                    os.remove(tmp_proto)
                except Exception:
                    pass
        if not (os.path.exists(model_path) and os.path.getsize(model_path) > 1_000_000):
            fd, tmp_model = tempfile.mkstemp(prefix="dnn_model_", suffix=".caffemodel", dir=model_dir)
            os.close(fd)
            urllib.request.urlretrieve(model_url, tmp_model)
            if os.path.getsize(tmp_model) > 1_000_000:
                os.replace(tmp_model, model_path)
            else:
                try:
                    os.remove(tmp_model)
                except Exception:
                    pass
        if os.path.exists(proto_path) and os.path.getsize(proto_path) > 1000 and os.path.exists(model_path) and os.path.getsize(model_path) > 1_000_000:
            return proto_path, model_path
        return None
    except Exception:
        return None


def _get_dnn_face_net() -> Any:
    if not HAS_OPENCV_NUMPY:
        return None
    global _DNN_FACE_NET
    if _DNN_FACE_NET is not None:
        return _DNN_FACE_NET
    paths = _ensure_dnn_ssd_models()
    if not paths:
        return None
    proto_path, model_path = paths
    try:
        net = cv2.dnn.readNetFromCaffe(proto_path, model_path)  # type: ignore[attr-defined]
        _DNN_FACE_NET = net
        return net
    except Exception:
        return None


def _get_insightface_app() -> Any:
    if not HAS_INSIGHTFACE:
        return None
    global _INSIGHTFACE_APP
    if _INSIGHTFACE_APP is not None:
        return _INSIGHTFACE_APP
    try:
        det_size = int(os.environ.get("AUTOCUT_FACE_DET_SIZE") or "1024")
    except Exception:
        det_size = 1024
    try:
        det_thresh = float(os.environ.get("AUTOCUT_FACE_DET_THRESH") or "0.4")
    except Exception:
        det_thresh = 0.4
    try:
        app = FaceAnalysis(allowed_modules=["detection", "recognition"], providers=["CPUExecutionProvider"])  # type: ignore[operator]
        app.prepare(ctx_id=-1, det_size=(det_size, det_size), det_thresh=det_thresh)
        _INSIGHTFACE_APP = app
        return app
    except Exception:
        return None


def _extract_face_embedding(face_bgr: Any, size: int = 64) -> Any:
    if not HAS_OPENCV_NUMPY:
        return None
    try:
        face = cv2.resize(face_bgr, (size, size))  # type: ignore[attr-defined]
        hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)  # type: ignore[attr-defined]
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])  # type: ignore[attr-defined]
        vec = hist.astype("float32").reshape(-1)
        norm = float(np.linalg.norm(vec))  # type: ignore[attr-defined]
        if norm <= 1e-6:
            return None
        return vec / norm
    except Exception:
        return None


def estimate_face_quality(face_bgr: Any, area: int, det_score: Any) -> float:
    if not HAS_OPENCV_NUMPY or face_bgr is None:
        return 0.0
    try:
        a = float(area)
    except Exception:
        a = 0.0
    area_norm = min(max(a / 40000.0, 0.0), 1.0)
    try:
        s = float(det_score) if isinstance(det_score, (int, float)) else 0.5
    except Exception:
        s = 0.5
    s = min(max(s, 0.0), 1.0)
    sharp_norm = 0.0
    try:
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]
        lap = cv2.Laplacian(gray, cv2.CV_64F)  # type: ignore[attr-defined]
        sharp = float(lap.var())
        sharp_norm = min(max(sharp / 200.0, 0.0), 1.0)
    except Exception:
        sharp_norm = 0.0
    q = 0.45 * s + 0.35 * sharp_norm + 0.20 * area_norm
    return float(min(max(q, 0.0), 1.0))


def _estimate_face_quality(face_bgr: Any, area: int, det_score: Any) -> float:
    return estimate_face_quality(face_bgr, area=area, det_score=det_score)


def dbscan_cosine(embeddings: Any, eps: float = 0.35, min_samples: int = 4) -> List[int]:
    if not HAS_OPENCV_NUMPY or embeddings is None:
        return []
    X = np.asarray(embeddings, dtype="float32")  # type: ignore[attr-defined]
    if X.ndim != 2 or X.shape[0] == 0:
        return []
    X = np.where(np.isfinite(X), X, 0.0)  # type: ignore[attr-defined]
    n = int(X.shape[0])
    norms = np.linalg.norm(X, axis=1, keepdims=True)  # type: ignore[attr-defined]
    norms = np.maximum(norms, 1e-9)  # type: ignore[attr-defined]
    Xn = X / norms
    sims = np.clip(Xn @ Xn.T, -1.0, 1.0)  # type: ignore[attr-defined]
    dists = 1.0 - sims
    adj = dists <= float(eps)

    labels = [-99] * n
    visited = [False] * n
    cluster_id = 0

    neigh_cache: List[List[int]] = []
    for i in range(n):
        neigh = np.flatnonzero(adj[i]).tolist()  # type: ignore[attr-defined]
        neigh_cache.append([int(x) for x in neigh])

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neigh = neigh_cache[i]
        if len(neigh) < int(min_samples):
            labels[i] = -1
            continue
        labels[i] = cluster_id
        in_queue = [False] * n
        queue = []
        for j in neigh:
            if j != i:
                queue.append(int(j))
                in_queue[int(j)] = True
        qpos = 0
        while qpos < len(queue):
            j = int(queue[qpos])
            qpos += 1
            if not visited[j]:
                visited[j] = True
                neigh_j = neigh_cache[j]
                if len(neigh_j) >= int(min_samples):
                    for k in neigh_j:
                        k = int(k)
                        if not in_queue[k]:
                            queue.append(k)
                            in_queue[k] = True
            if labels[j] in (-99, -1):
                labels[j] = cluster_id
        cluster_id += 1
    return labels


def _cosine_sim(a: Any, b: Any) -> float:
    if not HAS_OPENCV_NUMPY or a is None or b is None:
        return 0.0
    try:
        return float(np.dot(a, b))  # type: ignore[attr-defined]
    except Exception:
        return 0.0


class FaceIdentityAssigner:
    def __init__(
        self,
        sim_threshold: float = 0.92,
        sim_margin: float = 0.0,
        min_quality_to_update: float = 0.0,
    ):
        self.sim_threshold = float(sim_threshold)
        self.sim_margin = float(sim_margin)
        self.min_quality_to_update = float(min_quality_to_update)
        self._centroids: List[Any] = []
        self._counts: List[int] = []

    def assign(self, embedding: Any, quality: float | None = None) -> str:
        if embedding is None:
            pid = len(self._centroids) + 1
            self._centroids.append(None)
            self._counts.append(1)
            return f"p{pid:02d}"

        try:
            emb = np.asarray(embedding, dtype="float32")  # type: ignore[attr-defined]
            if emb.ndim > 1:
                emb = emb.reshape(-1)
            norm = float(np.linalg.norm(emb))  # type: ignore[attr-defined]
            if norm > 1e-6:
                emb = emb / norm
        except Exception:
            emb = embedding

        thr = self.sim_threshold
        try:
            env_thr = os.environ.get("AUTOCUT_FACE_SIM_THRESH", "").strip() or os.environ.get("AUTOCUT_FACE_SIM_THRESHOLD", "").strip()
            if env_thr:
                thr = float(env_thr)
        except Exception:
            pass

        best_idx = -1
        best_sim = -1.0
        second_sim = -1.0
        for i, c in enumerate(self._centroids):
            if c is None:
                continue
            s = _cosine_sim(emb, c)
            if s > best_sim:
                second_sim = best_sim
                best_sim = s
                best_idx = i
            elif s > second_sim:
                second_sim = s

        if best_idx >= 0 and best_sim >= thr and (best_sim - second_sim) >= self.sim_margin:
            n = self._counts[best_idx]
            c = self._centroids[best_idx]
            do_update = True
            if quality is not None and quality < self.min_quality_to_update:
                do_update = False
            if do_update:
                new_c = (c * n + emb) / float(n + 1)
                norm = float(np.linalg.norm(new_c))  # type: ignore[attr-defined]
                if norm > 1e-6:
                    new_c = new_c / norm
                self._centroids[best_idx] = new_c
                self._counts[best_idx] = n + 1
            return f"p{best_idx + 1:02d}"

        pid = len(self._centroids) + 1
        self._centroids.append(emb)
        self._counts.append(1)
        return f"p{pid:02d}"


def detect_faces_on_frame(frame: Any, max_faces: int = 5) -> List[Dict[str, Any]]:
    if not HAS_OPENCV_NUMPY:
        return []
    try:
        h_img, w_img = frame.shape[:2]
        app = _get_insightface_app()
        if app is not None:
            faces = app.get(frame) or []
            results: List[Dict[str, Any]] = []
            for f in faces:
                try:
                    bbox = getattr(f, "bbox", None)
                    if bbox is None:
                        continue
                    x0, y0, x1, y1 = [int(v) for v in bbox[:4]]
                    x0 = max(0, min(x0, w_img - 1))
                    y0 = max(0, min(y0, h_img - 1))
                    x1 = max(0, min(x1, w_img))
                    y1 = max(0, min(y1, h_img))
                    if x1 <= x0 or y1 <= y0:
                        continue
                    score = getattr(f, "det_score", None)
                    emb = getattr(f, "embedding", None)
                except Exception:
                    continue
                results.append(
                    {
                        "bbox": [x0, y0, x1 - x0, y1 - y0],
                        "score": float(score) if isinstance(score, (int, float)) else None,
                        "backend": "retinaface",
                        "embedding": emb,
                    }
                )
            results.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
            return results[: int(max_faces)]

        det = _get_yunet_detector(w_img, h_img)
        if det is not None:
            ok, faces = det.detect(frame)  # type: ignore[assignment]
            results: List[Dict[str, Any]] = []
            if ok is None:
                ok = False
            if faces is None:
                faces = []
            for row in faces:
                try:
                    x, y, w, h = [int(v) for v in row[:4]]
                    score = float(row[4]) if len(row) > 4 else 0.0
                except Exception:
                    continue
                results.append({"bbox": [x, y, w, h], "score": score, "backend": "yunet"})
            results.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
            return results[: int(max_faces)]

        net = _get_dnn_face_net()
        if net is not None:
            blob = cv2.dnn.blobFromImage(  # type: ignore[attr-defined]
                cv2.resize(frame, (300, 300)),  # type: ignore[attr-defined]
                1.0,
                (300, 300),
                (104.0, 177.0, 123.0),
                swapRB=False,
                crop=False,
            )
            net.setInput(blob)
            dets = net.forward()
            results: List[Dict[str, Any]] = []
            try:
                num = int(dets.shape[2])
            except Exception:
                num = 0
            for i in range(num):
                try:
                    conf = float(dets[0, 0, i, 2])
                except Exception:
                    continue
                if conf < 0.6:
                    continue
                try:
                    x0 = int(dets[0, 0, i, 3] * w_img)
                    y0 = int(dets[0, 0, i, 4] * h_img)
                    x1 = int(dets[0, 0, i, 5] * w_img)
                    y1 = int(dets[0, 0, i, 6] * h_img)
                except Exception:
                    continue
                x0 = max(0, min(x0, w_img - 1))
                y0 = max(0, min(y0, h_img - 1))
                x1 = max(0, min(x1, w_img))
                y1 = max(0, min(y1, h_img))
                if x1 <= x0 or y1 <= y0:
                    continue
                results.append({"bbox": [x0, y0, x1 - x0, y1 - y0], "score": conf, "backend": "dnn_ssd"})
            results.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
            return results[: int(max_faces)]

        dets = _get_haar_face_detectors()
        if not dets:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]
        results: List[Dict[str, Any]] = []
        for det in dets:
            faces = det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))  # type: ignore[attr-defined]
            for (x, y, w, h) in faces:
                results.append({"bbox": [int(x), int(y), int(w), int(h)], "score": None, "backend": "haar_ensemble"})
        if any(getattr(d, "__class__", object()).__name__ == "CascadeClassifier" for d in dets):
            try:
                profile_det = dets[-1]
                flipped = cv2.flip(gray, 1)  # type: ignore[attr-defined]
                faces = profile_det.detectMultiScale(flipped, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))  # type: ignore[attr-defined]
                w_img = gray.shape[1]
                for (x, y, w, h) in faces:
                    x0 = w_img - int(x) - int(w)
                    results.append({"bbox": [int(x0), int(y), int(w), int(h)], "score": None, "backend": "haar_ensemble"})
            except Exception:
                pass
        results = _nms_faces(results, iou_threshold=0.35)
        results.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
        return results[: int(max_faces)]
    except Exception:
        return []


def _nms_faces(faces: List[Dict[str, Any]], iou_threshold: float = 0.35) -> List[Dict[str, Any]]:
    if not HAS_OPENCV_NUMPY or not faces:
        return faces
    boxes = []
    scores = []
    for f in faces:
        bbox = f.get("bbox") or []
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        x, y, w, h = [float(v) for v in bbox]
        boxes.append([x, y, x + w, y + h])
        s = f.get("score")
        scores.append(float(s) if isinstance(s, (int, float)) else float(w * h))
    if not boxes:
        return []
    boxes_np = np.array(boxes, dtype="float32")  # type: ignore[attr-defined]
    scores_np = np.array(scores, dtype="float32")  # type: ignore[attr-defined]
    order = scores_np.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(boxes_np[i, 0], boxes_np[order[1:], 0])  # type: ignore[attr-defined]
        yy1 = np.maximum(boxes_np[i, 1], boxes_np[order[1:], 1])  # type: ignore[attr-defined]
        xx2 = np.minimum(boxes_np[i, 2], boxes_np[order[1:], 2])  # type: ignore[attr-defined]
        yy2 = np.minimum(boxes_np[i, 3], boxes_np[order[1:], 3])  # type: ignore[attr-defined]
        w = np.maximum(0.0, xx2 - xx1)  # type: ignore[attr-defined]
        h = np.maximum(0.0, yy2 - yy1)  # type: ignore[attr-defined]
        inter = w * h
        area_i = (boxes_np[i, 2] - boxes_np[i, 0]) * (boxes_np[i, 3] - boxes_np[i, 1])
        area_o = (boxes_np[order[1:], 2] - boxes_np[order[1:], 0]) * (boxes_np[order[1:], 3] - boxes_np[order[1:], 1])
        iou = inter / (area_i + area_o - inter + 1e-6)
        inds = np.where(iou <= float(iou_threshold))[0]  # type: ignore[attr-defined]
        order = order[inds + 1]
    out = []
    for idx in keep:
        out.append(faces[idx])
    return out


def extract_face_vision_at_time(
    cap: Any,
    t_sec: float,
    assigner: FaceIdentityAssigner,
    max_faces: int = 5,
    min_face_area: int = 40 * 40,
    debug_out_dir: str | None = None,
    debug_prefix: str = "frame",
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

        out_faces: List[Dict[str, Any]] = []
        for f in faces:
            x, y, w, h = f["bbox"]
            area = int(w) * int(h)
            if area < int(min_face_area):
                continue
            crop = frame[y : y + h, x : x + w]
            emb = f.get("embedding")
            if emb is None:
                emb = _extract_face_embedding(crop)
            q = _estimate_face_quality(crop, area=area, det_score=f.get("score"))
            pid = assigner.assign(emb, quality=q)
            out_faces.append({"bbox": f["bbox"], "person_id": pid, "score": f.get("score"), "backend": f.get("backend"), "quality": q})

        out_faces.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
        if debug_out_dir and out_faces:
            _dump_face_debug_images(
                frame=frame,
                faces=out_faces,
                out_dir=debug_out_dir,
                prefix=debug_prefix,
                t_sec=float(t_sec),
            )
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
    debug_out_dir: str | None = None,
    debug_prefix: str = "frame",
    t_sec: float | None = None,
) -> Dict[str, Any]:
    if (not HAS_OPENCV_NUMPY) or frame is None:
        return {"faces": [], "face_count": 0, "people_in_shot": []}
    try:
        faces = detect_faces_on_frame(frame, max_faces=max_faces)
        if not faces:
            return {"faces": [], "face_count": 0, "people_in_shot": []}
        out_faces: List[Dict[str, Any]] = []
        for f in faces:
            x, y, w, h = f["bbox"]
            area = int(w) * int(h)
            if area < int(min_face_area):
                continue
            crop = frame[y : y + h, x : x + w]
            emb = f.get("embedding")
            if emb is None:
                emb = _extract_face_embedding(crop)
            q = _estimate_face_quality(crop, area=area, det_score=f.get("score"))
            pid = assigner.assign(emb, quality=q)
            out_faces.append({"bbox": f["bbox"], "person_id": pid, "score": f.get("score"), "backend": f.get("backend"), "quality": q})
        out_faces.sort(key=lambda d: d["bbox"][2] * d["bbox"][3], reverse=True)
        if debug_out_dir and out_faces:
            _dump_face_debug_images(
                frame=frame,
                faces=out_faces,
                out_dir=debug_out_dir,
                prefix=debug_prefix,
                t_sec=float(t_sec) if t_sec is not None else None,
            )
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


def _dump_face_debug_images(
    frame: Any,
    faces: List[Dict[str, Any]],
    out_dir: str,
    prefix: str,
    t_sec: float | None,
) -> None:
    if not HAS_OPENCV_NUMPY or frame is None or not faces:
        return
    try:
        os.makedirs(out_dir, exist_ok=True)
        stamp = "na" if t_sec is None else f"{t_sec:010.3f}".replace(".", "_")
        frame_name = f"{prefix}_frame_{stamp}.jpg"
        frame_path = os.path.join(out_dir, frame_name)
        canvas = frame.copy()
        h_img, w_img = canvas.shape[:2]
        for i, f in enumerate(faces):
            bbox = f.get("bbox") or []
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            x, y, w, h = [int(v) for v in bbox]
            x0 = max(0, min(x, w_img - 1))
            y0 = max(0, min(y, h_img - 1))
            x1 = max(0, min(x + w, w_img))
            y1 = max(0, min(y + h, h_img))
            if x1 <= x0 or y1 <= y0:
                continue
            pid = str(f.get("person_id") or "")
            score = f.get("score")
            quality = f.get("quality")
            cv2.rectangle(canvas, (x0, y0), (x1, y1), (0, 255, 0), 2)  # type: ignore[attr-defined]
            label = pid
            if isinstance(score, (int, float)):
                label = f"{label} {float(score):.2f}".strip()
            if isinstance(quality, (int, float)):
                label = f"{label} q={float(quality):.2f}".strip()
            if label:
                cv2.putText(  # type: ignore[attr-defined]
                    canvas,
                    label,
                    (x0, max(0, y0 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,  # type: ignore[attr-defined]
                    0.6,
                    (0, 255, 0),
                    2,
                )
            crop = frame[y0:y1, x0:x1]
            face_name = f"{prefix}_face_{stamp}_{pid or 'p??'}_{i:02d}.jpg"
            face_path = os.path.join(out_dir, face_name)
            cv2.imwrite(face_path, crop)  # type: ignore[attr-defined]
            idx_path = os.path.join(out_dir, "index.jsonl")
            rec = {
                "t_sec": t_sec,
                "prefix": prefix,
                "frame_path": frame_path,
                "face_path": face_path,
                "person_id": pid,
                "score": score,
                "quality": quality,
                "backend": f.get("backend"),
                "bbox": [x0, y0, x1 - x0, y1 - y0],
            }
            with open(idx_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        cv2.imwrite(frame_path, canvas)  # type: ignore[attr-defined]
    except Exception:
        return
