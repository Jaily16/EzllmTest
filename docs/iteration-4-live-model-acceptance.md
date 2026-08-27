# Iteration 4 真实模型 Agent 质量验收

执行日期：2026-08-27–2026-08-28
状态：**通过**（planner 结构化质量与隔离真实 Agent E2E 均通过）

## 范围与费用边界

本次在用户明确授权后执行，只使用版本化合成目标和合成文档：

- 聊天模型固定为 `GLM-4.7`，embedding 固定为 `embedding-3`。
- 预检调用为 1 次 chat 与 1 次 embedding；质量套件上限为 6 次 chat 与 4 次 embedding。
- 未遍历其余三个聊天 provider，未读取真实项目，未访问 MySQL，未调用业务工具或产生 artifact 副作用。
- 报告不保存目标、prompt、模型正文、reasoning、文档正文、凭证、连接串、项目标识或 provider 原始异常。
- 供应商货币费用未从 API 返回，因此只记录调用与 Token，不推测人民币或美元金额。

## 首轮实际结果

连通性预检通过：`GLM-4.7` 返回固定 smoke 标记，chat usage 为 input `19`、output `244`、total `263`；`embedding-3` 返回 `2048` 维向量。

真实 planner 质量套件：

- 6 次调用全部完成，但 6/6 均未通过严格 `PlannerProposal` 结构校验。
- 工具选择成功率因此为 `0/6`，结构化输出有效率为 `0/6`，planner gate 为失败。
- 套件 input Token 为 `13,191`，total Token 为 `13,391`；依据 total-input 观察到 completion Token 为 `200`。当前 usage 解析只有在 provider 返回 reasoning breakdown 时才能单独填充 output Token，因此不把不完整的 output 字段作为账单依据。
- 六次 wall-clock 延迟为 `1357.746–2667.186 ms`；nearest-rank p50 为 `2303.766 ms`，p95 为 `2667.186 ms`。

真实 RAG/embedding 质量套件：

- 三个合成查询全部 top-1 命中，`3/3`，top-1 accuracy=`1.0`。
- citation coverage=`1.0`，context Token=`94`。
- index build/reuse=`1/2`，符合相同 revision 复用要求。
- 三次 query wall-clock 延迟为 `141.992–369.006 ms`；nearest-rank p50 为 `148.042 ms`，p95 为 `369.006 ms`。

首轮总计实际发起 7 次 chat 与 5 次 embedding（包含连通性预检）。已按固定上限停止，没有自动重试或扩大样本。

## 修复

首轮失败后没有查看、保存或放宽接受模型正文。代码修复集中在共享 provider 边界：

- 为 planner request 增加唯一的共享 prompt builder，明确要求只返回一个 `PlannerProposal` JSON object，禁止 Markdown、说明文字、分析和 code fence。
- 将 goal、observation 和工具元数据明确标为 untrusted data；模型仍不能提供 project/scope、审批、模型、预算、幂等、凭证或前置 artifact 正文。
- 在 `GLM-4.7` 请求中增加官方支持的 `response_format={"type":"json_object"}`。stream adapter 只允许这个冻结值，拒绝其他动态 response format。
- `json.loads`、Pydantic `extra="forbid"`、catalog-only 工具选择、输入 schema、运行时可信作用域、风险和审批校验全部保持严格，不增加 Markdown 剥离、宽松 JSON 修复或任意文本解析。
- 正式 runtime factory 与付费验收入口共用同一 prompt builder 和 response-format 常量，并由离线回归锁定。

官方依据：[`response_format` 的 `json_object` 模式](https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E5%AF%B9%E8%AF%9D%E8%A1%A5%E5%85%A8)；官方同时建议在提示词中明确要求 JSON 输出。

## 修复后付费复验

用户再次明确授权后，使用与首轮完全相同的六个 planner 样例、四份合成文档和三个查询复验；没有重新执行 smoke，也没有调用其他 provider。

真实 planner：

- tool selection=`6/6`，structured output=`6/6`，regenerate binding=`6/6`。
- input Token=`11,337`，total Token=`11,622`，依据 total-input 观察到 completion Token=`285`。
- 六次 wall-clock 延迟为 `1021.439–2637.884 ms`；nearest-rank p50=`1151.586 ms`，p95=`2637.884 ms`。

真实 RAG/embedding：

- 三个查询 top-1=`3/3`，top-1 accuracy=`1.0`，citation coverage=`1.0`。
- context Token=`94`，embedding calls=`4`，index build/reuse=`1/2`。
- 三次 query wall-clock 延迟为 `138.464–439.944 ms`；nearest-rank p50=`147.681 ms`，p95=`439.944 ms`。

