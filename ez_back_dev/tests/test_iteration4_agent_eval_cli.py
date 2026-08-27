from __future__ import annotations

import json

from app.agentEval import build_parser, main


def test_eval_cli_has_only_fixed_suite_and_format_controls(capsys):
    parser = build_parser()
    options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert options == {"-h", "--help", "--suite", "--format"}
    for forbidden in (
        "--dataset",
        "--provider",
        "--model",
        "--project",
        "--redis-url",
        "--output",
        "--host",
    ):
        assert forbidden not in options

    assert main(["--suite", "core", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"]["passed"] is True


def test_all_suite_requires_explicit_test_redis(monkeypatch, capsys):
    monkeypatch.delenv("EZLLM_TEST_REDIS_URL", raising=False)
    assert main(["--suite", "all", "--format", "json"]) == 2
    assert "eval_environment_error" in capsys.readouterr().err
