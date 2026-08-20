import re
from pathlib import Path

from scripts import verify_database


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def test_sample_database_declares_expected_six_tables():
    sql = SQL_PATH.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE `([^`]+)`", sql))

    assert tables == verify_database.EXPECTED_TABLES


def test_sample_database_contains_seven_projects():
    sql = SQL_PATH.read_text(encoding="utf-8")
    project_insert = re.search(r"INSERT INTO `tb_test_project` VALUES (.*?);", sql, re.S)

    assert project_insert is not None
    assert len(re.findall(r"\('Ez\d{19}'", project_insert.group(1))) == 7


def test_all_referenced_documents_are_present():
    sql = SQL_PATH.read_text(encoding="utf-8")
    paths = set(
        re.findall(
            r"'(static/projects/[^']+\.(?:pdf|docx|doc|md|txt))'",
            sql,
            flags=re.IGNORECASE,
        )
    )

    assert len(paths) == 47
    assert not [path for path in paths if not (BACKEND_ROOT / path).is_file()]


def test_live_database_verifier_is_metadata_and_select_only(monkeypatch, capsys):
    engine = _RecordingEngine(project_count=7)
    monkeypatch.setattr(verify_database, "engine", engine)
    monkeypatch.setattr(
        verify_database,
        "inspect",
        lambda _engine: _Inspector(verify_database.EXPECTED_TABLES),
    )

    verify_database.main()

    assert engine.statements == ["SELECT COUNT(*) FROM tb_test_project"]
    assert "Database OK: 6 tables and 7 sample projects found." in capsys.readouterr().out
