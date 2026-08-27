# EzllmTest Iteration 4 新对话提示词

> **归档状态：Iteration 4 已完成离线验收与隔离真实模型 Agent 合成 E2E。** 下文是保留的历史执行提示，不应再次按“尚未启动”状态运行。实际交付、门禁数字、真实费用边界和生产未验证限制见 [`docs/iteration-4-closeout.md`](iteration-4-closeout.md)。

Iteration 4 开工时按以下顺序使用这些提示词：第一条只允许只读接手；阅读并确认接手报告后，再发送第二条，只规划 Aspect 1。

后续每个 Aspect 都必须遵循：

```text
只读核验 → 计划确认 → 单方面实施 → 门禁验证 → 停止等待
```

不得在一个计划或实施回合中提前跨入下一 Aspect。

## 第一条提示词：Iteration 4 只读接手

```text
你现在只读接手 Windows 本地项目 D:\codex\EzllmTest_v2。GitHub main 已完成并发布 Iteration 1–3；Iteration 4 目标是把当前“确定性 AI 测试工作流平台”演进为可规划、可审批、可恢复、可评测、可观测的测试编排 Agent 平台。已锁定 Python/FastAPI 主线、LangGraph 单一 Agent 编排运行时、用户可见 Agent 工作台、受控 MCP 接口和本地 Docker Compose 工程栈。不要开始实现。

当前必须保护：19 个 workflow catalog；全部公共路由和 REST/SSE wire format；revision-aware artifact/cache；RAG 索引复用与 Token/上下文预算；延迟保存、取消、stale、失败回滚和 regeneration lock；所有 preliminary analysis 持久化；unit_case、integration_case、api_case、functional_case、nonfunctional_case session-only；ui_case、db_case、acceptance_case persisted。

完整阅读：

1. README.md，Iteration 1/2 closeout 与 Iteration 2 development log/token baseline；
2. Iteration 3 overview/closeout/development log；
3. docs/iteration-4-overview.md 和 docs/iteration-4-prompts.md；
4. backend requirements、config、main、routes、workflowCatalog、stream core、provider、artifact、revision、RAG registry/retrievers、DAO 和 SQL；
5. frontend package、router、state、composables、MainView、TestPlan、TestMenu、LLM feedback 和八类测试页；
6. relevant tests，包括 workflow cost baseline、contracts、closeout、credential scan；读取 .gitignore 和 .env.example 的变量名，但绝不读取真实 .env。

先执行只读的 git branch、git status、git diff --stat 和本地 origin/main 对比；不要 fetch、pull、stage、commit 或 push。不要运行测试、构建、服务或数据库命令，不安装依赖。可以仅浏览公开的官方岗位、框架和协议文档核对当前状态；不得访问 provider API、真实模型、embedding、MySQL 或真实项目。

请输出 Iteration 4 只读接手报告，至少说明：

- Verified：当前架构、数据流、可复用基础，以及确定性 workflow 与 Agent 的真实差距；
- Approved：已锁定的 Python、LangGraph、工作台、MCP 和 Compose 方向；
- Proposed：Agent 状态图、工具边界、风险审批模型及 MySQL/Redis 职责；
- Missing：Eval、可观测性、性能、交付和 CI 能力；
- 使用当前官方资料复核 LangGraph、OpenAI Agents SDK、DeepSeek Harness 和 Pi Agent Harness；除非发现阻塞性证据，不重新打开已确认的 LangGraph 选择；
- Aspect 1 的依赖、兼容性风险、需保护的用户资产，以及 Iteration 4 八个方面的顺序是否与当前代码冲突。

所有结论明确标记 Verified、Approved、Proposed 或 Missing。完成报告后立即停下，等待我的第二条提示词。
```

## 第二条提示词：只规划 Aspect 1

```text
基于刚才的只读接手报告，进入计划模式，只为 Iteration 4 Aspect 1“Agent 能力基线、架构契约与测量协议”制定详细实施计划。不要规划或实施 Aspect 2–8，不要开始修改代码，先把计划交给我确认。

计划必须：

- 重新核对当前 dirty worktree，全部既有内容均视为用户资产；
- 明确 Aspect 1 的文件范围、非目标、依赖、验证门禁和可回滚边界；
- 冻结 19 个 workflow、公共路由、REST/SSE、artifact、revision、RAG、缓存、取消、stale、regeneration lock 和 retention 基线，并记录 package manifests 哈希；
- 规划 ADR，锁定 Python + LangGraph，不引入 Java 重写或多 Agent；
- 保持现有 workflow catalog 为业务工具真源，Agent 内部调用应用服务层，不通过 HTTP 或 MCP 调用自身；
- 明确 MySQL 保存项目和有效 artifact，Redis 保存 Agent thread/checkpoint、租约、幂等、取消和短期事件重放；工作台与 loopback MCP 使用同一类型化工具定义；
- 给出概念性的 AgentRunState 和状态机，覆盖目标、结构化计划、审批、执行、验证、完成、取消、失败和恢复；
- 定义 read-only、paid、persistent、regenerate 风险级别和 HITL 规则；项目作用域由可信运行时注入，不能由模型提供；
- 规划步数、执行时间、Token、模型调用和工具调用预算；禁止保存或展示 chain-of-thought；
- 建立版本化合成数据集与基准矩阵，默认使用 deterministic fake provider；
- 指标至少覆盖 task success、trajectory validity、tool selection、approval bypass、structured output、恢复、重复副作用、项目隔离、RAG、p50/p95、TTFE、吞吐量、模型/embedding 次数、Token、估算成本、缓存命中和 OpenTelemetry 开销；
- 在任何依赖变化前捕获 Iteration 3 基线，性能门禁使用可复现的相对值，不虚构提升；
- 规划 LangGraph、checkpointer、Redis、MCP 和 OpenTelemetry 的版本兼容 spike；未经我批准不得安装依赖；
- 安全基线包括安全序列化、敏感数据脱敏、loopback 默认绑定、无任意文件/Shell/网络工具及零审批绕过；
- 测试先行设计静态契约、状态机模型测试、确定性 benchmark 和文档契约；
- 计划包含聚焦检查、完整 pytest、npm run lint、隔离 build、凭证扫描、git diff --check 和生成物检查；
- 不读取真实 .env，不访问真实模型、embedding、MySQL 或外网，不产生费用；
- 计划确认后也只能实施 Aspect 1；完成时创建或更新 docs/iteration-4-development-log.md，然后停下等待 Aspect 2；
- 不 stage、commit、fetch、pull 或 push，除非我另行明确要求。

先输出详细计划和关键架构决策，等待我确认，不要直接编辑任何文件。
```
