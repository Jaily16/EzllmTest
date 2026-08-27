# EzllmTest Iteration 4：可控、可恢复、可评测的测试编排 Agent

> **状态：Aspect 1–8 的离线验收与隔离真实模型 Agent 合成 E2E 均已完成。** 本文保留实施前的方面级路线图、标签和决策背景作为历史记录；已交付能力、真实门禁数字与限制以 [`docs/iteration-4-closeout.md`](iteration-4-closeout.md) 为准。交付目标为 `main`，本次不创建 Tag 或 Release；托管 CI 状态以仓库 badge/Actions 页面为准。

本文第 3–4 节的 `Verified`、`Approved`、`Proposed` 和 `Missing` 标签描述的是 Iteration 4 开工时的基线，不应被理解为当前交付状态。

## 1. 文档状态约定

Iteration 4 使用以下标签区分仓库事实与未来方案，避免把规划能力误写成已交付能力：

- **Verified**：已由当前 `main` 的代码、配置、测试或 Iteration 1–3 文档核实。
- **Approved**：产品与架构方向已经确认，但尚未实施。
- **Proposed**：需要在对应 Aspect 中完成兼容性验证、详细设计和用户审批。
- **Missing**：当前仓库尚不具备、且需要由后续 Aspect 补齐的能力。

## 2. 目标与产品边界

**Approved — 目标：** 将 EzllmTest 从由确定性工作流驱动的 AI 测试工作台，演进为可规划、可审批、可恢复、可评测、可观测的测试编排 Agent 平台。

目标架构不会用自由自治的 Agent 替换现有业务流程。Agent 负责理解目标、检查项目状态、提出结构化执行计划、请求必要审批、选择受控工具、验证结果并组织恢复；现有 workflow catalog 继续负责具体测试分析与生成。

目标用户旅程为：

```text
提出测试目标
  → Agent 检查项目、生命周期与可用能力
  → 生成结构化执行计划
  → 校验权限、预算和前置条件
  → 用户审批付费、持久化或重新生成动作
  → 调用受控测试工具
  → 汇总证据、状态、Token 与耗时
  → 完成、取消、失败回滚或断点恢复
```

## 3. 当前技术基线

### 3.1 已验证能力

- **Verified — 后端：** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy 2、PyMySQL、LangChain Core、OpenAI-compatible provider 客户端和 SSE。
- **Verified — 前端：** Vue 3、TypeScript、Vue Router、Element Plus、Axios 和 Vue CLI 5。
- **Verified — 工作流：** 一个 `project_analysis` 与 18 个测试工作流操作组成固定的 19 项 workflow catalog，覆盖单元、集成、API、UI、数据库、功能、非功能和验收测试。
- **Verified — 生命周期：** 项目创建、文档上传恢复、计划和菜单优先、路由守卫、下游重新生成锁定及统一步骤状态。
- **Verified — 结果安全：** revision-aware artifact/cache、完整成功后的延迟保存、取消、stale、失败回滚和旧有效结果保护。
- **Verified — 保留边界：** 所有 preliminary analysis 持久化；`unit_case`、`integration_case`、`api_case`、`functional_case`、`nonfunctional_case` 为当前页面 session-only；`ui_case`、`db_case`、`acceptance_case` 持久化。
- **Verified — RAG 与成本：** 文档分块、请求内向量检索、进程内 revision-aware 索引复用、上下文/输出/思考预算、Token 使用反馈和离线成本基线。
- **Verified — 体验基础：** Iteration 3 已建立设计系统、响应式应用壳、共享反馈、项目恢复、规划工作台、八类测试工作区、无障碍规则和 bundle 门禁。
- **Verified — 质量基础：** 仓库已有完整 pytest 契约体系、前端 lint/build 门禁、凭证扫描、离线 fixture 和真实 provider 代表性旅程记录。

### 3.2 当前缺口

