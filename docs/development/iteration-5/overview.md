# EzllmTest Iteration 5：工程治理、结构收敛与双模式交付

> **状态：Aspect 8 已执行但未完成（Blocked）。** Iteration 1–4 已完成并以 Iteration 4 的离线门禁、隔离真实模型合成 E2E 和托管 CI 作为当前产品基线。Iteration 5 不增加新的测试业务能力，目标是把经过多次迭代形成的仓库收敛为结构清晰、版本一致、规范统一、可维护且可用两种方式部署的长期工程。

本文只定义方面级路线、依赖顺序、保护边界和退出条件，不细分 task。每个 Aspect 必须在新的计划回合中单独设计、经确认后单独实施，不能跨 Aspect 顺手重构。

## 1. 状态标签

- **Verified**：已由当前代码、manifest、目录结构或 Iteration 4 收口证据核实。
- **Protected**：Iteration 5 必须保持的产品、数据、安全或交付契约。
- **Candidate**：看起来可能是垃圾、重复、旧命名或可合并内容，但尚未完成引用与运行证据审计，不能直接删除。
- **Approved**：本次迭代已经确认的工程治理方向。
- **Proposed**：需要在对应 Aspect 的计划中完成取舍、兼容性验证和回滚设计。
- **Missing**：当前仓库尚缺少、且本次迭代需要补齐的工程能力。

## 2. 迭代目标

Iteration 5 将围绕四个结果收敛仓库：

1. **清洁：** 清理本地生成物、无引用资产、重复实现、失效兼容层和迭代期临时代码，同时保护真实配置、用户项目、数据库、Redis 数据和历史验收证据。
2. **统一：** 建立可机器校验的运行时与依赖版本契约，只保留一份面向人的版本说明，消除 README、注释、Compose、Dockerfile 和 CI 之间的版本漂移。
3. **规范：** 统一 Python、TypeScript/Vue、配置、测试和文档风格；公共模块和复杂业务约束使用充分、准确的中文说明，同时保持标识符、协议字段和第三方术语的行业惯例。
4. **可交付：** 形成完整 Docker 容器运行方式，以及数据库、Redis、后端、Agent、前端和可选观测组件按步骤分模块运行的方式，并用同一验收契约验证两种拓扑。

目标不是把所有历史痕迹从 Git 历史中抹除，而是让当前生产源码、运行入口、镜像名、测试组织和主文档体现稳定产品结构。Iteration 1–4 的过程资料可以归档，但不得伪装成从未发生或丢失可审计证据。

## 3. 当前已核实的工程基线

### 3.1 可复用基础

- **Verified — 产品：** 19 个 workflow、22 个类型化工具、legacy API、独立 Agent API/worker、Agent 工作台、loopback MCP、RAG、Eval、benchmark 和 OpenTelemetry 已完成 Iteration 4 收口。
- **Verified — 后端：** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy 2、LangGraph、Redis、MySQL 和严格 JSON checkpoint 是当前主线。
- **Verified — 前端：** Vue 3、TypeScript、Vue Router、Element Plus、Vite、ESLint 和 vue-tsc 是当前主线。
- **Verified — 交付：** 根 `compose.yaml`、前后端 Dockerfile、GitHub Actions、Prometheus、Tempo 和 Grafana 已存在；本地也保留逐进程启动命令。
- **Verified — 质量：** 当前基线包含完整 pytest、Agent Eval/Acceptance/Benchmark、credential scan、前端 lint/type-check/build 和 Compose 契约。

### 3.2 已观察到的治理问题

