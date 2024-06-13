# 提供llm对业务文档初步智能分析的相关服务
import os
import prompt.promptStr as prompt
from llm.llm_chatGPT import ChatGPTModel
from chain.BasicChain import BasicChain
from dao import testProjectDao
from tools import documentTools
from tools.InfoType import InfoType
from tools.llmTools import choose_llm_by_name
from vectorstore.splitter import testdoc_text_splitter_for_menu
from model.ChainJsonModel import TestMenu

# 利用langsmith监控运行
os.environ["LANGCHAIN_API_KEY"] = "ls__8f1d0a23c4cb4c9d8b58076ba3de84c7"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "LangServe_Service"

llm = ChatGPTModel().get_model()

llm_first = choose_llm_by_name("GLM-3")


def start_test_summarize_analyze(pid: str):
    try:
        # 先去数据库里面找有没有此前分析过的信息
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value)
        if history_result:
            return history_result
        overflow = testProjectDao.get_project_type(pid).overflow
        if overflow:
            # 先将所有的业务文档进行拼接成一个大的document数组
            test_all_docs = documentTools.generate_all_testdocs_docs(pid)
            # 对文档进行切分
            all_docs = testdoc_text_splitter_for_menu.split_documents(test_all_docs)
            # 用map-reduce链进行分析
            result = BasicChain.invoke_map_reduce_chain_get_str(
                prompt.TESTDOC_SUMMARY_MAP_REDUCE_PART_PROMPT_STR,
                prompt.TESTDOC_SUMMARY_MAP_REDUCE_TOTAL_PROMPT_STR,
                all_docs,
                llm,
                4
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value, result)
            return result
        else:
            test_str = documentTools.generate_all_testdocs_str(pid)
            result = BasicChain.invoke_stuff_chain_get_str_with_str(
                prompt.TESTDOC_SUMMARY_STUFF_PROMPT_STR,
                test_str,
                llm
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value, result)
            return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def restart_test_summarize_analyze(pid: str, llm_name: str):
    try:
        summarize_llm = choose_llm_by_name(llm_name)
        overflow = testProjectDao.get_project_type(pid).overflow
        if overflow:
            # 先将所有的业务文档进行拼接成一个大的document数组
            test_all_docs = documentTools.generate_all_testdocs_docs(pid)
            # 对文档进行切分
            all_docs = testdoc_text_splitter_for_menu.split_documents(test_all_docs)
            # 用map-reduce链进行分析
            result = BasicChain.invoke_map_reduce_chain_get_str(
                prompt.TESTDOC_SUMMARY_MAP_REDUCE_PART_PROMPT_STR,
                prompt.TESTDOC_SUMMARY_MAP_REDUCE_TOTAL_PROMPT_STR,
                all_docs,
                summarize_llm,
                4
            )
            testProjectDao.update_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value, result)
            return result
        else:
            test_str = documentTools.generate_all_testdocs_str(pid)
            result = BasicChain.invoke_stuff_chain_get_str_with_str(
                prompt.TESTDOC_SUMMARY_STUFF_PROMPT_STR,
                test_str,
                summarize_llm
            )
            testProjectDao.update_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value, result)
            return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_test_menu(summary: str):
    query = prompt.TESTDOC_JSON_MENU_PROMPT_STR + summary + "\n\n"
    chain = BasicChain.json_chain(TestMenu, llm)
    return chain.invoke({"query": query})
