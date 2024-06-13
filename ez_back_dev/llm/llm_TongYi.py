import os

os.environ["DASHSCOPE_API_KEY"] = 'your_api_key'
from langchain_community.chat_models.tongyi import ChatTongyi


# 阿里通义千问api的调用

class TongYiModel:
    def __init__(self):
        self.model = ChatTongyi()

    def get_model(self):
        return self.model
