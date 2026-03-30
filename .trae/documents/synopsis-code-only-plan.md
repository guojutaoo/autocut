## 目标与成功标准

把 `outputs/autocut_project/llm_input/synopsis.txt` 从“自然语言摘要 + 粗标签”改为“纯代码可计算字段”，让 LLM 通过 **首句 + 末句 + 高频词** 自己推断段落含义，同时提供更有信息量的数值型多模态特征；并把段落切分策略调整为更细粒度（目标 15–25 段，单段 ≤180s 且 ≤80 句）。

成功标准：

* `synopsis.txt` 不再包含自然语言“摘要/总结”，每段只包含可由代码直接算出的字段（首句/末句/高频词/数值特征等）。

* `export_for_llm.py` 的分段更细：默认 `gap_threshold=2.5`，并带“二级拆分”（max 180s / max 80 lines）。

* 产物尾部包含统计块（段数/段长/高分段/人物频次/音频峰值段）。

* 可在没有可选依赖（如 `cv2`/`librosa`/`jieba`）时优雅降级（字段留空或为 `null`/`0`，不阻塞导出）。

## 现状分析（基于代码检视）

当前导出脚本为 [export\_for\_llm.py](file:///Users/bytedance/Downloads/autocut/scripts/export_for_llm.py)：

* `parse_transcript()` 解析 `transcript_for_llm.txt`，得到 `VisionEvent` 与 `DialogueLine`。

* `segment_dialogues(dialogues, gap_threshold)` 以“台词时间间隙”做一次分组，默认 gap\_threshold=6.0。

* `build_segments()` 为每个组计算：

  * `keywords`：命中关键字列表；`score`：关键字权重和

  * `vision_tag/audio_tag/density_tag`：从台词 tags 里取众数

  * `people_in_shot`：从 `VisionEvent` 在段落窗口内聚合的 `pXX`

* `write_synopsis()` 当前写的是自然语言 preview（前三句拼接 + “共 N 句”）以及标签字符串（“静态/正常/密集”），不满足“code-only 字段”诉求。

依赖现状：

* `librosa` 已在仓库中作为可选依赖存在（见 [ingestor.py](file:///Users/bytedance/Downloads/autocut/src/ingestion/ingestor.py#L28-L54) 与 requirements）。

* `jieba` 当前仓库未引入（全库无引用），需要新增为可选依赖或提供降级分词实现。

* `cv2` 在导出脚本中已做可选导入（`_HAS_CV2`）。

## 拟做改动（实现方案）

### 1) 调整分段策略：gap\_threshold=2.5 + 二级拆分

文件： [export\_for\_llm.py](file:///Users/bytedance/Downloads/autocut/scripts/export_for_llm.py)

改动点：

* 将 `main()` 的 `--gap-threshold` 默认值从 `6.0` 改为 `2.5`（仅影响 llm\_input 导出）。

* 在 `segment_dialogues()` 得到的组基础上新增 `split_dialogue_group()`：

  * 输入：一个 `List[DialogueLine]`

  * 输出：多个子组，每个子组满足：

    * `duration <= 180s`（子组内 max(end)-min(start)）

    * `lines <= 80`

  * 切分规则（决定性、可复现）：

    * 线性扫描累积台词；一旦下一句会超出 `max_sec` 或 `max_lines`，就在“最后一个仍满足约束的位置”切分；

    * 若单句本身跨度导致无法满足，则强制以单句成段（避免死循环）。

* 在 `export_all()` 中，把初始 groups 通过二级拆分展开，再调用 `build_segments()`。

验收：

* `synopsis.txt` 的候选段落数明显增加，长段（如 15min/376句）会被拆到 ≤180s/≤80句。

### 2) 重写 synopsis 输出为 code-only 字段

文件： [export\_for\_llm.py](file:///Users/bytedance/Downloads/autocut/scripts/export_for_llm.py)

改动点：

* 重写 `write_synopsis()`：

  * 去掉自然语言“摘要/preview”。

  * 每段输出以下字段（全部可纯 Python 计算）：

    * `start/end/duration`

    * `lines`（句数）

    * `first_line`：`lines[0].text`

    * `last_line`：`lines[-1].text`

    * `keywords_hit`（命中的关键词列表）

    * `score`：`len(keywords_hit) / total_keywords`（并写出分子分母，便于人看）

    * `people_ids`：优先来自段内说话人标签（若能解析），否则使用 `people_in_shot`（现成）

    * `top_terms`：段内高频词 top 5–6（优先 jieba；否则降级为基于正则的 token 统计）

    * `frame_diff_mean`：段内帧差均值（cv2 可用且提供 video\_path 时计算，否则为 null）

    * `db_std`：段内音频 RMS 转 dB 后的标准差（librosa 可用且提供 video\_path 时计算，否则为 null）

    * `speech_rate`：段内总字数 / duration

    * `density_label`：按 speech\_rate 分档（<2 稀疏，2–4 正常，>4 密集），并保留数值

  * 多模态标签输出为“带数值”的格式（例如 `动态(frame_diff=0.065)`，`dB_std=9.7`），分档只做辅助标签不替代数值。

输出格式建议（保持 txt 便于快速阅读，同时字段易 parse）：

* 每段一行，`key=value` 组合；复杂字段用 JSON 子串，例如 `top_terms=["...", "..."]`。

### 3) 高频词（jieba + 停用词）实现与降级策略

文件： [export\_for\_llm.py](file:///Users/bytedance/Downloads/autocut/scripts/export_for_llm.py)

实现：

* `try import jieba` / `jieba.posseg`：

  * POS 可用时只取名词/动词（`n*`/`v*`），再 `Counter.most_common(6)`

  * 提供内置最小停用词集合（常用虚词/标点/语气词），并支持 `--stopwords <path>` 可选加载扩展（utf-8，每行一个）

* 若 jieba 不可用：

  * 降级：用正则提取连续中文/字母数字 token（长度>=2）做 Counter

  * 仍做停用词过滤

依赖管理：

* 将 `jieba` 添加到 `requirements.txt`（作为建议依赖；脚本仍需 try/except 以保证缺失时不崩）。

### 4) 帧差（frame\_diff）实现

文件： [export\_for\_llm.py](file:///Users/bytedance/Downloads/autocut/scripts/export_for_llm.py)

实现：

* 新增 `compute_frame_diff_mean(video_path, start, end, sample_sec=1.0)`：

  * 仅在 `_HAS_CV2` 且 `video_path` 存在时运行

  * 每 1s 抽一帧（或按段长自适应：短段 0.5s、长段 1–2s），用 `cv2.absdiff(prev, cur)` 计算 `mean(absdiff)/255`

  * 返回段内相邻帧差均值（浮点）

### 5) dB\_std（音频波动）实现

文件： [export\_for\_llm.py](file:///Users/bytedance/Downloads/autocut/scripts/export_for_llm.py)

实现优先级（高效且可复用）：

* 优先复用 [ingestor.py:get\_audio\_rms\_profile](file:///Users/bytedance/Downloads/autocut/src/ingestion/ingestor.py#L40-L54)：

  * 先对整条音轨算一次 `times/rms`（librosa 可用时）

  * 对每段按 `times` 截取子区间，`rms -> dB`，计算 `np.std(db)`

  * 同时可得到 `rms_max`，用于“音频峰值段”统计

* 若 audio analysis 不可用：字段为 `null`，并在尾部统计里说明“audio features skipped”

### 6) 人物字段（speaker/face id）与尾部统计块

人物：

* `people_ids`：

  * 优先从台词行文本解析“说话人标签”（例如 `张三：...` 这类；若不存在则为空）

  * 兜底使用 `people_in_shot`（现有的 `pXX` 聚合）

* 统计块输出：

  * 总段数、均段长、段长分布（min/avg/max）

  * 高分段列表（按 `score` Top N，含时间范围）

  * 人物出场频次（按 `people_ids` 或 `people_in_shot` Counter Top N）

  * 音频峰值段（按 `rms_max` Top N；若不可用则跳过）

## 需要改动的文件清单

* [scripts/export\_for\_llm.py](file:///Users/bytedance/Downloads/autocut/scripts/export_for_llm.py)

  * 默认 gap\_threshold=2.5

  * 增加二级拆分（max 180s / 80 lines）

  * 重写 synopsis 输出为 code-only 字段

  * 增加 top\_terms/jieba（可选）与 stopwords

  * 增加 frame\_diff\_mean（可选，cv2）

  * 增加 db\_std/rms\_max（可选，librosa，经 ingestor 复用）

  * 增加尾部统计块

* [src/cli/xhs\_autocut.py](file:///Users/bytedance/Downloads/autocut/src/cli/xhs_autocut.py)（如需）

  * 调整调用 exporter 时传入 `--gap-threshold 2.5`（使 llm\_input 的默认行为符合预期，即便主流程 gap\_threshold 不变）

* [requirements.txt](file:///Users/bytedance/Downloads/autocut/requirements.txt)（如需）

  * 增加 `jieba`（并保持脚本可选导入，避免强依赖）

## 兼容性与降级策略

* 无 `cv2`：不计算 `frame_diff_mean`，字段为 `null`；其余照常输出。

* 无 `librosa/numpy`：不计算 `db_std/rms_max`，字段为 `null`；其余照常输出。

* 无 `jieba`：`top_terms` 使用降级 tokenizer；或为空（取决于实现选择）。

## 验证步骤（实现后执行）

1. 重新运行导出：

   * `python3 scripts/export_for_llm.py --transcript outputs/autocut_project/transcript_for_llm.txt --video /path/to/video --out outputs/autocut_project/llm_input --gap-threshold 2.5`
2. 检查 `synopsis.txt`：

   * 不含“摘要/自然语言总结”

   * 每段都有 `first_line/last_line/top_terms` 等字段

   * 长段已被拆分到 ≤180s/≤80 句
3. 检查 `export_summary.json`（如同步更新）字段一致性。

