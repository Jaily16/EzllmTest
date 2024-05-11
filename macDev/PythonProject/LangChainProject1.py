import os
from langchain_openai import ChatOpenAI

os.environ["OPENAI_API_KEY"] = "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"

llm = ChatOpenAI(verbose=True)

print(llm.invoke("什么是软件测试"))
