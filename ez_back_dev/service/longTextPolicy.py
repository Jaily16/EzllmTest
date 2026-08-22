"""Model-compatible routing rules for every streamed LLM workflow.

The catalog describes semantics, not provider marketing limits.  Exhaustive
corpus analysis may stuff a bounded source into one request and falls back to
hierarchical map-reduce above that bound.  Focused questions retrieve a small
context before one model call, while case generation consumes compact saved
artifacts.  Refine is intentionally not assigned: the current workflows merge
independent evidence rather than revising one order-dependent narrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from llm.provider import get_model_spec
from service.workflowBudget import BudgetStage, profile_for


SourceMode = Literal["exhaustive", "focused", "artifact"]


class LongTextStrategy(StrEnum):
    STUFF = "stuff"
    MAP_REDUCE = "map_reduce"
    RETRIEVAL_STUFF = "retrieval_stuff"
    ARTIFACT_STUFF = "artifact_stuff"


@dataclass(frozen=True)
class LongTextPolicy:
    operation: str
    source_mode: SourceMode
    stuff_limit_tokens: int
    overflow_strategy: LongTextStrategy
    supports_exhaustive_substage: bool = False

    def __post_init__(self) -> None:
        if self.stuff_limit_tokens <= 0:
            raise ValueError("stuff_limit_tokens must be positive")
        if self.source_mode == "focused" and (
            self.overflow_strategy is not LongTextStrategy.RETRIEVAL_STUFF
        ):
            raise ValueError("focused workflows must use retrieval_stuff")
        if self.source_mode == "artifact" and (
            self.overflow_strategy is not LongTextStrategy.ARTIFACT_STUFF
        ):
            raise ValueError("artifact workflows must use artifact_stuff")


def _exhaustive(operation: str, limit: int) -> LongTextPolicy:
    return LongTextPolicy(
        operation=operation,
        source_mode="exhaustive",
        stuff_limit_tokens=limit,
        overflow_strategy=LongTextStrategy.MAP_REDUCE,
    )


def _focused(
    operation: str, *, supports_exhaustive_substage: bool = False
) -> LongTextPolicy:
    return LongTextPolicy(
        operation=operation,
        source_mode="focused",
        stuff_limit_tokens=32_000,
        overflow_strategy=LongTextStrategy.RETRIEVAL_STUFF,
        supports_exhaustive_substage=supports_exhaustive_substage,
    )


def _artifact(
    operation: str, *, supports_exhaustive_substage: bool = False
) -> LongTextPolicy:
    return LongTextPolicy(
        operation=operation,
        source_mode="artifact",
        stuff_limit_tokens=16_000,
        overflow_strategy=LongTextStrategy.ARTIFACT_STUFF,
        supports_exhaustive_substage=supports_exhaustive_substage,
    )


LONG_TEXT_POLICIES: dict[str, LongTextPolicy] = {
    policy.operation: policy
    for policy in (
        _exhaustive("project_analysis", 64_000),
        _exhaustive("unit_menu", 32_000),
        _focused("unit_info"),
        _artifact("unit_case"),
        _artifact("integration_menu", supports_exhaustive_substage=True),
        _focused("integration_info", supports_exhaustive_substage=True),
        _artifact("integration_case"),
        _exhaustive("api_info", 32_000),
        _artifact("api_case"),
        _exhaustive("ui_info", 32_000),
        _artifact("ui_case"),
        _exhaustive("db_info", 32_000),
        _artifact("db_case"),
        _exhaustive("functional_info", 32_000),
        _artifact("functional_case"),
        _focused("nonfunctional_info"),
        _artifact("nonfunctional_case"),
        _exhaustive("acceptance_info", 32_000),
        _artifact("acceptance_case"),
    )
}


def get_long_text_policy(operation: str) -> LongTextPolicy:
    try:
        return LONG_TEXT_POLICIES[operation]
    except KeyError as exc:
        raise KeyError(f"unknown_operation:{operation}") from exc


def strategy_for(
    operation: str,
    source_tokens: int,
    *,
    source_mode: SourceMode | None = None,
) -> LongTextStrategy:
    if source_tokens < 0:
        raise ValueError("source_tokens cannot be negative")
    policy = get_long_text_policy(operation)
    mode = source_mode or policy.source_mode
    if mode != policy.source_mode and not policy.supports_exhaustive_substage:
        raise ValueError(f"{operation} does not support a {mode} substage")
    if mode == "focused":
        return LongTextStrategy.RETRIEVAL_STUFF
    if mode == "artifact":
        return LongTextStrategy.ARTIFACT_STUFF
    return (
        LongTextStrategy.STUFF
        if source_tokens <= policy.stuff_limit_tokens
        else LongTextStrategy.MAP_REDUCE
    )


def effective_context_budget(
    operation: str,
    stage: BudgetStage,
    model_label: str,
) -> int:
    """Return the app budget after provider window/output safety reserves."""

    profile = profile_for(operation, stage)
    spec = get_model_spec(model_label)
    output_reserve = min(profile.output_token_limit, spec.max_output_tokens)
    reasoning_reserve = profile.reasoning_budget or 0
    safety_reserve = max(4_096, spec.context_window_tokens // 10)
    provider_input_capacity = max(
        1,
        spec.context_window_tokens
        - output_reserve
        - reasoning_reserve
        - safety_reserve,
    )
    return min(profile.max_context_tokens, provider_input_capacity)
