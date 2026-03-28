#!/usr/bin/env python3
"""
Test subtitle font size - generate comparison videos with different font sizes.
"""

import os
import subprocess

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
TEST_DURATION = 3
OUTPUT_DIR = "/Users/bytedance/Downloads/autocut/test_font_output"

def resolve_ffmpeg_exe():
    env = os.environ.get("AUTOCUT_FFMPEG")
    if env and os.path.exists(env):
        return env
    imageio_path = "/Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
    if os.path.exists(imageio_path):
        return imageio_path
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"

def create_test_ass(font_size, line_height, output_path):
    """Create ASS file with specified font size."""
    bottom_margin = 270
    target_first_line_y = VIDEO_HEIGHT - bottom_margin
    base_offset = 14
    num_lines = 2
    total_height = num_lines * line_height
    multi_line_compensation = (num_lines - 1) * 5
    center_y = int(target_first_line_y + (total_height / 2) - (line_height / 2) + base_offset - multi_line_compensation)
    
    ass_content = f"""[Script Info]
ScriptType: v4.00+
Timer: 100.0000
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,PingFang SC,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H88000000,0,0,0,0,100,100,0,0,3,2,0,5,20,20,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,{{\\pos({VIDEO_WIDTH//2},{center_y})}}测试字幕{font_size}号\\N第二行文字对比
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return center_y

def generate_video(ass_path, output_path):
    ffmpeg = resolve_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", f"color=c=blue:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d={TEST_DURATION}",
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-t", str(TEST_DURATION),
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def extract_frame(video_path, output_path):
    ffmpeg = resolve_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-ss", "1",
        "-vframes", "1",
        output_path
    ]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(output_path)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    test_cases = [
        (80, 62, "font_80"),  # Original size
        (90, 68, "font_90"),  # +6 size
        (100, 74, "font_100"),  # +12 size (for clear comparison)
    ]
    
    print("=" * 70)
    print("字体大小对比测试")
    print("=" * 70)
    
    for font_size, line_height, name in test_cases:
        print(f"\n生成 {font_size}px 字体测试视频...")
        
        ass_path = os.path.join(OUTPUT_DIR, f"{name}.ass")
        video_path = os.path.join(OUTPUT_DIR, f"{name}.mp4")
        frame_path = os.path.join(OUTPUT_DIR, f"{name}.png")
        
        # Create ASS
        center_y = create_test_ass(font_size, line_height, ass_path)
        
        # Generate video
        if not generate_video(ass_path, video_path):
            print(f"  ❌ 视频生成失败")
            continue
        
        # Extract frame
        if not extract_frame(video_path, frame_path):
            print(f"  ❌ 帧提取失败")
            continue
        
        print(f"  ✅ 完成: {frame_path}")
        print(f"     字体: {font_size}px, 行高: {line_height}px, 中心Y: {center_y}")
    
    print("\n" + "=" * 70)
    print("对比文件已生成，请查看:")
    for _, _, name in test_cases:
        print(f"  {OUTPUT_DIR}/{name}.png")
    print("=" * 70)

if __name__ == "__main__":
    main()