- **Missing — Agent runtime：** 当前不存在显式 Agent 状态图、计划审批、可持久恢复的 thread/checkpoint 或受预算约束的工具循环。
- **Missing — 工具协议：** workflow catalog 尚未形成供 Agent 与 MCP 共用的类型化工具注册表、风险元数据和项目授权边界。
- **Missing — 运行基础设施：** 当前没有 Redis checkpoint、运行租约、跨进程幂等、独立 worker 或可恢复事件重放。
- **Missing — 系统化 Eval：** 当前成本基线和契约测试尚未覆盖 Agent 任务成功率、轨迹、工具选择、审批绕过和安全攻击集。
- **Missing — 可观测性：** 当前没有统一的 OpenTelemetry trace、Prometheus 指标、Tempo 链路和 Grafana 仪表盘。
- **Missing — 可复现工程栈：** 当前没有 Docker Compose 或仓库内 CI 工作流；Vue CLI 已进入维护模式，尚未迁移到 Vite。

## 4. 已批准的架构方向

### 4.1 Agent 编排

- **Approved：** 保持 Python/FastAPI 主线，不引入 Java/Spring 重写。
- **Approved：** 选择 LangGraph 作为唯一 Agent 编排运行时，不并行维护第二套 Agent 框架。
- **Approved：** 现有 19 项 workflow catalog 是业务能力和执行语义的真源，不重写为任意模型行为。
- **Approved：** Agent 内部通过应用服务层调用工具，不通过 HTTP 或 MCP 调用自身。
- **Approved：** 不保存或展示 chain-of-thought；只记录结构化计划、审批决定、工具动作、证据引用、状态、Token、成本和耗时。

