"""
FFmpeg-based video composition and rendering.
"""
from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import wave
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore

try:
    from ..freeze_effects import FreezeEffectEngine, load_effect_preset
except ImportError:
    FreezeEffectEngine = None  # type: ignore
    load_effect_preset = None  # type: ignore


logger = logging.getLogger(__name__)

def _resolve_ffmpeg_exe() -> str:
    env = os.environ.get("AUTOCUT_FFMPEG")
    if env and os.path.exists(env):
        return env
    imageio_path = "/Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
    if os.path.exists(imageio_path):
        return imageio_path
    which = shutil.which("ffmpeg")
    return which or "ffmpeg"


def _resolve_ffprobe_exe() -> str:
    env = os.environ.get("AUTOCUT_FFPROBE")
    if env and os.path.exists(env):
        return env
    ffmpeg_exe = _resolve_ffmpeg_exe()
    if os.path.basename(ffmpeg_exe).startswith("ffmpeg-"):
        candidate = os.path.join(os.path.dirname(ffmpeg_exe), os.path.basename(ffmpeg_exe).replace("ffmpeg-", "ffprobe-", 1))
        if os.path.exists(candidate):
            return candidate
    which = shutil.which("ffprobe")
    return which or "ffprobe"


def _run_capture(cmd: Sequence[str]) -> subprocess.CompletedProcess:
    cmd_list = list(cmd)
    if cmd_list and cmd_list[0] == "ffmpeg":
        cmd_list[0] = _resolve_ffmpeg_exe()
    elif cmd_list and cmd_list[0] == "ffprobe":
        cmd_list[0] = _resolve_ffprobe_exe()
    return subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)


@dataclass
class ComposeResult:
    """Result of a composition attempt.

    Attributes:
        out_dir: Output directory used for artifacts.
        ffmpeg_available: Whether ffmpeg was detected and used.
        output_video: Path to the generated ``compose.mp4`` if any.
        plan_path: Path to the JSON compose plan.
    """

    out_dir: str
    ffmpeg_available: bool
    output_video: Optional[str]
    plan_path: str


def _has_ffmpeg() -> bool:
    """Return ``True`` if the ``ffmpeg`` binary is available on PATH."""
    exe = _resolve_ffmpeg_exe()
    if os.path.isabs(exe):
        return os.path.exists(exe)
    return shutil.which(exe) is not None


def _has_drawtext() -> bool:
    """Return ``True`` if the ``drawtext`` filter is available in ffmpeg."""
    if not _has_ffmpeg():
        return False
    try:
        proc = _run_capture(["ffmpeg", "-filters"])
        out = proc.stdout.decode("utf-8", errors="ignore")
        return " drawtext " in out
    except Exception:
        return False


def _clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp ``value`` into the inclusive range [``min_value``, ``max_value``]."""

    return max(min_value, min(max_value, value))


def _get_video_resolution(path: str) -> tuple[int, int]:
    """Return (width, height) of a video file via ffprobe."""
    if not _has_ffmpeg():
        return 1080, 1920
    ffprobe_cmd = _resolve_ffprobe_exe()
    if os.path.isabs(ffprobe_cmd) and not os.path.exists(ffprobe_cmd):
        return 1080, 1920
    if not os.path.isabs(ffprobe_cmd) and shutil.which(ffprobe_cmd) is None:
        return 1080, 1920
    try:
        cmd = [
            ffprobe_cmd,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            parts = result.stdout.strip().split("x")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except Exception as exc:
        logger.warning("Failed to read video resolution for %s: %s", path, exc)
    return 1080, 1920


def _get_video_fps(path: str) -> float:
    if not _has_ffmpeg():
        return 30.0
    ffprobe_cmd = _resolve_ffprobe_exe()
    if os.path.isabs(ffprobe_cmd) and not os.path.exists(ffprobe_cmd):
        return 30.0
    if not os.path.isabs(ffprobe_cmd) and shutil.which(ffprobe_cmd) is None:
        return 30.0
    try:
        cmd = [
            ffprobe_cmd,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        rate = (proc.stdout or "").strip()
        if not rate:
            return 30.0
        if "/" in rate:
            num_s, den_s = rate.split("/", 1)
            num = float(num_s)
            den = float(den_s)
            if den > 0:
                fps = num / den
            else:
                fps = 30.0
        else:
            fps = float(rate)
        if fps <= 1.0 or fps > 240.0:
            return 30.0
        return fps
    except Exception:
        return 30.0


def _get_video_duration(path: str) -> float:
    """Return total duration of a video file in seconds via ffprobe."""
    if not _has_ffmpeg():
        return 0.0
    ffprobe_cmd = _resolve_ffprobe_exe()
    if os.path.isabs(ffprobe_cmd) and not os.path.exists(ffprobe_cmd):
        return 0.0
    if not os.path.isabs(ffprobe_cmd) and shutil.which(ffprobe_cmd) is None:
        return 0.0
    try:
        cmd = [
            ffprobe_cmd,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as exc:
        logger.warning("Failed to read video duration for %s: %s", path, exc)
    return 0.0


def _get_wav_duration_sec(path: Optional[str]) -> Optional[float]:
    """Return duration (in seconds) of a WAV file, or ``None``.

    This first tries the built-in :mod:`wave` module. If that fails, it
    falls back to ``ffprobe`` if available.
    """

    if not path or not os.path.exists(path):
        return None

    # 1. Try wave module (fastest, no subprocess)
    if path.lower().endswith(".wav"):
        try:
            with wave.open(path, "rb") as wf:
                frames = wf.getnframes()
                framerate = wf.getframerate()
                if framerate > 0:
                    return frames / float(framerate)
        except Exception:
            pass

    if _has_ffmpeg():
        try:
            proc = _run_capture(["ffmpeg", "-i", path])
            stderr = (proc.stderr or b"").decode("utf-8", errors="ignore")
            import re

            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
            if m:
                hh = int(m.group(1))
                mm = int(m.group(2))
                ss = float(m.group(3))
                return hh * 3600.0 + mm * 60.0 + ss
        except Exception:
            pass

    # 2. Fallback to ffprobe
    if _has_ffmpeg():
        ffprobe_cmd = _resolve_ffprobe_exe()
        if not os.path.isabs(ffprobe_cmd) and shutil.which(ffprobe_cmd) is None:
            return None
        try:
            cmd = [
                ffprobe_cmd,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as exc:
            logger.warning("Failed to read duration via ffprobe for %s: %s", path, exc)

    return None


def _load_triggers(triggers_path: str) -> List[Dict[str, Any]]:
    with open(triggers_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):  # pragma: no cover - defensive
        raise ValueError("triggers.json must contain a list of trigger dicts")
    return list(data)


def _compute_total_duration(segments: Sequence[Dict[str, Any]]) -> float:
    """Compute the total planned duration (seconds) of all segments."""

    total = 0.0
    for seg in segments:
        pre = seg.get("pre", {})
        freeze = seg.get("freeze", {})
        post = seg.get("post", {})
        pre_d = float(pre.get("duration", 0.0))
        freeze_d = float(freeze.get("duration", 0.0))
        post_d = float(post.get("duration", 0.0))
        total += pre_d + freeze_d + post_d
    return total


def _build_segments(
    triggers: Sequence[Dict[str, Any]],
    target_duration_sec: float = 0.0,
    narr_dur: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Build a segment plan around each ``freeze_frame`` trigger.

    The segment construction rules are:

    * ``pre_window``: 默认 5 秒，但若触发时间距离视频开始不足 5 秒，则用可达值；
    * ``freeze_duration``: 若叙述音频时长 ``narr_dur`` 可得，则使用
      ``clamp(narr_dur + 0.3, 1.5, 60.0)``，否则为 1.5 秒；
    * ``post_window``: 默认 3 秒。

    构造完成后，将按触发时间顺序累计段落时长，直到达到
    ``target_duration_sec``（允许超出不超过 10%）。最后一段的 ``post``
    时长允许被缩短，以更贴合目标时长。当 ``target_duration_sec <= 0``
    时，视为不限定目标时长，所有触发点都会被转换为片段。
    """

    PRE_WINDOW = 5.0
    POST_WINDOW = 3.0

    if narr_dur is not None and narr_dur > 0.0:
        freeze_duration = _clamp(narr_dur + 0.3, 1.5, 60.0)
    else:
        freeze_duration = 1.5

    # 先根据规则为所有触发点构造“自然”片段
    all_segments: List[Dict[str, Any]] = []
    for idx, trig in enumerate(triggers):
        if str(trig.get("type")) != "freeze_frame":
            continue
        t = float(trig.get("time", 0.0))
        if t < 0:
            continue

        pre_start = max(0.0, t - PRE_WINDOW)
        pre_duration = max(0.0, t - pre_start)
        post_start = t
        post_duration = POST_WINDOW

        all_segments.append(
            {
                "trigger_index": idx,
                "trigger_time": t,
                "pre": {
                    "start": pre_start,
                    "duration": pre_duration,
                },
                "freeze": {
                    "time": t,
                    "duration": freeze_duration,
                },
                "post": {
                    "start": post_start,
                    "duration": post_duration,
                },
            }
        )

    if target_duration_sec <= 0 or not all_segments:
        # 不限定目标时长：直接返回所有自然片段
        return all_segments

    # 带目标时长的调度：按时间顺序累计，必要时缩短最后一段的 post
    target = float(target_duration_sec)
    allowed_max = target * 1.1

    selected: List[Dict[str, Any]] = []
    cumulative = 0.0

    for seg in all_segments:
        pre = seg["pre"]
        freeze = seg["freeze"]
        post = seg["post"]

        pre_d = float(pre["duration"])
        freeze_d = float(freeze["duration"])
        post_d = float(post["duration"])
        seg_total = pre_d + freeze_d + post_d

        if cumulative >= target:
            # 已经达到或超过目标，避免进一步拉长
            break

        # 完整加入当前片段仍未达到目标时长
        if cumulative + seg_total <= target:
            selected.append(seg)
            cumulative += seg_total
            continue

        # 如果加入完整片段会跨过目标时长，这是“最后一段”
        base = pre_d + freeze_d
        desired_post_for_target = target - cumulative - base

        final_post = post_d
        final_total = cumulative + seg_total

        if 0.0 <= desired_post_for_target <= post_d:
            # 可以通过缩短 post 精确贴合目标时长
            final_post = desired_post_for_target
            final_total = target
        else:
            # 无法精确贴合，则保证总时长不超过 target * 1.1
            if final_total > allowed_max:
                max_post_by_allowed = allowed_max - cumulative - base
                if max_post_by_allowed <= 0.0:
                    # 连最小片段都无法在 110% 内放下，直接结束调度
                    break
                final_post = min(post_d, max_post_by_allowed)
                final_total = cumulative + base + final_post

        post["duration"] = max(final_post, 0.0)
        selected.append(seg)
        cumulative = final_total
        break

    return selected


