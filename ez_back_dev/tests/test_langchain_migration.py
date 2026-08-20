import re
import subprocess
import sys
from pathlib import Path

from model.TestProject import Base


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_production_code_has_no_forbidden_legacy_langchain_api():
    forbidden = re.compile(
        r"langchain_core\.pydantic_v1|"
        r"langchain\.chains|langchain\.retrievers|langchain\.storage|"
        r"langchain_community|\bChroma\b|\bFAISS\b"
    )
    findings = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if "tests" in path.parts or "test" in path.parts:
            continue
        if forbidden.search(path.read_text(encoding="utf-8")):
            findings.append(str(path.relative_to(BACKEND_ROOT)))

    assert findings == []


def test_application_import_does_not_open_network_connection():
    code = """
import socket

def fail(*args, **kwargs):
    raise AssertionError("network access during application import")

socket.create_connection = fail
socket.socket.connect = fail
import app.main
"""
    result = subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", "-c", code],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_sqlalchemy_two_metadata_preserves_six_table_shapes():
    expected_columns = {
        "tb_test_project": {"id", "name"},
        "tb_project_knowledge": {"id", "path"},
        "tb_project_requirement_testdoc": {"id", "path"},
        "tb_project_design_testdoc": {"id", "path"},
        "tb_project_type": {"id", "overflow"},
        "tb_project_info": {"id", "info_type", "info"},
    }

    assert set(Base.metadata.tables) == set(expected_columns)
    for table_name, columns in expected_columns.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) == columns

    assert {
        column.name for column in Base.metadata.tables["tb_project_info"].primary_key
    } == {"id", "info_type"}
