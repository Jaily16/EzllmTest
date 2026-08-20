
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

# 测试不同的llm看看(目前只支持调用5种模型好了，还可以支持不同版本)
TEST_PLAN_MINIMUM_TIMEOUT_SECONDS = 300.0


def generate_test_plan(pid: str, llm_name: str):
    try:
        overflow = testProjectDao.get_project_type(pid).overflow
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_TEST_PLAN.value)
        llm_plan = choose_llm_by_name(
            llm_name,
            minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
        )
        if overflow == 1 or overflow == 4:
            # 先将所有的业务需求文档进行拼接成一个大的document数组
            test_all_docs = documentTools.generate_require_testdocs_docs(pid)
            # 对文档进行切分
            all_docs = testdoc_text_splitter_for_acceptance.split_documents(test_all_docs)
            if history_result:
                result = history_result
            else:
                # 用map-reduce链进行分析
                result = BasicChain.invoke_map_reduce_chain_get_str(
                    prompt.TEST_PLAN_MAP_REDUCE_PART_PROMPT_STR,
                    prompt.TEST_PLAN_MAP_REDUCE_TOTAL_PROMPT_STR,
                    all_docs,
                    llm_plan,
                    5
                )
                testProjectDao.add_project_info(pid, InfoType.PROJECT_TEST_PLAN.value, result)
        else:
            test_str = documentTools.generate_require_testdocs_str(pid)
            if history_result:
                result = history_result
            else:
                result = BasicChain.invoke_stuff_chain_get_str_with_str(
                    prompt.TEST_PLAN_STUFF_PROMPT_STR,
                    test_str,
                    llm_plan
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
        overflow = testProjectDao.get_project_type(pid).overflow
        llm_plan = choose_llm_by_name(
            llm_name,
            minimum_timeout_seconds=TEST_PLAN_MINIMUM_TIMEOUT_SECONDS,
        )
        if overflow == 1 or overflow == 4:
            # 先将所有的业务需求文档进行拼接成一个大的document数组
            test_all_docs = documentTools.generate_require_testdocs_docs(pid)
            # 对文档进行切分
            all_docs = testdoc_text_splitter_for_acceptance.split_documents(test_all_docs)
            # 用map-reduce链进行分析
            result = BasicChain.invoke_map_reduce_chain_get_str(
                prompt.TEST_PLAN_MAP_REDUCE_PART_PROMPT_STR,
                prompt.TEST_PLAN_MAP_REDUCE_TOTAL_PROMPT_STR,
                all_docs,
                llm_plan,
                5
            )
            testProjectDao.update_project_info(pid, InfoType.PROJECT_TEST_PLAN.value, result)
        else:
            test_str = documentTools.generate_require_testdocs_str(pid)
            result = BasicChain.invoke_stuff_chain_get_str_with_str(
                prompt.TEST_PLAN_STUFF_PROMPT_STR,
                test_str,
                llm_plan
            )
            testProjectDao.update_project_info(pid, InfoType.PROJECT_TEST_PLAN.value, result)
        return result
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
