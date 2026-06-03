# 模型对比测试说明

本目录用于生成 deepseek 与 qwen 在“最终 PPT 文本生成”任务上的待评分材料。当前流程不自动给出评分结论，而是生成两个 Markdown 输出文件，之后可分别交给 GPT 和人工评分。

## 1. 测试目标

本测试覆盖完整生成链路：

```text
主题 -> 大纲 -> 知识补充 -> 最终文本
```

对比对象：

- `deepseek`
- `qwen`

默认输出：

```text
testing/model_comparison/outputs/deepseek_final_texts.md
testing/model_comparison/outputs/qwen_final_texts.md
```

这两个文件就是后续发给 GPT 评分、人工评分的主要材料。

## 2. 目录结构

```text
testing/model_comparison/
├── README.md
├── model_comparison_topics.json
├── outputs/
└── scripts/
    └── generate_final_text_outputs.py
```

各文件作用：

- `model_comparison_topics.json`：测试主题文件，后续增删主题只改这里。
- `scripts/generate_final_text_outputs.py`：批量生成最终文本的脚本。
- `outputs/`：脚本运行后保存 deepseek 和 qwen 的 Markdown 结果。

## 3. 修改测试主题

测试主题存放在：

```text
testing/model_comparison/model_comparison_topics.json
```

格式如下：

```json
[
  {
    "id": 1,
    "topic": "AI PPT 生成工具竞品分析与差异化定位",
    "capability": "竞品分析、结构化对比、产品逻辑归纳"
  }
]
```

字段说明：

- `id`：主题编号，必须是整数。
- `topic`：测试主题。
- `capability`：该主题主要考察的能力。

## 4. 运行前准备

在项目根目录执行命令：

```text
D:\NewStudy\universityGrade3-2\SEME\POGCC
```

确保已安装依赖：

```bash
pip install -r requirements.txt
```

确保项目根目录下存在 `config.json`，并配置好：

```json
{
  "deepseek_api_key": "你的 DeepSeek API Key",
  "dashscope_api_key": "你的阿里云百炼 API Key",
  "tavily_api_key": "你的 Tavily API Key",
  "llm_provider": "deepseek"
}
```

说明：

- 生成 deepseek 结果需要 `deepseek_api_key`。
- 生成 qwen 结果需要 `dashscope_api_key`。
- 知识补充会调用网络搜索，需要 `tavily_api_key`。

## 5. 先做 dry-run 检查

dry-run 只检查主题文件、参数和输出路径，不会调用模型或搜索 API。

```bash
python testing/model_comparison/scripts/generate_final_text_outputs.py --dry-run --max-topics 1 --providers deepseek qwen
```

看到类似输出即说明配置路径正常：

```text
Dry run only. No model/search API calls will be made.
Topic count: 1
Will write: testing/model_comparison/outputs/deepseek_final_texts.md
Will write: testing/model_comparison/outputs/qwen_final_texts.md
```

## 6. 小规模试跑

建议先只跑 1 个主题、1 个模型，确认 API Key、依赖和输出格式正常：

```bash
python testing/model_comparison/scripts/generate_final_text_outputs.py --max-topics 1 --providers deepseek
```

如果要试 qwen：

```bash
python testing/model_comparison/scripts/generate_final_text_outputs.py --max-topics 1 --providers qwen
```

试跑成功后检查：

```text
testing/model_comparison/outputs/deepseek_final_texts.md
testing/model_comparison/outputs/qwen_final_texts.md
```

## 7. 完整生成结果

确认小规模试跑成功后，运行完整 7 个主题、两个模型：

```bash
python testing/model_comparison/scripts/generate_final_text_outputs.py --providers deepseek qwen
```

默认每个主题生成 6 页。若要改为 5 页：

```bash
python testing/model_comparison/scripts/generate_final_text_outputs.py --providers deepseek qwen --pages 5
```

完整运行后会得到：

```text
testing/model_comparison/outputs/deepseek_final_texts.md
testing/model_comparison/outputs/qwen_final_texts.md
```

## 8. 输出文件内容

每个 Markdown 文件按主题组织，包含：

- provider 信息
- 测试主题
- 主要考察能力
- 大纲摘要
- 每页 slide 标题
- 每页 keyPoints
- 知识补充摘要
- 最终文本
- 生成状态和错误信息

如果某页生成失败，文件中会保留错误信息，方便后续分析。

## 9. 如何交给 GPT 评分

把下面其中一个文件发给 GPT：

```text
testing/model_comparison/outputs/deepseek_final_texts.md
testing/model_comparison/outputs/qwen_final_texts.md
```

推荐评分维度：

- 主题相关性
- 大纲遵循度
- 内容完整性
- 结构清晰度
- 知识补充利用程度
- 事实一致性风险
- PPT 展示可用性

可使用这样的评分提示词：

```text
请根据以下维度对这份 PPT 最终文本逐主题评分，每项 0-5 分，并给出简短理由：
1. 主题相关性
2. 大纲遵循度
3. 内容完整性
4. 结构清晰度
5. 知识补充利用程度
6. 事实一致性风险
7. PPT 展示可用性

请最后给出每个主题的总分、平均分、主要优点和主要问题。
```

人工评分时建议使用同一套维度，便于后续和 GPT 评分对齐。

## 10. 常用参数

```bash
python testing/model_comparison/scripts/generate_final_text_outputs.py [参数]
```

常用参数：

- `--topics-file`：指定主题文件，默认 `testing/model_comparison/model_comparison_topics.json`。
- `--providers`：指定模型，例如 `--providers deepseek qwen`。
- `--pages`：每个主题目标页数，默认 `6`。
- `--output-dir`：输出目录，默认 `testing/model_comparison/outputs`。
- `--max-topics`：只运行前 N 个主题，用于试跑。
- `--refine-knowledge`：启用完整知识整理流程，默认不启用。
- `--dry-run`：只检查配置，不调用 API。

## 11. 常见问题

### 缺少依赖

如果出现类似：

```text
ModuleNotFoundError: No module named 'langgraph'
```

说明依赖未安装完整，请执行：

```bash
pip install -r requirements.txt
```

### API Key 未配置

如果出现 deepseek、qwen 或 Tavily 相关配置错误，请检查项目根目录的 `config.json`。

### 运行时间较长

完整运行会对 7 个主题分别执行两个模型的完整流程，并且每页都会进行知识补充和最终文本生成，因此耗时较长，也会消耗 API 额度。建议先用 `--max-topics 1` 试跑。

### 输出文件过长

脚本默认会截断每页展示的知识补充摘要，避免 Markdown 文件过长。如需保留更多知识补充内容，可调整：

```bash
--knowledge-char-limit 3000
```

如果不想截断：

```bash
--knowledge-char-limit 0
```

## 12. 建议运行顺序

推荐按以下顺序获得最终结果：

```bash
python testing/model_comparison/scripts/generate_final_text_outputs.py --dry-run --max-topics 1 --providers deepseek qwen
python testing/model_comparison/scripts/generate_final_text_outputs.py --max-topics 1 --providers deepseek
python testing/model_comparison/scripts/generate_final_text_outputs.py --max-topics 1 --providers qwen
python testing/model_comparison/scripts/generate_final_text_outputs.py --providers deepseek qwen
```

最后使用 `outputs/` 下的两个 Markdown 文件进行 GPT 评分和人工评分。
