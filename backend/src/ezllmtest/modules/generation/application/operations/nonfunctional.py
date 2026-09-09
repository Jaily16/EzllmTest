# 实现非功能相关生成操作，复用统一模型和知识接口；有效结果保存遵循上层工作流边界。
from ezllmtest.modules.generation.application.chains.basic import BasicChain
from ezllmtest.modules.generation.application.chains.knowledge import knowledge_retrieval_chain
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.platform.ai.gateway import LLMError
from ezllmtest.platform.ai.legacy_models import ChatGLMModel, ChatGPTModel
from ezllmtest.modules.generation.schemas.analysis import ApiList, NonfunctionalTestMethodList
from ezllmtest.modules.generation.domain.prompts.templates import NONFUNCTIONAL_TEST_KNOWLEDGE_TEMPLATE, NONFUNCTIONAL_TEST_GENERATE_TEST_CASE_TEMPLATE
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
from ezllmtest.modules.knowledge.public import nfunctional_retriever
import ezllmtest.modules.generation.domain.prompts.text as prompt

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_nonfunctional_info(pid: str):
    """优先复用非功能性摘要；未命中时从需求文档检索相关约束后生成并登记。"""
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
    """按测试方法名称从当前项目知识文档检索方法知识，本函数不登记新的知识缓存。"""
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
    """用方法名称、测试知识与需求信息调用非功能用例模板。"""
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
    """组合所选方法的知识和用例正文，模型异常保留给接口统一处理。"""
    try:
        nonfunctional_test_knowledge = find_nonfunctional_test_knowledge(pid, test_name)
        test_cases = get_nonfunctional_test_cases(nonfunctional_test_knowledge, info, test_name)
        return {"nonfunctional_test_knowledge": nonfunctional_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
