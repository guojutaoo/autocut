# 雍正王朝多模态触发自动剪辑 PoC

本项目是一个基于 Python 的多模态触发自动剪辑最小可运行样例，用于验证《雍正王朝》这类长篇剧集的“情绪/事件触发 → 定格 + 文案总结”等自动剪辑链路。

- 语言与环境：Python 3.9+
- 依赖：见 `requirements.txt`（仅使用常见开源库；情绪识别模型为可选）
- 运行方式：离线批处理，不依赖外网下载数据；如需使用 DeepFace/FER 等模型，请预先在可联网环境中完成安装与模型缓存。

## 目录结构

```text
project/yongzheng_autocut/
  src/
    ingestion/          # 读取视频、提取音频、加载字幕
    vision/             # 人脸/视觉事件分析（DeepFace 可选，含占位降级逻辑）
    audio/              # BGM 节拍与强度分析（librosa）
    text/               # 台词关键词触发
    fusion/             # 多模态触发融合、平滑与迟滞
    actions/            # 剪辑动作映射（定格帧导出、JSON 产物）
    cli/                # 命令行入口 main.py
  configs/
    default.yaml        # 门限、权重、启用开关等配置
  tests/
    test_fusion_basic.py  # 最小化示例单元测试
  requirements.txt
  README.md
```

## 安装步骤

1. 建议使用虚拟环境：

```bash
cd project/yongzheng_autocut
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\\Scripts\\activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. （可选）安装视觉情绪识别库：

```bash
# 仅在需要启用 DeepFace / FER 表情识别时安装
pip install deepface fer
```

> 注意：DeepFace/FER 首次使用时可能需要下载预训练模型，如当前环境无外网，请在可联网环境中预先完成模型下载和缓存，或保持 `configs/default.yaml` 中 `vision.use_deepface: false` 使用内置占位逻辑。

## 运行示例

在项目根目录下执行：

```bash
cd project/yongzheng_autocut
python -m src.cli.main \
  --video path/to/your_video.mp4 \
  --config configs/default.yaml \
  --out outputs/demo_run
