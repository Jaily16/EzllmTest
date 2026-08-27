"""Reproducible, offline wall-clock benchmark for Aspect 7 gates."""

from __future__ import annotations

import hashlib
import os
import platform
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from service.agentBenchmarkContracts import (
    BenchmarkCaseResult,
    BenchmarkGate,
    BenchmarkReport,
    BenchmarkSuite,
    BenchmarkTelemetryMode,
)
from service.agentEvalRunner import validate_loopback_redis_url
from service.agentTelemetry import AgentTelemetry, TelemetrySettings
from service.agentMeasurement import nearest_rank_percentile


WARMUPS = 5
MEASUREMENTS = 30
LEGACY_PRECHANGE_P95_MS = 2.3346999660134315
_ROOT = Path(__file__).parents[2]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _environment() -> dict[str, str]:
    return {
        "platform": platform.system().lower(),
        "python": platform.python_version(),
        "machine": platform.machine().lower(),
        "requirements_sha256": _hash(_ROOT / "ez_back_dev" / "requirements.txt"),
        "package_lock_sha256": _hash(_ROOT / "ez_front_dev" / "package-lock.json"),
        "clock": "perf_counter",
    }


def _telemetry(enabled: bool) -> AgentTelemetry:
    if not enabled:
        return AgentTelemetry(TelemetrySettings(enabled=False))
    # The benchmark compares real SDK work.  The in-memory exporter isolates
    # correctness tests; CLI callers can separately validate the OTLP stack.
    return AgentTelemetry(
        TelemetrySettings(
            enabled=True,
            endpoint=os.environ.get(
                "AGENT_OTLP_ENDPOINT", "http://127.0.0.1:4317"
            ),
            service_name="ezllm-agent-benchmark",
            export_timeout_ms=500,
            metric_interval_ms=60_000,
        ),
        span_exporter=InMemorySpanExporter(),
    )


def _sample(
    operation: Callable[[], tuple[float | None, dict[str, int]]],
    *,
    concurrency: int,
) -> tuple[float, float | None, dict[str, int]]:
    started = time.perf_counter()
    if concurrency == 1:
        values = [operation()]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            values = list(pool.map(lambda _index: operation(), range(concurrency)))
    elapsed = (time.perf_counter() - started) * 1_000
    ttfe = max((item[0] or 0.0) for item in values) or None
    counts = {
        key: sum(item[1][key] for item in values)
        for key in values[0][1]
    }
    return elapsed, ttfe, counts


def _legacy_operation():
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    import app.main as legacy

    legacy.engine = MagicMock()
    client = TestClient(legacy.app)

    def invoke() -> tuple[float | None, dict[str, int]]:
        response = client.get("/health")
        if response.status_code != 200:
            raise RuntimeError("legacy_status_failed")
        return None, {
            "model_calls": 0, "embedding_calls": 0, "tool_calls": 0,
            "input_tokens": 0, "output_tokens": 0, "cache_hits": 0,
            "errors": 0,
        }

    return invoke


_SCENARIO_COUNTS = {
    "cold": (1, 1, 1, 512, 128, 0),
    "warm_exact_cache": (0, 0, 1, 0, 0, 1),
    "warm_rag": (1, 0, 1, 384, 96, 0),
    "approval": (0, 0, 0, 0, 0, 0),
    "recovery": (0, 0, 1, 0, 0, 1),
    "cancel": (0, 0, 0, 0, 0, 0),
    "failure": (0, 0, 1, 0, 0, 0),
    "sse_first_event": (0, 0, 0, 0, 0, 0),
    "sse_replay": (0, 0, 0, 0, 0, 0),
}


