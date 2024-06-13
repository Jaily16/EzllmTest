from llm.llm_ChatGLM import ChatGLMModel
from llm.llm_GLM4 import GLM4Model
from llm.llm_GPT4 import GPT4Model
from llm.llm_MoonShot import MoonShotModel
from llm.llm_TongYi import TongYiModel
from llm.llm_WenXin import WenXinModel
from llm.llm_chatGPT import ChatGPTModel


def choose_llm_by_name(name: str):
    # 'GPT-3.5', 'GPT-4.0', '文心一言', '通义千问', 'GLM-3', 'GLM-4', 'MoonShot'
    if name == "GPT-3.5":
        return ChatGPTModel().get_model()
    elif name == "GPT-4.0":
        return GPT4Model().get_model()
    elif name == "文心一言":
        return WenXinModel().get_model()
    elif name == "通义千问":
        return TongYiModel().get_model()
    elif name == "GLM-3":
        return ChatGLMModel().get_model()
    elif name == "GLM-4":
        return GLM4Model().get_model()
    else:
        return MoonShotModel().get_model()