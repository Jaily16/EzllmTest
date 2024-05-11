import os
os.environ["OPENAI_API_KEY"] = "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"

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

st.title('应用产品描述生成器')
prompt = ChatPromptTemplate.from_template("请编写一篇关于{topic}的软件产品描述，不超过200个字")
model = ChatOpenAI()
chain = prompt | model | StrOutputParser()

with st.form('my_form'):
    text = st.text_area('请输入主题词:', '游戏引擎')
    submitted = st.form_submit_button('提交')
    if submitted:
        st.info(chain.invoke({"topic": text}))
    chain.get_graph().print_ascii()