from __future__ import annotations

import io
import json
import logging

import pytest
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from service.agentTelemetry import AgentTelemetry, TelemetrySettings, TraceCarrier
from service.structuredLogging import SafeJsonLogger


class _FailingExporter(SpanExporter):
    def export(self, _spans):
        raise RuntimeError("credential=secret redis://private-host:6379/0")

    def shutdown(self):
        return None


def _settings(**updates) -> TelemetrySettings:
    values = {
        "enabled": True,
        "endpoint": "http://127.0.0.1:4317",
        "service_name": "ezllm-agent-test",
        "export_timeout_ms": 200,
        "metric_interval_ms": 1_000,
    }
    values.update(updates)
    return TelemetrySettings(**values)


@pytest.mark.parametrize(
    "endpoint",
    (
        "https://collector.example.com:4317",
        "http://127.0.0.1:4318/v1/traces",
        "http://user:secret@127.0.0.1:4317",
        "http://otel-collector:9999",
    ),
)
def test_telemetry_settings_reject_remote_or_ambiguous_exporters(endpoint):
    with pytest.raises(ValueError, match="OTLP endpoint"):
        _settings(endpoint=endpoint)


def test_trace_carrier_accepts_only_canonical_w3c_traceparent():
    carrier = TraceCarrier(
        traceparent="00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    )
    assert carrier.trace_id == "0123456789abcdef0123456789abcdef"
    for value in (
        "00-00000000000000000000000000000000-0123456789abcdef-01",
        "00-0123456789abcdef0123456789abcdef-0000000000000000-01",
        "00-ABCDEF6789abcdef0123456789abcdef-0123456789abcdef-01",
        "00-0123456789abcdef0123456789abcdef-0123456789abcdef-03",
        "constructor",
    ):
        with pytest.raises(ValueError):
            TraceCarrier(traceparent=value)


def test_manual_spans_share_trace_and_never_record_content_or_stacktraces():
    exporter = InMemorySpanExporter()
    telemetry = AgentTelemetry(_settings(), span_exporter=exporter)
    try:
        with telemetry.span(
            "agent.run",
            {"agent.status": "planning", "agent.operation": "ui_case"},
        ):
            carrier = telemetry.current_trace_carrier()
            assert carrier is not None
            with telemetry.span("agent.plan", {"gen_ai.request.model": "fake-model"}):
                pass
            with pytest.raises(RuntimeError):
                with telemetry.span("agent.validation"):
                    raise RuntimeError("prompt=do not store this")
        assert telemetry.force_flush(1_000)
        spans = exporter.get_finished_spans()
        assert [span.name for span in spans] == [
            "agent.plan",
            "agent.validation",
            "agent.run",
        ]
        assert len({span.context.trace_id for span in spans}) == 1
        assert carrier.trace_id == f"{spans[0].context.trace_id:032x}"
        rendered = json.dumps(
            [
                {
                    "name": span.name,
                    "attributes": dict(span.attributes or {}),
                    "events": [event.name for event in span.events],
                }
                for span in spans
            ],
            sort_keys=True,
        ).lower()
        assert "do not store this" not in rendered
        assert "traceback" not in rendered
        assert "exception.stacktrace" not in rendered
        assert "prompt" not in rendered
        assert "error.type" in rendered
    finally:
        telemetry.shutdown(1_000)


def test_exporter_failure_is_fail_open_and_counted_without_error_content():
    telemetry = AgentTelemetry(_settings(), span_exporter=_FailingExporter())
    try:
        with telemetry.span("agent.run"):
            business_result = {"status": "completed"}
        assert business_result == {"status": "completed"}
        telemetry.force_flush(1_000)
        assert telemetry.export_status.failed_batches >= 1
        assert telemetry.export_status.last_error == "export_failed"
    finally:
        telemetry.shutdown(1_000)


def test_json_logger_uses_a_fixed_allowlist_and_no_exception_payloads():
    stream = io.StringIO()
    logger = logging.getLogger("ezllm-safe-json-test")
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    safe = SafeJsonLogger(logger, service="ezllm-agent-test")
    safe.info(
        "agent.tool.completed",
        trace_id="0123456789abcdef0123456789abcdef",
        operation="ui_case",
        status="success",
        tool_calls=1,
        prompt="must-not-appear",
        exc_info=RuntimeError("must-not-appear"),
    )
    payload = json.loads(stream.getvalue())
    assert payload["event"] == "agent.tool.completed"
    assert payload["operation"] == "ui_case"
    assert payload["tool_calls"] == 1
    assert "prompt" not in payload
    assert "exc_info" not in payload
    assert "must-not-appear" not in stream.getvalue()
