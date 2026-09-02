import os
from pathlib import Path


os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from service import projectRevisionService
from service.projectRevisionService import (
    SourceRevisionEntry,
    artifact_input_hash,
    compute_project_source_revision,
    compute_source_revision,
)


def _entry(path: Path, kind: str, relative_path: str) -> SourceRevisionEntry:
    return SourceRevisionEntry.from_file(
        path,
        document_kind=kind,
        relative_path=relative_path,
    )


def test_source_revision_is_order_independent_and_normalizes_paths(tmp_path):
    first_path = tmp_path / "requirements.txt"
    second_path = tmp_path / "design.txt"
    first_path.write_bytes(b"fixed requirements")
    second_path.write_bytes(b"fixed design")

    requirement = _entry(first_path, "requirements", "docs/requirements.txt")
    design = _entry(second_path, "design", r"docs\design.txt")
    normalized_design = _entry(second_path, "design", "docs/design.txt")

    assert compute_source_revision([design, requirement]) == compute_source_revision(
        [requirement, normalized_design]
    )


def test_source_revision_changes_when_same_sized_file_content_changes(tmp_path):
    document = tmp_path / "requirements.txt"
    document.write_bytes(b"version-one")
    first = compute_source_revision(
        [_entry(document, "requirements", "requirements.txt")]
    )

    document.write_bytes(b"version-two")
    second = compute_source_revision(
        [_entry(document, "requirements", "requirements.txt")]
    )

    assert first != second


def test_artifact_input_hash_is_canonical_and_excludes_transport_metadata():
    first = artifact_input_hash(
        "api_case",
        {
            "selection": {"method": "boundary", "value": 2},
            "request_id": "request-a",
            "timestamp": "2026-08-20T10:00:00+08:00",
            "ui_label": "Boundary value analysis",
        },
    )
    second = artifact_input_hash(
        "api_case",
        {
            "ui_label": "边界值分析",
            "timestamp": "2026-08-20T10:01:00+08:00",
            "request_id": "request-b",
            "selection": {"value": 2, "method": "boundary"},
        },
    )

    assert first == second
    assert first != artifact_input_hash(
        "api_case",
        {"selection": {"method": "boundary", "value": 3}},
    )


def test_compute_project_source_revision_uses_all_document_groups(
    tmp_path, monkeypatch
):
    files = {
        "knowledge": tmp_path / "knowledge.txt",
        "requirements": tmp_path / "requirements.txt",
        "design": tmp_path / "design.txt",
    }
    for kind, path in files.items():
        path.write_text(f"fixed {kind}", encoding="utf-8")

    class Row:
        def __init__(self, path: Path):
            self.path = str(path)

    class FakeProjectDao:
        @staticmethod
        def find_project_knowledge_list(pid):
            assert pid == "Ez1"
            return [Row(files["knowledge"])]

        @staticmethod
        def find_project_requirement_testdoc_list(pid):
            assert pid == "Ez1"
            return [Row(files["requirements"])]

        @staticmethod
        def find_project_design_testdoc_list(pid):
            assert pid == "Ez1"
            return [Row(files["design"])]

    monkeypatch.setattr(projectRevisionService, "testProjectDao", FakeProjectDao)

    expected = compute_source_revision(
        [
            _entry(files["knowledge"], "knowledge", "knowledge.txt"),
            _entry(files["requirements"], "requirements", "requirements.txt"),
            _entry(files["design"], "design", "design.txt"),
        ]
    )
    assert compute_project_source_revision("Ez1") == expected
