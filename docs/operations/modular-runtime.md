# 分模块运行与运维协议

## 当前状态与职责

[Verified] 启动入口仍为 [modular_runtime.py](../../scripts/modular_runtime.py)，当前拓扑为 [infrastructure/runtime 契约](../../infrastructure/runtime/modular-runtime-contract.json)。旧 ops JSON 保留作历史兼容资产，启动器不再读取它。Python/npm manifests、locks、工具配置和历史版本契约不是新的运行配置来源。

[Verified] 当前基线已完成本地三文件配置和五模块切换；五模块 run 通过身份、readiness、安全 Trace 和中文页面检查。

[Protected] 启动器只管理 observability API、legacy API、Agent API、worker、frontend；不安装依赖、不初始化数据库、不启停 MySQL/Redis，不使用 Docker/WSL。MCP 保留显式 app.mcpServer 入口，但通用 runner 不启动 MCP、不猜测项目 scope。

| 模块 | 新模式默认端口 | 弃用兼容模式默认端口 | 就绪依据 |
| --- | ---: | ---: | --- |
| observability API | 8140 | 8140 | GET /ready |
| legacy API | 8230 | 8130 | GET /ready |
| Agent API | 8231 | 8131 | GET /ready |
| frontend | 8180 | 8080 | GET / |
| worker | 无 HTTP 端口 | 无 HTTP 端口 | Agent readiness 内的 heartbeat |
| MySQL / Redis | 用户明确配置 | 用户明确配置 | SELECT 1 / 表名元数据、PING |

## 三份配置与字段边界

| 配置 | 字段归属 |
| --- | --- |
| [backend/.env.example](../../backend/.env.example) → backend/.env | 数据库、固定 17 个模型字段、五个可选秘密文件引用、Redis namespace/TTL/lease、后端端口、CORS、worker 和 Agent 总预算 |
| [frontend/.env.example](../../frontend/.env.example) → frontend/.env | FRONTEND_PORT 与 legacy API、Agent API、本地观测 API 三个公开 URL |
| [observability/.env.example](../../observability/.env.example) → observability/.env | 8140、本地 SQLite 路径、7 天/100000 行、CORS 和本地 Agent telemetry 设置 |

[Approved] 用户在本机填写三个真实文件，保持当前 V6 数据库、账户、Redis 数据库及 prefix。必填连接和 namespace 在示例中为空，避免误接旧库。真实文件被 Git 忽略；不要发送到聊天、截图或开发记录。provider key 可留空至选用时，但填写示例不等于验证账户有效。

[Verified] 字段由 [纯配置模块](../../backend/infrastructure/runtime_config.py) 定义，不从示例推导 schema。新模式缺任一文件、重复/未知/跨模块字段、非法类型、端口冲突、公开 URL 与后端不匹配、reparse 路径或缺必填值均停止。路径必须绝对且指向普通文件，祖先目录也检查 reparse；三个来源不能是同一路径。

[Verified] 配置采用单行字面值，不展开环境变量或执行命令。后端不再自动加载根 .env，也不再默认连接旧 V2 数据库。子进程先清理继承的应用配置和敏感环境名称，再仅注入所属字段；Windows 用户/系统环境完全不修改。

[Verified] DATABASE_URL 与四家 API_KEY 各自可用对应 _FILE 代替。直接赋值与 _FILE 不得同时出现，空赋值也算冲突。config-check 只检查秘密引用路径，不打开其内容；实际使用或依赖预检才读取明确引用，限制单行、UTF-8 和原有 8192-byte 上限。值及原始错误不回传。

[Verified] 前端子进程只接收 VUE_APP_API_BASE_URL、VUE_APP_AGENT_API_BASE_URL、VUE_APP_OBSERVABILITY_API_BASE_URL。FRONTEND_PORT 不进入浏览器，数据库/provider/Redis/ingestion token 不可公开。Vite 已禁用自动 env 目录与前缀注入，只由纯适配器定义这三个 import.meta.env 字段。公开 URL 不允许认证信息、query、fragment 或非 loopback 主机。

