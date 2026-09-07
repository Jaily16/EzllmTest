# Iteration 6 收口报告

- 收口日期：2026-09-07（Asia/Shanghai）
- 不可变 V5 来源：`5cf1effb32a8efcd34902df05d27442f3586dc1c`
- 开发分支：`codex/iteration6`
- 本地开发 worktree：`D:\\codex\\EzllmTest_v6`

## 结论与证据边界

[Verified] Iteration 6 将 V5 的同一精确提交作为归档分支和 V6 开发基点，在保留公共产品能力的前提下完成目录收敛、三文件运行配置、Agent 模型与预算修复、本地中文观测后台，以及功能函数级中文注释。最终仓库树不包含本轮临时计划、提示词、开发日志或 Aspect 过程 closeout。

[Verified] V5 原始完整树仍可从[不可变提交](https://github.com/Jaily16/EzllmTest/tree/5cf1effb32a8efcd34902df05d27442f3586dc1c)和远程 `codex/iteration5-main-archive` 恢复。Iteration 6 没有删除、清空、回退或改写该归档。

[Protected] 三份真实 `.env`、`.env.aspect3.local`、上传项目、合成烟测项目、MySQL/Redis/SQLite 数据、日志、`node_modules`、`dist`、缓存和其他 ignored 用户资产均留在本机，不进入提交。本报告不记录其内容、值、哈希、大小、项目 ID、运行 ID或进程 ID。

[Missing] 本次收口不是生产容量、SLA、安全认证、客户项目质量或正式生产就绪证明；完整限制见[验证历史](validation-history.md)。

## 最终目录与运行架构

[Verified] 当前产品目录按职责分为：

- `backend`：legacy API、Agent API、worker、MCP、canonical domain、workflow、RAG、模型适配和持久化；
- `frontend`：Vue 3 / TypeScript / Vite 应用、Agent 工作台、中文观测页和八类测试生成页面；
- `observability`：本地观测说明、安全示例配置及 ignored SQLite 数据边界；
- `infrastructure`：七表 SQL 和五模块运行拓扑/前端公开配置适配；
- `docs`：长期产品、架构、运维、历史与验证证据。

[Verified] 当前本地运行入口为 [`scripts/modular_runtime.py`](../scripts/modular_runtime.py)，按 observability API、legacy API、Agent API、worker、frontend 的顺序启动，按相反顺序停止。HTTP 服务仅绑定 loopback 的 8140、8230、8231、8180；MySQL 与 Redis 是外部依赖，不归 runner 启停。安全运维协议见[分模块运行](operations/modular-runtime.md)。

[Verified] 运行配置只有三份显式来源：[`backend/.env.example`](../backend/.env.example) 对应 backend、[`frontend/.env.example`](../frontend/.env.example) 对应 frontend、[`observability/.env.example`](../observability/.env.example) 对应 observability。真实文件被忽略；缺失、重复、未知、跨模块或非法字段 fail closed，不搜索替代配置，也不修改 Windows 用户或系统环境变量。

## 公共产品契约

[Verified] [`workflow catalog`](../backend/service/workflow/catalog.py) 保留 19 个可恢复工作流；[`Agent tool registry`](../backend/service/agent/tool_registry.py) 保留 22 个类型化工具。项目作用域继续由可信宿主注入，模型调用、持久化与 regenerate 等高风险动作继续受人工审批约束。

[Verified] legacy REST/SSE、Agent REST/SSE 与 loopback MCP 入口保持存在：[`app.main`](../backend/app/main.py)、[`app.agentApi`](../backend/app/agentApi.py)、[`app.mcpServer`](../backend/app/mcpServer.py)。SSE 的增量、错误、取消与完整成功后保存边界保持；失败、截断或取消不会覆盖上一份有效结果。

[Verified] MySQL 继续作为项目、revision 和有效 artifact 的长期真源；Redis 继续承担 Agent checkpoint、队列、租约、幂等、取消与事件重放。[`schema.sql`](../infrastructure/database/schema.sql) 保留七张表并包含面向空库初始化的原始 `DROP TABLE IF EXISTS`，不得直接导入已有用户数据库。

[Verified] 页面首次进入只读取状态，不隐式调用 provider 或 embedding；五类 final 保持 session-only，UI、数据库与验收 final 保持 persisted artifact。reasoning 仅在获准的当前会话界面展示，不进入 checkpoint、持久化 artifact、观测日志或 Trace。

## Aspect 3–6 交付摘要

### Aspect 3：源码与产品边界

[Verified] 产品源码由旧 `ez_back_dev` / `ez_front_dev` 收敛为 `backend` / `frontend`，数据库结构进入 `infrastructure/database`。仓库自测、Eval/Acceptance/Benchmark 执行代码、CI、Docker/Compose 和外部观测交付设施从当前树排除；名称含 test、acceptance 或 test evidence 的产品测试生成功能保留。

[Verified] 文档上传路径、四家模型显式配置、项目分析错误分类、Kimi K3、DeepSeek 思考与输出上限、保存白名单，以及八类测试共享输出预算的定点修复均通过合成/静态门禁。RAG 默认聊天模型设置 300 秒最小 timeout，显式注入模型仍绕过 factory，provider 自动重试保持为零。

### Aspect 4：配置、模型绑定与预算

[Verified] backend、frontend、observability 三份配置按角色隔离；Vite 只公开 legacy API、Agent API、本地观测 API 三个 loopback URL。旧单文件参数仅保留为显式弃用兼容模式，不能与新模式混用或自动回退。

[Verified] Agent planner 与执行阶段逐次使用界面选择的同一模型，不接受提示词覆盖，不使用跨运行共享模型状态，也不静默回退 GLM。Planner 保持严格 JSON 和 4096 Token 上限。

[Verified] Agent 新运行总预算与单次 workflow 上限解耦：聚焦输入/输出默认 768000/393216，标准默认 2048000/1048576；步数、时间、模型/embedding/tool 调用次数未扩大。旧运行继续使用创建时持久化的 `RunBudget`，不重算 Redis 状态或审批绑定。

### Aspect 5：本地中文观测

[Verified] 独立 loopback 观测 API 使用 `iteration6-observability-v1`，将允许清单内的 Agent spans、metrics 和安全日志写入本地 SQLite。保留期为 7 天，总上限 100000 行，固定分配为 spans 50000、metric points 30000、logs 20000；清理 span 时按完整 Trace 删除。

[Verified] `/observability` 无需项目 ID，提供依赖健康、指标、p50/p95、Trace 层级、安全日志和容量状态。运行路径不再使用 OTLP Collector、Prometheus、Tempo、Grafana 或 LangChain/LangSmith 外部 tracing；现有 LangChain 产品工作流本身仍保留。

[Verified] exporter 与 ingestion 双重拒绝 prompt、completion、reasoning、项目/文件/工具正文、SQL、Redis 内容、header/cookie、异常正文、traceback、凭据和连接串。观测发送失败或队列满时丢弃观测副本，不阻断业务。

### Aspect 6：中文注释

[Verified] `backend` 的 163 个 Python 文件、902 个 `def/async def` 均具有中文 docstring；移除 docstring 与明确允许的 FastAPI 描述兼容参数后，实施前后 AST 零差异。62 个 FastAPI 路由的既有 OpenAPI 描述语义保持。

[Verified] `frontend/src` 的 56 个 TS/Vue 文件、561 个函数节点全部分类；461 个必须覆盖的功能单元具有中文 JSDoc，其余纯集合、纯转发或被外层功能单元覆盖的回调均有明确排除类别。忽略注释后的 TypeScript token 流以及 Vue template/style 保持不变。

## 验证结果

[Verified] Aspect 3–6 的离线与本地门禁覆盖 Python AST/内存编译、19 workflows、22 tools、FastAPI 路由、七表 SQL、配置隔离、模型绑定、预算/审批/持久化保护、本地观测 schema/API/SQLite/exporter、前端 type-check/ESLint/Prettier，以及输出到系统临时目录的 production build。最终构建转换 1198 个模块且未覆盖仓库 `dist`。

[Verified] 发布前当前五模块的身份、status、readiness 与四个 loopback 健康入口再次通过。该验证没有读取项目接口或观测数据内容，也没有触发 provider、embedding 或 Agent run。

[Verified] V2 的 tracked、untracked、ignored 与受保护类别在本轮前后 Git-visible 快照中保持一致。V6 最终候选不包含真实配置、上传目录、SQLite、日志、缓存、`node_modules` 或 `dist`。

## 2026-09-07 最小真实烟测

[Candidate] 在用户逐项授权下，使用一个不含客户内容的合成项目完成一次 GLM 项目分析：结果原子保存并可恢复，记录的输入 Token 为 1085、总 Token 为 4499。只保留这一脱敏结果摘要，不保留生成正文或项目标识。

[Candidate] 同一受控流程执行一次智谱 `embedding-3` 请求，返回 2048 个有限数值维度，用时约 2.38 秒；不保存向量或输入正文。

[Candidate] legacy RAG 首次请求在约 45.69 秒由应用 timeout 终止。经单独授权，将默认 RAG 聊天模型的最小 timeout 修正为 300 秒后，只重试一次并在约 56.15 秒成功，持久化两个预期知识结果；没有增加 provider 自动重试，`max_retries=0` 保持。

[Missing] 这些结果来自本机、合成输入和有限调用，不是压力/容量测试，不覆盖客户数据、持续负载、故障恢复、完整浏览器项目 E2E 或完整 Agent E2E；provider 返回的货币成本未记录，也不作估算。

## 发布与后续边界

[Approved] 最终发布只允许将同一个 release commit 普通快进到 `codex/iteration6` 和 `main`；不得 force-push、重写 main、移动 V5 归档、创建 tag 或 GitHub Release。远程分支保护规则无法由当前权限证明，普通 push 的实际结果是发布门禁。

[Verified] 本轮最终树只保留产品、运行、长期运维与历史证据文档；24 份 Iteration 6 临时计划/日志/过程 closeout 已排除，其余历史计划保留。历史容器与双拓扑文档只作不可变资料，不是当前 V6 可执行入口。

[Missing] 后续若要声称生产就绪，仍需另行授权并建立可审计的压力与容量基线、客户等价数据边界、完整项目/Agent E2E、故障恢复、安全评审和运维 SLA；不得由本次收口自动推导。
