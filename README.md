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

| 项目       | 复现建议 / 版本要求                                 | 验证边界                                             |
| ---------- | --------------------------------------------------- | ---------------------------------------------------- |
| 操作系统   | Windows 本地单进程开发；Linux 核心启动参考见下文    | Windows 已有分终端只读与不消费验收；Linux 未实机验证 |
| Python     | 使用 3.11；包声明最低 3.11                          | 更高 Python 版本不据此宣称锁文件兼容                 |
| Node / npm | Node 24，配套 npm；用 `npm ci`                      | 既有验证使用 Node 24 / npm 11                        |
| MySQL      | MySQL 8 系列、`utf8mb4`                             | SQL 来源为 8.0；8.4 安装方式是参考，未做版本迁移验收 |
| Redis      | 支持当前 Streams/Lua/过期操作的 Redis 兼容服务      | Windows 可选 Memurai；其全新安装不等于已有环境验收   |
| 模型账户   | 已接入的聊天供应商账户；检索还需智谱 embedding 权限 | key 存在不证明额度、模型可用性或真实链路通过         |
| Git / 网络 | 仓库访问权限、依赖下载及模型端点连接能力            | 当前仓库为私有；无权限需先获授权                     |

| 服务                | 默认 loopback 端口 |
| ------------------- | ------------------ |
| 产品 API            | 8230               |
| Agent API           | 8231               |
| 观测 API（Windows） | 8140               |
| 前端                | 8180               |
| 可选 MCP            | 8011               |

MySQL/Redis 通常分别使用 3306/6379，实际以自己的安装为准。首次复现采用空数据库与独立 Redis namespace；不需要 Java、RabbitMQ、Prometheus、Docker 或 WSL。本次 README 维护只做文档与人工配置检查，没有执行下面的安装、数据库导入和真实启动命令。

<a id="setup"></a>

## 七、启动项目