- **Verified — 本地生成物：** 工作目录中可见多个被忽略的 `__pycache__`/`.pyc` 等运行缓存。它们是本地清理候选，不应与 Git 跟踪文件或用户数据混为一类。
- **Verified — 版本表面分散：** Python 依赖、npm 依赖与锁文件、Python/Node 基础镜像、数据库/Redis/观测镜像、GitHub Actions SHA、README 版本文字和源码注释分别保存版本信息，缺少统一漂移检查。
- **Verified — 迭代命名进入活跃工程：** requirements 注释、容器镜像 tag、大量测试和 fixture 使用 `iteration4`/`aspect` 命名。历史证据可以保留这种命名，但活跃运行产物和长期模块不应依赖迭代号表达职责。
- **Verified — 后端目录偏平：** `service/` 同时包含 workflow、Agent runtime、工具、RAG、Eval、可观测性和工作台存储等多类职责，长期维护时边界不够直观。
- **Verified — 前端存在审计候选：** 旧 logo/测试类型图片并存，存在 `HelloWorld.vue`、`FounctionalTest.vue` 等旧模板或命名候选；是否删除或改名必须先证明路由、动态 import、样式和测试均无依赖。
- **Verified — 文档以迭代为主：** `docs/` 根目录保留大量按迭代命名的路线、契约和日志，历史价值明确，但长期运行手册、架构说明和版本说明需要从历史资料中独立出来。
- **Missing — 统一治理工具：** 当前没有一套同时检查 Python 格式、中文说明覆盖、目录边界、重复代码、孤立资产、版本漂移和两种部署拓扑的稳定门禁。

这些观察只说明需要审计，不等于已证明某个文件无用。文件名带有 `legacy`、`iteration`、`old`，或者文件处于 ignored 状态，都不能单独作为删除依据。

## 4. 全局保护契约

Iteration 5 的清理和重构必须继续保护：

- 19 个 workflow 的 operation、顺序、前置依赖、payload、预算和 persistence 语义。
- 22 个类型化工具的风险、审批、项目作用域、幂等、取消和 retention 语义。
- legacy 与 Agent 公共路由、REST 响应信封、SSE wire format 和 MCP 对外 schema。
- revision-aware artifact/cache、RAG 索引复用、Token/上下文预算、stale、取消、延迟保存、失败回滚和 regeneration lock。
- 所有 preliminary analysis 持久化；五类 session-only final 与三类 persisted final 的边界。
- MySQL 是项目、revision 和有效 persisted artifact 的长期真源；Redis 只保存 Agent 短期运行状态和 session-only 证据。
- 严格 JSON checkpoint、HITL 审批、零审批绕过、零重复副作用和零跨项目泄漏。
- 页面加载零隐式付费调用；Agent 不保存、不返回、不展示 chain-of-thought。
- 当前离线 Eval、安全、可靠性、性能、bundle 和 credential 门禁。
- 真实 `.env`、上传项目、MySQL 数据目录、Redis/观测卷、API Key、截图和本地运行产物不得被读取、移动、删除或提交。

如果结构整理必须改变公共 wire、数据库 schema、retention、工作流真源或真实项目存储位置，必须停止并提交独立迁移方案，不能隐藏在“清理”或“格式化”中。

## 5. 清理与保留分类

Aspect 1 必须先建立清理清单，后续 Aspect 只能对清单中的精确对象操作：

| 分类 | 含义 | 默认动作 |
| --- | --- | --- |
| Protected user data | `.env`、上传资料、数据库/Redis/观测卷、用户截图与本地 IDE 状态 | 不读取、不删除、不移动 |
| Protected product asset | 源码、schema、公共契约、有效 fixture、运行配置 | 保留；变更需测试与迁移证据 |
| Historical evidence | Iteration closeout、manifest、门禁与真实验收记录 | 保留内容；可在链接校验后归档位置 |
| Generated disposable | `__pycache__`、`.pyc`、pytest/cache、临时 build、coverage、日志等 | 证明位于允许目录后可精确清理 |
| Duplicate candidate | 重复图片、重复封装、重复版本说明、相似组件 | 引用、内容和行为对比后决定合并 |
| Legacy candidate | 旧模板、兼容层、拼写错误命名、迭代期入口 | 调用图和回归证明无依赖后迁移或删除 |
| Unknown | 来源或用途无法确定的内容 | 保留并升级为人工确认项 |

清理必须区分仓库 tracked 内容、本地 untracked/ignored 内容、Docker 容器/镜像、命名卷和外部数据库。任何递归删除都要先解析绝对路径、限制在允许根目录并输出 dry-run 清单；普通 Compose 命名卷和用户已有容器永不作为默认清理对象。

