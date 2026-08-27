import json

from app.agentAcceptance import build_parser, main


def test_acceptance_cli_has_only_fixed_suite_and_format(monkeypatch, capsys):
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
        "--file",
    ):
        assert forbidden not in options

    monkeypatch.setenv("EZLLM_TEST_REDIS_URL", "redis://127.0.0.1:6379/0")
    code = main(["--suite", "protocol", "--format", "json"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["decision"]["passed"] is True
    assert output["suite"] == "protocol"


def test_acceptance_cli_fails_closed_without_redis(monkeypatch, capsys):
    monkeypatch.delenv("EZLLM_TEST_REDIS_URL", raising=False)
    assert main(["--suite", "all"]) == 2
    assert capsys.readouterr().err.strip() == "acceptance_environment_error"
