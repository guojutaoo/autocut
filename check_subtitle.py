#!/usr/bin/env python3
"""Check subtitle position in video frames."""
import subprocess
import os

video_path = "outputs/autocut_project/compose.mp4"
output_dir = "outputs/subtitle_check"
os.makedirs(output_dir, exist_ok=True)

# Extract frames at different timestamps
timestamps = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

for ts in timestamps:
    output_path = f"{output_dir}/frame_{ts:03d}.png"
    cmd = [
        "/Users/bytedance/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
        "-y",
        "-ss", str(ts),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Extracted frame at {ts}s: {output_path}")
    else:
        print(f"Failed to extract frame at {ts}s: {result.stderr}")

print(f"\nFrames saved to {output_dir}/")
print("Check these frames to see if subtitle position is consistent.")
