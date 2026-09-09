# 实现长文本相关生成操作，复用统一模型和知识接口；有效结果保存遵循上层工作流边界。
"""Compatibility adapter that applies current long-text policy to legacy REST calls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ezllmtest.modules.generation.application.chains.basic import BasicChain
from ezllmtest.modules.generation.domain.long_text import LongTextStrategy, SourceMode, strategy_for
import ezllmtest.modules.projects.public as documentTools


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
    """让既有同步 REST 分析复用当前长文本政策，超长资料按完整抽取策略处理。"""
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
