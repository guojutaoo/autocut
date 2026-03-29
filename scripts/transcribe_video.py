"""
从本地视频文件提取音频并进行语音识别，生成带时间戳字幕（SRT）与逐字稿（JSON/TXT）。

示例：
  python scripts/transcribe_video.py --input /path/to/01.mp4
  python scripts/transcribe_video.py --input 01.mp4 --model medium --language zh --word-timestamps
"""

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: Optional[List[Word]] = None


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms_total = int(round(seconds * 1000))
    ms = ms_total % 1000
    s_total = ms_total // 1000
    s = s_total % 60
    m_total = s_total // 60
    m = m_total % 60
    h = m_total // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_text(path: str, content: str, encoding: str) -> None:
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def extract_audio_wav(input_video: str, out_wav: str) -> None:
    ensure_dir(os.path.dirname(out_wav))
    ffmpeg_exe = os.environ.get("AUTOCUT_FFMPEG", "").strip()
    if not ffmpeg_exe:
        try:
            import imageio_ffmpeg  # type: ignore

            ffmpeg_exe = str(imageio_ffmpeg.get_ffmpeg_exe() or "").strip()
        except Exception:
            ffmpeg_exe = "ffmpeg"
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        input_video,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        out_wav,
    ]
    subprocess.run(cmd, check=True)


def to_segments(raw_segments: Sequence[Any]) -> List[Segment]:
    segments: List[Segment] = []
    for seg in raw_segments:
        start = float(getattr(seg, "start", 0.0))
        end = float(getattr(seg, "end", 0.0))
        text = str(getattr(seg, "text", "")).strip()
        words_raw = getattr(seg, "words", None)
        words: Optional[List[Word]] = None
        if words_raw:
            words = []
            for w in words_raw:
                ws = float(getattr(w, "start", 0.0))
                we = float(getattr(w, "end", 0.0))
                wt = str(getattr(w, "word", getattr(w, "text", "")))
                words.append(Word(start=ws, end=we, text=wt))
        segments.append(Segment(start=start, end=end, text=text, words=words))
    return segments


def render_srt(segments: List[Segment]) -> str:
    blocks: List[str] = []
    for i, seg in enumerate(segments, start=1):
        blocks.append(str(i))
        blocks.append(f"{srt_timestamp(seg.start)} --> {srt_timestamp(seg.end)}")
        blocks.append(seg.text)
        blocks.append("")
    return "\n".join(blocks)


def render_txt(segments: List[Segment]) -> str:
    lines: List[str] = []
    for seg in segments:
        lines.append(f"[{srt_timestamp(seg.start)} - {srt_timestamp(seg.end)}] {seg.text}")
    return "\n".join(lines) + "\n"


def build_json_payload(input_path: str, model: str, language: Optional[str], segments: List[Segment]) -> Dict[str, Any]:
    segs: List[Dict[str, Any]] = []
    for s in segments:
        item: Dict[str, Any] = {"start": s.start, "end": s.end, "text": s.text}
        if s.words is not None:
            item["words"] = [{"start": w.start, "end": w.end, "text": w.text} for w in s.words]
        segs.append(item)
    return {"input": input_path, "model": model, "language": language, "segments": segs}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="本地视频路径，例如 01.mp4")
    parser.add_argument("--out-dir", default="output", help="输出目录（默认 output）")
    parser.add_argument("--model", default="small", help="模型名：tiny/base/small/medium/large-v3 等")
    parser.add_argument("--language", default="zh", help="语言（默认 zh）")
    parser.add_argument("--format", default="srt,json,txt", help="输出格式列表：srt,json,txt（逗号分隔）")
    parser.add_argument("--word-timestamps", action="store_true", help="启用逐字时间戳（不支持则自动降级）")
    parser.add_argument("--bom", action="store_true", help="输出 UTF-8 BOM，提升部分播放器兼容性")
    parser.add_argument("--keep-audio", action="store_true", help="保留中间 wav 文件")
    args = parser.parse_args()

    input_path = os.path.abspath(str(args.input))
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    out_dir = os.path.abspath(str(args.out_dir))
    ensure_dir(out_dir)
    base = os.path.splitext(os.path.basename(input_path))[0]

    wav_path = os.path.join(out_dir, f"{base}.asr.wav")
    extract_audio_wav(input_path, wav_path)

    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise RuntimeError(
            "缺少 ASR 依赖：请先执行 `pip install -r requirements.asr.txt` 安装 faster-whisper"
        ) from e

    model_name = str(args.model)
    language = str(args.language) if args.language else None
    word_ts = bool(args.word_timestamps)

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    raw_segments, _info = model.transcribe(
        wav_path,
        language=language,
        beam_size=5,
        word_timestamps=word_ts,
        vad_filter=True,
    )
    segments = to_segments(list(raw_segments))

    encoding = "utf-8-sig" if bool(args.bom) else "utf-8"
    formats = [p.strip().lower() for p in str(args.format).split(",") if p.strip()]

    if "srt" in formats:
        srt_path = os.path.join(out_dir, f"{base}.srt")
        write_text(srt_path, render_srt(segments), encoding=encoding)

    if "txt" in formats:
        txt_path = os.path.join(out_dir, f"{base}.txt")
        write_text(txt_path, render_txt(segments), encoding=encoding)

    if "json" in formats:
        json_path = os.path.join(out_dir, f"{base}.json")
        payload = build_json_payload(input_path, model=model_name, language=language, segments=segments)
        write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding=encoding)

    if not bool(args.keep_audio):
        try:
            os.remove(wav_path)
        except Exception:
            pass


if __name__ == "__main__":
    main()
