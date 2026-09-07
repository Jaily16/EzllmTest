"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import GPT4Model, get_lazy_chat_model, get_lazy_embeddings

__all__ = ["GPT4Model", "get_lazy_chat_model", "get_lazy_embeddings"]
