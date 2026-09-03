from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

SECRET_FILE_NAMES = frozenset(
    {
        "DATABASE_URL",
        "ZHIPU_API_KEY",
        "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
    }
)
SECRET_FILE_MAX_BYTES = 8192


class ConfigurationError(ValueError):
    """Raised when an explicit secret-file setting cannot be used safely."""


def _dotenv_disabled() -> bool:
    return os.getenv("PYTHON_DOTENV_DISABLED", "").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


if not _dotenv_disabled():
    load_dotenv(PROJECT_ROOT / ".env")


def _resolve_secret_value(
    name: str,
    direct_value: str | None,
    file_path: str | None,
) -> str:
    """Resolve one explicitly allowlisted value without exposing its contents.

    A direct environment value and its ``*_FILE`` counterpart are mutually
    exclusive.  This prevents an operator from believing a mounted secret is
    active while the process silently uses a stale environment value.
    """

    if name not in SECRET_FILE_NAMES:
        raise ConfigurationError("invalid secret file configuration")
    if direct_value is not None and file_path is not None:
        raise ConfigurationError("invalid secret file configuration")
    if file_path is None:
        return direct_value if direct_value is not None else ""
    if not file_path:
        raise ConfigurationError("invalid secret file configuration")

    try:
        path = Path(file_path)
        if not path.is_file():
            raise OSError
        with path.open("rb") as handle:
            payload = handle.read(SECRET_FILE_MAX_BYTES + 1)
        if len(payload) > SECRET_FILE_MAX_BYTES or b"\x00" in payload:
            raise ValueError
        value = payload.decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        raise ConfigurationError("invalid secret file configuration") from None

    if value.endswith("\r\n"):
        return value[:-2]
    if value.endswith("\n"):
        return value[:-1]
    return value


def _setting_value(name: str, default: str = "") -> str:
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
        return bool(
            self.zhipu_api_key
            and self.zhipu_api_key != "replace_with_your_zhipu_api_key"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    cors_value = os.getenv("CORS_ORIGINS", "http://localhost:8080")
    cors_origins = tuple(
        origin.strip() for origin in cors_value.split(",") if origin.strip()
    )
    return Settings(
        database_url=_setting_value(
            "DATABASE_URL",
            "mysql+pymysql://ezllmtest_v2_app@localhost:3306/ezllmtest_dev?charset=utf8mb4",
        ),
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
        moonshot_chat_model=os.getenv("MOONSHOT_CHAT_MODEL", "kimi-k2.5"),
        moonshot_timeout_seconds=float(os.getenv("MOONSHOT_TIMEOUT_SECONDS", "45")),
        backend_host=os.getenv("BACKEND_HOST", "localhost"),
        backend_port=int(os.getenv("BACKEND_PORT", "8130")),
        cors_origins=cors_origins,
    )
