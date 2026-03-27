"""Rendering and composition utilities for Yongzheng autocut PoC.

Currently exposes a minimal ffmpeg-based composer that can either:

* Execute real media composition when ``ffmpeg`` is available.
* Or, in environments without ``ffmpeg``, only emit a JSON "compose plan"
  describing the intended operations.
"""

from .ffmpeg_compose import compose_from_triggers, ComposeResult  # noqa: F401
