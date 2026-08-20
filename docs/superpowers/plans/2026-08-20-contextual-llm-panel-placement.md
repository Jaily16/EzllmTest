# Contextual LLM Panel Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render each streamed LLM execution panel directly beneath the button that started that specific analysis or case-generation operation.

**Architecture:** Keep the existing single `useLlmWorkflow` stream state per test page. Use its existing `activeOperation` ref with simple Vue `v-if` conditions to mount `LlmWorkflowExecution` at the active operation's action location, ensuring only one panel exists at a time and preserving cancellation, progress, reasoning, answer streaming, usage, and result handling.

**Tech Stack:** Vue 3 `<script setup>`, TypeScript, Element Plus, existing SSE composables, pytest frontend source contracts, Vue CLI lint/build.

## Global Constraints

- Do not change the SSE protocol, backend routes, database behavior, model configuration, or paid model usage.
- Preserve all existing user-owned working-tree changes.
- Do not duplicate stream state or render more than one execution panel at a time.
- Keep the test-plan page unchanged because it has one primary LLM action and its panel is already contextual.

---

### Task 1: Add contextual-placement contracts

**Files:**
- Modify: `ez_back_dev/tests/test_frontend_contracts.py`

**Interfaces:**
- Consumes: `activeOperation` returned by `useLlmWorkflow`.
- Produces: source-level regression checks for operation-specific `v-if` panel placement.

- [ ] **Step 1: Write the failing test**

Add a parametrized assertion that each of the eight test components contains one `LlmWorkflowExecution` condition per workflow operation and does not contain an unconditional top-level panel.

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests/test_frontend_contracts.py -q`

Expected: FAIL because the current panels are unconditionally rendered near the page top.

### Task 2: Move simple two-step page panels

**Files:**
- Modify: `ez_front_dev/src/components/ApiTest.vue`
- Modify: `ez_front_dev/src/components/UITest.vue`
- Modify: `ez_front_dev/src/components/DatabaseTest.vue`
- Modify: `ez_front_dev/src/components/FounctionalTest.vue`
- Modify: `ez_front_dev/src/components/NonfunctionalTest.vue`
- Modify: `ez_front_dev/src/components/AcceptanceTest.vue`

**Interfaces:**
- Consumes: `activeOperation`, `executionProps`, and `cancel` from `useLlmWorkflow`.
- Produces: analysis panel below the analysis button and case panel below the case-generation button.

- [ ] **Step 1: Destructure `activeOperation` from the composable**

Use the existing return value without adding new composable state.

- [ ] **Step 2: Place operation-conditional panels**

For each page, add `v-if="activeOperation === '<operation>'"` immediately after its corresponding button row and remove the unconditional top panel.

- [ ] **Step 3: Run the placement contract and lint**

Run the frontend-contract pytest target and `npm run lint`.

### Task 3: Move multi-step unit and integration panels

**Files:**
- Modify: `ez_front_dev/src/components/UnitTest.vue`
- Modify: `ez_front_dev/src/components/IntegrationTest.vue`

**Interfaces:**
- Produces: three operation-specific panel locations on each page: menu analysis, object/unit analysis, and test-case generation.

- [ ] **Step 1: Place the unit-test panels**

Map `unit_menu`, `unit_info`, and `unit_case` to their respective action rows.

- [ ] **Step 2: Place the integration-test panels**

Map `integration_menu`, `integration_info`, and `integration_case` to their respective action rows.

- [ ] **Step 3: Verify only the active panel mounts**

Use mutually exclusive equality checks against `activeOperation`; do not copy or instantiate a second composable.

### Task 4: Full verification

**Files:**
- Test: `ez_back_dev/tests/test_frontend_contracts.py`
- Test: all touched Vue components

- [ ] **Step 1: Run frontend contracts**

Run: `D:\tool\anaconda3\envs\ezllmtest\python.exe -m pytest tests/test_frontend_contracts.py -q`

- [ ] **Step 2: Run lint**

Run: `npm run lint`

- [ ] **Step 3: Run production build**

Run: `npm run build`

- [ ] **Step 4: Run static placement audit**

Confirm each target operation has exactly one conditional panel and no unconditional `LlmWorkflowExecution` remains.
