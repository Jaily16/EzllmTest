# EzllmTest

**从项目资料到测试计划、测试用例与受控 Agent 执行的软件测试工作台**。

Vue 3 工作台 · Python / FastAPI · 19 workflows · 22 Agent tools · 项目隔离检索 · 本地脱敏观测

[项目介绍](#introduction) · [界面展示](#screenshots) · [项目架构](#architecture) · [技术栈](#technology) · [目录结构](#directories) · [环境要求](#requirements) · [启动项目](#setup) · [性能简介](#performance)

<a id="introduction"></a>

## 一、项目介绍

EzllmTest 将需求、设计和测试知识组织为可恢复的项目上下文，支持“资料准备 → 业务分析与测试计划 → 八类测试分析 → 用例生成”的完整流程。确定性工作流负责稳定的生成步骤，单 Agent 工作台提供规划、工具执行、审批与恢复能力。项目面向本地开发与软件测试辅助，生成结果需要开发者审阅。

| 模块     | 能做什么                                                             | 实现中的重点                                                    |
| -------- | -------------------------------------------------------------------- | --------------------------------------------------------------- |
| 项目管理 | 创建和恢复项目，上传资料，检查准备状态                               | 资料 revision、部分上传恢复、下游结果过期判定                   |
| 知识检索 | 解析、切分资料，按项目检索相关证据                                   | 项目隔离、向量与关键词检索、进程内索引复用                      |
| 测试生成 | 19 个工作流，覆盖单元、集成、API、UI、数据库、功能、非功能和验收测试 | 流式反馈、模型选择、长文本预算、结构化结果、有效产物保存        |
| Agent    | 单 Agent 规划与执行，调用 22 个类型化工具                            | 审批绑定、预算、lease/fencing、幂等、取消、事件重放和恢复       |
| 本地观测 | 查看脱敏日志、Trace 摘要、指标与服务状态                             | 独立观测 API、内存 token、SQLite 默认保留 7 天且最多 100,000 行 |

**结果保存有明确边界**。分析产物可保存；单元、集成、API、功能、非功能的最终用例仅保留在当前页面，UI、数据库、验收的最终用例可持久化。失败、取消、截断或保存失败不会覆盖上一份有效结果。普通页面读取不自动调用模型。

深入设计见[项目说明与实现设计](docs/project-design.md#product)，演进过程见[迭代历史](docs/iteration-history.md#iteration-7)，测试口径和限制见[验证历史](docs/validation-history.md#limitations)。

<a id="screenshots"></a>

## 二、项目界面展示

> **历史展示：2026-08-25，Iteration 3 合成 Aurora 项目代表性旅程**。以下十张图从固定提交 `e6c42a5f20a9a0003dc553cece16fd72a9f6aece` 原字节恢复，包含当时的模型选项与界面状态；不是当前版本截图，也不是本次新执行的验收。图中需求指标属于合成项目，不代表 EzllmTest 的实测性能。当前 Agent、观测能力由源码与设计说明支撑，不用旧图冒充其界面。

完整时间、视口、operation 和脱敏方式见[原始图片清单](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/manifest.json)；逐图固定出处见[历史图片来源表](docs/iteration-history.md#historical-images)。

### 01 · 项目进入

统一入口提供创建新项目和恢复已有项目两种方式。观察重点是项目身份入口与使用引导，尚未触发生成。

![历史合成项目：项目进入](docs/assets/01-login.png)

### 02 · 项目资料准备

按业务需求、设计资料和测试知识登记输入，逐组显示准备结果。项目标识已遮盖；准备完成不等于模型分析已经完成。

![历史合成项目：项目资料准备](docs/assets/02-project-setup.png)

### 03 · 分析与计划流式生成

同一界面展示模型选择、执行进度、正文和取消入口。观察重点是流式执行状态与尚未保存的草稿之间的区别。

![历史合成项目：分析与计划流式生成](docs/assets/03-plan-running.png)

### 04 · 已保存的测试计划

完整计划按章节呈现，可回看已保存结果。观察重点是分析结束后的阅读体验；截图中的业务指标来自虚构 Aurora 需求。

![历史合成项目：已保存的测试计划](docs/assets/04-plan-saved.png)

### 05 · 八类测试菜单

工作台汇总资料版本、推荐类型和各测试入口。推荐、可以进入与已完成是不同状态，不能从菜单推荐数推断测试已完成。

![历史合成项目：八类测试菜单](docs/assets/05-test-menu.png)

### 06 · 单元对象与分析结果

通过带来源的完整对象名称区分同名类或模块，并展示流式完成、保存状态与 Token 用量。供应商未返回的统计不会被虚构为零。

![历史合成项目：单元对象与分析结果](docs/assets/06-unit-analysis.png)

### 07 · 单元测试用例

选择测试方法和输出格式后生成用例。页面明确提示“仅当前页面保留”，刷新或离开后不能按持久化产物恢复这一阶段结果。

![历史合成项目：单元测试用例](docs/assets/07-unit-cases.png)

### 08 · API 用例与会话结果

从已分析的接口中选择范围，再指定用例格式。观察重点是接口分析与最终会话结果分层，以及不会写入项目的保存提示。

![历史合成项目：API 用例与会话结果](docs/assets/08-api-session-only.png)

### 09 · UI 用例与持久化结果

以页面和交互分析为上游生成 UI 用例；成功后保存到项目，并按匹配模型与输入恢复。它与前两张图的会话结果具有不同生命周期。

![历史合成项目：UI 用例与持久化结果](docs/assets/09-ui-persisted.png)

### 10 · 移动端导航

窄屏抽屉保留项目上下文、测试分类和当前入口。该图展示响应式导航，不代表原生移动应用或全面移动端验收。

<img src="docs/assets/10-mobile-navigation.png" alt="历史合成项目：移动端导航" width="390">

<a id="architecture"></a>

## 三、项目架构

![EzllmTest 架构：交互入口、两条执行路径、领域归属、数据与观测边界](docs/assets/architecture.svg)

图中青绿色轨道表示确定性 workflow，紫色轨道表示单 Agent 的规划与执行；它们复用项目、知识和生成能力。产品 API 面向项目与生成，Agent API 面向运行控制，worker 负责异步任务，MCP 将同一受控能力提供给显式项目范围内的客户端。

MySQL 保存项目与有效结果；Redis 保存队列、checkpoint、lease、幂等和事件重放状态；向量索引是进程内缓存，原始资料仍在本地项目目录。观测由独立 API 管理 SQLite，通过 Windows 当前登录会话内的命名管道共享 token；token 不写配置、日志或命令参数。观测失败不阻断业务，鉴权不会因此关闭。

代码依赖按 `entrypoints → bootstrap → API / application → domain / ports` 组织。具体 adapter 位于领域的 `infrastructure` 或通用 `platform`；跨域调用经过业务所有者的 `public.py`，Agent runtime 通过 ports 获取能力。详见[目录职责与依赖方向](docs/project-design.md#architecture)。

<a id="technology"></a>

## 四、技术栈

以下技术均有当前源码支撑，便于从项目理解后端开发与 AI Agent 工程能力。

| 技术                             | 项目用途                                  | 体现的工程能力                                      |
| -------------------------------- | ----------------------------------------- | --------------------------------------------------- |
| Python 3.11 · FastAPI · Pydantic | 类型化 API、请求校验、进程入口和依赖装配  | 模块边界、异常契约、REST/OpenAPI、异步服务          |
| LangChain · LangGraph · MCP      | 检索与生成链、单 Agent 图、工具及资源协议 | RAG、状态机、工具约束、审批与恢复                   |
| Vue 3 · TypeScript · Vite        | 工作台、页面路由、业务实体与流式界面      | feature/entities 分层、类型契约、状态与生命周期管理 |
| MySQL · SQLAlchemy               | 项目资料记录和有效产物持久化              | 业务数据所有权、repository、失败结果保护            |
| Redis                            | 队列、checkpoint、lease、幂等与取消/重放  | 分布式协调、过期策略、失租约中止与恢复边界          |
| SSE                              | 生成进度、正文与 Agent 事件传输           | 增量解析、取消、断流、恢复与保存边界                |
| OpenTelemetry SDK · SQLite       | 本地脱敏遥测、Trace 摘要和指标聚合        | 遥测隔离、鉴权、数据最小化、保留策略                |

检索采用 LangChain `InMemoryVectorStore`，配合项目级有界索引缓存（当前容量 16、闲置 TTL 30 分钟）及关键词检索；不是 FAISS 或外部向量数据库。Java/Spring、RabbitMQ、Prometheus 未集成，相关安装资料仅放在后文扩展阅读。

精确版本以 [Python 依赖输入](backend/requirements.in)、[Windows lock](backend/requirements-windows.txt)、[Linux lock](backend/requirements.txt)、[包元数据](backend/pyproject.toml)和 [npm manifest](frontend/package.json) / [lock](frontend/package-lock.json)为准。

<a id="directories"></a>

## 五、项目目录结构

### 全项目

下列目录只展示实现、配置边界及数据位置；省略依赖、缓存、构建产物和受保护数据内容。

```text
EzllmTest/
├── backend/                      # Python 产品包、后端依赖与实际测试
│   ├── src/ezllmtest/             # 统一实现，详见下一棵树
│   ├── tests/                    # 离线契约、状态、安全与启动检查
│   ├── static/projects/          # 本地项目资料；运行数据，不提交
│   ├── pyproject.toml            # 包定义，依赖复用 requirements.in
│   ├── requirements*.in / *.txt  # 依赖输入与平台锁文件
│   └── .env.example              # 后端配置模板；真实 .env 本地保管
├── frontend/                     # Vue 工作台与前端工具
│   ├── src/
│   │   ├── app/                  # router、plugins、应用装配
│   │   ├── entities/             # project、workflow、agent-run
│   │   ├── features/             # onboarding、planning、test-generation
│   │   │                         # agent-workbench、observability、workspace、about
│   │   └── shared/               # assets、UI、HTTP/SSE、通用状态工具
│   ├── tools/                    # 显式公开配置与 Vite 启动工具
│   ├── tests/                    # Node 离线用例
│   ├── public/                   # 公开静态文件
│   └── .env.example              # 仅公开 URL 与工具端口
├── observability/                # 观测配置、说明和数据所有权
│   ├── data/                     # SQLite 本地数据，不提交
│   └── .env.example              # 监听、保留策略与遥测配置
├── infrastructure/               # 当前有效的声明式契约
│   ├── database/schema.sql       # 七表结构；包含 DROP TABLE
│   └── runtime/                  # 模块、端口及运行所有权声明
├── ops/                          # 可选运行辅助，不承载产品逻辑
│   ├── modular_runtime.py        # 配置、检查、进程归属与安全停止
│   └── modular/                  # run.ps1 / run.sh 包装
├── docs/                         # 三份长期文档 + 文档图片
│   ├── iteration-history.md      # 迭代结论、决策与历史出处
│   ├── validation-history.md     # 证据、测量口径与未验证范围
│   ├── project-design.md         # 深入设计与维护说明
│   └── assets/                   # 历史截图与架构 SVG
└── README.md                     # 项目展示、架构导览与首次复现入口
```

### 后端详细结构

以下展开实际职责目录及关键文件，省略 `__init__.py`，不表示每个模块都必须有相同模板层级。

```text
backend/
├── src/ezllmtest/
│   ├── entrypoints/                    # 五个 canonical 启动入口
│   │   ├── product_api.py              # 项目、资料、生成 API
│   │   ├── agent_api.py                # Agent 运行与事件 API
│   │   ├── agent_worker.py             # 队列消费 / 不消费连接检查
│   │   ├── observability_api.py        # 本地观测 API
│   │   └── mcp_server.py               # 显式 project scope 的 MCP
│   ├── bootstrap/                      # 先配置，后装配依赖
│   │   ├── settings.py                 # 角色来源、投影、环境清理
│   │   ├── app_factory.py              # CLI、Uvicorn 与应用生命周期
│   │   ├── dependencies.py             # 持久化依赖绑定
│   │   └── product_app.py / agent.py / worker.py / mcp_app.py
│   ├── modules/                        # 五个业务所有者
│   │   ├── projects/
│   │   │   ├── api/routes.py
│   │   │   ├── application/            # setup、documents、files、revision
│   │   │   │                           # workflow_status、test_evidence
│   │   │   ├── domain/info_type.py
│   │   │   ├── infrastructure/         # 项目 ORM 与 repository
│   │   │   ├── ports/repository.py
│   │   │   ├── schemas/                # records、setup
│   │   │   └── public.py               # 项目领域对外应用接口
│   │   ├── knowledge/
│   │   │   ├── application/agent.py     # 面向 Agent 的检索应用服务
│   │   │   ├── infrastructure/         # loaders、splitters、index
│   │   │   │                           # retrievers、vector_store
│   │   │   ├── ports/                  # documents、indexes、retrieval、splitters
│   │   │   ├── schemas/contracts.py
│   │   │   └── public.py
│   │   ├── generation/
│   │   │   ├── api/routes.py
│   │   │   ├── application/
│   │   │   │   ├── chains/             # basic、knowledge 生成链
│   │   │   │   ├── operations/         # unit、integration、api、ui、database
│   │   │   │   │                       # functional、nonfunctional、acceptance
│   │   │   │   │                       # long_text、summarize
│   │   │   │   └── stream*.py / analysis_stream.py / case_stream.py
│   │   │   │                           # test_plan.py、test_plan_stream.py
│   │   │   ├── domain/
│   │   │   │   ├── prompts/            # templates、text；运行提示词
│   │   │   │   └── catalog.py / budget.py / long_text.py / unit_reference.py
│   │   │   ├── infrastructure/         # artifact_repository、workflow_artifacts、models
│   │   │   ├── ports/                  # artifact_store、artifacts
│   │   │   ├── schemas/                # 请求、分析、产物、历史和错误
│   │   │   └── public.py
│   │   ├── agent/
│   │   │   ├── api/                    # http、mcp_adapter
│   │   │   ├── application/            # runtime、workbench、worker、worker_probe
│   │   │   ├── domain/contracts.py
│   │   │   ├── runtime/
│   │   │   │   ├── graph.py            # 单 Agent 图与状态推进
│   │   │   │   ├── planning/planner.py
│   │   │   │   ├── execution/executor.py
│   │   │   │   ├── memory/             # context、identity
│   │   │   │   ├── state/contracts.py
│   │   │   │   └── tools/              # registry、schemas、internal_adapter
│   │   │   ├── infrastructure/         # budget、checkpoint、coordinator
│   │   │   │                           # workbench_store、worker_probe
│   │   │   ├── ports/                  # budget、coordination、runtime、workbench
│   │   │   └── schemas/workbench.py
│   │   └── observability/
│   │       ├── api/http.py
│   │       ├── application/overview.py
│   │       ├── infrastructure/storage.py
│   │       ├── ports/storage.py
│   │       └── schemas/query.py
│   ├── platform/                      # 通用 IO、供应商与安全机制
│   │   ├── ai/                        # gateway、selection、stream、tokens
│   │   │                              # runtime_hooks、legacy_models（现有适配实现）
│   │   ├── database/                  # connection、通用 models 支持
│   │   ├── security/session_token.py  # Windows 会话 IPC 与内存 token
│   │   ├── telemetry/                 # contracts、agent_telemetry、local_export、logging
│   │   └── configuration.py / configuration_schema.py / settings.py / files.py
│   └── shared/status.py               # 无 IO、无框架依赖的通用状态
├── tests/
│   ├── fixtures/                      # iteration6-contracts、redis-scripts 人工契约
│   ├── conftest.py                    # 隔离配置和依赖替身
│   └── test_*.py                      # 架构、配置、契约、协调、token、runner、worker
└── static/projects/                   # 受保护项目资料；不随源码迁移
```

| 层/接口          | 唯一职责                                         |
| ---------------- | ------------------------------------------------ |
| `api`            | HTTP/MCP 协议适配、参数与响应，调用应用服务      |
| `application`    | 编排业务步骤与状态变化，依赖 domain / ports      |
| `domain`         | 工作流、预算和业务规则，不承接通用 IO            |
| `ports`          | 声明应用需要的能力，隔离具体存储与执行实现       |
| `infrastructure` | 实现所属领域 adapter、ORM 与 repository          |
| `schemas`        | 对应领域的请求、结果及内部契约类型               |
| `public.py`      | 已存在的跨域稳定操作和 DTO，不重新导出整套旧模块 |

推荐阅读：`entrypoints/product_api.py` → `bootstrap/app_factory.py` 与 `settings.py` → `modules/projects/api/routes.py` → `modules/generation/domain/catalog.py` → `modules/agent/runtime/graph.py` → `platform/security/session_token.py` → 相应测试。

<a id="requirements"></a>

## 六、环境要求

先准备必需组件，再按平台 lock 安装项目依赖。本机参考值核对于 2026-09-11；推荐范围由依赖声明、前端 lock 的 engines 交集和协议要求推导，**没有逐版本运行验收**。

| 组件           | 本机参考版本       | 推荐兼容范围                       | 是否必需                       |
| -------------- | ------------------ | ---------------------------------- | ------------------------------ |
| Python         | 3.11.15            | 3.11.x–3.12.x，优先 3.11           | 是                             |
| Node.js        | 24.18.0            | 22.13+ 的 22.x，或 24.x；优先 24.x | 是                             |
| npm            | 11.16.0            | 10.x–11.x，与所选 Node 兼容        | 是                             |
| MySQL          | 8.4.11             | 8.0.x 或 8.4.x，优先 8.4           | 是                             |
| Redis 兼容服务 | 8.2.9              | 7.2–8.x，支持 Streams / Lua        | 是，Agent 协调依赖             |
| SQLite         | Python 内置 3.53.2 | 使用所选 Python 自带版本           | Windows 观测使用，无需独立服务 |
| Git            | 2.55.0             | 2.40+ 的 2.x                       | 获取仓库使用                   |
| Conda          | 24.9.2             | 能创建上述 Python 环境即可         | 可选，已有 venv 也可           |
| RabbitMQ       | 4.3.5              | 未集成，不设运行版本要求           | 否                             |

Node 选择参考 [LTS 发布状态](https://nodejs.org/en/about/previous-releases)，Redis 范围参考 [redis-py 支持表](https://github.com/redis/redis-py#supported-redis-versions)。仓库 Node 离线测试使用 Node 24，以满足测试加载器的 API 要求。业务依赖仍以 [平台 locks](backend/)与 [package-lock.json](frontend/package-lock.json) 为准，不用本表替代锁定版本。

模型账户按所用供应商准备；知识检索的 embedding 当前使用智谱。Java、RabbitMQ、Prometheus 不属于启动依赖。Windows 支持完整三端；Linux 提供关闭遥测后的核心启动参考，未做实机验证。

| 服务                | 端口 |
| ------------------- | ---- |
| 产品 API            | 8230 |
| Agent API           | 8231 |
| 观测 API（Windows） | 8140 |
| 前端                | 8180 |
| 可选 MCP            | 8011 |

<a id="setup"></a>

## 七、启动项目

流程：**启动已有基础设施 → 安装项目依赖 → 初始化新数据库 → 填写必要配置 → 启动 → 检查**。已有环境直接复用数据库和三份配置，跳过初始化。

<a id="install"></a>

### 7.1 启动已有基础设施

以下命令不安装组件。服务名和安装目录以自己的机器为准；已运行时直接复用，不重复启动。

**Windows / PowerShell：**

```powershell
# MySQL 服务名可能是 MySQL 或 MySQL84，先找到实际名称。
Get-Service *mysql*
Start-Service MySQL
Get-Service MySQL
mysql -h 127.0.0.1 -u root -p -e "SELECT 1;"

# 原生 Redis 兼容服务按已有 Windows 服务管理。
# 若现有 Redis 为独立程序，在安装目录的单独终端运行：
Set-Location '你的 Redis 安装目录'
.\redis-server.exe redis.conf
```

Redis 启动终端保持运行，在另一终端检查：

```powershell
& '你的 Redis 安装目录\redis-cli.exe' PING
```

返回 `PONG` 表示连接成功。有认证时按自己的服务设置连接，不把密码写入命令历史。

**Linux / Bash（已有 systemd 服务）：**

```bash
sudo systemctl start mysql redis-server
systemctl is-active mysql redis-server
mysql -h 127.0.0.1 -u root -p -e 'SELECT 1;'
redis-cli PING
```

<details>
<summary>可选：RabbitMQ 启动与检查（项目未集成）</summary>

运行 EzllmTest 不需要 RabbitMQ；以下仅用于管理机器上已有的组件。

```powershell
Start-Service RabbitMQ
Get-Service RabbitMQ
# 在已有 RabbitMQ sbin 目录执行
.\rabbitmq-diagnostics.bat ping
```

```bash
sudo systemctl start rabbitmq-server
systemctl is-active rabbitmq-server
sudo rabbitmq-diagnostics ping
```

</details>

<a id="dependencies"></a>

### 7.2 获取仓库与安装项目依赖

需要仓库访问权限；使用 Git 凭据管理器或 SSH 认证，不把 token 放入 URL。以下假定已准备 `ezllmtest` Python 环境；使用 venv 时换成自己的激活命令。

**Windows：**

```powershell
git clone https://github.com/Jaily16/EzllmTest.git 'D:\projects\EzllmTest'
conda activate ezllmtest
Set-Location 'D:\projects\EzllmTest'
python -m pip install -r backend/requirements-windows.txt
python -m pip install --no-deps --editable backend
Set-Location frontend
npm ci
```

**Linux：**

```bash
git clone https://github.com/Jaily16/EzllmTest.git "$HOME/EzllmTest"
conda activate ezllmtest
cd "$HOME/EzllmTest"
python -m pip install -r backend/requirements.txt
python -m pip install --no-deps --editable backend
cd frontend
npm ci
```

先安装平台 lock，再注册 editable 产品包；构建隔离可能获取 `pyproject.toml` 声明的 setuptools。Python 开发工具见 [requirements-dev.in](backend/requirements-dev.in) 与对应开发 lock，不要求重新生成锁文件。

<a id="initialize"></a>

### 7.3 初始化新数据库

**仅新环境执行。`schema.sql` 包含 `DROP TABLE`，只能导入刚创建且确认无表的数据库。** 数据库或账户已存在时停止，改用新名称并同步配置；不要用 `IF NOT EXISTS` 掩盖误选既有库。

在 MySQL 管理员客户端执行：

```sql
CREATE DATABASE ezllmtest_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'ezllmtest'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_A_NEW_STRONG_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON ezllmtest_demo.* TO 'ezllmtest'@'127.0.0.1';
USE ezllmtest_demo;
SELECT DATABASE();
SHOW TABLES;
```

确认选中 `ezllmtest_demo` 且没有表后，**Windows 在同一个客户端**导入，路径按实际位置填写：

```sql
SOURCE D:/projects/EzllmTest/infrastructure/database/schema.sql;
SHOW TABLES;
```

**Linux** 确认空库后可用输入重定向：

```bash
mysql -h 127.0.0.1 -u root -p ezllmtest_demo < "$HOME/EzllmTest/infrastructure/database/schema.sql"
mysql -h 127.0.0.1 -u root -p ezllmtest_demo -e 'SHOW TABLES;'
```

应显示 **7 张表**。SQL 仅提供结构，不含历史截图项目。资料通过前端创建/上传入口登记，项目目录按需创建。Redis 使用独立数据库编号和 key prefix，不导入旧任务、不执行 `FLUSHDB`；观测 SQLite 及目录自动初始化，无需手工建目录或复制作者数据。

<a id="configuration"></a>

### 7.4 只填写自己的连接与模型凭据

将 `backend/.env.example`、`frontend/.env.example`、`observability/.env.example` 分别**复制为同目录的 `.env`**，保留示例；已有 `.env` 直接复用，不覆盖。根 `.env.example` 是迁移说明，不是第四份运行配置。

通常只需要填写 **backend/.env**：

```dotenv
DATABASE_URL=mysql+pymysql://ezllmtest:YOUR_URL_ENCODED_PASSWORD@127.0.0.1:3306/ezllmtest_demo?charset=utf8mb4
AGENT_REDIS_URL=redis://127.0.0.1:6379/1
AGENT_REDIS_PREFIX=ezllmtest:demo

# 知识检索使用智谱 embedding。
ZHIPU_API_KEY=YOUR_ZHIPU_KEY
```

| 内容           | 填写方式                                                                                                        |
| -------------- | --------------------------------------------------------------------------------------------------------------- |
| 数据库         | 使用新库和应用账户；用户名/密码中的特殊字符需要 URL 编码                                                        |
| Redis          | 地址、认证（如有）、独立数据库编号和不与其他项目共用的 prefix                                                   |
| 智谱 embedding | 填 `ZHIPU_API_KEY`，确认账户可调用模板中的 embedding 模型；任意聊天 key 不能替代它                              |
| 聊天供应商     | 按实际选择填写 `ZHIPU_API_KEY`、`DASHSCOPE_API_KEY`、`DEEPSEEK_API_KEY` 或 `MOONSHOT_API_KEY`；未使用的可留空   |
| 供应商端点     | 仅在账户平台要求时改 `*_BASE_URL`；如 Moonshot 中国平台为 `https://api.moonshot.cn/v1`，必须与 key 所属平台一致 |

前端公开 URL、端口与观测默认项按模板保留即可。观测模板的 `data/ezllmtest-observability.sqlite3` 相对于**观测配置文件所在目录**定位，换终端目录不影响位置；原有 `observability/data` 内的合法绝对路径仍可用。快捷模式不改写已有配置。

配置不展开 `$HOME`、`$Repo` 等变量，未知/重复字段会被拒绝。使用 `DATABASE_URL_FILE` 或 API key 的 `_FILE` 时，填绝对普通文件路径，并删除对应直接赋值行；即使该行为空也不能并存。错误只分享字段名和类别，不贴凭据。

`--local-config` 显式定位固定三端文件，不向上搜索、不在缺失时回退；不能与 `--*-env-file` 或 runner 旧兼容配置参数混用。Python 入口仍要求绝对 `--repo-root`。

<a id="windows"></a>

### 7.5 Windows：一键启动三端

在仓库根执行，仅在前一步成功后执行下一步：

```powershell
conda activate ezllmtest
Set-Location 'D:\projects\EzllmTest'
.\ops\modular\run.ps1 config-check --local-config
.\ops\modular\run.ps1 preflight --local-config
.\ops\modular\run.ps1 start --local-config
```

`config-check` 验证三端配置，`preflight` 验证 MySQL、表结构元数据与 Redis，`start` 启动观测 API、产品 API、Agent API、**普通 worker**、前端五个进程。脚本使用当前激活的 Python，管理启动顺序及 token 共享。

**普通 worker 执行 Agent 队列，是使用 Agent 工作台所需的后台执行者**；项目与确定性生成页面不靠它消费任务。启动后当前 namespace 中已有的待处理任务也可能执行，产生模型调用和业务写入。

保存返回的 `run-id`，用于管理这一组进程：

```powershell
.\ops\modular\run.ps1 status --run-id '<返回的 run-id>'
.\ops\modular\run.ps1 ready --run-id '<返回的 run-id>'
.\ops\modular\run.ps1 stop --run-id '<返回的 run-id>'
```

打开 **http://127.0.0.1:8180/**。不要同时通过 runner 与独立终端重复启动同一端口；runner 按 PID、创建时间和命令指纹核验归属，只停止自己创建的进程。

<details>
<summary>排错时使用：五个独立终端</summary>

每一块在不同 PowerShell 终端执行，先停止 runner 的进程组。保持单进程，不加 reload 或多 worker。

```powershell
# 终端一：观测 API
conda activate ezllmtest
python -m ezllmtest.entrypoints.observability_api --repo-root 'D:\projects\EzllmTest' --local-config
```

```powershell
# 终端二：产品 API
conda activate ezllmtest
python -m ezllmtest.entrypoints.product_api --repo-root 'D:\projects\EzllmTest' --local-config
```

```powershell
# 终端三：Agent API
conda activate ezllmtest
python -m ezllmtest.entrypoints.agent_api --repo-root 'D:\projects\EzllmTest' --local-config
```

```powershell
# 终端四：普通 worker
conda activate ezllmtest
python -m ezllmtest.entrypoints.agent_worker --repo-root 'D:\projects\EzllmTest' --local-config --consumer local-worker
```

```powershell
# 终端五：前端
Set-Location 'D:\projects\EzllmTest\frontend'
npm run serve -- --local-config
```

每块自行指定环境或路径，不依赖其他终端变量。原完整配置文件参数仍可用，见[角色矩阵与完整命令](docs/project-design.md#configuration)。

</details>

<a id="linux"></a>

### 7.6 Linux：核心启动参考

**未做 Linux 实机验证。** 在 Linux 的 `observability/.env` 中设置 `AGENT_TELEMETRY_ENABLED=false`，其他模板项保留。token 共享目前只有 Windows adapter，因此不启动观测 API、不使用全栈 runner，观测页面不可用。

每块分别在独立 Bash 终端执行：

```bash
conda activate ezllmtest
python -m ezllmtest.entrypoints.product_api --repo-root "$(realpath "$HOME/EzllmTest")" --local-config
```

```bash
conda activate ezllmtest
python -m ezllmtest.entrypoints.agent_api --repo-root "$(realpath "$HOME/EzllmTest")" --local-config
```

```bash
conda activate ezllmtest
python -m ezllmtest.entrypoints.agent_worker --repo-root "$(realpath "$HOME/EzllmTest")" --local-config --consumer local-worker
```

```bash
cd "$HOME/EzllmTest/frontend"
npm run serve -- --local-config
```

只排查 Redis 连接时，worker 命令追加 `--no-consume --once`；它不处理任务，也不满足正常 worker 就绪。

### 7.7 可选入口解释

- **不消费 worker**：验证 Redis 连接及独立短期心跳，不读/认领/确认队列、不装配模型能力。日常无需开启；普通 worker 命令追加 `--no-consume` 即切换，加 `--once` 检查一次退出。它不计入正常 worker 集合，只启动它时 Agent `/ready` 返回 503 属于预期。
- **Uvicorn**：承载 FastAPI 的 HTTP 服务器，已由 `python -m` 内部启动，不是额外服务。需自行管理服务器参数时参考[等价入口](docs/project-design.md#startup)，保持角色来源隔离；普通使用直接启动 runner 即可。
- **MCP**：向外部 AI 客户端提供 tools/resources，让其在明确的项目 scope 内使用项目能力，沿用隔离、工具权限与审批约束。网页通过 REST/SSE 工作，**不需要启动 MCP**，runner 也不会自动启动它。

MCP 以下仅为模板，项目 ID 必须明确授权；客户端连接 `http://127.0.0.1:8011/mcp`。快捷模式仅读取 backend；额外遥测需使用完整 backend/observability 参数模式。

```powershell
conda activate ezllmtest
python -m ezllmtest.entrypoints.mcp_server --repo-root 'D:\projects\EzllmTest' --local-config --project-id '<明确授权的项目 ID>' --actor-id local-operator --scope-version v1 --port 8011
```

<a id="check-stop"></a>

### 7.8 健康检查与退出

```powershell
curl.exe -i http://127.0.0.1:8230/health
curl.exe -i http://127.0.0.1:8230/ready
curl.exe -i http://127.0.0.1:8231/ready
curl.exe -i http://127.0.0.1:8140/ready
curl.exe -I http://127.0.0.1:8180/
```

Linux 使用 `curl` 并跳过观测地址；`ss -ltnp` 查看监听。Windows 使用 `Get-NetTCPConnection -State Listen` 查看端口与 PID。

| 状态                                     | 含义与排查                                           |
| ---------------------------------------- | ---------------------------------------------------- |
| 产品 `/health`、`/ready` 200             | 进程及最小数据库检查通过                             |
| Agent `/ready` 200                       | Redis 和普通 worker 就绪，不等于模型与生成链验证     |
| Agent `/ready` 503                       | 检查 Redis / 普通 worker；不消费模式不满足就绪       |
| 观测 `/ready` 200                        | SQLite 可用，正常写入并执行保留策略                  |
| `runtime_config:*` / `frontend_config:*` | 核对字段、重复项、角色、路径、端口与 CORS            |
| `No module named ezllmtest`              | 激活正确环境，用 `python -m pip show ezllmtest` 核对 |
| embedding 错误                           | 检查智谱 key、模型和账户权限                         |
| 端口 / IPC 冲突                          | 核对并关闭自己的重复实例，不按端口强杀               |

runner 使用 `stop --run-id`。独立终端按前端 → worker → Agent API → 产品 API → 观测 API 的顺序各自 Ctrl+C；Linux 无观测终端。保留已有 MySQL/Redis、用户数据和配置。

<a id="performance"></a>

## 八、性能简介

当前沿用前端构建与缓存优化，减少等待和重复模型成本：

| 指标             | 优化前           | 优化后（当前沿用）                             |
| ---------------- | ---------------- | ---------------------------------------------- |
| 前端构建耗时 p95 | 12393.5751 ms    | **788.016 ms**，降低约 93.6%                   |
| 初始最大 JS 文件 | 443227 B         | **293597 B**，缩小约 33.8%                     |
| 完整有效结果命中 | 重复进入生成路径 | 直接恢复结果，避免本次重复模型调用和 embedding |
| 项目索引         | 重复装配索引     | 项目级有界内存缓存，容量 16、闲置 30 分钟淘汰  |

缓存要求项目、资料 revision、模型、提示词版本与选择等身份一致；失败、取消、截断和过期结果不冒充有效命中。检索使用 LangChain InMemoryVectorStore，按项目与语料隔离复用。

数值来自已有同机测量，当前沿用对应优化，**不是本次重测或线上 SLA**。构建耗时、最大 JS 文件大小不代表 API 延迟或所有网络传输量；缓存两行描述实现策略。完整来源与测量条件见[验证历史](docs/validation-history.md#performance-model)。
