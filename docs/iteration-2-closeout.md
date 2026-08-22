# EzllmTest Iteration 2 完成报告

日期：2026-08-20
代码状态：Task 0–9 的离线实现与审计已完成，全部改动仍在用户的未提交 worktree 中。
发布状态：离线门禁通过；真实 MySQL 结构变更未执行，真实 provider 付费 A/B 未执行。

## 1. 完成范围

Iteration 2 建立了 19 个 workflow catalog、固定 small/large 离线成本基线、revision-aware artifact、可恢复项目创建与上传、统一项目生命周期、合并后的初始分析调用图、18 个通用工作流的最终结果持久化、revision-scoped RAG 索引复用、阶段化上下文/输出/思考预算，以及八类测试页面的共享步骤状态和保存结果恢复。

本轮 Task 9 只执行离线兼容性、效率、迁移和发布审计。没有启动应用服务，没有连接真实 MySQL，没有访问模型或 embedding API，没有运行迁移，也没有提交或推送 Git。

## 2. 真实状态流与恢复边界

项目状态流为：创建项目 → 上传知识/需求/设计文档 → 持久化上传组进度 → 确认 source revision → 生成项目摘要/测试计划/测试菜单 → 按菜单进入八类测试 → 恢复或生成各分析/用例步骤。

- 创建页从 setup status 恢复上传组，只重试未完成组；资料变更会产生新的 source revision。
- 路由守卫、MainView 和 TestMenu 读取同一只读 `workflow status`。状态读取不会自动发起 LLM，也不会自动生成测试结果。
- 后端 artifact 以项目、artifact、输入 hash、source revision、提示词版本和模型标签组成兼容键；精确命中通过原 SSE 返回 `artifact/result/completed`，聊天和 embedding 计数均为零。
- 八类测试页共享 `useTestWorkflow` 和 `WorkflowStepper`。单元/集成保留三阶段，其余六类保留分析/用例两阶段。
- 当前浏览器会话使用 `sessionStorage` 恢复已显示结果和白名单选择；`info`、`unit_info` 等上游正文不会被误当作选择重复保存。换会话时可由用户点击“继续”从服务端 artifact 恢复。
- 上游重新生成成功后只把传递依赖的下游步骤标为 stale；失败时旧有效结果仍可见。文档 revision 变化会使旧分析与测试 artifact 确定性过期。

## 3. API、SSE 与数据库兼容性

离线契约验证保留项目创建、登录、上传、项目资料 CRUD、项目类型、setup/status、workflow/status、测试计划、通用 workflow，以及全部旧测试类型 GET/POST/PUT 路径。旧 `{status, reason, data}` 响应信封和以下 SSE 事件仍可用：`meta`、`progress`、`reasoning_delta`、`answer_delta`、`summary_delta`、`menu`、`usage`、`artifact`、`stale`、`result`、`completed`、`error`。

六张旧表保持原名称、列和主键：

- `tb_test_project`
- `tb_project_knowledge`
- `tb_project_requirement_testdoc`
- `tb_project_design_testdoc`
- `tb_project_type`
- `tb_project_info`

新表 `tb_project_workflow_artifact` 与六张旧表统一定义在根目录 `ezllmtest.sql`。artifact 与旧 `InfoType` 更新在同一事务中写入；保存失败会回滚，不会用半成品替换旧结果。仓库结构文件不包含项目数据或其他业务数据写入语句。

## 4. 离线效率验收

指标为 `C/E/I/O`：聊天调用数、索引 embedding 构建批次数、累计输入上下文 Token、累计输出上限。全部数据来自 mock chat、mock embedding 和固定 small/large 文档，不是 provider 账单。

| Profile | 场景 | Task 0 | Iteration 2 完成值 |
| --- | --- | ---: | ---: |
| Small | 19 个隔离首轮合计 | 40/13/21804/1138688 | 39/13/20408/230400 |
| Large | 19 个隔离首轮合计 | 71/13/387179/1392640 | 39/13/227588/230400 |
| Small | 相同请求重复合计 | 19/5/9319/475136 | 15/0/6738/76800 |
| Large | 相同请求重复合计 | 19/5/51965/475136 | 15/0/46352/76800 |
| Small | `project_analysis` 首轮 | 3/0/2560/73728 | 2/0/1633/10240 |
| Large | `project_analysis` 首轮 | 9/0/60399/122880 | 2/0/35113/10240 |

验收结论：

- 所有持久化 artifact 的精确重复均为零聊天、零 embedding、零输入 Token、零输出上限。按后续产品决策，`unit_case`、`integration_case`、`api_case`、`functional_case` 和 `nonfunctional_case` 为当前页面临时结果，不再计入可恢复 artifact。
- small 初始项目分析为两次聊天调用，满足不超过两次的门槛。
- 同项目/corpus/source revision/embedding 模型的并发检索只构建一个索引；同 revision 强制重新生成的代表 RAG 工作流新增 embedding 构建均为零。
- 每次模型调用的输入上下文都不超过 operation、阶段和 provider
  共同解析出的有效预算。
