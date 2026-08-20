# EzllmTest Local Reproduction Implementation Plan

> **For agentic workers:** Implement the tasks in order and verify each subsystem before continuing.

**Goal:** Reproduce EzllmTest locally on Windows with Vue 3, FastAPI, MySQL 8.4, GLM-4.7, and embedding-3.

**Architecture:** The frontend runs on port 8080 and calls FastAPI on port 8130. FastAPI reads local configuration from an untracked `.env`, stores project data in MySQL, and accesses Zhipu through its OpenAI-compatible endpoint.

**Tech Stack:** Python 3.11, Conda, FastAPI, SQLAlchemy, LangChain 0.2, Vue 3, MySQL 8.4.

## Global Constraints

- Environment creation, dependency installation, and database import are performed manually by the user.
- Only GLM-4.7 and embedding-3 are supported in this reproduction.
- Secrets must never be committed; LangSmith tracing remains disabled by default.
- Import all sample rows from `ezllmtest.sql` into `ezllmtest_dev`.

## Tasks

- [ ] Add environment-based backend/frontend configuration and a broadly constrained dependency list.
- [ ] Route chat and embedding calls through one Zhipu provider factory.
- [ ] Remove committed credentials and runtime LangChain Hub dependencies.
- [ ] Add health, configuration, provider, and database smoke tests.
- [ ] Update the Vue model selector and API base URL.
- [ ] Document manual Conda, pip, MySQL, startup, and verification commands.
