# 解析显式配置并校验字段、路径和跨端契约；错误只携带类别及允许的字段名。
"""Explicit local runtime configuration; no application imports or discovery.

Examples document this schema, never define it. Values are kept in memory and
errors contain only known field names/categories, not supplied values or paths.
"""

from __future__ import annotations

import math
import os
import re
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


class RuntimeConfigurationError(ValueError):
    """A redacted configuration failure safe to show to the operator."""


MODEL_FIELDS = frozenset(
    f"{provider}_{suffix}"
    for provider in ("ZHIPU", "DASHSCOPE", "DEEPSEEK", "MOONSHOT")
    for suffix in ("API_KEY", "BASE_URL", "CHAT_MODEL", "TIMEOUT_SECONDS")
) | {"ZHIPU_EMBEDDING_MODEL"}
SECRET_FIELDS = frozenset({"DATABASE_URL", "ZHIPU_API_KEY", "DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY"})
SECRET_FILE_FIELDS = frozenset(f"{name}_FILE" for name in SECRET_FIELDS)
BUDGET_DEFAULTS = {
    "AGENT_FOCUSED_MAX_INPUT_TOKENS": 768_000,
    "AGENT_FOCUSED_MAX_OUTPUT_TOKENS": 393_216,
    "AGENT_STANDARD_MAX_INPUT_TOKENS": 2_048_000,
    "AGENT_STANDARD_MAX_OUTPUT_TOKENS": 1_048_576,
}
BACKEND_DEFAULTS = {
    "BACKEND_HOST": "127.0.0.1",
    "BACKEND_PORT": "8230",
    "CORS_ORIGINS": "http://127.0.0.1:8180,http://localhost:8180",
    "AGENT_API_PORT": "8231",
    "AGENT_CHECKPOINT_TTL_SECONDS": "604800",
    "AGENT_IDEMPOTENCY_TTL_SECONDS": "604800",
    "AGENT_CANCEL_TTL_SECONDS": "604800",
    "AGENT_EVENT_TTL_SECONDS": "3600",
    "AGENT_EVENT_MAX_LENGTH": "2000",
    "AGENT_LEASE_TTL_SECONDS": "30",
    "AGENT_LEASE_RENEW_SECONDS": "10",
    "AGENT_COMMAND_CLAIM_SECONDS": "45",
    "AGENT_WORKER_HEARTBEAT_TTL_SECONDS": "30",
    "AGENT_WORKER_GROUP": "ezllm-agent-workers",
    "LANGGRAPH_STRICT_MSGPACK": "true",
    **{name: str(value) for name, value in BUDGET_DEFAULTS.items()},
}
BACKEND_FIELDS = frozenset(BACKEND_DEFAULTS) | MODEL_FIELDS | SECRET_FIELDS | SECRET_FILE_FIELDS | {"AGENT_REDIS_URL", "AGENT_REDIS_PREFIX"}
PUBLIC_FRONTEND_FIELDS = frozenset(
    {
        "VUE_APP_API_BASE_URL",
        "VUE_APP_AGENT_API_BASE_URL",
        "VUE_APP_OBSERVABILITY_API_BASE_URL",
    }
)
FRONTEND_DEFAULTS = {"FRONTEND_PORT": "8180"}
FRONTEND_FIELDS = PUBLIC_FRONTEND_FIELDS | {"FRONTEND_PORT"}
AGENT_TELEMETRY_FIELDS = frozenset(
    {
        "AGENT_TELEMETRY_ENABLED",
        "AGENT_TELEMETRY_SERVICE_NAME",
        "AGENT_OTEL_EXPORT_TIMEOUT_MS",
        "AGENT_OTEL_METRIC_INTERVAL_MS",
    }
)
OBSERVABILITY_DEFAULTS = {
    "AGENT_TELEMETRY_ENABLED": "false",
    "AGENT_TELEMETRY_SERVICE_NAME": "ezllm-agent",
    "AGENT_OTEL_EXPORT_TIMEOUT_MS": "2000",
    "AGENT_OTEL_METRIC_INTERVAL_MS": "30000",
    "OBSERVABILITY_HOST": "127.0.0.1",
    "OBSERVABILITY_PORT": "8140",
    "OBSERVABILITY_RETENTION_DAYS": "7",
    "OBSERVABILITY_MAX_ROWS": "100000",
    "OBSERVABILITY_CORS_ORIGINS": "http://127.0.0.1:8180,http://localhost:8180",
}
OBSERVABILITY_FIELDS = frozenset(OBSERVABILITY_DEFAULTS) | {
    "OBSERVABILITY_DATABASE_PATH"
}
ALL_FIELDS = BACKEND_FIELDS | FRONTEND_FIELDS | OBSERVABILITY_FIELDS
LEGACY_INTERNAL_FIELDS = frozenset(
    {
        "PYTHON_DOTENV_DISABLED",
        "EZLLMTEST_VITE_ENV_DIR",
    }
)
LEGACY_FIELDS = ALL_FIELDS | LEGACY_INTERNAL_FIELDS
BOOL_FIELDS = frozenset({"LANGGRAPH_STRICT_MSGPACK", "AGENT_TELEMETRY_ENABLED"})
PORT_FIELDS = frozenset(
    {"BACKEND_PORT", "AGENT_API_PORT", "FRONTEND_PORT", "OBSERVABILITY_PORT"}
)
POSITIVE_INTEGER_FIELDS = frozenset(BUDGET_DEFAULTS) | frozenset(
    name for name in BACKEND_DEFAULTS if name.endswith(("_SECONDS", "_LENGTH"))
) | {
    "AGENT_OTEL_EXPORT_TIMEOUT_MS",
    "AGENT_OTEL_METRIC_INTERVAL_MS",
    "OBSERVABILITY_RETENTION_DAYS",
    "OBSERVABILITY_MAX_ROWS",
}
CONFIG_PREFIXES = ("AGENT_", "ZHIPU_", "DASHSCOPE_", "DEEPSEEK_", "MOONSHOT_", "DATABASE_", "BACKEND_", "FRONTEND_", "VITE_", "VUE_APP_", "OTEL_", "LANGCHAIN_", "LANGSMITH_", "LANGGRAPH_", "EZLLMTEST_")
SENSITIVE_NAME = re.compile(r"API_KEY|PASSWORD|SECRET|TOKEN|DATABASE_URL|REDIS_URL", re.IGNORECASE)
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _error(category: str, name: str | None = None) -> RuntimeConfigurationError:
    """只用稳定类别与允许字段名构造配置错误，禁止把字段值或连接串拼入消息。"""
    suffix = f": {name}" if name in ALL_FIELDS else ""
    return RuntimeConfigurationError(f"runtime_config:{category}{suffix}")


