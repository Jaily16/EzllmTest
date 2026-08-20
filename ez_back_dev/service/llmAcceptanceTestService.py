from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from dao import testProjectDao
from llm.provider import LLMError
from llm.llm_chatGPT import ChatGPTModel
from prompt.templates import USE_CASE_INFO_TEMPLATE, \
    USE_CASE_INFO_MAP_TEMPLATE, USE_CASE_INFO_MAP_REDUCE_TEMPLATE, FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE, \
    FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE, ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE
from tools import documentTools
from tools.InfoType import InfoType
import prompt.promptStr as prompt
from vectorstore.splitter import testdoc_text_splitter_for_acceptance

llm = ChatGPTModel().get_model()


def find_out_requirement_info(pid: str):
    try:
        overflow = testProjectDao.get_project_type(pid).overflow
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_ACCEPTANCE_SUMMARY.value)
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
                    prompt.ACCEPTANCE_TEST_SUMMARY_MAP_PROMPT_STR,
                    prompt.ACCEPTANCE_TEST_SUMMARY_REDUCE_PROMPT_STR,
                    all_docs,
                    llm,
                    5
                )
                testProjectDao.add_project_info(pid, InfoType.PROJECT_ACCEPTANCE_SUMMARY.value, result)
        else:
            test_str = documentTools.generate_require_testdocs_str(pid)
            if history_result:
                result = history_result
            else:
                result = BasicChain.invoke_stuff_chain_get_str_with_str(
                    prompt.ACCEPTANCE_TEST_SUMMARY_PROMPT_STR,
                    test_str,
                    llm
                )
                testProjectDao.add_project_info(pid, InfoType.PROJECT_ACCEPTANCE_SUMMARY.value, result)
        return result
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_acceptance_test_knowledge(pid: str):
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
    try:
        acceptance_test_knowledge = find_acceptance_test_knowledge(pid)
        test_cases = get_acceptance_test_cases(acceptance_test_knowledge, info)
        return {"acceptance_test_knowledge": acceptance_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