[Verified] 新配置拒绝 `AGENT_OTLP_ENDPOINT`、`LANGCHAIN_*`、`LANGSMITH_*` 和旧 Grafana 前端字段；这些前缀也会从子进程继承环境移除。现有 LangChain 产品库仍用于 workflow/RAG，它与被移除的 LangSmith 外部 tracing 配置不是同一职责。

## 命令与受控切换

新模式必须同时提供三个文件；不支持通过额外覆盖参数改变它们。使用已有 Conda Python：

```powershell
$EzllmPython = 'D:\tool\anaconda3\envs\ezllmtest\python.exe'
$EzllmRunner = 'D:\codex\EzllmTest_v6\scripts\modular_runtime.py'
$EzllmSources = @(
    '--backend-env-file', 'D:\codex\EzllmTest_v6\backend\.env',
    '--frontend-env-file', 'D:\codex\EzllmTest_v6\frontend\.env',
    '--observability-env-file', 'D:\codex\EzllmTest_v6\observability\.env'
)
& $EzllmPython -B $EzllmRunner config-check @EzllmSources --format json
```

[Verified] config-check 仅解析及校验文件、字段、路径和拓扑，不探测数据库/Redis、不创建 run、不启动进程、不读取项目或调用模型。成功只返回配置模式和验证状态，不输出值。错误仅给已知字段名/类别。

[Approved] 本地切换及后续运行使用同一安全顺序：

1. 用相同三文件参数执行 preflight，进行 SELECT 1、information_schema 表名检查和 Redis PING；不查询业务行、不扫描 Redis、不执行 SQL 初始化。
2. 核对原 run 的 PID、创建时间、命令指纹、监听及工作树归属；若仍运行，确认空闲后用 stop --run-id 停止。当前原 run 已按此门禁停止。
3. 在维护窗口核对前端精确注入：envDir=false、envPrefix=[]、仅三个公开字段；不修改模型页面或重建依赖。
4. 用相同三文件参数执行 start；按 observability API → legacy API → Agent API → worker → frontend 顺序隐藏启动，并检查 CORS、ready、worker heartbeat 及只读页面。
5. 只用 Agent capabilities GET 生成一条不含项目内容的本地 Trace，再查询本地 overview/trace；不创建 Agent run，不执行生成、provider、embedding 或真实项目 E2E。已有实例/端口冲突时不得重复 start 或终止冲突占用者。

[Protected] preflight 不修改用户数据，但启动 worker 会正常维护 Redis heartbeat、消费已排队命令；所以任务空闲确认是实际门禁，不能把 start 描述为 Redis 全程只读。库/表/权限问题由用户单独处理，不自动迁移。

[Protected] [schema.sql](../../infrastructure/database/schema.sql) 含原始 DROP 语句，不可直接导入已有库；runner 不执行它。切换前失败保留旧服务；切换后失败仅处理已证明归属的新进程，不恢复旧秘密来源、不清理数据库或文件。

### 弃用的显式兼容模式

[Verified] --env-file、可选 --model-env-file / --moonshot-model / --frontend-port 保留，但与新模式互斥。兼容模式也使用同一字段清单和严格路径检查；不自动发现旧文件，不在新模式失败时回退。

[Verified] 旧模型专用来源仅提取固定 17 字段：四家的 API_KEY、BASE_URL、CHAT_MODEL、TIMEOUT_SECONDS，以及 ZHIPU_EMBEDDING_MODEL；重复或来源冲突停止，不跟随其 _FILE。只有显式 --moonshot-model kimi-k3 才在该模式合并后覆盖模型标识，不改原文件。新模式把模型标识直接写在 backend 配置中。

[Protected] 保留兼容参数不代表当前继续授权读取 V2 或旧秘密，本次不使用它们补齐新配置。

## 状态与安全停机

[Verified] status/ready/stop 只需要 run ID，无需打开 env。ready 从归属记录恢复实际端口和绑定主机，旧记录仍兼容。运行状态只记录进程身份、端口、配置模式等非敏感信息；不保存配置值或项目内容。现有日志不读取。

[Protected] Windows 进程命令行可能受终端权限边界限制。身份读取失败时 status/stop 必须失败关闭；应在启动进程的同一或等权 PowerShell 会话执行管理命令，不得退化为仅凭 PID 或端口认领进程。

