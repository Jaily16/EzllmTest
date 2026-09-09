# 实现项目摘要相关生成操作，复用统一模型和知识接口；有效结果保存遵循上层工作流边界。
# 提供llm对业务文档初步智能分析的相关服务
import ezllmtest.modules.generation.domain.prompts.text as prompt
from ezllmtest.platform.ai.legacy_models import ChatGPTModel
from ezllmtest.modules.generation.application.chains.basic import BasicChain
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.platform.ai.gateway import LLMError
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
from ezllmtest.platform.ai.selection import choose_llm_by_name
from ezllmtest.modules.knowledge.public import testdoc_text_splitter_for_menu
from ezllmtest.modules.generation.schemas.analysis import TestMenu
from ezllmtest.modules.generation.application.operations.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()

def start_test_summarize_analyze(pid: str):
    """已有项目摘要时直接复用；缺失时完整分析需求与设计文档并保存。"""
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
    """根据显式模型重新完整分析项目文档，成功结果更新已有摘要。"""
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
    """将项目摘要和固定指令交给结构化菜单链，返回通过 TestMenu schema 的结果。"""
    query = prompt.TESTDOC_JSON_MENU_PROMPT_STR + summary + "\n\n"
    chain = BasicChain.json_chain(TestMenu, llm)
    return chain.invoke({"query": query})
