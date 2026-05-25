# POGCC 后端应用

## 目录结构

```
app/
├── api/                # API接口层
│   ├── __init__.py
│   └── routes/        # API路由
│       ├── __init__.py
│       ├── rag.py          # 知识查询 路由（查询知识、上传文档）
│       ├── generator.py    # 生成 路由（生成大纲、补全内容）
│       ├── model.py        # 模型管理 路由（获取/切换模型）
│       ├── search.py       # 搜索 路由（网络知识搜索）
│       └── health.py       # 健康检查
├── core/               # 核心逻辑
│   ├── __init__.py
│   ├── knowledge_agent/    # 知识 Agent 核心模块
│   │   ├── __init__.py
│   │   ├── agent.py            # KnowledgeAgent 主流程（LangGraph 状态图）
│   │   ├── search_agent.py     # 自我规划网络搜索 Agent
│   │   ├── query_processor.py  # 查询处理器
│   │   └── result_generator.py # 结果生成器
│   ├── generator/          # 生成模块
│   │   ├── __init__.py
│   │   ├── outline_maker.py     # 大纲生成
│   │   └── content_expander.py  # 内容补全
│   ├── document_parser.py  # 文档解析（Word/PDF）
│   └── faiss_db.py         # 向量数据库
├── prompts/              # 提示词模板
│   ├── __init__.py
│   └── templates.py      # 提示词模板（大纲/内容/RAG/搜索规划/评估/整理）
├── schema/              # Pydantic 模型
│   ├── __init__.py
│   └── models.py         # 数据模型
├── services/            # 服务层
│   ├── __init__.py
│   ├── llm_service.py        # LLM 服务工厂（支持运行时切换模型）
│   ├── deepseek_service.py   # DeepSeek 服务（官方 OpenAI 兼容接口）
│   ├── qwen_service.py       # Qwen 服务（阿里云百炼）
│   └── web_search_service.py # 网络搜索服务（Tavily API）
└── utils/               # 工具类
    ├── __init__.py
    ├── config.py        # 配置管理（统一读取 config.json）
    └── errors.py        # 错误处理
```

## 核心功能

### 1. 知识 Agent（KnowledgeAgent）

基于 LangGraph 状态图实现的知识检索与回答生成流程：

```
process_query → retrieve_knowledge → generate_answer → END
                     │
                     └── 内部调用 SearchAgent（自我规划网络搜索）
                         plan_searches → execute_search → evaluate_knowledge
                                                              │
                                                     不充分 → execute_search（补充搜索）
                                                     充分   → summarize_knowledge → 返回知识摘要
```

- **查询处理**：清洗和扩展用户查询
- **知识检索**：通过网络搜索 Agent 自我规划检索外部知识（本地知识库待集成）
- **结果生成**：基于检索到的知识生成回答

### 2. 网络搜索 Agent（SearchAgent）

具备自我规划能力的知识检索链路：

- **规划搜索**：LLM 分析主题，自动生成多个搜索关键词，覆盖不同维度
- **执行搜索**：通过 Tavily API 搜索网络，获取相关网页内容
- **评估充分性**：LLM 判断已收集的知识是否充分，决定是否需要补充搜索
- **补充搜索**：知识不充分时，LLM 生成新的搜索词继续搜索（最多 3 轮）
- **整理知识**：将搜索结果整理为结构化的知识摘要

### 3. 生成模块

- **大纲生成**：根据用户需求生成PPT大纲结构
- **内容补全**：基于大纲节点扩写详细内容

### 4. 文档解析

- **Word解析**：解析.docx和.doc文件
- **PDF解析**：解析.pdf文件

### 5. 向量数据库

- **文档存储**：存储文档向量
- **相似性搜索**：基于向量相似度检索相关文档

### 6. LLM 模型管理

- **双模型支持**：支持 DeepSeek 和 Qwen 两种大语言模型
- **运行时切换**：通过 API 动态切换模型，无需重启服务
- **前端集成**：前端可通过按钮一键切换模型

### 7. API接口

- **知识查询接口**：`/api/rag/query`、`/api/rag/upload`
- **搜索接口**：`/api/search/knowledge`
- **生成接口**：`/api/generator/outline`、`/api/generator/content`
- **模型管理接口**：`/api/model/info`、`/api/model/switch`
- **健康检查**：`/health`

## 技术栈