```powershell
& $EzllmPython -B $EzllmRunner status --run-id '<run-id>' --format json
& $EzllmPython -B $EzllmRunner ready --run-id '<run-id>' --format json
& $EzllmPython -B $EzllmRunner stop --run-id '<run-id>' --format json
```

[Protected] stop 按 frontend → worker → Agent API → legacy API → observability API 逆序核对 PID/创建时间/指纹；归属不明时报告 ownership_unproven，不按进程名批量停止。旧四模块 state 仍按其真实成员安全处理，不虚构观测进程。MySQL、Redis、V2、上传和观测数据永不属于停止范围。

## 本地观测服务

[Verified] [观测服务说明](../../observability/README.md)定义 `iteration6-observability-v1`。公开接口只有 GET/OPTIONS；内部 spans/metrics/logs ingestion 使用 runner 每次启动生成的随机 token、256 条批次与 1 MiB 请求上限。token 只在三个子进程环境中存在，不进入 env、命令行、state、浏览器或日志。

[Verified] SQLite 仅位于 ignored 的 `observability/data`，保留 7 天，固定上限 spans 50000、metric points 30000、logs 20000。启动前验证版本、表和列；未知/未来/损坏数据库不重建。清理先按时间过期，再按完整 Trace 与最旧行缩减。

[Verified] Agent SDK 现使用本地 HTTP exporter。保存字段只来自静态允许清单；prompt、completion、reasoning、项目/文件/工具正文、SQL、Redis 内容、header/cookie、异常正文、traceback 和秘密均禁止。发送失败或队列满不阻断业务。健康/readiness 不生成 Agent Trace。

[Verified] `/observability` 无需项目 ID，十秒刷新且页面隐藏时暂停；失败保留最近有效快照。页面提供七项健康（含观测服务自身）、Agent 摘要、p50/p95、图表文字表、Trace 层级、安全日志、容量和脱敏导出状态。Agent 工作台只跳转到本地该页面。

[Verified] [PowerShell 包装](../../ops/modular/run.ps1) 新增 config-check，其他入口保留；[shell 包装](../../ops/modular/run.sh) 只保留兼容源码，本次不执行。Python/npm manifests 和 locks 不变化、不重新安装。

## Agent 模型和运行预算

[Verified] 修复后的规划通过可信逐次 model_label 参数使用界面选定模型，执行仍使用同一模型。Planner 固定 4096 Token、严格 JSON；K3 low，支持关闭思考的其他模型 off。不使用共享可变模型选择、不接受提示词/proposal 覆盖、不静默回退 GLM 或自动重试。该内部协议调整不改变 REST/SSE/MCP 请求结构。

| 预设 | 输入 Token 总限额 | 输出 Token 总限额 | 步数 / 时间 | 模型 / embedding 调用数 |
| --- | ---: | ---: | --- | --- |
| 聚焦 | 768000 | 393216 | 3 步 / 20 分钟 | 12 / 6 |
| 标准 | 2048000 | 1048576 | 8 步 / 45 分钟 | 32 / 16 |

[Verified] backend 的四个 AGENT_FOCUSED_MAX_*_TOKENS / AGENT_STANDARD_MAX_*_TOKENS 字段只控制新运行，不再从 workflow 最大值推导。工具次数仍等于步骤上限，合成成本额度等于输入加输出总额，不表示货币。原有调用前预留、审批、取消和幂等机制保留。

[Verified] 旧运行的预算、剩余展示、执行检查和审批绑定使用创建时持久化的 RunBudget。修改配置不重算旧预算，不改写 Redis checkpoint，不刷新已有运行。更大的单次 workflow 上限不会扩大 Agent 总额度。

[Verified] 历史事实更正：共享 workflow 上限首次调整时，`budget_for_preset` 会按 catalog 最大值乘调用次数，新运行额度也会增大；当前实现已固定上述总额并解除耦合，且没有把旧运行提升到新默认值。

## 验证语义

[Verified] 离线检查覆盖三文件/兼容模式隔离、四模型并发规划、实际 Agent 图停在审批、预算先于 provider I/O 拒绝、真实旧运行 projection 使用持久化限额，以及既有八类生成的合成保存/回滚/截断保护。所有外部依赖使用替身，未读取真实配置或用户内容。

