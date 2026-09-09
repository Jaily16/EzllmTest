# 实现验收相关生成操作，复用统一模型和知识接口；有效结果保存遵循上层工作流边界。
from ezllmtest.modules.generation.application.chains.basic import BasicChain
from ezllmtest.modules.generation.application.chains.knowledge import knowledge_retrieval_chain
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.platform.ai.gateway import LLMError
from ezllmtest.platform.ai.legacy_models import ChatGPTModel
from ezllmtest.modules.generation.domain.prompts.templates import USE_CASE_INFO_TEMPLATE, USE_CASE_INFO_MAP_TEMPLATE, USE_CASE_INFO_MAP_REDUCE_TEMPLATE, FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE, FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE, ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
import ezllmtest.modules.generation.domain.prompts.text as prompt
from ezllmtest.modules.knowledge.public import testdoc_text_splitter_for_acceptance
from ezllmtest.modules.generation.application.operations.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()


def find_out_requirement_info(pid: str):
    """优先复用已保存验收需求摘要；缺失时完整分析需求文档并登记结果。"""
    try:
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_ACCEPTANCE_SUMMARY.value)
        if history_result:
            result = history_result
        else:
            result = invoke_exhaustive_document_analysis(
                operation="acceptance_info",
                pid=pid,
                document_loader=documentTools.generate_require_testdocs_docs,
                splitter=testdoc_text_splitter_for_acceptance,
                stuff_prompt=prompt.ACCEPTANCE_TEST_SUMMARY_PROMPT_STR,
                map_prompt=prompt.ACCEPTANCE_TEST_SUMMARY_MAP_PROMPT_STR,
                reduce_prompt=prompt.ACCEPTANCE_TEST_SUMMARY_REDUCE_PROMPT_STR,
                llm=llm,
                max_concurrency=5,
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_ACCEPTANCE_SUMMARY.value, result)
        return result
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_acceptance_test_knowledge(pid: str):
    """优先读取项目验收知识，缺失时从项目知识文档检索并登记以供复用。"""
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_ACCEPTANCE_TEST_KNOWLEDGE.value)
        if history_result:
            return history_result
        else:
            knowledge_docs = documentTools.generate_knowledge_docs(pid)
            knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
            acceptance_test_knowledge = knowledge_chain.invoke({"input": prompt.ACCEPTANCE_TEST_KNOWLEDGE_STR})[
                "answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_ACCEPTANCE_TEST_KNOWLEDGE.value,
                                            acceptance_test_knowledge)
            return acceptance_test_knowledge
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_acceptance_test_cases(acceptance_test_knowledge: str, info: str):
    """把验收知识与需求信息填入既有生成模板；模型错误向上抛出，其他异常保留历史失败返回。"""
    try:
        test_case_chain = BasicChain.stuff_chain(ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke(
            {"acceptance_test_knowledge": acceptance_test_knowledge, "content": info})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_acceptance_test_cases(pid: str, info: str):
    """组合项目验收知识与生成用例，返回知识和用例两部分给调用方。"""
    try:
        acceptance_test_knowledge = find_acceptance_test_knowledge(pid)
        test_cases = get_acceptance_test_cases(acceptance_test_knowledge, info)
        return {"acceptance_test_knowledge": acceptance_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
