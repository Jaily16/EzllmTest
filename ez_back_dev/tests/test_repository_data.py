import re
from pathlib import Path

from scripts import verify_database


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = PROJECT_ROOT / "ezllmtest.sql"
BACKEND_ROOT = PROJECT_ROOT / "ez_back_dev"
MIGRATION_PATH = (
    BACKEND_ROOT / "migrations" / "iteration_2_workflow_artifacts.sql"
)


class _ScalarResult:
    def __init__(self, value: int):
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class _RecordingConnection:
    def __init__(self, statements: list[str], project_count: int):
        self.statements = statements
        self.project_count = project_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        self.statements.append(str(statement))
        return _ScalarResult(self.project_count)


class _RecordingEngine:
    def __init__(self, project_count: int):
        self.project_count = project_count
        self.statements: list[str] = []

    def connect(self):
        return _RecordingConnection(self.statements, self.project_count)


class _Inspector:
    def __init__(self, tables: set[str]):
        self.tables = tables

    def get_table_names(self) -> list[str]:
        return sorted(self.tables)


def test_sample_database_declares_expected_six_tables():
    sql = SQL_PATH.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE `([^`]+)`", sql))

    assert tables == verify_database.EXPECTED_TABLES


def test_uploaded_sql_files_define_empty_tables_only():
    data_write = re.compile(
        r"(?im)^\s*(?:INSERT|REPLACE)\s+INTO\b|^\s*LOAD\s+DATA\b"
    )
    base_sql = SQL_PATH.read_text(encoding="utf-8")
    migration_sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert data_write.search(base_sql) is None
    assert data_write.search(migration_sql) is None
    assert "static/projects/" not in base_sql
    assert "CREATE TABLE IF NOT EXISTS tb_project_workflow_artifact" in migration_sql


def test_runtime_project_documents_and_examples_are_git_ignored():
    ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "/example/" in ignore
    assert "/ez_back_dev/static/projects/" in ignore


def test_live_database_verifier_is_metadata_and_select_only(monkeypatch, capsys):
    engine = _RecordingEngine(project_count=0)
    monkeypatch.setattr(verify_database, "engine", engine)
    monkeypatch.setattr(
        verify_database,
        "inspect",
        lambda _engine: _Inspector(verify_database.EXPECTED_TABLES),
    )

    verify_database.main()

    assert engine.statements == ["SELECT COUNT(*) FROM tb_test_project"]
    assert "Database OK: 6 tables available; project rows=0." in capsys.readouterr().out