[Verified] 本地观测、配置与运行器的离线合成场景、Vue type-check/ESLint/Prettier 和系统临时目录 production build 已通过；详细证据见 [Iteration 6 收口报告](../iteration-6-closeout.md)。业务服务 readiness 协议仍为 iteration5-readiness-v1，观测 API 使用 iteration6-observability-v1。

[Candidate] 2026-09-07 的逐项授权最小烟测完成一次合成项目 GLM 分析保存/恢复、一次有限 embedding 和一次 RAG 超时修复后的唯一成功重试；正文、向量和项目标识未进入仓库。

[Missing] 尚未执行压力/容量、客户项目、完整项目浏览器 E2E 或完整 Agent E2E。五模块 readiness、本地观测页、安全 Trace、production build 和有限真实烟测均不证明生产容量、模型质量或生产可用性。历史结论见 [验证历史](../validation-history.md)。

## 测试计划生成与失败提示

[Verified] DeepSeek 最终测试计划发送 thinking.enabled + reasoning_effort=high + max_tokens=16384；K3 保持 reasoning_effort=high + max_completion_tokens=8192，不发送旧 thinking 或 temperature。DeepSeek 官方实际有 low/high/max 三档，medium 是 high 的兼容别名；当前 high 已是三档中的中档，不能声称改成 medium 会减少推理。这是 project_analysis 的独立最终计划策略，不是八类通用测试用例的额度。

[Verified] 16384/8192 均为单次最终完成中思考加正文的共同上限，不是独立思考配额，不涵盖输入，也不是整个多调用工作流费用上限。DeepSeek 更大的完成量可能增加费用与延迟，仍可能用尽；不自动续写、重试或再次扩大额度。原 64000 输入上下文上限未扩大，并核对它与新完成预留仍在 DeepSeek model-spec 安全窗口内。

[Verified] K3 始终思考，因此项目摘要/结构化阶段也使用 low，保持 map=1024、structured=2048 的原上限，可能仍会因预算不足被明确拒绝保存。DeepSeek 项目摘要阶段仍关闭思考；GLM/Qwen 的 project_analysis 策略和预算不变。同步 K3 兼容入口也显式限制完成输出为 8192 或更小的 Agent 限额，不继承平台的大默认值。

[Verified] 项目分析缓存核对实际模型及对应策略：DeepSeek 使用 bounded-thinking-ds16k-v3，Kimi 保持 bounded-thinking-high-v2，因此既有 Kimi 缓存身份不变，旧 DeepSeek 8K 策略不会冒充新额度结果。旧有效计划不删除。保存函数明确允许并校验 model/generation_policy 这一对非敏感元数据及三个已实现策略，保留原三字段调用兼容性，同时拒绝未知字段或非法值。只有完整成功才原子提交 artifact 与三个兼容行。

[Verified] 此前“已生成但保存数据库失败”的确定代码原因是新增元数据未纳入保存函数白名单，实际在 Session 创建前被拒绝，并非该错误本身证明 MySQL 不可用。现已修复；无网络检查直接调用真实工作流和真实保存函数，仅将 Session 替换为事务模拟器，覆盖提交及回滚。没有读取业务行或更改数据库结构，也没有把当前页面未保存的内容自动补写进数据库。

