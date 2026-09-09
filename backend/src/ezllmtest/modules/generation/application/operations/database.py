# 实现数据库相关生成操作，复用统一模型和知识接口；有效结果保存遵循上层工作流边界。
from ezllmtest.modules.generation.application.chains.basic import BasicChain
from ezllmtest.modules.generation.application.chains.knowledge import knowledge_retrieval_chain
import ezllmtest.modules.projects.public as testProjectDao
from ezllmtest.platform.ai.gateway import LLMError
from ezllmtest.platform.ai.legacy_models import ChatGLMModel, ChatGPTModel
from ezllmtest.modules.generation.domain.prompts.templates import DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE
import ezllmtest.modules.projects.public as documentTools
from ezllmtest.modules.projects.public import InfoType
import ezllmtest.modules.generation.domain.prompts.text as prompt
from ezllmtest.modules.knowledge.public import testdoc_text_splitter_for_db
from ezllmtest.modules.generation.application.operations.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_database_info(pid: str):
    """优先读取数据库摘要，缺失时按完整设计文档分析并登记结果。"""
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_DB_SUMMARY.value)
        if history_result:
            db_info = history_result
        else:
            db_info = invoke_exhaustive_document_analysis(
                operation="db_info",
                pid=pid,
                document_loader=documentTools.generate_design_testdocs_docs,
                splitter=testdoc_text_splitter_for_db,
                stuff_prompt=prompt.DATABASE_TEST_SUMMARY_PROMPT_STR,
                map_prompt=prompt.DATABASE_TEST_SUMMARY_MAP_PROMPT_STR,
                reduce_prompt=prompt.DATABASE_TEST_SUMMARY_REDUCE_PROMPT_STR,
                llm=llm_cn,
                max_concurrency=4,
            )
            testProjectDao.add_project_info(pid, InfoType.PROJECT_DB_SUMMARY.value, db_info)
        return db_info
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def find_db_test_knowledge(pid: str):
    """读取项目数据库测试知识，缺失时检索知识文档并保存复用记录。"""
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_DB_TEST_KNOWLEDGE.value)
        if history_result:
            return history_result
        else:
            knowledge_docs = documentTools.generate_knowledge_docs(pid)
            knowledge_chain = knowledge_retrieval_chain(knowledge_docs)
            db_test_knowledge = knowledge_chain.invoke({"input": prompt.DATABASE_TEST_KNOWLEDGE_STR})["answer"]
            testProjectDao.add_project_info(pid, InfoType.PROJECT_DB_TEST_KNOWLEDGE.value,
                                            db_test_knowledge)
            return db_test_knowledge
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_db_test_cases(db_test_knowledge: str, info: str):
    """用数据库测试知识及设计信息调用既有用例模板，保留模型异常与普通失败的区分。"""
    try:
        test_case_chain = BasicChain.stuff_chain(DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke({"db_test_knowledge": db_test_knowledge, "content": info})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_db_test_cases(pid: str, info: str):
    """组合数据库知识与用例正文返回给接口，不在此改变有效产物管理规则。"""
    try:
        db_test_knowledge = find_db_test_knowledge(pid)
        test_cases = get_db_test_cases(db_test_knowledge, info)
        return {"db_test_knowledge": db_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
