"""Fixed offline benchmark CLI; no provider or arbitrary path switches."""

from __future__ import annotations

import argparse
import json
import sys

from service.evaluation.benchmark_contracts import BenchmarkSuite, BenchmarkTelemetryMode
from service.evaluation.benchmark_runner import run_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EzLLM offline Agent benchmark")
    parser.add_argument("--suite", choices=[item.value for item in BenchmarkSuite], default="all")
    parser.add_argument(
        "--telemetry",
        choices=[item.value for item in BenchmarkTelemetryMode],
        default="compare",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_benchmark(args.suite, args.telemetry)
    except (RuntimeError, ValueError):
        print("Agent benchmark environment is unavailable", file=sys.stderr)
        return 2
    payload = report.model_dump(mode="json")
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    else:
        print(
            f"suite={report.suite.value} cases={len(report.cases)} "
            f"passed={str(report.passed).lower()} export={report.telemetry_export_status}"
        )
        for gate in report.gates:
            print(f"{gate.name}: {gate.status}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