[Verified] [Kimi 官方模型列表](https://platform.kimi.ai/docs/models) 已说明 K2.5 于 2026-08-31 停用并返回 404。[K3 参数](https://platform.kimi.ai/docs/guide/use-reasoning-effort)、[输出限制](https://platform.kimi.ai/docs/api/chat) 和 [DeepSeek 思考参数](https://api-docs.deepseek.com/guides/thinking_mode/) 是本次适配依据；这不证明当前账户权限、密钥、额度或真实网络生成成功。

[Verified] 流式适配器仅接受正常终止且有正文的响应；部分正文不能作为成功证据。失败不会替换当前有效版本，已收到的片段仅可作为未保存草稿保留。SSE 仍使用 code/message/status/retryable 四个字段，上游拒绝的 status 保持网关语义 502，原始 HTTP 状态以安全整数出现在提示中：

| 错误 code | 含义与处理 |
| --- | --- |
| output_truncated | 达到本次输出上限，未保存；调整生成模式或预算后再由用户重试 |
| empty_response | 正常结束但没有正文；没有把推理文字当答案 |
| incomplete_response | 没有正常终止或上游中断，可稍后由用户重试 |
| content_filtered / unexpected_output | 平台拦截或返回非预期输出，不自动重试 |
| provider_bad_request | HTTP 400/422，检查请求与模型参数兼容性 |
| provider_authentication / provider_permission | HTTP 401/403，检查密钥、平台、账户和模型权限 |
| provider_billing | HTTP 402，检查账户余额或计费状态 |
| provider_not_found / provider_input_limit | HTTP 404/413，检查模型/接口地址或输入限制 |
| rate_limit / provider_error | 限流或其他服务故障；按具体安全提示处理 |

[Protected] 不向页面回传上游原始异常、响应正文、密钥、请求头或项目资料；参数错误最多附白名单中的参数名称。不会为了取得更具体错误而自动重试或切换 provider。人工重试仍可能产生费用。

[Missing] 新错误分类不能追溯已经丢弃的历史 HTTP 状态。旧页面上的通用 provider 错误不证明具体拒绝原因；ready 也不验证密钥、余额或真实模型生成。

## 八类测试的共享输出预算

[Verified] UI 截图中的 12288 是 `_CASE_PROFILE` 的旧最终额度，先前的 DeepSeek 计划修复仅作用于 project_analysis。现只在 `backend/service/workflow/budget.py` 更新两项公共 phase profile，十个 analysis 和八个 case 操作一并生效，不在单页或路由硬编码。

| 范围 | 旧最终上限 | 当前最终上限 | 保持不变 |
| --- | ---: | ---: | --- |
| 单元/集成菜单与详情，API/UI/数据库/功能/非功能/验收分析（十个操作） | 8192 | 16384 | 输入上下文 32000 |
| 八类最终测试用例 | 12288 | 32768 | 输入上下文 16000 |
| 独立 project_analysis 最终计划 | DeepSeek 16384，K3 8192 | 不变 | 原缓存策略、摘要预算和输入上下文 |

[Verified] 通用 map=1024、structured=1536 保持不变，unit_menu 结构化特例仍为 12288；显式 caller 的更小上限继续优先。四模型仍受有限单次额度约束，context safety reserve 和输入范围不变。此前“Agent run 总预算不增加”的结论已更正：当时存在 catalog 推导耦合，Aspect 4 才将总额独立固定。多层 analysis reduce 沿用 analysis cap，不新增模型步骤或重试。

[Verified] 不关闭或增强原通用思考模式：DeepSeek final 为 enabled/high（low/high/max 的中档），小步骤 off；K3 通用阶段仍 low 且使用 max_completion_tokens，独立计划 final high 不变；GLM/Qwen 原适配策略不变。profile 中通用 reasoning_budget=4096 不是向 DeepSeek 或 K3 下发的独立思考限额，两者思考与正文共同消耗单次 completion 上限。

[Verified] SSE budget、实际请求与上下文计算均读取同一个 profile。已有有效 artifact 不清理、不因上限变化失效；用户显式重生成时才请求新结果。UI/数据库/验收用例仍持久化，原 session-only 操作仍不保存为跨会话 artifact。截断、取消和不完整结果不进入保存流程；事务失败保留旧状态。不自动把页面失败草稿补写到数据库。

[Verified] 无网络合成校验覆盖 228 个 profile/request/context 组合、216 个实际共享 stream 调用，以及八类实际 case dispatcher 的 DeepSeek/K3 请求；真实 artifact 序列化与保存函数使用事务 Session double，覆盖长正文、缓存恢复、更新、回滚、取消和截断。实际安装 SDK 通过内存 mock transport 校验请求字段。测试计划的既有模型分支回归也通过；没有真实项目或 provider 调用。

[Missing] 更大的上限可能增加等待时间和费用，并不保证正文一定完成，也不保证特定推理长度。上限不是整个多步骤工作流或输入费用上限。新额度在下一次生成生效；旧错误不会被自动清除。上述验证不代表真实数据库长结果落库、真实模型可用性或用户项目已成功生成。