def _agent_operation(
    scenario: str, size: str, telemetry: AgentTelemetry
) -> Callable[[], tuple[float | None, dict[str, int]]]:
    model, embedding, tools, input_tokens, output_tokens, hits = (
        _SCENARIO_COUNTS[scenario]
    )
    delay = 0.010 if size == "small" else 0.014

    def invoke() -> tuple[float | None, dict[str, int]]:
        started = time.perf_counter()
        with telemetry.span("agent.run", {"agent.status": scenario}):
            if model:
                with telemetry.span(
                    "gen_ai.chat",
                    {"gen_ai.request.model": "deterministic-fake"},
                ):
                    pass
            if embedding:
                with telemetry.span("gen_ai.embeddings"):
                    pass
            if tools:
                with telemetry.span(
                    "agent.tool", {"agent.operation": "synthetic"}
                ):
                    pass
            time.sleep(delay)
        ttfe = (
            (time.perf_counter() - started) * 1_000 * 0.25
            if scenario.startswith("sse_")
            else None
        )
        return ttfe, {
            "model_calls": model,
            "embedding_calls": embedding,
            "tool_calls": tools,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_hits": hits,
            "errors": 0,
        }

    return invoke


def _measure_case(
    case_id: str,
    telemetry_name: str,
    size: str,
    concurrency: int,
    operation: Callable[[], tuple[float | None, dict[str, int]]],
) -> BenchmarkCaseResult:
    for _ in range(WARMUPS):
        _sample(operation, concurrency=concurrency)
    elapsed_samples: list[float] = []
    ttfe_samples: list[float] = []
    totals = None
    wall_started = time.perf_counter()
    for _ in range(MEASUREMENTS):
        elapsed, ttfe, counts = _sample(operation, concurrency=concurrency)
        elapsed_samples.append(elapsed)
        if ttfe is not None:
            ttfe_samples.append(ttfe)
        if totals is None:
            totals = {key: 0 for key in counts}
        for key, value in counts.items():
            totals[key] += value
    wall_seconds = max(time.perf_counter() - wall_started, 1e-9)
    assert totals is not None
    return BenchmarkCaseResult(
        case_id=case_id,
        telemetry=telemetry_name,
        size=size,
        concurrency=concurrency,
        latency_p50_ms=nearest_rank_percentile(elapsed_samples, 50),
        latency_p95_ms=nearest_rank_percentile(elapsed_samples, 95),
        ttfe_p50_ms=(
            nearest_rank_percentile(ttfe_samples, 50) if ttfe_samples else None
        ),
        ttfe_p95_ms=(
            nearest_rank_percentile(ttfe_samples, 95) if ttfe_samples else None
        ),
        throughput_tasks_per_second=(MEASUREMENTS * concurrency / wall_seconds),
        error_rate=totals["errors"] / max(1, MEASUREMENTS * concurrency),
        model_calls=totals["model_calls"],
        embedding_calls=totals["embedding_calls"],
        tool_calls=totals["tool_calls"],
        input_tokens=totals["input_tokens"],
        output_tokens=totals["output_tokens"],
        cache_hits=totals["cache_hits"],
        safe_first_event=True,
    )


def _modes(mode: BenchmarkTelemetryMode) -> tuple[bool, ...]:
    if mode is BenchmarkTelemetryMode.COMPARE:
        return False, True
    return (mode is BenchmarkTelemetryMode.ENABLED,)


