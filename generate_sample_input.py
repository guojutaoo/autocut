"""Generate a tiny synthetic video + subtitles for local smoke tests.

This script is intentionally self-contained and does not download any assets.
It creates:
- outputs/sample_input/sample.avi
- outputs/sample_input/sample.srt

The video is designed to have a high-contrast segment around ~2s so that the
placeholder vision analyzer can generate intensity peaks.
"""

from __future__ import annotations

import os


def main() -> None:
    import cv2  # type: ignore
    import numpy as np

    out_dir = os.path.join("outputs", "sample_input")
    os.makedirs(out_dir, exist_ok=True)

    video_path = os.path.join(out_dir, "sample.avi")
    srt_path = os.path.join(out_dir, "sample.srt")

    fps = 25
    duration_sec = 6
    width, height = 640, 360
    total_frames = fps * duration_sec

    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter for {video_path}")

    for i in range(total_frames):
        t = i / fps
        if 1.8 <= t <= 2.6:
            # High contrast block: checkerboard
            block = 40
            yy, xx = np.indices((height, width))
            checker = ((yy // block + xx // block) % 2) * 255
            frame = np.stack([checker, checker, checker], axis=-1).astype(np.uint8)
            cv2.putText(
                frame,
                "SHENGZHI / DUODI",
                (30, 180),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 0, 255),
                3,
                cv2.LINE_AA,
            )
        else:
            # Low contrast background
            gray = 120 + int(20 * np.sin(t * 2.0))
            frame = np.full((height, width, 3), gray, dtype=np.uint8)
            cv2.putText(
                frame,
                f"t={t:.2f}s",
                (30, 180),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (200, 200, 200),
                2,
                cv2.LINE_AA,
            )

        writer.write(frame)

    writer.release()

    # Create a tiny SRT that includes keywords from configs/default.yaml.
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(
            """1\n00:00:01,900 --> 00:00:02,700\n皇上，这道圣旨要宣了。\n\n2\n00:00:02,700 --> 00:00:03,300\n此处夺嫡之争出现反转。\n\n3\n00:00:04,200 --> 00:00:05,000\n交接兵权，风向变了。\n\n"""
        )

    print("Generated:", os.path.abspath(video_path))
    print("Generated:", os.path.abspath(srt_path))


if __name__ == "__main__":
    main()
