from langchain_community.chat_models import ChatZhipuAI
import os

os.environ["ZHIPUAI_API_KEY"] = "your_api_key"


class ChatGLMModel:
    def __init__(self):
        self.model = ChatZhipuAI(
            model="glm-3-turbo",
            temperature=0.5,
        )

    def get_model(self):
        return self.model
