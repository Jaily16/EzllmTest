"""Compatibility wrapper for the Moonshot Kimi provider."""

from llm.provider import get_lazy_chat_model


class MoonShotModel:
    def get_model(self):
        return get_lazy_chat_model("Moonshot Kimi")
