"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import MoonShotModel, get_lazy_chat_model

__all__ = ["MoonShotModel", "get_lazy_chat_model"]
