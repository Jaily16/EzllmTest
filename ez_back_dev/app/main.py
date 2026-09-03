from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.routers import router
from infrastructure.config import get_settings
from infrastructure.persistence.project_repository import engine
from infrastructure.llm.gateway import (
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMOutputParsingError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    UnsupportedModelError,
)
from tools.status import Status

settings = get_settings()
READINESS_SCHEMA_VERSION = "iteration5-readiness-v1"

app = FastAPI(
    title="EzllmTest BackEnd API",
    description="基于LLM驱动的软件测试计划和用例生成平台的后端api接口 "
)

app.include_router(router)


def _llm_error_response(status_code: int, reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": Status.LLM_APIS_ANALYSIS_FAILURE.value,
            "reason": reason,
            "data": False,
        },
    )


@app.exception_handler(UnsupportedModelError)
async def unsupported_model_handler(_request, exc: UnsupportedModelError):
    return _llm_error_response(400, str(exc))


@app.exception_handler(LLMConfigurationError)
async def llm_configuration_handler(_request, exc: LLMConfigurationError):
    return _llm_error_response(503, str(exc))


@app.exception_handler(LLMTimeoutError)
async def llm_timeout_handler(_request, exc: LLMTimeoutError):
    return _llm_error_response(504, str(exc))


@app.exception_handler(LLMRateLimitError)
async def llm_rate_limit_handler(_request, exc: LLMRateLimitError):
    return _llm_error_response(429, str(exc))


@app.exception_handler(LLMOutputParsingError)
@app.exception_handler(LLMEmptyResponseError)
@app.exception_handler(LLMProviderError)
async def llm_upstream_handler(_request, exc):
    return _llm_error_response(502, str(exc))


@app.get("/health")
def health():
    database_status = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "database": database_status,
        "llm_configured": settings.llm_configured,
        "chat_model": settings.zhipu_chat_model,
        "embedding_model": settings.zhipu_embedding_model,
    }


@app.get("/ready")
def readiness():
    """Return a safe, read-only readiness result for the legacy API."""
    database_ok = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False

    return JSONResponse(
        status_code=200 if database_ok else 503,
        content={
            "schema_version": READINESS_SCHEMA_VERSION,
            "service": "legacy-api",
            "status": "ready" if database_ok else "not_ready",
            "checks": {"database": "ok" if database_ok else "unavailable"},
        },
    )

# 将配置挂在到app上,解决跨域问题
app.add_middleware(
    CORSMiddleware,
    # 这里配置允许跨域访问的前端地址
    allow_origins=list(settings.cors_origins),
    # 跨域请求是否支持 cookie， 如果这里配置true，则allow_origins不能配置*
    allow_credentials=False,
    # 支持跨域的请求类型，可以单独配置get、post等，也可以直接使用通配符*表示支持所有
    allow_methods=["*"],
    allow_headers=["*"],
)
