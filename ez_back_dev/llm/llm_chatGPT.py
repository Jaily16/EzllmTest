"""Compatibility façade for the consolidated legacy model wrappers."""

from infrastructure.llm.legacy_models import (
    ChatGPTModel,
    get_lazy_chat_model,
    get_lazy_embeddings,
)

__all__ = ["ChatGPTModel", "get_lazy_chat_model", "get_lazy_embeddings"]