def _save_plan(plan: Dict[str, Any], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    plan_path = os.path.join(out_dir, "compose_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    return plan_path


def _run_ffmpeg(cmd: Sequence[str]) -> None:
    """Run an ffmpeg command and raise if it fails."""
    cmd_list = list(cmd)
    if cmd_list[0] == "ffmpeg":
        cmd_list[0] = _resolve_ffmpeg_exe()
    elif cmd_list[0] == "ffprobe":
        cmd_list[0] = _resolve_ffprobe_exe()

    logger.debug("Running ffmpeg: %s", " ".join(cmd_list))
    
    # Actually, we should check if the command exists before running to give a better error message
    if os.path.isabs(cmd_list[0]) and not os.path.exists(cmd_list[0]):
        raise FileNotFoundError(f"Command not found: {cmd_list[0]}")
    if not os.path.isabs(cmd_list[0]) and shutil.which(cmd_list[0]) is None:
        raise FileNotFoundError(f"Command not found: {cmd_list[0]}")
        
    proc = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if logger.isEnabledFor(logging.DEBUG):
        stderr = proc.stderr.decode("utf-8", errors="ignore").strip()
        if stderr:
            tail = "\n".join(stderr.splitlines()[-40:])
            logger.debug("ffmpeg stderr (tail):\n%s", tail)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="ignore")
        logger.error("ffmpeg command failed: %s", stderr)
        raise RuntimeError("ffmpeg command failed")


def _safe_file_line(path: str) -> str:
    """Format a path for ffmpeg concat list file."""

    # Use single quotes and escape any existing single quotes conservatively.
    safe = path.replace("'", "'\\''")
    return f"file '{safe}'\n"


def _get_speech_start_offset(wav_path: str, fps: float, threshold: float = 0.08) -> float:
    """Analyze audio file with a sliding window to find sustained speech start.
    
    Increased threshold to 0.08 (8%) and added windowing to ignore tiny clicks.
    """
    if not wav_path or not os.path.exists(wav_path):
        return 0.0
    try:
        cmd = [
            "ffmpeg", "-y", "-i", wav_path,
            "-f", "s16le", "-ac", "1", "-ar", "16000", "-"
        ]
        proc = _run_capture(cmd)
        if proc.returncode != 0:
            return 0.0
            
        content = proc.stdout
        if not content: return 0.0

        import struct
        n_samples = len(content) // 2
        fmt = f"<{n_samples}h"
        samples = struct.unpack(fmt, content)
        
        max_val = 32768.0
        framerate = 16000
        
        # --- NEW: Debug Log Volume Profile for first 1s ---
        window_size = int(0.02 * framerate) # 20ms window
        logger.info("--- Audio Energy Profile (First 1s, 20ms steps) ---")
        for start_idx in range(0, min(len(samples), framerate), window_size):
            window = samples[start_idx : start_idx + window_size]
            if not window: break
            rms = (sum(s**2 for s in window) / len(window))**0.5 / max_val
            time_mark = start_idx / framerate
            # Print a simple bar chart in logs
            bar = "#" * int(rms * 100)
            logger.debug(f"Time {time_mark:.3f}s: {rms:.4f} {bar}")

        # --- NEW: Sliding window detection (must be loud for at least 40ms) ---
        required_sustained_samples = int(0.04 * framerate)
        for i in range(len(samples) - required_sustained_samples):
            # Check if current window average is above threshold
            window = samples[i : i + required_sustained_samples]
            rms = (sum(s**2 for s in window) / len(window))**0.5 / max_val
            if rms > threshold:
                fps = float(fps) if fps else 30.0
                window_center = (i + (required_sustained_samples / 2.0)) / float(framerate)
                quantized = math.ceil(window_center * fps) / fps
                logger.info(
                    ">>> Speech window center %.3fs (RMS %.4f, thr %.3f) -> start %.3fs (fps %.0f)",
                    window_center,
                    rms,
                    threshold,
                    quantized,
                    fps,
                )
                return quantized
                
        logger.warning("No sustained speech detected in %s", wav_path)
    except Exception as e:
        logger.warning("Audio analysis failed: %s", e)
    return 0.0

def _generate_ass_subtitle(
    text: str,
    total_duration: float,
    w: int,
    h: int,
    prefix: str,
    tmp_dir: str,
    speech_start: float = 0.0,
    speech_duration: float = 0.0,
    fps: float = 30.0,
    bottom_margin: int = 180,
    tts_boundaries_path: Optional[str] = None,
) -> str:
    """Generate an .ass subtitle file for the given text with timing."""
    import re
    
    text = text.strip()
    ass_path = os.path.join(tmp_dir, f"{prefix}_narration.ass")
    if not text:
        # Create empty ASS
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(
                "[Script Info]\n"
                "ScriptType: v4.00+\n"
                "Timer: 100.0000\n"
                "[Events]\n"
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            )
        return ass_path

    raw_phrases = re.findall(r"[^,.，。！？；;]+[,.，。！？；;]?", text)
    phrases = [p.strip() for p in raw_phrases if p.strip()]
    if not phrases:
        phrases = [text[i : i + 18] for i in range(0, len(text), 18)]

    min_dur = float(os.environ.get("AUTOCUT_SUB_MIN_DUR", "1.0") or 1.0)
    speed_mode = str(os.environ.get("AUTOCUT_SUB_SPEED_MODE", "auto") or "auto").strip().lower()
    cps_raw = str(os.environ.get("AUTOCUT_SUB_CPS", "6") or "6").strip().lower()
    visible_chars_limit = int(os.environ.get("AUTOCUT_SUB_VISIBLE_CHARS", "24") or 24)
    min_dur = max(0.2, min_dur)
    visible_chars_limit = max(10, visible_chars_limit)

    def build_chunks(target_len: int) -> List[str]:
        out: List[str] = []
        buf2 = ""
        for p in phrases:
            if not buf2:
                buf2 = p
                continue
            if len(buf2) + len(p) <= target_len:
                buf2 += p
                continue
            out.append(buf2)
            buf2 = p
        if buf2:
            out.append(buf2)
        return out

    total_chars_all = sum(len(p) for p in phrases) or len(text)
    start_t = max(0.0, speech_start)
    active_dur = speech_duration if speech_duration > 0 else max(0.0, total_duration - speech_start)
    end_t = min(total_duration, start_t + active_dur)
    if end_t <= start_t:
        end_t = min(total_duration, start_t + 1.0)
    available_time = max(0.1, end_t - start_t)

    if tts_boundaries_path and os.path.exists(tts_boundaries_path):
        try:
            with open(tts_boundaries_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            items = payload.get("boundaries", payload)
            max_chars_env = int(os.environ.get("AUTOCUT_SUB_VISIBLE_CHARS", "24") or 24)
            max_chars_env = max(10, max_chars_env)
            tokens = []
            for it in items:
                try:
                    t0 = float(it.get("start"))
                    t1 = float(it.get("end"))
                except Exception:
                    continue
                if t1 <= t0:
                    continue
                tok = str(it.get("text") or "").strip()
                if not tok:
                    continue
                if len(tok) > max_chars_env:
                    total_len = float(len(tok))
                    acc = 0.0
                    for i in range(0, len(tok), max_chars_env):
                        piece = tok[i : i + max_chars_env]
                        if not piece:
                            continue
                        seg_start = t0 + (t1 - t0) * (acc / total_len)
                        acc += len(piece)
                        seg_end = t0 + (t1 - t0) * (acc / total_len)
                        tokens.append((seg_start, seg_end, piece))
                else:
                    tokens.append((t0, t1, tok))

            if tokens:
                pause_thr = float(os.environ.get("AUTOCUT_SUB_PAUSE_THR", "0.40") or 0.40)
                pause_thr = float(_clamp(pause_thr, 0.05, 2.0))
                max_chars = int(os.environ.get("AUTOCUT_SUB_VISIBLE_CHARS", "24") or 24)
                max_chars = max(10, max_chars)
                out_chunks: List[tuple[float, float, str]] = []

                buf = ""
                c_start = None
                c_end = None
                prev_end = None
                for t0, t1, tok in tokens:
                    if prev_end is not None and (t0 - prev_end) >= pause_thr and buf:
                        out_chunks.append((float(c_start or 0.0), float(c_end or prev_end), buf))
                        buf = ""
                        c_start = None
                        c_end = None

                    if not buf:
                        c_start = t0
                    buf += tok
                    c_end = t1
                    prev_end = t1

                    if len(buf) >= max_chars:
                        out_chunks.append((float(c_start or 0.0), float(c_end or 0.0), buf))
                        buf = ""
                        c_start = None
                        c_end = None

                if buf and c_start is not None and c_end is not None:
                    out_chunks.append((float(c_start), float(c_end), buf))

                if out_chunks:
                    fps = float(fps) if fps else 30.0
                    try:
                        fixed_lines = int(os.environ.get("AUTOCUT_ASS_LINES", "3") or 3)
                    except Exception:
                        fixed_lines = 3
                    fixed_lines = max(1, min(6, fixed_lines))
                    font_size = 70
                    line_height = int(font_size * 1.2)
                    fixed_top_margin = max(0, int(h - bottom_margin - fixed_lines * line_height))
                    pos_x = int(w / 2)
                    pos_tag = f"{{\\an8\\pos({pos_x},{fixed_top_margin})}}"
                    ass_content = [
                        "[Script Info]",
                        "ScriptType: v4.00+",
                        "Timer: 100.0000",
                        f"PlayResX: {w}",
                        f"PlayResY: {h}",
                        "WrapStyle: 2",
                        "",
                        "[V4+ Styles]",
                        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                        f"Style: Default,PingFang SC,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,20,20,{fixed_top_margin},1",
                        "",
                        "[Events]",
                        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
                    ]

                    def format_ass_time(seconds: float) -> str:
                        h = int(seconds // 3600)
                        m = int((seconds % 3600) // 60)
                        s = int(seconds % 60)
                        cs = int((seconds % 1) * 100)
                        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

                    def wrap_ass_text(value: str) -> str:
                        value = value.replace("\n", " ").strip()
                        segs = [value[i : i + 18] for i in range(0, len(value), 18)]
                        if len(segs) >= 2 and len(segs[-1]) < 3:
                            segs[-2] += segs[-1]
                            segs = segs[:-1]
                        if len(segs) > fixed_lines:
                            segs = segs[:fixed_lines]
                        if len(segs) < fixed_lines:
                            pad = [r"{\alpha&HFF&}　"] * (fixed_lines - len(segs))
                            segs = segs + pad
                        return "\\N".join(segs).replace("\n", "\\N")

                    for t0, t1, value in out_chunks:
                        st = start_t + t0
                        et = start_t + t1
                        if et <= st:
                            et = st + 0.05
                        if st >= total_duration:
                            break
                        st = max(0.0, min(total_duration, st))
                        et = max(0.0, min(total_duration, et))
                        if et <= st:
                            continue
                        ass_content.append(
                            f"Dialogue: 0,{format_ass_time(st)},{format_ass_time(et)},Default,,0,0,0,,{pos_tag}{wrap_ass_text(value)}"
                        )

                    with open(ass_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(ass_content))
                    return ass_path
        except Exception:
            pass

    max_chunks = max(1, int(available_time / min_dur))
    target_chunk_len = max(18, int(math.ceil(total_chars_all / max_chunks)))
    chunks = build_chunks(target_chunk_len)
    while len(chunks) > max_chunks:
        max_chunks = max(1, max_chunks - 1)
        target_chunk_len = max(18, int(math.ceil(total_chars_all / max_chunks)))
        chunks = build_chunks(target_chunk_len)

    total_chars = sum(len(p) for p in chunks)
    if total_chars == 0:
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(
                "[Script Info]\n"
                "ScriptType: v4.00+\n"
                "Timer: 100.0000\n"
                "[Events]\n"
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            )
        return ass_path

    fps = float(fps) if fps else 30.0
    try:
        fixed_lines = int(os.environ.get("AUTOCUT_ASS_LINES", "3") or 3)
    except Exception:
        fixed_lines = 3
    fixed_lines = max(1, min(6, fixed_lines))
    font_size = 70
    line_height = int(font_size * 1.2)
    fixed_top_margin = max(0, int(h - bottom_margin - fixed_lines * line_height))
    pos_x = int(w / 2)
    pos_tag = f"{{\\an8\\pos({pos_x},{fixed_top_margin})}}"

    # ASS Header
    ass_content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "Timer: 100.0000",
        f"PlayResX: {w}",
        f"PlayResY: {h}",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,PingFang SC,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,20,20,{fixed_top_margin},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    def format_ass_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def wrap_ass_text(value: str) -> str:
        value = value.replace("\n", " ").strip()
        segs = [value[i : i + 18] for i in range(0, len(value), 18)]
        if len(segs) >= 2 and len(segs[-1]) < 3:
            segs[-2] += segs[-1]
            segs = segs[:-1]
        if len(segs) > fixed_lines:
            segs = segs[:fixed_lines]
        if len(segs) < fixed_lines:
            pad = [r"{\alpha&HFF&}　"] * (fixed_lines - len(segs))
            segs = segs + pad
        return "\\N".join(segs).replace("\n", "\\N")

    if speed_mode not in ("auto", "fixed"):
        speed_mode = "auto"

    if speed_mode == "fixed":
        try:
            cps = float(cps_raw or "6")
        except Exception:
            cps = 6.0
        cps = max(1.0, cps)
        durations = [max(min_dur, min(len(p), visible_chars_limit) / cps) for p in chunks]
        total_need = sum(durations)
        if total_need > available_time and len(chunks) > 1:
            max_chunks = max(1, int(available_time / min_dur))
            target_chunk_len = max(18, int(math.ceil(total_chars_all / max_chunks)))
            chunks = build_chunks(target_chunk_len)
            durations = [max(min_dur, min(len(p), visible_chars_limit) / cps) for p in chunks]
            total_need = sum(durations)

        if total_need > available_time:
            scale = available_time / total_need
            durations = [d * scale for d in durations]
            total_need = sum(durations)

        if total_need < available_time:
            durations[-1] += (available_time - total_need)
    else:
        weights = [max(1.0, float(min(len(p), visible_chars_limit))) for p in chunks]
        total_w = float(sum(weights)) if weights else 1.0
        durations = [available_time * (w / total_w) for w in weights]

        if durations:
            min_total = min_dur * len(durations)
            if min_total >= available_time:
                scale = available_time / max(0.001, sum(durations))
                durations = [max(0.05, d * scale) for d in durations]
            else:
                durations = [max(min_dur, d) for d in durations]
                extra = available_time - sum(durations)
                if abs(extra) > 1e-6:
                    headroom = [max(0.0, d - min_dur) for d in durations]
                    headroom_total = sum(headroom)
                    if extra < 0 and headroom_total > 1e-6:
                        shrink = -extra
                        durations = [
                            d - shrink * (hr / headroom_total) if hr > 0 else d
                            for d, hr in zip(durations, headroom)
                        ]
                    elif extra > 0:
                        durations[-1] += extra

    cur_t = start_t
    for p, d in zip(chunks, durations):
        if cur_t >= end_t:
            break
        next_t = min(end_t, cur_t + d)
        start_str = format_ass_time(cur_t)
        end_str = format_ass_time(next_t)
        ass_content.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{pos_tag}{wrap_ass_text(p)}")
        cur_t = next_t

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_content))
        
    return ass_path


def _render_segment_with_narration(
    base_segment_path: str,
    narration_audio: str,
    narration_text: str,
    seg_duration: float,
    w: int,
    h: int,
    v_fps: float,
    narration_offset: float,
    prefix: str,
    tmp_dir: str,
    bg_duck_db: float = -30.0,
    mute_bg_when_tts: bool = False,
    duck_exclude_ranges: Optional[List[Tuple[float, float]]] = None,
) -> str:
    fps_int = int(round(v_fps)) if v_fps else 30
    if fps_int <= 0:
        fps_int = 30

    detect_speech_start = str(os.environ.get("AUTOCUT_DETECT_SPEECH_START", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }
    speech_start = (
        _get_speech_start_offset(narration_audio, fps=v_fps)
        if (narration_audio and detect_speech_start)
        else 0.0
    )
    total_audio_dur = _get_wav_duration_sec(narration_audio) or seg_duration
    tts_boundaries_path = os.path.splitext(narration_audio)[0] + ".boundaries.json"
    tts_boundaries_available = bool(tts_boundaries_path and os.path.exists(tts_boundaries_path))
    boundaries_first = None
    boundaries_last = None
    if tts_boundaries_available:
        try:
            with open(tts_boundaries_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            items = payload.get("boundaries", payload)
            starts = []
            ends = []
            for it in items:
                try:
                    t0 = float(it.get("start"))
                    t1 = float(it.get("end"))
                except Exception:
                    continue
                if t1 > t0:
                    starts.append(t0)
                    ends.append(t1)
            if starts and ends:
                boundaries_first = min(starts)
                boundaries_last = max(ends)
        except Exception:
            tts_boundaries_available = False

    narration_offset_sec = max(0.0, float(narration_offset))
    available_for_speech = max(0.0, float(seg_duration) - narration_offset_sec)
    if tts_boundaries_available and boundaries_last is not None:
        speech_start = 0.0
        speech_active_dur = max(0.1, min(available_for_speech, float(boundaries_last)))
    else:
        available_audio = max(0.0, float(total_audio_dur) - float(speech_start))
        speech_active_dur = max(0.1, min(available_for_speech, available_audio))

    logger.info(
        "Syncing narrated segment %s: offset=%.3fs, speech_start=%.3fs, active=%.3fs, seg=%.3fs",
        prefix,
        narration_offset_sec,
        speech_start,
        speech_active_dur,
        seg_duration,
    )

    ass_path = _generate_ass_subtitle(
        narration_text,
        seg_duration,
        w,
        h,
        prefix,
        tmp_dir,
        speech_start=narration_offset_sec,
        speech_duration=speech_active_dur,
        fps=v_fps,
        bottom_margin=180,
        tts_boundaries_path=tts_boundaries_path if tts_boundaries_available else None,
    )

    out_path = os.path.join(tmp_dir, f"{prefix}_segment_narrated.mp4")

    safe_ass_path_escaped = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")

    tts_trim_start = max(0.0, float(speech_start))
    tts_trim_end = tts_trim_start + speech_active_dur
    narration_delay_ms = int(round(narration_offset_sec * 1000.0))
    duck_factor = 0.0 if mute_bg_when_tts else math.pow(10.0, float(bg_duck_db) / 20.0)
    if tts_boundaries_available and boundaries_first is not None and boundaries_last is not None:
        duck_start = narration_offset_sec + float(boundaries_first)
        duck_end = min(float(seg_duration), narration_offset_sec + float(boundaries_last))
        tts_trim_start = 0.0
        tts_trim_end = min(float(total_audio_dur), max(0.1, float(boundaries_last)))
    else:
        duck_start = narration_offset_sec
        duck_end = min(float(seg_duration), narration_offset_sec + speech_active_dur)

    if narration_audio and os.path.exists(narration_audio):
        v_filter = f"[0:v]setpts=PTS-STARTPTS,subtitles={safe_ass_path_escaped}[vout];"
        duck_enable = f"between(t,{duck_start:.3f},{duck_end:.3f})"
        if duck_exclude_ranges:
            for start, end in duck_exclude_ranges:
                if end > start:
                    duck_enable += f"*not(between(t,{start:.3f},{end:.3f}))"
        v_filter += (
            f"[0:a]asetpts=PTS-STARTPTS,volume={duck_factor:.6f}:enable='{duck_enable}'[bg];"
            f"[1:a]atrim=start={tts_trim_start:.3f}:end={tts_trim_end:.3f},asetpts=PTS-STARTPTS,adelay={narration_delay_ms}|{narration_delay_ms}[tts];"
            "[bg][tts]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        inputs = [
            "ffmpeg",
            "-y",
            "-i",
            base_segment_path,
            "-i",
            narration_audio,
        ]
    else:
        v_filter = f"[0:v]setpts=PTS-STARTPTS,subtitles={safe_ass_path_escaped}[vout];"
        v_filter += "[0:a]asetpts=PTS-STARTPTS[aout]"
        inputs = [
            "ffmpeg",
            "-y",
            "-i",
            base_segment_path,
        ]

    try:
        _run_ffmpeg(
            [
                *inputs,
                "-filter_complex",
                v_filter,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps_int),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-t",
                f"{seg_duration:.3f}",
                "-avoid_negative_ts",
                "make_zero",
                out_path,
            ]
        )
    finally:
        pass
    return out_path


def _build_segment_video(
    video_path: str,
    narration_audio: Optional[str],
    segment: Dict[str, Any],
    tmp_dir: str,
    vf_args: Sequence[str] | None = None,
    narration_text: Optional[str] = None,
    freeze_effect_engine: Optional[Any] = None,
) -> str:
    """Materialize a single highlight segment using ffmpeg.

    Returns the path to the generated segment ``.mp4``.
    """

    trigger_index = int(segment.get("trigger_index", 0))
    render_type = str(segment.get("render_type") or "freeze").strip().lower()

    prefix = f"seg_{trigger_index:04d}"
    seg_output = os.path.join(tmp_dir, f"{prefix}_segment.mp4")
    seg_base = os.path.join(tmp_dir, f"{prefix}_segment_base.mp4")

    vf_args = list(vf_args) if vf_args else []
    v_fps = _get_video_fps(video_path)
    fps_int = int(round(v_fps)) if v_fps else 30
    if fps_int <= 0:
        fps_int = 30

    v_width, v_height = _get_video_resolution(video_path)
    if vf_args:
        for arg in vf_args:
            if "pad=" in arg:
                import re

                match = re.search(r"pad=(\d+):(\d+)", arg)
                if match:
                    v_width, v_height = int(match.group(1)), int(match.group(2))

    base_vf = ""
    if vf_args and "-vf" in vf_args:
        base_vf = vf_args[vf_args.index("-vf") + 1]

    bg_duck_db = float(os.environ.get("AUTOCUT_BG_DUCK_DB", "-30"))

    if render_type in ("overdub", "pure_audio", "slow_mo"):
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        if end <= start:
            end = start + 2.0
        clip_dur = max(0.01, end - start)

        # 检测旁白时长，如果旁白 > 视频时长则自动延长最后一帧
        narr_dur = _get_wav_duration_sec(narration_audio) if narration_audio else None
        if render_type == "slow_mo":
            speed = float(segment.get("speed", 0.5))
            if speed <= 0:
                speed = 0.5
            out_dur = clip_dur / speed
            extend_dur = 0.0
            # 如果旁白更长，计算需要延长的时长
            if narr_dur is not None and narr_dur > out_dur:
                extend_dur = narr_dur - out_dur + 0.3
                out_dur = narr_dur + 0.3
                logger.info(
                    "slow_mo segment %s: extending last frame by %.3fs to fit narration %.3fs",
                    prefix,
                    extend_dur,
                    narr_dur,
                )
            v_chain = f"{base_vf}," if base_vf else ""
            v_chain += f"setpts=(PTS-STARTPTS)*(1/{speed})"
            # 如果需要延长，添加 tpad 滤镜延长最后一帧
            if extend_dur > 0:
                v_chain += f",tpad=stop_mode=clone:stop_duration={extend_dur:.3f}"
            filter_complex = f"[0:v]{v_chain}[vout];[0:a]asetpts=PTS-STARTPTS,atempo={speed}[aout]"
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{start:.3f}",
                    "-accurate_seek",
                    "-i",
                    video_path,
                    "-t",
                    f"{clip_dur:.3f}",
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[vout]",
                    "-map",
                    "[aout]",
                    "-t",
                    f"{out_dur:.3f}",
                    "-r",
                    str(fps_int),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-avoid_negative_ts",
                    "make_zero",
                    seg_base,
                ]
            )
            seg_duration = float(out_dur)
        else:
            # overdub / pure_audio: 检测旁白时长
            target_dur = clip_dur
            extend_dur = 0.0
            if narr_dur is not None and narr_dur > clip_dur:
                extend_dur = narr_dur - clip_dur + 0.3
                target_dur = narr_dur + 0.3
                logger.info(
                    "overdub segment %s: extending last frame by %.3fs to fit narration %.3fs",
                    prefix,
                    extend_dur,
                    narr_dur,
                )
            # 构建 video filter，如果需要延长则添加 tpad
            v_filter_parts = []
            if vf_args and "-vf" in vf_args:
                v_filter_parts.append(vf_args[vf_args.index("-vf") + 1])
            if extend_dur > 0:
                v_filter_parts.append(f"tpad=stop_mode=clone:stop_duration={extend_dur:.3f}")
            
            if v_filter_parts:
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{start:.3f}",
                    "-accurate_seek",
                    "-i",
                    video_path,
                    "-t",
                    f"{clip_dur:.3f}",
                    "-vf",
                    ",".join(v_filter_parts),
                    "-r",
                    str(fps_int),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-avoid_negative_ts",
                    "make_zero",
                    seg_base,
                ]
            else:
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{start:.3f}",
                    "-accurate_seek",
                    "-i",
                    video_path,
                    "-t",
                    f"{clip_dur:.3f}",
                    *vf_args,
                    "-r",
                    str(fps_int),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-avoid_negative_ts",
                    "make_zero",
                    seg_base,
                ]
            _run_ffmpeg(ffmpeg_cmd)
            seg_duration = float(target_dur)

        if render_type == "pure_audio":
            _run_ffmpeg(["ffmpeg", "-y", "-i", seg_base, "-c", "copy", seg_output])
            return seg_output

        if narration_audio and os.path.exists(narration_audio) and narration_text:
            narrated_path = _render_segment_with_narration(
                seg_base,
                narration_audio,
                narration_text,
                seg_duration,
                v_width,
                v_height,
                v_fps,
                0.0,
                prefix,
                tmp_dir,
                bg_duck_db=bg_duck_db,
                mute_bg_when_tts=False,
            )
            _run_ffmpeg(["ffmpeg", "-y", "-i", narrated_path, "-c", "copy", seg_output])
            return seg_output

        _run_ffmpeg(["ffmpeg", "-y", "-i", seg_base, "-c", "copy", seg_output])
        return seg_output

    pre = segment["pre"]
    freeze = segment["freeze"]
    post = segment["post"]

    pre_start = float(pre["start"])
    pre_duration = float(pre["duration"])
    freeze_time = float(freeze["time"])
    freeze_duration = float(freeze["duration"])
    post_start = float(post["start"])
    post_duration = float(post["duration"])
    freeze_anchor_time = post_start if post_start >= 0 else freeze_time

    if narration_audio and os.path.exists(narration_audio) and narration_text:
        narr_dur = _get_wav_duration_sec(narration_audio)
        if narr_dur is not None and narr_dur > 0:
            freeze_duration = max(freeze_duration, float(_clamp(narr_dur + 0.3, 1.5, 60.0)))

    pre_path = os.path.join(tmp_dir, f"{prefix}_pre.mp4")
    post_path = os.path.join(tmp_dir, f"{prefix}_post.mp4")
    freeze_frame_img = os.path.join(tmp_dir, f"{prefix}_freeze.jpg")
    freeze_bg_audio = os.path.join(tmp_dir, f"{prefix}_freeze_bg.wav")
    freeze_mute_audio = os.path.join(tmp_dir, f"{prefix}_freeze_mute.wav")
    freeze_video = os.path.join(tmp_dir, f"{prefix}_freeze.mp4")

    clip_files: List[str] = []
    if pre_duration > 0.01:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{pre_start:.3f}",
                "-accurate_seek",
                "-i",
                video_path,
                "-t",
                f"{pre_duration:.3f}",
                *vf_args,
                "-r",
                str(fps_int),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-avoid_negative_ts",
                "make_zero",
                pre_path,
            ]
        )
        clip_files.append(pre_path)

    # Background audio for freeze window (if original video has audio)
    # 尝试探测是否有音频流，如果没有，生成静音音频
    has_audio = False
    proc = _run_capture(["ffmpeg", "-i", video_path])
    stderr_output = (proc.stderr or b"").decode("utf-8", errors="ignore")
    if "Audio:" in stderr_output:
        has_audio = True

    freeze_bg_strategy = os.environ.get("AUTOCUT_FREEZE_BG_STRATEGY", "mute").strip().lower()
    if freeze_bg_strategy not in ("mute", "duck", "ambience", "continue"):
        freeze_bg_strategy = "mute"

    if freeze_bg_strategy == "continue" and has_audio:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{freeze_anchor_time:.3f}",
                "-accurate_seek",
                "-i",
                video_path,
                "-t",
                f"{freeze_duration:.3f}",
                "-vn",
                "-ac",
                "2",
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                "-avoid_negative_ts",
                "make_zero",
                freeze_bg_audio,
            ]
        )
        freeze_audio_final = freeze_bg_audio
    elif freeze_bg_strategy in ("duck", "ambience") and has_audio:
        try:
            ambience_sec = float(os.environ.get("AUTOCUT_FREEZE_AMBIENCE_SEC", "0.4"))
        except Exception:
            ambience_sec = 0.4
        ambience_sec = float(_clamp(ambience_sec, 0.1, 3.0))
        ambience_start = max(0.0, freeze_anchor_time - ambience_sec)
        ambience_dur = max(0.1, min(ambience_sec, freeze_anchor_time - ambience_start + 0.001))
        ambience_audio = os.path.join(tmp_dir, f"{prefix}_freeze_ambience.wav")
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{ambience_start:.3f}",
                "-accurate_seek",
                "-i",
                video_path,
                "-t",
                f"{ambience_dur:.3f}",
                "-vn",
                "-ac",
                "2",
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                "-avoid_negative_ts",
                "make_zero",
                ambience_audio,
            ]
        )
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                ambience_audio,
                "-t",
                f"{freeze_duration:.3f}",
                "-c:a",
                "pcm_s16le",
                freeze_bg_audio,
            ]
        )
        freeze_audio_final = freeze_bg_audio
    else:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-t",
                f"{freeze_duration:.3f}",
                "-c:a",
                "pcm_s16le",
                freeze_mute_audio,
            ]
        )
        freeze_audio_final = freeze_mute_audio

    freeze_impl = os.environ.get("AUTOCUT_FREEZE_IMPL", "tpad").strip().lower()
    logger.info(
        "Building freeze segment %s: impl=%s, anchor=%.3fs, dur=%.3fs",
        prefix,
        freeze_impl,
        freeze_anchor_time,
        freeze_duration,
    )

    if freeze_impl == "loop_jpg":
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{freeze_anchor_time:.3f}",
                "-accurate_seek",
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-update",
                "1",
                freeze_frame_img,
            ]
        )
        freeze_cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(fps_int),
            "-i",
            freeze_frame_img,
            "-i",
            freeze_audio_final,
        ]
        v_filter = ""
        if base_vf:
            v_filter += f"[0:v]{base_vf}[vout]"
        else:
            v_filter += "[0:v]null[vout]"
        freeze_cmd.extend(["-filter_complex", v_filter, "-map", "[vout]", "-map", "1:a"])
        freeze_cmd.extend(
            [
                "-t",
                f"{freeze_duration:.3f}",
                "-r",
                str(fps_int),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-avoid_negative_ts",
                "make_zero",
                freeze_video,
            ]
        )
        _run_ffmpeg(freeze_cmd)
    else:
        frame_dur = 1.0 / float(max(1, fps_int))
        v_chain = f"{base_vf}," if base_vf else ""
        v_chain += (
            f"trim=duration={frame_dur:.6f},setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={freeze_duration:.3f}"
        )
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{freeze_anchor_time:.3f}",
                "-accurate_seek",
                "-i",
                video_path,
                "-i",
                freeze_audio_final,
                "-filter_complex",
                f"[0:v]{v_chain}[vout]",
                "-map",
                "[vout]",
                "-map",
                "1:a",
                "-t",
                f"{freeze_duration:.3f}",
                "-r",
                str(fps_int),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-avoid_negative_ts",
                "make_zero",
                freeze_video,
            ]
        )

    if freeze_effect_engine is not None and FreezeEffectEngine is not None:
        freeze_effective_video = os.path.join(tmp_dir, f"{prefix}_freeze_with_effect.mp4")
        v_width, v_height = _get_video_resolution(video_path)
        if vf_args:
            for arg in vf_args:
                if "pad=" in arg:
                    import re
                    match = re.search(r"pad=(\d+):(\d+)", arg)
                    if match:
                        v_width, v_height = int(match.group(1)), int(match.group(2))
        effect_applied = freeze_effect_engine.apply_effects_to_freeze_segment(
            freeze_video,
            freeze_audio_final,
            freeze_effective_video,
            freeze_duration,
            fps_int,
            v_width,
            v_height,
        )
        if effect_applied and os.path.exists(freeze_effective_video):
            freeze_video = freeze_effective_video

    clip_files.append(freeze_video)

    # Post clip
    if post_duration > 0.01:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{post_start:.3f}",
                "-accurate_seek",
                "-i",
                video_path,
                "-t",
                f"{post_duration:.3f}",
                *vf_args,
                "-r",
                str(fps_int),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-avoid_negative_ts",
                "make_zero",
                post_path,
            ]
        )
        clip_files.append(post_path)

    inputs: List[str] = ["ffmpeg", "-y"]
    for p in clip_files:
        inputs.extend(["-i", os.path.abspath(p)])

    filter_parts: List[str] = []
    for i in range(len(clip_files)):
        filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
        filter_parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
    concat_inputs = "".join([f"[v{i}][a{i}]" for i in range(len(clip_files))])
    filter_parts.append(f"{concat_inputs}concat=n={len(clip_files)}:v=1:a=1[vout][aout]")
    filter_complex = ";".join(filter_parts)

    _run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps_int),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-avoid_negative_ts",
            "make_zero",
            seg_base,
        ]
    )

    seg_duration = float(pre_duration + freeze_duration + post_duration)
    if narration_audio and os.path.exists(narration_audio) and narration_text:
        duck_exclude_ranges = None
        if freeze_effect_engine is not None:
            try:
                stinger_cfg = freeze_effect_engine.config.stinger
                if stinger_cfg.enabled:
                    stinger_dur = float(stinger_cfg.duration_ms) / 1000.0
                    if stinger_dur <= 0:
                        stinger_dur = 0.8
                    stinger_start = pre_duration
                    stinger_end = min(pre_duration + stinger_dur, pre_duration + freeze_duration)
                    duck_exclude_ranges = [(stinger_start, stinger_end)]
            except Exception:
                duck_exclude_ranges = None
        try:
            narration_offset = float(os.environ.get("AUTOCUT_NARRATION_OFFSET", f"{pre_duration:.3f}"))
        except Exception:
            narration_offset = pre_duration
        narrated_path = _render_segment_with_narration(
            seg_base,
            narration_audio,
            narration_text,
            seg_duration,
            v_width,
            v_height,
            v_fps,
            narration_offset,
            prefix,
            tmp_dir,
            bg_duck_db=bg_duck_db,
            mute_bg_when_tts=False,
            duck_exclude_ranges=duck_exclude_ranges,
        )
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                narrated_path,
                "-c",
                "copy",
                seg_output,
            ]
        )
        return seg_output

    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            seg_base,
            "-c",
            "copy",
            seg_output,
        ]
    )
    return seg_output


