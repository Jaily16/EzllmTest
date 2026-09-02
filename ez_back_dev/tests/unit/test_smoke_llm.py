import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import smoke_llm


from repo_paths import REPO_ROOT as PROJECT_ROOT


class _FakeChatModel:
    def __init__(self, selected: list[tuple[str, str]], label: str):
        self.selected = selected
        self.label = label

    def invoke(self, prompt: str):
        self.selected.append((self.label, prompt))
        return SimpleNamespace(
            content="SMOKE_OK",
            usage_metadata={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
        )


class _FakeEmbeddings:
    def __init__(self, calls: list[str]):
        self.calls = calls

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


def test_provider_argument_is_required():
    with pytest.raises(SystemExit) as exc_info:
        smoke_llm.main([])

    assert exc_info.value.code == 2


def test_cost_confirmation_is_required_before_factory_call(monkeypatch):
    def unexpected_factory_call(_label):
        raise AssertionError("model factory must not run before cost confirmation")

    monkeypatch.setattr(smoke_llm, "get_chat_model", unexpected_factory_call)

    with pytest.raises(SystemExit, match="--confirm-cost"):
        smoke_llm.main(["--provider", "deepseek"])


@pytest.mark.parametrize(
    ("provider", "expected_label"),
    [
        ("zhipu", "GLM-4.7"),
        ("alibaba", "通义千问"),
        ("deepseek", "DeepSeek"),
        ("moonshot", "Moonshot Kimi"),
    ],
)
def test_selected_provider_invokes_only_its_public_label(
    monkeypatch, capsys, provider, expected_label
):
    selected: list[tuple[str, str]] = []
    embedding_calls: list[str] = []
    monkeypatch.setattr(
        smoke_llm,
        "get_chat_model",
        lambda label: _FakeChatModel(selected, label),
    )
    monkeypatch.setattr(
        smoke_llm,
        "get_embeddings",
        lambda: _FakeEmbeddings(embedding_calls),
    )

    assert smoke_llm.main(["--provider", provider, "--confirm-cost"]) == 0

    assert [label for label, _prompt in selected] == [expected_label]
    assert embedding_calls == []
    output = capsys.readouterr().out
    assert f"Provider: {provider}" in output
    assert "Chat response: SMOKE_OK" in output
    assert "total_tokens=4" in output


def test_embedding_requires_zhipu_provider(monkeypatch):
    def unexpected_factory_call(_label):
        raise AssertionError("chat factory must not run for an invalid flag combination")

    monkeypatch.setattr(smoke_llm, "get_chat_model", unexpected_factory_call)

    with pytest.raises(SystemExit, match="only supported with --provider zhipu"):
        smoke_llm.main(
            ["--provider", "moonshot", "--confirm-cost", "--with-embedding"]
        )


def test_embedding_runs_only_with_explicit_flag(monkeypatch, capsys):
    selected: list[tuple[str, str]] = []
    embedding_calls: list[str] = []
    monkeypatch.setattr(
        smoke_llm,
        "get_chat_model",
        lambda label: _FakeChatModel(selected, label),
    )
    monkeypatch.setattr(
        smoke_llm,
        "get_embeddings",
        lambda: _FakeEmbeddings(embedding_calls),
    )

    result = smoke_llm.main(
        ["--provider", "zhipu", "--confirm-cost", "--with-embedding"]
    )

    assert result == 0
    assert len(embedding_calls) == 1
    assert "Embedding dimensions: 3" in capsys.readouterr().out


def test_unexpected_provider_error_is_not_rendered(monkeypatch):
    secret_like_detail = "sk-" + "x" * 40

    class _FailingChatModel:
        def invoke(self, _prompt):
            raise RuntimeError(secret_like_detail)

    monkeypatch.setattr(smoke_llm, "get_chat_model", lambda _label: _FailingChatModel())

    with pytest.raises(SystemExit) as exc_info:
        smoke_llm.main(["--provider", "deepseek", "--confirm-cost"])

    rendered_error = str(exc_info.value)
    assert "unexpected provider error" in rendered_error
    assert secret_like_detail not in rendered_error


def test_readme_documents_only_explicit_paid_smoke_commands():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    for provider in ("zhipu", "alibaba", "deepseek", "moonshot"):
        assert (
            f"smoke_llm.py --provider {provider} --confirm-cost" in readme
        )
    assert "--provider zhipu --confirm-cost --with-embedding" in readme
    assert not re.search(r"^python .*smoke_llm\.py\s*$", readme, flags=re.MULTILINE)
