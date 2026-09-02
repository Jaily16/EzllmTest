import re
from pathlib import Path

from scripts import verify_database


from repo_paths import REPO_ROOT as PROJECT_ROOT
SQL_PATH = PROJECT_ROOT / "ezllmtest.sql"
BACKEND_ROOT = PROJECT_ROOT / "ez_back_dev"


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


def test_schema_only_database_declares_all_seven_tables():
    sql = SQL_PATH.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE `([^`]+)`", sql))

    assert tables == verify_database.EXPECTED_TABLES


def test_uploaded_sql_defines_empty_tables_without_a_migration_folder():
    data_write = re.compile(
        r"(?im)^\s*(?:INSERT|REPLACE)\s+INTO\b|^\s*LOAD\s+DATA\b"
    )
    base_sql = SQL_PATH.read_text(encoding="utf-8")

    assert data_write.search(base_sql) is None
    assert "static/projects/" not in base_sql
    assert "CREATE TABLE `tb_project_workflow_artifact`" in base_sql
    assert not (BACKEND_ROOT / "migrations").exists()


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
    assert "Database OK: 7 tables available; project rows=0." in capsys.readouterr().out
