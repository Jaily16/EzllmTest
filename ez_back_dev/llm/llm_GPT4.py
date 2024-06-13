import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

os.environ["OPENAI_API_KEY"] = "your_api_key"


class GPT4Model:
    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4-turbo")
        self.embeddings = OpenAIEmbeddings(model="gpt-4-turbo")

    def get_model(self):
        return self.model

    def get_embeddings(self):
        return self.embeddings
