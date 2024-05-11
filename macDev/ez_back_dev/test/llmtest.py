from llm.llm_chatGPT import ChatGPTModel
from vectorstore.loader import load_document
from dao.testProjectDao import find_project_testdoc_list
from langchain_community.document_loaders import UnstructuredMarkdownLoader


def test_connect():
    model = ChatGPTModel()
    llm = model.get_model()
    print(llm.invoke("请问你是谁"))


def test_loader():
    pid = "Ez1788931757752451072"
    testdocs = find_project_testdoc_list(pid)
    for testdoc in testdocs:
        doc = load_document("../" + testdoc.path)
        print(doc)


def test_markdown():
    path = "../static/projects/Ez1788916403366002688/testdoc/ProjectFiles.md"
    loader = UnstructuredMarkdownLoader(path)
    print(loader.load())
