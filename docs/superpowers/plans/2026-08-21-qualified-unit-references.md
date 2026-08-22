# Qualified Unit References Implementation Plan

> **For agentic workers:** Implement inline with tests first. Do not commit or push; preserve the shared dirty worktree.

**Goal:** Make same-named subsystems, modules, classes, functions, and methods independently selectable, retrievable, cached, restored, and displayed without breaking legacy unit-menu responses.

**Architecture:** The model-facing schema extracts `display_name`, `qualified_name`, and `source_hint`; a focused backend adapter converts those objects to canonical strings while preserving the existing string-list REST/SSE result shape. Vue derives typed select options from canonical or legacy strings, sends both `unit` and `unit_type`, and existing artifact selection hashing distinguishes each qualified target.

**Tech Stack:** Python 3.11, Pydantic 2, FastAPI workflow services, Vue 3 Composition API, TypeScript 4.5, Element Plus, pytest contract tests.

## Global Constraints

- Keep existing REST/SSE event names and the four unit-menu string-list fields compatible.
- Accept old plain-string unit menus and old callers that omit `unit_type`.
- Do not access real models, embeddings, MySQL, or external network during verification.
- Do not install dependencies, stage, commit, push, or overwrite unrelated dirty-worktree assets.

---

### Task 1: Qualified reference model and codec

**Files:**
- Modify: `ez_back_dev/model/ChainJsonModel.py`
- Create: `ez_back_dev/service/unitReferenceService.py`
- Create: `ez_back_dev/tests/test_unit_reference_service.py`

**Interfaces:**
- Produces `QualifiedUnitReference`, `QualifiedUnitTestMenu` and `encode_unit_menu(...) -> UnitTestMenu`.
- Produces `parse_unit_reference(value, unit_type) -> UnitReferenceTarget` for retrieval and prompt labels.

- [ ] Add failing tests proving two `create` functions with different qualified names remain different canonical values, exact duplicates are removed, and legacy strings remain readable.
- [ ] Run `pytest tests/test_unit_reference_service.py -q` and confirm missing interfaces fail.
- [ ] Implement a delimiter-based canonical codec containing display name, qualified name, and non-content source hint; sanitize empty values and delimiters.
- [ ] Re-run the focused tests.

### Task 2: Model extraction, retrieval, and cache identity

**Files:**
- Modify: `ez_back_dev/prompt/promptStr.py`
- Modify: `ez_back_dev/service/llmWorkflowAnalysisStreamService.py`
- Modify: `ez_back_dev/service/llmWorkflowCaseStreamService.py`
- Modify: `ez_back_dev/service/llmUnitTestService.py`
- Modify: `ez_back_dev/service/workflowCatalog.py`
- Modify: `ez_back_dev/tests/test_llm_workflow_analysis_stream.py`
- Modify: `ez_back_dev/tests/test_workflow_catalog.py`

**Interfaces:**
- `unit_menu` still returns `subsystem_list/module_list/class_list/function_list: string[]`.
- `unit_info` and `unit_case` accept optional `unit_type`; new clients always send it.

- [ ] Add failing tests for distinct qualified menu values, qualified retrieval queries, and `unit_type` selection fields.
- [ ] Change the structured model prompt to require hierarchy/package/module/class/signature and a source locator instead of bare names.
- [ ] Encode the structured menu before SSE/artifact persistence; switch legacy menu extraction through the same adapter.
- [ ] Parse the selected reference for retrieval and prompts, and bump `unit_menu`/`unit_info` prompt versions so old ambiguous artifacts are not reused as current output.
- [ ] Re-run focused workflow and catalog tests.

### Task 3: Typed Vue selection and restoration

**Files:**
- Modify: `ez_front_dev/src/components/UnitTest.vue`
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Produces `UnitOption { value, label }`; `value` is the canonical backend reference and `label` visibly contains the qualifier/source.
- Sends `{ unit, unit_type }` for unit analysis and case generation.

- [ ] Add a failing frontend contract requiring typed options, unique values, `unit_type` payloads, and old-selection fallback.
- [ ] Replace direct string options with a computed, deduplicated `UnitOption[]`; preserve `v-model` as the canonical string.
- [ ] Restore `unit_type` directly from new saved selections, falling back to legacy list membership for old sessions.
- [ ] Run frontend contracts, lint, and production build.

### Task 4: Full offline verification and documentation

**Files:**
- Modify: `docs/iteration-2-development-log.md`

- [ ] Run the complete backend test suite with mock providers/in-memory SQLite.
- [ ] Run `git diff --check` and inspect `git status --short` without staging.
- [ ] Record compatibility behavior, test results, and the no-network/no-database boundary.
