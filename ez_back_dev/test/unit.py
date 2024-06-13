from prompt.templates import INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE
from tools import documentTools
from vectorstore.retrievers import design_retriever
from prompt import templates
from chain.KnowledgeChain import knowledge_retrieval_chain


def test_retriever():
    pid = "Ez1790304752236494848"
    test_all_docs = documentTools.generate_design_testdocs_docs(pid)
    design_retriever.add_documents(test_all_docs)
    print(documentTools.docs_to_meaningful_strings(design_retriever.get_relevant_documents("用户发布博客")))


def test_template():
    str1 = templates.UNIT_TEST_KNOWLEDGE_TEMPLATE.format_prompt()
    print(str1)


def test_find_knowledge():
    pid = "Ez1790304752236494848"
    docs = documentTools.generate_knowledge_docs(pid)
    chain = knowledge_retrieval_chain(docs)
    print(chain.invoke({"input": "请问什么是单元测试"})["answer"])


def test2():
    str = INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE.format(
        strategy="大爆炸集成(Big Bang Integration)")
    print(type(str))
