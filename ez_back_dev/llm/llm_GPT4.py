"""Compatibility wrapper for legacy imports."""

from llm.provider import get_lazy_chat_model, get_lazy_embeddings


class GPT4Model:
    def get_model(self):
        return get_lazy_chat_model()

    def get_embeddings(self):
        return get_lazy_embeddings()
