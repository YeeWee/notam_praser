"""NOTAM Parser FastAPI 应用入口

启动命令：
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

API 文档：
    Swagger UI: http://localhost:8000/docs
    ReDoc: http://localhost:8000/redoc
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api.routes import router

settings = get_settings()

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="NOTAM（航行通告）完整解析器 API\n\n"
                "功能：\n"
                "- 正则解析层：提取 Q/A/B/C/D/E 行结构化字段\n"
                "- LLM 解析层：E 行语义解析（摘要、翻译、分类、术语、限制区域）\n"
                "- 术语库校验：ICAO Doc 8400 标准术语验证\n",
    version="0.1.0-mvp",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS（开发环境）
if settings.debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 注册路由
app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    if settings.debug:
        print(f"DEBUG 模式已启用")
        print(f"LLM 配置：{settings.openai_model}")
        if settings.openai_api_base:
            print(f"API Base: {settings.openai_api_base}")
        else:
            print("使用 OpenAI 官方 API")


@app.get("/")
async def root():
    """根端点"""
    return {
        "name": settings.app_name,
        "version": "0.1.0-mvp",
        "docs": "/docs",
        "health": "/api/v1/health"
    }
