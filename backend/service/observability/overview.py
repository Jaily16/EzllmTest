"""Pure aggregation helpers for the local Chinese observability dashboard."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


_LATENCY_METRICS = {
    "graph": "ezllm.agent.graph.node.duration",
    "model": "ezllm.agent.model.duration",
    "tool": "ezllm.agent.tool.duration",
    "sse_ttfe": "ezllm.agent.sse.ttfe",
}


def _histogram_percentile(
    records: list[dict[str, Any]], percentile: float
) -> float | None:
    """处理直方图分位值并返回现有契约规定的结果。

    参数:
        `records`：沿用签名中 `list[dict[str, Any]]` 类型约束的输入。
        `percentile`：沿用签名中 `float` 类型约束的输入。

    返回:
        `float | None`，内容保持现有调用方契约。"""
    buckets: dict[float, int] = defaultdict(int)
    total_count = 0
    observed_maximum: float | None = None
    for record in records:
        bounds = [float(value) for value in record["bounds"]]
        counts = [int(value) for value in record["bucket_counts"]]
        maximum = record.get("maximum")
        if maximum is not None:
            observed_maximum = max(observed_maximum or float(maximum), float(maximum))
        for index, count in enumerate(counts):
            upper = bounds[index] if index < len(bounds) else math.inf
            buckets[upper] += count
            total_count += count
    if total_count == 0:
        return None
    rank = max(1, math.ceil(total_count * percentile))
    cumulative = 0
    for upper in sorted(buckets):
        cumulative += buckets[upper]
        if cumulative >= rank:
            if math.isinf(upper):
                return observed_maximum
            return upper
    return observed_maximum


def build_metric_overview(
    records: list[dict[str, Any]], *, since_ms: int, now_ms: int
) -> dict[str, Any]:
    """构建指标overview，并遵循现有调用契约。

    参数:
        `records`：沿用签名中 `list[dict[str, Any]]` 类型约束的输入。
        `since_ms`：沿用签名中 `int` 类型约束的输入。
        `now_ms`：沿用签名中 `int` 类型约束的输入。

    返回:
        `dict[str, Any]`，内容保持现有调用方契约。"""
    counters: dict[str, float] = defaultdict(float)
    histograms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    latest_gauges: dict[str, tuple[int, float]] = {}
    error_parts: dict[str, list[float]] = {
        "model": [0.0, 0.0],
        "tool": [0.0, 0.0],
    }
    bucket_count = 12
    duration = max(1, now_ms - since_ms)
    bucket_width = max(1, math.ceil(duration / bucket_count))
    series = [
        {
            "started_at_ms": since_ms + index * bucket_width,
            "commands": 0.0,
            "model_calls": 0.0,
            "tool_calls": 0.0,
        }
        for index in range(bucket_count)
    ]

    for record in records:
        name = str(record["name"])
        kind = str(record["kind"])
        if kind == "counter":
            value = float(record.get("value") or 0)
            counters[name] += value
            if name in {
                "ezllm.agent.model.calls",
                "ezllm.agent.tool.calls",
            }:
                key = "model" if ".model." in name else "tool"
                error_parts[key][1] += value
                status = str(record.get("labels", {}).get("status", "success"))
                if status not in {"success", "ok"}:
                    error_parts[key][0] += value
            series_key = {
                "ezllm.agent.commands.processed": "commands",
                "ezllm.agent.model.calls": "model_calls",
                "ezllm.agent.tool.calls": "tool_calls",
            }.get(name)
            if series_key is not None:
                index = min(
                    bucket_count - 1,
                    max(0, (int(record["observed_at_ms"]) - since_ms) // bucket_width),
                )
                series[index][series_key] += value
        elif kind == "gauge":
            observed = int(record["observed_at_ms"])
            previous = latest_gauges.get(name)
            if previous is None or observed >= previous[0]:
                latest_gauges[name] = (observed, float(record.get("value") or 0))
        elif kind == "histogram":
            histograms[name].append(record)

    window_minutes = duration / 60_000
    latency = {
        key: {
            "p50": _histogram_percentile(histograms[name], 0.50),
            "p95": _histogram_percentile(histograms[name], 0.95),
        }
        for key, name in _LATENCY_METRICS.items()
    }
    return {
        "active_runs": latest_gauges.get(
            "ezllm.agent.runs.active", (0, 0.0)
        )[1],
        "commands": counters["ezllm.agent.commands.processed"],
        "commands_per_minute": (
            counters["ezllm.agent.commands.processed"] / window_minutes
        ),
        "model_calls": counters["ezllm.agent.model.calls"],
        "tool_calls": counters["ezllm.agent.tool.calls"],
        "input_tokens": counters["ezllm.agent.model.input_tokens"],
        "output_tokens": counters["ezllm.agent.model.output_tokens"],
        "model_error_rate": (
            error_parts["model"][0] / error_parts["model"][1]
            if error_parts["model"][1]
            else 0.0
        ),
        "tool_error_rate": (
            error_parts["tool"][0] / error_parts["tool"][1]
            if error_parts["tool"][1]
            else 0.0
        ),
        "latency_ms": latency,
        "series": series,
    }
