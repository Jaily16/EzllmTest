"""Deterministic tests for the additive Aspect 6 readiness endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.agentApi as agent_api
import app.main as legacy_api


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        assert str(statement).upper() == "SELECT 1"
        return 1


class _Engine:
    def connect(self):
        return _Connection()


class _BrokenEngine:
    def connect(self):
        raise RuntimeError("database unavailable")


class _Redis:
    def __init__(self, healthy: bool):
        self.healthy = healthy

    async def ping(self):
        if not self.healthy:
            raise RuntimeError("redis unavailable")
        return True


class _Store:
    def __init__(self, *, redis_healthy: bool, worker_healthy: bool):
        self.redis = _Redis(redis_healthy)
        self.worker_healthy = worker_healthy

    async def worker_available(self):
        return self.worker_healthy


class _Workbench:
    def __init__(self, *, redis_healthy: bool, worker_healthy: bool):
        self.store = _Store(
            redis_healthy=redis_healthy,
            worker_healthy=worker_healthy,
        )


def test_legacy_readiness_is_read_only_and_safe(monkeypatch):
    monkeypatch.setattr(legacy_api, "engine", _Engine())

    response = TestClient(legacy_api.app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "iteration5-readiness-v1",
        "service": "legacy-api",
        "status": "ready",
        "checks": {"database": "ok"},
    }


def test_legacy_readiness_returns_503_without_database_details(monkeypatch):
    monkeypatch.setattr(legacy_api, "engine", _BrokenEngine())

    response = TestClient(legacy_api.app).get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "schema_version": "iteration5-readiness-v1",
        "service": "legacy-api",
        "status": "not_ready",
        "checks": {"database": "unavailable"},
    }
    assert "database unavailable" not in response.text


def test_agent_readiness_requires_redis_and_worker():
    app = agent_api.create_agent_api_app(
        service=_Workbench(redis_healthy=True, worker_healthy=True),
        allowed_origins=("http://localhost:8080",),
        allow_test_host=True,
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "iteration5-readiness-v1",
        "service": "agent-api",
        "status": "ready",
        "checks": {"redis": "ok", "worker": "available"},
    }


def test_agent_readiness_does_not_expose_failure_details():
    app = agent_api.create_agent_api_app(
        service=_Workbench(redis_healthy=True, worker_healthy=False),
        allowed_origins=("http://localhost:8080",),
        allow_test_host=True,
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "schema_version": "iteration5-readiness-v1",
        "service": "agent-api",
        "status": "not_ready",
        "checks": {"redis": "ok", "worker": "unavailable"},
    }
    assert "redis unavailable" not in response.text
