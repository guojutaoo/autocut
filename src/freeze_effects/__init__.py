"""
Freeze Effects Module
=====================
独立动效模块，为 AutoCut 的 freeze 定格段提供视觉效果和音效增强。

支持的效果：
- 白闪 (white_flash): 定格瞬间的画面闪白
- 放大推进 (zoom_in): Ken Burns 式的缓慢放大效果
- 击中音效 (stinger): 短促的"咔"声

使用方式：
1. 在 CLI 参数中指定 effect_preset
2. 效果在全局视频维度应用，所有 freeze 段共享同一动效配置
"""
from .engine import FreezeEffectEngine, load_effect_preset
from .presets import PRESETS

__all__ = ["FreezeEffectEngine", "load_effect_preset", "PRESETS"]
