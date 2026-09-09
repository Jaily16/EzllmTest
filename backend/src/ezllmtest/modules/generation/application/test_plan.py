# 编排项目摘要、计划与菜单生成，三者共同构成项目分析结果。

from ezllmtest.modules.generation.application.chains.basic import BasicChain
from ezllmtest.modules.generation.application.chains.knowledge import knowledge_retrieval_chain
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.platform.ai.gateway import LLMError
from ezllmtest.platform.ai.legacy_models import ChatGLMModel, ChatGPTModel, LlamaModel, MoonShotModel, SparkModel, TongYiModel, WenXinModel
from ezllmtest.modules.generation.domain.prompts.templates import ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE, GENERATE_TEST_PLAN_TEMPLATE
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
import ezllmtest.modules.generation.domain.prompts.text as prompt
from ezllmtest.platform.ai.selection import choose_llm_by_name
from ezllmtest.modules.knowledge.public import testdoc_text_splitter_for_acceptance
from ezllmtest.modules.generation.application.operations.long_text import invoke_exhaustive_document_analysis

# 测试不同的llm看看(目前只支持调用5种模型好了，还可以支持不同版本)
TEST_PLAN_MINIMUM_TIMEOUT_SECONDS = 300.0


def generate_test_plan(pid: str, llm_name: str):
    """读取已有计划或完整分析需求文档生成计划，模型选择使用计划专属最低超时。"""
    try:
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_TEST_PLAN.value)
        llm_plan = choose_llm_by_name(
            llm_name,
            minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
        )
        if history_result:
            result = history_result
        else:
            result = invoke_exhaustive_document_analysis(
                operation="project_analysis",
                pid=pid,
                document_loader=documentTools.generate_require_testdocs_docs,
                splitter=testdoc_text_splitter_for_acceptance,
                stuff_prompt=prompt.TEST_PLAN_STUFF_PROMPT_STR,
                map_prompt=prompt.TEST_PLAN_MAP_REDUCE_PART_PROMPT_STR,
                reduce_prompt=prompt.TEST_PLAN_MAP_REDUCE_TOTAL_PROMPT_STR,
                llm=llm_plan,
                max_concurrency=5,
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_TEST_PLAN.value, result)
        return result
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 重新生成测试计划
def generate_test_plan_again(pid: str, llm_name: str):
    """显式重新生成测试计划并更新既有记录，失败不转换为有效计划。"""
    try:
        llm_plan = choose_llm_by_name(
            llm_name,
            minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
        )
        result = invoke_exhaustive_document_analysis(
            operation="project_analysis",
            pid=pid,
            document_loader=documentTools.generate_require_testdocs_docs,
            splitter=testdoc_text_splitter_for_acceptance,
            stuff_prompt=prompt.TEST_PLAN_STUFF_PROMPT_STR,
            map_prompt=prompt.TEST_PLAN_MAP_REDUCE_PART_PROMPT_STR,
            reduce_prompt=prompt.TEST_PLAN_MAP_REDUCE_TOTAL_PROMPT_STR,
            llm=llm_plan,
            max_concurrency=5,
        )
        testProjectDao.update_project_info(pid, InfoType.PROJECT_TEST_PLAN.value, result)
        return result
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