- **Web框架**：FastAPI
- **状态管理**：LangGraph（知识 Agent、搜索 Agent 均基于状态图实现）
- **向量数据库**：FAISS
- **语言模型**：DeepSeek / Qwen（通过API调用，支持运行时切换）
- **网络搜索**：Tavily API（专为 RAG 优化的搜索 API）
- **文档解析**：python-docx、PyPDF2
- **数据验证**：Pydantic
- **配置管理**：config.json

## 环境配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

本地 RAG 使用的向量模型需自行下载（仓库不附带，体积超过 GitHub 单文件限制）。将 **`BAAI/bge-small-en-v1.5`** 下载到项目内地址 **`app/rag/bge-small-en-v1.5/`**（[Hugging Face](https://huggingface.co/BAAI/bge-small-en-v1.5) 模型 ID）。

### 2. 配置 config.json

复制 `config.json.example` 为 `config.json`，并按需填写 API Key 和并发配置：

```bash
cp config.json.example config.json
```

`config.json` 内容说明：

```json
{
  "deepseek_api_key": "你的DeepSeek API Key",
  "dashscope_api_key": "你的阿里云百炼 API Key",
  "tavily_api_key": "你的Tavily API Key",
  "llm_provider": "deepseek",
  "content_batch_max_workers": 3,
  "knowledge_batch_max_workers": 3,
  "search_query_max_workers": 4
}
```

| 字段                          | 说明                                                                                                                    | 是否必须                        |
| :---------------------------- | :---------------------------------------------------------------------------------------------------------------------- | :------------------------------ |
| `deepseek_api_key`            | DeepSeek API 密钥，当前 DeepSeek 服务通过官方 OpenAI 兼容接口调用，默认模型为 `deepseek-v4-pro`，并关闭 thinking 模式。 | 使用 `deepseek` 时必须填写      |
| `dashscope_api_key`           | 阿里云百炼 / DashScope API 密钥，用于 Qwen 服务。                                                                       | 只有使用 `qwen` 时需要          |
| `tavily_api_key`              | Tavily 搜索 API 密钥，用于网络搜索和知识检索增强。                                                                      | 只有使用搜索功能时需要          |
| `llm_provider`                | 默认 LLM 提供方，可选值为 `deepseek` 或 `qwen`。                                                                        | 建议保留；缺省时使用 `deepseek` |
| `content_batch_max_workers`   | 批量生成页面内容时的最大并发数。代码会限制在 `1` 到 `8` 之间。                                                          | 可选；缺省为 `3`                |
| `knowledge_batch_max_workers` | 批量知识检索时的最大并发数。代码会限制在 `1` 到 `8` 之间。                                                              | 可选；缺省为 `3`                |
| `search_query_max_workers`    | 多个搜索词并行搜索时的最大并发数。代码会限制在 `1` 到 `8` 之间。                                                        | 可选；缺省为 `4`                |

如果只使用 DeepSeek 生成大纲，最小配置如下：

```json
{
  "deepseek_api_key": "你的DeepSeek API Key",
  "llm_provider": "deepseek"
}
```

> ⚠️ `config.json` 已在 `.gitignore` 中，不会被提交到代码仓库。

### 3. 启动服务

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API 文档

启动服务后，访问以下地址查看API文档：

- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

### 模型管理 API

```bash
# 获取当前模型信息
curl http://localhost:8000/api/model/info

# 切换到 Qwen 模型
curl -X POST http://localhost:8000/api/model/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "qwen"}'

# 切换到 DeepSeek 模型
curl -X POST http://localhost:8000/api/model/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "deepseek"}'
```

### 知识搜索 API

```bash
# 搜索外部知识
curl -X POST http://localhost:8000/api/search/knowledge \
  -H "Content-Type: application/json" \
  -d '{"topic": "人工智能在医疗领域的应用"}'
```

## 测试

所有命令默认在项目根目录执行；使用 conda 时先运行 `conda activate POGCC`。
最直观的真实后端验证是大纲生成，会读取 `config.json` 并消耗 DeepSeek 额度：
```bash
python tests/test_outline_timing.py "人工智能导论" deepseek --pages 5
```
不消耗 API 额度的基础检查：
```bash
python -m compileall app tests
pytest tests/test_json_protocol.py tests/test_generator.py tests/new/schema -v
```
完整接口链路验证：
```bash
python tests/new/e2e/test_full_generation.py --topic "人工智能导论"
```
E2E 会自动检测后端是否启动，未启动时会尝试拉起 `uvicorn`；该测试会调用 LLM，可能消耗 API 额度。