def positive_integer(name: str, value: str) -> int:
    """校验整数的字面形式和允许范围，拒绝布尔值或依赖隐式转换的配置。"""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise _error("positive_integer_required", name)
    number = int(value)
    if number < 1 or number > 9_007_199_254_740_991:
        raise _error("positive_integer_required", name)
    return number


def explicit_regular_file(path_value: str) -> Path:
    """仅接受显式绝对普通文件，并核验文件及祖先的链接属性；此步骤不读取正文。"""
    path = Path(path_value)
    if not path.is_absolute():
        raise _error("absolute_path_required")
    try:
        for candidate in (path, *path.parents):
            info = candidate.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise _error("reparse_path_forbidden")
        if not path.is_file():
            raise _error("regular_file_required")
    except OSError:
        raise _error("file_unavailable") from None
    return path


def parse_env_lines(lines: Iterable[str], allowed: frozenset[str]) -> dict[str, str]:
    """解析有限的键值语法并拒绝重复或未知字段；只处理字面值，不展开环境变量或执行配置。"""
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise _error("invalid_entry")
        if name not in allowed:
            raise _error("unknown_or_cross_module_field")
        if name in values:
            raise _error("duplicate_field", name)
        value = value.strip()
        if value.startswith(("'", '"')):
            closing = value.find(value[0], 1)
            if closing < 1 or (value[closing + 1:].strip() and not value[closing + 1:].lstrip().startswith("#")):
                raise _error("invalid_quoted_value", name)
            value = value[1:closing]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if any(character in value for character in ("\x00", "\r", "\n")):
            raise _error("invalid_value", name)
        if name in BOOL_FIELDS and value.casefold() in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            value = "true" if value.casefold() in {"true", "1", "yes", "on"} else "false"
        values[name] = value
    validate_fields(values, allowed)
    return values


