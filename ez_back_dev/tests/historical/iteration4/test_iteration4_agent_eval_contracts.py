from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from service.agentEvalContracts import (
    EvalCaseResult,
    EvalCounters,
    EvalMetric,
    EvalSuite,
    assert_safe_eval_payload,
)


def test_eval_contracts_are_strict_finite_and_json_only():
    counters = EvalCounters(tool_calls=1, input_tokens=10)
    result = EvalCaseResult(
        case_id="core-safe",
        suite=EvalSuite.CORE,
        passed=True,
        trajectory=("planning", "completed"),
        terminal_status="completed",
        counters=counters,
    )
    assert EvalCaseResult.model_validate_json(result.model_dump_json()) == result

    with pytest.raises(ValidationError):
        EvalCaseResult.model_validate({**result.model_dump(), "prompt": "hidden"})
    with pytest.raises(ValidationError):
        EvalMetric(name="latency", value=math.inf, numerator=None, denominator=None)


@pytest.mark.parametrize(
    "payload",
    [
        {"reasoning": "hidden"},
        {"nested": {"completion": "hidden"}},
        {"value": "SENSITIVE_DOCUMENT_SENTINEL"},
        {"path": "C:\\private\\project.txt"},
    ],
)
def test_eval_payload_safety_rejects_hidden_or_sensitive_material(payload):
    with pytest.raises(ValueError, match="unsafe eval payload"):
        assert_safe_eval_payload(payload)