## 6. 版本统一原则

Iteration 5 所说的“只保留一份版本说明”不意味着删除 package manager 必需的版本声明，而是建立以下分层：

- Python、npm、Docker 和 GitHub Actions 的可执行 manifest/lock/digest 继续作为各自安装与运行真源。
- 新增一个可机器读取的跨工具链版本契约，统一 Python、Node、npm、MySQL、Redis、Compose、基础镜像和关键框架的兼容组合。
- 只保留一份面向人的版本与升级策略文档，并从可执行真源生成或校验；README 只链接该文档，不再手工重复精确版本表。
- CI 必须检查 manifest、lock、Dockerfile、Compose、Actions 和版本文档是否漂移。
- Python 需要形成可重复解析的直接/传递依赖锁定证据；npm 继续以 lockfile 和 `npm ci` 为准；Docker 镜像继续使用不可变 digest。
- 每次升级必须先做 resolver/import/build/Compose spike，再更新 manifest；不能为了“最新”一次性升级全部包，也不能保留两个互相冲突的版本说明。

具体采用 `pyproject.toml`、requirements 分层或其他锁定工具，由 Aspect 2 基于当前官方支持、Windows/Ubuntu 兼容性和回滚成本决定，本 overview 不预先锁定工具。

## 7. 代码风格与中文说明原则

- Python、TypeScript/Vue、YAML/JSON、Markdown 分别使用统一 formatter/linter；格式化与语义修改分批，避免无法审查的大型混合 diff。
- Python/TypeScript 标识符、类名、函数名、协议字段、CLI 参数、日志 event 和第三方 API 名称保持英文，避免破坏生态和 wire compatibility。
- 面向维护者的模块说明、公共类/函数 docstring、复杂状态机、审批/幂等/租约/预算、数据保留与安全不变量使用准确中文。
- 注释解释“为什么、边界和失败后果”，不逐行翻译代码，不保留过期的 Iteration/Aspect 叙事，不把 prompt、凭证或用户正文写入示例。
- 对纯 getter、显而易见赋值和框架模板不强制冗余注释；“注释充分”通过公共 API 覆盖和复杂规则覆盖衡量，而不是按注释行数衡量。
- 前后端命名、错误码、状态枚举和术语建立统一词汇表；拼写修复必须同步 import、路由、测试和文档。

## 8. 目标仓库形态

Iteration 5 不要求为追求“整齐”进行一次性全仓搬迁，而是遵循以下结构原则：

- 活跃后端按领域与职责组织，例如 workflow、agent、retrieval、artifacts、platform/telemetry、delivery 等边界；入口、应用服务、领域契约和基础设施适配器不再混放在单一平面目录。
- 活跃前端按功能域组织 Agent、项目 onboarding、规划、测试工作区和共享 UI；共享组件必须真正被多个功能使用。
- 测试目录镜像产品边界，区分 unit、contract、integration、acceptance 与 fixtures；历史 release fixture 与当前回归 fixture 分区。
- 长期文档独立为 architecture、operations、development、security、versions 等主题；Iteration 1–4 过程文档移动时保留内容、hash、链接重定向或映射。
- 生产镜像、服务名、模块名和入口不包含 `iteration4-aspect7` 等迭代标签；版本由产品 release/version 契约表达。
- 合并重复实现优先于建立新的抽象层；只有两个以上稳定调用方且语义一致时才提取共享模块。

最终精确目录树必须由 Aspect 4–5 基于 import graph、循环依赖、文件规模和变更成本提出，并包含分阶段迁移与兼容 shim 的删除时点。

## 9. 八个实施方面

### Aspect 1 — 基线盘点、资产分类与安全清理边界

冻结 Iteration 4 的 Git、接口、数据、依赖、性能和交付基线；生成 tracked/untracked/ignored、容器/卷和外部数据的分类清单；建立 dry-run 清理规则、保护 allowlist、引用审计方法和回滚边界。只清理已证明可再生且位于安全范围内的本地缓存，不删除源码候选。

