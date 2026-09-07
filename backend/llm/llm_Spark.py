"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import SparkModel, get_lazy_chat_model

__all__ = ["SparkModel", "get_lazy_chat_model"]

