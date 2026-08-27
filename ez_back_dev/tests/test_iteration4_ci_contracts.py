from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/iteration4-offline.yml"


def test_ci_has_read_only_triggers_concurrency_and_immutable_actions():
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "pull_request:",
        "branches: [main]",
        "workflow_dispatch:",
        "permissions:\n  contents: read",
        "cancel-in-progress: true",
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0",
        "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e # v6.4.0",
        "persist-credentials: false",
        "package-manager-cache: false",
    ):
        assert required in text
    assert "secrets." not in text
    assert "upload-artifact" not in text


def test_ci_is_offline_and_runs_all_delivery_gates():
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "PYTHON_DOTENV_DISABLED: \"1\"",
        "EZLLM_TEST_REDIS_URL: redis://127.0.0.1:6379/0",
        "redis:8.2.8-alpine@sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103",
        "python scripts/scan_credentials.py",
        "python -m pytest tests -q",
        "python -m app.agentEval --suite all --format json",
        "python -m app.agentAcceptance --suite all --format json",
        "python -m app.agentBenchmark --suite all --telemetry compare --format json",
        "npm ci --ignore-scripts --no-audit --no-fund",
        "npm run lint -- --no-fix",
        "npm run type-check",
        "npm run build",
        "scripts/check_frontend_bundle.py ez_front_dev/dist",
        "docker compose --env-file ops/compose/.env.example config --quiet",
        "docker compose --env-file ops/compose/.env.example -p ezllm-aspect8-ci up --build -d --wait",
        "up{job=\"ezllm-otel-collector\"}",
        "--user admin:replace_with_local_grafana_password",
        "http://tempo:3200/api/search?service.name=ezllm-agent-api&limit=10",
        "ASPECT8_ACCEPTANCE_TOPOLOGY=isolated_compose",
        "docker compose --env-file ops/compose/.env.example -p ezllm-aspect8-ci down -v",
    ):
        assert required in text
    for forbidden in (
        "ZHIPU_API_KEY: ${{",
        "DASHSCOPE_API_KEY: ${{",
        "DEEPSEEK_API_KEY: ${{",
        "MOONSHOT_API_KEY: ${{",
        "continue-on-error: true",
    ):
        assert forbidden not in text
