import os
from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from dao import testProjectDao
from llm.llm_ChatGLM import ChatGLMModel
from llm.llm_chatGPT import ChatGPTModel
from prompt.templates import DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE
from tools import documentTools
from tools.InfoType import InfoType
import prompt.promptStr as prompt
from vectorstore.splitter import testdoc_text_splitter_for_unit

# 利用langsmith监控运行
os.environ["LANGCHAIN_API_KEY"] = "ls__8f1d0a23c4cb4c9d8b58076ba3de84c7"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "LangServe_Service"

llm = ChatGPTModel().get_model()
llm_cn = ChatGLMModel().get_model()


def find_out_database_info(pid: str):
    try:
        history_result = testProjectDao.get_project_info(pid, InfoType.PROJECT_DB_SUMMARY.value)
        overflow = testProjectDao.get_project_type(pid).overflow
        if history_result:
            db_info = history_result
        else:
            if overflow >= 3:
                # 先将所有的业务开发文档进行拼接成一个大的document数组
                test_all_docs = documentTools.generate_design_testdocs_docs(pid)
                # 对文档进行切分
                all_docs = testdoc_text_splitter_for_unit.split_documents(test_all_docs)
                map_str = prompt.DATABASE_TEST_SUMMARY_MAP_PROMPT_STR
                reduce_str = prompt.DATABASE_TEST_SUMMARY_REDUCE_PROMPT_STR
                db_info = BasicChain.invoke_map_reduce_chain_get_str(
                    map_str,
                    reduce_str,
                    all_docs,
                    llm_cn,
                    4
                )
            else:
                test_str = documentTools.generate_design_testdocs_str(pid)
                db_info = BasicChain.invoke_stuff_chain_get_str_with_str(prompt.DATABASE_TEST_SUMMARY_PROMPT_STR,
                                                                         test_str,
                                                                         llm_cn)
            testProjectDao.add_project_info(pid, InfoType.PROJECT_DB_SUMMARY.value, db_info)
        return db_info
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
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def get_db_test_cases(db_test_knowledge: str, info: str):
    try:
        test_case_chain = BasicChain.stuff_chain(DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE, llm)
        return test_case_chain.invoke({"db_test_knowledge": db_test_knowledge, "content": info})
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


def generate_db_test_cases(pid: str, info: str):
    try:
        db_test_knowledge = find_db_test_knowledge(pid)
        test_cases = get_db_test_cases(db_test_knowledge, info)
        return {"db_test_knowledge": db_test_knowledge, "test_cases": test_cases}
    except Exception as e:
        print("encountered exception {}".format(e))
        return False
