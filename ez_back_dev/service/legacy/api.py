from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.llm.gateway import LLMError
from infrastructure.llm.legacy_models import ChatGLMModel, ChatGPTModel
from model.ChainJsonModel import ApiList
from prompt.templates import API_TEST_INFO_TEMPLATE, API_TEST_GENERATE_TEST_CASE_TEMPLATE, \
    APIS_TEST_GENERATE_TEST_CASE_TEMPLATE, API_TEST_INFO_MAP_REDUCE_TEMPLATE
from service.project import documents as documentTools
from tools.InfoType import InfoType
from service.retrieval.factory import api_retriever
import prompt.promptStr as prompt
from service.retrieval.splitters import testdoc_text_splitter_for_unit
from service.legacy.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_apis_info(pid: str):
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_APIS_SUMMARY.value)
        if history_result:
            apis_info = history_result
        else:
            apis_info = invoke_exhaustive_document_analysis(
                operation="api_info",
                pid=pid,
                document_loader=documentTools.generate_design_testdocs_docs,
                splitter=testdoc_text_splitter_for_unit,
                stuff_prompt=prompt.API_TEST_SUMMARY_PROMPT_STR,
                map_prompt=prompt.API_TEST_SUMMARY_MAP_PROMPT_STR,
                reduce_prompt=prompt.API_TEST_SUMMARY_REDUCE_PROMPT_STR,
                llm=llm_cn,
                max_concurrency=3,
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_APIS_SUMMARY.value, apis_info)
        api_list_chain = BasicChain.json_chain(ApiList, llm)
        query = prompt.API_TEST_JSON_PROMPT_STR + apis_info
        api_list_json = api_list_chain.invoke({"query": query})
        return {"apis_info": apis_info, "list": api_list_json}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_out_api_info(pid: str, api_name: str):
    try:
        design_docs = documentTools.generate_design_testdocs_docs(pid)
        retriever = api_retriever(design_docs)
        api_docs = retriever.invoke(api_name)
        api_docs_str = documentTools.docs_to_meaningful_strings(api_docs)
        stuff_chain = BasicChain.stuff_chain(API_TEST_INFO_TEMPLATE, llm_cn)
        api_info = stuff_chain.invoke({"api_name": api_name, "docs": api_docs_str})
        return api_info
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_api_test_knowledge(pid: str):
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_API_TEST_KNOWLEDGE.value)
        if history_result:
            return history_result
        else:
            knowledge_docs = documentTools.generate_knowledge_docs(pid)
            knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
            api_test_knowledge = knowledge_chain.invoke({"input": prompt.API_TEST_KNOWLEDGE_STR})["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_API_TEST_KNOWLEDGE.value,
                                            api_test_knowledge)
            return api_test_knowledge
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_api_test_cases(api_test_knowledge: str, info: str, test_type: int, output_type: int, api_name: str = ''):
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
            test_case_chain = BasicChain.stuff_chain(API_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
            return test_case_chain.invoke({"api_test_knowledge": api_test_knowledge, "api_name": api_name,
                                           "content": info, "case_template": output_template})
        else:
            test_case_chain = BasicChain.stuff_chain(APIS_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
            return test_case_chain.invoke({"api_test_knowledge": api_test_knowledge,
                                           "content": info, "case_template": output_template})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_api_test_cases(pid: str, info: str, test_type: int, output_type: int, api_name: str = ''):
    try:
        if api_name != '':
            info = find_out_api_info(pid, api_name)
        api_test_knowledge = find_api_test_knowledge(pid)
        test_cases = get_api_test_cases(api_test_knowledge, info, test_type, output_type, api_name)
        return {"api_test_knowledge": api_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
