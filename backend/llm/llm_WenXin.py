"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import WenXinModel, get_lazy_chat_model

__all__ = ["WenXinModel", "get_lazy_chat_model"]
