import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

os.environ["OPENAI_API_KEY"] = "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"


class ChatGPTModel:
    def __init__(self):
        self.model = ChatOpenAI()
        self.embeddings = OpenAIEmbeddings()

    def getModel(self):
        return self.model

    def getEmbeddings(self):
        return self.embeddings
