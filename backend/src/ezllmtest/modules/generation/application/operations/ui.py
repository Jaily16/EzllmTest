# 实现界面相关生成操作，复用统一模型和知识接口；有效结果保存遵循上层工作流边界。
from ezllmtest.modules.generation.application.chains.basic import BasicChain
from ezllmtest.modules.generation.application.chains.knowledge import knowledge_retrieval_chain
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.platform.ai.gateway import LLMError
from ezllmtest.platform.ai.legacy_models import ChatGLMModel, ChatGPTModel
from ezllmtest.modules.generation.domain.prompts.templates import UI_TEST_GENERATE_TEST_CASE_TEMPLATE
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
import ezllmtest.modules.generation.domain.prompts.text as prompt
from ezllmtest.modules.knowledge.public import testdoc_text_splitter_for_unit, testdoc_text_splitter_for_ui
from ezllmtest.modules.generation.application.operations.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_ui_info(pid: str):
    """优先复用 UI 摘要，缺失时完整分析设计资料并登记。"""
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_UI_SUMMARY.value)
        if history_result:
            ui_info = history_result
        else:
            ui_info = invoke_exhaustive_document_analysis(
                operation="ui_info",
                pid=pid,
                document_loader=documentTools.generate_design_testdocs_docs,
                splitter=testdoc_text_splitter_for_ui,
                stuff_prompt=prompt.UI_TEST_SUMMARY_PROMPT_STR,
                map_prompt=prompt.UI_TEST_SUMMARY_MAP_PROMPT_STR,
                reduce_prompt=prompt.UI_TEST_SUMMARY_REDUCE_PROMPT_STR,
                llm=llm_cn,
                max_concurrency=5,
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_UI_SUMMARY.value, ui_info)
        return ui_info
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_ui_test_knowledge(pid: str):
    """读取项目 UI 测试知识，缺失时检索知识文档并保存复用项。"""
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_UI_TEST_KNOWLEDGE.value)
        if history_result:
            return history_result
        else:
            knowledge_docs = documentTools.generate_knowledge_docs(pid)
            knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
            ui_test_knowledge = knowledge_chain.invoke({"input": prompt.UI_TEST_KNOWLEDGE_STR})["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_UI_TEST_KNOWLEDGE.value,
                                            ui_test_knowledge)
            return ui_test_knowledge
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_ui_test_cases(ui_test_knowledge: str, info: str):
    """将界面信息和测试知识填入既有 UI 用例生成模板。"""
    try:
        test_case_chain = BasicChain.stuff_chain(UI_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke({"ui_test_knowledge": ui_test_knowledge, "content": info})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_ui_test_cases(pid: str, info: str):
    """返回 UI 测试知识与生成正文，保持知识获取和用例生成的调用顺序。"""
    try:
        ui_test_knowledge = find_ui_test_knowledge(pid)
        test_cases = get_ui_test_cases(ui_test_knowledge, info)
        return {"ui_test_knowledge": ui_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
