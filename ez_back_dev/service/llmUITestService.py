import os
from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from dao import testProjectDao
from llm.llm_ChatGLM import ChatGLMModel
from llm.llm_chatGPT import ChatGPTModel
from prompt.templates import UI_TEST_GENERATE_TEST_CASE_TEMPLATE
from tools import documentTools
from tools.InfoType import InfoType
from vectorstore.retrievers import design_retriever
import prompt.promptStr as prompt
from vectorstore.splitter import testdoc_text_splitter_for_unit, testdoc_text_splitter_for_ui

# 利用langsmith监控运行
os.environ["LANGCHAIN_API_KEY"] = "ls__8f1d0a23c4cb4c9d8b58076ba3de84c7"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "LangServe_Service"

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_ui_info(pid: str):
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_UI_SUMMARY.value)
        overflow = testProjectDao.get_project_type(pid).overflow
        if history_result:
            ui_info = history_result
        else:
            if overflow >= 3:
                # 先将所有的业务开发文档进行拼接成一个大的document数组
                test_all_docs = documentTools.generate_design_testdocs_docs(pid)
                # 对文档进行切分
                all_docs = testdoc_text_splitter_for_ui.split_documents(test_all_docs)
                map_str = prompt.UI_TEST_SUMMARY_MAP_PROMPT_STR
                reduce_str = prompt.UI_TEST_SUMMARY_REDUCE_PROMPT_STR
                ui_info = BasicChain.invoke_map_reduce_chain_get_str(
                    map_str,
                    reduce_str,
                    all_docs,
                    llm_cn,
                    5
                )
            else:
                test_str = documentTools.generate_design_testdocs_str(pid)
                ui_info = BasicChain.invoke_stuff_chain_get_str_with_str(prompt.UI_TEST_SUMMARY_PROMPT_STR,
                                                                         test_str,
                                                                         llm_cn)
            testProjectDao.add_project_info(pid, InfoType.PROJECT_UI_SUMMARY.value, ui_info)
        return ui_info
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_ui_test_knowledge(pid: str):
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_UI_TEST_KNOWLEDGE.value)
        if history_result:
            return history_result
        else:
            knowledge_docs = documentTools.generate_knowledge_docs(pid)
            knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
            ui_test_knowledge = knowledge_chain.invoke({"input": prompt.UI_TEST_KNOWLEDGE_STR})["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_UI_TEST_KNOWLEDGE.value,
                                            ui_test_knowledge)
            return ui_test_knowledge
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_ui_test_cases(ui_test_knowledge: str, info: str):
    try:
        test_case_chain = BasicChain.stuff_chain(UI_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke({"ui_test_knowledge": ui_test_knowledge, "content": info})
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_ui_test_cases(pid: str, info: str):
    try:
        ui_test_knowledge = find_ui_test_knowledge(pid)
        test_cases = get_ui_test_cases(ui_test_knowledge, info)
        return {"ui_test_knowledge": ui_test_knowledge, "test_cases": test_cases}
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