**退出条件：** 每个候选都有分类、来源、大小、引用证据、拟议动作和恢复方式；用户数据与未知内容零触碰；清理前后 Git 与完整门禁一致。

### Aspect 2 — 依赖收敛与单一版本契约

核对 Python、Node/npm、前后端框架、Docker images、Compose 和 GitHub Actions 的当前官方支持与兼容交集；建立机器版本契约、唯一人类版本说明、可重复锁定和漂移检查；删除过期的手工版本注释和迭代式镜像标签。

**退出条件：** 干净环境解析、`pip check`、`npm ci`、镜像解析和完整测试通过；所有运行表面指向同一兼容组合；README 不再维护第二份精确版本清单。

### Aspect 3 — 工程规范、中文注释与自动化门禁

发布 Python、TypeScript/Vue、配置和文档规范；建立格式化、lint、类型检查、换行、import、命名和中文说明规则；先冻结基线，再以可审查批次应用到后续会移动的代码，并把检查接入本地命令和 CI。

**退出条件：** 新增与修改代码自动符合规范；核心公共接口和复杂不变量具有准确中文说明；没有注释噪声、过期迭代叙事或格式化造成的行为变化。

### Aspect 4 — 后端领域化重组与重复逻辑收敛

基于实际调用图拆分当前平面 `app/service/llm/dao` 职责，收敛 workflow 与 Agent 共享能力、配置、错误、序列化、RAG、artifact、Eval 和 telemetry 边界；迁移迭代期命名、兼容层和重复封装，保持入口与公共 wire 兼容。

**退出条件：** 后端依赖方向可解释、无新增循环依赖、重复实现有证据地合并、旧 shim 有明确删除门禁，19 workflow 与 Agent 安全/恢复测试无漂移。

### Aspect 5 — 前端、测试、资产与文档结构收敛

将前端按功能域与共享层整理，修复拼写和旧模板命名；审计重复图片、字体、组件与样式；让测试镜像产品边界；把长期文档与 Iteration 历史分区并维护链接映射。历史 fixture 内容不可为迎合新目录而静默改写。

**退出条件：** 路由、懒加载、工作台、八类测试页、无障碍和 bundle 全部兼容；无引用资产经双重证明后移除；活跃源码和运行说明不再依赖迭代号组织。

### Aspect 6 — 分步骤、分模块运行与运维入口

建立不依赖完整 Compose 的模块化运行方式，统一配置校验、启动、健康检查和停止协议。推荐顺序为 MySQL → Redis → legacy API → Agent API → worker → frontend，MCP 与观测组件作为可选模块；提供 Windows PowerShell 和可移植命令说明。

**退出条件：** 新环境按文档可逐模块启动、诊断和停止；每个模块的端口、依赖、env、数据目录和健康状态明确；任何步骤不会隐式读取未知 `.env`、初始化或覆盖用户数据库。

### Aspect 7 — Docker 容器交付与部署加固

整理生产语义的镜像名、multi-stage build、非 root/最小权限、healthcheck、profiles、配置/secret 注入、持久卷、备份和升级边界；让核心栈与可观测栈可以组合启停，并与模块化运行共享同一版本与配置契约。

**退出条件：** digest-pinned 容器可从干净环境构建并健康运行；宿主只暴露批准端口；命名卷可备份且不会被普通停机误删；容器模式与模块模式具有相同业务契约。

### Aspect 8 — 双模式集成验收与 Iteration 5 收口

在临时合成数据上分别执行模块化运行和完整 Docker 运行旅程，复核功能、安全、恢复、性能、资源、启动、构建、文档和清洁度；发布稳定架构图、版本说明、开发规范、运维手册、迁移映射和 closeout。

**退出条件：** 两种运行方式均通过同一离线 Agent/legacy 验收；approval bypass、重复副作用、跨项目泄漏和敏感泄漏为零；仓库无禁止生成物，历史资料可追溯，README 只描述已验证能力。

## 10. 依赖顺序