def _execute_plan(
    video_path: str,
    narration_audio: Optional[str],
    segments: Sequence[Dict[str, Any]],
    out_dir: str,
) -> Optional[str]:
    """Execute the given segment plan via ffmpeg.

    Returns the path to the final ``compose.mp4`` if successful, otherwise
    ``None`` (errors are logged).
    """

    if not segments:
        # No triggers; simplest behaviour is to copy the original video.
        compose_path = os.path.join(out_dir, "compose.mp4")
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                video_path,
                "-c",
                "copy",
                compose_path,
            ]
        )
        return compose_path

    tmp_dir = os.path.join(out_dir, "compose_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    segment_videos: List[str] = []
    try:
        for seg in segments:
            seg_video = _build_segment_video(video_path, narration_audio, seg, tmp_dir)
            segment_videos.append(seg_video)

        compose_path = os.path.join(out_dir, "compose.mp4")
        list_path = os.path.join(tmp_dir, "compose_segments.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for p in segment_videos:
                f.write(_safe_file_line(os.path.abspath(p)))

        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                compose_path,
            ]
        )
        # Cleanup temp directory on success
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        return compose_path
    except Exception as exc:  # pragma: no cover - runtime / ffmpeg errors
        logger.error("Failed to execute compose plan via ffmpeg: %s", exc)
        return None