```

参数说明：
- `--video`：输入视频路径，本地 `mp4`/`mov` 等常见格式，建议包含音频轨；
- `--config`：YAML 配置文件路径，可基于 `configs/default.yaml` 修改；
- `--out`：输出目录路径（若不存在会自动创建），本例为 `outputs/demo_run`。

运行完成后，输出目录包含：

- `outputs/demo_run/triggers.json`：融合后的触发事件列表，每个事件包含时间码、类型、置信度和来源模态等信息；
- `outputs/demo_run/frames/*.jpg`：为触发事件导出的定格帧图片，可用于后续剪辑/包装；
- `outputs/demo_run/run_summary.json`：本次运行的概要信息（输入、配置、触发数量、导出帧数量等）。

## 配置说明（configs/default.yaml）

`configs/default.yaml` 提供了一个可直接运行的默认配置，你可以根据需要调整：

- `vision`：
  - `use_deepface`：是否启用 DeepFace 表情识别；为 `false` 时使用简单对比度占位逻辑；
  - `frame_stride`：视觉分析的帧抽样步长，数值越大分析越稀疏；
  - `intensity_threshold`：视觉占位强度阈值，用于筛选高对比度帧；
- `audio`：
  - `enabled`：是否启用音频分析；
  - `min_intensity`：归一化 RMS 强度阈值，高于该值的窗视为情绪/节奏上扬；
- `text`：
  - `enabled`：是否启用字幕关键词触发；
  - `keywords`：关键词列表及其权重，用于在台词/字幕中打点；
- `fusion`：
  - `weights`：视觉/音频/文本三类事件在融合时的权重；
  - `threshold_on`/`threshold_off`：迟滞开启/关闭门限；
  - `cooldown_sec`：触发冷却时间，避免频繁触发；
- `actions`：
  - `freeze_frame.enabled`：是否导出定格帧图片。

你可以复制一份 `default.yaml` 为新的配置文件，独立调节不同策略组合：

```bash
cp configs/default.yaml configs/your_experiment.yaml
# 编辑 your_experiment.yaml 后：
python -m src.cli.main \
  --video path/to/your_video.mp4 \
  --config configs/your_experiment.yaml \
  --out outputs/exp_your_name
```

## 流程概览

1. **Ingestion**：
   - 使用 OpenCV 读取视频帧（带步长抽样）；
   - 使用 pydub 尝试从视频中提取音频为 WAV（失败则退回用视频路径做音频分析或直接跳过）；
   - 若存在同名 `.srt` 字幕文件，则加载为台词序列。
2. **Vision**：
   - 若配置启用 DeepFace 且已安装，则按配置帧率进行表情识别，输出情绪事件；
   - 否则使用灰度图标准差作为简单视觉强度指标，输出 `vision_intensity_peak` 事件。
3. **Audio**：
   - 使用 librosa 分析 BGM 的 onset（节拍）和 RMS（强度），输出 `audio_beat` 与 `audio_intensity_peak` 事件。
4. **Text**：
   - 在每条字幕中匹配关键词，按关键词权重输出 `text_keyword` 事件。
5. **Fusion**：
   - 对多模态事件按时间排序，使用指数衰减 + 权重加权 + 迟滞门限与冷却时间生成稳定触发；
   - 输出统一的触发列表，事件类型默认为 `freeze_frame`。
6. **Actions**：
   - 将触发点映射为定格帧导出位置，写出 `frames/*.jpg`；
   - 同时持久化 `triggers.json`（可被下游剪辑/包装工具消费）。

## LLM Step2 导出（Skill 2 Segment Writer 输入）

当你已经拿到 LLM Skill 1 的选段清单（`skill1_output.json`，字段形态与 `outputs/step2.json` 一致）后，可以用 `scripts/export_step2.py` 把“逐字稿 + 视频 + Skill1 选段”导出为 Skill 2 所需的每段上下文与 5 张关键帧截图。

输出目录结构（示例 `llm_step2/`）：

```text
llm_step2/
  skill1_output.json
  step2_manifest.json
  seg_01_context.txt
  seg_01_frame_1.jpg
  seg_01_frame_2.jpg
  seg_01_frame_3.jpg
  seg_01_frame_4.jpg
  seg_01_frame_5.jpg
  ...
```

示例命令：

```bash
./step2_llm.sh \
  --transcript transcript_for_llm.txt \
  --synopsis synopsis.txt \
  --video 雍正王朝_EP01.mp4 \
  --skill1 skill1_output.json
```

`--synopsis` 当前不参与生成逻辑，可不传；但传入时会校验文件存在性。

如果只想验证文本与清单（不抽帧），可加 `--no-frames`。

如果不传 `--out`，默认输出到 `outputs/step2/${video文件名去扩展名}`。

## 测试与验证

项目提供一个最小化示例测试（主要覆盖融合逻辑）：

```bash
cd project/yongzheng_autocut
python -m compileall src  # 快速检查语法
python tests/test_fusion_basic.py  # 简单运行示例测试
```

你可以在本地准备一段短的《雍正王朝》片段（或任意剧情视频），配上同名 `.srt` 字幕文件，结合不同配置观察触发点与定格帧的变化效果。

## 合成渲染与 TTS

本 PoC 在多模态触发基础上，提供了一个“定格 + 旁白”的最小合成能力：

1. 触发检测阶段仍通过 `src.cli.main` 入口执行，输出 `triggers.json` 和定格帧；
2. 合成阶段通过 `src.cli.compose` 入口，读取源视频与触发清单，按每个 `freeze_frame` 触发生成“0.8s 前镜头 + 1.2s 定格 + 0.8s 后镜头”的高光片段，并在定格段上叠加可选旁白音频（包含对原音轨的简单 ducking，降低约 8 dB）。

### 依赖与降级行为

- **ffmpeg**：
  - 若系统 PATH 中存在 `ffmpeg`，`compose` CLI 会实际调用 ffmpeg 生成 `compose.mp4`；
  - 若未安装 `ffmpeg`，则无法生成 `compose.mp4`。
- **edge-tts（可选）**：
  - 当已安装 `edge-tts` 且环境可访问对应服务时，`src.tts.tts_edge.synthesize` 会生成真实 TTS 旁白音频；
  - 当未安装或无法访问服务时，会自动回退为一段 0.5s 静音 WAV，以保证流水线在离线环境下也能完整跑通。

### 合成示例命令

先运行分析阶段（示例，生成 `outputs/demo_run2`）：

```bash
cd project/yongzheng_autocut
python -m src.cli.main \
  --video outputs/sample_input/sample.avi \
  --config configs/demo.yaml \
  --out outputs/demo_run2
```

然后运行合成阶段（不指定目标时长，使用默认的 0.8/1.2/0.8 模板）：

```bash
cd project/yongzheng_autocut
python -m src.cli.compose \
  --video outputs/sample_input/sample.avi \
  --triggers outputs/demo_run2/triggers.json \
  --out outputs/final_demo \
  --narration "这一段是权谋博弈的核心转折，皇上宣旨导致兵权重新分配。"
```

输出说明：

- `outputs/final_demo/compose.mp4`：当 ffmpeg 可用时生成的合成成片。

### 目标时长调度（示例：5 分钟）

如果希望生成一条约 5 分钟的解说高光，可以在合成阶段额外指定 `--target-duration`（单位为秒）。例如：

```bash
cd project/yongzheng_autocut
python -m src.cli.compose \
  --video outputs/sample_input/sample.avi \
  --triggers outputs/demo_run2/triggers.json \
  --out outputs/final_5min \
  --narration "这一段是权谋博弈的核心转折，皇上宣旨导致兵权重新分配。" \
  --target-duration 300
```

此时片段会按触发时间顺序累计，直到接近目标时长，最后一段的 `post` 可能被自动缩短以贴合目标。

另外，`configs/compose_5min.yaml` 提供了一个只包含 `target_duration_sec: 300` 的配置样例，方便在项目或上层编排中约定目标时长。

## 小红书一条命令出片（xhs_autocut）

在前述分析与合成能力之上，项目提供了一个面向“小红书风格解说视频”的一条命令入口 `xhs_autocut`：

```bash
cd project/yongzheng_autocut
python -m src.cli.xhs_autocut \
  --video outputs/sample_input/sample.avi \
  --out outputs/xhs_demo \
  --target-duration 300 \
  --portrait 1080x1920 \
  --title-prefix "雍正王朝权谋解析" \
  --hashtags "#雍正王朝 #权谋 #历史"
```

### 依赖说明

- **Python 3.9+**：基础运行环境。
- **edge-tts（可选）**：
  - 已安装且可用时，会为每个剧情段生成真实的中文解说旁白 `narration_*.wav`；
  - 未安装或网络不可用时，会自动回退到 0.5 秒静音 WAV，占位不影响整体流程跑通。
- **ffmpeg（可选）**：
  - 已安装时，会实际调用 ffmpeg 生成竖屏 9:16 成片 `compose_xhs.mp4`；
  - 未安装时，无法生成 `compose_xhs.mp4`，但仍会产出音频/封面/文案等素材。

### 输出产物结构示例

以上命令运行完成后，`--out` 目录（示例为 `outputs/xhs_demo`）下会包含：

- `compose_xhs.mp4`（仅在安装了 ffmpeg 的机器上生成）：
  - 已按 9:16 竖屏裁剪/缩放的合成成片，包含“剧情 + 定格 + 旁白叠加”的高光串联。
- `cover.jpg`：
  - 封面图，默认取首个入选故事段的中间帧作为定格画面。
- `xhs_caption.txt` / `caption.txt`：
  - 推荐文案，内容结构为：
    - 第一行：标题（示例：`雍正王朝权谋解析｜这一段，其实是在用圣旨逼人表态`）；
    - 第二行：话题/标签（示例：`#雍正王朝 #权谋 #历史`）；
    - 第三行：摘要（示例：`摘要：这一段台词看似客气，其实每一句都在试探底线。`）。
- `narration_*.wav`：
  - 每个故事段对应的一段旁白音频，文件名按顺序编号，例如 `narration_00.wav`、`narration_01.wav` 等。

### 发布到小红书的推荐步骤

1. 在本地或有 GUI 的环境中打开 `compose_xhs.mp4`，确认整体节奏和画面效果；
2. 在小红书创建新笔记，上传 `compose_xhs.mp4` 作为视频内容；
3. 在封面选择界面，上传或选择本目录下的 `cover.jpg` 作为封面图；
4. 打开 `xhs_caption.txt` 或 `caption.txt`，将标题、话题和摘要按需复制到小红书的标题和正文区域，可根据平台字数限制做少量微调；
5. 如需二次精修旁白或加字幕，可在剪辑软件中基于 `narration_*.wav` 做进一步包装，再导出上传。

通过这一入口，你可以在**一条命令**下获得一整套“小红书可发片”的核心素材，在无 ffmpeg / edge-tts 的环境中也会自动退化为“静音旁白 + 封面 + 文案”的形态，保证链路始终可跑通。

## 已知限制

- 本 PoC 不包含任何预训练情绪/事件识别模型，仅提供调用 DeepFace/FER 的可选入口；
- 音频侧仅输出节拍与强度特征，不做精细的情绪标签分类；
- 剪辑动作目前提供了“定格帧导出 + 简单高光合成（定格 + 旁白叠加）”的最小可运行版本；更复杂的转场、字幕动画、多轨混音等仍需由后续剪辑流水线实现。
