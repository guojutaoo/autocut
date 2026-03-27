"""Text-to-speech utilities based on :mod:`edge_tts`.

The goal is to provide a minimal, offline-friendly wrapper that:

* Uses ``edge-tts`` when the library is installed and network access is
  available.
* Gracefully degrades to generating a short (0.5s) silent WAV file when
  synthesis fails for any reason (missing dependency, network error, etc.).

This keeps the overall PoC runnable in fully offline environments while still
allowing higher-fidelity TTS where possible.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import wave
from typing import Final

logger = logging.getLogger(__name__)

try:  # Optional dependency
    import edge_tts  # type: ignore

    HAS_EDGE_TTS: Final[bool] = True
except Exception:  # pragma: no cover - optional path
    edge_tts = None  # type: ignore
    HAS_EDGE_TTS = False


_SILENCE_DURATION_SEC: Final[float] = 0.5
_SILENCE_SAMPLE_RATE: Final[int] = 16000


def _normalize_percentage(value: str) -> str:
    """Normalize ``rate`` / ``volume`` strings for ``edge-tts``.

    ``edge-tts`` expects values like ``"+0%"``, ``"+20%"`` or ``"-10%"``.
    This helper accepts more relaxed forms (``"0"``, ``"0%"``, ``"+10"``,
    etc.) and normalizes them to the ``+/-NN%`` form.
    """

    text = (value or "").strip()
    if not text:
        return "+0%"

    # Strip trailing percent sign if present
    if text.endswith("%"):
        core = text[:-1].strip()
    else:
        core = text

    if not core:
        return "+0%"

    if core[0] in "+-":
        return f"{core}%" if not core.endswith("%") else core

    # No explicit sign, treat as positive
    return f"+{core}%"


def _ensure_wav_path(out_path: str) -> str:
    """Return a path with ``.wav`` extension based on ``out_path``.

    If ``out_path`` already ends with ``.wav`` (case-insensitive), it is
    returned as-is; otherwise the extension is replaced with ``.wav``.
    """

    base, ext = os.path.splitext(out_path)
    if ext.lower() == ".wav":
        return out_path
    if not base:
        base = "tts_silence"
    return base + ".wav"


def _generate_silence_wav(out_path: str) -> str:
    """Generate a short mono 16-bit PCM silent WAV file.

    The file duration is fixed to ``_SILENCE_DURATION_SEC``.
    The actual file path (with ``.wav`` extension) is returned.
    """

    target = _ensure_wav_path(out_path)
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)

    n_frames = int(_SILENCE_DURATION_SEC * _SILENCE_SAMPLE_RATE)
    logger.info(
        "Generating %.3fs silent WAV as TTS fallback at %s",
        _SILENCE_DURATION_SEC,
        target,
    )

    with wave.open(target, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(_SILENCE_SAMPLE_RATE)
        wf.writeframes(b"\x00\x00" * n_frames)

    return target


async def _synthesize_with_edge_tts(
    text: str,
    out_path: str,
    voice: str,
    rate: str,
    volume: str,
) -> None:
    """Internal coroutine that performs TTS using :mod:`edge_tts`.

    Parameters are expected to be already normalized.
    """

    if edge_tts is None:  # pragma: no cover - defensive
        raise RuntimeError("edge-tts is not available")

    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=rate,
        volume=volume,
    )
    await communicate.save(out_path)


def _boundaries_sidecar_path(audio_out_path: str) -> str:
    base, _ = os.path.splitext(audio_out_path)
    return base + ".boundaries.json"


def _to_seconds_from_edge_tts_ticks(value: int) -> float:
    return float(value) / 10_000_000.0


async def _synthesize_with_edge_tts_boundaries(
    text: str,
    out_path: str,
    voice: str,
    rate: str,
    volume: str,
) -> None:
    if edge_tts is None:  # pragma: no cover - defensive
        raise RuntimeError("edge-tts is not available")

    output_format = str(
        os.environ.get("AUTOCUT_TTS_OUTPUT_FORMAT", "riff-24khz-16bit-mono-pcm") or ""
    ).strip()

    kwargs = {"rate": rate, "volume": volume}
    if output_format:
        kwargs["output_format"] = output_format

    try:
        communicate = edge_tts.Communicate(text, voice, **kwargs)
    except TypeError:
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        output_format = ""

    sidecar = _boundaries_sidecar_path(out_path)
    boundaries = []

    directory = os.path.dirname(out_path) or "."
    os.makedirs(directory, exist_ok=True)

    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            kind = chunk.get("type")
            if kind == "audio":
                data = chunk.get("data")
                if data:
                    f.write(data)
            elif kind == "WordBoundary":
                offset = chunk.get("offset")
                duration = chunk.get("duration")
                token = chunk.get("text") or chunk.get("word") or ""
                try:
                    offset_i = int(offset)
                    duration_i = int(duration)
                except Exception:
                    continue
                boundaries.append(
                    {
                        "text": str(token),
                        "offset": offset_i,
                        "duration": duration_i,
                        "start": _to_seconds_from_edge_tts_ticks(offset_i),
                        "end": _to_seconds_from_edge_tts_ticks(offset_i + duration_i),
                    }
                )

    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": 1,
                "voice": voice,
                "rate": rate,
                "volume": volume,
                "output_format": output_format,
                "boundaries": boundaries,
            },
            f,
            ensure_ascii=False,
        )


def synthesize(
    text: str,
    out_path: str,
    voice: str = "zh-CN-YunjianNeural",
    rate: str = "0%",
    volume: str = "0%",
) -> str:
    """Synthesize ``text`` into speech audio at ``out_path``.

    This function is intentionally synchronous for simplicity. It will:

    1. If ``text`` 为空或全是空白：直接生成 0.5s 静音 WAV，返回文件路径；
    2. 如果 ``edge-tts`` 未安装：记录日志并生成静音 WAV；
    3. 否则尝试调用 ``edge-tts`` 生成语音文件；一旦失败（网络错误、
       服务异常等），会回退到静音 WAV。

    返回值为实际生成的音频文件路径（可能与传入的 ``out_path`` 路径
    在扩展名上略有不同，例如从 ``.mp3`` 回退为 ``.wav``）。
    """

    if not text.strip():
        logger.info("TTS text is empty, using silent fallback instead.")
        return _generate_silence_wav(out_path)

    out_dir = os.path.dirname(out_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    if not HAS_EDGE_TTS:
        logger.warning(
            "edge-tts library not available, falling back to silent WAV. "
            "Install 'edge-tts' for real TTS output.",
        )
        return _generate_silence_wav(out_path)

    rate_norm = _normalize_percentage(rate)
    volume_norm = _normalize_percentage(volume)

    try:
        boundaries_mode = str(os.environ.get("AUTOCUT_TTS_BOUNDARIES", "1") or "1").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
        }

        coro = (
            _synthesize_with_edge_tts_boundaries(
                text=text,
                out_path=out_path,
                voice=voice,
                rate=rate_norm,
                volume=volume_norm,
            )
            if boundaries_mode
            else _synthesize_with_edge_tts(
                text=text,
                out_path=out_path,
                voice=voice,
                rate=rate_norm,
                volume=volume_norm,
            )
        )
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            # Run in a separate thread to avoid "RuntimeError: asyncio.run() cannot be called from a running event loop"
            import threading
            def _run_in_thread(coroutine, result_box):
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(coroutine)
                    result_box['success'] = True
                except Exception as e:
                    result_box['error'] = e
                finally:
                    new_loop.close()
                    
            box = {}
            t = threading.Thread(target=_run_in_thread, args=(coro, box))
            t.start()
            t.join()
            if 'error' in box:
                raise box['error']
        else:
            asyncio.run(coro)
            
        logger.info("Generated TTS audio at %s", out_path)
        if boundaries_mode:
            logger.info("Generated TTS boundaries at %s", _boundaries_sidecar_path(out_path))
        return out_path
    except Exception as exc:  # pragma: no cover - network / runtime issues
        logger.warning("edge-tts synthesis failed, using silent fallback: %s", exc)
        return _generate_silence_wav(out_path)