def compose_from_triggers(
    video_path: str,
    triggers_path: str,
    out_dir: str,
    narration_audio: Optional[str] = None,
    target_duration_sec: float = 0.0,
) -> ComposeResult:
    """Compose a highlight reel from triggers and an input video.

    This function always writes ``compose_plan.json`` into ``out_dir``.
    当 ``ffmpeg`` 可用时，会尝试根据该计划生成 ``compose.mp4``，否则仅输出
    计划文件，方便在无 ffmpeg 环境中完成调试与联调。可选的
    ``target_duration_sec`` 会被用于在构造片段时进行“目标时长调度”。
    """

    os.makedirs(out_dir, exist_ok=True)

    triggers = _load_triggers(triggers_path)
    narr_dur = _get_wav_duration_sec(narration_audio) if narration_audio else None
    segments = _build_segments(
        triggers,
        target_duration_sec=target_duration_sec,
        narr_dur=narr_dur,
    )

    ffmpeg_available = _has_ffmpeg()
    total_planned = _compute_total_duration(segments)

    target_value = float(target_duration_sec) if target_duration_sec else 0.0
    duration_limited = bool(
        target_value > 0.0 and total_planned < target_value * 0.9
    )

    plan: Dict[str, Any] = {
        "source_video": os.path.abspath(video_path),
        "triggers_path": os.path.abspath(triggers_path),
        "narration_audio": os.path.abspath(narration_audio)
        if narration_audio
        else None,
        "narration_duration_sec": narr_dur,
        "target_duration_sec": target_value,
        "total_planned_duration_sec": total_planned,
        "duration_limited_by_source": duration_limited,
        "ffmpeg_available": ffmpeg_available,
        "segments": segments,
    }

    plan_path = _save_plan(plan, out_dir)

    output_video: Optional[str] = None
    if ffmpeg_available:
        logger.info("ffmpeg detected on PATH, executing compose plan...")
        output_video = _execute_plan(video_path, narration_audio, segments, out_dir)
        if output_video:
            logger.info("Compose video generated at %s", output_video)
        else:
            logger.warning("Compose video generation failed, see logs above.")
    else:
        logger.warning(
            "ffmpeg not available on PATH; only compose_plan.json was generated."
        )

    return ComposeResult(
        out_dir=os.path.abspath(out_dir),
        ffmpeg_available=ffmpeg_available,
        output_video=os.path.abspath(output_video) if output_video else None,
        plan_path=os.path.abspath(plan_path),
    )


