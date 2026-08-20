"""Compatibility wrapper for the removed Llama provider."""

from llm.provider import get_lazy_chat_model


class LlamaModel:
    def get_model(self):
        return get_lazy_chat_model()
