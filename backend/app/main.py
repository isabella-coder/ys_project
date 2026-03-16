"""
FastAPI 应用主入口
"""

import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings
from app.db import init_db

# 配置日志
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.LOG_FORMAT,
)
logger = logging.getLogger(__name__)

# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 启动和关闭事件 ============

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info(f"🚀 {settings.APP_NAME} 正在启动...")
    
    # 初始化数据库
    try:
        init_db()
        logger.info("✓ 数据库初始化成功")
    except Exception as e:
        logger.error(f"✗ 数据库初始化失败: {e}")
        raise
    
    logger.info(f"✓ 服务启动成功: http://{settings.HOST}:{settings.PORT}")
    logger.info(f"✓ API 文档: http://{settings.HOST}:{settings.PORT}/docs")

    # 启动 APScheduler 定时任务
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.tasks.followup_reminder import run_followup_reminder_job

        scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        scheduler.add_job(
            run_followup_reminder_job,
            "cron",
            hour=11,
            minute=0,
            id="followup_reminder",
            replace_existing=True,
        )
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("✓ 定时任务已启动: 每日 11:00 回访提醒")
    except Exception as e:
        logger.warning(f"⚠ 定时任务启动失败（不影响主服务）: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    # 关闭 APScheduler
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("✓ 定时任务已关闭")
    logger.info("💤 应用正在关闭...")


# ============ 健康检查 ============

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ============ 路由注册 ============

from app.api import leads, stats, chat, auth, audit, store

app.include_router(leads.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(store.router, prefix="/api/v1")

# ============ 静态文件 ============

import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_store_console_dir = Path(__file__).resolve().parent.parent.parent / "admin" / "store-console"
if _store_console_dir.is_dir():
    app.mount("/store-console", StaticFiles(directory=str(_store_console_dir), html=True), name="store-console")


# ============ 根路由 ============

@app.get("/")
async def root():
    """根路由"""
    return {
        "message": f"欢迎使用 {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


# ============ 错误处理（待实现）============

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    """统一 HTTP 异常输出，保持前端可消费的结构。"""
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "code": exc.status_code, "message": message},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    """请求参数校验错误统一返回 422。"""
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "code": 422,
            "message": "请求参数校验失败",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    """兜底异常处理，避免把内部堆栈直接暴露给客户端。"""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "code": 500, "message": "服务器内部错误"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
