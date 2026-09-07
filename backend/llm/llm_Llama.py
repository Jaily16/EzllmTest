"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import LlamaModel, get_lazy_chat_model

__all__ = ["LlamaModel", "get_lazy_chat_model"]
