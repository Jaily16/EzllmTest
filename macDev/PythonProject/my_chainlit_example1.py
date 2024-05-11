import chainlit as cl
import os

os.environ["OPENAI_API_KEY"] = "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"

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI


@cl.on_chat_start
async def on_chat_start():
    model = ChatOpenAI(streaming=True)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一名软件测试专家，你能够为软件工程人员设计的软件提供优秀的测试建议。",
            ),
            ("human", "{question}"),
        ]
    )
    runnable = prompt | model | StrOutputParser()
    cl.user_session.set("runnable", runnable)


@cl.on_message
async def on_message(message: cl.Message):
    runnable = cl.user_session.get("runnable")
    runnable.get_graph().print.ascii()

    msg = cl.Message(content="")

    async for chunk in runnable.astream(
            {"question": message.content},
            config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()]),
    ):
        await msg.stream_token(chunk)

    await msg.send()
