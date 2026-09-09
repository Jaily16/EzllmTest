# 项目说明与实现设计

> 当前对象：Iteration 7 源码。方面一至五已按各自范围完成；方面六本地收口完成，本提交用于普通快进发布。历史与本轮验收分别见[迭代历史](iteration-history.md#iteration-7)和[验证历史](validation-history.md#iteration-7)。

## 目录

- [产品与边界](#product)
- [三端与目录职责](#architecture)
- [工作流、模型与预算](#workflow-models)
- [协议、数据与安全](#contracts-data)
- [配置与角色隔离](#configuration)
- [分终端启动](#startup)
- [可选 runner 与维护](#maintenance)
- [开发与排错](#development)
- [中文说明与审阅规则](#chinese-comments)

<a id="product"></a>
## 产品与边界

EzllmTest 是本地软件测试工作台：项目资料登记与准备 → 业务分析、测试计划和推荐菜单 → 八类测试分析与用例生成。现有 Vue 状态方案、单 Agent、19 workflows 和 22 个类型化工具继续使用，不引入多 Agent 产品组织、Pinia 或新的 UI 框架。

普通页面读取不自动发起生成。付费模型调用、审批、重新生成及持久化有明确的业务触发和边界。失败、取消、截断、结构化输出错误及保存失败不覆盖上一份有效结果。当前验证不构成生产容量、安全认证、SLA 或客户项目质量证明。

<a id="architecture"></a>
## 三端与目录职责

| 顶层 | 唯一职责 | 当前内容与边界 |
| --- | --- | --- |
| backend | Python 产品实现与后端依赖 | src/ezllmtest 单一产品包、实际端内 tests、requirements 输入/平台 locks、pyproject；受保护项目数据原地保留 |
| frontend | Vue 产品与前端可执行工具 | app、features、entities、shared；所属资源随 feature 或 shared 管理；Vite/TypeScript/npm、端内 tests 和公开配置 tools |
| observability | 观测配置与数据所有权 | 示例配置、简明说明、受保护 SQLite；Python 查询与写入实现属于 backend |
| infrastructure | 当前有效声明 | 七表 SQL 和 runtime JSON；不放历史报告、秘密或前端可执行适配 |
| ops | 可选运维辅助 | modular_runtime.py 及 PowerShell/shell 包装；主启动说明使用分终端命令 |
| docs | 三份长期文档 | 本文件、iteration-history.md、validation-history.md；无子目录或图片 |

根 README 是简明入口，Git/语言/格式化等必要根文件继续保留。没有根 scripts、tests、migrations 或 skills；端内测试已有实际用例，其他目录只有存在真实职责时才新增。用户项目数据不属于可删除的旧源码残留。方面六经精确备份和消费者核验退出五份旧 frontend/src/assets 资源；根 .env.aspect3.local、依赖、缓存和已有构建目录均不因源码收口被删除。历史出处及更正见[方面六记录](iteration-history.md#iteration7-aspect6)。

后端的五个入口统一通过 bootstrap 显式装配，业务代码位于 modules/projects、knowledge、generation、agent、observability：

| 业务所有者 | 负责内容 |
| --- | --- |
| projects | 创建、资料登记、source revision、准备状态、项目 ORM/repository |
| knowledge | 文档读取、切分、索引复用、检索策略与项目隔离 |
| generation | workflow catalog、提示词、结构化结果、生成和有效 artifact 持久化 |
| agent | 图、规划、工具、审批、预算、执行、恢复、workbench 和 worker |
| observability | 本地查询 API、聚合、ingestion 和 SQLite 存储 |

entrypoints → bootstrap；bootstrap 装配 API、应用服务和具体 adapter。API → application；application → domain/ports 或其他模块的 public；infrastructure → ports/platform；platform → shared。跨域只经过所有者的稳定 public 操作及 DTO，不重新导出整套旧模块。

项目与产物 ORM 留在各自业务基础设施，通用 engine/session 创建由 platform/database 管理且延迟进行；数据根由显式 repo root 装配。Agent runtime 不直接依赖其他域的 repository、Redis 实现或 provider SDK。遥测 wire schema 和脱敏清单归 platform/telemetry，观测查询 schema 留在观测域。shared 仅放无 IO、无框架依赖的通用值与纯函数。

旧平面源码和 import facade 已退出，无 sys.path 注入或 sys.modules 别名。当前结构是有效实现的归属说明，不要求机械铺满 application/domain/ports 等模板目录。中文说明随职责迁移；函数拆分或 facade 删除后，不用旧函数总数作为必须相等的验收门槛。

前端页面归所属 feature/pages，testing/agent 已分别归 test-generation/agent-workbench；onboarding、planning 和其他页面也按职责归位。项目身份/准备状态、workflow 定义/状态、artifact 元数据和 Agent DTO 归 entities；HTTP、通用 SSE 和无业务含义的 UI 归 shared。通用 SSE 通过参数/回调交接业务状态，不导入 planning；跨 feature 展示用 props/events 或 app 装配，避免大范围 barrel 掩盖深层依赖。

<a id="workflow-models"></a>
## 工作流、模型与预算

项目创建与资料恢复保留部分上传成功结果，只重试未完成组。资料确认产生 source revision；初始分析成功后才开放测试工作区。菜单“推荐”与“可以进入”分开表达，重新生成期间旧有效正文可读，但下游执行受状态守卫约束。

全部 preliminary analysis 可持久化；unit_case、integration_case、api_case、functional_case、nonfunctional_case 五类 final 仅当前页面保留；ui_case、db_case、acceptance_case 三类 final 保存为 artifact。精确缓存身份包含项目、operation/artifact、资料 revision、提示词版本、模型标签及输入/选择摘要。改变 revision 或依赖后旧结果标为 stale；只有新结果完整保存成功才提升有效版本。

### 19 workflows 与长文本策略

资料在应用预算内时直接 stuff；需要全量抽取且超限时才分层 map-reduce。聚焦查询先项目隔离检索、去重和限额，再 stuff，不对已限制的检索结果二次 map。用例以已保存分析、选择和少量检索作 artifact-stuff，不重复装入全量文档。当前不使用 refine。

| 工作流 | 长文本来源 | 当前策略 | 超限处理和理由 |
| --- | --- | --- | --- |
| `project_analysis` | 全部需求与设计资料 | `stuff` ≤ 64K | 超限后分层 `map-reduce`；项目测试范围需要完整跨文档证据 |
| `unit_menu` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`；需要穷举模块、组件、类和服务 |
| `unit_info` | 所选单元相关设计资料 | `retrieval-stuff` | 先检索指定单元，避免无关模块占用上下文 |
| `unit_case` | 单元分析产物、方法选择、测试知识 | `artifact-stuff` ≤ 16K | 不重新读取全量设计资料 |
| `integration_menu` | 已保存的单元菜单；缺失时为全部设计资料 | `artifact-stuff`；回退全量时 `stuff` ≤ 32K | 全量回退超限后分层 `map-reduce` |
| `integration_info` | 系统/子系统选择为全设计；具名对象为相关设计 | 全量 `stuff` ≤ 32K；具名对象 `retrieval-stuff` | 只有系统级穷举超限时分层 `map-reduce` |
| `integration_case` | 集成对象分析、策略选择、测试知识 | `artifact-stuff` ≤ 16K | 依赖规范化上游产物，不重复全量设计资料 |
| `api_info` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，用于穷举 API |
| `api_case` | API 分析产物；指定 API 时补充相关设计 | `artifact-stuff` + `retrieval-stuff` | 只检索选中 API，不对检索结果再 map |
| `ui_info` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，用于穷举页面和交互 |
| `ui_case` | UI 分析产物和测试知识 | `artifact-stuff` ≤ 16K | 不重复全量设计资料 |
| `db_info` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，使用数据库语义切分器 |
| `db_case` | 数据库分析产物和测试知识 | `artifact-stuff` ≤ 16K | 不重复全量设计资料 |
| `functional_info` | 全部需求资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，用于穷举用例和业务规则 |
| `functional_case` | 功能分析产物；指定用例时补充相关需求 | `artifact-stuff` + `retrieval-stuff` | 只检索选中用例，不对检索结果再 map |
| `nonfunctional_info` | 与性能、安全、兼容性等问题相关的需求 | `retrieval-stuff` | 这是聚焦问题，不应摘要全部需求后再回答 |
| `nonfunctional_case` | 非功能分析产物、方法选择和测试知识 | `artifact-stuff` ≤ 16K | 只合并所选方法需要的上下文 |
| `acceptance_info` | 全部需求资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，保留验收条件覆盖 |
| `acceptance_case` | 验收分析产物和测试知识 | `artifact-stuff` ≤ 16K | 不重复全量需求资料 |

所有需要结构化列表或菜单的流程仍可能在正文分析后增加一次结构化解析调用；这不是第二次长文档分析。相同文档版本和选择命中完整产物缓存时，恢复路径保持 0 次模型调用和 0 次 embedding 构建。

应用预算与供应商宣称窗口不同：项目级全量输入 64000、其他全量分析 32000、用例输入 16000 Token；每次请求继续为输出、思考与安全余量预留空间。具名单元使用规范化 qualified reference，避免同名类/模块混淆。菜单判断基于资料中的实际测试对象和证据，不能把某类系统的特征机械要求到所有项目。

### 模型与单次请求

模型标识由统一注册及选择实现维护；本项目已接入智谱、阿里云百炼、DeepSeek、Moonshot。真实可用性与费用不由配置存在或历史烟测推导。

Agent planner 通过可信 model_label 使用界面选定模型，执行沿用该模型；不允许提示词/proposal 覆盖、不使用共享可变选择、不静默回退 GLM。Planner 4096 Token 严格 JSON，K3 low，其他支持关闭思考的规划适配为 off。

当前 project_analysis 最终计划：DeepSeek thinking.enabled、reasoning_effort=high、max_tokens=16384；K3 reasoning_effort=high、max_completion_tokens=8192，不发送旧 thinking/temperature。项目摘要 map=1024、structured=2048；K3 low，DeepSeek off。上述是本项目实现参数，不是实时供应商能力或价格核验。

通用十个 analysis 操作的最终输出上限为 16384，八个 case 为 32768；输入分别保持 32000/16000。通用 map=1024、structured=1536，unit_menu 结构化特例 12288；调用方显式更小的限制继续优先。通用 DeepSeek final high、小步骤 off，通用 K3 low；项目最终计划的 high 单独处理。思考与正文共同消耗单次 completion 上限，不把 reasoning_budget=4096 描述为向这两家单独下发的思考配额。

较大额度不会自动续写、重试、清理旧 artifact 或把失败草稿补存为成功。已有有效结果保留，新额度在下一次明确生成时生效。

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


错误信封仍使用 code/message/status/retryable；上游拒绝保留网关 502 语义，原始 HTTP 状态只以安全整数展示。旧已丢弃状态不可追溯，不打印响应正文或自动切换供应商。

### Agent 总预算

| 预设 | 输入 Token 总限额 | 输出 Token 总限额 | 步数 / 时间 | 模型 / embedding 调用数 |
| --- | ---: | ---: | --- | --- |
| 聚焦 | 768000 | 393216 | 3 步 / 20 分钟 | 12 / 6 |
| 标准 | 2048000 | 1048576 | 8 步 / 45 分钟 | 32 / 16 |

四个 AGENT_FOCUSED_MAX_*_TOKENS / AGENT_STANDARD_MAX_*_TOKENS 字段只控制新运行。旧运行使用创建时持久化的 RunBudget；修改配置或单次 workflow 限额不能扩大旧预算。工具次数仍受步骤上限约束，合成成本额度不是货币。调用前预留、审批绑定、取消与幂等规则继续生效。

<a id="contracts-data"></a>
## 协议、数据与安全

保持现有 REST 方法、路径、请求/响应字段和错误信封；SSE 的恢复游标、heartbeat、取消、截断及完成/保存顺序保持。MCP tools/resources、显式 project scope、审批与错误响应保持。协议清单由现有端内测试及 fixture 核对，不能用静态装饰器数量替代实际注册契约。

可信项目 scope 由宿主注入，模型或 MCP payload 不得覆盖 scope、审批、幂等键或预算。付费、持久化、regenerate 审批绑定 plan/project/revision/model/arguments/context/budget，变化或过期即失效。Checkpoint 使用严格 JSON；恢复检查 fencing、幂等及已有 artifact，不确定的 session-only 结果进入 outcome_unknown，不自动重复付费。

MySQL 长期保存项目及有效结果；Redis 保存 checkpoint、queue、lease、幂等、取消与重放等瞬态协调信息；SQLite 只保存脱敏本地观测。用户项目仍在 backend/static/projects，不随源码层级或当前 CWD 改变。

[infrastructure SQL](../infrastructure/database/schema.sql) 是七张表的声明式结构，包含 DROP TABLE IF EXISTS，不能直接在已有用户数据库执行。当前方面不初始化或迁移数据库。已有数据库变更需要单独明确目标、备份、停写窗口和审核后的 DDL。

观测 ingestion 批次上限 256 条、请求上限 1 MiB；外部查询只读。原地 SQLite 保留 7 天、总上限 100000 行，分别为 spans 50000、metrics 30000、logs 20000；先按时间清理，再按完整 Trace 与最旧行缩减。未知/未来/损坏数据库不自动重建。

不保存 prompt、completion、reasoning、项目/文件/工具正文、SQL/Redis 内容、header/cookie、异常正文、traceback、凭据或连接串。exporter 与 ingestion 均检查白名单；队列满或发送失败不阻断业务。观测启动会正常维护 SQLite，不能将启动验收描述为数据库字节不变。

<a id="configuration"></a>
## 配置与角色隔离

只有三个显式本地配置来源，示例见 [backend](../backend/.env.example)、[frontend](../frontend/.env.example)、[observability](../observability/.env.example)。真实 .env 不进入 Git、截图、备份包或开发记录；本项目的 manifests/locks/runtime 声明不是新的秘密来源。

| 角色 | 可读取来源 |
| --- | --- |
| 产品 API | backend、frontend |
| Agent API | backend、frontend、observability |
| worker | backend、observability |
| MCP | backend；启用遥测时显式提供 observability |
| 观测 API | observability、frontend；不读取 backend 秘密 |
| 前端 | 仅 frontend |

入口先校验绝对 repo root 和明确配置路径，再装配应用；--help 不读配置或连接依赖。不搜索替代 .env，不展开变量或执行配置文本。继承的冲突应用配置清理后，以显式文件为准；不修改 Windows 用户/系统环境。

加载器拒绝重复/未知/跨角色字段、必填缺失、非法类型、端口/端点/CORS 不一致、重复来源及 reparse/越界路径。DATABASE_URL 和四家 API_KEY 可使用对应 _FILE，但直接赋值与 _FILE 不能并存；config-check 仅校验引用路径，实际运行才按原有单行 UTF-8、8192-byte 限制读取。错误只给字段名/类别，不回显值。

前端只暴露 VUE_APP_API_BASE_URL、VUE_APP_AGENT_API_BASE_URL、VUE_APP_OBSERVABILITY_API_BASE_URL；FRONTEND_PORT 仅供启动工具使用。Vite 的 envDir=false、envPrefix=[]，不自动加载 dotenv。公开 URL 仅 loopback，不允许认证信息、query 或 fragment。

Windows 观测进程创建随机内存 token 和命名管道，显式 DACL 限制当前登录会话、拒绝远程、排他创建。生产者核对账户、会话、规范化工作根、端点与协议身份，使用有界 IO 和确认；句柄不可继承。重启更换 token，发送失败后丢弃缓存并有界重取。token 不进入环境、命令参数、文件、state、日志或浏览器。

<a id="startup"></a>
## 分终端启动（Windows 单进程）

[Verified] 方面三已使用原地三个配置文件验证以下独立入口，不回写配置。worker 按下述不消费模式验收，正常任务消费未验证；结果见[验证历史](validation-history.md#iteration-7)。产品包注册方法见[开发说明](#development)。

### 终端一：观测 API

```powershell
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -B -m ezllmtest.entrypoints.observability_api --repo-root 'D:\codex\EzllmTest_v6' --observability-env-file 'D:\codex\EzllmTest_v6\observability\.env' --frontend-env-file 'D:\codex\EzllmTest_v6\frontend\.env'
```

### 终端二：产品 API

```powershell
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -B -m ezllmtest.entrypoints.product_api --repo-root 'D:\codex\EzllmTest_v6' --backend-env-file 'D:\codex\EzllmTest_v6\backend\.env' --frontend-env-file 'D:\codex\EzllmTest_v6\frontend\.env'
```

### 终端三：Agent API

```powershell
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -B -m ezllmtest.entrypoints.agent_api --repo-root 'D:\codex\EzllmTest_v6' --backend-env-file 'D:\codex\EzllmTest_v6\backend\.env' --frontend-env-file 'D:\codex\EzllmTest_v6\frontend\.env' --observability-env-file 'D:\codex\EzllmTest_v6\observability\.env'
```

### 终端四：worker 不消费验收

```powershell
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -B -m ezllmtest.entrypoints.agent_worker --repo-root 'D:\codex\EzllmTest_v6' --backend-env-file 'D:\codex\EzllmTest_v6\backend\.env' --observability-env-file 'D:\codex\EzllmTest_v6\observability\.env' --consumer local-acceptance-worker --no-consume
```

`--no-consume` 只检查 Redis 连接并写入独立、有 TTL 的验收心跳，不读取队列、不创建消费组、不认领/确认任务、不装配模型执行能力。增加 `--once` 可执行一次后退出。启动状态明确显示 `worker mode=no-consume`，退出后心跳自然过期。

验收心跳不加入正常 worker 集合。因此，没有正常 worker 时，Agent `/ready` 返回 503、观测页显示 worker 不可用，均不代表本次连接验收失败。需要处理真实任务时，在明确允许消费已有队列的独立运行阶段移除 `--no-consume`，并使用不同 consumer；普通 worker 可能立即处理历史任务，本次验收没有启动该模式。

### 终端五：前端

```powershell
Set-Location -LiteralPath 'D:\codex\EzllmTest_v6\frontend'
npm run serve -- --env-file 'D:\codex\EzllmTest_v6\frontend\.env'
```

构建命令为 npm run build -- --env-file <前端配置绝对路径>。Vite 禁用自动 dotenv 加载，仅三个公开 URL 进入浏览器，端口只供工具使用。

### Uvicorn 与 MCP

三个 API 均支持单进程 Uvicorn :app。以产品 API 为例，在新的独立终端设置只承载路径的选择器：

```powershell
$env:EZLLMTEST_REPO_ROOT = 'D:\codex\EzllmTest_v6'
$env:EZLLMTEST_BACKEND_ENV_FILE = 'D:\codex\EzllmTest_v6\backend\.env'
$env:EZLLMTEST_FRONTEND_ENV_FILE = 'D:\codex\EzllmTest_v6\frontend\.env'
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -m uvicorn ezllmtest.entrypoints.product_api:app --host 127.0.0.1 --port 8230
```

Agent API 选择 backend/frontend/observability；观测 API 只选择 observability/frontend，不能带 backend 选择器。以下命令分别在新终端使用，不继承其他角色的选择器：

```powershell
# Agent API 的独立 Uvicorn 终端
$env:EZLLMTEST_REPO_ROOT = 'D:\codex\EzllmTest_v6'
$env:EZLLMTEST_BACKEND_ENV_FILE = 'D:\codex\EzllmTest_v6\backend\.env'
$env:EZLLMTEST_FRONTEND_ENV_FILE = 'D:\codex\EzllmTest_v6\frontend\.env'
$env:EZLLMTEST_OBSERVABILITY_ENV_FILE = 'D:\codex\EzllmTest_v6\observability\.env'
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -B -m uvicorn ezllmtest.entrypoints.agent_api:app --host 127.0.0.1 --port 8231
```

```powershell
# 观测 API 的独立 Uvicorn 终端
$env:EZLLMTEST_REPO_ROOT = 'D:\codex\EzllmTest_v6'
$env:EZLLMTEST_FRONTEND_ENV_FILE = 'D:\codex\EzllmTest_v6\frontend\.env'
$env:EZLLMTEST_OBSERVABILITY_ENV_FILE = 'D:\codex\EzllmTest_v6\observability\.env'
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -B -m uvicorn ezllmtest.entrypoints.observability_api:app --host 127.0.0.1 --port 8140
```

这三种 `uvicorn :app` 命令是等价入口说明；方面三真实验收使用上面的 `python -m` 入口，没有另行复跑三组 Uvicorn 命令。只支持单进程，不加 `--reload` 或多 worker。

worker 和 MCP 不读取 frontend。MCP 使用 python -m ezllmtest.entrypoints.mcp_server，要求 --repo-root、--backend-env-file、--project-id；可选 --observability-env-file 复用遥测，scope 由操作人明确提供。runner 不启动 MCP，方面三未启动连接真实项目的 MCP。

[Protected] 观测端以当前登录 SID 的显式 DACL 创建排他命名管道，拒绝远程客户端。生产者验证账户、登录会话、工作根和端点绑定；读写及接收确认均有超时，句柄不可继承。重启更换内存 token，生产者在失败后丢弃缓存并有界重取；失败只影响观测。token 不进入环境变量、文件、命令参数、日志、state 或浏览器。

[Missing] 方面三只支持 Windows 单进程共享；不宣称 Linux、Uvicorn reload 或多 worker 已实现/验证。普通终端以 Ctrl+C 结束本终端进程；runner 仅管理自己创建且身份核验通过的进程。

<a id="maintenance"></a>
## 可选 runner 与维护

[runner](../ops/modular_runtime.py) 和 [runtime 声明](../infrastructure/runtime/modular-runtime-contract.json) 只负责本项目进程。runner 是可选便利工具；本轮方面三真实验收采用独立终端，没有把 runner 启动当成其证据。

```powershell
$EzllmPython = 'D:\tool\anaconda3\envs\ezllmtest\python.exe'
$EzllmRunner = 'D:\codex\EzllmTest_v6\ops\modular_runtime.py'
$EzllmSources = @(
    '--backend-env-file', 'D:\codex\EzllmTest_v6\backend\.env',
    '--frontend-env-file', 'D:\codex\EzllmTest_v6\frontend\.env',
    '--observability-env-file', 'D:\codex\EzllmTest_v6\observability\.env'
)
& $EzllmPython -B $EzllmRunner config-check @EzllmSources --format json
& $EzllmPython -B $EzllmRunner preflight @EzllmSources --format json
```

config-check 只校验配置，不探测依赖或启动进程。preflight 使用 MySQL SELECT 1、表名元数据和 Redis PING，不查询业务行或扫描队列。失败时解决明确问题，不改端口或停止未知占用者。

runner start 会启动普通消费 worker，不等于 --no-consume 验收。只有明确允许处理现有队列的维护窗口才执行：

```powershell
& $EzllmPython -B $EzllmRunner start @EzllmSources --format json
& $EzllmPython -B $EzllmRunner status --run-id '<返回的 run-id>' --format json
& $EzllmPython -B $EzllmRunner ready --run-id '<返回的 run-id>' --format json
& $EzllmPython -B $EzllmRunner stop --run-id '<返回的 run-id>' --format json
```

启动顺序为观测、产品、Agent、worker、前端，退出相反。独立终端用各自 Ctrl+C；runner 仅管理自己记录的进程，按 PID、创建时间、命令指纹和工作树归属检查。身份不可读时以 ownership_unproven 失败关闭，不按端口或进程名批量停止，不认领独立终端进程。旧四模块 state 按真实成员处理。MySQL、Redis、V2 和数据不归 runner 停机。

当前数据、已有日志与备份原地保护；源码清理不能递归吞并它们。开发固定在 V6，不新建 worktree 或 D:\codex 顶层目录。Iteration 7 备份只追加到 V2 的 _archive/iteration-7 独立批次，先列精确白名单再复制，禁止把依赖、秘密或整个工作树打包。

<a id="development"></a>
## 开发与排错

依赖真源是 [requirements.in](../backend/requirements.in)、Linux/Windows locks、[pyproject](../backend/pyproject.toml) 和 [npm manifest](../frontend/package.json)/lock。旧版本 JSON 仅有[历史出处](iteration-history.md#historical-sources)，不再是执行真源。Python 包依赖声明复用 requirements.in，不维护第二套独立版本表。

方面三记录的环境为既有 Conda Python 3.11.15、Node 24.18.0/npm 11.16.0。当前仍有八项 Python 安装/声明差异，见[验证限制](validation-history.md#iteration-7)；这些是本机历史核对值，不声称其他机器环境相同，不在文档归并中安装或修复。

若本项目尚未注册且已具备兼容依赖，可按原有授权方式离线注册 editable 包；该命令不会解析或升级依赖：

```powershell
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -m pip --isolated install --no-index --no-deps --no-build-isolation --no-cache-dir --no-compile --editable 'D:\codex\EzllmTest_v6\backend'
```

本轮未执行安装。Windows IPC 使用已固定的 pywin32==312；Linux lock/shell 包装保留不代表 Linux 独立 token 共享已验证。

| 现象 | 处理边界 |
| --- | --- |
| 找不到 ezllmtest 包 | 核对所用 Python 与 editable 注册位置，不能 sys.path 注入或创建旧 facade |
| 配置错误 | 按字段类别检查明确来源、角色和路径，不打印真实值或自动搜索其他 .env |
| 端口冲突 | 记录归属并停止该启动，不改端口、不按端口杀进程 |
| Agent /ready=503 | 区分 Redis 不通与无正常 worker；不消费验收不能证明任务可执行 |
| 观测不可用 | 核对同一登录会话、根/端点和观测进程；不得关闭 ingestion 鉴权 |
| 生成失败或截断 | 保留旧有效结果，不把草稿写成成功；明确重试的成本与作用域 |
| 现有数据库需变更 | 独立审核 DDL 和保护方案，不执行初始化 SQL 覆盖现库 |

端内真实测试位于 backend/tests、frontend/tests；离线后端禁止真实网络和受保护资料访问，pytest 禁用无关自动插件。默认验收分别记录离线覆盖、浏览器验证和未验证，不以 readiness 替代完整 Agent 旅程。中文注释说明职责、调用关系、状态转换和安全约束；方面五按下述规则补齐和改进说明，验证结果单独记录。

<a id="chinese-comments"></a>
## 中文说明与审阅规则

说明以职责为单位，回答实际需要的问题：谁调用、依赖谁、输入的业务含义、状态如何变化、何时产生 IO，以及失败或取消后保留什么。公共接口、应用服务和关键状态转换必须有说明；重复函数名、泛称“遵循现有契约”或复制签名不能代替这些信息。

- 普通取值、纯转换、匿名展示回调和纯数据测试替身可以豁免单独 docstring，但必须有具体理由和所属逻辑块说明。IO、鉴权、预算、审批、保存、取消、重放、队列、token 与进程归属不因代码短而豁免。
- 接口声明与实现共同解释能力和副作用；重载及协议方法逐项分类，不因为没有执行体就整组忽略。类型签名和公开 DTO 不变，函数拆分或退出重复 facade 后不要求总数与旧结构相同。
- 只将 AST 识别的模块、类、函数首部字符串视为 docstring。提示词、普通三引号字符串、错误消息及命令参数属于运行内容。Pydantic/schema 类说明、FastAPI/MCP 公开描述和其他被消费的说明冻结，需要解释时添加相邻普通注释。
- TypeScript/JSDoc 类型指令、lint/覆盖率标记、许可证及 shebang 保留。Vue 说明主要放在 script 内，template/style 块保持原字节；SQL 的 MySQL 可执行版本注释不能当作普通注释处理。
- 测试说明写清人工场景、替身隔离和断言意图；不把测试通过扩大为真实配置、模型或正常 worker 消费已验收。离线 Python 子进程统一临时 PYTHONUTF8=1，避免仅给父进程 -X utf8 造成输出解码差异。
- 修改后比较 Python 执行 AST、完整公开 schema/工具元数据和 TypeScript/Vue 结构；格式检查只处理本次注释引入的问题，不顺带重排代码。发现行为问题只登记，不在注释任务中修复。

方面五的逐文件、逐节点清单与验证结果见[验证历史](validation-history.md#iteration7-aspect5)。中文 docstring 数只用于筛查，已有有效说明、补充、重写与具体豁免分别记录；类说明、普通注释和调用方边界不能用一个函数计数取代。
