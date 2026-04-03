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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        transcript = os.path.join(td, "transcript_for_llm.txt")
        synopsis = os.path.join(td, "synopsis.txt")
        skill1 = os.path.join(td, "skill1_output.json")
        out_dir = os.path.join(td, "llm_step2")

        _write(
            transcript,
            "\n".join(
                [
                    "[00:00:00,500 - 00:00:01,000] 台词：“上一句” | 【台词密度：低】",
                    "[00:00:02,000 - 00:00:03,000] 台词：“核心句一” | 【台词密度：高】",
                    "[00:00:03,200 - 00:00:04,000] 台词：“核心句二” | 【台词密度：高】",
                    "[00:00:05,000 - 00:00:06,000] 台词：“下一句” | 【台词密度：低】",
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
                        "start": "00:00:02",
                        "end": "00:00:04",
                        "duration": 2.0,
                        "render_type": "freeze",
                        "anchor_time": "00:00:03",
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
            "--skill1",
            skill1,
            "--out",
            out_dir,
            "--no-frames",
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

        ctx = os.path.join(out_dir, "seg_01_context.txt")
        mf = os.path.join(out_dir, "step2_manifest.json")
        bundle = os.path.join(out_dir, "seg_01_bundle.md")
        all_md = os.path.join(out_dir, "step2_all.md")
        assert os.path.exists(ctx)
        assert os.path.exists(mf)
        assert os.path.exists(bundle)
        assert os.path.exists(all_md)
        with open(ctx, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# 核心范围: [00:00:02 — 00:00:04]" in content
        assert "▶ [00:00:02 -> 00:00:03]" in content
        assert "▶ [00:00:03 -> 00:00:04]" in content
        assert "[00:00:00 -> 00:00:01]" in content
        assert "[00:00:05 -> 00:00:06]" in content

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
