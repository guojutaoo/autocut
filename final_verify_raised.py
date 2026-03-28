#!/usr/bin/env python3
"""
Final verification of subtitle position with raised position (150px higher).
"""

import os
import subprocess
from PIL import Image, ImageDraw

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
TEST_DURATION = 3
BOTTOM_MARGIN = 270  # Raised by 150px (was 120)
OUTPUT_DIR = "/Users/bytedance/Downloads/autocut/final_verify_raised_output"

def resolve_ffmpeg_exe():
    env = os.environ.get("AUTOCUT_FFMPEG")
    if env and os.path.exists(env):
        return env
    imageio_path = "/Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
    if os.path.exists(imageio_path):
        return imageio_path
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"

def create_test_ass(text, num_lines, output_path):
    """Create ASS file using the fixed formula."""
    line_height = 62
    target_first_line_y = VIDEO_HEIGHT - BOTTOM_MARGIN  # 1650
    base_offset = 14
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
Style: Default,PingFang SC,52,&H00FFFFFF,&H000000FF,&H00000000,&H88000000,0,0,0,0,100,100,0,0,3,2,0,5,20,20,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,{{\\pos({VIDEO_WIDTH//2},{center_y})}}{text}
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    return center_y, target_first_line_y

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

def analyze_frame(frame_path):
    """Find the Y position of the first line of text."""
    img = Image.open(frame_path)
    width, height = img.size
    
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    pixels = img.load()
    
    # Find all rows with white pixels
    text_rows = []
    for y in range(height):
        white_count = 0
        for x in range(width):
            r, g, b = pixels[x, y]
            if r > 180 and g > 180 and b > 180:
                white_count += 1
        if white_count > 50:
            text_rows.append(y)
    
    if not text_rows:
        return None
    
    # Group consecutive rows
    groups = []
    current = [text_rows[0]]
    for y in text_rows[1:]:
        if y == current[-1] + 1:
            current.append(y)
        else:
            groups.append(current)
            current = [y]
    groups.append(current)
    
    # Return the top of the first group (first line)
    return min(groups[0]) if groups else None

def create_marked_frame(frame_path, output_path, first_line_y, target_y):
    """Create a marked version of the frame showing subtitle position."""
    img = Image.open(frame_path)
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # Draw red line at detected first line position
    if first_line_y:
        draw.line([(0, first_line_y), (width, first_line_y)], fill='red', width=2)
        draw.text((10, first_line_y - 15), f"Detected: Y={first_line_y}", fill='red')
    
    # Draw green line at target position
    draw.line([(0, target_y), (width, target_y)], fill='green', width=2)
    draw.text((10, target_y - 15), f"Target: Y={target_y}", fill='green')
    
    img.save(output_path)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    test_cases = [
        ("1行字幕测试", 1, "line1"),
        ("2行字幕\\N第二行测试", 2, "line2"),
        ("3行字幕\\N第二行\\N第三行测试", 3, "line3"),
        ("4行字幕\\N第二行\\N第三行\\N第四行测试", 4, "line4"),
    ]
    
    print("=" * 70)
    print("验证抬高后的字幕位置 (抬高150px)")
    print("=" * 70)
    print(f"\n视频高度: {VIDEO_HEIGHT}px")
    print(f"目标底部边距: {BOTTOM_MARGIN}px (120 + 150)")
    print(f"目标第一行Y位置: {VIDEO_HEIGHT - BOTTOM_MARGIN}px")
    print()
    
    results = []
    
    for text, num_lines, name in test_cases:
        print(f"\n测试 {num_lines} 行字幕...")
        
        ass_path = os.path.join(OUTPUT_DIR, f"{name}.ass")
        video_path = os.path.join(OUTPUT_DIR, f"{name}.mp4")
        frame_path = os.path.join(OUTPUT_DIR, f"{name}.png")
        marked_path = os.path.join(OUTPUT_DIR, f"{name}_marked.png")
        
        # Create ASS
        center_y, target_y = create_test_ass(text, num_lines, ass_path)
        
        # Generate video
        if not generate_video(ass_path, video_path):
            print(f"  ❌ 视频生成失败")
            continue
        
        # Extract frame
        if not extract_frame(video_path, frame_path):
            print(f"  ❌ 帧提取失败")
            continue
        
        # Analyze
        actual_y = analyze_frame(frame_path)
        
        if actual_y is None:
            print(f"  ❌ 未检测到字幕")
            continue
        
        diff = actual_y - target_y
        
        # Create marked frame
        create_marked_frame(frame_path, marked_path, actual_y, target_y)
        
        results.append({
            'num_lines': num_lines,
            'center_y': center_y,
            'actual_y': actual_y,
            'target_y': target_y,
            'diff': diff,
            'marked_path': marked_path
        })
        
        status = "✅" if abs(diff) <= 5 else "❌"
        print(f"  {status} 中心Y: {center_y}, 实际第一行Y: {actual_y}, 偏差: {diff:+d}px")
        print(f"     标记帧: {marked_path}")
    
    # Summary
    print("\n" + "=" * 70)
    print("验证结果汇总")
    print("=" * 70)
    
    if len(results) >= 2:
        actual_positions = [r['actual_y'] for r in results]
        max_diff = max(actual_positions) - min(actual_positions)
        target_y = results[0]['target_y']
        
        print(f"\n目标第一行Y位置: {target_y}px")
        print(f"\n实际位置:")
        for r in results:
            print(f"  {r['num_lines']}行: Y={r['actual_y']} (偏差: {r['diff']:+d}px)")
        
        print(f"\n最大位置差异: {max_diff}px")
        
        if max_diff <= 5:
            print(f"\n✅ 验证成功！所有字幕第一行位置基本一致")
            print(f"   所有测试的第一行都在Y={target_y}±5px范围内")
        else:
            print(f"\n❌ 验证失败！不同行数的字幕位置不一致")
    else:
        print("\n❌ 测试数据不足")

if __name__ == "__main__":
    main()
