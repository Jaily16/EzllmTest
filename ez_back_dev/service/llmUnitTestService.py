# 提供llm对业务文档单元测试智能分析的相关服务
import os
import prompt.promptStr as prompt
from llm.llm_chatGPT import ChatGPTModel
from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from dao import testProjectDao
from tools import documentTools
from tools.InfoType import InfoType
from tools.llmTools import choose_llm_by_name
from vectorstore.splitter import testdoc_text_splitter_for_unit
from model.ChainJsonModel import UnitTestMenu, UnitTestMethod
from vectorstore.retrievers import design_retriever
from prompt.templates import (UNIT_TEST_UNIT_INFO_MAP_TEMPLATE, UNIT_TEST_UNIT_INFO_REDUCE_TEMPLATE,
                              UNIT_TEST_UNIT_INFO_STUFF_TEMPLATE, UNIT_TEST_TYPE_JSON_TEMPLATE,
                              UNIT_TEST_GENERATE_TEST_CASE_TEMPLATE_2)

# 利用langsmith监控运行
os.environ["LANGCHAIN_API_KEY"] = "ls__8f1d0a23c4cb4c9d8b58076ba3de84c7"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "LangServe_Service"

llm = ChatGPTModel().get_model()

# llm_test = ChatGPTModel().get_model()
# llm_test = WenXinModel().get_model()
# llm_test = TongYiModel().get_model()
# llm_test = ChatGLMModel().get_model()
# llm_test = MoonShotModel().get_model()


