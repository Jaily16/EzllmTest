# Aspect 4 后端领域迁移映射

> [Verified] 历史资料：本文记录 Iteration 5 的迁移证据。机器 fixture 与 checker 已从当前 V6 树移除，以下两个来源固定指向不可变 V5 快照，不是当前可执行验证入口。

本文是 Iteration 5 Aspect 4 的结构证据，不是新的运行时配置，也不替代
[`iteration5_backend_architecture_baseline_v1.json`](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/current/iteration5/iteration5_backend_architecture_baseline_v1.json)
或
[`iteration5_backend_migration_v1.json`](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/current/iteration5/iteration5_backend_migration_v1.json)。
机器可读 fixture 保存完整路径映射、每批 pre/post normalized SHA-256 和人工审查状态；
`scripts/check_backend_boundaries.py` 在离线检查时重新验证它们。

## Verified：迁移前的职责事实

迁移前的 `ez_back_dev/app` 同时承担 delivery、legacy 路由、Agent API、MCP 和质量 CLI；
平面 `service` 同时承载 Agent runtime、workflow、project lifecycle、RAG、Eval、telemetry、
worker 和 legacy workflow；`llm`、`dao`、`vectorstore`、`tools` 又分别暴露旧的公共 import path。
这些路径已经被测试、脚本、Docker/Compose、CI 或运行入口使用，不能仅因命名旧而删除。

迁移后，`app` 和 `serve.py` 仍是 delivery façade；真实实现按职责位于以下包：

| Canonical 包 | 职责边界 |
| --- | --- |
| `infrastructure` | 配置、运行时 hook、LLM gateway/stream/legacy model、MySQL repository、artifact repository、telemetry/logging |
| `service.agent` | Agent contract、planner、graph、runtime、checkpoint、lease/coordinator、budget、tool registry/executor、workbench、worker、MCP adapter |
| `service.workflow` | 19 项 workflow catalog、stream、test plan、预算、artifact orchestration、long-text 和 unit reference |
| `service.project` | 项目文档/文件、revision、setup、workflow status、test evidence |
| `service.retrieval` | retrieval evidence contract、session、index、loader、splitter、retriever factory；不依赖 Agent runtime |
| `service.evaluation` | Eval、Acceptance、Benchmark、评分、测量和 RAG benchmark |
| `service.legacy` | 旧的 acceptance/api/database/functional/integration/nonfunctional/summarize/unit/UI workflow 实现 |
| `model`、`prompt`、`chain`、`tools.InfoType`、`tools.status` | 保留的 shared model/resource 或稳定枚举 |

## Proposed：静态依赖方向

```text
app / serve
    ↓
service.agent / workflow / project / legacy / evaluation
    ↓
service.retrieval
    ↓
infrastructure.llm / persistence / observability / config

model / prompt / chain / stable enums
    ↑
infrastructure adapters
```

实际静态规则由 checker 执行：

- `infrastructure.*` 不导入 `app` 或 `service.*`；它只使用 stable model/resource、配置和外部库。
- `service.retrieval.*` 不导入 `service.agent.*`；trusted scope 通过
  `TrustedProjectScopeLike` protocol 传入，Agent 的具体认证模型仍由 Agent 层拥有。
- `service.workflow.*` 不导入 Agent runtime；workflow 只调用 project、retrieval 和 infrastructure。
- `service.project.*` 不导入 delivery；project 的数据库职责留在 persistence adapter。
- `service.evaluation.*` 可以调用被测 Agent/workflow/project，但 app 只保留 CLI façade。
- compatibility façade 只能转发到 canonical module，不包含业务 class/function、数据库操作、provider 调用或重复序列化逻辑。

`service.retrieval.factory` 仍使用 `service.project.documents` 的既有 token/document helper；这是已审计的
utility edge，不允许它反向依赖 Agent。artifact DAO 与 artifact service 的拒绝键和 stale 语义尚未被
characterization 证明为同一集合，因此只保留各自策略，没有强行合并。

## Verified：old-to-new import map

完整逐模块映射在 architecture fixture 的 `module_map` 中。主要分组如下：

| 旧路径组 | Canonical 目标 |
| --- | --- |
| `app.config`、`llm.provider`、`llm.streaming` | `infrastructure.config`、`infrastructure.llm.gateway`、`infrastructure.llm.stream` |
| `llm.llm_*`、`tools.llmTools` | `infrastructure.llm.legacy_models`、`infrastructure.llm.selection` |
| `dao.testProjectDao`、`dao.workflowArtifactDao` | `infrastructure.persistence.project_repository`、`infrastructure.persistence.artifact_repository` |
| `service.agentContracts`、`agentRuntimeContracts`、`agentBudgetLedger`、`agentRedisCoordinator`、`agentTelemetry` | Agent contract/budget/coordinator 和 infrastructure observability canonical module |
| `service.agent*` runtime/tool/workbench/worker modules | `service.agent.*` |
| `service.agentRetrieval`、`vectorstore.*` | `service.retrieval.*` |
| `service.project*Service`、`tools.documentTools`、`tools.fileTools` | `service.project.*` |
| `service.workflow*`、`llmWorkflow*`、`llmTestPlan*`、`longTextPolicy`、`unitReferenceService` | `service.workflow.*` |
| `service.agent*Eval*`、`agentMeasurement`、`agentRag*` | `service.evaluation.*` |
| `legacyLongTextService`、`llm*TestService` | `service.legacy.*` |

