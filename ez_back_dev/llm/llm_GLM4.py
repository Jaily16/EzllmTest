"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import GLM4Model, get_lazy_chat_model

__all__ = ["GLM4Model", "get_lazy_chat_model"]
