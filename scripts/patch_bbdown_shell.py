from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


def _backup(path: Path) -> None:
    if not path.exists():
        return
    suffix = time.strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak_bbdown_{suffix}")
    if not backup.exists():
        backup.write_bytes(path.read_bytes())


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _ensure_line(lines: list[str], line: str) -> list[str]:
    if any(l.strip() == line.strip() for l in lines):
        return lines
    if lines and lines[-1] and not lines[-1].endswith("\n"):
        lines[-1] = lines[-1] + "\n"
    lines.append(line if line.endswith("\n") else line + "\n")
    return lines


def _patch_zshrc(zshrc: Path) -> None:
    wanted = 'export PATH="$HOME/.dotnet/tools:$PATH"'

    if not zshrc.exists():
        zshrc.write_text(wanted + "\n", encoding="utf-8")
        return

    raw = _normalize_newlines(zshrc.read_text(encoding="utf-8", errors="ignore")).splitlines(True)
    out: list[str] = []
    changed = False

    for ln in raw:
        if ln.strip() == "~":
            changed = True
            continue
        if ln.strip().startswith('export PATH="/Users/bytedance/.dotnet/tools:'):
            changed = True
            continue
        out.append(ln)

    before = "".join(out)
    out = _ensure_line(out, wanted)
    after = "".join(out)
    if changed or after != before:
        _backup(zshrc)
        zshrc.write_text(after, encoding="utf-8")


def _detect_dotnet_root() -> str | None:
    candidates = [
        "/opt/homebrew/opt/dotnet/libexec",
        os.environ.get("DOTNET_ROOT") or "",
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def _patch_zprofile(zprofile: Path) -> None:
    dotnet_root = _detect_dotnet_root()
    wanted_path = 'export PATH="$HOME/.dotnet/tools:$PATH"'
    wanted_root = f'export DOTNET_ROOT="{dotnet_root}"' if dotnet_root else None
    wanted_root_arm = 'export DOTNET_ROOT_ARM64="$DOTNET_ROOT"'

    if not zprofile.exists():
        lines: list[str] = []
        if wanted_root:
            lines.append(wanted_root + "\n")
        lines.append(wanted_root_arm + "\n")
        lines.append(wanted_path + "\n")
        zprofile.write_text("".join(lines), encoding="utf-8")
        return

    raw = _normalize_newlines(zprofile.read_text(encoding="utf-8", errors="ignore")).splitlines(True)
    out: list[str] = []
    for ln in raw:
        if wanted_root and ln.strip().startswith("export DOTNET_ROOT="):
            continue
        out.append(ln)

    if wanted_root:
        out = _ensure_line(out, wanted_root)
    out = _ensure_line(out, wanted_root_arm)
    out = _ensure_line(out, wanted_path)

    merged = "".join(out)
    if merged != "".join(raw):
        _backup(zprofile)
        zprofile.write_text(merged, encoding="utf-8")


def main() -> int:
    home = Path.home()
    zshrc = home / ".zshrc"
    zprofile = home / ".zprofile"

    if shutil.which("dotnet") is None:
        return 2

    _patch_zshrc(zshrc)
    _patch_zprofile(zprofile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

