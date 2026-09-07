from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.llm.gateway import LLMError
from infrastructure.llm.legacy_models import (
    ChatGLMModel,
    ChatGPTModel,
    GPT4Model,
    MoonShotModel,
    TongYiModel,
    WenXinModel,
)
from model.ChainJsonModel import ApiList, UseCaseList
from prompt.templates import USE_CASE_INFO_TEMPLATE, \
    USE_CASE_INFO_MAP_TEMPLATE, USE_CASE_INFO_MAP_REDUCE_TEMPLATE, FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE, \
    FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE
from service.project import documents as documentTools
from tools.InfoType import InfoType
from service.retrieval.factory import require_retriever
import prompt.promptStr as prompt
from service.retrieval.splitters import testdoc_text_splitter_for_use_case
from service.legacy.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()
llm_cn = GPT4Model().get_model()


def find_out_use_cases_info(pid: str):
    """查找OUT USE用例信息，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。"""
    try:
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_FUNCTIONAL_SUMMARY.value)
        if history_result:
            result = history_result
        else:
            result = invoke_exhaustive_document_analysis(
                operation="functional_info",
                pid=pid,
                document_loader=documentTools.generate_require_testdocs_docs,
                splitter=testdoc_text_splitter_for_use_case,
                stuff_prompt=prompt.FUNCTIONAL_TEST_SUMMARY_STUFF_PROMPT_STR,
                map_prompt=prompt.FUNCTIONAL_TEST_SUMMARY_MAP_PROMPT_STR,
                reduce_prompt=prompt.FUNCTIONAL_TEST_SUMMARY_REDUCE_PROMPT_STR,
                llm=llm_cn,
                max_concurrency=3,
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_FUNCTIONAL_SUMMARY.value, result)
        json_chain = BasicChain.json_chain(UseCaseList, llm)
        query = prompt.FUNCTIONAL_TEST_JSON_PROMPT_STR + result
        return {"text_info": result, "list_info": json_chain.invoke({"query": query})}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_out_use_case_info(pid: str, use_case_name: str):
    """查找OUT USE用例信息，并遵循现有调用契约。"""
    try:
        require_docs = documentTools.generate_require_testdocs_docs(pid)
        uc_docs = require_retriever(require_docs).invoke(use_case_name)
        uc_str = documentTools.docs_to_meaningful_strings(uc_docs)
        stuff_chain = BasicChain.stuff_chain(USE_CASE_INFO_TEMPLATE, llm_cn)
        uc_info = stuff_chain.invoke({"use_case_name": use_case_name, "docs": uc_str})
        return uc_info
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_functional_test_knowledge(pid: str):
    """查找功能测试测试知识库，并遵循现有调用契约。

    参数:
        `pid`：项目 ID。"""
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_FUNCTION_TEST_KNOWLEDGE.value)
        if history_result:
            return history_result
        else:
            knowledge_docs = documentTools.generate_knowledge_docs(pid)
            knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
            functional_test_knowledge = knowledge_chain.invoke({"input": prompt.FUNCTIONAL_TEST_KNOWLEDGE_STR})[
                "answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_FUNCTION_TEST_KNOWLEDGE.value,
                                            functional_test_knowledge)
            return functional_test_knowledge
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_functional_test_cases(functional_test_knowledge: str, info: str, test_type: int, output_type: int,
                              use_case_name: str = ''):
    """获取功能测试测试用例，并遵循现有调用契约。

    参数:
        `functional_test_knowledge`：沿用签名中 `str` 类型约束的输入。
        `info`：沿用签名中 `str` 类型约束的输入。
        `test_type`：沿用签名中 `int` 类型约束的输入。
        `output_type`：沿用签名中 `int` 类型约束的输入。
        `use_case_name`：沿用签名中 `str` 类型约束的输入。"""
    try:
        if output_type == 0:
            output_template = prompt.UNIT_TEST_CASE_TXT_TEMPLATE
        elif output_type == 1:
            output_template = prompt.UNIT_TEST_CASE_MD_TEMPLATE
        elif output_type == 2:
            output_template = prompt.UNIT_TEST_CASE_XML_TEMPLATE
        else:
            output_template = prompt.UNIT_TEST_CASE_CSV_TEMPLATE
        if test_type == 1:
            test_case_chain = BasicChain.stuff_chain(FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE, llm)
            return test_case_chain.invoke(
                {"functional_test_knowledge": functional_test_knowledge, "use_case": use_case_name,
                 "content": info, "case_template": output_template})
        else:
            test_case_chain = BasicChain.stuff_chain(FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE, llm)
            return test_case_chain.invoke({"functional_test_knowledge": functional_test_knowledge,
                                           "content": info, "case_template": output_template})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_functional_test_cases(pid: str, info: str, test_type: int, output_type: int, use_case_name: str = ''):
    """生成功能测试测试用例，并遵循现有调用契约。"""
    try:
        if use_case_name != '':
            info = find_out_use_case_info(pid, use_case_name)
        functional_test_knowledge = find_functional_test_knowledge(pid)
        test_cases = get_functional_test_cases(functional_test_knowledge, info, test_type, output_type, use_case_name)
        return {"functional_test_knowledge": functional_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
