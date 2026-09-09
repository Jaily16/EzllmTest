"""显式配置装配：只读取该角色声明的文件，先配置后导入产品依赖。"""
from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from ezllmtest.platform import configuration_schema as schema
from ezllmtest.platform import configuration

ROLE_SOURCES = {
    "product-api": ("backend", "frontend"),
    "agent-api": ("backend", "frontend", "observability"),
    "worker": ("backend", "observability"),
    "mcp": ("backend",),
    "observability-api": ("observability", "frontend"),
}

@dataclass(frozen=True, repr=False)
class ProcessConfiguration:
    """只在进程内流转的已校验配置，repr 不暴露秘密。"""
    role: str
    repo_root: Path
    values: dict[str, str] = field(repr=False)
    port: int | None = None

def checked_root(value: str) -> Path:
    """验证显式绝对工作目录及祖先，拒绝符号链接和 junction，避免数据根随当前终端目录变化。"""
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        raise schema.RuntimeConfigurationError("runtime_config:repo_root_required")
    for item in (path, *path.parents):
        if item.is_symlink() or getattr(item.lstat(), "st_file_attributes", 0) & 1024:
            raise schema.RuntimeConfigurationError("runtime_config:reparse_path_forbidden")
    return path.resolve()

def load_process(role: str, repo_root: str, *, backend=None, frontend=None,
                 observability=None, resolve_secrets=True) -> ProcessConfiguration:
    """只读取角色允许的显式配置源，先校验字段、端点和 CORS，再投影角色所需值；秘密引用仅在显式启用解析时进入进程内快照。"""
    if role not in ROLE_SOURCES:
        raise schema.RuntimeConfigurationError("runtime_config:unknown_process_role")
    root = checked_root(repo_root)
    paths = dict(backend=backend, frontend=frontend, observability=observability)
    required = set(ROLE_SOURCES[role])
    if role == "mcp" and observability:
        required.add("observability")
    if any(paths[k] for k in paths if k not in required):
        raise schema.RuntimeConfigurationError("runtime_config:cross_role_source")
    sources, seen = {}, set()
    for name in sorted(required):
        if not paths[name]:
            raise schema.RuntimeConfigurationError("runtime_config:explicit_source_required")
        source = schema.explicit_regular_file(paths[name])
        if source.resolve() in seen:
            raise schema.RuntimeConfigurationError("runtime_config:distinct_sources_required")
        seen.add(source.resolve())
        fields = getattr(schema, name.upper() + "_FIELDS")
        values = {**getattr(schema, name.upper() + "_DEFAULTS"), **schema.read_env_file(str(source), fields)}
        schema.validate_fields(values, fields)
        needed = {"backend": ("DATABASE_URL", "AGENT_REDIS_URL", "AGENT_REDIS_PREFIX"),
                  "frontend": tuple(schema.PUBLIC_FRONTEND_FIELDS),
                  "observability": ("OBSERVABILITY_DATABASE_PATH",)}[name]
        if any(not values.get(k) and not values.get(k + "_FILE") for k in needed):
            raise schema.RuntimeConfigurationError("runtime_config:explicit_value_required")
        sources[name] = values
    public = sources.get("frontend", {})
    obs = sources.get("observability", {})
    if obs:
        obs["OBSERVABILITY_DATABASE_PATH"] = str(schema.explicit_observability_database_path(
            obs["OBSERVABILITY_DATABASE_PATH"], observability_directory=Path(observability).parent))
    ports = [int(v[k]) for v in sources.values() for k in
             ("BACKEND_PORT", "AGENT_API_PORT", "OBSERVABILITY_PORT", "FRONTEND_PORT") if k in v]
    if len(ports) != len(set(ports)):
        raise schema.RuntimeConfigurationError("runtime_config:distinct_ports_required")
    for owner, port, url, cors in (
        ("backend", "BACKEND_PORT", "VUE_APP_API_BASE_URL", "CORS_ORIGINS"),
        ("backend", "AGENT_API_PORT", "VUE_APP_AGENT_API_BASE_URL", "CORS_ORIGINS"),
        ("observability", "OBSERVABILITY_PORT", "VUE_APP_OBSERVABILITY_API_BASE_URL", "OBSERVABILITY_CORS_ORIGINS")):
        if owner not in sources or not public:
            continue
        if urlsplit(public[url]).port != int(sources[owner][port]):
            raise schema.RuntimeConfigurationError("runtime_config:endpoint_port_mismatch")
        origins = {v.strip() for v in sources[owner][cors].split(",")}
        if not {f"http://127.0.0.1:{public['FRONTEND_PORT']}", f"http://localhost:{public['FRONTEND_PORT']}"}.issubset(origins):
            raise schema.RuntimeConfigurationError("runtime_config:frontend_origin_missing")
    values = dict(sources.get("backend", {}))
    if role == "observability-api":
        values = dict(obs)
        values.update({
            "EZLLMTEST_LEGACY_READY_URL": public["VUE_APP_API_BASE_URL"].rstrip("/") + "/ready",
            "EZLLMTEST_AGENT_READY_URL": public["VUE_APP_AGENT_API_BASE_URL"].rstrip("/") + "/ready",
            "EZLLMTEST_FRONTEND_URL": "http://127.0.0.1:" + public["FRONTEND_PORT"]})
    elif obs:
        values.update({k: v for k, v in obs.items() if k in schema.AGENT_TELEMETRY_FIELDS})
        values["EZLLMTEST_OBSERVABILITY_INGEST_URL"] = f"http://{obs['OBSERVABILITY_HOST']}:{obs['OBSERVABILITY_PORT']}"
    if resolve_secrets:
        for key in schema.SECRET_FIELDS:
            if key in values or key + "_FILE" in values:
                values[key] = schema.resolve_secret_reference(key, values.get(key), values.get(key + "_FILE"))
                values.pop(key + "_FILE", None)
    port_key = {"product-api": "BACKEND_PORT", "agent-api": "AGENT_API_PORT",
                "observability-api": "OBSERVABILITY_PORT"}.get(role)
    return ProcessConfiguration(role, root, values, int(values[port_key]) if port_key else None)

def activate(config: ProcessConfiguration) -> None:
    """清除继承的配置及敏感环境变量并禁用自动 dotenv；安装不可变进程快照，防止父终端旧值覆盖显式文件。"""
    for name in tuple(os.environ):
        upper = name.upper()
        if upper in schema.ALL_FIELDS | schema.LEGACY_INTERNAL_FIELDS | {"PYTHONPATH", "PYTHONSTARTUP", "PYTHONPYCACHEPREFIX", "NODE_OPTIONS", "DOTENV_CONFIG_PATH"} or upper.startswith(schema.CONFIG_PREFIXES) or schema.SENSITIVE_NAME.search(upper):
            os.environ.pop(name, None)
    os.environ["PYTHON_DOTENV_DISABLED"] = "true"
    configuration.install(config.values, config.repo_root)

def from_environment(role: str) -> ProcessConfiguration:
    """Uvicorn 适配层仅从专用环境变量取文件路径和工作目录，配置值仍交给角色加载器读取。"""
    return load_process(role, os.environ.get("EZLLMTEST_REPO_ROOT", ""),
        backend=os.environ.get("EZLLMTEST_BACKEND_ENV_FILE"),
        frontend=os.environ.get("EZLLMTEST_FRONTEND_ENV_FILE"),
        observability=os.environ.get("EZLLMTEST_OBSERVABILITY_ENV_FILE"))
