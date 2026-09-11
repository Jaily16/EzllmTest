"""五个入口共用的装配点；CLI 帮助不导入产品 adapter。"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from ezllmtest.bootstrap.settings import ROLE_SOURCES, activate, checked_root, from_environment, load_process


def create_app(config):
    """先激活角色配置，再延迟装配该进程需要的依赖；观测 API 独立拥有 SQLite 和会话管道，不绑定产品数据库。"""
    activate(config)
    values = config.values
    if config.role != "observability-api":
        from ezllmtest.bootstrap.dependencies import bind_persistence
        bind_persistence()
    if config.role in {"agent-api", "worker", "mcp"} and values.get("AGENT_TELEMETRY_ENABLED", "false").lower() in {"true", "1", "yes", "on"}:
        from ezllmtest.platform.security.session_token import configure_provider
        configure_provider(config.repo_root, values["EZLLMTEST_OBSERVABILITY_INGEST_URL"])
    if config.role == "product-api":
        from ezllmtest.bootstrap.product_app import create_product_app
        return create_product_app()
    if config.role == "agent-api":
        from ezllmtest.modules.agent.api.http import create_agent_api_app
        from ezllmtest.bootstrap.agent import build_default_workbench_service
        return create_agent_api_app(service=build_default_workbench_service(), owns_service=True)
    if config.role == "observability-api":
        from ezllmtest.modules.observability.api.http import create_observability_app
        from ezllmtest.modules.observability.infrastructure.storage import ObservabilityStore
        from ezllmtest.platform.security.session_token import SessionTokenServer
        endpoint = f"http://{values['OBSERVABILITY_HOST']}:{values['OBSERVABILITY_PORT']}"
        server = SessionTokenServer(config.repo_root, endpoint)
        app = create_observability_app(
            store=ObservabilityStore(Path(values["OBSERVABILITY_DATABASE_PATH"]),
                retention_days=int(values["OBSERVABILITY_RETENTION_DAYS"]),
                max_rows=int(values["OBSERVABILITY_MAX_ROWS"])),
            ingest_token=server.token,
            allowed_origins=tuple(x.strip() for x in values["OBSERVABILITY_CORS_ORIGINS"].split(",")))
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            """管道与 SQLite 同属观测进程，失败时回收本进程已建立的资源。"""
            server.start()
            try:
                async with original_lifespan(application):
                    yield
            finally:
                await asyncio.to_thread(server.close)
        app.router.lifespan_context = lifespan
        return app
    return None


def configured_app(role: str):
    """供 Uvicorn 的 :app 入口读取显式路径选择器，再走与 CLI 相同的配置和装配流程。"""
    return create_app(from_environment(role))


def main(role: str, argv=None):
    """先解析参数，使 --help 在配置读取之前退出；不消费 worker 绕过模型服务装配，API 端口必须与显式文件一致。"""
    parser = argparse.ArgumentParser(description=f"EzllmTest {role} 独立入口")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--local-config", action="store_true", help="显式使用仓库根下各角色固定的 .env，不搜索其他位置")
    for source in ("backend", "frontend", "observability"):
        if source in ROLE_SOURCES[role] or role == "mcp" and source == "observability":
            parser.add_argument(f"--{source}-env-file")
    if role == "worker":
        parser.add_argument("--consumer", required=True)
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--no-consume", action="store_true", help="仅验证 Redis 连接及独立验收心跳，不消费任务")
    elif role == "mcp":
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--actor-id", default="loopback-operator")
        parser.add_argument("--scope-version", default="v1")
        parser.add_argument("--port", type=int, default=8011)
    else:
        parser.add_argument("--port", type=int)
    args = parser.parse_args(argv)
    sources = {source: getattr(args, f"{source}_env_file", None)
        for source in ("backend", "frontend", "observability")}
    if args.local_config:
        if any(value is not None for value in sources.values()):
            parser.error("local-config conflicts with explicit configuration files")
        # 只展开当前角色允许的固定位置；MCP 不借此读取观测或前端配置。
        root = checked_root(args.repo_root)
        sources = {source: str(root / source / ".env") for source in ROLE_SOURCES[role]}
    else:
        for source in ROLE_SOURCES[role]:
            if sources[source] is None:
                parser.error(f"--{source}-env-file is required without --local-config")
    config = load_process(role, args.repo_root, **sources)
    if role not in {"worker", "mcp"} and args.port is not None and args.port != config.port:
        parser.error("port must match the explicit configuration")
    if role == "worker" and args.no_consume:
        # 验收不装配持久化、模型或工具执行能力，配置仍按 worker 角色校验。
        activate(config)
        app = None
    else:
        app = create_app(config)
    if role == "worker":
        from ezllmtest.bootstrap.worker import _run
        return asyncio.run(_run(args))
    if role == "mcp":
        from ezllmtest.bootstrap.mcp_app import create_loopback_app
        from ezllmtest.modules.agent.domain.contracts import TrustedProjectScope
        app = create_loopback_app(project_scope=TrustedProjectScope(
            project_id=args.project_id, actor_id=args.actor_id, scope_version=args.scope_version))
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port if role == "mcp" else config.port)
    return 0