def read_env_file(path_value: str, allowed: frozenset[str]) -> dict[str, str]:
    """在路径校验后打开明确文件，将读取失败折叠为安全配置类别，再交给统一字段解析器。"""
    path = explicit_regular_file(path_value)
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            return parse_env_lines(stream, allowed)
    except (OSError, UnicodeError):
        raise _error("file_unreadable") from None


def resolve_secret_reference(name: str, direct: str | None, reference: str | None) -> str:
    """值和 _FILE 互斥；仅在解析阶段有界读取已核验的秘密文件，不向错误消息输出正文。"""
    if name not in SECRET_FIELDS or (direct is not None and reference is not None):
        raise _error("secret_source_conflict", name)
    if reference is None:
        return direct if direct is not None else ""
    path = explicit_regular_file(reference)
    try:
        with path.open("rb") as handle:
            payload = handle.read(8193)
        if len(payload) > 8192 or b"\x00" in payload:
            raise ValueError
        value = payload.decode("utf-8")
        if value.endswith("\r\n"):
            value = value[:-2]
        elif value.endswith("\n"):
            value = value[:-1]
        if "\r" in value or "\n" in value:
            raise ValueError
        return value
    except (OSError, UnicodeError, ValueError):
        raise _error("invalid_secret_reference", name) from None


def _url(value: str, name: str, schemes: set[str], *, loopback: bool, credentials: bool = False):
    """解析并检查 URL 的协议、主机和凭据边界，错误只携带字段类别。"""
    try:
        parsed = urlsplit(value)
        port = parsed.port
        valid = parsed.scheme in schemes and bool(parsed.hostname) and (port is None or 1 <= port <= 65535)
        valid = valid and (not loopback or parsed.hostname.casefold() in LOOPBACK_HOSTS)
        valid = valid and (credentials or (parsed.username is None and parsed.password is None))
        valid = valid and not parsed.fragment
        if not valid:
            raise ValueError
        return parsed
    except ValueError:
        raise _error("invalid_url", name) from None


def validate_fields(values: Mapping[str, str], allowed: frozenset[str]) -> None:
    """先拒绝未知字段，再逐项校验值类型、端点及秘密引用路径；检查引用路径不读取秘密正文。"""
    if set(values).difference(allowed):
        raise _error("unknown_or_cross_module_field")
    for name, value in values.items():
        if not isinstance(value, str) or any(char in value for char in ("\x00", "\r", "\n")):
            raise _error("invalid_value", name)
        if name in PORT_FIELDS:
            if positive_integer(name, value) > 65535:
                raise _error("invalid_port", name)
        elif name in POSITIVE_INTEGER_FIELDS:
            number = positive_integer(name, value)
            if name == "OBSERVABILITY_RETENTION_DAYS" and number > 365:
                raise _error("retention_out_of_range", name)
            if name == "OBSERVABILITY_MAX_ROWS" and not 100 <= number <= 1_000_000:
                raise _error("row_limit_out_of_range", name)
            if name == "AGENT_OTEL_EXPORT_TIMEOUT_MS" and not 100 <= number <= 30_000:
                raise _error("timeout_out_of_range", name)
            if name == "AGENT_OTEL_METRIC_INTERVAL_MS" and not 1_000 <= number <= 300_000:
                raise _error("interval_out_of_range", name)
        elif name in BOOL_FIELDS and value.casefold() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            raise _error("boolean_required", name)
        elif name in MODEL_FIELDS and name.endswith("_TIMEOUT_SECONDS"):
            try:
                number = float(value)
                if not math.isfinite(number) or number <= 0:
                    raise ValueError
            except ValueError:
                raise _error("positive_timeout_required", name) from None
        elif name in {"BACKEND_HOST", "OBSERVABILITY_HOST"} and value.casefold() not in LOOPBACK_HOSTS:
            raise _error("loopback_required", name)
        elif name in {"AGENT_REDIS_PREFIX", "AGENT_WORKER_GROUP", "AGENT_TELEMETRY_SERVICE_NAME"} and (not value or any(char.isspace() for char in value)):
            raise _error("nonempty_identifier_required", name)
        elif name in PUBLIC_FRONTEND_FIELDS:
            if value:
                parsed = _url(value, name, {"http", "https"}, loopback=True)
                if parsed.query:
                    raise _error("query_in_public_endpoint", name)
        elif name in MODEL_FIELDS and name.endswith("_BASE_URL"):
            _url(value, name, {"http", "https"}, loopback=False)
        elif name in MODEL_FIELDS and name.endswith(("_CHAT_MODEL", "_EMBEDDING_MODEL")) and not value:
            raise _error("nonempty_value_required", name)
        elif name == "AGENT_REDIS_URL" and value:
            _url(value, name, {"redis", "rediss"}, loopback=True, credentials=True)
        elif name == "DATABASE_URL" and value:
            _url(value, name, {"mysql", "mysql+pymysql"}, loopback=True, credentials=True)
        elif name in {"CORS_ORIGINS", "OBSERVABILITY_CORS_ORIGINS"}:
            origins = [item.strip() for item in value.split(",")]
            for origin in origins:
                parsed = _url(origin, name, {"http", "https"}, loopback=True)
                if parsed.path not in {"", "/"} or parsed.query:
                    raise _error("origin_required", name)
    for name in SECRET_FIELDS:
        reference = f"{name}_FILE"
        if name in values and reference in values:
            raise _error("secret_source_conflict", name)
        if reference in values:
            # Validate the reference only. config-check never opens its contents.
            explicit_regular_file(values[reference])
    if "AGENT_LEASE_RENEW_SECONDS" in values and "AGENT_LEASE_TTL_SECONDS" in values:
        if int(values["AGENT_LEASE_RENEW_SECONDS"]) >= int(values["AGENT_LEASE_TTL_SECONDS"]):
            raise _error("renewal_must_precede_expiry", "AGENT_LEASE_RENEW_SECONDS")