LangGraph 的定位是可组合确定性流程与 Agent 决策的低层运行时，并提供持久化、流式执行和人工中断能力。实施时仍须重新核对当前官方版本和兼容性：[LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)、[persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。

选择前已对照以下方案；除非 Aspect 1 发现阻塞性兼容问题，否则不重新打开框架选择：

| 方案 | 已核对定位 | 本项目结论 |
|---|---|---|
| LangGraph | Python 低层 Agent 编排与持久执行 | **Approved**，最贴近现有 LangChain/FastAPI 与确定性 workflow |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/agents/) | tools、handoffs、guardrails、sessions、tracing 与 MCP | 保留为对照，不在同一产品中再引入第二运行时 |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | Node/TypeScript、插件化完整 harness | 当前重写成本高，且官方仍提示 developer preview 风险 |
| [Pi Agent Harness](https://github.com/earendil-works/pi) | Node/TypeScript、面向 coding agent 的运行时 | 产品方向偏 coding agent，安全权限需由宿主额外实现 |

### 4.2 工具、MCP 与审批

- **Approved：** Agent 工作台与 MCP 共享同一份类型化工具定义，但使用不同适配层。
- **Approved：** MCP 默认只绑定 loopback；遵循 tools、resources、prompts、progress、cancellation 和 errors 的协议语义，并在实施时重新核对[当前 MCP specification](https://modelcontextprotocol.io/specification/)。
- **Approved：** 不暴露任意 Shell、文件系统、SQL 或外部网络工具。
- **Approved：** 项目 ID、用户/项目作用域和权限由可信运行时注入，不能接受模型自行构造。
- **Approved：** 工具至少划分 `read-only`、`paid`、`persistent`、`regenerate` 四类风险；付费、持久化和重新生成操作必须经过明确的人类审批。
- **Proposed：** 每个工具声明 Pydantic 输入输出、前置条件、风险等级、幂等键、预算影响、可取消性和结果保留方式。

### 4.3 状态与数据职责

- **Verified：** MySQL 当前保存项目、文档信息、工作流状态和有效 artifact，是业务持久化真源。
- **Approved：** MySQL 继续承担上述职责；Agent checkpoint 不改变 artifact revision、延迟保存或 retention 语义。
- **Approved：** Redis 用于 Agent thread/checkpoint、运行租约、幂等、取消信号和有 TTL 的短期事件重放。
- **Proposed：** 使用独立 Redis-backed worker 执行可恢复运行；具体 worker/checkpointer 包只能在 Aspect 1 兼容性验证后锁定。
- **Approved：** Agent thread state、项目 artifact 和 RAG 索引必须分层，不得互相冒充长期记忆。

### 4.4 可观测与本地工程栈

- **Approved：** Docker Compose 提供可复现的 frontend、API、worker、MySQL、Redis、OpenTelemetry Collector、Prometheus、Tempo 和 Grafana 服务。
- **Approved：** graph、model、tool、retrieval、checkpoint 和 SSE 建立关联 trace/span；prompt、completion 和工具敏感参数默认不采集。
- **Proposed：** 采用 OpenTelemetry GenAI 语义约定，并在实施时锁定与当前 SDK 兼容的稳定字段：[OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)。
- **Approved：** Vue CLI 到 Vite 的迁移放在可观测与交付 Aspect 中，以构建时间、bundle、开发启动和回归结果证明价值；不能只因工具更新而迁移。[Vue CLI maintenance status](https://cli.vuejs.org/)、[Vite guide](https://vite.dev/guide/)

## 5. 全局保护契约

Iteration 4 的所有 Aspect 必须保护：

- 19 个 workflow operation 的名称、顺序、前置依赖和既有 payload。
- 公共路由、REST 响应信封、SSE event 名称、字段和完成/取消时序。
- revision-aware artifact/cache、RAG 索引复用与上下文、输出、思考预算。
- 完整成功后的延迟保存、取消、stale、失败回滚及 regeneration lock。
- 所有 preliminary analysis 的持久化，以及五类 session-only 和三类 persisted final 边界。
- 页面加载不自动产生付费模型或 embedding 调用的产品原则。
- 真实 `.env`、API Key、数据库密码、项目文档、模型 reasoning 和用户数据不得进入日志、trace、测试数据或 Git。

若某个 Aspect 必须修改生产数据库结构、公共 REST/SSE、retention 或现有 workflow 真源，必须停止并提交单独方案，不能在原 Aspect 中静默扩大范围。

## 6. 八个实施方面

这些是依赖有序的方面，不在本文件中细分实现任务。

### Aspect 1 — Agent 能力基线、架构契约与测量协议

冻结 Iteration 3 的接口、成本、延迟、RAG 和可靠性基线；发布 Agent、工具、状态、数据与安全 ADR；建立版本化合成任务集、指标字典和相对门禁；完成 LangGraph、checkpoint、Redis、MCP 与 OpenTelemetry 的只读版本/兼容性验证。

**退出条件：** 基线可重复、边界决策完整、测量方法不依赖真实 provider，且没有安装或启用 Agent runtime。

### Aspect 2 — 类型化工具注册表与 MCP 互操作

将现有只读查询和 workflow 能力映射为类型化、受项目作用域约束的工具；建立风险、审批、预算、幂等和取消元数据；为内部 Agent 与 loopback MCP 提供独立适配层。

**退出条件：** 工具契约覆盖 19 个 workflow，内部调用不自发 HTTP，MCP 无任意文件/Shell/网络能力，且旧接口行为不变。

### Aspect 3 — LangGraph 运行时与持久执行

建立显式 Agent 状态图、HITL interrupt、Redis checkpoint、运行租约、幂等、取消、恢复和可重放事件；为步数、时间、模型、Token 和工具调用设置硬预算。

**退出条件：** 合成任务可在中断、进程重启和失败注入后安全恢复，且不会产生重复保存或覆盖旧 artifact。

### Aspect 4 — 测试编排 Agent 工作台

新增目标输入、结构化计划、审批/编辑/拒绝、执行时间线、工具与证据、Token/成本、取消/恢复和 trace ID 界面；保持响应式、键盘和无障碍基线。

**退出条件：** 页面无隐式模型调用，风险动作可解释且必须审批，用户能区分计划、运行、保存、失败和恢复状态。

### Aspect 5 — 上下文工程、RAG 证据与记忆边界

分离 thread checkpoint、项目 artifact 和检索索引；增加检索来源与引用；对 dense、hybrid 和可选 rerank 做固定语料对比，只在准确性收益覆盖延迟与成本时采用新路径。

**退出条件：** 检索决策由 recall@k、MRR/nDCG、引用覆盖、延迟和成本证据支持，且跨项目数据隔离测试为零泄漏。

### Aspect 6 — Agent Eval、可靠性与安全门禁

建立版本化 golden tasks，评估任务成功、轨迹合法性、工具选择、结构化输出、审批、恢复和副作用；加入 prompt injection、越权工具、跨项目泄漏和预算突破测试。

**退出条件：** 离线 Eval 可重复，审批绕过与跨项目泄漏为零，真实模型 Eval 仍需单独费用批准。

### Aspect 7 — 可观测性、性能与交付工具链

接入脱敏 trace/metrics、Compose 观测栈、结构化日志、负载基准与 GitHub Actions 离线门禁；在同一基准下完成 Vue CLI 到 Vite 的兼容迁移与前后数据比较。

**退出条件：** 冷/热/恢复/并发基准和可观测开销有可复现实测；不变 API 的 p95 不超过 Aspect 1 基线 15%，观测开销不超过 5%，且 warm cache 继续保持零模型/embedding 调用。

### Aspect 8 — 集成 Agent 验收与 Iteration 4 收口

覆盖项目创建、Agent 规划、审批、执行、缓存、stale、取消、重启恢复、失败回滚、session-only/persisted、MCP、安全门禁和观测仪表盘；汇总架构、Eval 和性能证据。

**退出条件：** 完整离线旅程和门禁通过，README 只呈现已经验证的产品能力；提交、推送或发布必须等待单独指令。

## 7. 依赖顺序

```text
Aspect 1  基线、契约与测量协议
    ↓
Aspect 2  工具注册表与 MCP
    ↓
Aspect 3  LangGraph 与持久执行
    ↓
Aspect 4  Agent 工作台
    ↓
Aspect 5  上下文、RAG 与记忆边界
    ↓
Aspect 6  Eval、可靠性与安全
    ↓
Aspect 7  可观测、性能与交付
    ↓
Aspect 8  集成验收与收口
```

工具边界必须先于 Agent runtime；运行时必须先于用户界面；稳定状态和证据模型必须先于系统化 Eval；性能结论必须在可观测数据与固定基准具备后给出。

## 8. Eval 与性能证据协议

Iteration 4 不接受仅凭框架名称或单次演示得出的“性能提升”。每项结论必须记录：

- Git revision、操作系统、Python/Node 版本、依赖锁定值和服务拓扑。
- 数据集版本、任务数量、样本量、并发度、冷启动/热缓存状态和测量命令。
- task success、trajectory validity、tool selection、structured output 和 approval bypass。
- 取消/失败/重启恢复、重复副作用、跨项目隔离、stale/cache/retention 正确性。
- RAG recall@k、MRR/nDCG、引用覆盖率、索引与查询延迟。
- p50、p95、TTFE、吞吐量、错误率、模型/embedding 次数、Token 和估算成本。
- 启用与关闭 OpenTelemetry 的对照开销。

默认使用 deterministic fake provider、内存或隔离测试数据和固定随机种子。真实 provider、embedding 或 MySQL 验证必须单独批准、限定预算，并与离线门禁分开记录。

Aspect 1 只建立基线和相对门禁；没有数据时不得填入虚构的优化百分比。任何新缓存、检索、worker 或构建工具都必须与原基线对照，说明收益、成本和回滚条件。

## 9. 每个 Aspect 的工作协议

1. 只读核验 Git、相关代码、契约、文档和既有资产。
2. 提交该 Aspect 的决策完整计划，明确文件范围、非目标、迁移与回滚边界。
3. 等待用户确认，不提前修改代码或安装依赖。
4. 以测试先行方式只实施获批 Aspect。
5. 运行聚焦测试、完整离线门禁、lint/build、凭证和生成物检查。
6. 更新 `docs/iteration-4-development-log.md`，记录事实、测量数据与已知限制。
7. 不自动进入下一 Aspect，不 stage、commit、fetch、pull 或 push。

## 10. Iteration 4 成功标准与非目标

成功标准：

- Agent 能在受控工具和预算内形成计划、获得审批、执行并验证测试工作流。
- 中断、取消、失败和进程重启不会造成重复付费副作用或覆盖旧有效结果。
- Agent、MCP、RAG 和项目数据具备明确权限与项目隔离。
- Eval、性能和可观测证据能够在本地离线复现。
- 新架构不破坏 Iteration 1–3 的接口、缓存、artifact、stale 与 retention 语义。

明确非目标：

- 不构建多 Agent 组织或开放式自主执行系统。
- 不进行 Java/Spring 全量重写。
- 不引入 Kafka、Kubernetes、任意 Shell/文件工具或通用个人长期记忆。
- 不因技术趋势直接引入新向量数据库、reranker 或队列；必须先有基准证据。
- 不在 Aspect 8 之前宣称 Iteration 4 已完成，也不在没有单独指令时发布。
