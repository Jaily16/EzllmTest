from llamaapi import LlamaAPI
from langchain_experimental.llms import ChatLlamaAPI

# Replace 'Your_API_Token' with your actual API token
llama = LlamaAPI("your_api_key")


# 测试为不行
class LlamaModel:
    def __init__(self):
        self.model = ChatLlamaAPI(client=llama)

    def get_model(self):
        return self.model
