# 协调项目文档登记与查询，文件属于原项目数据边界。
from ezllmtest.platform.ai.tokens import num_tokens_from_string
import string

import tiktoken
import ezllmtest.modules.projects.ports.repository as testProjectDao
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate, format_document
from ezllmtest.modules.knowledge.public import load_document

document_prompt = PromptTemplate.from_template("{page_content}")


# 定义一个工具类，将Document类连接成为字符串
def docs_to_string(docs: [Document]):
    """按统一文档格式拼接内容；有引用 ID 时保留引用前缀供生成结果关联来源。"""
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
    """按文档顺序附加编号与可用引用 ID，保留来源提示后拼接正文。"""
    result = ""
    for index, doc in enumerate(docs):
        citation = doc.metadata.get("_ezllm_citation_id")
        label = f"[{citation}] " if citation else ""
        result += label + "第" + str(index + 1) + "个文档内容如下:\n" + doc.page_content + "\n"
    return result


# 查询所有业务文档并拼接成一个大的字符串
def generate_all_testdocs_str(pid: string):
    """依次加载当前项目登记的需求和设计资料并拼成带组别的文本，失败保持历史返回。"""
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
    """仅加载当前项目需求资料并按顺序拼接，文件路径来自项目登记。"""
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
    """仅加载当前项目设计资料并按顺序拼接，不把知识文档混入设计输入。"""
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
    """汇集项目需求与设计 Document 对象，供完整语料分析使用。"""
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
    """按项目登记加载需求 Document 集合，加载失败不伪造空的成功结果。"""
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
    """按项目登记加载设计 Document 集合，保留文档元数据。"""
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
    """加载当前项目知识文档集合，检索层据此建立项目内索引。"""
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
