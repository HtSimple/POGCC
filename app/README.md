# POGCC 后端应用

## 目录结构

```
app/
├── api/                # API接口层
│   ├── __init__.py
│   └── routes/        # API路由
│       ├── __init__.py
│       ├── rag.py          # RAG 路由（上传文档、查知识库）
│       ├── generator.py    # 生成 路由（生成大纲、补全内容）
│       ├── model.py        # 模型管理 路由（获取/切换模型）
│       └── health.py       # 健康检查
├── core/               # 核心逻辑
│   ├── __init__.py
│   ├── rag_agent/         # RAG 核心模块
│   │   ├── __init__.py
│   │   ├── agent.py           # RAG Agent 核心类
│   │   ├── query_processor.py    # 查询处理器
│   │   ├── document_retriever.py # 文档检索器
│   │   └── result_generator.py  # 结果生成器
│   ├── generator/         # 生成模块
│   │   ├── __init__.py
│   │   ├── outline_maker.py     # 大纲生成
│   │   └── content_expander.py  # 内容补全
│   ├── document_parser.py  # 文档解析（Word/PDF）
│   └── faiss_db.py       # 向量数据库
├── prompts/              # 提示词模板
│   ├── __init__.py
│   └── templates.py      # 提示词模板
├── schema/              # Pydantic 模型
│   ├── __init__.py
│   └── models.py         # 数据模型
├── services/            # 服务层
│   ├── __init__.py
│   ├── llm_service.py   # LLM 服务工厂
│   ├── deepseek_service.py  # DeepSeek 服务
│   └── qwen_service.py  # Qwen 服务
└── utils/               # 工具类
    ├── __init__.py
    ├── config.py        # 配置管理（统一读取 config.json）
    └── errors.py        # 错误处理
```

## 核心功能

### 1. RAG Agent
- **查询处理**：清洗和扩展用户查询
- **文档检索**：从向量数据库中检索相关文档
- **结果生成**：基于检索到的文档生成回答

### 2. 生成模块
- **大纲生成**：根据用户需求生成PPT大纲结构
- **内容补全**：基于大纲节点扩写详细内容

### 3. 文档解析
- **Word解析**：解析.docx和.doc文件
- **PDF解析**：解析.pdf文件

### 4. 向量数据库
- **文档存储**：存储文档向量
- **相似性搜索**：基于向量相似度检索相关文档

### 5. LLM 模型管理
- **双模型支持**：支持 DeepSeek 和 Qwen 两种大语言模型
- **运行时切换**：通过 API 动态切换模型，无需重启服务
- **前端集成**：前端可通过按钮一键切换模型

### 6. API接口
- **RAG接口**：`/api/rag/query`、`/api/rag/upload`
- **生成接口**：`/api/generator/outline`、`/api/generator/content`
- **模型管理接口**：`/api/model/info`、`/api/model/switch`
- **健康检查**：`/health`

## 技术栈

- **Web框架**：FastAPI
- **向量数据库**：FAISS
- **语言模型**：DeepSeek / Qwen（通过API调用，支持运行时切换）
- **文档解析**：python-docx、PyPDF2
- **数据验证**：Pydantic
- **配置管理**：config.json
- **状态管理**：LangGraph

## 环境配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 config.json

复制 `config.json.example` 为 `config.json` 并填写 API Key：

```bash
cp config.json.example config.json
```

`config.json` 内容说明：

```json
{
  "deepseek_api_key": "你的DeepSeek API Key",
  "dashscope_api_key": "你的阿里云百炼 API Key",
  "llm_provider": "deepseek"
}
```

| 字段 | 说明 | 可选值 |
| :--- | :--- | :--- |
| `deepseek_api_key` | DeepSeek API 密钥 | 同济大学 LLM 平台 Key |
| `dashscope_api_key` | 阿里云百炼 API 密钥 | 阿里云 DashScope Key |
| `llm_provider` | 默认使用的模型 | `deepseek` 或 `qwen` |

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

## 测试

运行测试：

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_rag.py
pytest tests/test_generator.py
```

## 扩展和定制

### 1. 添加新的文档解析器
在 `core/document_parser.py` 中添加新的解析器实现。

### 2. 扩展向量数据库
在 `core/faiss_db.py` 中扩展向量数据库功能。

### 3. 定制提示词模板
在 `prompts/templates.py` 中修改提示词模板。

### 4. 添加新的LLM服务
1. 在 `services/` 下创建新的服务文件（如 `zhipu_service.py`）
2. 继承 `BaseLLMService` 并实现 `generate()` 方法
3. 在 `llm_service.py` 的 `VALID_PROVIDERS` 中添加新提供者
4. 在 `_create_service()` 中添加分支

### 5. 添加新的API接口
在 `api/routes/` 目录中添加新的路由文件。

## 部署

### Docker 部署

1. 构建镜像：
   ```bash
   docker build -t pogcc .
   ```

2. 运行容器（挂载配置文件）：
   ```bash
   docker run -p 8000:8000 -v /path/to/config.json:/app/config.json pogcc
   ```

## 小组成员实现功能对应文件

| 功能模块 | 对应文件/文件夹 | 说明 |
| :--- | :--- | :--- |
| **文件解析** | `core/document_parser.py` | 实现Word和PDF文档的解析功能 |
| **RAG向量数据库** | `core/faiss_db.py` | 实现基于FAISS的向量数据库存储和检索 |
| **语义划分** | `core/rag_agent/` | 在RAG agent模块中实现文本语义切分功能 |
| **JSON Schema标准** | `schema/models.py` | 定义大纲和页级内容的JSON Schema标准 |

### 集成说明

1. **文件解析**：直接使用 `DocumentParser` 类的 `parse()` 方法解析文档
2. **向量数据库**：使用 `FAISSDB` 类的 `add_document()` 和 `search()` 方法进行文档管理和检索
3. **语义划分**：在 `rag_agent` 模块中集成到文档处理流程
4. **JSON Schema**：在 `models.py` 中定义数据模型，用于API请求和响应验证