修复后套件总门禁为 **PASS**。复验实际调用为 6 次 chat 与 4 次 embedding；连同首轮和预检，本次真实验收工作累计为 13 次 chat 与 9 次 embedding。供应商没有在响应中返回货币费用，仍只记录调用与 Token，不推测人民币或美元金额。

## 安全结果

- real project reads=`0`
- MySQL calls=`0`
- tool side effects=`0`
- stored model content=`0`
- stored reasoning=`0`
- credential exposure=`0`

真实 `.env` 仅由现有配置加载器读取；验收输出、本文档和测试中均不包含密钥值。

## 结论与边界

首轮已验证的代码缺口是 runtime planner 直接发送 request JSON，却没有显式 `PlannerProposal` 输出指令或 provider JSON mode。修复后相同六个样例全部通过，支持该缺口是本次失败的直接工程原因；模型正文仍按设计立即丢弃，未用于报告或诊断。

本次证据验证的是合成目标上的真实 planner 结构化规划和合成语料上的真实 embedding/RAG，不等同于真实客户项目、真实 MySQL 或完整业务 workflow 的付费端到端质量验收。catalog-only、`extra="forbid"`、可信作用域注入、HITL、零 CoT 和副作用边界均由原有离线门禁继续保护。

Aspect 8 的版本化 gate 仍是其完成当时的离线历史证据，不回写或伪造为真实模型通过。

## 隔离的真实模型 Agent 端到端验收

用户进一步授权后，执行了固定的 `ui_info → ui_case` 真实付费旅程。该旅程使用实际 Agent API ASGI app、Redis command worker、LangGraph graph、安全 Redis checkpointer、HITL、内部工具适配器、artifact 服务和真实 RAG/embedding；Agent 没有通过 HTTP 或 MCP 自调业务 workflow。

隔离边界：

- 项目、requirements、design 和 knowledge 全部在系统临时目录中合成；没有枚举或读取真实项目。
- `DATABASE_URL` 在导入 DAO 前强制指向临时 SQLite；用户 MySQL 调用为 `0`。
- Redis 使用固定镜像 `redis:8.2.8-alpine@sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103`，仅发布到 `127.0.0.1:6399`，`/data` 为 tmpfs，且每次 run 使用唯一 namespace。
- 临时 SQLite、合成文档和 Redis 容器在完成后均已删除；端口 `6399` 已释放。用户既有 Redis 容器未停止或修改。

最终通过结果：

- trajectory=`ui_info, ui_case`，terminal status=`completed`，人工审批=`2`。
- `ui_info` 与 `ui_case` artifact 各保存 `1` 份，内容结构非空；重复副作用=`0`。
- 真实 RAG query=`1`、citation=`1`、context Token=`98`、index build/reuse=`1/0`。
- 最终 run 的预算 ledger：model calls=`4`、embedding calls=`2`、input/output Token=`15,209/26,112`、tool calls=`2`、steps=`2`。
- wall-clock=`96,163.598 ms`。provider 未返回货币费用，`estimated_cost_units=0` 不能解释为免费，也不推测人民币或美元金额。
- approval bypass、跨项目/真实项目读取、用户数据库调用、重复副作用、公开正文泄漏、checkpoint 正文泄漏、stored reasoning 和 credential exposure 均为 `0`。

该验收发现并修复了两个只在真实多步骤旅程中暴露的问题：

1. `VALIDATION_SUCCEEDED` 在还有后续步骤时曾回到 planner，导致冻结计划被重新生成并再次审批 `ui_info`。现在状态直接推进到既有计划的下一步，并依据下一工具风险进入 `awaiting_approval` 或 `executing`；回归测试验证两步各执行一次且不重新规划。
2. Windows 上 SQLAlchemy pool 会在临时目录退出时继续持有 SQLite 文件句柄。验收入口现在先关闭 Redis、再显式 dispose 隔离 engine，最后删除临时目录；清理异常也进入脱敏阶段错误码。

为透明记录实际费用边界，本次 E2E 调试共执行四个隔离 run：首个 run 在 `ui_info` 后暴露状态推进缺陷，后两个完整 run 暴露/定位 Windows 清理问题，最终 run 完整通过。根据实际完成节点与预算 ledger，累计为 `14` 次 chat 和 `6` 次 embedding；没有调用另外三个聊天 provider。所有 run 均使用合成数据和临时存储。

该结果把先前“只验证 planner 与 RAG、未调用业务工具”的边界提升为完整的真实模型 Agent 合成项目旅程，但仍不代表真实客户项目、用户 MySQL 或生产负载验收。Aspect 8 离线 fixture 与历史 gate 继续保持不变。
