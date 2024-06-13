import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

os.environ["OPENAI_API_KEY"] = "your_api_key"


class ChatGPTModel:
    def __init__(self):
        self.model = ChatOpenAI(model="gpt-3.5-turbo")
        self.embeddings = OpenAIEmbeddings(model="gpt-3.5-turbo")

    def get_model(self):
        return self.model

    def get_embeddings(self):
        return self.embeddings
