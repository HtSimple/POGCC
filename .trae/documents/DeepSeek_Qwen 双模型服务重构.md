## 计划：将 LLM 服务拆分为 DeepSeek + Qwen 双模型

### 1. 创建 `app/services/deepseek_service.py`

* 将现有 `llm_service.py` 中的代码迁移过来，类名改为 `DeepSeekService`

* 保持原有的同济大学 API 端点和 DeepSeek-R1 模型调用逻辑不变

* 从 `config.json` 读取 `deepseek_api_key`

### 2. 创建 `app/services/qwen_service.py`

* 新建 `QwenService` 类，使用 OpenAI 兼容接口调用千问流式输出；

* API 端点：`https://dashscope.aliyuncs.com/compatible-mode/v1`

* 模型：`qwen-plus`

* 从 `config.json` 读取 `dashscope_api_key`

* 使用 `openai` 库调用

### 3. 修改 `app/services/llm_service.py` 为工厂模式

* 定义 `BaseLLMService` 抽象基类，包含 `generate()` 方法

* `LLMService` 作为工厂类，根据 `config.json` 中的 `llm_provider` 字段（默认 `"deepseek"`）自动选择使用 `DeepSeekService` 或 `QwenService`

* 保持 `LLMService().generate()` 接口不变，上层代码无需修改

### 4. 修改 `app/core/rag_agent/result_generator.py`

* 删除内部重复的 `_call_llm` 方法

* 改为使用 `LLMService`（工厂模式），与 `outline_maker` 和 `content_expander` 保持一致

### 5. 更新 `config.json`

* 添加 `dashscope_api_key` 字段（暂填占位符）

* 添加 `llm_provider` 字段（默认 `"deepseek"`）

### 6. 更新 `requirements.txt`

* 添加 `openai` 依赖（千问调用使用 OpenAI 兼容接口）

### 7. 运行测试验证

* 验证 DeepSeek 服务正常

* 验证 Qwen 服务正常

* 验证工厂模式切换正常