@dataclass(frozen=True)
class RuntimeConfiguration:
    backend: dict[str, str] = field(repr=False)
    frontend: dict[str, str] = field(repr=False)
    observability: dict[str, str] = field(repr=False)

    @property
    def frontend_port(self) -> int:
        """返回前端显式配置的 loopback 端口。"""
        return int(self.frontend["FRONTEND_PORT"])

    def backend_environment(self) -> dict[str, str]:
        """为兼容 runner 形成后端与遥测配置的合并视图；子进程仍须经 isolated_environment 按角色过滤。"""
        return {**self.backend, **self.observability}


def explicit_observability_database_path(
    path_value: str, *, observability_directory: Path
) -> Path:
    """将 SQLite 定位限制在明确观测目录的 data 边界，拒绝越界、链接及非数据库文件位置。"""
    path = Path(path_value)
    if not path.is_absolute() or path.suffix.casefold() != ".sqlite3":
        raise _error("invalid_observability_database_path", "OBSERVABILITY_DATABASE_PATH")
    expected_parent = (observability_directory / "data").resolve()
    candidate = path.resolve()
    try:
        candidate.relative_to(expected_parent)
    except ValueError:
        raise _error(
            "observability_database_outside_data_directory",
            "OBSERVABILITY_DATABASE_PATH",
        ) from None
    try:
        for ancestor in (candidate, *candidate.parents):
            if not ancestor.exists():
                continue
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(
                info, "st_file_attributes", 0
            ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise _error("reparse_path_forbidden")
        if candidate.exists() and not candidate.is_file():
            raise _error("regular_file_required")
    except OSError:
        raise _error("file_unavailable") from None
    return candidate


def load_three_files(backend: str, frontend: str, observability: str) -> RuntimeConfiguration:
    """runner 的三端契约检查入口：三份文件必须独立，端口互异且公开 URL/CORS 与服务声明一致。"""
    paths = [explicit_regular_file(value) for value in (backend, frontend, observability)]
    if len({os.path.normcase(str(path.resolve())) for path in paths}) != 3:
        raise _error("distinct_sources_required")
    backend_values = {**BACKEND_DEFAULTS, **read_env_file(backend, BACKEND_FIELDS)}
    frontend_values = {**FRONTEND_DEFAULTS, **read_env_file(frontend, FRONTEND_FIELDS)}
    observability_values = {**OBSERVABILITY_DEFAULTS, **read_env_file(observability, OBSERVABILITY_FIELDS)}
    for values, allowed in ((backend_values, BACKEND_FIELDS), (frontend_values, FRONTEND_FIELDS), (observability_values, OBSERVABILITY_FIELDS)):
        validate_fields(values, allowed)
    for name in ("DATABASE_URL", "AGENT_REDIS_URL", "AGENT_REDIS_PREFIX"):
        if not backend_values.get(name) and not backend_values.get(f"{name}_FILE"):
            raise _error("explicit_value_required", name)
    for name in ("VUE_APP_API_BASE_URL", "VUE_APP_AGENT_API_BASE_URL"):
        if not frontend_values.get(name):
            raise _error("explicit_value_required", name)
    if not observability_values.get("OBSERVABILITY_DATABASE_PATH"):
        raise _error("explicit_value_required", "OBSERVABILITY_DATABASE_PATH")
    observability_values["OBSERVABILITY_DATABASE_PATH"] = str(
        explicit_observability_database_path(
            observability_values["OBSERVABILITY_DATABASE_PATH"],
            observability_directory=paths[2].parent,
        )
    )
    ports = [
        int(backend_values["BACKEND_PORT"]),
        int(backend_values["AGENT_API_PORT"]),
        int(frontend_values["FRONTEND_PORT"]),
        int(observability_values["OBSERVABILITY_PORT"]),
    ]
    if len(set(ports)) != 4:
        raise _error("distinct_ports_required")
    endpoint_hosts = (
        backend_values["BACKEND_HOST"].casefold(),
        "127.0.0.1",
        observability_values["OBSERVABILITY_HOST"].casefold(),
    )
    for name, port, host in zip(
        (
            "VUE_APP_API_BASE_URL",
            "VUE_APP_AGENT_API_BASE_URL",
            "VUE_APP_OBSERVABILITY_API_BASE_URL",
        ),
        (ports[0], ports[1], ports[3]),
        endpoint_hosts,
    ):
        if not frontend_values.get(name):
            raise _error("explicit_value_required", name)
        parsed = _url(frontend_values[name], name, {"http", "https"}, loopback=True)
        equivalent_hosts = {"127.0.0.1", "localhost"} if host in {"127.0.0.1", "localhost"} else {host}
        if parsed.scheme != "http" or parsed.hostname.casefold() not in equivalent_hosts or parsed.port != port or parsed.path not in {"", "/"} or parsed.query:
            raise _error("managed_endpoint_mismatch", name)
    expected_origins = {f"http://127.0.0.1:{ports[2]}", f"http://localhost:{ports[2]}"}
    origins = {item.strip().rstrip("/") for item in backend_values["CORS_ORIGINS"].split(",")}
    if not expected_origins.intersection(origins):
        raise _error("frontend_origin_missing", "CORS_ORIGINS")
    observability_origins = {
        item.strip().rstrip("/")
        for item in observability_values["OBSERVABILITY_CORS_ORIGINS"].split(",")
    }
    if not expected_origins.intersection(observability_origins):
        raise _error("frontend_origin_missing", "OBSERVABILITY_CORS_ORIGINS")
    return RuntimeConfiguration(backend_values, frontend_values, observability_values)


def isolated_environment(
    values: Mapping[str, str],
    *,
    role: str,
    inherited: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """从父环境清除冲突和敏感配置，仅投影指定角色的字段；前端只接收公开配置。"""
    validate_fields(values, LEGACY_FIELDS)
    child = dict(os.environ if inherited is None else inherited)
    for name in tuple(child):
        upper = name.upper()
        if upper in ALL_FIELDS | LEGACY_INTERNAL_FIELDS | {"CORS_ORIGINS", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONPYCACHEPREFIX", "NODE_OPTIONS", "DOTENV_CONFIG_PATH", "PYTHON_DOTENV_DISABLED"} or upper.startswith(CONFIG_PREFIXES) or SENSITIVE_NAME.search(upper):
            child.pop(name, None)
    selected_by_role = {
        "frontend": PUBLIC_FRONTEND_FIELDS,
        "legacy-api": BACKEND_FIELDS,
        "agent-api": BACKEND_FIELDS | AGENT_TELEMETRY_FIELDS,
        "worker": BACKEND_FIELDS | AGENT_TELEMETRY_FIELDS,
        "observability-api": OBSERVABILITY_FIELDS,
    }
    selected = selected_by_role.get(role)
    if selected is None:
        raise _error("unknown_process_role")
    child.update({name: value for name, value in values.items() if name in selected})
    if role != "frontend":
        child["PYTHON_DOTENV_DISABLED"] = "true"
    return child
