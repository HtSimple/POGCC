from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import rag, generator, health, model
from app.utils.errors import AppException, exception_handler, generic_exception_handler
from app.services.llm_service import LLMService
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_service = LLMService()
    yield


app = FastAPI(
    title="POGCC - PPT大纲智能生成与内容补全系统",
    description="基于RAG技术的智能PPT辅助系统",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(rag.router)
app.include_router(generator.router)
app.include_router(health.router)
app.include_router(model.router)

# 注册异常处理
app.add_exception_handler(AppException, exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 根路径
@app.get("/")
async def root():
    return {
        "message": "Welcome to POGCC API",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)