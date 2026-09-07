from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from infrastructure.runtime_config import SECRET_FIELDS, resolve_secret_reference


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

SECRET_FILE_NAMES = SECRET_FIELDS
SECRET_FILE_MAX_BYTES = 8192


class ConfigurationError(ValueError):
    """Raised when an explicit secret-file setting cannot be used safely."""


def _resolve_secret_value(
    name: str,
    direct_value: str | None,
    file_path: str | None,
) -> str:
    """返回当前resolve敏感值值。

    参数:
        `name`：目标名称。
        `direct_value`：沿用签名中 `str | None` 类型约束的输入。
        `file_path`：沿用签名中 `str | None` 类型约束的输入。

    返回:
        `str`，内容保持现有调用方契约。

    异常:
        `ConfigurationError`：输入、状态或下游结果不满足现有约束时抛出。"""

    try:
        return resolve_secret_reference(name, direct_value, file_path)
    except ValueError:
        raise ConfigurationError("invalid secret file configuration") from None


def _setting_value(name: str, default: str = "") -> str:
    """返回当前设置值。"""
    direct_value = os.getenv(name)
    file_path = os.getenv(f"{name}_FILE")
    resolved = _resolve_secret_value(name, direct_value, file_path)
    if direct_value is None and file_path is None:
        return default
    return resolved


@dataclass(frozen=True)
class Settings:
    database_url: str
    zhipu_api_key: str
    zhipu_base_url: str
    zhipu_chat_model: str
    zhipu_embedding_model: str
    zhipu_timeout_seconds: float
    dashscope_api_key: str
    dashscope_base_url: str
    dashscope_chat_model: str
    dashscope_timeout_seconds: float
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_chat_model: str
    deepseek_timeout_seconds: float
    moonshot_api_key: str
    moonshot_base_url: str
    moonshot_chat_model: str
    moonshot_timeout_seconds: float
    backend_host: str
    backend_port: int
    cors_origins: tuple[str, ...]

    @property
    def llm_configured(self) -> bool:
        """返回当前LLM已配置的。"""
        return bool(
            self.zhipu_api_key
            and self.zhipu_api_key != "replace_with_your_zhipu_api_key"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取设置，并遵循现有调用契约。

    返回:
        `Settings`，内容保持现有调用方契约。"""
    cors_value = os.getenv("CORS_ORIGINS", "http://127.0.0.1:8180,http://localhost:8180")
    cors_origins = tuple(
        origin.strip() for origin in cors_value.split(",") if origin.strip()
    )
    return Settings(
        database_url=_setting_value("DATABASE_URL"),
        zhipu_api_key=_setting_value("ZHIPU_API_KEY"),
        zhipu_base_url=os.getenv(
            "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"
        ),
        zhipu_chat_model=os.getenv("ZHIPU_CHAT_MODEL", "glm-4.7"),
        zhipu_embedding_model=os.getenv("ZHIPU_EMBEDDING_MODEL", "embedding-3"),
        zhipu_timeout_seconds=float(os.getenv("ZHIPU_TIMEOUT_SECONDS", "45")),
        dashscope_api_key=_setting_value("DASHSCOPE_API_KEY"),
        dashscope_base_url=os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        dashscope_chat_model=os.getenv("DASHSCOPE_CHAT_MODEL", "qwen3.5-plus"),
        dashscope_timeout_seconds=float(
            os.getenv("DASHSCOPE_TIMEOUT_SECONDS", "45")
        ),
        deepseek_api_key=_setting_value("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_chat_model=os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash"),
        deepseek_timeout_seconds=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45")),
        moonshot_api_key=_setting_value("MOONSHOT_API_KEY"),
        moonshot_base_url=os.getenv(
            "MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"
        ),
        moonshot_chat_model=os.getenv("MOONSHOT_CHAT_MODEL", "kimi-k3"),
        moonshot_timeout_seconds=float(os.getenv("MOONSHOT_TIMEOUT_SECONDS", "45")),
        backend_host=os.getenv("BACKEND_HOST", "127.0.0.1"),
        backend_port=int(os.getenv("BACKEND_PORT", "8230")),
        cors_origins=cors_origins,
    )
