"""Compatibility wrapper for the removed WenXin provider."""

from llm.provider import get_lazy_chat_model


class WenXinModel:
    def get_model(self):
        return get_lazy_chat_model()
