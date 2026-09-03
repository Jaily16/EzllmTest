from langchain_core.documents import Document

from service import legacyLongTextService as legacy


def test_legacy_exhaustive_analysis_stuffs_small_corpus(monkeypatch):
    calls = []
    monkeypatch.setattr(
        legacy.BasicChain,
        "invoke_stuff_chain_get_str_with_str",
        lambda prompt, text, llm: calls.append(("stuff", prompt, text, llm))
        or "small-result",
    )
    monkeypatch.setattr(
        legacy.BasicChain,
        "invoke_map_reduce_chain_get_str",
        lambda *_args: calls.append(("map",)) or "map-result",
    )
    monkeypatch.setattr(
        legacy.documentTools,
        "num_tokens_from_string",
        lambda _text: 100,
    )

    result = legacy.invoke_exhaustive_document_analysis(
        operation="unit_menu",
        pid="p",
        document_loader=lambda _pid: [Document(page_content="design")],
        splitter=type("Splitter", (), {"split_documents": lambda self, docs: docs})(),
        stuff_prompt="stuff-prompt",
        map_prompt="map-prompt",
        reduce_prompt="reduce-prompt",
        llm=object(),
        max_concurrency=4,
    )

    assert result == "small-result"
    assert [item[0] for item in calls] == ["stuff"]


def test_legacy_exhaustive_analysis_maps_large_corpus(monkeypatch):
    calls = []
    monkeypatch.setattr(
        legacy.BasicChain,
        "invoke_stuff_chain_get_str_with_str",
        lambda *_args: calls.append(("stuff",)) or "small-result",
    )
    monkeypatch.setattr(
        legacy.BasicChain,
        "invoke_map_reduce_chain_get_str",
        lambda *args: calls.append(("map", args[2])) or "large-result",
    )
    monkeypatch.setattr(
        legacy.documentTools,
        "num_tokens_from_string",
        lambda _text: 32_001,
    )

    result = legacy.invoke_exhaustive_document_analysis(
        operation="api_info",
        pid="p",
        document_loader=lambda _pid: [Document(page_content="design")],
        splitter=type("Splitter", (), {"split_documents": lambda self, docs: docs})(),
        stuff_prompt="stuff-prompt",
        map_prompt="map-prompt",
        reduce_prompt="reduce-prompt",
        llm=object(),
        max_concurrency=4,
    )

    assert result == "large-result"
    assert [item[0] for item in calls] == ["map"]
