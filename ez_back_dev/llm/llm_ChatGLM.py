"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import ChatGLMModel, get_lazy_chat_model

__all__ = ["ChatGLMModel", "get_lazy_chat_model"]
