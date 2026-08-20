from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from dao import testProjectDao
from llm.provider import LLMError
from llm.llm_ChatGLM import ChatGLMModel
from llm.llm_GPT4 import GPT4Model
from llm.llm_MoonShot import MoonShotModel
from llm.llm_TongYi import TongYiModel
from llm.llm_WenXin import WenXinModel
from llm.llm_chatGPT import ChatGPTModel
from model.ChainJsonModel import ApiList, UseCaseList
from prompt.templates import USE_CASE_INFO_TEMPLATE, \
    USE_CASE_INFO_MAP_TEMPLATE, USE_CASE_INFO_MAP_REDUCE_TEMPLATE, FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE, \
    FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE
from tools import documentTools
from tools.InfoType import InfoType
from vectorstore.retrievers import require_retriever
import prompt.promptStr as prompt
from vectorstore.splitter import testdoc_text_splitter_for_use_case

llm = ChatGPTModel().get_model()
llm_cn = GPT4Model().get_model()


def find_out_use_cases_info(pid: str):
    try:
        overflow = testProjectDao.get_project_type(pid).overflow
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_FUNCTIONAL_SUMMARY.value)
        if overflow == 1 or overflow == 4:
            # 先将所有的业务需求文档进行拼接成一个大的document数组
            test_all_docs = documentTools.generate_require_testdocs_docs(pid)
            # 对文档进行切分
            all_docs = testdoc_text_splitter_for_use_case.split_documents(test_all_docs)
            if history_result:
                result = history_result
            else:
                # 用map-reduce链进行分析
                result = BasicChain.invoke_map_reduce_chain_get_str(
                    prompt.FUNCTIONAL_TEST_SUMMARY_MAP_PROMPT_STR,
                    prompt.FUNCTIONAL_TEST_SUMMARY_REDUCE_PROMPT_STR,
                    all_docs,
                    llm,
                    3
                )
                testProjectDao.add_project_info(pid, InfoType.PROJECT_FUNCTIONAL_SUMMARY.value, result)
            json_chain = BasicChain.json_chain(UseCaseList, llm)
            query = prompt.FUNCTIONAL_TEST_JSON_PROMPT_STR + result
            return {"text_info": result, "list_info": json_chain.invoke({"query": query})}
        else:
            test_str = documentTools.generate_require_testdocs_str(pid)
            if history_result:
                result = history_result
            else:
                result = BasicChain.invoke_stuff_chain_get_str_with_str(
                    prompt.FUNCTIONAL_TEST_SUMMARY_STUFF_PROMPT_STR,
                    test_str,
                    llm_cn
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
    try:
        require_docs = documentTools.generate_require_testdocs_docs(pid)
        uc_docs = require_retriever(require_docs).invoke(use_case_name)
        uc_str = documentTools.docs_to_meaningful_strings(uc_docs)
        tokens = documentTools.num_tokens_from_string(uc_str)
        if tokens > 14500:
            map_str = USE_CASE_INFO_MAP_TEMPLATE.format(use_case_name=use_case_name)
            reduce_str = USE_CASE_INFO_MAP_REDUCE_TEMPLATE.format(use_case_name=use_case_name)
            uc_info = BasicChain.invoke_map_reduce_chain_get_str(
                map_str,
                reduce_str,
                uc_docs,
                llm_cn,
                2
            )
        else:
            stuff_chain = BasicChain.stuff_chain(USE_CASE_INFO_TEMPLATE, llm_cn)
            uc_info = stuff_chain.invoke({"use_case_name": use_case_name, "docs": uc_str})
        return uc_info
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_functional_test_knowledge(pid: str):
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
