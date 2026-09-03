# EzllmTest Iteration 3 Frontend Experience Roadmap

> **For agentic workers:** This document is an aspect-level roadmap, not an implementation task list. Work on exactly one aspect at a time. Start each aspect with a dedicated planning pass, obtain user approval for that plan, then implement and verify only that aspect before moving on.

**Goal:** Turn EzllmTest into a coherent, modern, responsive, and approachable AI testing workspace while preserving the workflow correctness, caching behavior, API compatibility, and cost controls established in Iterations 1 and 2.

**Architecture:** Keep Vue 3, TypeScript, Vue Router, Axios, and Element Plus as the frontend foundation. Establish a small design system and shared interaction patterns first, then improve the application shell and each stage of the real user journey in dependency order; backend changes are outside the default scope and require a separately justified plan.

**Tech Stack:** Vue 3.2 Composition API, TypeScript 4.5, Vue Router 4, Element Plus 2.7, Axios, Vue CLI 5, Python/FastAPI contract tests, ESLint, browser-based visual verification.

## Global Constraints

- This is a frontend-first iteration. Do not change backend REST/SSE behavior, database schema, workflow catalog, prompts, model routing, retrieval, persistence, or Token budgets unless a frontend requirement is proven impossible without a backend change and the user separately approves it.
- Preserve all public routes, request fields, stable model labels, response envelopes, SSE event names, cancellation behavior, delayed saving, artifact recovery, stale-revision rules, and route guards.
- Preserve the product decision that every preliminary analysis is persisted; `unit_case`, `integration_case`, `api_case`, `functional_case`, and `nonfunctional_case` are current-page session-only results; `ui_case`, `db_case`, and `acceptance_case` remain persisted.
- During project-analysis regeneration, the test menu and all individual test routes must remain unavailable until the new plan/menu is ready. Once enabled, individual test entries use `可进入`, not a false whole-test-type `已完成` state.
- Do not trigger real chat or embedding calls, connect to MySQL, read a real `.env`, expose reasoning or credentials, or install/upgrade dependencies without explicit approval for that action.
- Treat every dirty-worktree file as user-owned. Do not overwrite, discard, reset, stage, commit, pull, or push unless the user explicitly requests it.
- Keep Chinese as the primary product language. UI copy must distinguish `当前`, `可进入`, `已锁定`, `进行中`, `已完成`, `已过期`, `失败`, `已取消`, `已从缓存恢复`, `已保存`, and `仅当前页面保留` consistently.
- Target usable layouts from 360 px mobile width through 1920 px desktop width. Normal page interaction must not require horizontal scrolling.
- Aim for WCAG 2.1 AA contrast, full keyboard operation for primary flows, visible focus, semantic labels, reduced-motion support, and error messages that explain recovery actions.
- Prefer CSS variables, Element Plus theme variables, and focused shared components over scattered inline styles. Do not replace the framework or add a large design dependency merely for appearance.
- Every aspect must finish with focused regression checks, `npm run lint`, `npm run build`, and browser screenshots at agreed viewports. Run backend tests only when frontend contracts or shared repository checks are affected.

---

## 1. Current product baseline

Iteration 2 is complete on `main`. The platform currently supports this real journey:

`登录或创建项目 → 上传知识库/需求/设计文档 → 确认资料 → 项目分析/测试计划 → 测试菜单 → 进入已启用测试类型 → 分析测试对象 → 生成或恢复结果`

The backend exposes one project-analysis stream plus 18 generic workflow operations. It supports progress, current-session reasoning, streamed answers, Token usage, cancellation, delayed persistence, revision-aware recovery, and retrieval-index reuse. The repository schema contains seven empty table definitions in `ezllmtest.sql` and no sample data.

The frontend already has useful behavioral foundations:

- `projectAnalysis.ts` and the router guard coordinate lifecycle access.
- `projectSetup.ts` restores project-creation/upload progress.
- `useLlmStream.ts`, `useLlmWorkflow.ts`, and `useTestWorkflow.ts` centralize streaming and step state.
- `WorkflowStepper.vue`, `LlmExecutionPanel.vue`, and `LlmWorkflowExecution.vue` provide reusable workflow feedback.
- `MainView.vue`, `TestPlan.vue`, `TestMenu.vue`, and eight test pages expose the completed workflow.

The static takeover should verify, rather than blindly assume, the following visible debt signals:

- visual tokens, typography, spacing, color, and status presentation are scattered across component-scoped and inline styles;
- fixed widths, absolute positioning, a fixed 280 px sidebar, an 800 px menu row, a 620 px unit selector, and limited media queries can cause narrow-screen overflow;
- project context and lifecycle status compete with a dense sidebar instead of forming a clear workspace hierarchy;
- repeated test-page layouts and control styles can drift even though their workflow behavior is shared;
- generated content is often displayed as a large textarea, while progress, reasoning, usage, persistence, errors, and results need clearer progressive disclosure;
- accessibility coverage is partial, and the repository currently has no dedicated frontend component or end-to-end test runner.

## 2. Product and visual direction

The recommended direction is a professional AI quality-engineering workspace: calm, precise, trustworthy, and information-dense without feeling crowded. Keep the existing green brand cue as a restrained accent rather than a full-page wash; use neutral surfaces, clear elevation, readable Chinese typography, consistent semantic colors, and motion only when it explains state change.

The interface should answer four questions without forcing the user to infer them:

1. Which project am I working on?
2. Where am I in the overall testing journey?
3. What can I do now, and what is blocked?
4. Is the visible result running, cached, saved, stale, cancelled, failed, or session-only?

## 3. Ordered implementation aspects

These are deliberately aspects, not Tasks. A new detailed plan is created only when the user starts that aspect.

### Aspect 1 — Experience baseline and design-system foundation

Establish the visual and interaction rules that every later aspect consumes. Produce a page/state inventory, viewport screenshot baseline, UI-debt map, design tokens, typography hierarchy, spacing/radius/shadow scale, semantic status palette, focus rules, content-width rules, and Element Plus theme strategy. Decide where global styles live and how shared primitives are named. Use one low-risk pilot surface to verify the foundation without redesigning the whole product.

Exit condition: the approved design direction is documented, reusable tokens exist, the pilot proves desktop and mobile behavior, and no workflow/API behavior changes.

### Aspect 2 — Information architecture and responsive application shell

Rework the persistent workspace frame: header, project identity, lifecycle summary, sidebar/drawer behavior, primary navigation, current-route indication, locked/stale/regenerating states, content container, and mobile navigation. Make the product journey visible without duplicating or contradicting backend-derived status.

Exit condition: all existing routes remain compatible; desktop, tablet, and mobile navigation are usable; project-analysis regeneration still locks downstream routes; and no normal viewport has horizontal overflow.

### Aspect 3 — Shared interaction and feedback components

Standardize page headers, section cards, field groups, model selectors, primary/secondary/destructive buttons, empty/loading/error states, workflow stepper states, confirmation patterns, and result containers. Redesign LLM feedback primitives so progress, model identity, cancellation, reasoning, Token usage, cache/persistence state, and partial output form one understandable hierarchy. Reasoning remains current-session-only and uses progressive disclosure.

Exit condition: shared components have explicit contracts and are demonstrated on representative states without changing dispatch, SSE, persistence, or retry semantics.

### Aspect 4 — Entry, project recovery, creation, and document onboarding

Improve `LoginView` and `CreateView` as one coherent onboarding journey. Clarify the difference between opening an existing project and creating a new one; improve document-category guidance, validation, upload progress, partial recovery, retry, confirmation, project-ID copy/save guidance, and safe escape paths. Never hide which document group failed or which completed uploads will be reused.

Exit condition: a first-time user can create a project and a returning user can recover one without guessing; refresh/retry behavior remains compatible with `projectSetup.ts`; and destructive or paid actions are never triggered implicitly.

### Aspect 5 — Test-plan and test-menu workflow cockpit

