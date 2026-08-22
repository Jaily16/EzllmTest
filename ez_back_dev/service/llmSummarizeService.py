# 提供llm对业务文档初步智能分析的相关服务
import prompt.promptStr as prompt
from llm.llm_chatGPT import ChatGPTModel
from chain.BasicChain import BasicChain
from dao import testProjectDao
from llm.provider import LLMError
from tools import documentTools
from tools.InfoType import InfoType
from tools.llmTools import choose_llm_by_name
from vectorstore.splitter import testdoc_text_splitter_for_menu
from model.ChainJsonModel import TestMenu
from service.legacyLongTextService import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()

def start_test_summarize_analyze(pid: str):
    try:
        # 先去数据库里面找有没有此前分析过的信息
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value)
        if history_result:
            return history_result
        result = invoke_exhaustive_document_analysis(
            operation="project_analysis",
            pid=pid,
            document_loader=documentTools.generate_all_testdocs_docs,
            splitter=testdoc_text_splitter_for_menu,
            stuff_prompt=prompt.TESTDOC_SUMMARY_STUFF_PROMPT_STR,
            map_prompt=prompt.TESTDOC_SUMMARY_MAP_REDUCE_PART_PROMPT_STR,
            reduce_prompt=prompt.TESTDOC_SUMMARY_MAP_REDUCE_TOTAL_PROMPT_STR,
            llm=llm,
            max_concurrency=4,
        )
        testProjectDao.add_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value, result)
        return result
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def restart_test_summarize_analyze(pid: str, llm_name: str):
    try:
        summarize_llm = choose_llm_by_name(llm_name)
        result = invoke_exhaustive_document_analysis(
            operation="project_analysis",
            pid=pid,
            document_loader=documentTools.generate_all_testdocs_docs,
            splitter=testdoc_text_splitter_for_menu,
            stuff_prompt=prompt.TESTDOC_SUMMARY_STUFF_PROMPT_STR,
            map_prompt=prompt.TESTDOC_SUMMARY_MAP_REDUCE_PART_PROMPT_STR,
            reduce_prompt=prompt.TESTDOC_SUMMARY_MAP_REDUCE_TOTAL_PROMPT_STR,
            llm=summarize_llm,
            max_concurrency=4,
        )
        testProjectDao.update_project_info(pid, InfoType.PROJECT_INITIAL_SUMMARY.value, result)
        return result
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_test_menu(summary: str):
    query = prompt.TESTDOC_JSON_MENU_PROMPT_STR + summary + "\n\n"
    chain = BasicChain.json_chain(TestMenu, llm)
    return chain.invoke({"query": query})
