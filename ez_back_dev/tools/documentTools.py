import string
import tiktoken
from langchain_core.documents import Document
from langchain_core.prompts import format_document, PromptTemplate
from dao import testProjectDao
from vectorstore.loader import load_document

document_prompt = PromptTemplate.from_template("{page_content}")


# 定义一个工具类，将Document类连接成为字符串
def docs_to_string(docs: [Document]):
    return "".join(
        (
            f"[{doc.metadata['_ezllm_citation_id']}] "
            if doc.metadata.get("_ezllm_citation_id")
            else ""
        )
        + format_document(doc, document_prompt)
        for doc in docs
    )


def docs_to_meaningful_strings(docs: [Document]):
    result = ""
    for index, doc in enumerate(docs):
        citation = doc.metadata.get("_ezllm_citation_id")
        label = f"[{citation}] " if citation else ""
        result += label + "第" + str(index + 1) + "个文档内容如下:\n" + doc.page_content + "\n"
    return result


# 查询所有业务文档并拼接成一个大的字符串
def generate_all_testdocs_str(pid: string):
    try:
        test_paths = testProjectDao.find_project_requirement_testdoc_list(pid)
        result = ""
        for index, test_path in enumerate(test_paths):
            docs = load_document(test_path.path)
            doc_str = docs_to_string(docs)
            result += "需求文档" + str(index + 1) + ":\n" + doc_str + "\n\n"
        test_paths = testProjectDao.find_project_design_testdoc_list(pid)
        for index, test_path in enumerate(test_paths):
            docs = load_document(test_path.path)
            doc_str = docs_to_string(docs)
            result += "开发文档" + str(index + 1) + ":\n" + doc_str + "\n\n"
        return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查询所有业务需求文档并拼接成一个大的字符串
def generate_require_testdocs_str(pid: string):
    try:
        test_paths = testProjectDao.find_project_requirement_testdoc_list(pid)
        result = ""
        for index, test_path in enumerate(test_paths):
            docs = load_document(test_path.path)
            doc_str = docs_to_string(docs)
            result += "文档" + str(index + 1) + ":\n" + doc_str + "\n\n"
        return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查询所有业务设计文档并拼接成一个大的字符串
def generate_design_testdocs_str(pid: string):
    try:
        test_paths = testProjectDao.find_project_design_testdoc_list(pid)
        result = ""
        for index, test_path in enumerate(test_paths):
            docs = load_document(test_path.path)
            doc_str = docs_to_string(docs)
            result += "文档" + str(index + 1) + ":\n" + doc_str + "\n\n"
        return result
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查询所有业务文档并拼接成一个大Document数组
def generate_all_testdocs_docs(pid: string):
    try:
        require_test_paths = testProjectDao.find_project_requirement_testdoc_list(pid)
        design_test_paths = testProjectDao.find_project_design_testdoc_list(pid)
        test_all_docs = []
        for test_path in require_test_paths:
            doc = load_document(test_path.path)
            test_all_docs += doc
        for test_path in design_test_paths:
            doc = load_document(test_path.path)
            test_all_docs += doc
        return test_all_docs
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查询需求文档并拼接成一个大Document数组
def generate_require_testdocs_docs(pid: string):
    try:
        test_paths = testProjectDao.find_project_requirement_testdoc_list(pid)
        test_all_docs = []
        for test_path in test_paths:
            doc = load_document(test_path.path)
            test_all_docs += doc
        return test_all_docs
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查询开发文档并拼接成一个大Document数组
def generate_design_testdocs_docs(pid: string):
    try:
        test_paths = testProjectDao.find_project_design_testdoc_list(pid)
        test_all_docs = []
        for test_path in test_paths:
            doc = load_document(test_path.path)
            test_all_docs += doc
        return test_all_docs
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 查询所有知识库并且拼接成一个大Document数组
def generate_knowledge_docs(pid: string):
    try:
        knowledge_paths = testProjectDao.find_project_knowledge_list(pid)
        knowledge_all_docs = []
        for path in knowledge_paths:
            doc = load_document(path.path)
            knowledge_all_docs += doc
        return knowledge_all_docs
    except Exception as e:
        print("encountered exception {}".format(e))
        return False


# 计算并返回一个字符串的token值
def num_tokens_from_string(text_str: str) -> int:
    # 获取指定编码的编码器
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    # encoding = tiktoken.get_encoding(encoding_name)
    # 将文本字符串编码为指定编码，并计算编码后的标记数量
    num_tokens = len(encoding.encode(text_str))
    # 返回标记数量
    return num_tokens
