# 根据显式模型标签选择本次 Provider 能力，避免界面名称与实际模型混用。
from ezllmtest.platform.ai.gateway import get_chat_model


def choose_llm_by_name(name: str, minimum_timeout_seconds: float = 0.0):
    """按明确模型标签和最低超时获取惰性模型，选择动作不触发生成。"""
    return get_chat_model(name, minimum_timeout_seconds)
