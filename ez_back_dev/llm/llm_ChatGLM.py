"""Compatibility wrapper for the former GLM-3 integration."""

from llm.provider import get_lazy_chat_model


class ChatGLMModel:
    def get_model(self):
        return get_lazy_chat_model()
