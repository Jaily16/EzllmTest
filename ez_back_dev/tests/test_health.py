from fastapi.testclient import TestClient

import app.main as main_module


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        return 1


class _Engine:
    def connect(self):
        return _Connection()


def test_health_reports_database_and_models(monkeypatch):
    monkeypatch.setattr(main_module, "engine", _Engine())
    response = TestClient(main_module.app).get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["chat_model"] == "glm-4.7"
    assert response.json()["embedding_model"] == "embedding-3"
