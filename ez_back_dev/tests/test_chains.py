import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from chain.BasicChain import BasicChain
from chain.KnowledgeChain import knowledge_retrieval_chain
from llm.provider import LLMOutputParsingError
from model.ChainJsonModel import ApiList


def test_basic_json_chain_returns_plain_dict():
    llm = RunnableLambda(lambda _: '{"api_list": ["GET /health"]}')

    result = BasicChain.json_chain(ApiList, llm).invoke({"query": "list APIs"})

    assert result == {"api_list": ["GET /health"]}


def test_basic_json_chain_translates_malformed_output():
    llm = RunnableLambda(lambda _: "not-json")

    with pytest.raises(LLMOutputParsingError, match="structured output"):
        BasicChain.json_chain(ApiList, llm).invoke({"query": "list APIs"})


def test_stuff_chain_keeps_document_content():
    llm = RunnableLambda(lambda prompt: prompt.to_string())

    result = BasicChain.invoke_stuff_chain_get_str(
        "summarize", [Document(page_content="project-only-content")], llm
    )

    assert "project-only-content" in result


def test_knowledge_chain_preserves_answer_context_and_input_keys():
    class FakeRetriever:
        def invoke(self, query):
            assert query == "what is scoped?"
            return [Document(page_content="only this project")]

    llm = RunnableLambda(lambda prompt: prompt.to_string())
    chain = knowledge_retrieval_chain([], llm=llm, retriever=FakeRetriever())

    result = chain.invoke({"input": "what is scoped?"})

    assert result["input"] == "what is scoped?"
    assert result["context"][0].page_content == "only this project"
    assert "only this project" in result["answer"]