[安装环境](#install) → [获取代码与依赖](#dependencies) → [初始化数据](#initialize) → [填写三份配置](#configuration) → [Windows 启动](#windows) / [Linux 参考](#linux) → [检查与停止](#check-stop)

<a id="install"></a>

### 7.1 安装环境与基础设施

#### Python 与 Node

推荐安装 [Miniconda](https://www.anaconda.com/docs/getting-started/installation)，在已初始化 Conda 的 PowerShell / Bash 中执行：

```text
conda create -n ezllmtest python=3.11
conda activate ezllmtest
python --version
```

已有 Python 3.11 时可改用 [venv](https://docs.python.org/3.11/library/venv.html)。以下两种环境方案任选一种，不叠加激活：

```powershell
# Windows；后续每个 Python 终端用此激活命令替换 conda activate
py -3.11 -m venv "$env:USERPROFILE\venvs\ezllmtest"
& "$env:USERPROFILE\venvs\ezllmtest\Scripts\Activate.ps1"
```

```bash
# Linux；已安装 python3.11 及对应 venv 支持时
python3.11 -m venv "$HOME/venvs/ezllmtest"
source "$HOME/venvs/ezllmtest/bin/activate"
```

Node 使用[官方下载](https://nodejs.org/en/download)的 **24 系列** Windows 安装包，或 Linux 对应架构的官方二进制包。Linux 解压后将包的 `bin` 加入本终端 PATH；npm 随 Node 提供。安装后检查 `node --version`、`npm --version`，不要用发行版过旧的 Node 替代。

#### MySQL

Windows：按 [MySQL 官方 Windows 指南](https://dev.mysql.com/doc/refman/8.4/en/windows-installation.html)安装 MSI，并通过 Configurator 设置管理员密码、端口及 Windows 服务。8.4 安装还需满足官方列出的 VC++ 运行库要求。以下服务名以安装时选择的 `MySQL84` 为例；客户端路径按实际版本调整：

```powershell
# 管理员终端，仅在服务未运行时启动
Get-Service -Name MySQL84
Start-Service -Name MySQL84
& 'C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe' -h 127.0.0.1 -u root -p
```

Linux：按[官方 APT 指南](https://dev.mysql.com/doc/mysql-apt-repo-quick-guide/en/)下载当前 `mysql-apt-config` DEB，选择受支持的 8 系列。把下例版本占位替换成下载文件名，检查仓库配置后安装：

```bash
sudo dpkg -i ./mysql-apt-config_VERSION_all.deb
sudo apt-get update
sudo apt-get install mysql-server
sudo systemctl start mysql
sudo systemctl status mysql --no-pager
mysql -h 127.0.0.1 -u root -p
```

进入 MySQL 客户端后先执行 `SELECT 1;`。命令中的 `-p` 会交互提示密码，不把密码写入命令行。

#### Redis

Windows 原生方案采用 [Redis 官方介绍的 Memurai](https://redis.io/tutorials/howtos/how-to-run-redis-on-windows-natively-with-memurai/)，按 MSI 指引安装兼容服务，并确认所选版本及许可适合自己的用途。它是新机器安装参考，不能冒充本项目历史验收所用环境。

```powershell
# 管理员终端；服务名和路径以 MSI 实际安装为准
Get-Service -Name Memurai
Start-Service -Name Memurai
& 'C:\Program Files\Memurai\memurai-cli.exe' -h 127.0.0.1 -p 6379 PING
```

Linux 使用 [Redis 官方 APT 安装说明](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/apt/)。Ubuntu/Debian 安装示例：

```bash
sudo apt-get install lsb-release curl gpg
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
sudo chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt-get install redis
sudo systemctl start redis-server
redis-cli -h 127.0.0.1 -p 6379 PING
```

以上 APT 仓库配置用于尚未配置该仓库的新环境；已有同名文件时先核对，不能盲目覆盖。`PING` 应返回 `PONG`。服务启用密码时采用客户端交互输入方式（如 `redis-cli --askpass PING`），并在后续配置中填写自己的连接 URL。SQLite 由 Python 与观测程序管理，不需要单独安装数据库服务。

<details>
<summary>扩展阅读：Java / RabbitMQ / Prometheus（本项目未集成，不是启动前置条件）</summary>

- **Java / Eclipse Temurin**：可选官方 Windows MSI，或按[官方 Linux 包仓库说明](https://adoptium.net/installation)安装所需 JDK；安装后执行 `java -version`、`javac -version`。这些命令只检查 Java 环境，不会为 EzllmTest 新增 Java 服务。
- **RabbitMQ / Erlang**：Windows 按[官方说明](https://www.rabbitmq.com/docs/install-windows)先安装兼容版本的 Erlang/OTP，再安装 RabbitMQ 服务；Linux 按[官方 Debian/Ubuntu 仓库说明](https://www.rabbitmq.com/docs/install-debian)安装 `rabbitmq-server`。Linux 启动/检查用 `sudo systemctl start rabbitmq-server`、`sudo rabbitmq-diagnostics ping`；Windows 可在管理员终端的 RabbitMQ `sbin` 中用 `.\rabbitmq-service.bat start`、`.\rabbitmq-diagnostics.bat ping`。本项目队列使用 Redis，没有 RabbitMQ 接入配置。
- **Prometheus**：按[官方入门指南](https://prometheus.io/docs/prometheus/latest/getting_started/)下载对应平台二进制包并解压，Linux 使用 `./prometheus --config.file=prometheus.yml`，Windows 使用 `.\prometheus.exe --config.file=prometheus.yml`；`--version` 检查版本。随包示例可抓取 Prometheus 自身，不能据此声称已采集 EzllmTest 指标；本项目没有现成 Prometheus scrape 接入。

</details>

<a id="dependencies"></a>

### 7.2 获取仓库与安装项目依赖

当前仓库需要 GitHub 访问权限。先通过 Git 凭据管理器或 SSH 完成自己的认证，不把访问 token 放进 clone URL。以下路径只是新机器示例，可替换成自己的绝对目录。

**Windows / PowerShell：**

```powershell
git clone https://github.com/Jaily16/EzllmTest.git 'D:\projects\EzllmTest'
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
Set-Location -LiteralPath $Repo
conda activate ezllmtest
python -m pip install -r "$Repo\backend\requirements-windows.txt"
python -m pip install --no-deps --editable "$Repo\backend"
Set-Location -LiteralPath "$Repo\frontend"
npm ci
```

**Linux / Bash：**

```bash
git clone https://github.com/Jaily16/EzllmTest.git "$HOME/EzllmTest"
REPO="$(realpath "$HOME/EzllmTest")"
cd "$REPO"
conda activate ezllmtest
python -m pip install -r "$REPO/backend/requirements.txt"
python -m pip install --no-deps --editable "$REPO/backend"
cd "$REPO/frontend"
npm ci
```

先安装平台 lock，再注册 editable 产品包。`pyproject.toml` 的构建隔离可能下载它声明的 setuptools；这不要求重新求解业务依赖或重新生成 lock。开发检查与运行环境分别管理：Python 工具输入见 [requirements-dev.in](backend/requirements-dev.in)及对应平台开发 lock；npm 开发工具已随 `npm ci` 安装。已有环境中发现版本差异时单独核对，不用 README 的示例版本替代 lock。

<a id="initialize"></a>

### 7.3 初始化空数据库与项目资料目录

**`schema.sql` 包含 `DROP TABLE`。只能在刚创建、确认无表的新数据库执行**。下例固定使用 `ezllmtest_demo`：若数据库或应用账户已经存在，立即停止，换一个全新名称并同步后续配置；不要改为 `IF NOT EXISTS` 后继续导入。

在 MySQL 管理员客户端先执行创建步骤，确认成功后再继续：

```sql
CREATE DATABASE ezllmtest_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'ezllmtest'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_A_NEW_STRONG_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON ezllmtest_demo.* TO 'ezllmtest'@'127.0.0.1';
USE ezllmtest_demo;
SELECT DATABASE();
SHOW TABLES;
```

把密码占位替换为新密码。`SELECT DATABASE()` 必须是 `ezllmtest_demo`，`SHOW TABLES` 必须为空。账户只授予运行所需 CRUD 权限，结构初始化由管理员执行。

Windows 在**同一个 MySQL 客户端**执行下列语句，`SOURCE` 路径采用正斜杠，按实际仓库位置修改：

```sql
SOURCE D:/projects/EzllmTest/infrastructure/database/schema.sql;
SHOW TABLES;
SELECT COUNT(*) AS table_count FROM information_schema.tables
WHERE table_schema = 'ezllmtest_demo' AND table_type = 'BASE TABLE';
```

Linux 在 Bash 中导入；仍以刚才已确认的空数据库为前提：

```bash
REPO="$(realpath "$HOME/EzllmTest")"
mysql -h 127.0.0.1 -u root -p ezllmtest_demo < "$REPO/infrastructure/database/schema.sql"
mysql -h 127.0.0.1 -u root -p ezllmtest_demo -e 'SHOW TABLES; SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema = "ezllmtest_demo" AND table_type = "BASE TABLE";'
```

导入后应有 **7 张表**。仓库 SQL 只有结构，没有复现历史截图项目的种子数据。项目需求、设计与知识资料应通过前端创建/上传入口登记；它会写入自己的新项目，生成按钮可能产生模型费用。

如有自己的 SQL 备份，只恢复到另一个单独新建的数据库，先核对备份是否内含 `USE` / `CREATE DATABASE` 及其目标；不可直接导入既有库。文件资料还需按自身备份清单恢复到对应项目路径，不能认为 SQL 自动包含上传文件。

Redis 使用独立数据库编号（示例 `/1`）及 `AGENT_REDIS_PREFIX=ezllmtest:demo`，不导入作者旧任务，不执行 `FLUSHDB`。Windows 观测 SQLite 自动初始化，不下载或复制作者的数据库。

新复现环境按需创建两个数据目录；已有项目目录仅保留：

```powershell
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
foreach ($Relative in @('backend\static\projects', 'observability\data')) {
    $Target = Join-Path $Repo $Relative
    if (-not (Test-Path -LiteralPath $Target)) { New-Item -ItemType Directory -Path $Target | Out-Null }
}
```

```bash
REPO="$(realpath "$HOME/EzllmTest")"
mkdir -p "$REPO/backend/static/projects" "$REPO/observability/data"
```

<a id="configuration"></a>

### 7.4 填写三份本地配置

**运行配置只有 `backend/.env`、`frontend/.env`、`observability/.env`**。根 `.env.example` 是迁移说明，不是第四份配置。只在目标不存在时复制模板：

```powershell
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
foreach ($Name in @('backend', 'frontend', 'observability')) {
    $Source = Join-Path $Repo "$Name\.env.example"
    $Target = Join-Path $Repo "$Name\.env"
    if (Test-Path -LiteralPath $Target) { Write-Host "$Name/.env 已存在，保留" }
    else { [System.IO.File]::Copy($Source, $Target, $false) }
}
```

```bash
REPO="$(realpath "$HOME/EzllmTest")"
for name in backend frontend observability; do
  if [ -e "$REPO/$name/.env" ]; then
    printf '%s/.env 已存在，保留\n' "$name"
  else
    (set -C; cat "$REPO/$name/.env.example" > "$REPO/$name/.env") || exit 1
  fi
done
```

以下是**模板中需要核对/填写的字段片段**；编辑现有条目，不把片段追加到模板造成重复字段。其他预算、TTL、模型默认值按模板保留。

**`backend/.env`：**

```dotenv
DATABASE_URL=mysql+pymysql://ezllmtest:REPLACE_WITH_URL_ENCODED_PASSWORD@127.0.0.1:3306/ezllmtest_demo?charset=utf8mb4
AGENT_REDIS_URL=redis://127.0.0.1:6379/1
AGENT_REDIS_PREFIX=ezllmtest:demo
ZHIPU_API_KEY=REPLACE_WITH_YOUR_ZHIPU_KEY
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
ZHIPU_CHAT_MODEL=glm-4.7
ZHIPU_EMBEDDING_MODEL=embedding-3
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8230
AGENT_API_PORT=8231
CORS_ORIGINS=http://127.0.0.1:8180,http://localhost:8180
```

| 字段                                               | 应填写的内容                                                                                   |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                                     | 上面新数据库及应用账户的 SQLAlchemy URL；密码中的 `@`、`:`、`/` 等按 URL percent-encoding 编码 |
| `AGENT_REDIS_URL` / `AGENT_REDIS_PREFIX`           | 自己的 Redis、独立数据库编号与 key 前缀；有认证时填写正确 URL                                  |
| `ZHIPU_API_KEY` / `ZHIPU_BASE_URL`                 | 智谱 key 与已接入的端点；当前 embedding 使用智谱惰性适配，需相应模型权限                       |
| `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL`         | 选择阿里云百炼聊天模型时填写；模板端点为 `https://dashscope.aliyuncs.com/compatible-mode/v1`   |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`           | 选择 DeepSeek 时填写；模板端点为 `https://api.deepseek.com`                                    |
| `MOONSHOT_API_KEY` / `MOONSHOT_BASE_URL`           | 选择 Moonshot 时填写；模板端点为 `https://api.moonshot.ai/v1`                                  |
| 各供应商 `*_CHAT_MODEL` / `*_TIMEOUT_SECONDS`      | 按模板及当前接入实现核对，不把任意供应商/模型名当作通用插件                                    |
| `BACKEND_PORT` / `AGENT_API_PORT` / `CORS_ORIGINS` | 与前端公开 URL、前端端口一致，使用本机地址                                                     |

不使用的聊天供应商 key 可保留模板空值；选择它之前再配置。**仅有任意聊天模型 key 不足以完成检索**，智谱 embedding 是当前单独的依赖。

**`frontend/.env`：**

```dotenv
FRONTEND_PORT=8180
VUE_APP_API_BASE_URL=http://127.0.0.1:8230
VUE_APP_AGENT_API_BASE_URL=http://127.0.0.1:8231
VUE_APP_OBSERVABILITY_API_BASE_URL=http://127.0.0.1:8140
```

三个 URL 会进入浏览器，`FRONTEND_PORT` 仅用于启动工具。不要在此加入 API key、数据库连接或其他后端字段。Vite 自动 dotenv 发现关闭，仅使用显式配置与公开字段白名单。

**`observability/.env`（Windows）：**

```dotenv
OBSERVABILITY_HOST=127.0.0.1
OBSERVABILITY_PORT=8140
OBSERVABILITY_DATABASE_PATH=D:\projects\EzllmTest\observability\data\ezllmtest-observability.sqlite3
OBSERVABILITY_RETENTION_DAYS=7
OBSERVABILITY_MAX_ROWS=100000
OBSERVABILITY_CORS_ORIGINS=http://127.0.0.1:8180,http://localhost:8180
AGENT_TELEMETRY_ENABLED=true
AGENT_TELEMETRY_SERVICE_NAME=ezllm-agent
AGENT_OTEL_EXPORT_TIMEOUT_MS=2000
AGENT_OTEL_METRIC_INTERVAL_MS=30000
```

Linux 修改自己的 observability 配置中的以下两项，其余条目保留；路径中的 `developer` 换成实际用户名，必须填写展开后的绝对路径：

```dotenv
OBSERVABILITY_DATABASE_PATH=/home/developer/EzllmTest/observability/data/ezllmtest-observability.sqlite3
AGENT_TELEMETRY_ENABLED=false
```

SQLite 路径必须位于这份观测配置所在目录的 `data` 内；不能指向任意外部目录。Linux 核心启动仍读取遥测配置以明确关闭它，不启动 SQLite 观测服务。

配置规则：不支持在 `.env` 内展开 `$HOME`、`$Repo`、`${VAR}` 等 shell 变量；未知/重复/跨角色字段会被拒绝。对于 schema 支持的秘密字段，直接值与对应 `*_FILE` 二选一（例如 `DATABASE_URL` 与 `DATABASE_URL_FILE`）；使用 `_FILE` 时删除同名直接条目，空赋值也不能并存。秘密引用文件用受保护的绝对普通文件路径，不指向链接。配置值不输出到日志或公开前端。

| 进程角色  | 允许的配置源                                  |
| --------- | --------------------------------------------- |
| 产品 API  | backend + frontend                            |
| Agent API | backend + frontend + observability            |
| worker    | backend + observability                       |
| 观测 API  | observability + frontend；不读取 backend 秘密 |
| MCP       | backend；启用遥测时显式加入 observability     |
| 前端      | 仅 frontend                                   |

加载器先校验显式文件，再清理继承的冲突环境并装配依赖；不会用父终端旧值覆盖文件。详细字段与投影规则见[配置设计](docs/project-design.md#configuration)。

<a id="windows"></a>

### 7.5 Windows：五个独立终端

以下每段都是独立 PowerShell 终端的完整启动命令。Python 终端先激活同一个环境，再将 `$Repo` 设置为自己的绝对仓库路径；变量不会跨终端共享。使用 venv 时替换激活行。

按 **观测 API → 产品 API → Agent API → 不消费 worker → 前端** 顺序启动。Windows 观测和生产者应处于同一登录会话、使用同一规范化仓库路径与观测端点。token 由程序通过受限命名管道共享，不能手动写到 `.env`、命令行或用户/系统环境。

**终端 1：观测 API**

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
python -B -m ezllmtest.entrypoints.observability_api --repo-root "$Repo" --observability-env-file "$Repo\observability\.env" --frontend-env-file "$Repo\frontend\.env"
```

**终端 2：产品 API**

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
python -B -m ezllmtest.entrypoints.product_api --repo-root "$Repo" --backend-env-file "$Repo\backend\.env" --frontend-env-file "$Repo\frontend\.env"
```

**终端 3：Agent API**

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
python -B -m ezllmtest.entrypoints.agent_api --repo-root "$Repo" --backend-env-file "$Repo\backend\.env" --frontend-env-file "$Repo\frontend\.env" --observability-env-file "$Repo\observability\.env"
```

**终端 4：不消费 worker**

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
python -B -m ezllmtest.entrypoints.agent_worker --repo-root "$Repo" --backend-env-file "$Repo\backend\.env" --observability-env-file "$Repo\observability\.env" --consumer local-readonly-probe --no-consume
```

**终端 5：前端**

```powershell
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
Set-Location -LiteralPath "$Repo\frontend"
npm run serve -- --env-file "$Repo\frontend\.env"
```

不消费 worker 只 `PING` Redis 并写入独立、有 TTL 的验收心跳，不创建消费组、不读取/认领/确认任务、不装配模型执行能力。它不加入正常 worker 集合，因此 Agent `/ready` 返回 **503 是预期**。可添加 `--once` 完成一次检查后退出。

准备执行自己项目的 Agent 任务时，先用 Ctrl+C 退出不消费终端，再使用普通 worker；它可能立即处理所配置 namespace 内的队列，并产生模型调用：

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
python -B -m ezllmtest.entrypoints.agent_worker --repo-root "$Repo" --backend-env-file "$Repo\backend\.env" --observability-env-file "$Repo\observability\.env" --consumer local-worker-01
```

<details>
<summary>等价 Uvicorn 指引：三个 API 的角色路径选择器</summary>

任选相应角色替代上面的 `python -m` 启动，不要重复占用同一端口。每个终端清除所有旧来源选择器，再只设置该角色允许的来源；选择器只放路径，不放秘密。当前支持单进程，不加 `--reload` 或多个 `--workers`，以下是等价指引，历史真实启动验收使用的是 `python -m`。

**观测 API**

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
foreach ($Name in @('BACKEND', 'FRONTEND', 'OBSERVABILITY')) {
    Remove-Item -LiteralPath "Env:EZLLMTEST_${Name}_ENV_FILE" -ErrorAction SilentlyContinue
}
$env:EZLLMTEST_REPO_ROOT = $Repo
$env:EZLLMTEST_OBSERVABILITY_ENV_FILE = "$Repo\observability\.env"
$env:EZLLMTEST_FRONTEND_ENV_FILE = "$Repo\frontend\.env"
python -m uvicorn ezllmtest.entrypoints.observability_api:app --host 127.0.0.1 --port 8140
```

**产品 API**

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
foreach ($Name in @('BACKEND', 'FRONTEND', 'OBSERVABILITY')) {
    Remove-Item -LiteralPath "Env:EZLLMTEST_${Name}_ENV_FILE" -ErrorAction SilentlyContinue
}
$env:EZLLMTEST_REPO_ROOT = $Repo
$env:EZLLMTEST_BACKEND_ENV_FILE = "$Repo\backend\.env"
$env:EZLLMTEST_FRONTEND_ENV_FILE = "$Repo\frontend\.env"
python -m uvicorn ezllmtest.entrypoints.product_api:app --host 127.0.0.1 --port 8230
```

**Agent API**

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
foreach ($Name in @('BACKEND', 'FRONTEND', 'OBSERVABILITY')) {
    Remove-Item -LiteralPath "Env:EZLLMTEST_${Name}_ENV_FILE" -ErrorAction SilentlyContinue
}
$env:EZLLMTEST_REPO_ROOT = $Repo
$env:EZLLMTEST_BACKEND_ENV_FILE = "$Repo\backend\.env"
$env:EZLLMTEST_FRONTEND_ENV_FILE = "$Repo\frontend\.env"
$env:EZLLMTEST_OBSERVABILITY_ENV_FILE = "$Repo\observability\.env"
python -m uvicorn ezllmtest.entrypoints.agent_api:app --host 127.0.0.1 --port 8231
```

</details>

<details>
<summary>可选 MCP：明确项目 scope 后单独启动</summary>

先创建自己的项目，将下面占位替换为真实项目 ID；不要使用历史截图标识。MCP 客户端的工具调用可能触发业务操作，需要遵守审批和预算边界。本次文档维护没有连接真实项目启动 MCP。

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
python -B -m ezllmtest.entrypoints.mcp_server --repo-root "$Repo" --backend-env-file "$Repo\backend\.env" --project-id 'REPLACE_WITH_YOUR_PROJECT_ID' --actor-id local-operator --scope-version v1 --port 8011
```

上述命令不加载遥测来源。Windows 已启动观测且需要 MCP 遥测时，显式加入 `--observability-env-file "$Repo\observability\.env"`，与同会话的观测 API 配合。MCP 协议与项目范围见[协议设计](docs/project-design.md#contracts-data)。

</details>

<details>
<summary>可选 PowerShell runner：配置检查、预检、整组启动和按归属停止</summary>

统一 runner 是便利入口。**`start` 启动普通消费 worker**，不能作为不消费验收，也不能与已手动启动的同端口进程同时运行；不自动启动 MySQL/Redis。先完成环境激活与配置：

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
Set-Location -LiteralPath $Repo
$ConfigArgs = @('--backend-env-file', "$Repo\backend\.env", '--frontend-env-file', "$Repo\frontend\.env", '--observability-env-file', "$Repo\observability\.env")
.\ops\modular\run.ps1 config-check @ConfigArgs
.\ops\modular\run.ps1 preflight @ConfigArgs
# 两项均成功且允许普通队列消费后，再启动
.\ops\modular\run.ps1 start @ConfigArgs
```

记录启动输出的 `run-id`，在同一已激活环境的 PowerShell 中操作该组进程：

```powershell
conda activate ezllmtest
$Repo = (Resolve-Path -LiteralPath 'D:\projects\EzllmTest').Path
Set-Location -LiteralPath $Repo
$RunId = 'REPLACE_WITH_RETURNED_RUN_ID'
.\ops\modular\run.ps1 status --run-id $RunId
.\ops\modular\run.ps1 ready --run-id $RunId
.\ops\modular\run.ps1 stop --run-id $RunId
```

runner 通过 PID、创建时间和归属核验停止自己启动的进程，不按端口杀进程。旧根 `scripts` 路径已退出，当前实现见 [ops/modular_runtime.py](ops/modular_runtime.py)。

</details>

<a id="linux"></a>

### 7.6 Linux：核心功能启动参考（未实机验证）

以下为 Ubuntu/Debian 风格 Bash 的静态核对参考，不代表 Linux 验收通过。先在自己的 `observability/.env` 中设置 `AGENT_TELEMETRY_ENABLED=false` 和合法 Linux 绝对数据路径。**不启动观测 API，不执行 shell runner `start`**：独立 token 共享目前只有 Windows adapter，即使关闭遥测也不能把观测 API 宣称为可用。

四个终端分别执行；每个 Python 终端都激活环境并定义 REPO。前端仍保留三个合法公开 URL，观测页面在此模式下不可用。

**终端 1：产品 API**

```bash
conda activate ezllmtest
REPO="$(realpath "$HOME/EzllmTest")"
python -B -m ezllmtest.entrypoints.product_api --repo-root "$REPO" --backend-env-file "$REPO/backend/.env" --frontend-env-file "$REPO/frontend/.env"
```

**终端 2：Agent API**

```bash
conda activate ezllmtest
REPO="$(realpath "$HOME/EzllmTest")"
python -B -m ezllmtest.entrypoints.agent_api --repo-root "$REPO" --backend-env-file "$REPO/backend/.env" --frontend-env-file "$REPO/frontend/.env" --observability-env-file "$REPO/observability/.env"
```

**终端 3：不消费 worker**

```bash
conda activate ezllmtest
REPO="$(realpath "$HOME/EzllmTest")"
python -B -m ezllmtest.entrypoints.agent_worker --repo-root "$REPO" --backend-env-file "$REPO/backend/.env" --observability-env-file "$REPO/observability/.env" --consumer linux-readonly-probe --no-consume
```

**终端 4：前端**

```bash
REPO="$(realpath "$HOME/EzllmTest")"
cd "$REPO/frontend"
npm run serve -- --env-file "$REPO/frontend/.env"
```

明确允许队列消费后，将不消费终端替换为普通 worker（会处理任务，不属于历史只读验收）：

```bash
conda activate ezllmtest
REPO="$(realpath "$HOME/EzllmTest")"
python -B -m ezllmtest.entrypoints.agent_worker --repo-root "$REPO" --backend-env-file "$REPO/backend/.env" --observability-env-file "$REPO/observability/.env" --consumer linux-worker-01
```

Linux 核心参考保留项目、生成与 Agent 的业务入口；完整本地观测、Windows IPC、多 worker 和 reload 不在这一支持声明内。无遥测时不应尝试绕过 ingestion 鉴权获取观测功能。

<a id="check-stop"></a>

### 7.7 检查、排错与停止

Windows 可用 `curl.exe`，Linux 用 `curl`。在已启动对应服务后只检查下面的健康端点与前端入口：

```powershell
curl.exe -i http://127.0.0.1:8230/health
curl.exe -i http://127.0.0.1:8230/ready
curl.exe -i http://127.0.0.1:8231/health
curl.exe -i http://127.0.0.1:8231/ready
curl.exe -i http://127.0.0.1:8140/ready
curl.exe -I http://127.0.0.1:8180/
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(8140,8180,8230,8231) } | Select-Object LocalAddress,LocalPort,OwningProcess
```

```bash
curl -i http://127.0.0.1:8230/health
curl -i http://127.0.0.1:8230/ready
curl -i http://127.0.0.1:8231/health
curl -i http://127.0.0.1:8231/ready
curl -I http://127.0.0.1:8180/
ss -ltnp
```

| 观察                                     | 解释 / 处理                                                                         |
| ---------------------------------------- | ----------------------------------------------------------------------------------- |
| 产品 `/health` 200，`/ready` 200         | 进程及最小数据库检查通过；不等于模型或生成通过                                      |
| Agent `/health` 200，`/ready` 503        | 先区分 Redis 失败与无普通 worker；不消费模式不会满足正常就绪                        |
| Windows 观测 `/ready` 200                | 本地 SQLite 可用；正常运行会写入并执行保留策略                                      |
| Linux 观测连接失败                       | 当前核心模式预期；不要改为启动 Windows 专用 token adapter                           |
| `runtime_config:*` / `frontend_config:*` | 核对允许的字段、重复项、角色来源、绝对路径、端口与 CORS；只分享错误类别，不贴秘密值 |
| 检索时报 embedding 配置/权限错误         | 核对智谱 embedding key、模型与账户权限，不只检查聊天供应商                          |
| `No module named ezllmtest`              | 本终端激活错误环境或未 editable 安装；用 `python -m pip show ezllmtest` 核对位置    |
| 端口占用 / IPC 冲突                      | 先核对已有进程归属，停止自己重复启动的实例；不换端口绕过配置契约                    |

浏览器打开 `http://127.0.0.1:8180/`。首次只看首页和介绍不产生项目；创建、上传、生成与 Agent 消费是后续主动业务操作。历史 Windows 验收只覆盖真实配置启动、不消费 worker、观测人工事件和只读页面，未覆盖登录后的完整生成链。

分终端启动按反序在各自终端 **Ctrl+C**：前端 → worker → Agent API → 产品 API → 观测 API。Linux 没有观测终端。等待 Python/Node 子进程退出，验收心跳自然过期；保留已有 MySQL/Redis 服务，不按端口强杀。runner 启动的进程则按对应 `run-id` 使用 `stop`。数据目录、`.env` 和已有数据库不因停机被清理。

<a id="performance"></a>

## 八、性能简介

实现通过完整产物缓存与项目索引缓存减少重复工作：相同项目、资料 revision、模型、提示词版本与选择命中完整有效产物时，直接恢复结果，避免重复模型调用和 embedding；索引按项目与语料身份复用、按容量/闲置 TTL 淘汰。不同输入或过期资料不会被当作相同命中。

| 已有记录                     | 数值 / 条件                           | 应如何理解                                               |
| ---------------------------- | ------------------------------------- | -------------------------------------------------------- |
| Iteration 7 方面六离线检查   | 后端 **54 项通过**；前端 **5 项通过** | 历史契约与行为检查数量，不是吞吐量                       |
| Iteration 7 方面六人工构建   | Vite 8.2.2，1202 modules，**957 ms**  | 单次本机人工配置构建，非 API 延迟、QPS 或 SLA            |
| Iteration 4 冻结前端构建 p95 | **12393.5751 → 788.016 ms**           | 同一固定机器与重复构建协议下的历史比较，不外推到当前设备 |
| Iteration 4 初始最大 JS 文件 | **443227 → 293597 B**                 | 历史构建产物体积口径，不是所有网络传输总量               |

历史证据、测量条件及 A/B/C/D/P 等级完整保留在[验证历史](docs/validation-history.md#performance-model)及[方面六记录](docs/validation-history.md#iteration7-aspect6)。本次 README 更新没有重跑性能或压力测试；正常 worker 消费、真实模型/embedding、真实项目 MCP、Linux IPC、reload/多 worker 仍不宣称已通过当前端到端验收。
