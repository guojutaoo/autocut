"""
Freeze Effects Usage Examples
============================

本文件展示如何在不同场景下使用 freeze_effects 动效模块。
"""

def example_1_list_presets():
    from .presets import list_presets
    print("=" * 60)
    print("示例 1: 列出所有可用的动效预设")
    print("=" * 60)
    presets = list_presets()
    print(f"可用预设: {presets}")
    print()


def example_2_load_preset():
    from . import load_effect_preset
    print("=" * 60)
    print("示例 2: 加载预设并查看配置")
    print("=" * 60)
    config = load_effect_preset("weibo_pop")
    print(f"weibo_pop 预设配置:")
    print(f"  白闪: enabled={config.white_flash.enabled}, "
          f"duration_ms={config.white_flash.duration_ms}, "
          f"intensity={config.white_flash.intensity}")
    print(f"  放大推进: enabled={config.zoom_in.enabled}, "
          f"start={config.zoom_in.start_zoom}, "
          f"end={config.zoom_in.end_zoom}, "
          f"ease={config.zoom_in.ease}")
    print(f"  击中音效: enabled={config.stinger.enabled}, "
          f"freq={config.stinger.frequency}Hz, "
          f"gain={config.stinger.gain_db}dB")
    print()


def example_3_custom_config():
    from . import FreezeEffectEngine
    print("=" * 60)
    print("示例 3: 自定义动效配置")
    print("=" * 60)
    custom_config = {
        "white_flash": {"enabled": True, "duration_ms": 80, "intensity": 0.9},
        "zoom_in": {"enabled": True, "start_zoom": 1.0, "end_zoom": 1.1, "ease": "ease_out"},
        "stinger": {"enabled": True, "duration_ms": 100, "frequency": 2000, "gain_db": -5.0, "fade_out_ms": 60},
    }
    engine = FreezeEffectEngine(custom_config)
    print(f"自定义配置已加载")
    print(f"  白闪: {engine.config.white_flash}")
    print(f"  放大推进: {engine.config.zoom_in}")
    print(f"  击中音效: {engine.config.stinger}")
    print()


def example_4_build_filters():
    from . import FreezeEffectEngine
    print("=" * 60)
    print("示例 4: 构建 ffmpeg 滤镜链")
    print("=" * 60)
    engine = FreezeEffectEngine("weibo_pop")

    duration = 2.0
    fps = 30
    w, h = 1080, 1920

    video_filter = engine.build_video_filter_simple(duration, fps, w, h)
    print(f"视频滤镜链:\n  {video_filter}")

    audio_filter = engine.build_audio_filter(duration)
    print(f"\n音频滤镜链:\n  {audio_filter}")
    print()


def example_5_compare_presets():
    from . import load_effect_preset
    print("=" * 60)
    print("示例 5: 对比不同预设的效果参数")
    print("=" * 60)
    preset_names = ["none", "weibo_pop", "cinematic", "dramatic", "subtle"]
    for name in preset_names:
        config = load_effect_preset(name)
        print(f"\n{name}:")
        print(f"  白闪: duration={config.white_flash.duration_ms}ms, "
              f"intensity={config.white_flash.intensity}")
        print(f"  放大: {config.zoom_in.start_zoom} -> {config.zoom_in.end_zoom} "
              f"({config.zoom_in.ease})")
        print(f"  音效: {'启用' if config.stinger.enabled else '禁用'}, "
              f"{config.stinger.frequency}Hz, {config.stinger.gain_db}dB")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Freeze Effects 动效模块使用示例")
    print("=" * 60 + "\n")

    example_1_list_presets()
    example_2_load_preset()
    example_3_custom_config()
    example_4_build_filters()
    example_5_compare_presets()

    print("\n" + "=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)

    print("\n使用方式：")
    print("-" * 60)
    print("from src.render.ffmpeg_compose import compose_segments_xhs")
    print("")
    print("# 在调用 compose_segments_xhs 时，通过 freeze_effect 参数启用动效")
    print("result = compose_segments_xhs(")
    print("    video_path='input.mp4',")
    print("    segments=segments_list,")
    print("    narration_audios=narration_list,")
    print("    out_dir='output/',")
    print("    freeze_effect='weibo_pop',  # <-- 只需这一行启用动效")
    print(")")
