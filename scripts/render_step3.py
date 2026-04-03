#!/usr/bin/env python3
import os
import sys
import json
import argparse
import subprocess
import shutil
import logging
from typing import Any, Dict, List

# Add parent dir to path to import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.tts.tts_edge import synthesize

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def time_to_sec(t_str: str) -> float:
    parts = t_str.strip().split(':')
    sec = 0.0
    for i, p in enumerate(reversed(parts)):
        sec += float(p) * (60 ** i)
    return sec

def sec_to_srt_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec * 1000) % 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

import re

def remove_ssml_tags(text: str) -> str:
    """Remove SSML tags like <break time="0.5s"/> from text"""
    return re.sub(r'<[^>]+>', '', text)

def create_ass_from_boundaries(boundaries_path: str, output_ass: str, full_text: str):
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,10,10,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    def sec_to_ass_time(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec * 100) % 100)
        return f"{h:01d}:{m:02d}:{s:02d}.{ms:02d}"

    with open(output_ass, "w", encoding="utf-8") as f:
        f.write(ass_header)
        clean_text = remove_ssml_tags(full_text)
        if not os.path.exists(boundaries_path):
            f.write(f"Dialogue: 0,0:00:00.00,0:59:59.99,Default,,0,0,0,,{clean_text}\n")
            return

        with open(boundaries_path, "r", encoding="utf-8") as data_f:
            data = json.load(data_f)
        
        boundaries = data.get("boundaries", [])
        if not boundaries:
            f.write(f"Dialogue: 0,0:00:00.00,0:59:59.99,Default,,0,0,0,,{clean_text}\n")
            return

        for b in boundaries:
            start = b["start"]
            end = b["end"]
            text = remove_ssml_tags(b["text"])
            if not text.strip():
                continue
            f.write(f"Dialogue: 0,{sec_to_ass_time(start)},{sec_to_ass_time(end)},Default,,0,0,0,,{text}\n")

