"""Controlled command-line entry point for the offline Aspect 6 Eval."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from service.agentEvalContracts import EvalSuite
from service.agentEvalRunner import run_eval


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic, offline Iteration 4 Agent Eval gate."
    )
    parser.add_argument(
        "--suite",
        choices=tuple(item.value for item in EvalSuite),
        default=EvalSuite.ALL.value,
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _text_report(report) -> str:
    passed = sum(item.passed for item in report.results)
    return (
        f"Aspect 6 Eval {report.suite.value}: {passed}/{len(report.results)} "
        f"cases passed; hard_gate={'pass' if report.decision.passed else 'fail'}; "
        "real_model=not_authorized; performance=N/A"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_eval(
            EvalSuite(args.suite),
            redis_url=os.environ.get("EZLLM_TEST_REDIS_URL"),
        )
    except Exception:
        # Deliberately exclude exception text: it may contain a URL or local path.
        print("eval_environment_error", file=sys.stderr)
        return 2
    if args.format == "json":
        print(
            json.dumps(
                report.model_dump(mode="json"),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        print(_text_report(report))
    return 0 if report.decision.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