Turn `TestPlan` and `TestMenu` into a clear planning workspace. Separate source summary, recommended plan, enabled test types, prerequisites, regeneration impact, stale state, and next actions. Make the menu a responsive dashboard that explains why each test type is available or unavailable and routes users to a sensible next step.

Exit condition: plan generation/regeneration is unambiguous; downstream locking is visible immediately; menu cards consistently say `可进入` once unlocked; and recommendations do not masquerade as completion.

### Aspect 6 — Eight test-type workspaces

Apply one coherent page anatomy across unit, integration, API, UI, database, functional, nonfunctional, and acceptance testing while retaining their real differences. Standardize stage placement, qualified target labels, selectors, model choice, action order, stale/reset behavior, restored content, final results, and responsive layouts. Do not flatten distinct workflows into misleading generic controls.

Exit condition: all eight pages share predictable navigation and state language; duplicate names remain distinguishable through qualified references; analysis resume avoids unnecessary calls; and session-only versus persisted final results are visibly explained.

### Aspect 7 — Accessibility, responsiveness, perceived performance, and content quality

Run a cross-product hardening pass for keyboard order, focus restoration, accessible names, contrast, zoom, reduced motion, screen-reader status announcements, mobile touch targets, long Chinese/English text, empty/slow/error states, skeletons, layout stability, fonts, images, and bundle warnings. Improve perceived performance without hiding actual model latency or fabricating progress.

Exit condition: agreed accessibility checks pass, the key journey works at 360/768/1024/1440/1920 widths, no critical content is clipped, and asset/bundle decisions are measured rather than aesthetic guesses.

### Aspect 8 — Integrated UX acceptance and Iteration 3 closeout

Validate the complete journey against a state matrix: new project, returning project, partial upload, analysis required, analysis running, ready menu, each enabled test page, cached recovery, stale revision, regeneration, cancellation, structured-output error, persistence error, and session-only result. Resolve cross-page inconsistencies, update documentation, record known limits, and prepare a closeout report.

Exit condition: lint/build and approved offline tests pass; browser evidence covers the key viewports and states; credential/generated-asset checks are clean; no provider or database cost is incurred; and release/commit/push happens only after a separate explicit instruction.

## 4. Dependency order

```text
Aspect 1: foundation
    ↓
Aspect 2: shell and information architecture
    ↓
Aspect 3: shared interaction and feedback
    ↓
Aspect 4: entry and project onboarding
    ↓
Aspect 5: plan and menu cockpit
    ↓
Aspect 6: eight test workspaces
    ↓
Aspect 7: cross-product hardening
    ↓
Aspect 8: integrated acceptance and closeout
```

An aspect may expose a prerequisite defect in an earlier aspect. Fix that prerequisite inside the earlier aspect's boundary or pause for user approval; do not silently redesign later areas in advance.

## 5. Planning contract for each new aspect

When an aspect begins, its planning conversation must:

1. re-check Git status and treat existing changes as user assets;
2. inspect the relevant current components, state, routes, and frontend contracts;
3. capture or describe the current visible states before proposing changes;
4. define exact in-scope and out-of-scope files and behaviors;
5. specify test-first contracts and browser verification viewports;
6. identify whether a dependency addition or backend change is truly necessary;
7. present the detailed implementation plan for approval before editing;
8. implement only the approved aspect and update the Iteration 3 development log;
9. stop before the next aspect.

## 6. Iteration-level success criteria

- The primary journey is understandable without prior platform knowledge.
- Visual hierarchy and interaction semantics are consistent across every route.
- The UI remains faithful to backend lifecycle truth and never implies false completion.
- Long-running AI work clearly communicates progress, cost information, cancellation, recovery, and persistence state.
- Desktop and mobile layouts are deliberate, not merely compressed versions of a fixed desktop page.
- Accessibility and error recovery are part of the design, not a final cosmetic patch.
- Existing Iteration 2 workflow, cache, database, and cost behavior remains compatible.
- No real provider, embedding, or MySQL access occurs unless separately and explicitly authorized.
