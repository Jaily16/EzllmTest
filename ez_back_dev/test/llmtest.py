from llm.llm_chatGPT import ChatGPTModel
from vectorstore.loader import load_document
from dao.testProjectDao import find_project_testdoc_list
from langchain_community.document_loaders import UnstructuredMarkdownLoader, PyPDFLoader
from tools import documentTools


def test_connect():
    model = ChatGPTModel()
    llm = model.get_model()
    print(llm.invoke("请问你是谁"))


def test_loader():
    pid = "Ez1789257412218191872"
    testdocs = find_project_testdoc_list(pid)
    for testdoc in testdocs:
        doc = load_document("../" + testdoc.path)
        print(doc)


def test_markdown():
    path = "../static/projects/Ez1789195814036307968/knowledge/硕士复试通知书.pdf"
    loader = PyPDFLoader(path)
    print(loader.load())


def test_generate_big_str():
    pid = "Ez1789538136368349184"
    test_paths = find_project_testdoc_list(pid)
    result = ""
    for index, test_path in enumerate(test_paths):
        docs = load_document("../" + test_path.path)
        doc_str = documentTools.docs_to_string(docs)
        result += "文档" + str(index + 1) + ":\n" + doc_str + "\n\n"
    print(result)
