import sys
import os
import subprocess
import struct

def test_audio_profile(wav_path: str):
    print(f"Testing {wav_path}")
    cmd = [
        "ffmpeg", "-y", "-i", wav_path,
        "-f", "s16le", "-ac", "1", "-ar", "16000", "-"
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        print("FFmpeg failed")
        return
        
    content = proc.stdout
    n_samples = len(content) // 2
    fmt = f"<{n_samples}h"
    samples = struct.unpack(fmt, content)
    
    max_val = 32768.0
    framerate = 16000
    
    window_size = int(0.02 * framerate) # 20ms
    print("--- Audio Energy Profile (First 1s, 20ms steps) ---")
    
    for start_idx in range(0, min(len(samples), framerate), window_size):
        window = samples[start_idx : start_idx + window_size]
        if not window: break
        rms = (sum(s**2 for s in window) / len(window))**0.5 / max_val
        time_mark = start_idx / framerate
        bar = "#" * int(rms * 100)
        print(f"Time {time_mark:.3f}s: {rms:.4f} {bar}")

    threshold = 0.08
    required_sustained_samples = int(0.04 * framerate)
    for i in range(len(samples) - required_sustained_samples):
        window = samples[i : i + required_sustained_samples]
        rms = (sum(s**2 for s in window) / len(window))**0.5 / max_val
        if rms > threshold:
            offset = i / float(framerate)
            print(f">>> SUCCESS: Sustained speech detected at {offset:.3f}s (RMS: {rms:.4f})")
            return

test_audio_profile("outputs/autocut_project/narrations/narration_00.wav")
