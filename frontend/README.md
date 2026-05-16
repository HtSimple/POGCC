# POGCC 前端

## Mock / 后端接口切换

前端通过 Vite 环境变量控制数据来源：

```bash
VITE_USE_MOCK=true
```

取值说明：

- `true`：使用前端内置 mock 数据，不依赖后端，适合展示效果。
- `false`：连接真实 FastAPI 后端。

后端地址通过下面参数配置：

```bash
VITE_API_BASE_URL=http://localhost:8000
```

默认行为：

- 如果没有配置 `VITE_USE_MOCK`，前端默认使用 mock 数据。
- 要连接真实后端，需要在 `frontend/.env` 中写入：

```bash
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000
```

## 启动

```bash
npm install
npm run dev
```

访问：

```text
http://localhost:5173
```
