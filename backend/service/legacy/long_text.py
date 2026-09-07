"""Compatibility adapter that applies current long-text policy to legacy REST calls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chain.BasicChain import BasicChain
from service.workflow.long_text import LongTextStrategy, SourceMode, strategy_for
from service.project import documents as documentTools


def invoke_exhaustive_document_analysis(
    *,
    operation: str,
    pid: str,
    document_loader: Callable[[str], list[Any]],
    splitter: Any,
    stuff_prompt: str,
    map_prompt: str,
    reduce_prompt: str,
    llm: Any,
    max_concurrency: int,
    source_mode: SourceMode = "exhaustive",
) -> str:
    """调用完整分析文档分析，并遵循现有调用契约。

    参数:
        `operation`：工作流操作名。
        `pid`：项目 ID。
        `document_loader`：沿用签名中 `Callable[[str], list[Any]]` 类型约束的输入。
        `splitter`：沿用签名中 `Any` 类型约束的输入。
        `stuff_prompt`：沿用签名中 `str` 类型约束的输入。
        `map_prompt`：沿用签名中 `str` 类型约束的输入。
        `reduce_prompt`：沿用签名中 `str` 类型约束的输入。
        `llm`：沿用签名中 `Any` 类型约束的输入。
        `max_concurrency`：沿用签名中 `int` 类型约束的输入。
        `source_mode`：沿用签名中 `SourceMode` 类型约束的输入。

    返回:
        `str`，内容保持现有调用方契约。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
    documents = document_loader(pid)
    if not documents:
        raise ValueError("document corpus is empty")
    source_text = documentTools.docs_to_string(documents)
    source_tokens = documentTools.num_tokens_from_string(source_text)
    strategy = strategy_for(
        operation,
        source_tokens,
        source_mode=source_mode,
    )
    if strategy is LongTextStrategy.MAP_REDUCE:
        chunks = splitter.split_documents(documents)
        return BasicChain.invoke_map_reduce_chain_get_str(
            map_prompt,
            reduce_prompt,
            chunks,
            llm,
            max_concurrency,
        )
    return BasicChain.invoke_stuff_chain_get_str_with_str(
        stuff_prompt,
        source_text,
        llm,
    )
