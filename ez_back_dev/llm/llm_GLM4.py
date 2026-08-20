"""Compatibility wrapper for the former GLM-4 integration."""

from llm.provider import get_lazy_chat_model


class GLM4Model:
    def get_model(self):
        return get_lazy_chat_model()