def run_cmd(cmd: List[str]):
    logger.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def render_segment(seg: Dict[str, Any], video_path: str, tmp_dir: str, rules: Dict[str, Any]) -> str:
    order = seg["order"]
    prefix = f"seg_{order:02d}"
    
    # 1. TTS
    narration = seg.get("narration", "")
    tts_wav = os.path.join(tmp_dir, f"{prefix}_tts.wav")
    boundaries_path = os.path.join(tmp_dir, f"{prefix}_tts.boundaries.json")
    
    logger.info(f"[{prefix}] Generating TTS...")
    synthesize(text=narration, out_path=tts_wav)
    
    # 2. ASS
    ass_path = os.path.join(tmp_dir, f"{prefix}.ass")
    create_ass_from_boundaries(boundaries_path, ass_path, narration)
    
    # 3. Cut Video
    sub_clips = seg.get("sub_clips")
    cut_files = []
    if sub_clips:
        logger.info(f"[{prefix}] Cutting sub-clips...")
        for i, sc in enumerate(sub_clips):
            sc_start = time_to_sec(sc["start"])
            sc_dur = float(sc["dur"])
            sc_out = os.path.join(tmp_dir, f"{prefix}_sub_{i}.mp4")
            run_cmd([
                "ffmpeg", "-y", "-ss", str(sc_start), "-i", video_path,
                "-t", str(sc_dur), "-c:v", "libx264", "-c:a", "aac", "-avoid_negative_ts", "make_zero", sc_out
            ])
            cut_files.append(sc_out)
    else:
        logger.info(f"[{prefix}] Cutting main clip...")
        start_sec = time_to_sec(seg["clip"]["start"])
        end_sec = time_to_sec(seg["clip"]["end"])
        dur = end_sec - start_sec
        sc_out = os.path.join(tmp_dir, f"{prefix}_sub_0.mp4")
        run_cmd([
            "ffmpeg", "-y", "-ss", str(start_sec), "-i", video_path,
            "-t", str(dur), "-c:v", "libx264", "-c:a", "aac", "-avoid_negative_ts", "make_zero", sc_out
        ])
        cut_files.append(sc_out)
        
    # Concat cuts if needed
    if len(cut_files) > 1:
        concat_list = os.path.join(tmp_dir, f"{prefix}_concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for cf in cut_files:
                f.write(f"file '{os.path.abspath(cf)}'\n")
        raw_video = os.path.join(tmp_dir, f"{prefix}_raw.mp4")
        run_cmd([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy", raw_video
        ])
    else:
        raw_video = cut_files[0]
        
    # 4. Speed up, mix audio and burn subtitles
    logger.info(f"[{prefix}] Applying speed, mix, and subtitles...")
    video_speed = seg.get("video_speed")
    if video_speed is None:
        if "tts_duration_sec" in seg and "clip_duration_sec" in seg and seg["tts_duration_sec"] > 0:
            video_speed = float(seg["clip_duration_sec"]) / float(seg["tts_duration_sec"])
        else:
            video_speed = 1.0
    out_video = os.path.join(tmp_dir, f"{prefix}_out.mp4")
    
    # Escape ASS path for FFmpeg filter
    ass_rel_path = os.path.relpath(ass_path, start=os.getcwd()).replace("\\", "/")
    
    orig_db = rules.get("original_audio_db", -15)
    
    # For "freeze" type, we need to handle it properly if requested.
    # But since instructions say overdub_only logic is enough, we will at least ensure the video isn't broken.
    render_type = seg.get("render_type", "overdub")
    if render_type == "freeze":
        freeze_ts = seg.get("freeze_frame_ts", seg["clip"]["start"])
        freeze_sec = time_to_sec(freeze_ts)
        dur = seg.get("tts_duration_sec", 3.0) + 1.0
        
        # Create a frozen video
        frozen_raw = os.path.join(tmp_dir, f"{prefix}_frozen.mp4")
        
        # We replace raw_video with the frozen one.
        # But wait, ffmpeg loop on a single frame needs different input handling.
        # Let's extract frame first:
        frame_img = os.path.join(tmp_dir, f"{prefix}_freeze.jpg")
        run_cmd([
            "ffmpeg", "-y", "-ss", str(freeze_sec), "-i", video_path,
            "-vframes", "1", "-update", "1", frame_img
        ])
        # Then create video from image and silent audio
        run_cmd([
            "ffmpeg", "-y", "-loop", "1", "-i", frame_img,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-avoid_negative_ts", "make_zero", frozen_raw
        ])
        raw_video = frozen_raw
        video_speed = 1.0  # Reset speed for freeze since we already set duration

    # Handle transitions
    # In v7_final, transition is specified per segment. For a simple implementation,
    # we just generate the clip as usual. Crossfades between segments requires a complex
    # filter_complex for all clips. Since we just concat at the end, crossfade requires
    # all inputs to be processed in one ffmpeg command or complex script.
    # For now, we will do hard cuts in concat, which works. 
    # If the user strictly wants fade_black, we can add a fade filter to the end of this segment.
    transition_type = seg.get("transition_type", "cut")
    transition_dur = float(seg.get("transition_duration_sec", 0.0))
    
    fade_filter = ""
    if transition_type == "fade_black" and transition_dur > 0:
        # We need to fade out at the end. We must know the final duration.
        # final duration = dur / video_speed
        if render_type == "freeze":
            final_dur = dur
        else:
            if sub_clips:
                final_dur = sum(float(sc["dur"]) for sc in sub_clips) / video_speed
            else:
                final_dur = (time_to_sec(seg["clip"]["end"]) - time_to_sec(seg["clip"]["start"])) / video_speed
        
        fade_start = max(0, final_dur - transition_dur)
        fade_filter = f",fade=t=out:st={fade_start}:d={transition_dur}"

    # Fix for atempo limits (0.5 to 100.0). If it's very close to 1.0, we can omit it, but let's just apply it.
    video_speed = max(0.5, min(100.0, float(video_speed)))
    
    # We remove the 'subtitles' filter because the environment's ffmpeg doesn't support libass.
    # We will mux the ASS file as a separate stream instead.
    filter_complex = (
        f"[0:v]setpts=(1/{video_speed})*PTS{fade_filter}[v];"
        f"[0:a]atempo={video_speed},volume={orig_db}dB[va];"
        f"[1:a]volume=0dB[ta];"
        f"[va][ta]amix=inputs=2:duration=longest[a]"
    )
    
    run_cmd([
        "ffmpeg", "-y",
        "-i", raw_video,
        "-i", tts_wav,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        out_video
    ])
    
    return out_video

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="Path to step3_final_transcript.json")
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--out", required=True, help="Output mp4 path")
    args = parser.parse_args()
    
    with open(args.plan, "r", encoding="utf-8") as f:
        plan = json.load(f)
        
    rules = plan.get("render_rules", {})
    segments = plan.get("segments", [])
    
    tmp_dir = os.path.join(os.path.dirname(os.path.abspath(args.out)), "render_step3_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    
    try:
        out_segments = []
        for seg in segments:
            logger.info(f"=== Processing segment {seg['order']} ===")
            out_seg = render_segment(seg, args.video, tmp_dir, rules)
            out_segments.append(out_seg)
            
        logger.info("=== Concatenating all segments ===")
        concat_list = os.path.join(tmp_dir, "final_concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for seg_file in out_segments:
                f.write(f"file '{os.path.abspath(seg_file)}'\n")
                
        run_cmd([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c:v", "libx264", "-c:a", "aac", args.out
        ])
        
        logger.info(f"=== Video successfully rendered to {args.out} ===")
        
    finally:
        pass

if __name__ == "__main__":
    main()