def _build_portrait_vf_args(render: Optional[Dict[str, Any]]) -> List[str]:
    """Build ``-vf`` arguments for portrait (9:16) rendering.

    The returned list can be splatted into an ffmpeg command. When ``render``
    is ``None`` or does not request a 9:16 aspect, an empty list is returned.
    """

    if not render:
        return []

    aspect = str(render.get("aspect", "")).strip()
    if aspect not in {"9:16", "9/16"}:
        return []

    res = str(render.get("resolution", "1080x1920"))
    try:
        w_str, h_str = res.lower().split("x", 1)
        width = int(w_str)
        height = int(h_str)
    except Exception:  # pragma: no cover - defensive parsing
        width = 1080
        height = 1920

    # Strategy: scale to target width while preserving aspect ratio, then
    # pad to the desired height (letterbox) and center vertically.
    vf = f"scale={width}:-2,pad={width}:{height}:0:floor((oh-ih)/2):black"
    return ["-vf", vf]


def compose_segments_xhs(
    video_path: str,
    segments: Sequence[Dict[str, Any]],
    narration_audios: Sequence[Optional[str]],
    out_dir: str,
    render: Optional[Dict[str, Any]] = None,
    output_basename: str = "compose_xhs.mp4",
    narration_texts: Sequence[Optional[str]] | None = None,
    freeze_effect: Optional[str] = None,
) -> Optional[str]:
    """Compose an XHS-oriented highlight reel with per-segment narration.

    This helper is similar to :func:`compose_from_triggers`, but instead of
    reading triggers from JSON it works on an explicit list of segment
    dictionaries **and** a parallel list of narration audio files (one per
    segment).

    When ``ffmpeg`` is not available on the system, the function returns
    ``None`` and does not attempt any media rendering.

    Args:
        freeze_effect: Optional freeze effect preset name (e.g., "weibo_pop",
            "cinematic", "dramatic", "subtle", "none"). When provided, applies
            the effect to all freeze segments in the video. Effects include
            white flash, zoom-in, and stinger audio.
    """

    if not _has_ffmpeg():
        logger.warning(
            "ffmpeg not available on PATH; XHS composition will only have a plan, "
            "no actual compose_xhs.mp4 will be generated.",
        )
        return None

    if not segments:
        logger.warning("No segments provided to compose_segments_xhs; nothing to do.")
        return None

    if len(narration_audios) != len(segments):  # pragma: no cover - defensive
        logger.warning(
            "narration_audios length (%d) does not match segments length (%d); "
            "extra items will be ignored.",
            len(narration_audios),
            len(segments),
        )

    vf_args = _build_portrait_vf_args(render)
    v_fps = _get_video_fps(video_path)
    fps_int = int(round(v_fps)) if v_fps else 30
    if fps_int <= 0:
        fps_int = 30

    tmp_dir = os.path.join(out_dir, "compose_xhs_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    segment_videos: List[str] = []
    keep_tmp = (
        os.environ.get("AUTOCUT_KEEP_TMP", "").strip().lower() not in ("", "0", "false")
        or logger.isEnabledFor(logging.DEBUG)
    )

    freeze_effect_engine = None
    if freeze_effect and freeze_effect != "none" and FreezeEffectEngine is not None:
        freeze_effect_engine = FreezeEffectEngine(freeze_effect)
        logger.info("Freeze effect enabled: %s", freeze_effect)

    try:
        for idx, seg in enumerate(segments):
            narr_audio = narration_audios[idx] if idx < len(narration_audios) else None
            narr_text = narration_texts[idx] if narration_texts and idx < len(narration_texts) else None
            seg_video = _build_segment_video(
                video_path,
                narr_audio,
                seg,
                tmp_dir,
                vf_args=vf_args,
                narration_text=narr_text,
                freeze_effect_engine=freeze_effect_engine,
            )
            segment_videos.append(seg_video)

        compose_path = os.path.join(out_dir, output_basename)
        inputs: List[str] = ["ffmpeg", "-y"]
        for p in segment_videos:
            inputs.extend(["-i", os.path.abspath(p)])

        filter_parts: List[str] = []
        for i in range(len(segment_videos)):
            filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
            filter_parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs = "".join([f"[v{i}][a{i}]" for i in range(len(segment_videos))])
        filter_parts.append(f"{concat_inputs}concat=n={len(segment_videos)}:v=1:a=1[vout][aout]")
        filter_complex = ";".join(filter_parts)

        _run_ffmpeg(
            [
                *inputs,
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps_int),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-avoid_negative_ts",
                "make_zero",
                compose_path,
            ]
        )
        # Cleanup temp directory on success
        if os.path.exists(tmp_dir) and not keep_tmp:
            shutil.rmtree(tmp_dir)
        if keep_tmp:
            logger.info("Kept tmp dir for debugging: %s", tmp_dir)
        return compose_path
    except Exception as exc:  # pragma: no cover - runtime / ffmpeg errors
        logger.error("Failed to execute XHS compose via ffmpeg: %s", exc)
        if keep_tmp:
            logger.info("Kept tmp dir for debugging: %s", tmp_dir)
        return None
