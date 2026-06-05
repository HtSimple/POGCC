# LLM API 成本控制

成本控制仅统计 DeepSeek 和千问两个 LLM API，不统计 Tavily 搜索。

## Token 数据来源

每次模型调用完成后，系统优先读取 API 响应中的真实 `usage`：

- DeepSeek：`prompt_tokens`、`completion_tokens`、`total_tokens`、
  `prompt_cache_hit_tokens`、`prompt_cache_miss_tokens`
- 千问：`prompt_tokens`、`completion_tokens`、`total_tokens`

当 API 请求失败或响应没有 `usage` 时，才使用字符长度估算 Token。前端最近调用列表会显示
“API 实际值”或“估算值”。

## 当前价格配置

价格配置位于 `config.json` 的 `api_cost_rates`。

- DeepSeek `deepseek-v4-pro`：按中文价格页和人民币账户配置，币种为 CNY。
  缓存命中输入 `¥0.025`/百万 Token，缓存未命中输入 `¥3`/百万 Token，
  输出 `¥6`/百万 Token。
- 千问 `qwen3.6-plus`：按阿里云百炼中国内地阶梯价格配置，币种为 CNY。
  单次输入不超过 256K Token 时，输入 `¥2`/百万 Token、输出 `¥12`/百万 Token；
  单次输入超过 256K 且不超过 1M Token 时，输入 `¥8`/百万 Token、输出 `¥48`/百万 Token。

价格可能变化，请以官方控制台账单为准。

## 限额

前端“API 成本控制”页面可分别设置每个 LLM 的调用次数、Token 和成本限额。达到任一上限后，
下一次对应模型调用会被拦截。运行时统计保存在 `app/data/api_usage.json`，不会提交到 Git。
