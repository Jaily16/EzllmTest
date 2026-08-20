from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from dao import testProjectDao
from llm.provider import LLMError
from llm.llm_ChatGLM import ChatGLMModel
from llm.llm_chatGPT import ChatGPTModel
from model.ChainJsonModel import ApiList, NonfunctionalTestMethodList
from prompt.templates import NONFUNCTIONAL_TEST_KNOWLEDGE_TEMPLATE, NONFUNCTIONAL_TEST_GENERATE_TEST_CASE_TEMPLATE
from tools import documentTools
from tools.InfoType import InfoType
from vectorstore.retrievers import nfunctional_retriever
import prompt.promptStr as prompt

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_nonfunctional_info(pid: str):
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_NONFUNCTIONAL_SUMMARY.value)
        if history_result:
            nonfunctional_info = history_result
        else:
            require_docs = documentTools.generate_require_testdocs_docs(pid)
            retriever = nfunctional_retriever(require_docs)
            nonfunctional_docs = retriever.invoke("非功能性需求[性能 (Performance) 可扩展性 (Scalability) "
                                                  "可靠性 (Reliability) 可用性 (Availability) 安全性 (Security) "
                                                  "可维护性 (Maintainability) 可移植性 (Portability) 兼容性 (Compatibility) "
                                                  "可测试性 (Testability) 用户友好性 (Usability) 响应时间 (Response Time)"
                                                  "容量 (Capacity) 数据完整性 (Data Integrity) 灾难恢复 (Disaster Recovery) "
                                                  "合规性 (Compliance) 可配置性 (Configurability) "
                                                  "国际化和本地化 (Internationalization and Localization) 日志记录 (Logging)"
                                                  "监控 (Monitoring) 存储需求 (Storage Requirements)]")
            nonfunctional_docs_str = documentTools.docs_to_meaningful_strings(nonfunctional_docs)
            tokens = documentTools.num_tokens_from_string(nonfunctional_docs_str)
            if tokens > 14500:
                map_str = prompt.NONFUNCTIONAL_TEST_SUMMARY_MAP_PROMPT_STR
                reduce_str = prompt.NONFUNCTIONAL_SUMMARY_REDUCE_PROMPT_STR
                nonfunctional_info = BasicChain.invoke_map_reduce_chain_get_str(
                    map_str,
                    reduce_str,
                    nonfunctional_docs,
                    llm_cn,
                    3
                )
            else:
                nonfunctional_info = BasicChain.invoke_stuff_chain_get_str_with_str(
                    prompt.NONFUNCTIONAL_TEST_SUMMARY_PROMPT_STR,
                    nonfunctional_docs_str,
                    llm_cn)
            testProjectDao.add_project_info(pid, InfoType.PROJECT_NONFUNCTIONAL_SUMMARY.value, nonfunctional_info)
        nonfunctional_list_chain = BasicChain.json_chain(NonfunctionalTestMethodList, llm)
        query = prompt.NONFUNCTIONAL_TEST_JSON_PROMPT_STR + nonfunctional_info
        nonfunctional_list_json = nonfunctional_list_chain.invoke({"query": query})
        return {"nonfunctional_info": nonfunctional_info, "list": nonfunctional_list_json}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_nonfunctional_test_knowledge(pid: str, test_name: str):
    try:
        knowledge_docs = documentTools.generate_knowledge_docs(pid)
        knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
        nonfunctional_test_knowledge = \
            knowledge_chain.invoke({"input": NONFUNCTIONAL_TEST_KNOWLEDGE_TEMPLATE.format(test_name=test_name)})[
                "answer"]
        return nonfunctional_test_knowledge
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_nonfunctional_test_cases(nonfunctional_test_knowledge: str, info: str, method_name: str):
    try:
        test_case_chain = BasicChain.stuff_chain(NONFUNCTIONAL_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke({"knowledge": nonfunctional_test_knowledge,
                                       "content": info, "test_name": method_name})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_nonfunctional_test_cases(pid: str, info: str, test_name: str):
    try:
        nonfunctional_test_knowledge = find_nonfunctional_test_knowledge(pid, test_name)
        test_cases = get_nonfunctional_test_cases(nonfunctional_test_knowledge, info, test_name)
        return {"nonfunctional_test_knowledge": nonfunctional_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
