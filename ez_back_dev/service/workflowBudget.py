"""Stage-specific workflow budgets without provider-specific request fields."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Literal, Sequence

from service.workflowCatalog import get_workflow_definition
from tools.documentTools import num_tokens_from_string


ReasoningMode = Literal["off", "low", "balanced"]
BudgetStage = Literal["map", "structured", "final"]
TokenCounter = Callable[[str], int]


@dataclass(frozen=True)
class WorkflowBudgetProfile:
    map_output_tokens: int
    structured_output_tokens: int
    final_output_tokens: int
    max_context_tokens: int
    reasoning_mode: ReasoningMode
    reasoning_budget: int | None
    stage: BudgetStage = "final"

    def __post_init__(self) -> None:
        for value in (
            self.map_output_tokens,
            self.structured_output_tokens,
            self.final_output_tokens,
            self.max_context_tokens,
        ):
            if value <= 0:
                raise ValueError("workflow budgets must be positive")
        if self.reasoning_budget is not None and self.reasoning_budget <= 0:
            raise ValueError("reasoning_budget must be positive when set")

    @property
    def output_token_limit(self) -> int:
        return {
            "map": self.map_output_tokens,
            "structured": self.structured_output_tokens,
            "final": self.final_output_tokens,
        }[self.stage]

    def public_metadata(self) -> dict[str, int | str | None]:
        return {
            "stage": self.stage,
            "map_output_tokens": self.map_output_tokens,
            "structured_output_tokens": self.structured_output_tokens,
            "final_output_tokens": self.final_output_tokens,
            "max_context_tokens": self.max_context_tokens,
            "reasoning_mode": self.reasoning_mode,
            "reasoning_budget": self.reasoning_budget,
        }


_PROJECT_PROFILE = WorkflowBudgetProfile(
    map_output_tokens=1_024,
    structured_output_tokens=2_048,
    final_output_tokens=8_192,
    max_context_tokens=64_000,
    reasoning_mode="balanced",
    reasoning_budget=4_096,
)
_ANALYSIS_PROFILE = WorkflowBudgetProfile(
    map_output_tokens=1_024,
    structured_output_tokens=1_536,
    final_output_tokens=8_192,
    max_context_tokens=32_000,
    reasoning_mode="balanced",
    reasoning_budget=4_096,
)
_CASE_PROFILE = WorkflowBudgetProfile(
    map_output_tokens=1_024,
    structured_output_tokens=1_536,
    final_output_tokens=12_288,
    max_context_tokens=16_000,
    reasoning_mode="balanced",
    reasoning_budget=4_096,
)

_OPERATION_PROFILE_OVERRIDES: dict[str, dict[str, int]] = {
    # Qualified unit references are exhaustive and can contain hundreds of
    # independently addressable methods. The generic 1.5K structured cap can
    # truncate otherwise valid JSON before the top-level object is closed.
    "unit_menu": {"structured_output_tokens": 12_288},
}


def profile_for(
    operation: str,
    stage: BudgetStage = "final",
) -> WorkflowBudgetProfile:
    definition = get_workflow_definition(operation)
    base = {
        "project": _PROJECT_PROFILE,
        "analysis": _ANALYSIS_PROFILE,
        "case": _CASE_PROFILE,
    }[definition.phase]
    override = _OPERATION_PROFILE_OVERRIDES.get(operation)
    if override:
        base = replace(base, **override)
    return replace(
        base,
        stage=stage,
        reasoning_mode="balanced" if stage == "final" else "off",
        reasoning_budget=base.reasoning_budget if stage == "final" else None,
    )


def stage_for_model_call(stage: str) -> BudgetStage:
    normalized = stage.lower()
    if "_map_" in normalized or normalized.endswith("_map"):
        return "map"
    if any(
        marker in normalized
        for marker in (
            "structured",
            "method",
            "knowledge_",
            "detail",
            "repair",
            "digest_generate",
            "digest_reduce",
        )
    ):
        return "structured"
    return "final"


def _truncate_to_token_budget(
    text: str,
    max_tokens: int,
    token_counter: TokenCounter,
) -> str:
    if not text or max_tokens <= 0:
        return ""
    if token_counter(text) <= max_tokens:
        return text
    low = 0
    high = len(text)
    while low < high:
        midpoint = (low + high + 1) // 2
        if token_counter(text[:midpoint]) <= max_tokens:
            low = midpoint
        else:
            high = midpoint - 1
    return text[:low].rstrip()


def _truncate_suffix_to_token_budget(
    text: str,
    max_tokens: int,
    token_counter: TokenCounter,
) -> str:
    if not text or max_tokens <= 0:
        return ""
    if token_counter(text) <= max_tokens:
        return text
    low = 0
    high = len(text)
    while low < high:
        midpoint = (low + high + 1) // 2
        if token_counter(text[-midpoint:]) <= max_tokens:
            low = midpoint
        else:
            high = midpoint - 1
    return text[-low:].lstrip() if low else ""


def _truncate_preserving_edges(
    text: str,
    max_tokens: int,
    token_counter: TokenCounter,
) -> str:
    if token_counter(text) <= max_tokens:
        return text
    separator = "\n"
    separator_tokens = token_counter(separator)
    available = max(max_tokens - separator_tokens, 1)
    head_budget = max(1, round(available * 0.6))
    tail_budget = max(available - head_budget, 1)
    head = _truncate_to_token_budget(text, head_budget, token_counter)
    tail = _truncate_suffix_to_token_budget(text, tail_budget, token_counter)
    if len(head) + len(tail) >= len(text):
        tail = text[len(head) :].lstrip()
    combined = f"{head}{separator}{tail}" if tail else head
    while head and token_counter(combined) > max_tokens:
        head = head[:-1].rstrip()
        combined = f"{head}{separator}{tail}" if head else tail
    if token_counter(combined) > max_tokens:
        return _truncate_suffix_to_token_budget(
            text, max_tokens, token_counter
        )
    return combined


def select_within_token_budget(
    chunks: Sequence[str],
    max_context_tokens: int,
    *,
    token_counter: TokenCounter = num_tokens_from_string,
) -> list[str]:
    if max_context_tokens <= 0:
        raise ValueError("max_context_tokens must be positive")
    selected: list[str] = []
    used = 0
    for chunk in chunks:
        if not chunk:
            continue
        remaining = max_context_tokens - used
        if remaining <= 0:
            break
        tokens = token_counter(chunk)
        if tokens <= remaining:
            selected.append(chunk)
            used += tokens
            continue
        if not selected:
            truncated = _truncate_to_token_budget(
                chunk, remaining, token_counter
            )
            if truncated:
                selected.append(truncated)
        break
    return selected


@dataclass(frozen=True)
class BoundedPrompt:
    prompt: str
    input_context_tokens: int
    selected_context_tokens: int
    reduced: bool


def bound_prompt_context(
    instruction: str,
    context_text: str,
    max_context_tokens: int,
    *,
    token_counter: TokenCounter = num_tokens_from_string,
) -> BoundedPrompt:
    before = token_counter(context_text)
    selected = _truncate_preserving_edges(
        context_text,
        max_context_tokens,
        token_counter,
    )
    after = token_counter(selected) if selected else 0
    rendered_prompt = (
        f"{instruction}\n\n{selected}" if instruction else selected
    )
    return BoundedPrompt(
        prompt=rendered_prompt,
        input_context_tokens=before,
        selected_context_tokens=after,
        reduced=after < before,
    )
