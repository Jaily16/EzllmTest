# Task 7 Runtime Verification and Final Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make paid smoke tests explicitly opt-in, document the modern four-provider setup, and deliver a requirement-by-requirement iteration audit.

**Architecture:** Convert the current implicit GLM/embedding script into an argument-driven CLI that selects exactly one chat provider and requires a separate cost-confirmation flag. Keep embeddings behind an additional Zhipu-only flag, test all gates without network access, and reuse the already authorized real-call evidence instead of making duplicate paid requests.

**Tech Stack:** Python 3.11, argparse, pytest, LangChain Core runnables, Markdown, Git safety scanner.

## Global Constraints

- Preserve all dirty worktree changes and the 50 authorized staged index-only deletions.
- Never print API keys, database passwords, `.env` content, raw provider exceptions, or credential fingerprints.
- Do not make new model/embedding calls; record the already completed user-approved smoke results.
- Do not connect to MySQL, install dependencies, start services, commit, or push.
- Keep public API model labels unchanged even though the frontend displays concrete model IDs.

---

### Task 1: Add offline tests for an explicit paid-smoke CLI

**Files:**
- Create: `ez_back_dev/tests/test_smoke_llm.py`
- Modify: `ez_back_dev/scripts/smoke_llm.py`

**Interfaces:**
- Consumes: registry providers `zhipu`, `alibaba`, `deepseek`, and `moonshot` and `get_chat_model(label)`.
- Produces: `main(argv: list[str] | None = None) -> int` requiring `--provider` and `--confirm-cost`; optional `--with-embedding` is valid only with `zhipu`.

- [x] **Step 1: Write failing CLI tests**

```python
def test_cost_confirmation_is_required_before_factory_call(monkeypatch):
    called = False
    monkeypatch.setattr(smoke_llm, "get_chat_model", lambda _label: called)
    with pytest.raises(SystemExit, match="--confirm-cost"):
        smoke_llm.main(["--provider", "deepseek"])
    assert called is False


def test_selected_provider_invokes_only_its_public_label(monkeypatch, capsys):
    selected = []
    monkeypatch.setattr(
        smoke_llm,
        "get_chat_model",
        lambda label: _FakeRunnable(selected, label),
    )
    assert smoke_llm.main(["--provider", "deepseek", "--confirm-cost"]) == 0
    assert selected == ["DeepSeek"]
    assert "SMOKE_OK" in capsys.readouterr().out
```

- [x] **Step 2: Run focused tests and confirm failure**

Run: `python -W error::DeprecationWarning -m pytest tests/test_smoke_llm.py -q`

Expected: import/signature failures because the old script has no argument-driven CLI.

- [x] **Step 3: Implement the minimal safe CLI**

Use `argparse` choices for the four provider slugs, refuse execution without `--confirm-cost`, route one safe fixed prompt through the selected public label, truncate displayed response content, and catch unexpected exceptions without rendering raw SDK details. Execute Zhipu `embedding-3` only when `--with-embedding` is supplied.

- [x] **Step 4: Run focused and complete backend tests**

Run: `python -W error::DeprecationWarning -m pytest tests/test_smoke_llm.py -q`

Run: `python -W error::DeprecationWarning -m pytest tests -q`

Expected: all tests pass without network access.

### Task 2: Update README setup and migration guidance

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `.env.example`, `requirements.txt`, provider registry, Task 5 scanner, and Task 6 validation commands.
- Produces: Current Python/LangChain baseline, four-provider environment table, Moonshot `.ai`/`.cn` endpoint pairing, explicit smoke commands, credential scanning, and known limitations.

- [x] **Step 1: Replace stale dependency and provider instructions**

Document exact pinned modern versions, four chat provider labels/model IDs, Zhipu-only embeddings, and the rule that keys stay only in root `.env`.

- [x] **Step 2: Add explicit paid smoke commands**

```powershell
python .\scripts\smoke_llm.py --provider zhipu --confirm-cost
python .\scripts\smoke_llm.py --provider alibaba --confirm-cost
python .\scripts\smoke_llm.py --provider deepseek --confirm-cost
python .\scripts\smoke_llm.py --provider moonshot --confirm-cost
python .\scripts\smoke_llm.py --provider zhipu --confirm-cost --with-embedding
```

- [x] **Step 3: Add migration, safety, and limitation notes**

Explain LangChain 1.x/Pydantic 2/SQLAlchemy 2 migration, current `.env` region override, offline test and credential scan commands, existing frontend warning baseline, provider-level versus business-endpoint real verification, and historical-key rotation.

### Task 3: Perform and record the final requirement audit

**Files:**
- Modify: `docs/iteration-1-tasks.md`
- Modify: `docs/iteration-development-log.md`

**Interfaces:**
- Consumes: Task 1–6 logs, `72 passed`, frontend lint/build, scanner result, and already completed real provider responses.
- Produces: Completed Task 7 checklist with traceable evidence, paid-test outcomes, known limitations, and next steps.

- [x] **Step 1: Record existing paid verification without re-running it**

Record successful GLM-4.7/embedding-3 reproduction plus `QWEN_OK` (83 total tokens), `DEEPSEEK_OK` (115 total tokens), and `MOONSHOT_OK` (300 total tokens). Record the initial Moonshot `.ai` 401 and successful `.cn` correction without including keys.

- [x] **Step 2: Map every iteration requirement to file/test evidence**

Cover modern dependencies, four-provider registry, LCEL/Pydantic/retrieval migration, API/database compatibility, frontend selectors, credential safety, and offline verification.

- [x] **Step 3: State known limitations and user-only next steps**

State that real provider factory calls do not prove every FastAPI business endpoint, only Zhipu provides embeddings, live MySQL verification was not executed during Task 6, frontend warnings remain, Git history is not rewritten, and staged generated-file deletions remain uncommitted.

- [x] **Step 4: Re-run offline final gates**

Run the full backend suite, credential scanner, generated-file count check, and README/smoke-script syntax checks. Do not run the paid CLI.

- [x] **Step 5: Do not commit**

Leave all iteration work in the user-owned worktree for review.
