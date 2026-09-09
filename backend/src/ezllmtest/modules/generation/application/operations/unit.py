# 实现单元相关生成操作，复用统一模型和知识接口；有效结果保存遵循上层工作流边界。
# 提供llm对业务文档单元测试智能分析的相关服务
import ezllmtest.modules.generation.domain.prompts.text as prompt
from ezllmtest.platform.ai.legacy_models import ChatGPTModel
from ezllmtest.modules.generation.application.chains.basic import BasicChain
from ezllmtest.modules.generation.application.chains.knowledge import knowledge_retrieval_chain
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.platform.ai.gateway import LLMError
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
from ezllmtest.platform.ai.selection import choose_llm_by_name
from ezllmtest.modules.knowledge.public import testdoc_text_splitter_for_unit
from ezllmtest.modules.generation.schemas.analysis import QualifiedUnitTestMenu, UnitTestMethod
from ezllmtest.modules.knowledge.public import design_retriever
from ezllmtest.modules.generation.domain.prompts.templates import UNIT_TEST_UNIT_INFO_MAP_TEMPLATE, UNIT_TEST_UNIT_INFO_REDUCE_TEMPLATE, UNIT_TEST_UNIT_INFO_STUFF_TEMPLATE, UNIT_TEST_TYPE_JSON_TEMPLATE, UNIT_TEST_GENERATE_TEST_CASE_TEMPLATE_2
from ezllmtest.modules.generation.application.operations.long_text import invoke_exhaustive_document_analysis
from ezllmtest.modules.generation.domain.unit_reference import encode_unit_menu

llm = ChatGPTModel().get_model()

# llm_test = ChatGPTModel().get_model()
# llm_test = WenXinModel().get_model()
# llm_test = TongYiModel().get_model()
# llm_test = ChatGLMModel().get_model()
# llm_test = MoonShotModel().get_model()


def summarize_unit_info(pid: str, llm_name: str):
    """复用或生成单元摘要后构造限定单元菜单；缓存命中也可能调用结构化模型链。"""
    try:
        # 如果此前分析过了就取历史数据
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_UNITS_SUMMARY.value)
        if history_result:
            json_chain = BasicChain.json_chain(QualifiedUnitTestMenu, llm)
            query = prompt.UNIT_TEST_FIND_UNIT_INFO_JSON_STR + history_result
            return {
                "text_info": history_result,
                "list_info": encode_unit_menu(
                    json_chain.invoke({"query": query})
                ).model_dump(),
            }
        summarize_llm = choose_llm_by_name(llm_name)
        result = invoke_exhaustive_document_analysis(
            operation="unit_menu",
            pid=pid,
            document_loader=documentTools.generate_design_testdocs_docs,
            splitter=testdoc_text_splitter_for_unit,
            stuff_prompt=prompt.UNIT_TEST_FIND_UNIT_INFO_STUFF_PROMPT_STR,
            map_prompt=prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_PART_PROMPT_STR,
            reduce_prompt=prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_TOTAL_PROMPT_STR,
            llm=summarize_llm,
            max_concurrency=5,
        )
        testProjectDao.add_project_info(pid, InfoType.PROJECT_UNITS_SUMMARY.value, result)
        json_chain = BasicChain.json_chain(QualifiedUnitTestMenu, llm)
        query = prompt.UNIT_TEST_FIND_UNIT_INFO_JSON_STR + result
        return {
            "text_info": result,
            "list_info": encode_unit_menu(
                json_chain.invoke({"query": query})
            ).model_dump(),
        }
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def summarize_unit_info_again(pid: str, llm_name: str):
    """使用指定模型重新生成单元摘要并更新记录，再形成限定引用菜单。"""
    try:
        summarize_llm = choose_llm_by_name(llm_name)
        result = invoke_exhaustive_document_analysis(
            operation="unit_menu",
            pid=pid,
            document_loader=documentTools.generate_design_testdocs_docs,
            splitter=testdoc_text_splitter_for_unit,
            stuff_prompt=prompt.UNIT_TEST_FIND_UNIT_INFO_STUFF_PROMPT_STR,
            map_prompt=prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_PART_PROMPT_STR,
            reduce_prompt=prompt.UNIT_TEST_FIND_UNIT_INFO_MAP_REDUCE_TOTAL_PROMPT_STR,
            llm=summarize_llm,
            max_concurrency=5,
        )
        testProjectDao.update_project_info(pid, InfoType.PROJECT_UNITS_SUMMARY.value, result)
        json_chain = BasicChain.json_chain(QualifiedUnitTestMenu, llm)
        query = prompt.UNIT_TEST_FIND_UNIT_INFO_JSON_STR + result
        return {
            "text_info": result,
            "list_info": encode_unit_menu(
                json_chain.invoke({"query": query})
            ).model_dump(),
        }
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_out_test_unit_info(pid: str, unit_name: str, llm_name: str):
    """按单元名称检索设计上下文，生成单元分析及测试方法类型。"""
    try:
        analyze_llm = choose_llm_by_name(llm_name)
        design_docs = documentTools.generate_design_testdocs_docs(pid)
        unit_docs = design_retriever(design_docs).invoke(unit_name)
        unit_docs_str = documentTools.docs_to_string(unit_docs)
        stuff_chain = BasicChain.stuff_chain(UNIT_TEST_UNIT_INFO_STUFF_TEMPLATE, analyze_llm)
        unit_info = stuff_chain.invoke({"unit": unit_name, "docs": unit_docs_str})
        test_type_chain = BasicChain.json_chain(UnitTestMethod, llm)
        query = UNIT_TEST_TYPE_JSON_TEMPLATE.format(unit=unit_name, content=unit_info)
        type_json = test_type_chain.invoke({"query": query})
        return {"unit_info": unit_info, "test_type": type_json}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_unit_test_knowledge(pid: str, method_type: int):
    """按所选单元方法取得知识依据，供对应单元用例生成使用。"""
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
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_test_cases(unit_test_knowledge: str, static_method: str, unit_test_method_knowledge: str,
                        unit: str, unit_info: str, output_type: int, llm_name: str):
    """结合具名单元、测试方法和知识形成单元用例，限定名继续区分同名目标。"""
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
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
