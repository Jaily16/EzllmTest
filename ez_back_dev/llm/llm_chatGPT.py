"""Compatibility wrapper for legacy imports.

The local reproduction no longer calls OpenAI. Both methods delegate to the
configured Zhipu-compatible provider.
"""

from llm.provider import get_lazy_chat_model, get_lazy_embeddings


class ChatGPTModel:
    def get_model(self):
        return get_lazy_chat_model()

    def get_embeddings(self):
        return get_lazy_embeddings()
