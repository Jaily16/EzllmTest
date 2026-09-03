# 提供llm对业务文档集成测试智能分析的相关服务
import prompt.promptStr as prompt
from chain.KnowledgeChain import knowledge_retrieval_chain
from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.llm.gateway import LLMError
from infrastructure.llm.legacy_models import ChatGLMModel, ChatGPTModel
from chain.BasicChain import BasicChain
from model.ChainJsonModel import IntegrationTestMenu
from service.project import documents as documentTools
from tools.InfoType import InfoType
from service.retrieval.factory import design_retriever
from prompt.templates import (INTEGRATION_TEST_INFO_STUFF_TEMPLATE, INTEGRATION_TEST_INFO_MAP_TEMPLATE,
                              INTEGRATION_TEST_INFO_REDUCE_TEMPLATE, INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE,
                              INTEGRATION_TEST_GENERATE_TEST_CASE_TEMPLATE)
from service.retrieval.splitters import testdoc_text_splitter_for_integration
from service.legacy.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def get_integration_test_info(units_info: str):
    try:
        json_chain = BasicChain.json_chain(IntegrationTestMenu, llm)
        query = prompt.INTEGRATION_TEST_MENU_JSON_STR + units_info
        return json_chain.invoke({"query": query})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_integration_description(pid: str, integration_type: int, unit_name: str = ''):
    try:
        if integration_type == 0:
            return invoke_exhaustive_document_analysis(
                operation="integration_info",
                pid=pid,
                document_loader=documentTools.generate_design_testdocs_docs,
                splitter=testdoc_text_splitter_for_integration,
                stuff_prompt=prompt.INTEGRATION_TEST_SYSTEM_INFO_STUFF_PROMPT_STR,
                map_prompt=prompt.INTEGRATION_TEST_SYSTEM_INFO_MAP_PROMPT_STR,
                reduce_prompt=prompt.INTEGRATION_TEST_SYSTEM_INFO_REDUCE_PROMPT_STR,
                llm=llm_cn,
                max_concurrency=5,
            )
        if integration_type == 1:
            return invoke_exhaustive_document_analysis(
                operation="integration_info",
                pid=pid,
                document_loader=documentTools.generate_design_testdocs_docs,
                splitter=testdoc_text_splitter_for_integration,
                stuff_prompt=prompt.INTEGRATION_TEST_SUBSYSTEM_INFO_STUFF_PROMPT_STR,
                map_prompt=prompt.INTEGRATION_TEST_SUBSYSTEM_INFO_MAP_PROMPT_STR,
                reduce_prompt=prompt.INTEGRATION_TEST_SUBSYSTEM_INFO_REDUCE_PROMPT_STR,
                llm=llm_cn,
                max_concurrency=5,
            )

        if integration_type == 2:
            unit_type = "类(class)或模块"
        elif integration_type == 3:
            unit_type = "类(class)或函数"
        else:
            unit_type = "函数"
        design_docs = documentTools.generate_design_testdocs_docs(pid)
        selected_docs = design_retriever(design_docs).invoke(unit_name)
        doc_str = documentTools.docs_to_string(selected_docs)
        stuff_chain = BasicChain.stuff_chain(INTEGRATION_TEST_INFO_STUFF_TEMPLATE, llm_cn)
        return stuff_chain.invoke({"integration_unit": unit_name, "unit_type": unit_type, "docs": doc_str})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_integration_test_knowledge(pid: str, strategy_type: int):
    history_integration_test_knowledge = testProjectDao.get_project_info(pid,
                                                                         InfoType.PROJECT_INTEGRATION_TEST_KNOWLEDGE.value)
    history_static_blackbox_knowledge = testProjectDao.get_project_info(pid,
                                                                        InfoType.PROJECT_STATIC_BLACKBOX_KNOWLEDGE.value)
    if history_integration_test_knowledge and history_static_blackbox_knowledge:
        if strategy_type == 0:
            history_bigbang_knowledge = testProjectDao.get_project_info(pid,
                                                                        InfoType.PROJECT_INTEGRATION_BIGBANG_KNOWLEDGE.value)
            if history_bigbang_knowledge:
                return {"integration_test_knowledge": history_integration_test_knowledge,
                        "static_blackbox_knowledge": history_static_blackbox_knowledge,
                        "integration_strategy_knowledge": history_bigbang_knowledge}
        elif strategy_type == 1:
            history_topdown_knowledge = testProjectDao.get_project_info(pid,
                                                                        InfoType.PROJECT_INTEGRATION_TOP_DOWN_KNOWLEDGE.value)
            if history_topdown_knowledge:
                return {"integration_test_knowledge": history_integration_test_knowledge,
                        "static_blackbox_knowledge": history_static_blackbox_knowledge,
                        "integration_strategy_knowledge": history_topdown_knowledge}
        elif strategy_type == 2:
            history_bottomup_knowledge = testProjectDao.get_project_info(pid,
                                                                         InfoType.PROJECT_INTEGRATION_BOTTOM_UP_KNOWLEDGE.value)
            if history_bottomup_knowledge:
                return {"integration_test_knowledge": history_integration_test_knowledge,
                        "static_blackbox_knowledge": history_static_blackbox_knowledge,
                        "integration_strategy_knowledge": history_bottomup_knowledge}
        else:
            history_sandwich_knowledge = testProjectDao.get_project_info(pid,
                                                                         InfoType.PROJECT_INTEGRATION_SANDWICH_KNOWLEDGE.value)
            if history_sandwich_knowledge:
                return {"integration_test_knowledge": history_integration_test_knowledge,
                        "static_blackbox_knowledge": history_static_blackbox_knowledge,
                        "integration_strategy_knowledge": history_sandwich_knowledge}
    knowledge_docs = documentTools.generate_knowledge_docs(pid)
    knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
    if not history_integration_test_knowledge:
        integration_test_knowledge = knowledge_chain.invoke({"input": prompt.INTEGRATION_TEST_KNOWLEDGE_STR})[
            "answer"]
        testProjectDao.add_project_info(pid, InfoType.PROJECT_INTEGRATION_TEST_KNOWLEDGE.value,
                                        integration_test_knowledge)
    else:
        integration_test_knowledge = history_integration_test_knowledge
    if not history_static_blackbox_knowledge:
        static_blackbox_knowledge = \
            knowledge_chain.invoke({"input": prompt.UNIT_TEST_KNOWLEDGE_TEMPLATE_BLACKBOX_STR})[
                "answer"]
        testProjectDao.add_project_info(pid, InfoType.PROJECT_STATIC_BLACKBOX_KNOWLEDGE.value,
                                        static_blackbox_knowledge)
    else:
        static_blackbox_knowledge = history_static_blackbox_knowledge
    if strategy_type == 0:
        history_bigbang_knowledge = testProjectDao.get_project_info(pid,
                                                                    InfoType.PROJECT_INTEGRATION_BIGBANG_KNOWLEDGE.value)
        if not history_bigbang_knowledge:
            integration_strategy_knowledge = knowledge_chain.invoke({
                "input": INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE.format(
                    strategy="大爆炸集成(Big Bang Integration)")
            })["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_INTEGRATION_BIGBANG_KNOWLEDGE.value,
                                            integration_strategy_knowledge)
        else:
            integration_strategy_knowledge = history_bigbang_knowledge
    elif strategy_type == 1:
        history_topdown_knowledge = testProjectDao.get_project_info(pid,
                                                                    InfoType.PROJECT_INTEGRATION_TOP_DOWN_KNOWLEDGE.value)
        if not history_topdown_knowledge:
            integration_strategy_knowledge = knowledge_chain.invoke({
                "input": INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE.format(
                    strategy="自顶向下集成(Top-Down Integration)")
            })["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_INTEGRATION_TOP_DOWN_KNOWLEDGE.value,
                                            integration_strategy_knowledge)
        else:
            integration_strategy_knowledge = history_topdown_knowledge
    elif strategy_type == 2:
        history_bottomup_knowledge = testProjectDao.get_project_info(pid,
                                                                     InfoType.PROJECT_INTEGRATION_BOTTOM_UP_KNOWLEDGE.value)
        if not history_bottomup_knowledge:
            integration_strategy_knowledge = knowledge_chain.invoke({
                "input": INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE.format(
                    strategy="自底向上集成(Bottom-up Intagration)")
            })["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_INTEGRATION_BOTTOM_UP_KNOWLEDGE.value,
                                            integration_strategy_knowledge)
        else:
            integration_strategy_knowledge = history_bottomup_knowledge
    else:
        history_sandwich_knowledge = testProjectDao.get_project_info(pid,
                                                                     InfoType.PROJECT_INTEGRATION_SANDWICH_KNOWLEDGE.value)
        if not history_sandwich_knowledge:
            integration_strategy_knowledge = knowledge_chain.invoke({
                "input": INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE.format(
                    strategy="三明治集成(Sandwich Integration)")
            })["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_INTEGRATION_SANDWICH_KNOWLEDGE.value,
                                            integration_strategy_knowledge)
        else:
            integration_strategy_knowledge = history_sandwich_knowledge
    return {"integration_test_knowledge": integration_test_knowledge,
            "static_blackbox_knowledge": static_blackbox_knowledge,
            "integration_strategy_knowledge": integration_strategy_knowledge}


def generate_integration_test_cases(integration_test_knowledge: str, strategy: str, strategy_knowledge: str,
                                    blackbox_method_knowledge: str, integration_object: str,
                                    integration_object_info: str,
                                    output_type: int):
    try:
        if output_type == 0:
            output_template = prompt.UNIT_TEST_CASE_TXT_TEMPLATE
        elif output_type == 1:
            output_template = prompt.UNIT_TEST_CASE_MD_TEMPLATE
        elif output_type == 2:
            output_template = prompt.UNIT_TEST_CASE_XML_TEMPLATE
        else:
            output_template = prompt.UNIT_TEST_CASE_CSV_TEMPLATE
        test_case_chain = BasicChain.stuff_chain(INTEGRATION_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke(
            {"integration_test_knowledge": integration_test_knowledge, "static_method": "静态黑盒测试",
             "strategy": strategy, "strategy_knowledge": strategy_knowledge,
             "blackbox_knowledge": blackbox_method_knowledge, "integration_unit": integration_object,
             "case_template": output_template, "integration_unit_info": integration_object_info})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
