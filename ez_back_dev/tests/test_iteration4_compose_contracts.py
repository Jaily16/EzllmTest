from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]


def _compose():
    return yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))


def test_compose_pins_external_images_and_only_publishes_loopback_ports():
    compose = _compose()
    services = compose["services"]
    assert set(services) == {
        "frontend", "legacy-api", "agent-api", "worker", "mysql", "redis",
        "otel-collector", "prometheus", "tempo", "grafana",
    }
    for name in ("mysql", "redis", "otel-collector", "prometheus", "tempo", "grafana"):
        image = services[name]["image"]
        assert "@sha256:" in image and len(image.rsplit("@sha256:", 1)[1]) == 64
    assert services["frontend"]["ports"] == ["127.0.0.1:8080:8080"]
    assert services["legacy-api"]["ports"] == ["127.0.0.1:8130:8130"]
    assert services["agent-api"]["ports"] == ["127.0.0.1:8131:8131"]
    assert services["grafana"]["ports"] == ["127.0.0.1:3000:3000"]
    assert services["prometheus"]["ports"] == ["127.0.0.1:9090:9090"]
    for name in ("mysql", "redis", "worker", "otel-collector", "tempo"):
        assert "ports" not in services[name]


def test_compose_uses_named_data_volumes_and_no_real_project_bind_mount():
    compose = _compose()
    assert set(compose["volumes"]) == {
        "mysql_data", "redis_data", "project_files", "prometheus_data",
        "tempo_data", "grafana_data",
    }
    rendered = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    assert "static/projects:" not in rendered
    assert "project_files:/app/static/projects" in rendered
    assert "otel-collector:4317" in rendered
    assert "debug" not in (ROOT / "ops/observability/otel-collector.yaml").read_text(encoding="utf-8").lower()


def test_collector_redacts_content_and_grafana_is_provisioned():
    collector = (ROOT / "ops/observability/otel-collector.yaml").read_text(encoding="utf-8").lower()
    for key in (
        "gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.prompt",
        "tool.arguments", "tool.results", "retrieval.query.text", "db.statement",
        "redis.key", "url.query", "authorization", "cookie",
    ):
        assert key in collector
    datasources = yaml.safe_load(
        (ROOT / "ops/observability/grafana/provisioning/datasources/datasources.yaml").read_text(encoding="utf-8")
    )
    assert {item["uid"] for item in datasources["datasources"]} == {"prometheus", "tempo"}
    assert (ROOT / "ops/observability/grafana/dashboards/agent-overview.json").is_file()


def test_docker_context_excludes_credentials_dependencies_and_project_files():
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for pattern in (".env", "**/.env", "**/node_modules", "ez_back_dev/static/projects"):
        assert pattern in ignore
    backend = (ROOT / "ez_back_dev/Dockerfile").read_text(encoding="utf-8")
    assert "python:3.11.15-slim@sha256:" in backend
    assert "PYTHON_DOTENV_DISABLED=1" in backend


def test_only_published_observability_uis_join_the_gateway_network():
    services = _compose()["services"]
    for name in ("prometheus", "grafana"):
        assert set(services[name]["networks"]) == {
            "observability",
            "application",
        }
    assert services["otel-collector"]["networks"] == ["observability"]
    assert services["tempo"]["networks"] == ["observability"]
    for name in ("mysql", "redis", "otel-collector", "tempo"):
        assert "ports" not in services[name]
    grafana_env = services["grafana"]["environment"]
    assert grafana_env["GF_PLUGINS_PREINSTALL_DISABLED"] == "true"
    assert grafana_env["GF_ANALYTICS_CHECK_FOR_UPDATES"] == "false"
