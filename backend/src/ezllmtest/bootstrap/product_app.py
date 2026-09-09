# 装配产品 API 的 router、异常处理及生命周期，具体业务由所属域实现。
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from ezllmtest.modules.projects.api.routes import router as projects_router
from ezllmtest.modules.generation.api.routes import router as generation_router
from ezllmtest.platform.settings import get_settings
from ezllmtest.platform.database.connection import get_engine
from ezllmtest.platform.ai.gateway import LLMConfigurationError, LLMEmptyResponseError, LLMOutputParsingError, LLMProviderError, LLMRateLimitError, LLMTimeoutError, UnsupportedModelError
from ezllmtest.shared.status import Status

def create_product_app():
    """装配产品路由和进程配置，导入阶段不创建应用或数据库连接。"""
    settings = get_settings()
    READINESS_SCHEMA_VERSION = "iteration5-readiness-v1"

    app = FastAPI(
        title="EzllmTest BackEnd API",
        description="基于LLM驱动的软件测试计划和用例生成平台的后端api接口 "
    )

    app.include_router(projects_router)
    app.include_router(generation_router)


    def _llm_error_response(status_code: int, reason: str) -> JSONResponse:
        """将 LLM 异常转换为稳定且不泄露敏感信息的错误响应。"""
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
        """将不支持的模型选择转换为 400 响应，复用产品端统一错误信封。"""
        return _llm_error_response(400, str(exc))


    @app.exception_handler(LLMConfigurationError)
    async def llm_configuration_handler(_request, exc: LLMConfigurationError):
        """模型配置缺失时返回 503，不尝试隐式读取其他配置补齐。"""
        return _llm_error_response(503, str(exc))


    @app.exception_handler(LLMTimeoutError)
    async def llm_timeout_handler(_request, exc: LLMTimeoutError):
        """将 Provider 超时转换为 504，保留上层可识别的错误格式。"""
        return _llm_error_response(504, str(exc))


    @app.exception_handler(LLMRateLimitError)
    async def llm_rate_limit_handler(_request, exc: LLMRateLimitError):
        """将 Provider 限流转换为 429，供调用方决定是否稍后重试。"""
        return _llm_error_response(429, str(exc))


    @app.exception_handler(LLMOutputParsingError)
    @app.exception_handler(LLMEmptyResponseError)
    @app.exception_handler(LLMProviderError)
    async def llm_upstream_handler(_request, exc):
        """将上游故障、空输出或解析失败转换为 502，不将其当作有效生成结果。"""
        return _llm_error_response(502, str(exc))


    # 只执行数据库 SELECT 1 并返回模型配置状态；健康检查不发起模型或 embedding 请求。
    @app.get("/health", description="\f")
    def health():
        """\f
        处理 `GET /health` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        database_status = "ok"
        try:
            with get_engine().connect() as connection:
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


    # 以数据库最小连接结果决定 200 或 503，只返回允许公开的就绪字段。
    @app.get("/ready")
    def readiness():
        """Return a safe, read-only readiness result for the legacy API.\f
        处理 `GET /ready` 请求，并沿用既有状态码、响应 schema 与安全边界。"""
        database_ok = False
        try:
            with get_engine().connect() as connection:
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
    return app
