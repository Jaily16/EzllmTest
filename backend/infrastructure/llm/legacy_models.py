"""Single implementation for the historical model wrapper classes.

The old modules remain import-compatible façades.  Keeping the tiny class
names here prevents the legacy provider adapters from drifting apart while
preserving their original provider labels and lazy-call behaviour.
"""

from __future__ import annotations

from infrastructure.llm.gateway import get_lazy_chat_model, get_lazy_embeddings


class ChatGLMModel:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model()


class ChatGPTModel:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model()

    def get_embeddings(self):
        """返回当前适配器配置的 embedding 实例。"""
        return get_lazy_embeddings()


class GLM4Model:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model()


class GPT4Model:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model()

    def get_embeddings(self):
        """返回当前适配器配置的 embedding 实例。"""
        return get_lazy_embeddings()


class LlamaModel:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model()


class MoonShotModel:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model("Moonshot Kimi")


class SparkModel:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model()


class TongYiModel:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model("通义千问")


class WenXinModel:
    def get_model(self):
        """返回当前适配器配置的模型实例。"""
        return get_lazy_chat_model()
