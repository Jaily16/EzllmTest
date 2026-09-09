# 从已安装的进程配置快照派生运行设置，不自行发现 dotenv。
from __future__ import annotations

from ezllmtest.platform import configuration as runtime_values
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path



def _setting_value(name: str, default: str = "") -> str:
    """读取 bootstrap 已解析的秘密值，不在业务层读取秘密文件。"""
    return runtime_values.get(name, default)

@dataclass(frozen=True, repr=False)
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
        """仅判断智谱 key 非空且不是示例占位值，不能据此宣称所有 Provider 已连通。"""
        return bool(
            self.zhipu_api_key
            and self.zhipu_api_key != "replace_with_your_zhipu_api_key"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """从已安装配置快照构造并缓存运行设置，CORS 和模型设置不从父终端重新发现。"""
    cors_value = runtime_values.get("CORS_ORIGINS", "http://127.0.0.1:8180,http://localhost:8180")
    cors_origins = tuple(
        origin.strip() for origin in cors_value.split(",") if origin.strip()
    )
    return Settings(
        database_url=_setting_value("DATABASE_URL"),
        zhipu_api_key=_setting_value("ZHIPU_API_KEY"),
        zhipu_base_url=runtime_values.get(
            "ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"
        ),
        zhipu_chat_model=runtime_values.get("ZHIPU_CHAT_MODEL", "glm-4.7"),
        zhipu_embedding_model=runtime_values.get("ZHIPU_EMBEDDING_MODEL", "embedding-3"),
        zhipu_timeout_seconds=float(runtime_values.get("ZHIPU_TIMEOUT_SECONDS", "45")),
        dashscope_api_key=_setting_value("DASHSCOPE_API_KEY"),
        dashscope_base_url=runtime_values.get(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        dashscope_chat_model=runtime_values.get("DASHSCOPE_CHAT_MODEL", "qwen3.5-plus"),
        dashscope_timeout_seconds=float(
            runtime_values.get("DASHSCOPE_TIMEOUT_SECONDS", "45")
        ),
        deepseek_api_key=_setting_value("DEEPSEEK_API_KEY"),
        deepseek_base_url=runtime_values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_chat_model=runtime_values.get("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash"),
        deepseek_timeout_seconds=float(runtime_values.get("DEEPSEEK_TIMEOUT_SECONDS", "45")),
        moonshot_api_key=_setting_value("MOONSHOT_API_KEY"),
        moonshot_base_url=runtime_values.get(
            "MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"
        ),
        moonshot_chat_model=runtime_values.get("MOONSHOT_CHAT_MODEL", "kimi-k3"),
        moonshot_timeout_seconds=float(runtime_values.get("MOONSHOT_TIMEOUT_SECONDS", "45")),
        backend_host=runtime_values.get("BACKEND_HOST", "127.0.0.1"),
        backend_port=int(runtime_values.get("BACKEND_PORT", "8230")),
        cors_origins=cors_origins,
    )
