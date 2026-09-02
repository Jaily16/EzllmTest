"""Controlled CLI for the deterministic Iteration 4 integrated acceptance."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from service.evaluation.acceptance_contracts import AcceptanceSuite
from service.evaluation.acceptance_runner import run_acceptance


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic offline Iteration 4 acceptance gate."
    )
    parser.add_argument(
        "--suite",
        choices=tuple(item.value for item in AcceptanceSuite),
        default=AcceptanceSuite.ALL.value,
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _text_report(report) -> str:
    passed = sum(item.passed for item in report.results)
    return (
        f"Aspect 8 acceptance {report.suite.value}: "
        f"{passed}/{len(report.results)} cases passed; "
        f"hard_gate={'pass' if report.decision.passed else 'fail'}; "
        "real_model=not_authorized; hosted_ci=awaiting_explicit_push"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_acceptance(
            AcceptanceSuite(args.suite),
            redis_url=os.environ.get("EZLLM_TEST_REDIS_URL"),
        )
    except Exception:
        print("acceptance_environment_error", file=sys.stderr)
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
