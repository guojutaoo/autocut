# 微博风“定格特效（快闪+放大+音效）”实现计划

## 目标
在当前 AutoCut 的“Freeze 定格段”上实现类似你给的微博链接那种效果：
- 定格瞬间有 **快闪**（视觉白闪/亮度冲击）
- 定格期间有 **轻微放大推进**（Ken Burns/zoom-in）
- 定格瞬间有 **快闪音效**（stinger/击中音/“咔”一下）

并保持：
- 字幕/底部文案现有逻辑可继续工作（优先 Pillow 贴图方式）
- 音画对齐不被破坏（段落间无错位）
- 兼容不同 ffmpeg 构建（缺少 drawtext 也能跑）

## 现状梳理（基于代码）
- 每个 Segment 由 `pre + freeze + post` 三段组成；freeze 段是“截一张图 + loop 成视频 + 混音”。
- 段落拼接已经改为重编码 + concat filter，理论上可避免 PTS 造成的音画错位。
- 当前 overlay 文案：优先 Pillow 生成 `overlay.png`，再通过 ffmpeg overlay 叠加（而不是 drawtext）。
- ffmpeg 可能缺 drawtext；但 overlay/zoompan/fade 通常可用，需要做能力检测与降级。

相关代码位置：
- Freeze 段生成：`_build_segment_video()` in [ffmpeg_compose.py](file:///Users/bytedance/Downloads/autocut/src/render/ffmpeg_compose.py)
- 段落合成：`compose_segments_xhs()` in [ffmpeg_compose.py](file:///Users/bytedance/Downloads/autocut/src/render/ffmpeg_compose.py)
- CLI：`xhs_autocut.py`（目前作为通用 pipeline 使用）[xhs_autocut.py](file:///Users/bytedance/Downloads/autocut/src/cli/xhs_autocut.py)

## 实现方案（方案 A：纯 ffmpeg 滤镜实现，Pillow 仅负责字幕 PNG）

### 1) 定义“定格特效”参数（可配置 + 默认值）
在渲染侧增加一个 freeze effect 配置对象（先从 CLI 传入，后续也可落到 compose_plan.json）：
- `freeze_effect`: `"weibo_pop"`（开启该效果；默认关闭或保持现状）
- `flash_duration_ms`: 默认 100ms（白闪持续时间）
- `zoom_to`: 默认 1.06（定格期间从 1.0 缓慢推进到 1.06）
- `zoom_ease`: 线性或 ease-out（可先线性）
- `stinger_enable`: 默认 true
- `stinger_gain_db`: 默认 -6dB
- `stinger_duration_ms`: 默认 120ms

### 2) 视频侧：Freeze 段滤镜链（白闪 + zoom-in）
将 freeze 段从“静态 loop”升级为“动效 loop”，实现：
- **zoom-in**：使用 `zoompan` 或使用 `scale+crop` 的表达式来做推进
- **白闪**：用 `color=white` 叠加到画面上，并用 `fade` 做快速淡出

建议 filter_complex（概念表达，具体表达式在实现阶段微调）：
- 输入：
  - `[0:v]`：freeze_frame_img（loop）
  - `[2:v]`：overlay_png（Pillow 生成字幕）可选
- 处理：
  1. `[0:v]` 先应用 portrait 的 `scale+pad`（确保最终 1080x1920）
  2. 在 portrait 后应用 zoom（避免 zoom 后尺寸不一致）
  3. 生成 `color=white:s=1080x1920:d=flash_dur` 并 `fade` 快速衰减
  4. overlay 白闪：`overlay=enable='between(t,0,flash_dur)'`
  5. overlay 字幕 PNG：`overlay=0:0`（或按底部区域放置）

降级策略：
- 如果 ffmpeg 不支持 `zoompan`：仅做白闪（或直接退回原 freeze）
- 如果 ffmpeg 不支持 `fade`：仅做亮度提升 `eq=brightness=...:enable=...`

### 3) 音频侧：Freeze 段加入“快闪音效”
目标：在 freeze 段的起始瞬间，叠加一个短促的“击中音/咔哒音”，并与旁白/底噪混合。

实现思路（不依赖外部音效文件）：
- 用 ffmpeg 生成一个短音效流（stinger），如：
  - `sine`（高频短促）+ `afade` + `highpass/lowpass` + `volume`
  - 或 `anoisesrc`（噪声）+ `bandpass` + `afade`
- 将 stinger 与 freeze_mix_audio（背景音+旁白）进行 `amix`

filter_complex（概念表达）：
- `[base]`：现有 freeze_mix_audio
- `[st]`：`sine=f=1800:d=0.12` + `afade=t=out:d=0.08` + `volume=-6dB`
- `[base][st]amix=inputs=2:duration=first:dropout_transition=0[aout]`

降级策略：
- 如果 stinger 生成失败：只保留原有混音

### 4) 接口层：CLI 支持开关（最小改动）
在 `xhs_autocut.py` 增加参数（默认关闭或默认开启按你偏好，建议默认开启 weibo_pop）：
- `--freeze-effect weibo_pop|none`
- `--freeze-flash-ms 100`
- `--freeze-zoom 1.06`
- `--freeze-stinger / --no-freeze-stinger`

并把这些参数透传到渲染层（`compose_segments_xhs` / `_build_segment_video`）。

### 5) 计划文件（compose_plan.json）可选增强
为了让 LLM/人工可控，允许在每个 segment 里写：
- `freeze_effect`（可覆盖全局默认）
- `flash_ms/zoom_to/stinger_enable`（可覆盖）

并在 `--from-plan` 渲染模式下尊重这些配置。

## 验证方案
1. 用 `generate_sample_input.py` 生成样例视频，跑一次 `--render`，确认：
   - freeze 段有明显白闪 + 缓慢推进
   - freeze 起始有短促音效
2. 用真实视频跑一个短输出（target-duration 调小，如 30s）：
   - 检查段落交界处音画无错位
   - 检查字幕 PNG 仍能贴在底部
3. 兼容性测试：
   - 若 ffmpeg 缺某滤镜，日志提示降级但仍能出片

## 风险与应对
- 不同 ffmpeg 编译选项导致滤镜缺失：加入能力探测 + 降级路径，保证“能出片”优先。
- 音画错位：freeze 段与整片拼接统一用重编码 + `setpts/asetpts` + concat filter（已存在），并确保每个 seg 的 freeze/post 起点逻辑不重复偏移。
- 字幕绘制依赖字体：Pillow 继续使用 PingFang.ttc（若缺失再 fallback）。

## 交付物
- 新增/修改 CLI 参数：支持 weibo_pop 冻结特效与音效开关
- 渲染层实现：Freeze 段加入白闪 + zoom-in + stinger 混音
- 文档：更新 workflow_design.md 或 PROJECT_ANALYSIS.md 中对 freeze effect 的说明（可选）