旧路径全部保留为显式兼容 façade。`app.routers` 仍导出
`projectSetupService`、`projectWorkflowStatusService`、`stream_test_plan`、
`stream_llm_workflow` 和 legacy operation function 名称，避免测试与外部调用者丢失模块级符号。

## Protected：入口与公共契约

以下入口没有改名：

- `app.main:app`
- `app.agentApi:app`
- `app.agentWorker`
- `app.mcpServer`
- `app.agentEval`
- `app.agentAcceptance`
- `app.agentBenchmark`
- `serve.py`

迁移不改变 19 个 workflow 的 catalog 顺序、operation、prerequisite、persistence、prompt version
或 budget；不改变 22 个工具的 schema、risk、approval、scope、idempotency、cancel 或 retention。
legacy REST/SSE、Agent REST/SSE、MCP URI/schema、artifact/revision/cache/RAG、严格 JSON checkpoint、
HITL、lease、recovery、MySQL/Redis 数据职责和页面零隐式付费调用均由历史 fixture 与现有 contract
test 继续保护。

`AGENT_GRAPH_VERSION`、`MCP_SERVER_VERSION`、`TELEMETRY_SCHEMA_VERSION`、
`AGENT_RAG_POLICY_VERSION` 等协议/数据版本字符串没有因目录重组改名。

## Verified：动态加载与交叉引用

checker 使用 AST 审计静态 import、相对 import、`importlib.import_module`、`__import__`、pytest
monkeypatch/fixture 字符串，并检查 Dockerfile `COPY`/入口、Compose command、GitHub Actions、
`serve.py`、`python -m`、`uvicorn` module string 以及仓库文档命令。当前未解析的动态 import 为零。
已登记的显式边界例外仅包括：

- `service.evaluation.acceptance_runner:app.main` 的 integration probe；
- `service.evaluation.eval_runner:app.main` 与 `service.evaluation.eval_runner:app.mcpServer` 的离线 probe；
- `app.agentApi:dao.testProjectDao` 的兼容 probe；
- `uvicorn:app.main:app`、`uvicorn:app.agentApi:app`、`uvicorn:app.mcpServer:create_loopback_app` 的运行字符串。

跨仓库外部消费者无法由本仓库证明，所以旧 façade 不在本 Aspect 删除。新的引用、未知动态加载、
路径越界或用户修改都必须升级为人工审查项，不能通过扩大 ignore 解决。

另有一个历史静态符号缺口：`ez_back_dev/test/llmtest.py` 与 `test/daotest.py` 引用了
`dao.testProjectDao.find_project_testdoc_list`，但该函数在迁移前的 HEAD 实现中就不存在。
这两个旧测试根文件不属于当前 pytest collection；本 Aspect 不凭空补造其行为，也不删除它们，
将其保留为 `Unknown`/历史引用，等待单独的 owner 与 characterization 证据。

## Verified：迁移批次证据

当前 migration fixture 的批次为：

1. `infrastructure`：config、LLM、persistence、observability、Agent contracts/budget/coordinator；
2. `retrieval-project-workflow`：retrieval、project、workflow 及 document/file 入口；
3. `agent-evaluation-legacy`：Agent runtime、evaluation、legacy 和 provider wrapper；
4. `delivery-facade-and-audit`：app/serve/script delivery façade、active contract test/document
   边界更新与 style checker 的 canonical import 更新。

每批都设置 `manual_reviewed=true`、明确 source/canonical path 数组、pre/post normalized SHA-256 和 review
说明；新增的 package/checker/test 文件使用 `new_path_post_change_sha256` 记录。父 fixture 是
`iteration5_backend_architecture_baseline_v1.json`，`auto_accept_current_values=false`。

## Protected：删除与回滚边界

`removed_paths` 当前为空。兼容 façade 的保留不是“暂时忽略”，而是基于测试、脚本、文档、CI、
Docker/Compose、CLI 和潜在外部消费者不可完全证明而作出的保护决策。删除 shim 需要另一个人工审查
记录，至少证明静态/动态 import、路由、pytest collection、文档链接、Docker/Compose/Actions、CLI
module string 和运行时 smoke 均无引用。

每批修改前的普通文件已备份到仓库外 task-owned 目录并记录 hash。回滚只在当前文件 hash 仍等于
该批 post-change hash 时恢复；若用户修改了同一路径则停止并保留。新增文件只有路径和 post hash
同时匹配时才可移除。不得使用 Git destructive command，也不得删除 `.env`、上传目录、数据库/Redis/
观测数据、普通 Compose volume 或用户文件。

## Missing：当前验证限制

宿主缺少部分 Python runtime package 时，完整 pytest 和 Agent Eval/Acceptance/Benchmark 只能报告
blocked，不能伪称运行通过；这不改变静态迁移证据。Aspect 2 的 Linux pip-tools resolver spike
继续作为既有限制，不在 Aspect 4 处理。旧 shim 的外部消费者、运行中 provider/数据库/Redis 数据和
真实项目内容也不由本仓库静态审计读取；它们因此继续 Protected。
