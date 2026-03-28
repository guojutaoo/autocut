"""
Freeze Effect Engine
====================
独立于主项目的动效引擎，为 freeze 定格段生成 ffmpeg 滤镜链。

核心功能：
1. 生成白闪 (white_flash) 滤镜链
2. 生成放大推进 (zoom_in) 滤镜链
3. 生成击中音效 (stinger) 滤镜链
4. 组装完整的 filter_complex

使用方式：
    engine = FreezeEffectEngine(effect_config)
    video_filter, audio_filter = engine.build_filters(
        freeze_duration, fps, width, height
    )
"""

from __future__ import annotations

import logging
import math
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .presets import get_preset, PRESETS

logger = logging.getLogger(__name__)


def _resolve_ffmpeg_exe() -> str:
    env = os.environ.get("AUTOCUT_FFMPEG")
    if env and os.path.exists(env):
        return env
    imageio_path = "/Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
    if os.path.exists(imageio_path):
        return imageio_path
    import shutil
    which = shutil.which("ffmpeg")
    return which or "ffmpeg"


def _has_zoompan() -> bool:
    try:
        proc = subprocess.run(
            [_resolve_ffmpeg_exe(), "-filters"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out = proc.stdout.decode("utf-8", errors="ignore")
        return " zoompan " in out
    except Exception:
        return False


@dataclass
class WhiteFlashConfig:
    enabled: bool = False
    duration_ms: int = 100
    intensity: float = 0.8


@dataclass
class ZoomInConfig:
    enabled: bool = False
    start_zoom: float = 1.0
    end_zoom: float = 1.06
    ease: str = "ease_out"


@dataclass
class StingerConfig:
    enabled: bool = False
    duration_ms: int = 120
    frequency: int = 1800
    gain_db: float = -6.0
    fade_out_ms: int = 80
    profile: str = "sine"
    file_path: str = ""


@dataclass
class EffectConfig:
    white_flash: WhiteFlashConfig
    zoom_in: ZoomInConfig
    stinger: StingerConfig

    @classmethod
    def from_preset(cls, preset_name: str) -> "EffectConfig":
        preset = get_preset(preset_name)
        return cls(
            white_flash=WhiteFlashConfig(**preset["white_flash"]),
            zoom_in=ZoomInConfig(**preset["zoom_in"]),
            stinger=StingerConfig(**preset["stinger"]),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "EffectConfig":
        return cls(
            white_flash=WhiteFlashConfig(**data.get("white_flash", {})),
            zoom_in=ZoomInConfig(**data.get("zoom_in", {})),
            stinger=StingerConfig(**data.get("stinger", {})),
        )

    def to_dict(self) -> dict:
        return {
            "white_flash": {
                "enabled": self.white_flash.enabled,
                "duration_ms": self.white_flash.duration_ms,
                "intensity": self.white_flash.intensity,
            },
            "zoom_in": {
                "enabled": self.zoom_in.enabled,
                "start_zoom": self.zoom_in.start_zoom,
                "end_zoom": self.zoom_in.end_zoom,
                "ease": self.zoom_in.ease,
            },
            "stinger": {
                "enabled": self.stinger.enabled,
                "duration_ms": self.stinger.duration_ms,
                "frequency": self.stinger.frequency,
                "gain_db": self.stinger.gain_db,
                "fade_out_ms": self.stinger.fade_out_ms,
                "profile": self.stinger.profile,
                "file_path": self.stinger.file_path,
            },
        }


def load_effect_preset(name: str) -> EffectConfig:
    return EffectConfig.from_preset(name)


class FreezeEffectEngine:
    def __init__(self, config: EffectConfig | dict | str):
        if isinstance(config, str):
            self.config = EffectConfig.from_preset(config)
        elif isinstance(config, dict):
            self.config = EffectConfig.from_dict(config)
        elif isinstance(config, EffectConfig):
            self.config = config
        else:
            self.config = EffectConfig.from_preset("none")

        self._has_zoompan = _has_zoompan()
        logger.info(
            "FreezeEffectEngine initialized with white_flash=%s, zoom_in=%s, stinger=%s, zoompan=%s",
            self.config.white_flash.enabled,
            self.config.zoom_in.enabled,
            self.config.stinger.enabled,
            self._has_zoompan,
        )

    def _build_zoom_filter(self, duration: float, fps: int, w: int, h: int) -> str:
        if not self.config.zoom_in.enabled:
            return ""

        z = self.config.zoom_in
        zoom_delta = z.end_zoom - z.start_zoom

        if zoom_delta <= 0 or duration <= 0:
            return ""

        if z.ease == "ease_out":
            zoom_rate = zoom_delta / duration
        elif z.ease == "ease_in_out":
            zoom_rate = zoom_delta / (duration * 2)
        else:
            zoom_rate = zoom_delta / duration

        if not self._has_zoompan:
            logger.warning("zoompan not available, skipping zoom effect")
            return ""

        zoom_expr = f"{z.start_zoom}+{zoom_rate}*t"
        return (
            f"zoompan="
            f"'min(zoom+{zoom_rate}, {z.end_zoom})'"
            f":d={int(duration * fps)}"
            f":s={w}x{h}"
            f":fps={fps}"
        )

    def _build_white_flash_filter(
        self, duration: float, w: int, h: int, fps: int
    ) -> str:
        if not self.config.white_flash.enabled:
            return ""

        flash_dur = self.config.white_flash.duration_ms / 1000.0
        if flash_dur <= 0 or flash_dur > duration:
            flash_dur = min(flash_dur, duration * 0.3)

        intensity = self.config.white_flash.intensity
        intensity = max(0.0, min(1.0, intensity))

        alpha_val = int(255 * intensity)

        fade_in_dur = flash_dur * 0.1
        fade_out_start = flash_dur * 0.5
        fade_out_dur = flash_dur * 0.5

        return (
            f"color=white:s={w}x{h}:d={flash_dur}:"
            f"fmt=yuvalpha,"
            f"format=yuva{self._pix_fmt(w, h)},"
            f"trim=duration={flash_dur},"
            f"fade=t=in:st=0:d={fade_in_dur}:alpha={alpha_val},"
            f"fade=t=out:st={fade_out_start}:d={fade_out_dur}:alpha={alpha_val},"
            f"setpts=PTS-STARTPTS+{0:.3f}/TB"
        )

    def _pix_fmt(self, w: int, h: int) -> str:
        return "yuv420p"

    def _build_stinger_filter(self, duration: float, fps: int) -> str:
        if not self.config.stinger.enabled:
            return ""

        s = self.config.stinger
        fade_out_dur = s.fade_out_ms / 1000.0

        gain_linear = math.pow(10, s.gain_db / 20.0)

        if (s.profile or "").strip().lower() == "file" and s.file_path:
            file_path = s.file_path
            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)
            if os.path.exists(file_path):
                file_path = file_path.replace("\\", "\\\\").replace("'", "\\'")
                stinger_dur = s.duration_ms / 1000.0
                if stinger_dur > 0:
                    fade_out_dur = min(fade_out_dur, stinger_dur)
                    return (
                        f"amovie='{file_path}',"
                        f"atrim=0:{stinger_dur},"
                        f"asetpts=PTS-STARTPTS,"
                        f"afade=t=out:st={stinger_dur - fade_out_dur}:d={fade_out_dur},"
                        f"volume={gain_linear:.4f}"
                    )
                return f"amovie='{file_path}',asetpts=PTS-STARTPTS,volume={gain_linear:.4f}"

        stinger_dur = s.duration_ms / 1000.0
        if stinger_dur <= 0:
            return ""

        sine_dur = min(stinger_dur, duration * 0.5)

        if (s.profile or "").strip().lower() == "camera_old":
            noise_dur = sine_dur
            fade_out_dur = min(fade_out_dur, noise_dur)
            return (
                f"anoisesrc=d={noise_dur}:c=white,"
                f"bandpass=f={s.frequency}:w=2000,"
                f"afade=t=out:st={noise_dur - fade_out_dur}:d={fade_out_dur},"
                f"volume={gain_linear:.4f}"
            )

        return (
            f"sine=f={s.frequency}:d={sine_dur},"
            f"afade=t=out:st={sine_dur - fade_out_dur}:d={fade_out_dur},"
            f"volume={gain_linear:.4f}"
        )

    def build_video_filter(
        self,
        freeze_duration: float,
        fps: int,
        w: int,
        h: int,
        base_scale_filter: str = "",
    ) -> str:
        filters: List[str] = []

        zoom_filter = self._build_zoom_filter(freeze_duration, fps, w, h)
        flash_filter = self._build_white_flash_filter(freeze_duration, w, h, fps)

        if zoom_filter:
            filters.append(zoom_filter)
        elif base_scale_filter:
            filters.append(base_scale_filter)
        else:
            filters.append(f"scale={w}:{h}")

        flash_chain = ""
        if flash_filter:
            flash_chain = (
                f"[flash];"
                f"[outv]overlay=0:0:enable='between(t,0,{self.config.white_flash.duration_ms / 1000.0})'[outv]"
            )

        if flash_chain:
            return (
                f"[inv]{';'.join(filters)}[tmp];"
                f"color=white:s={w}x{h}:d={self.config.white_flash.duration_ms / 1000.0}[flash];"
                f"[tmp]{flash_chain}"
            )

        return f"[inv]{';'.join(filters)}[outv]"

    def build_video_filter_simple(
        self,
        freeze_duration: float,
        fps: int,
        w: int,
        h: int,
    ) -> str:
        if not self.config.zoom_in.enabled:
            return "[0:v]null[outv]"

        z = self.config.zoom_in
        zoom_delta = z.end_zoom - z.start_zoom
        if zoom_delta <= 0:
            return "[0:v]null[outv]"

        if z.ease == "ease_out":
            zoom_rate = zoom_delta / freeze_duration
        elif z.ease == "ease_in_out":
            zoom_rate = zoom_delta / (freeze_duration * 2)
        else:
            zoom_rate = zoom_delta / freeze_duration

        zoom_rate = max(0.0001, min(0.1, zoom_rate))

        if self._has_zoompan:
            total_frames = max(1, int(round(freeze_duration * fps)))
            step = zoom_delta / float(total_frames)
            z_expr = f"min({z.start_zoom}+{step}*on,{z.end_zoom})"
            x_expr = "floor(iw/2-(iw/zoom/2))"
            y_expr = "floor(ih/2-(ih/zoom/2))"
            return (
                f"[0:v]zoompan="
                f"z='{z_expr}'"
                f":x='{x_expr}'"
                f":y='{y_expr}'"
                f":d={total_frames}"
                f":s={w}x{h}"
                f":fps={fps}"
                f"[outv]"
            )

        logger.warning("zoompan not available, using scale filter instead")
        end_w = int(w * z.end_zoom)
        end_h = int(h * z.end_zoom)
        return f"[0:v]scale={end_w}:{end_h}:force_original_aspect_ratio=increase,crop={w}:{h}[outv]"

    def build_audio_filter(self, freeze_duration: float) -> str:
        stinger = self._build_stinger_filter(freeze_duration, 30)
        if not stinger:
            return "[0:a]anull[outa]"

        return f"[0:a]anull[base];[base]{stinger}[outa]"

    def build_stinger_audio_only(self, freeze_duration: float) -> Optional[str]:
        if not self.config.stinger.enabled:
            return None

        s = self.config.stinger
        stinger_dur = s.duration_ms / 1000.0
        if stinger_dur <= 0:
            return None

        fade_out_dur = s.fade_out_ms / 1000.0
        sine_dur = min(stinger_dur, freeze_duration * 0.5)
        gain_linear = math.pow(10, s.gain_db / 20.0)

        return (
            f"sine=f={s.frequency}:d={sine_dur},"
            f"afade=t=out:st={sine_dur - fade_out_dur}:d={fade_out_dur},"
            f"volume={gain_linear:.4f}"
        )

    def apply_effects_to_freeze_segment(
        self,
        freeze_video_path: str,
        freeze_audio_path: str,
        output_path: str,
        freeze_duration: float,
        fps: int,
        w: int,
        h: int,
    ) -> bool:
        import shutil
        from .engine import _resolve_ffmpeg_exe as _get_ffmpeg

        logger.info(
            "apply_effects_to_freeze_segment: video=%s, audio=%s, duration=%.3f, fps=%d, size=%dx%d",
            freeze_video_path, freeze_audio_path, freeze_duration, fps, w, h
        )
        logger.info("Effect config: white_flash=%s, zoom_in=%s, stinger=%s",
            self.config.white_flash.enabled, self.config.zoom_in.enabled, self.config.stinger.enabled)

        if not os.path.exists(freeze_video_path):
            logger.error("Freeze video not found: %s", freeze_video_path)
            return False

        has_audio_file = freeze_audio_path and os.path.exists(freeze_audio_path)
        logger.info("Has audio file: %s", has_audio_file)

        cmd: List[str] = ["ffmpeg", "-y"]
        filter_parts = []

        v_filter = self.build_video_filter_simple(freeze_duration, fps, w, h)
        logger.info("Video filter: %s", v_filter)
        filter_parts.append(v_filter)

        if has_audio_file:
            cmd.extend(["-i", freeze_video_path, "-i", freeze_audio_path])
            base_a = "[1:a]"
        else:
            cmd.extend(["-i", freeze_video_path])
            base_a = "[0:a]"

        if self.config.stinger.enabled:
            stinger_filter = self._build_stinger_filter(freeze_duration, fps)
            if stinger_filter:
                filter_parts.append(
                    f"{stinger_filter}[stinger];"
                    f"{base_a}asetpts=PTS-STARTPTS[base];"
                    "[base][stinger]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                )
            else:
                filter_parts.append(f"{base_a}asetpts=PTS-STARTPTS[aout]")
        else:
            filter_parts.append(f"{base_a}asetpts=PTS-STARTPTS[aout]")

        filter_complex = ";".join(filter_parts)
        logger.info("Filter complex: %s", filter_complex)

        cmd.extend([
            "-filter_complex",
            filter_complex,
            "-map", "[outv]",
            "-map", "[aout]",
        ])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", f"{freeze_duration:.3f}",
            output_path,
        ])

        try:
            cmd[0] = _get_ffmpeg()
            logger.info("Running ffmpeg with effects: %s", " ".join(cmd[:10]) + "...")
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                stderr = proc.stderr.decode("utf-8", errors="ignore")
                logger.error("ffmpeg failed: %s", stderr[-500:])
                return False
            return True
        except Exception as exc:
            logger.error("Failed to apply effects: %s", exc)
            return False


def build_effect_video(
    freeze_frame_img: str,
    freeze_audio: str,
    output_path: str,
    duration: float,
    fps: int,
    w: int,
    h: int,
    effect_config: EffectConfig | dict | str = "weibo_pop",
) -> bool:
    engine = FreezeEffectEngine(effect_config)
    return engine.apply_effects_to_freeze_segment(
        freeze_frame_img,
        freeze_audio,
        output_path,
        duration,
        fps,
        w,
        h,
    )
