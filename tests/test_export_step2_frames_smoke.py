import json
import os
import subprocess
import sys
import tempfile


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _make_video(path: str) -> None:
    import numpy as np  # type: ignore
    import cv2  # type: ignore

    w, h = 320, 180
    fps = 25
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    if not out.isOpened():
        raise RuntimeError("VideoWriter open failed")
    try:
        for i in range(fps * 3):
            img = np.zeros((h, w, 3), dtype=np.uint8)
            img[:] = (i % 255, (i * 2) % 255, (i * 3) % 255)
            out.write(img)
    finally:
        out.release()


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        transcript = os.path.join(td, "transcript_for_llm.txt")
        synopsis = os.path.join(td, "synopsis.txt")
        skill1 = os.path.join(td, "skill1_output.json")
        video = os.path.join(td, "sample.avi")
        out_dir = os.path.join(td, "llm_step2")

        _make_video(video)
        _write(
            transcript,
            "\n".join(
                [
                    "[00:00:00,500 - 00:00:01,000] 台词：“上一句” | 【台词密度：低】",
                    "[00:00:01,500 - 00:00:02,000] 台词：“核心句一” | 【台词密度：高】",
                    "[00:00:02,100 - 00:00:02,700] 台词：“核心句二” | 【台词密度：高】",
                    "[00:00:02,800 - 00:00:03,000] 台词：“下一句” | 【台词密度：低】",
                    "",
                ]
            ),
        )
        _write(synopsis, "dummy\n")
        _write_json(
            skill1,
            {
                "episode": "E01",
                "total_segments": 1,
                "selected_segments": 1,
                "segments": [
                    {
                        "index": 1,
                        "order": 1,
                        "start": "00:00:01",
                        "end": "00:00:03",
                        "duration": 2.0,
                        "render_type": "freeze",
                        "anchor_time": "00:00:02",
                        "bridge_note": "(开篇段，无需桥接)",
                        "one_line_summary": "摘要",
                        "context_file": "seg_01_context.txt",
                        "frame_files": [
                            "seg_01_frame_1.jpg",
                            "seg_01_frame_2.jpg",
                            "seg_01_frame_3.jpg",
                            "seg_01_frame_4.jpg",
                            "seg_01_frame_5.jpg",
                        ],
                    }
                ],
            },
        )

        cmd = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), "..", "scripts", "export_step2.py"),
            "--transcript",
            transcript,
            "--synopsis",
            synopsis,
            "--video",
            video,
            "--skill1",
            skill1,
            "--out",
            out_dir,
        ]
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env = dict(os.environ)
        env["PYTHONPATH"] = repo_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

        for i in range(1, 6):
            assert os.path.exists(os.path.join(out_dir, f"seg_01_frame_{i}.jpg"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