```text
Aspect 1  盘点与安全清理边界
    ↓
Aspect 2  依赖与版本契约
    ↓
Aspect 3  规范与中文说明门禁
    ↓
Aspect 4  后端领域化重组
    ↓
Aspect 5  前端 / 测试 / 资产 / 文档收敛
    ↓
Aspect 6  分模块运行方式
    ↓
Aspect 7  Docker 交付方式
    ↓
Aspect 8  双模式验收与收口
```

先清理再重构可以避免搬运垃圾；先统一版本再格式化和迁移可以避免在不稳定环境中制造大 diff；先冻结规范再移动代码可以让新结构直接符合门禁；模块化入口必须先稳定，Docker 才能包装同一组真实入口；最终验收必须同时覆盖两种部署方式。

## 11. 测量与验收原则

Iteration 5 的价值不能用“文件更整齐”或主观观感证明。每个 Aspect 应按适用范围记录：

- tracked/untracked/ignored 数量与体积、清理数量、未知项和零用户数据触碰证据。
- 依赖冲突、重复版本说明、锁文件可重复性、漏洞/弃用项和升级回滚结果。
- lint/type-check/格式化违规、中文说明覆盖、循环依赖、模块边界和重复代码指标。
- pytest 收集/执行、应用 import/startup、前端 build/bundle、Docker build/image/startup/health 的 p50/p95 或稳定样本。
- legacy、Agent、RAG、缓存、恢复、审批和项目隔离契约的回归结果。
- 模块化与 Docker 两种拓扑的冷启动、健康检查、停止、数据保留和恢复结果。

性能只使用同机、同 fixture、同命令的相对值；不要求每次整理都宣称提升，但不得超过批准的回归阈值。无数据、环境变化或样本不足时标记 N/A，不填入虚构百分比。

## 12. 每个 Aspect 的执行协议

1. 只读核对 Git、相关实现、引用图、配置、历史证据和用户资产。
2. 仅为当前 Aspect 产出详细计划，明确文件范围、非目标、删除清单、迁移、门禁和回滚。
3. 等待用户确认；不提前清理、格式化、移动文件、安装依赖或启动服务。
4. 测试先行实施当前 Aspect；语义修改、格式化和文件移动尽量拆分为可审查阶段。
5. 运行聚焦测试、完整 pytest、Agent 离线门禁、前端门禁、Compose/模块运行检查、credential scan、`git diff --check` 和生成物检查。
6. 更新 `docs/iteration-5-development-log.md`，只记录真实命令、结果、删除对象、迁移映射和限制。
7. 完成后立即停止，不自动进入下一 Aspect；不 stage、commit、fetch、pull 或 push，除非用户另行明确授权。

## 13. 成功标准与非目标

成功标准：

- 仓库和本地工作区可通过安全、可重复的清理协议恢复到无禁止生成物状态。
- 版本兼容组合可机器校验，只有一份面向人的版本说明，没有失效的迭代式版本注释。
- 活跃代码按长期产品职责组织，重复实现、无引用资产和临时兼容层有证据地收敛。
- 核心模块具有准确中文说明，代码风格和目录边界由自动化门禁维护。
- Docker 完整栈和前后端/数据库分模块运行都能从干净环境复现并通过同一业务验收。
- Iteration 4 的功能、安全、数据和性能契约没有因清理或移动而退化。

明确非目标：

- 不新增测试类型、Agent 自主能力、多 Agent、模型 provider 或数据库业务表。
- 不借结构整理重写公共 API/SSE/MCP、workflow catalog 或 artifact/retention 语义。
- 不强制把变量、函数、协议字段翻译为中文，也不追求逐行注释。
- 不删除 Git 历史、closeout、真实验收证据或为美观改写历史 fixture。
- 不默认删除 Docker 命名卷、数据库、Redis、上传项目、真实 `.env` 或用户已有构建成果。
- 不在未测量前宣称启动、构建、运行或维护效率已经提升。
- 不在 Aspect 8 之前宣称 Iteration 5 完成，也不在没有明确授权时提交、推送、发布或部署到生产环境。
