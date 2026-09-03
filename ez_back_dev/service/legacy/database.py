from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from infrastructure.persistence import project_repository as testProjectDao
from infrastructure.llm.gateway import LLMError
from infrastructure.llm.legacy_models import ChatGLMModel, ChatGPTModel
from prompt.templates import DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE
from service.project import documents as documentTools
from tools.InfoType import InfoType
import prompt.promptStr as prompt
from service.retrieval.splitters import testdoc_text_splitter_for_db
from service.legacy.long_text import invoke_exhaustive_document_analysis

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_database_info(pid: str):
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
    try:
        test_case_chain = BasicChain.stuff_chain(DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke({"db_test_knowledge": db_test_knowledge, "content": info})
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_db_test_cases(pid: str, info: str):
    try:
        db_test_knowledge = find_db_test_knowledge(pid)
        test_cases = get_db_test_cases(db_test_knowledge, info)
        return {"db_test_knowledge": db_test_knowledge, "test_cases": test_cases}
    except LLMError:
        raise
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
