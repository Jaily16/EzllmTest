import os

os.environ["OPENAI_API_KEY"] = "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"
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from fastapi import FastAPI
from langserve import add_routes

template = "请扮演一位资深游戏博主，您负责为用户生成适合微博发布的中文文章。请把用户输入内容扩展成为150个字左右的文章，并添加适当的表情符号使内容引人入胜并体现专业性"
prompt = ChatPromptTemplate.from_messages([("system", template), ("human", "{input}")])

model = ChatOpenAI()

chain = prompt | model | StrOutputParser()

app = FastAPI(
    title="游戏领域博主",
    description="基于LangChain构建并由LangServe部署的游戏技术博主API"
)

add_routes(app, chain, path="/writer")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8080)