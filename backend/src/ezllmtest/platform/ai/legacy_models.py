"""保留仍被业务调用的模型包装类实现；旧源码路径的 import facade 已退出。"""

from __future__ import annotations

from ezllmtest.platform.ai.gateway import get_lazy_chat_model, get_lazy_embeddings


class ChatGLMModel:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model()


class ChatGPTModel:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model()

    def get_embeddings(self):
        """返回惰性 embedding 包装，真正嵌入请求由调用方显式触发。"""
        return get_lazy_embeddings()


class GLM4Model:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model()


class GPT4Model:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model()

    def get_embeddings(self):
        """返回惰性 embedding 包装，真正嵌入请求由调用方显式触发。"""
        return get_lazy_embeddings()


class LlamaModel:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model()


class MoonShotModel:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model("Moonshot Kimi")


class SparkModel:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model()


class TongYiModel:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model("通义千问")


class WenXinModel:
    def get_model(self):
        """返回惰性模型包装；历史类名不等于实际 Provider，实际模型以调用参数及统一目录为准。"""
        return get_lazy_chat_model()
