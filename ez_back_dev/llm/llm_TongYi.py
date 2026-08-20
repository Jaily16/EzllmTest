"""Compatibility wrapper for the Alibaba Cloud TongYi provider."""

from llm.provider import get_lazy_chat_model

class TongYiModel:
    def get_model(self):
        return get_lazy_chat_model("通义千问")
