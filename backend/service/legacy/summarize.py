# 提供llm对业务文档初步智能分析的相关服务
import prompt.promptStr as prompt
from infrastructure.llm.legacy_models import ChatGPTModel
from chain.BasicChain import BasicChain
from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.llm.gateway import LLMError
from service.project import documents as documentTools
from tools.InfoType import InfoType
from infrastructure.llm.selection import choose_llm_by_name
from service.retrieval.splitters import testdoc_text_splitter_for_menu
from model.ChainJsonModel import TestMenu
from service.legacy.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()

def start_test_summarize_analyze(pid: str):
    """启动测试摘要分析，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。"""
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
    """重新启动测试摘要分析，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。
        `llm_name`：界面选择的模型标识。"""
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
    """获取测试测试菜单，并遵循现有调用契约。"""
    query = prompt.TESTDOC_JSON_MENU_PROMPT_STR + summary + "\n\n"
    chain = BasicChain.json_chain(TestMenu, llm)
    return chain.invoke({"query": query})
