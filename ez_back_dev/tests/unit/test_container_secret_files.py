"""Unit tests for the explicit, allowlisted container secret-file boundary."""

from __future__ import annotations

import importlib
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest


def _config_module(monkeypatch):
    # Prevent the legacy import-time dotenv behavior from looking for a real
    # repository .env while these tests exercise only the pure resolver.
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "true")
    module = importlib.import_module("app.config")
    return importlib.reload(module)


@pytest.fixture
def secret_dir():
    # pytest's default temp root is ACL-restricted on this host.  This
    # task-owned directory is outside the repository and contains no user data.
    root = Path(__file__).resolve().parents[4].parent
    with TemporaryDirectory(prefix="ezllmtest-aspect7-secret-", dir=str(root)) as directory:
        yield Path(directory)


def test_explicit_file_is_used_for_allowlisted_name(secret_dir: Path, monkeypatch) -> None:
    config = _config_module(monkeypatch)
    secret_file = secret_dir / "secret.txt"
    secret_file.write_text("fixture-secret\n", encoding="utf-8")

    assert config._resolve_secret_value("ZHIPU_API_KEY", None, str(secret_file)) == (
        "fixture-secret"
    )


def test_direct_value_and_file_conflict_fails_closed(secret_dir: Path, monkeypatch) -> None:
    config = _config_module(monkeypatch)
    secret_file = secret_dir / "secret.txt"
    secret_file.write_text("fixture-secret", encoding="utf-8")

    with pytest.raises(config.ConfigurationError) as error:
        config._resolve_secret_value("ZHIPU_API_KEY", "direct-value", str(secret_file))

    message = str(error.value)
    assert "direct-value" not in message
    assert str(secret_file) not in message


@pytest.mark.parametrize(
    "content",
    ["x" * 8193, "bad\x00value"],
)
def test_invalid_file_content_fails_without_disclosing_input(
    secret_dir: Path, monkeypatch, content: str
) -> None:
    config = _config_module(monkeypatch)
    secret_file = secret_dir / "secret.txt"
    secret_file.write_text(content, encoding="utf-8")

    with pytest.raises(config.ConfigurationError) as error:
        config._resolve_secret_value("ZHIPU_API_KEY", None, str(secret_file))

    message = str(error.value)
    assert content not in message
    assert str(secret_file) not in message


def test_missing_file_fails_without_disclosing_path(secret_dir: Path, monkeypatch) -> None:
    config = _config_module(monkeypatch)
    secret_file = secret_dir / "missing-secret.txt"

    with pytest.raises(config.ConfigurationError) as error:
        config._resolve_secret_value("ZHIPU_API_KEY", None, str(secret_file))

    assert str(secret_file) not in str(error.value)


def test_empty_file_preserves_unconfigured_behavior(secret_dir: Path, monkeypatch) -> None:
    config = _config_module(monkeypatch)
    secret_file = secret_dir / "empty-secret.txt"
    secret_file.write_text("", encoding="utf-8")

    assert config._resolve_secret_value("ZHIPU_API_KEY", None, str(secret_file)) == ""


def test_unset_file_keeps_existing_direct_value(monkeypatch) -> None:
    config = _config_module(monkeypatch)

    assert config._resolve_secret_value("ZHIPU_API_KEY", "direct-value", None) == (
        "direct-value"
    )


def test_non_allowlisted_name_is_rejected(secret_dir: Path, monkeypatch) -> None:
    config = _config_module(monkeypatch)
    secret_file = secret_dir / "secret.txt"
    secret_file.write_text("fixture-secret", encoding="utf-8")

    with pytest.raises(config.ConfigurationError):
        config._resolve_secret_value("UNLISTED_SETTING", "", str(secret_file))
