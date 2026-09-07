"""Transport-neutral retrieval evidence contracts and trusted-scope protocol."""

from __future__ import annotations

import math
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class TrustedProjectScopeLike(Protocol):
    """The minimum trusted scope shape required by retrieval.

    Agent owns the concrete authenticated scope model.  Retrieval only needs
    these three immutable values and must not import the Agent contract layer.
    """

    project_id: str
    actor_id: str
    scope_version: str


class _RetrievalContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
    )


class RetrievalCitation(_RetrievalContractModel):
    citation_id: StrictStr = Field(pattern=r"^C[1-9][0-9]*$")
    corpus: Literal["design", "requirements", "knowledge"]
    source_label: StrictStr = Field(min_length=1, max_length=128)
    page: int = Field(ge=1)
    rank: int = Field(ge=1)
    score: float
    score_kind: Literal["dense", "rrf", "term_coverage"]
    chunk_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("score")
    @classmethod
    def _finite_score(cls, value: float) -> float:
        """处理有限数值分数，并保持 `RetrievalCitation` 的现有状态约束。

        参数:
            `value`：待处理的值。

        返回:
            `float`，内容保持现有调用方契约。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""
        if not math.isfinite(value):
            raise ValueError("retrieval score must be finite")
        return round(value, 6)


class RetrievalQueryEvidence(_RetrievalContractModel):
    strategy: Literal["dense_v1", "hybrid_rrf_v1", "hybrid_rerank_v1"]
    policy_version: Literal["iteration4-aspect5-v1"] = "iteration4-aspect5-v1"
    corpus: Literal["design", "requirements", "knowledge"]
    source_revision: StrictStr = Field(min_length=1, max_length=128)
    query_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    index_status: Literal["build", "reuse"]
    context_tokens: int = Field(ge=0, le=6_000)
    citations: tuple[RetrievalCitation, ...] = ()


class ToolRetrievalEvidence(_RetrievalContractModel):
    policy_version: Literal["iteration4-aspect5-v1"] = "iteration4-aspect5-v1"
    strategy: Literal["dense_v1", "hybrid_rrf_v1", "hybrid_rerank_v1"]
    queries: tuple[RetrievalQueryEvidence, ...] = Field(min_length=1)
    context_tokens: int = Field(ge=0)
    index_builds: int = Field(ge=0)
    index_reuses: int = Field(ge=0)
