from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
load_dotenv(PROJECT_ROOT / ".env")


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
        database_url=os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://ezllmtest_v2_app@localhost:3306/ezllmtest_dev?charset=utf8mb4",
        ),
        zhipu_api_key=os.getenv("ZHIPU_API_KEY", ""),
        zhipu_base_url=os.getenv(
            "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"
        ),
        zhipu_chat_model=os.getenv("ZHIPU_CHAT_MODEL", "glm-4.7"),
        zhipu_embedding_model=os.getenv("ZHIPU_EMBEDDING_MODEL", "embedding-3"),
        zhipu_timeout_seconds=float(os.getenv("ZHIPU_TIMEOUT_SECONDS", "45")),
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        dashscope_base_url=os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        dashscope_chat_model=os.getenv("DASHSCOPE_CHAT_MODEL", "qwen3.5-plus"),
        dashscope_timeout_seconds=float(
            os.getenv("DASHSCOPE_TIMEOUT_SECONDS", "45")
        ),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_chat_model=os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash"),
        deepseek_timeout_seconds=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45")),
        moonshot_api_key=os.getenv("MOONSHOT_API_KEY", ""),
        moonshot_base_url=os.getenv(
            "MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"
        ),
        moonshot_chat_model=os.getenv("MOONSHOT_CHAT_MODEL", "kimi-k2.5"),
        moonshot_timeout_seconds=float(os.getenv("MOONSHOT_TIMEOUT_SECONDS", "45")),
        backend_host=os.getenv("BACKEND_HOST", "localhost"),
        backend_port=int(os.getenv("BACKEND_PORT", "8130")),
        cors_origins=cors_origins,
    )