- map/structured 等机械阶段没有 high reasoning；Qwen 最终思考预算最多 4096，所有阶段输出上限均受 profile 硬限制。
- 完整逐工作流数字和安全字段约束见 `docs/iteration-2-token-baseline.md`。

## 5. 离线发布门禁

- 后端离线门禁：`275 passed, 1 deselected`；跳过项仍是用户删除历史样本文档后不再成立的仓库资料完整性断言。
- 前端 ESLint：零错误、零警告。
- 前端生产构建：成功；Webpack 只报告既有 `asset size limit` 与 `entrypoint size limit`，涉及字体、Logo、vendor CSS/JavaScript。
- 凭证扫描覆盖 tracked、staged 和非忽略 untracked 文本，只输出文件/规则元数据；本轮没有凭证命中。
- Git generated-artifact tracking 检查未发现 `.env`、Python cache、`node_modules` 或 `dist` 被跟踪；仅允许 `.env.example`。
- `git diff --check` 无空白错误，仅报告现有 LF/CRLF 转换提示。

离线测试进程设置 `PYTHON_DOTENV_DISABLED=1`，使用内存 SQLite，清空全部 provider key，并在成本基线中阻止 socket、provider 和 embedding 客户端创建。因此没有读取真实 `.env`，没有连接 MySQL，也没有产生模型费用。

## 6. 数据库结构状态与批准门禁

状态：**未执行**。根目录 `ezllmtest.sql` 现在是包含七张空表的唯一结构文件，仓库中不再保留独立迁移目录。该文件包含面向空库初始化的 `DROP TABLE IF EXISTS`，不得直接覆盖已有数据的数据库。生产或现有 `ezllmtest_dev` 数据库变更需要用户另行明确批准，并应先完成备份、校验目标库和安排应用停写窗口；旧六表数据库如需升级，应由数据库管理员从结构文件中审核并单独执行工作流表 DDL。

## 7. 可选付费 A/B 检查清单

本轮实际执行：**零次**。此前 Iteration 1 的 provider 连通性不等于本轮 A/B 授权，不能自动沿用。

每次付费检查必须满足：

1. 用户明确指定一个 provider、模型、固定项目和最大费用，并分别批准聊天与 embedding。
2. 迁移和备份状态已确认；测试资料不包含凭证或不应外发的内容。
3. 旧版和新版各运行至多一个相同代表请求，不自动遍历所有 provider。
4. 只记录 HTTP/SSE 成功状态、延迟、model call count，以及 input/reasoning/output/total Token 数字。
5. 不保存 prompt、业务文档、模型正文、reasoning 内容、provider 原始异常或凭证。
6. 完成后立即停止，报告实际费用风险和缓存命中情况；没有新的明确批准不得扩大样本。

## 8. 已知限制

- 七表结构尚未在真实 MySQL 验证；生产数据库变更前仍处于 gated 状态。
- index registry 是单进程内存缓存，容量 16、空闲 TTL 30 分钟。多 worker、进程重启、TTL/LRU 淘汰会分别重建索引。
- `sessionStorage` 是标签会话级恢复；跨浏览器/设备需要用户点击“继续”读取后端 artifact。
- 离线 Token 使用项目固定 tokenizer，是相对比较代理，不代表 GLM、Qwen、DeepSeek 或 Kimi 的实际账单，也不替代质量评测。
- 本轮没有启动服务做浏览器 E2E；Vue 模板/TypeScript 由 lint 和 production build 编译验证，跨页行为由静态发布契约覆盖。
- 构建资产仍超过 Vue CLI 默认建议阈值，Node 24 对旧 CLI 依赖还会发出 `fs.Stats` 弃用提示。
- 凭证扫描不扫描完整 Git 历史；历史凭证仍需在供应商侧撤销或轮换。

## 9. 回滚说明

迁移前回滚不需要数据库操作：在保护当前 dirty worktree 后，由用户明确决定如何形成提交或部署包，再部署上一个已知版本。不要对包含用户资产的 worktree 使用 `git reset --hard` 或覆盖式 checkout。

如果迁移后必须退回 Iteration 1：

1. 停止写入并备份数据库。
2. 部署迁移前应用版本；六张旧表和 legacy `InfoType` 仍保持兼容。
3. 只有在确认不再需要 revision-aware artifact 且获得破坏性操作批准后，才可执行：

```sql
DROP TABLE IF EXISTS tb_project_workflow_artifact;
```

4. 进程内索引无需数据库回滚；重启后端即可清空。

本报告只提供回滚命令，没有执行任何删除、回滚、迁移、提交或推送操作。
