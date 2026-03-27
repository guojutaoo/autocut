# AutoCut & LLM 协作工作流设计方案

为了解决目前解说文案“机械化、非剧情重点”的问题，我们需要从“全自动”转向“AI 辅助半自动”的工作流。以下是三种方案的调研与对比：

## 方案一：基于台词片段的解说重写流 (本项目目前推荐)

**核心思想**：由 AutoCut 负责从海量视频中根据“台词关键词”和“画面强度”初筛出候选片段，并导出该片段的**原始台词剧本**。用户将此剧本发给 AIME 或其他 LLM，由 LLM 重新创作解说词，最后由 AutoCut 负责渲染。

- **优势**：保证解说词的人文深度和剧情逻辑，同时节省了手动找素材的时间。
- **AutoCut 提供的素材**：
  - `candidate_segments.json`：包含每个片段的起始时间、原始台词、关键词命中情况。
  - `segment_previews/`：该片段的关键帧截图，帮助 LLM 理解画面内容。
- **用户提供的素材**：
  - `final_script.json`：经过 LLM 润色后的解说词及对应的片段序号。

## 方案二：全局剧情概要重构流 (面向深度长视频)

**核心思想**：AutoCut 将全集视频的字幕进行分段摘要，生成一个全集的“剧情脉络图”。用户要求 LLM 基于这个脉络图挑选出几个最能体现“权谋”的时刻，并写出串联起来的剧本。

- **优势**：成片具有极强的整体感，不再是零碎的卡点。
- **工作流**：
  1. AutoCut 提取全集字幕并做聚类。
  2. LLM 决定哪些段落应该入选，并给出“入选理由”和“串联词”。
  3. 用户将 LLM 的建议反馈给 AutoCut 进行精准剪辑。

---

## 方案一执行细节 (The AIME Workflow)

### 步骤 1：AutoCut 准备素材
运行 `sh build.sh` 后，系统会自动在 `outputs/` 下生成：
- `xhs_caption.txt` (包含原始台词的摘要)
- `compose_plan_xhs.json` (包含每个片段的 `subtitle_texts`)

### 步骤 2：脚本专家创作
将上述文件内容复制给任意 LLM（如 ChatGPT, Claude, DeepSeek 等），并参考 `.trae/skills/video-script-expert.md` 的规范。LLM 会输出一个格式严谨的剧本。

### 步骤 3：AutoCut 最终渲染
将 AIME 生成的文案填回 `compose_plan_xhs.json` 的 `narration_text` 字段，重新执行渲染。
