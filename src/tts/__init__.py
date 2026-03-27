"""TTS utilities for the Yongzheng autocut PoC.

This package currently exposes a thin wrapper around ``edge-tts`` with
best-effort, offline-friendly fallback to a short silent WAV file.
"""

from .tts_edge import synthesize  # noqa: F401