def summarize_unit_info(pid: str, llm_name: str):
    try:
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_UNITS_SUMMARY.value)
        if history_result:
            json_chain = BasicChain.json_chain(UnitTestMenu, llm)
            query = prompt.UNIT_TEST_FIND_UNIT_INFO_JSON_STR + history_result
            return {"text_info": history_result, "list_info": json_chain.invoke({"query": query})}
        overflow = testProjectDao.get_project_type(pid).overflow
        summarize_llm = choose_llm_by_name(llm_name)
        if overflow >= 3:
            # 先将所有的业务开发文档进行拼接成一个大的document数组
            test_all_docs = documentTools.generate_design_testdocs_docs(pid)
            # 对文档进行切分
            all_docs = testdoc_text_splitter_for_unit.split_documents(test_all_docs)
            # 用map-reduce链进行分析
            result = BasicChain.invoke_map_reduce_chain_get_str(
                prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_PART_PROMPT_STR,
                prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_TOTAL_PROMPT_STR,
                all_docs,
                summarize_llm,
                5
            )
        else:
            test_str = documentTools.generate_design_testdocs_str(pid)
            result = BasicChain.invoke_stuff_chain_get_str_with_str(
                prompt.UNIT_TEST_FIND_UNIT_INFO_STUFF_PROMPT_STR,
                test_str,
                summarize_llm
            )
        testProjectDao.add_project_info(pid, InfoType.PROJECT_UNITS_SUMMARY.value, result)
        json_chain = BasicChain.json_chain(UnitTestMenu, llm)
        query = prompt.UNIT_TEST_FIND_UNIT_INFO_JSON_STR + result
        return {"text_info": result, "list_info": json_chain.invoke({"query": query})}
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def summarize_unit_info_again(pid: str, llm_name: str):
    try:
        overflow = testProjectDao.get_project_type(pid).overflow
        summarize_llm = choose_llm_by_name(llm_name)
        if overflow >= 3:
            # 先将所有的业务开发文档进行拼接成一个大的document数组
            test_all_docs = documentTools.generate_design_testdocs_docs(pid)
            # 对文档进行切分
            all_docs = testdoc_text_splitter_for_unit.split_documents(test_all_docs)
            # 用map-reduce链进行分析
            result = BasicChain.invoke_map_reduce_chain_get_str(
                prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_PART_PROMPT_STR,
                prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_TOTAL_PROMPT_STR,
                all_docs,
                summarize_llm,
                5
            )
        else:
            test_str = documentTools.generate_design_testdocs_str(pid)
            result = BasicChain.invoke_stuff_chain_get_str_with_str(
                prompt.UNIT_TEST_FIND_UNIT_INFO_STUFF_PROMPT_STR,
                test_str,
                summarize_llm
            )
        testProjectDao.update_project_info(pid, InfoType.PROJECT_UNITS_SUMMARY.value, result)
        json_chain = BasicChain.json_chain(UnitTestMenu, llm)
        query = prompt.UNIT_TEST_FIND_UNIT_INFO_JSON_STR + result
        return {"text_info": result, "list_info": json_chain.invoke({"query": query})}
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_out_test_unit_info(pid: str, unit_name: str, llm_name: str):
    try:
        analyze_llm = choose_llm_by_name(llm_name)
        design_docs = documentTools.generate_design_testdocs_docs(pid)
        design_retriever.add_documents(design_docs)
        unit_docs = design_retriever.invoke(unit_name)
        unit_docs_str = documentTools.docs_to_string(unit_docs)
        tokens = documentTools.num_tokens_from_string(unit_docs_str)
        if tokens > 14500:
            map_str = UNIT_TEST_UNIT_INFO_MAP_TEMPLATE.format(unit=unit_name)
            reduce_str = UNIT_TEST_UNIT_INFO_REDUCE_TEMPLATE.format(unit=unit_name)
            unit_info = BasicChain.invoke_map_reduce_chain_get_str(
                map_str,
                reduce_str,
                unit_docs,
                analyze_llm,
                5
            )
        else:
            stuff_chain = BasicChain.stuff_chain(UNIT_TEST_UNIT_INFO_STUFF_TEMPLATE, analyze_llm)
            unit_info = stuff_chain.invoke({"unit": unit_name, "docs": unit_docs_str})
        test_type_chain = BasicChain.json_chain(UnitTestMethod, llm)
        query = UNIT_TEST_TYPE_JSON_TEMPLATE.format(unit=unit_name, content=unit_info)
        type_json = test_type_chain.invoke({"query": query})
        return {"unit_info": unit_info, "test_type": type_json}
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_unit_test_knowledge(pid: str, method_type: int):
    try:
        # 如果此前分析过了就取历史数据
        history_unit_test_knowledge = testProjectDao.get_project_info(pid, InfoType.PROJECT_UNIT_TEST_KNOWLEDGE.value)
        history_static_blackbox_knowledge = testProjectDao.get_project_info(pid,
                                                                            InfoType.PROJECT_STATIC_BLACKBOX_KNOWLEDGE.value)
        history_static_whitebox_knowledge = testProjectDao.get_project_info(pid,
                                                                            InfoType.PROJECT_STATIC_WHITEBOX_KNOWLEDGE.value)
        # 1表示黑盒测试 2表示白盒测试
        if method_type == 1:
            if history_unit_test_knowledge and history_static_blackbox_knowledge:
                unit_test_knowledge = history_unit_test_knowledge
                unit_method_knowledge = history_static_blackbox_knowledge
            else:
                knowledge_docs = documentTools.generate_knowledge_docs(pid)
                knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
                if history_unit_test_knowledge:
                    unit_test_knowledge = history_unit_test_knowledge
                else:
                    unit_test_knowledge = knowledge_chain.invoke({"input": prompt.UNIT_TEST_KNOWLEDGE_STR})["answer"]
                    testProjectDao.add_project_info(pid, InfoType.PROJECT_UNIT_TEST_KNOWLEDGE.value,
                                                    unit_test_knowledge)
                if history_static_blackbox_knowledge:
                    unit_method_knowledge = history_static_blackbox_knowledge
                else:
                    unit_method_knowledge = knowledge_chain.invoke({"input": prompt.UNIT_TEST_KNOWLEDGE_TEMPLATE_BLACKBOX_STR})["answer"]
                    testProjectDao.add_project_info(pid, InfoType.PROJECT_STATIC_BLACKBOX_KNOWLEDGE.value,
                                                    unit_method_knowledge)
        else:
            if history_unit_test_knowledge and history_static_whitebox_knowledge:
                unit_test_knowledge = history_unit_test_knowledge
                unit_method_knowledge = history_static_whitebox_knowledge
            else:
                knowledge_docs = documentTools.generate_knowledge_docs(pid)
                knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
                if history_unit_test_knowledge:
                    unit_test_knowledge = history_unit_test_knowledge
                else:
                    unit_test_knowledge = knowledge_chain.invoke({"input": prompt.UNIT_TEST_KNOWLEDGE_STR})["answer"]
                    testProjectDao.add_project_info(pid, InfoType.PROJECT_UNIT_TEST_KNOWLEDGE.value,
                                                    unit_test_knowledge)
                if history_static_whitebox_knowledge:
                    unit_method_knowledge = history_static_whitebox_knowledge
                else:
                    unit_method_knowledge = knowledge_chain.invoke({"input": prompt.UNIT_TEST_KNOWLEDGE_TEMPLATE_WHITEBOX_STR})["answer"]
                    testProjectDao.add_project_info(pid, InfoType.PROJECT_STATIC_WHITEBOX_KNOWLEDGE.value,
                                                    unit_method_knowledge)
        return {"unit_test_knowledge": unit_test_knowledge, "unit_method_knowledge": unit_method_knowledge}
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_test_cases(unit_test_knowledge: str, static_method: str, unit_test_method_knowledge: str,
                        unit: str, unit_info: str, output_type: int, llm_name: str):
    try:
        if output_type == 0:
            output_template = prompt.UNIT_TEST_CASE_TXT_TEMPLATE
        elif output_type == 1:
            output_template = prompt.UNIT_TEST_CASE_MD_TEMPLATE
        elif output_type == 2:
            output_template = prompt.UNIT_TEST_CASE_XML_TEMPLATE
        else:
            output_template = prompt.UNIT_TEST_CASE_CSV_TEMPLATE
        llm_test = choose_llm_by_name(llm_name)
        test_case_chain = BasicChain.stuff_chain(UNIT_TEST_GENERATE_TEST_CASE_TEMPLATE_2, llm_test)
        return test_case_chain.invoke({"unit_test_knowledge": unit_test_knowledge, "static_method": static_method,
                                       "unit_test_method_knowledge": unit_test_method_knowledge, "unit": unit,
                                       "case_template": output_template, "unit_info": unit_info})
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
