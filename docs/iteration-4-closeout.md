# Iteration 4 Closeout：离线集成验收

状态：**Aspect 1–8 已完成离线验收**。本 closeout 记录的是确定性 fake planner/provider、合成项目、隔离 Redis/MySQL/SQLite 和本地 Compose 的证据；真实模型 Agent 质量验收未执行，也未授权产生模型费用或发布。

## 交付结果

- 保留 Python 3.11/FastAPI 主线，以 LangGraph 单 Agent 实现观察、规划、逐步审批、执行、验证、取消、失败和恢复状态图。
- 19 个 workflow 仍是业务能力、前置依赖、持久化和成本规则的唯一真源；Agent 通过进程内应用服务层调用，不经 HTTP 或 MCP 自调。
- 22 个类型化工具由工作台与 MCP 共享：3 个只读状态工具和 19 个 workflow 工具。loopback MCP 默认只能执行只读工具。
- MySQL 继续保存项目、revision 与有效 persisted artifact；Redis 保存 checkpoint/thread、租约、fencing、幂等、取消、短期事件重放和 session-only 证据。
- 工作台提供结构化计划、HITL 风险审批、时间线、预算、恢复、RAG 引用和证据投影，不保存或展示 chain-of-thought。
- OpenTelemetry 为 Agent API、command、worker、graph、tool、checkpoint、SSE 和恢复提供脱敏 trace/metrics；普通本地进程默认关闭，Compose 显式启用。
- 本地交付栈包含 digest-pinned Docker Compose、Prometheus、Tempo、Grafana、Vite 前端、离线 Eval、benchmark 和 GitHub Actions 定义。

## 冻结兼容边界

Iteration 4 未改变 19 个 workflow catalog、legacy 公共路由、REST `{status, reason, data}` 包装、legacy SSE 事件、artifact identity、revision-aware cache/RAG、stale、取消、延迟保存、失败回滚、regeneration lock 或 retention 语义。legacy `reasoning_delta` 仍作为受保护 wire 兼容字段存在；Agent 路径不生成、不保存、不返回也不展示原始 CoT。

`unit_case`、`integration_case`、`api_case`、`functional_case`、`nonfunctional_case` 继续为 session-only；`ui_case`、`db_case`、`acceptance_case` 继续为 persisted。session-only 结果只在 run-scoped Redis 保留 7 天，persisted 结果继续以 MySQL artifact 为长期真源。

## 验收证据

### Eval 与集成旅程

- Aspect 6 Eval：**104/104** 通过；task success、trajectory validity、tool selection、structured output、recovery 与安全攻击预期阻断均为 100%。
- Aspect 8 Acceptance：**18/18** 通过；覆盖项目 setup、Agent 计划与审批、exact cache、RAG 引用、session/persisted/regenerate、stale、取消、失败回滚、crash/reconcile、event replay、API 隔离、MCP 边界和 telemetry 脱敏。
- 硬安全计数：approval bypass = 0、duplicate side effect = 0、project isolation violation = 0、预算突破 = 0、任意能力执行 = 0、敏感数据泄漏 = 0。
- warm exact-cache 的新增模型调用与 embedding 调用均为 0；真实 provider、真实 embedding、用户 MySQL、用户项目读取和模型货币费用均为 0。

### 性能与观测

- 同一 Windows 环境的最终 benchmark：legacy p95 比率 `1.083736659134018`，低于 `1.15` 门禁；OTel enabled/disabled p95 比率 `1.014521458310483`，低于 `1.05` 门禁。
- 唯一验证项目 `ezllm-aspect8-verify-20260827` 的 10 个 Compose 服务全部健康；非 loopback Agent Host 在容器内返回 421。
- Tempo 观察到 `http.agent_api → agent.command.enqueue → agent.command.worker → agent.run → graph → tool/checkpoint → SSE`，并观察到 recover command；禁用属性查询命中 0。
- Prometheus 观察到 run/command/graph/tool/checkpoint/recovery/SSE 指标，标签不含 project、run、thread 或 revision。真实模型与检索未调用，因此没有伪造 model/retrieval 运行样本。
- Grafana 的 Prometheus、Tempo datasource 和 `ezllm-agent-overview` dashboard 可加载；应用容器日志敏感模式命中 0。

### 浏览器与前端

- 工作台在 360×800、768×1024、1024×768、1440×900 和 1920×1080 五个视口均无横向溢出。
- 审批对话框完成焦点进入、Escape 关闭和焦点返回；可见按钮高度至少 44px。
- 合成 UI 旅程验证逐步批准、persisted artifact 摘要、RAG 引用、session-only 7 天证据、trace disabled/instrumented 以及 retryable failure 恢复。
- Vite lint、type-check、隔离 build、bundle checker 与零 source map 门禁保留。

## 安全与恢复结论

可信项目作用域只由宿主注入；模型、请求参数和 MCP payload 不能提供或覆盖 scope、审批、幂等键或预算。paid、persistent、regenerate 步骤在副作用前绑定 plan/project/revision/model/arguments/context/budget 的审批；编辑、过期或任何绑定变化都会使审批失效。

Checkpoint 使用仓库内严格 JSON serializer，不使用 pickle、动态 import 或 constructor envelope。恢复先核对租约 fencing、幂等状态和 persisted artifact；session-only 不确定结果进入 `outcome_unknown`，不自动重复付费调用。Redis 数据丢失只会使旧 thread 不可恢复，不破坏 MySQL 中的有效 artifact。

## 发布状态与已知限制

- GitHub Actions 定义和本地等价命令已验证；托管状态保持 `awaiting_explicit_push`，不得将其描述成已在托管端成功运行。
- 真实模型 Agent 质量验收未执行；现有 Iteration 3 截图仅是 legacy 真实 provider 证据，不是 Agent 真实模型证据。
- 本次未创建 commit、tag、Release 或部署；未 stage、未 commit、未 fetch、未 pull、未 push。
- 正式发布、真实 provider 质量/费用评估和托管 CI 运行均需后续单独授权。

详细实施命令、实际结果与停点见 `docs/iteration-4-development-log.md`；版本化门禁见 `ez_back_dev/tests/fixtures/iteration4_aspect8_gate_v1.json`。