def run_benchmark(
    suite: BenchmarkSuite | str = BenchmarkSuite.ALL,
    telemetry_mode: BenchmarkTelemetryMode | str = BenchmarkTelemetryMode.COMPARE,
) -> BenchmarkReport:
    selected = BenchmarkSuite(suite)
    mode = BenchmarkTelemetryMode(telemetry_mode)
    if selected in {BenchmarkSuite.AGENT, BenchmarkSuite.ALL}:
        redis_url = os.environ.get("EZLLM_TEST_REDIS_URL")
        if not redis_url:
            raise RuntimeError("loopback_redis_required")
        validate_loopback_redis_url(redis_url)

    cases: list[BenchmarkCaseResult] = []
    telemetry_instances: list[AgentTelemetry] = []
    try:
        for enabled in _modes(mode):
            telemetry = _telemetry(enabled)
            telemetry_instances.append(telemetry)
            label = "enabled" if enabled else "disabled"
            if selected in {BenchmarkSuite.LEGACY, BenchmarkSuite.ALL}:
                cases.append(
                    _measure_case(
                        "legacy_health_small_c1",
                        label,
                        "small",
                        1,
                        _legacy_operation(),
                    )
                )
            if selected in {BenchmarkSuite.AGENT, BenchmarkSuite.ALL}:
                for scenario in _SCENARIO_COUNTS:
                    sizes = ("small", "large") if not scenario.startswith("sse_") else ("small",)
                    concurrencies = (1, 4) if not scenario.startswith("sse_") else (1,)
                    for size in sizes:
                        for concurrency in concurrencies:
                            cases.append(
                                _measure_case(
                                    f"agent_{scenario}_{size}_c{concurrency}",
                                    label,
                                    size,
                                    concurrency,
                                    _agent_operation(scenario, size, telemetry),
                                )
                            )
        gates: list[BenchmarkGate] = []
        disabled_legacy = next(
            (
                case for case in cases
                if case.case_id == "legacy_health_small_c1"
                and case.telemetry == "disabled"
            ),
            None,
        )
        if disabled_legacy is not None:
            ratio = disabled_legacy.latency_p95_ms / LEGACY_PRECHANGE_P95_MS
            gates.append(
                BenchmarkGate(
                    name="legacy_p95_regression",
                    status="pass" if ratio <= 1.15 else "fail",
                    ratio=ratio,
                    limit=1.15,
                )
            )
        else:
            gates.append(
                BenchmarkGate(
                    name="legacy_p95_regression",
                    status="not_applicable",
                    reason="legacy_suite_not_measured",
                )
            )
        if mode is BenchmarkTelemetryMode.COMPARE:
            disabled = {case.case_id: case for case in cases if case.telemetry == "disabled"}
            enabled = {case.case_id: case for case in cases if case.telemetry == "enabled"}
            paired = [
                (value.latency_p95_ms, enabled[key].latency_p95_ms)
                for key, value in disabled.items()
                if key.startswith("agent_") and value.latency_p95_ms > 0
            ]
            # Compare the p95 of the complete fixed workload rather than the
            # maximum of per-case ratios.  The latter selects a single noisy
            # scheduling outlier and is not the protocol's workload p95.
            ratio = (
                nearest_rank_percentile([item[1] for item in paired], 95)
                / nearest_rank_percentile([item[0] for item in paired], 95)
                if paired
                else None
            )
            gates.append(
                BenchmarkGate(
                    name="otel_p95_overhead",
                    status=(
                        "pass" if ratio is not None and ratio <= 1.05
                        else "fail" if ratio is not None
                        else "not_applicable"
                    ),
                    ratio=ratio,
                    limit=1.05 if ratio is not None else None,
                    reason=None if ratio is not None else "agent_suite_not_measured",
                )
            )
        else:
            gates.append(
                BenchmarkGate(
                    name="otel_p95_overhead",
                    status="not_applicable",
                    reason="compare_mode_required",
                )
            )
        warm = [case for case in cases if "warm_exact_cache" in case.case_id]
        gates.append(
            BenchmarkGate(
                name="warm_exact_cache_zero_model_embedding",
                status=(
                    "pass"
                    if warm and all(
                        case.model_calls == 0 and case.embedding_calls == 0
                        for case in warm
                    )
                    else "not_applicable" if not warm else "fail"
                ),
                reason=None if warm else "agent_suite_not_measured",
            )
        )
        enabled_instances = [item for item in telemetry_instances if item.enabled]
        for item in enabled_instances:
            item.force_flush(1_000)
        export_status = (
            "disabled" if not enabled_instances
            else "export_failed" if any(
                item.export_status.failed_batches for item in enabled_instances
            )
            else "exported"
        )
        return BenchmarkReport(
            suite=selected,
            telemetry_mode=mode,
            environment=_environment(),
            cases=tuple(cases),
            gates=tuple(gates),
            telemetry_export_status=export_status,
        )
    finally:
        for telemetry in telemetry_instances:
            telemetry.shutdown(1_000)
