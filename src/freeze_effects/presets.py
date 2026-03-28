"""
Freeze Effect Presets
=====================
预定义的动效配置，可直接在 CLI 或 compose_plan.json 中引用。

每个 preset 包含：
- white_flash: 白闪配置
  - enabled: bool - 是否启用
  - duration_ms: int - 闪白持续时间（毫秒）
  - intensity: float - 强度 0.0-1.0

- zoom_in: 放大推进配置
  - enabled: bool - 是否启用
  - start_zoom: float - 起始缩放值
  - end_zoom: float - 结束缩放值
  - ease: str - 缓动函数 ('linear', 'ease_out', 'ease_in_out')

- stinger: 击中音效配置
  - enabled: bool - 是否启用
  - duration_ms: int - 音效持续时间
  - frequency: int - 音调 (Hz)
  - gain_db: float - 增益 (dB，负值表示衰减)
  - fade_out_ms: int - 淡出时间
"""

PRESETS = {
    "none": {
        "white_flash": {"enabled": False, "duration_ms": 0, "intensity": 0.0},
        "zoom_in": {"enabled": False, "start_zoom": 1.0, "end_zoom": 1.0, "ease": "linear"},
        "stinger": {"enabled": False, "duration_ms": 0, "frequency": 1000, "gain_db": 0.0, "fade_out_ms": 0},
    },

    "weibo_pop": {
        "white_flash": {"enabled": True, "duration_ms": 100, "intensity": 0.8},
        "zoom_in": {"enabled": True, "start_zoom": 1.0, "end_zoom": 1.06, "ease": "ease_out"},
        "stinger": {"enabled": True, "duration_ms": 120, "frequency": 1800, "gain_db": -6.0, "fade_out_ms": 80},
    },

    "cinematic": {
        "white_flash": {"enabled": True, "duration_ms": 150, "intensity": 0.6},
        "zoom_in": {"enabled": True, "start_zoom": 1.0, "end_zoom": 1.12, "ease": "ease_out"},
        "stinger": {"enabled": True, "duration_ms": 200, "frequency": 1200, "gain_db": -8.0, "fade_out_ms": 120},
    },

    "dramatic": {
        "white_flash": {"enabled": True, "duration_ms": 80, "intensity": 1.0},
        "zoom_in": {"enabled": True, "start_zoom": 1.0, "end_zoom": 1.15, "ease": "ease_in_out"},
        "stinger": {"enabled": True, "duration_ms": 150, "frequency": 2400, "gain_db": -4.0, "fade_out_ms": 100},
    },

    "subtle": {
        "white_flash": {"enabled": True, "duration_ms": 60, "intensity": 0.4},
        "zoom_in": {"enabled": True, "start_zoom": 1.0, "end_zoom": 1.03, "ease": "linear"},
        "stinger": {"enabled": False, "duration_ms": 0, "frequency": 1000, "gain_db": 0.0, "fade_out_ms": 0},
    },
}


def get_preset(name: str) -> dict:
    """Get a preset by name, return 'none' if not found."""
    return PRESETS.get(name, PRESETS["none"])


def list_presets() -> list:
    """Return list of available preset names."""
    return list(PRESETS.keys())
