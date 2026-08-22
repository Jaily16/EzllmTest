
from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from dao import testProjectDao
from llm.provider import LLMError
from llm.llm_ChatGLM import ChatGLMModel
from llm.llm_Llama import LlamaModel
from llm.llm_MoonShot import MoonShotModel
from llm.llm_Spark import SparkModel
from llm.llm_TongYi import TongYiModel
from llm.llm_WenXin import WenXinModel
from llm.llm_chatGPT import ChatGPTModel
from prompt.templates import ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE, GENERATE_TEST_PLAN_TEMPLATE
from tools import documentTools
from tools.InfoType import InfoType
import prompt.promptStr as prompt
from tools.llmTools import choose_llm_by_name
from vectorstore.splitter import testdoc_text_splitter_for_acceptance
from service.legacyLongTextService import invoke_exhaustive_document_analysis

# 测试不同的llm看看(目前只支持调用5种模型好了，还可以支持不同版本)
TEST_PLAN_MINIMUM_TIMEOUT_SECONDS = 300.0


def generate_test_plan(pid: str, llm_name: str):
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
