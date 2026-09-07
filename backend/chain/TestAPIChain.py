# 用来测试一下langserve
import os
import string

# from tools.documentTools import generate_testdocs_str
# from llm.llm_chatGPT import ChatGPTModel
# from prompt import promptStr
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
#
# llm = ChatGPTModel().get_model()
#
# pid = "Ez1789569184871481344"
# testdoc_str = generate_testdocs_str(pid)
# file = open("testdoc.txt", "wb")
# file.write(testdoc_str.encode("utf-8"))
# file.close()
#
# prompt = ChatPromptTemplate.from_messages([("system", promptStr.TESTDOC_SUMMARY_STUFF_PROMPT_STR),
#                                            ("human", "{input}")])
#
# chain = prompt | llm | StrOutputParser()
