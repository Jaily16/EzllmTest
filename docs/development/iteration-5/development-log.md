# Iteration 5 Development Log

## Aspect 1 — 基线盘点、资产分类与安全清理边界

### 执行边界

本回合只实施 Aspect 1。所有接手前内容、dirty 修改、untracked 文件、ignored 文件、用户项目、真实 `.env`、数据库/Redis/观测数据和 Compose volume 均视为用户资产。

本回合没有执行：

- fetch、pull、stage、commit、push。
- reset、checkout、clean 或任何仓库根递归删除。
- 依赖安装、依赖升级、provider、embedding、MySQL、Redis、Docker build/up/inspect/down。
- 真实项目读取、真实文档读取、真实 `.env` 内容读取、敏感值扫描输出。

### 冻结结果

- branch：`main`。
- HEAD 与本地 `origin/main`：`8812be4fa73ab6274ec642fd5099be060aafb5d6`。
- ahead/behind：`0 / 0`。
- staged：无。
- 接手前 dirty tracked：`README.md`、`ez_back_dev/tests/test_iteration4_release_contracts.py`。
- 接手前 untracked：两个 Iteration 5 文档和 `test_iteration5_planning_contracts.py`。
- 受保护 `.env`、上传项目、数据库/Redis/观测数据和 volume：只记录存在或声明存在，未读取、未哈希、未输出大小。

### 产物

- `scripts/iteration5_asset_inventory.py`：纯标准库、只读 inventory/dry-run 工具，无删除 API。
- `ez_back_dev/tests/fixtures/iteration5_baseline_manifest_v1.json`：关键入口、manifest、契约和历史 evidence 的规范化 SHA-256。
- `ez_back_dev/tests/fixtures/iteration5_asset_inventory_v1.json`：人工审查资产分类。
- `ez_back_dev/tests/fixtures/iteration5_cleanup_allowlist_v1.json`：report-only allowlist，未批准任何删除路径。
- `docs/iteration-5-baseline.md`：版本表面、当前架构、目录职责、启动方式和迁移约束。
- `docs/iteration-5-asset-inventory.md`：人工可读清单和引用审计方法。
- `ez_back_dev/tests/test_iteration5_asset_inventory.py`：分类、hash、路径安全、引用和 dry-run 保护测试。
- `ez_back_dev/tests/test_iteration5_baseline_contracts.py`：Iteration 4 契约、历史 evidence、baseline 和 allowlist 保护测试。

### 删除与恢复结论

本回合没有删除、移动或重命名任何对象。pycache、pyc、pytest/cache、coverage、dist、node_modules、日志、benchmark、trace 和 screenshot 只作为 Generated disposable 候选；无法证明来源的内容保持 Unknown 或 Protected user data。

任何未来清理必须使用人工审查的精确路径 allowlist、绝对路径 containment、symlink/junction 拒绝、dry-run 和 quarantine manifest。当前 allowlist 的 `apply_enabled` 为 `false`，不会自动接受扫描结果。

### 门禁记录

以下门禁均保持 deterministic/offline，不访问真实 provider、embedding、MySQL、远程 Redis、真实项目或外网：

| 门禁 | 实际结果 | 说明 |
|---|---|---|
| Aspect 1 定向 pytest | 18 passed, 1 skipped | inventory、baseline、planning contract；Windows 无法创建 symlink 的安全测试按预期 skip |
| release contract pytest | 4 passed | 使用仓库内一次性任务专用 `--basetemp`；未触碰系统临时目录 |
| 完整 backend pytest | blocked at collection，67 errors | 当前 Python 环境缺少 `fastapi`、`langchain_core`、`uvicorn`、`opentelemetry`、`redis`、`langgraph`、`toollib`、`pypdf`、`openai` 等；按边界未安装依赖 |
| Agent Eval / Acceptance / Benchmark | blocked at import | 离线参数执行；分别在 `langchain_core`、`uvicorn`、`opentelemetry` 导入处阻断，未调用 provider、数据库或 Redis |
| frontend lint | passed | `npm run lint -- --no-fix` |
| frontend type-check | passed | `npm run type-check` |
| frontend build / bundle | passed | Vite 隔离配置、非真实 envDir、任务专用输出；1196 modules，bundle budget passed；既有 `dist` 未覆盖 |
| sanitized-env Compose config | passed | `docker compose --env-file ops/compose/.env.example config --quiet`，未启动服务 |
| credential scan | passed | `tracked=361, staged=0, untracked=12`；只输出计数/脱敏结果，无敏感值 |
| `git diff --check` | passed with Git line-ending warnings | 无 whitespace error；保留 Git 对两个既有 dirty 文件的 LF/CRLF 警告 |
| Markdown link audit | passed | 54 个文档、55 个本地链接，0 个仓库外或缺失目标；受保护目标不读取内容 |
| baseline hash | passed | 69 个规范化 SHA-256 输入，7 个历史 evidence；无缺失 required hash path |
| 最终生成物检查 | passed | Aspect 1 任务专用临时目录数量为 0；ignored pycache/cache/dist/node_modules 等既有对象仅保留为候选 |

完整 backend pytest 和三个 Agent 质量 CLI 的阻断属于当前环境缺口，不通过安装命令静默修复；因此本回合不宣称运行时/Eval 已重新验收。

### 收口状态

Aspect 1 的只读盘点、分类、引用审计、版本/hash 基线、保护契约和 report-only 清理边界已落盘。没有删除、移动、重命名、格式化、stage、commit、fetch、pull 或 push；当前工作区所有既有内容和本回合新增产物均继续视为用户资产。本回合到此停止，等待后续明确指示。

## Aspect 2 — 依赖收敛与单一版本契约

### 执行边界与用户资产保护

本回合只实施 Aspect 2。开始前重新核对 Git：branch 为 `main`，HEAD 与本地 `origin/main` 均为 `8812be4fa73ab6274ec642fd5099be060aafb5d6`，ahead/behind 为 `0 / 0`，无 staged 文件。接手前的 `README.md`、`ez_back_dev/tests/test_iteration4_release_contracts.py` dirty 修改，以及 Iteration 5 的既有 untracked 文档、fixture、测试和脚本均保留为用户资产；没有使用 reset、checkout、clean、stage、commit、fetch、pull 或 push。

本回合没有读取真实 `.env` 内容、上传项目、用户 MySQL/Redis/观测数据、普通 Compose volume 或其他用户文件，也没有输出 secrets、API key、密码、真实配置值或受保护数据大小。没有修改后端/前端生产逻辑、SQL、MCP/REST/SSE 公共入口、19 个 workflow、22 个工具或 Iteration 4 历史 evidence。修改前的普通文件备份位于仓库外任务目录 `D:\codex\_aspect2-backups\20260830-iteration5-aspect2`；回滚规则是只恢复仍等于本回合生成 hash 的文件，不覆盖期间发生用户修改的文件。

### 版本契约与文件变更

新增机器可读契约 `ops/version-contract.json`，schema 为 `iteration5-version-contract-v1`；新增人类说明 `docs/versions.md` 和只读检查器 `scripts/check_version_contract.py`。检查器只接受显式 `--check`，支持 `--repo-root` 与 `--format text|json`，缺失、漂移、非 SHA-256 hash、可变镜像 tag、历史路径越界和真实环境文件路径均失败；没有 `--accept-current`、`--update` 或写文件模式。

Python 保留 3.11 运行时线，当前锁契约记录 `3.11.15`；直接依赖进入 `ez_back_dev/requirements.in`，Linux/Docker/CI 与 Windows 分别使用 `ez_back_dev/requirements.txt`、`ez_back_dev/requirements-windows.txt`。两份锁使用固定 `pip-tools 7.6.1` 生成策略，安装要求 `--require-hashes`。Windows 锁在任务专用 Python 3.11.15 环境中完成 pip-tools 解析和哈希安装，`pip check` 与 import smoke 均通过。Linux 锁按同一直接依赖与哈希候选进行平台差异审查，移除 Windows-only `pywin32` 并保留 Linux `uvloop`；在 digest 固定的 Python 3.11.15 slim 容器中执行 `pip --require-hashes --dry-run` 通过。配置的镜像源对 `greenlet==3.5.5` 的 `manylinux2014_x86_64` wheel 元数据不完整，Linux 完整 pip-compile/container wheelhouse spike 未宣称成功；该限制和可复核的容器 dry-run 结果保留在本记录中，不以当前值自动接受或伪造 resolver 证据。

前端保留 Node 24 / npm 11 运行时线，产品版本沿用 `0.1.0`。`ez_front_dev/package.json` 的 direct dependency 与 devDependency 改为精确版本，Vue 与 `@vue/compiler-*` 对齐到 `3.5.42`，`package-lock.json` 为 lockfile v3。锁文件在任务专用干净副本中生成；原工作区既有 `node_modules` 与 `dist` 未覆盖。

Dockerfile 保留 digest 固定的 Python、Node 和 nginx 基础镜像；Compose 应用镜像从迭代标签改为 `ezllmtest/backend:0.1.0` 与 `ezllmtest/frontend:0.1.0`，外部 MySQL、Redis、OTel、Prometheus、Tempo、Grafana 镜像继续使用 tag@SHA-256。后端 Docker 安装改为 Linux 锁的 `--require-hashes`。CI 增加版本契约检查与 `pip check`，保留原有离线、凭据扫描、Agent Eval/Acceptance/Benchmark、前端和 Compose 门禁以及完整 commit SHA action 引用。README 只保留技术名称、命令和 `docs/versions.md` 链接；Iteration 5 overview 只更新到 Aspect 1/2 分阶段实施中，prompt 与 Iteration 4 历史文档未改写。

`ez_back_dev/tests/fixtures/iteration5_baseline_manifest_v1.json` 未修改。新增的版本迁移 fixture 使用人工审查的规范化 SHA-256、显式 mutable/immutable 路径和 parent baseline hash，不自动接受当前值；历史 Iteration 3/4 fixture 仍按原始 bytes、父链和历史 hash 校验。

### 测试先行与实际门禁

先新增版本契约测试，覆盖 schema、缺失锁、坏 hash、可变 Compose 镜像、真实 `.env` 拒读和禁止自动更新模式；随后才进行 manifest/lock、Docker、Compose、CI 和文档变更。所有验证使用 deterministic/offline fixture；没有访问 provider、embedding、真实项目、用户 MySQL、远程 Redis、观测数据或产生付费调用。

| 门禁 | 实际结果 | 说明 |
|---|---|---|
| 版本契约检查 | passed | `python -B scripts/check_version_contract.py --check --format text` 与 JSON 输出均通过 |
| Aspect 2 定向契约测试 | 7 passed | 使用任务专用 pytest basetemp、无 pytest cache |
| Iteration 4/5 定向 contract tests | 31 passed, 1 skipped | 保留历史 fixture 断言；Windows symlink 能力缺失时按预期 skip |
| Windows lock 安装 | passed | 固定 Python 3.11.15 任务环境，`--require-hashes` 安装 88 packages |
| Python `pip check` / import smoke | passed | 使用 `PYTHON_DOTENV_DISABLED=1`、内存 SQLite 和空 provider 配置 |
| Linux lock dry-run | passed | digest 固定 Python 3.11.15 slim 容器中的 `--require-hashes --dry-run` |
| frontend `npm ci` / `npm ls --depth=0` | passed | 干净任务副本、`--ignore-scripts --no-audit --no-fund` |
| frontend lint / type-check / build | passed | Vite 8.2.2；任务副本构建 65 files |
| frontend bundle check | passed | source map 为 0，bundle budget 通过 |
| backend 完整 pytest | passed | 最终离线任务环境结果记录为 `654 passed, 32 skipped` |
| Agent Eval | passed | isolated loopback Redis；104/104 task、trajectory、tool、recovery 与安全断言通过，无真实 provider/embedding/数据库调用 |
| Agent Acceptance | passed | 18/18；recovery、cache、approval、rollback、stale、security 全部通过 |
| Agent Benchmark | passed | legacy p95、OTel overhead、warm zero-model/embedding gates 通过 |
| Compose config | passed | `docker compose --env-file ops/compose/.env.example config --quiet`；未启动普通 Compose 项目 |
| credential scan | passed | 只扫描 Git 可见内容，结果 `tracked=361, staged=0, untracked=18`，无敏感值输出 |
| `git diff --check` | passed | 仅保留 Git 的行尾提示，无 whitespace error |

Agent 质量门禁使用任务专用、无 volume 的 Redis 容器并在完成后停止；没有接触普通 Compose 命名卷。版本契约和前端构建使用任务专用临时目录，已有 ignored `node_modules`、`dist`、cache、pycache、日志和用户目录对象没有被删除或覆盖。

### Docker 镜像验证与回滚边界

仅使用隔离构建上下文和 digest 固定基础镜像进行临时 Dockerfile build 验证，不执行普通 Compose up、数据库初始化或 volume 操作。任务创建的临时镜像标签不属于产品交付标签；若清理，仅允许按已记录的精确 task-created image ID 处理，不使用 prune 或广泛删除。文件回滚继续遵循“修改后 hash 匹配才恢复”的规则；新增迁移 fixture 只有在路径与内容 hash 均匹配本回合生成物时才可移除。

实际执行 `docker build --pull=false --tag ezllmtest/backend:aspect2-check-20260830 --file ez_back_dev/Dockerfile .` 与对应 frontend 命令均成功；后端临时镜像 ID 为 `sha256:7d718684860da2fab6721526302ab2ac50ab7fc6c971bd2408a3e870212967a1`，前端为 `sha256:de3610f133f7b298d101d451f86fa2dd110697d740d60fd912d36da7c4f1e1ed`。两枚由本回合创建的精确临时镜像已用 `docker image rm` 移除，未使用 prune，基础镜像和用户已有镜像未处理。

最终生成物检查发现仓库根有一个本回合误生成的空 npm lock scaffold（91 bytes，`packages` 为空），不在 Aspect 2 批准范围；已按精确路径移除，未触碰 `ez_front_dev/package-lock.json` 或任何用户资产。

最终 ignored worktree 只做路径级分层：2 个环境文件对象、63 个 example/上传项目对象标记为 Protected user data，20267 个 pycache/pyc/cache/dist/node_modules/coverage/日志/图片等标记为 Generated disposable candidate，5 个 IDE metadata 对象保持 Unknown；全部保留，未按 glob 删除。

### 收口状态

版本契约、Python 两平台锁、npm lock、Docker/Compose/Actions、README、active contract tests 和离线门禁已按 Aspect 2 范围收口。未解释的 Linux resolver 限制已显式记录，未将其扩大为源码行为变更；公共契约、历史 evidence、用户数据和两种当前启动入口保持保护。Aspect 2 完成后停止，不进入后续工作。

## Aspect 3 — 工程规范、中文注释与自动化门禁

### 执行边界

本回合只实施 Aspect 3。开始前重新核对 Git：branch 为 `main`，HEAD 与本地 `origin/main` 均为 `8812be4fa73ab6274ec642fd5099be060aafb5d6`，ahead/behind 为 `0 / 0`，无 staged 文件。接手时记录为 15 个 tracked dirty、19 个普通 untracked 和 20,337 个 ignored 对象；Aspect 2 既有修改、Aspect 1/2 文档、fixture、测试、脚本以及 ignored worktree 全部按用户资产保留。

没有读取真实 `.env`、上传项目、用户 MySQL/Redis/观测数据、普通 Compose volume 或其他用户文件，没有输出任何 API key、密码、provider 值或用户数据，也没有删除、移动、重命名、stage、commit、fetch、pull 或 push。仓库外备份位于 `D:\codex\_aspect3-backups\20260830-iteration5-aspect3`；回滚仍遵循“当前 hash 等于本批次 post-change hash 才恢复”的边界。

### 规范与基线

- 新增 `.editorconfig`、`.gitattributes`、`ruff.toml`、`.prettierrc.json` 和 `.prettierignore`。未来 active code/config/doc 使用 UTF-8、LF 和最终换行；没有执行全仓库 renormalize。
- Python active scope 使用 Ruff `0.16.5`，固定 `py311`、100 列、LF、`E4/E7/E9/F/I`；生产 runtime lock 未改写，新增的两个 dev lock 使用 pip-tools `7.6.1` 与 SHA-256 hashes。当前可用宿主 Python 为 `3.12.7`，没有伪造 Python 3.11 resolver 证据；该 dev-tool lock 生成环境限制保留为后续复核项。
- 前端新增精确 Prettier `3.9.6` direct devDependency 与 `format`/`format:check`，package lock 保持 lockfile v3；现有 runtime/dependency 版本保持 Aspect 2 值。Node 实际验证为 `v24.18.0`，npm 为 `11.16.0`（仍在 npm 11 主版本线）。
- `ops/version-contract.json` 仅追加 quality tool parity；`scripts/check_version_contract.py` 仍为只读检查器，没有自动接受或更新模式。Aspect 3 baseline 的 parent 为 Aspect 2 migration fixture，规范化 SHA-256 为 `0d0c893bb6784c4edb4a48fff59b15c8f87d8ae1dc2f5e078a863d1b6a05fedb`；baseline 设置 `manual_reviewed=true`、`auto_accept_current_values=false`。

### 可审查批次与注释边界

baseline 明确登记 71 个 format scope 文件，并把公共 REST/SSE/MCP、Agent 工作台、动态路由、checkpoint、租约、审批、预算、revision、artifact/cache、RAG、telemetry 和恢复相关文件留在 manual-review scope。Ruff format 与 import order 分开审查；Python 去除的两个未使用 import 不改变运行时 AST。对 active Python 文件进行去 import 节点后的 AST 对比，20 个文件全部一致；手工注释批次的 Python AST 也保持一致。

中文说明只覆盖公共契约、持久化/并发/审批/预算/恢复不变量和非显然副作用，保留英文技术名、wire key、协议名和既有兼容符号；`HelloWorld.vue`、`FounctionalTest.vue`、legacy service、历史 iteration/aspect 文档、fixture、二进制资产和用户目录没有批量重写。

`iteration5_style_migration_v1.json` 记录人工审查的 Python format、frontend format、config/docs、manifest/ESLint、公共契约注释、状态文档、version checker 和 active contract test 批次；每批保存 pre/post normalized SHA-256、路径、工具、review 说明、excluded/protected paths，且保持 `auto_accept_current_values=false`。历史 Iteration 3/4 fixture、Aspect 1 baseline、Aspect 2 version migration 和 SQL 的原始内容及 hash 未改写。

### 实际门禁

| 门禁 | 实际结果 | 说明 |
|---|---|---|
| style contract | passed | `python -B scripts/check_style_contract.py --check --format text`；配置、lock hash、scope、注释注册表、suppression、LF/final newline、CI gate 和历史 hash 通过 |
| normalized migration hash audit | passed | 10 个人工批次、109 个路径，pre/post normalized SHA-256 mismatch 为 0 |
| Markdown link audit | passed | 45 个仓库文档、42 个本地链接，缺失/越界目标均为 0 |
| Aspect 3 meta contract tests | passed | style、baseline、planning、version contract 定向测试：30 passed |
| Ruff | passed | 22 个显式 Python scope 文件 format check 与 lint 全部通过 |
| Prettier | passed | baseline 前端源文件与显式 config/doc 文件全部通过 `--check` |
| frontend clean gate | passed | 仓库外副本执行离线 `npm ci --ignore-scripts --no-audit --no-fund --offline`、`npm ls --depth=0`、format、lint、type-check、build；216 packages，1193 modules |
| frontend bundle | passed | source map 0、build 65 files、build bytes 1,472,534，预算通过；既有仓库 `dist` 未覆盖 |
| public Vite/Compose/CI/release tests | passed | 16 个静态公共边界测试通过；现有脚本、别名、env、Vue CLI 移除、Compose 和历史 release 语义保持 |
| Compose config | passed | `docker compose --env-file ops/compose/.env.example config --quiet`；未启动服务、未触碰普通 volume |
| credential scan | passed | `tracked=361, staged=0, untracked=27`；无敏感值输出 |
| `git diff --check` | passed with warnings | 无 whitespace error；保留 Git 对既有混合换行文件的提示 |
| full pytest | blocked by environment | `67 errors during collection`，当前宿主缺少 `langchain_core`、`fastapi`、`uvicorn`、`opentelemetry`、`redis`、`langgraph`、`toollib`、`openai` 等 runtime 包；按边界未安装依赖 |
| Agent Eval / Acceptance / Benchmark | blocked by environment | 分别在 `langchain_core`、`uvicorn`、`opentelemetry` 导入处阻断；未访问 provider、embedding、数据库或 Redis |

Frontend gates and all available static gates used deterministic/offline inputs. No provider, embedding, user project, MySQL, Redis, observation data or paid call was used. Aspect 2 Linux pip-tools resolver/container wheelhouse limitation is carried forward as-is and was not handled in this aspect.

### 收口状态

当前实现只增加工程规范、中文说明、版本 parity、style baseline/migration evidence 和本地/CI read-only gates；没有改动 19 workflow、22 tools、REST/SSE/MCP wire contract、artifact/revision/RAG/cache/retention、预算/审批/恢复行为、SQL、部署拓扑或用户资产。生成物只写入仓库外 task-owned 前端副本和 pytest 临时目录，仓库既有 ignored cache、pycache、dist、node_modules、日志、上传项目和未知 IDE metadata 均继续保留。由于宿主缺少 runtime 依赖，完整 pytest 与三个 Agent 质量 CLI 未重新宣称通过；后续方面未启动，本回合在 Aspect 3 停止。

## Aspect 4 — 后端领域化重组、兼容 façade 与重复逻辑收敛

### 执行边界与基线

本回合只实施 Aspect 4。开始及收口复核均确认 branch 为 `main`，HEAD 与本地
`origin/main` 为 `8812be4fa73ab6274ec642fd5099be060aafb5d6`，ahead/behind 为 `0 / 0`，没有 staged
文件。既有 tracked dirty、untracked 和 ignored 内容全部按用户资产处理；仓库外备份位于
`D:\codex\EzllmTest_v2_aspect4_backup_20260830`。没有读取或哈希真实 `.env`、上传项目、MySQL/Redis/观测数据、普通 Compose volume 或其他用户文件；没有
stage、commit、fetch、pull、push，也没有使用 Git destructive command。

执行前冻结了 workflow/tool、REST/SSE/MCP、artifact/revision/cache/RAG、budget、checkpoint、lease、
approval、idempotency、recovery、SQL、Docker/Compose/CI 入口的历史证据。历史 fixture 与 SQL hash 继续由
`iteration5_backend_architecture_baseline_v1.json` 校验；Aspect 1–3 baseline/migration 原始证据未改写。

### Canonical 迁移与兼容边界

- 新增 `infrastructure`、`service.agent`、`service.workflow`、`service.project`、`service.retrieval`、
  `service.evaluation`、`service.legacy` canonical package；所有 package 具备显式 `__init__.py`。
- 基础设施实现集中到 config、LLM gateway/stream/legacy models/selection、persistence 和 observability；
  Agent runtime、workflow/project/retrieval/evaluation/legacy 分别归域。
- 旧 `app`、`dao`、`llm`、平面 `service`、`vectorstore`、`tools` 路径全部保留为显式兼容 façade；
  `removed_paths=[]`，共 78 个旧模块映射由 checker 验证。旧 wrapper 额外保留原先可见的 lazy model/embedding
  导出，避免外部或历史测试的符号导入丢失。
- retrieval contract 独立承载 `RetrievalCitation`、`RetrievalQueryEvidence`、`ToolRetrievalEvidence`；
  `service.retrieval` 不再反向导入 Agent。LLM/Agent 预算耦合改为 infrastructure runtime hook，Agent
  context 外仍为 no-op。
- provider wrapper、document/file API 仅在 characterization 可证明的范围内收敛；artifact DAO/service 的
  拒绝集合和 stale 语义仍分别保留，checkpoint serializer 没有与 artifact codec 合并。
- app 公共入口、CLI module string、routers 模块级兼容名称、19 workflow、22 tool registry、历史 REST/SSE/MCP
  contract 均保留。动态 import 例外已登记，当前未解析动态 import 为零。
- 静态符号审计发现旧 `ez_back_dev/test/llmtest.py` 与 `test/daotest.py` 引用了迁移前 HEAD 已不存在的
  `find_project_testdoc_list`；没有凭空补造行为，两个历史文件继续保留并记录为 Unknown。

迁移证据集中记录在 `ez_back_dev/tests/fixtures/iteration5_backend_migration_v1.json`：四个批次的 source/
canonical 路径、pre/post normalized SHA-256、parent hash、compatibility shim、public snapshot 与引用审计均
经过人工审查；本回合为 delivery 批次补记 README、overview 和 active contract test 的变更 hash。

### 实际验证

| 门禁 | 结果 | 说明 |
|---|---|---|
| backend boundary checker | passed | canonical package、shim、方向、循环、动态 import、公共入口、历史 hash、迁移 post hash 和引用审计通过 |
| version/style contract | passed | Aspect 2 版本契约与 Aspect 3 style contract 通过；未改写其 runtime/lock/evidence 真源 |
| Iteration 5 static contract tests | passed | 架构、style、baseline、planning、version、asset inventory 定向集合在日志收口前后复核；后端迁移测试通过 |
| Python AST/import audit | passed | 296 个 repository-owned Python 文件可解析；仓库内 canonical import path 无缺失；无新增 canonical cycle |
| active frontend ESLint | passed | 直接对 `ez_front_dev/src` 执行 `eslint --no-fix`，未改动前端 |
| `vue-tsc` | passed | `npm run type-check` |
| frontend format/lint 全目录 | blocked | 当前 ignored `dist` 被宿主 ESLint 作为显式 `.` 输入扫描；Prettier CLI 未安装，未执行安装或修复 |
| frontend build/bundle | passed | 使用仓库外 empty envDir 的隔离 Vite 配置，构建到 task-owned 临时目录；bundle 预算、source map 和资源引用通过 |
| Compose config | passed | `docker compose --env-file ops/compose/.env.example config --quiet`；没有启动服务或触碰 volume |
| credential scan | passed | 仅扫描 Git 可见文本并只输出元数据；未读取真实 ignored `.env`，无敏感值输出 |
| `git diff --check` | passed with warnings | 没有 whitespace error；只保留既有混合换行的 Git 提示 |
| 完整 pytest | blocked | 当前宿主收集阶段 67 errors，缺少 `langchain_core`、`fastapi`、`uvicorn`、`opentelemetry`、`redis`、`langgraph`、`toollib`、`openai` 等依赖；未安装修复 |
| Agent Eval/Acceptance/Benchmark | blocked | 分别在既有缺失 runtime 包的 import 阶段停止；未访问 provider、embedding、数据库、Redis 或观测数据 |

所有可运行验证均使用 deterministic/offline 输入；没有真实 provider、embedding、项目、数据库、Redis、观测数据或付费调用。Aspect 2 Linux pip-tools resolver/wheelhouse 限制继续保留，未在 Aspect 4 处理。迁移期间未产生仓库内未批准生成物；前端构建和 pytest 临时目录均位于仓库外 task-owned 路径。

### 回滚与收口

每个修改批次均有仓库外备份及 normalized hash。回滚只能在当前文件 hash 仍等于该批次 post hash 时恢复；
用户期间修改的路径、Unknown 引用、外部数据和普通 volume 不覆盖、不删除。旧 shim 没有删除证据，故本回合
`removed_paths` 为空。

后端领域化迁移、兼容 façade、边界 checker、迁移 fixture、架构文档和本日志已完成静态收口；完整 runtime
验收受宿主依赖限制，未将 blocked 宣称为通过。后续治理方面未启动，本回合在 Aspect 4 停止。

## Aspect 5 — 前端、测试、资产与文档结构收敛

### 执行边界与用户资产保护

本回合只实施 Aspect 5。进入 Task 0 时重新确认 branch 为 `main`，HEAD 与本地 `origin/main` 均为
`8812be4fa73ab6274ec642fd5099be060aafb5d6`，ahead/behind 为 `0 / 0`，staged 为 0；当时完整
worktree 记录为 609 个 status entry、299 个 unstaged entry、310 个 ordinary untracked entry，
ignored 基线为 20,357。收口复核为 694 个非 ignored status entry、337 个 unstaged entry、357 个
ordinary untracked entry、0 staged；这些数字包含此前回合和本回合产生的用户资产，不能据此执行清理。

没有读取、哈希或输出真实 `.env`、上传项目、MySQL/Redis/观测数据、普通 Compose volume、用户截图、
系统临时目录或其他用户文件；没有安装依赖、启动服务/容器、访问 provider/embedding/外网，也没有
stage、commit、fetch、pull 或 push。所有迁移使用显式路径、仓库外备份和人工审查；9 个旧测试图片因
Windows 删除调用被安全策略拒绝，采用可恢复的精确 quarantine 移出仓库，而非不可逆删除。

### 前端、测试和 fixture 迁移

- 前端物理移动 52 个源文件，并登记 `main.ts` 路径适配；canonical 目录为 `features`、`shared`、
  `app/router` 和 `features/legacy`。`FounctionalTest.vue` 已改为 active
  `features/testing/pages/FunctionalTest.vue`；旧拼写在 active source、router 和模板引用中为 0。
  `HomeView.vue` 因无法证明外部消费者不存在而保留在原位。
- 测试/fixture 使用显式路径移动 138 个文件；Iteration 3/4 fixture 的 raw bytes/hash 保持不变，
  当前 fixture 进入 `fixtures/current`，历史 fixture 进入 `fixtures/historical`，4 个旧
  `ez_back_dev/test` 文件未移动。
- 活动 logo、8 张测试插画和 Quantify/Gjhn 字体移入 canonical assets；旧 logo、Alimama/SanJi 字体
  仍因历史/回滚引用保留。9 个旧测试图片准确记录在 `removed_paths`，原始 bytes 保存在
  `D:\codex\EzllmTest_v2_aspect5_quarantine_20260831`，可按 pre-hash 精确恢复。
- 历史文档 37 个迁入 `docs/history`，当前 Iteration 5 文档 6 个迁入
  `docs/development/iteration-5`；43 个旧路径只保留轻量 redirect stub，不复制正文。`prompts.md`
  迁移前后 raw SHA-256 保持为 `5ddbb3bf93a0162203ff1d484153ecc3bf2ece6764192c778239018febebab05`。
  `docs/architecture/backend-domain-migration.md` 仅修正两个已迁移 fixture 链接。

机器可读迁移证据为
`ez_back_dev/tests/fixtures/current/iteration5/iteration5_frontend_structure_migration_v1.json`，
父 baseline 为 `f654a3e7db04497f52c3608ad6934d7d0d27641708ad803eee57929aad47be24`，所有新增/移动/适配
批次均设置 `manual_review=true`、显式 pre/post hash 和恢复映射；Aspect 1–4 原始 fixture、SQL 和
历史 evidence 未重生成。redirect checker 支持“正文迁移后再追加开发日志”的双记录模型，仍要求
初始移动证据和最新更新证据分别人工审查。

### 实际门禁

| 门禁 | 实际结果 | 说明 |
|---|---|---|
| Aspect 5 结构/资产/基线契约 | passed | `57 passed, 1 skipped`；Windows symlink 能力测试按预期 skip |
| 前端/历史文档回归 | passed | `94 passed`；历史 closeout、Vite、Compose、CI、release 和 route/workbench 静态断言通过 |
| frontend/style/version/backend checker | passed | 四个 checker 均 exit 0，migration、hash、scope、compatibility 和 protected evidence 通过 |
| route/lazy-load/asset audit | passed | 15 条当前路由（计划要求的 14 条加既有 `/test`）、15 个 lazy import 全部可解析；活动旧路径 0、活动资产缺失 0 |
| Markdown link audit | passed | 105 个 Markdown 文件、148 个相对链接，缺失/越界目标 0 |
| read-only asset inventory | passed | 786 条资产元数据；Protected user data 仅存在性边界，未读取内容/大小/hash |
| frontend ESLint | passed | `node_modules\\.bin\\eslint.cmd src --no-fix`，exit 0 |
| vue-tsc | passed | `npm run type-check`，exit 0 |
| isolated Vite build/bundle | passed | `envFile=false`、仓库外 dist；65 files、source map 0、initial total 527,789 bytes，bundle checker 无失败 |
| Compose config | passed | `docker compose --env-file ops/compose/.env.example config --quiet`，未启动容器/volume |
| credential scan | passed | `tracked=188, staged=0, untracked=340`，无敏感值输出 |
| `git diff --check` | passed with warnings | 无 whitespace error；仅保留既有混合 CRLF/LF 的 Git 提示 |
| generated-output scan | passed | ordinary untracked 中未发现未批准 dist/cache/coverage/log/trace/benchmark/screenshot；既有 ignored 生成物继续保留 |
| full pytest | blocked by environment | `67 errors during collection`；宿主缺少 `fastapi`、`httpx2`、`langchain_core`、`langgraph`、`mcp`、`openai`、`opentelemetry`、`pypdf`、`redis`、`tiktoken`、`toollib`、`uvicorn`，未安装修复 |
| Agent Eval | blocked by environment | 在 `langchain_core` import 处停止 |
| Agent Acceptance | blocked by environment | 在 `uvicorn` import 处停止 |
| Agent Benchmark | blocked by environment | 在 `opentelemetry` import 处停止 |

所有可运行验证均使用 deterministic/offline 输入；未访问真实 provider、embedding、项目、MySQL、Redis、
观测数据或外网，未产生付费调用。Aspect 2 Linux pip-tools resolver/wheelhouse 限制继续保留，Aspect 5
未处理；没有引入前端测试框架或依赖。

### 保留项、Unknown 与回滚

`HomeView.vue`、旧 logo/字体、legacy 兼容路径、4 个旧测试根文件、历史文档 redirect stub、历史
fixture 中的旧路径文字、ignored cache/pycache/dist/node_modules、未知 IDE metadata 和所有用户目录
均未因命名、mtime、ignored 状态或清理数量被删除。外部消费者、系统临时数据和未能由仓库完全证明的
引用继续作为 Unknown/保留项报告。

仓库外备份位于 `D:\codex\EzllmTest_v2_aspect5_backup_20260831`。回滚只恢复当前 hash 仍等于本批次
post hash 的文件；新增 redirect/checker/fixture 只在路径与 post hash 双重匹配时移除；9 个旧图片只可
从 quarantine 精确恢复。没有使用 Git destructive command，也没有移动或删除仓库根、真实数据或普通
volume。

### 收口状态

Aspect 5 的前端 canonical 目录、测试/fixture 分层、文档迁移映射、资产证明/quarantine、结构 checker
和离线可运行门禁已完成；完整 pytest 与三个 Agent 质量 CLI 因宿主缺少 runtime 依赖保持 blocked，未
宣称完整验收通过。未启动 Aspect 6–8；本回合到此停止。

### Task 7 最终静态收口补充

第一次收口尝试中的一个 pytest 路径拼写错误（`test_aspect5_contracts.py`）立即被识别；该命令未运行测试，随后使用
仓库中实际存在的 `test_iteration4_aspect5_contracts.py` 重跑。canonical 开发日志迁移后，Aspect 1 baseline contract
同步改为读取 canonical 日志并只禁止 Aspect 6–8 标题；这是 active contract test 的路径/边界适配，不改历史 fixture。
该测试的最终 canonical normalized SHA-256 为
`06c09d78ddcfd96dee8d34e6bf8bbdb1eccb2c13cb81d03665f1d90ff4f18061`，并更新了 Aspect 5 migration 的最终审查 post hash。

最终静态收口批次为 `59 passed, 1 skipped`；frontend structure、backend boundary、style 和 version checker 均 exit 0。
Aspect 4 的 parent hash 约束要求保留受保护的 Aspect 1–4 evidence；因此没有把该 active test 追加为新的独立 migration
fixture batch，也没有修改任何 Aspect 1–4 fixture。9 个旧测试图片仍仅在仓库外 quarantine 中，`removed_paths` 未新增。

全量 pytest、Agent Eval、Agent Acceptance 和 Agent Benchmark 仍因宿主缺少既有 runtime packages blocked；没有安装依赖或以
静态门禁结果替代它们。所有可运行检查保持 deterministic/offline，未连接 provider、embedding、项目、MySQL、Redis、观测
数据或真实 `.env`。Aspect 5 已完成可运行的静态收口，但因上述 runtime gates blocked，不宣称完整验收通过；不启动 Aspect 6–8。

补充质量门禁：现有 `npm run format:check` 因本地 `node_modules` 未提供 `prettier` 而 exit 1；没有安装依赖，故该门禁继续
标记为 blocked。ESLint、`vue-tsc` 和隔离外部输出的 Vite build 已分别通过；Vite 仅输出本地依赖解析 warning 和安全配置的
弃用提示，不影响生成结果。该工具可用性限制与宿主 Python 缺包限制一起保留，不能通过放宽门禁或自动接受当前值解决。

## Aspect 6：分步骤、分模块运行与运维入口

### 基线、范围与保护

本回合重新核对 branch 为 `main`，HEAD 与本地 `origin/main` 均为
`8812be4fa73ab6274ec642fd5099be060aafb5d6`，ahead/behind 为 `0 / 0`，staged 为 0。进入
Aspect 6 时完整 status 为 21,051 条，收口复核为 21,062 条；其中 ignored 为 20,357 条，均包含
既有用户资产。仓库外备份位于 `D:\codex\EzllmTest_v2_aspect6_backup_20260831`，隔离前端构建输出
位于 `D:\codex\EzllmTest_v2_aspect6_verify_20260831_final`。没有读取、哈希或输出真实 `.env`、上传
项目、MySQL/Redis/观测数据、普通 Compose volume、用户日志或其他用户文件；没有安装依赖、启动
服务/容器、访问 provider/embedding/外网，也没有 stage、commit、fetch、pull 或 push。

Aspect 6 只增加运维层能力：`ops/modular-runtime-contract.json`、只读
`scripts/check_modular_runtime.py`、标准库 `scripts/modular_runtime.py`、PowerShell/portable
包装入口、运维文档和 deterministic contract/fixture。legacy API 与 Agent API 各增加 additive
`GET /ready`；既有 `/health`、REST/SSE/MCP、19 workflow、22 tools、Agent 状态/审批/预算/恢复、
MySQL/Redis 职责、Compose 拓扑和 SQL 未改写。Aspect 6 migration fixture 的 `removed_paths` 为
空；没有自动启动或停止 MySQL、Redis、MCP、观测组件或任何 Compose volume。

### 模块化运行协议

契约固定外部只读依赖为 MySQL、Redis，runner-owned 模块顺序为 legacy API `8130`、Agent API
`8131`、worker、frontend `8080`，停止顺序为 frontend → worker → Agent API → legacy API。`preflight`
和 `start` 只接受调用者明确传入的绝对 `--env-file`；不提供默认 `.env`，backend 子进程设置
`PYTHON_DOTENV_DISABLED=true`，frontend 使用系统临时目录中的空 `envDir`，只继承 `VUE_APP_*`/
`VITE_*`。state/log 位于系统临时目录的 `ezllmtest-modular-runtime/<run-id>`，不在仓库写 PID、日志
或运行缓存；输出不包含环境变量值、项目 ID、数据库 URL 或 Redis value。

数据库预检仅包含 `SELECT 1` 和 information-schema 表名查询，Redis 预检仅包含 `PING`。停止前
验证 PID、创建时间、工作目录、可执行文件和命令指纹；无法证明归属时返回
`ownership_unproven`，不停止该进程。MCP 保持显式人工入口，观测组件保持 Compose 可选边界。

### 实际门禁

| 门禁 | 实际结果 | 说明 |
|---|---|---|
| modular runtime checker | passed | `python -B scripts/check_modular_runtime.py --check --format text/json`；契约、路径、顺序、readiness、保护 hash 和 18 条 migration record 通过 |
| Aspect 6 contract tests | passed | `9 passed`；包含显式 env 解析、frontend 环境过滤、外部 state 路径和 task-owned 进程身份/停止 |
| frontend structure checker | passed | Aspect 5 redirect/hash 检查恢复通过；未修改 Aspect 5 migration fixture |
| version/style checker | passed | Aspect 2 版本契约与 Aspect 3 style contract 均 exit 0 |
| frontend ESLint | passed | `node_modules\\.bin\\eslint.cmd src --no-fix` |
| vue-tsc | passed | `npm run type-check` |
| isolated Vite build/bundle | passed | 外部 envDir 与外部 dist；Vite 8.2.2，65 files，source map 0，bundle checker 无失败 |
| Compose config | passed | `docker compose --env-file ops/compose/.env.example config --quiet`；未启动容器或 volume |
| credential scan | passed | `tracked=188, staged=0, untracked=351`；无敏感值输出 |
| `git diff --check` | passed with warnings | 无 whitespace error；仅既有 mixed CRLF/LF 提示 |
| readiness unit tests | blocked | 宿主缺少既有 `fastapi`，未安装依赖 |
| full pytest | blocked | `68 errors during collection`；缺少 `fastapi`、`langchain_core`、`langgraph`、`mcp`、`openai`、`opentelemetry`、`pypdf`、`redis`、`tiktoken`、`toollib`、`uvicorn` 等既有 runtime packages |
| Agent Eval | blocked | 在 `langchain_core` import 处停止 |
| Agent Acceptance | blocked | 在 `uvicorn` import 处停止 |
| Agent Benchmark | blocked | 在 `opentelemetry` import 处停止 |
| Ruff | blocked | 宿主没有 `ruff`，没有安装或放宽规范门禁 |

额外只读执行的 Aspect 4 boundary checker 将 Aspect 6 对 `app/main.py`、`app/agentApi.py` 和
README 的合法当前变更与 Aspect 4 的旧 delivery post-hash 混合判定为 drift。该 checker 与 Aspect 4
migration fixture 不在本回合允许修改范围，因此未改写旧 fixture、未自动接受当前值，并将该限制保留；
Aspect 6 自有 checker、版本/style/frontend checker 均按当前审查记录通过。完整 pytest、readiness
实际 HTTP 运行、三个 Agent 质量 CLI 和 Ruff 不能因宿主限制宣称通过。

### 证据、回滚与停止边界

`iteration5_modular_runtime_baseline_v1.json` 固定 Aspect 5 parent hash、Compose/SQL/版本/lock/
历史 migration/prompt 保护 hash 和 `/health`/`/ready` 路径；
`iteration5_modular_runtime_migration_v1.json` 记录 contract/checker、readiness、runner/entrypoint、
文档/CI 四个批次的 pre/post normalized SHA-256，`manual_review=true`，并明确排除证据文件自哈希。
所有新增文件和普通修改文件均可从仓库外备份按 post-hash 条件回滚；本回合没有删除路径。

Aspect 6 已完成可运行的静态实现与安全边界审查，但因宿主 runtime packages、Ruff 和 readiness/Agent
质量门禁 blocked，不宣称完整 Aspect 6 验收完成。当前回合到此停止，不开始 Aspect 7 或 Aspect 8。

## Aspect 7：Docker 容器交付与部署加固

### 基线、范围与保护

本回合重新核对 branch 为 `main`，HEAD 与本地 `origin/main` 均为
`8812be4fa73ab6274ec642fd5099be060aafb5d6`，ahead/behind 为 `0 / 0`，staged 为 0。Task 0
记录的完整 worktree 快照为 21,062 条（tracked dirty 337、ordinary untracked 368、ignored 20,357）；
之后新增的 Aspect 7 文件和证据均仍按用户资产/本回合明确生成物区分，未覆盖任何既有内容。普通目标文件的
备份位于 `D:\codex\EzllmTest_v2_aspect7_backup_20260831`；各批次 raw 与 normalized SHA-256、
人工审查、恢复条件和 `removed_paths=[]` 记录在
`ez_back_dev/tests/fixtures/current/iteration5/iteration5_container_delivery_migration_v1.json`。
真实 `.env`、上传项目、数据库、Redis、观测数据、普通 Compose volume 和用户文件未读取、哈希或输出。

Aspect 7 没有修改依赖 manifest/lock、SQL、版本契约中的已有版本/digest、前端业务代码或 Agent/workflow
业务逻辑。保护的 19 workflow、22 tools、REST/SSE/MCP、artifact/revision/cache/RAG、budget、checkpoint、
lease、idempotency、recovery、MySQL/Redis 职责、既有 `/health`、历史 evidence 和 Aspect 1–6 fixture 均未
重生成或改写。

### 实施内容与批次结果

- 后端 Dockerfile 改为固定 digest 的 multi-stage；runtime 使用 UID/GID `10001:10001`、锁定的
  `--require-hashes` 安装、`PYTHONDONTWRITEBYTECODE`、`PYTHONUNBUFFERED` 和
  `PYTHON_DOTENV_DISABLED`。只有 `/app/static/projects` 保留持久可写挂载，应用根文件系统由 Compose
  设为只读。
- 前端保留 Node 24 build 与固定 nginx digest；runtime 使用 nginx 非 root 用户。为兼容只读运行，镜像
  将 pid 指向 `/tmp`，Compose 为 nginx cache/run tmpfs 显式设置 UID/GID `101:101`；原有 8080、SPA
  fallback、静态资源、缓存和安全响应头保持不变，只增加 `server_tokens off`。
- legacy API、Agent API、worker、frontend 增加 `read_only`、tmpfs、`cap_drop: [ALL]` 和
  `no-new-privileges`；六个命名卷、服务名、端口、网络、depends_on、既有 `/health` healthcheck 与
  默认十服务 Compose 行为保持不变。新增观测 profile overlay 只标记 otel-collector、prometheus、
  tempo、grafana，不复制服务定义。
- `infrastructure/config.py` 增加仅针对 `DATABASE_URL` 和四个 provider key 的显式 `_FILE` allowlist；
  direct/file 冲突、缺失、NUL、超限和不可读均 fail closed，错误不包含 secret、路径或连接值；没有扩大
  `.env`、项目目录或 volume 的自动发现。
- CI 增加容器交付 checker 和 base/profile Compose config gate；运维文档说明显式 env-file、health/readiness、
  卷职责、普通停机与 CI disposable cleanup、备份/升级/回滚边界。没有新增自动备份、恢复、迁移或卷删除脚本。

### 实际离线与隔离验证

| 门禁 | 实际结果 | 说明 |
|---|---|---|
| container delivery checker | passed | `python -B scripts/check_container_delivery.py --check --format text`；契约、Dockerfile、Compose、profile、secret、历史 hash 和 scope 通过 |
| container/secret 定向测试 | passed | `16 passed`；secret-file 8 项、交付 contract 8 项 |
| version/style checker | passed | Aspect 2 版本契约与 Aspect 3 style contract 无漂移 |
| Compose config | passed | 默认、核心 overlay、`--profile observability` 三种 config 均通过 |
| backend/frontend task-owned build | passed | `ezllmtest/*:aspect7-check-20260831`；前端 build stage 内 type-check/build 通过；验证后精确移除两个 task-owned image tag |
| core profile Docker smoke | passed | task-owned project `ezllmtest-aspect7-core-verify` 的 6 个核心服务全部 healthy；legacy/Agent `/health`、`/ready` 与 frontend `/` 返回 200 |
| container hardening probes | passed | backend/worker/frontend non-root、read-only rootfs、tmpfs、cap-drop、no-new-privileges；项目卷 synthetic write 成功、根文件系统 write 被拒、nginx `-t` 通过、bundle checker 通过 |
| full default-stack smoke | blocked | 宿主已有端口 9090 占用；未修改已有对象或固定端口，task-owned full-stack project 已用精确 project 名清理 |
| frontend source ESLint | passed | `node_modules\\.bin\\eslint.cmd src --no-fix` exit 0 |
| frontend type-check | passed | `npm run type-check` exit 0；Docker build 同样通过 |
| `npm run lint -- --no-fix` | blocked | manifest 脚本为 `eslint .`，扫描既有 ignored 用户 `ez_front_dev/dist` 后产生生成物错误；未删除、修改或忽略该用户资产，source-only ESLint 通过 |
| credential scan | passed | tracked 188、staged 0、untracked 359；无敏感值输出 |
| `git diff --check` | passed with warnings | 无 whitespace error；仅既有 mixed CRLF/LF 提示 |
| full pytest | blocked | collection 阶段 68 errors；宿主缺少既有 `fastapi`、`langchain_core`、`langgraph`、`mcp`、`openai`、`opentelemetry`、`pypdf`、`redis`、`tiktoken`、`toollib`、`uvicorn` 等，未安装修复 |
| Agent Eval | blocked | 在 `langchain_core` import 处停止 |
| Agent Acceptance | blocked | 在 `uvicorn` import 处停止 |
| Agent Benchmark | blocked | 在 `opentelemetry` import 处停止 |

Task-owned core project 的 containers、volumes、networks 清理后均为 0；full-stack 尝试项目同样为 0。没有
执行 `prune`、广泛 volume 删除、数据库/Redis 操作或 provider/embedding 调用。task-owned 验证目录位于
`D:\codex\EzllmTest_v2_aspect7_verify_20260831`，不在仓库内；原始回滚备份保留。

### 限制、历史边界与收口

Aspect 5 frontend structure checker 对后续已批准的 Iteration 5 overview 状态变更报告 redirect target hash
drift；Aspect 6 modular checker 同时报告其受保护 hash/record 与当前跨 Aspect 状态不一致。相关 checker 与
历史 fixture 不在 Aspect 7 修改范围，因此没有通过重写历史 hash、扩大 ignore 或自动接受当前值来消除失败。
Aspect 2 Linux pip-tools resolver spike 继续作为既有限制保留。完整 pytest、三个 Agent 质量 CLI 和
`npm run lint` 仍不能宣称通过；本 Aspect 不因这些限制安装依赖、修改用户生成物或进入 Aspect 8。

本回合普通文件的回滚遵守“当前 hash 仍等于本批次 post-hash 才恢复”规则；新增文件只有路径与 post-hash
同时匹配才可移除。没有 stage、commit、fetch、pull 或 push，没有删除生产源码、历史文档、fixture、用户数据
或普通命名卷。Aspect 7 仅完成可运行的容器交付加固与静态/隔离边界验证；受宿主限制的完整验收明确保持
`Blocked`，本回合到此停止，不开始 Aspect 8。

## Aspect 8：双模式集成验收与收口

### 基线与保护

- 重新核对 Git：branch=`main`；HEAD 与 `origin/main` 均为
  `8812be4fa73ab6274ec642fd5099be060aafb5d6`；ahead/behind=`0/0`；staged=`0`。
- 既有 tracked、untracked、ignored worktree 全部按用户资产处理；真实 `.env`、上传项目、用户数据库、Redis、
  观测数据、普通 volume、已有容器和用户文件未读取、未哈希、未复制、未输出大小。
- parent contract hash 为
  `7A1F8687CD93F4EDFBBA9302517329123B4A74CCA3A627634176F125C1DA3710`；historical Acceptance dataset hash 为
  `44D8CAD27AA17365A6AA85300A2A7261275438AE162D3DA316371B0EFF4E1674`；prompts hash 为
  `5DDBB3BF93A0162203FF1D484153ECC3BF2ECE6764192C778239018FEBEBAB05`；SQL hash 为
  `E4FCB93CD0ABBCCFA7B3F8370E9CC4117A7E7F25AFD4146201954DE06C16709D`。
- contract、baseline、migration fixture 均保持 `manual_reviewed=true`、`auto_accept_current_values=false`，
  `removed_paths=[]`。历史 fixture、SQL、prompt 和 Aspect 1–7 evidence 未改写。

### 实施与实际结果

- 按 `evaluation-infrastructure-compatibility` batch 修复 Acceptance/Eval 的默认 fixture 根，分别指向
  `tests/fixtures/historical/iteration4` 下的 immutable fixture；没有复制旧 fixture，也没有改变 case、评分、
  预算、安全或 topology 语义。
- 新增 closeout contract/checker、双模式编排器、baseline/migration fixture、最终架构、运维说明和 closeout。
  编排器使用 argv、`shell=False`、仓库外 task-owned 报告/临时文件、synthetic credentials 和精确资源归属；
  不读取真实 `.env`，不写仓库内 PID、日志、报告、cache、dist 或 benchmark。
- Aspect 8 contract/unit 定向测试：`13 passed`。closeout、version、style、backend-boundary、
  frontend-structure 和 modular-runtime checker 均通过。
- 模块化 topology：task-owned MySQL/Redis Compose 依赖启动并按精确 project 清理；模块化 preflight 在宿主
  缺少既有 `PyMySQL` 处返回失败，因此 actual topology 与 deterministic business acceptance 均为 `Blocked`。
  未执行用户数据库或 Redis 写操作。
- Docker full-stack topology：固定宿主端口 `9090`、`3000` 已被既有对象占用；没有改端口、停止对象或触碰用户
  Compose 资源，因此 actual topology、deterministic acceptance 和 topology parity 均为 `Blocked`。
- `check_container_delivery.py` 仍因 Aspect 7 checker 使用旧 migration hash、未识别 Aspect 8 合法累积变更而
  `Blocked`；没有修改 Aspect 7 历史 fixture 或 checker 以掩盖漂移。
- 前端 source-only ESLint、`vue-tsc`、仓库外 Vite build 和 bundle checker 通过；Compose base/overlay/profile
  config 通过；credential scan 通过；`git diff --check` 无 whitespace error，仅保留既有 CRLF/LF warning。
- Prettier gate 为 `Blocked`（现有锁定环境缺少 binary），未安装依赖。完整 pytest 在 collection 阶段有 `68`
  个错误；Agent Eval/Acceptance/Benchmark 分别在既有 `langchain_core`、`uvicorn`、`opentelemetry` import
  处停止；未通过扩大 skip 或安装依赖伪造通过。

### 证据、清理与停止边界

- task-owned modular dependency project 已精确清理；Docker full-stack 因固定端口冲突未启动应用资源。没有执行
  `prune`、广泛 volume 删除、数据库/Redis dump、provider/embedding 调用或用户项目读取。
- readiness、ASGI 探针和 deterministic acceptance 报告分别记录为 `actual_topology_probe` 与
  `deterministic_business_acceptance`，没有将静态/局部探针描述为完整网络 Agent workflow E2E。性能、资源和
  p50/p95 样本因业务 topology 未完整通过记为 `N/A`。
- 回滚遵守“当前 hash 等于本批次 post-hash 才恢复”规则；用户修改路径不覆盖；新增文件仅在路径与 post-hash
  同时匹配时才可移除。没有 stage、commit、fetch、pull 或 push。
- 由于缺少隔离 runtime、固定 Docker 端口冲突、Prettier 和受保护的旧累积 checker 阻塞，本次状态为
  `Aspect 8 已执行但未完成（Blocked）`，不标记 Iteration 5 完成，不开始其他 Aspect。

## 残留治理复验（2026-08-31）

本节是对上方历史记录的最新复验补充，不改写此前的失败证据、历史 fixture 或 parent hash。

### 基线与保护

- branch=`main`；HEAD 与 `origin/main` 均为
  `8812be4fa73ab6274ec642fd5099be060aafb5d6`；ahead/behind=`0/0`；staged=`0`。
- 当前 tracked dirty、ordinary untracked、ignored 内容继续全部视为用户资产；真实 `.env`、上传项目、用户
  MySQL/Redis/观测数据、普通 Compose volume、已有容器/镜像和用户文件未读取、未哈希、未输出大小。
- Aspect 1–7 fixture、历史 evidence、SQL、prompt 和原有 migration 内容未被改写；新增证据只使用人工审查的
  Aspect 8 cumulative overlay，`auto_accept_current_values=false`，`removed_paths=[]`。
- 目标 Ruff scope 的两个纯 import/formatter 文件先备份到仓库外；没有 stage、commit、fetch、pull 或 push。

### 最新离线证据

| Gate | 结果 | 证据 |
| --- | --- | --- |
| targeted Ruff active scope | Passed | 已登记的 22 个 Python 文件 `ruff check` 与 `ruff format --check` 均通过；没有执行 broad `--fix` |
| style/version/container/closeout checker | Passed | 当前人工审查 hash overlay、baseline parent、migration records 和保护边界均通过 |
| full pytest | Passed | 外部 basetemp：`D:\\codex\\EzllmTest_v2_residual_pytest_tmp_20260831_final`；`727 passed, 32 skipped` |
| Agent Eval | Passed | 外部质量报告：`D:\\codex\\EzllmTest_v2_residual_quality_20260831\\eval.json`；`104/104` |
| Agent Acceptance | Passed | 同一 immutable historical dataset，18/18；dataset SHA-256 为 `44D8CAD27AA17365A6AA85300A2A7261275438AE162D3DA316371B0EFF4E1674` |
| Agent Benchmark | Passed | 两次同条件隔离运行均通过；legacy p95 ratio 约 `1.035`、`1.070`，OTel ratio 约 `1.025`、`1.033`；warm-cache gate 通过 |
| modular topology | Passed | `D:\\codex\\EzllmTest_v2_residual_dual_mode_modular2_20260831`；task-owned MySQL/Redis 依赖和 runner 子进程均按精确归属清理 |
| frontend source gates | Passed | source-only ESLint、`vue-tsc`、仓库外 Vite build、bundle checker 和外部锁定 Prettier check 通过 |
| repository `npm run format:check` | Blocked | 现有 ignored `node_modules` 没有 Prettier binary；未安装、未覆盖或修改用户依赖目录 |
| Compose/static gates | Passed | base、overlay、observability profile `config --quiet`、credential scan、`git diff --check` 通过；后者仅保留既有 CRLF/LF warning |
| Docker full-stack topology | Blocked | 固定端口 `9090`、`3000` 仍被既有对象占用；`8080/8130/8131/23306/26379` 当前空闲；未改端口、未停止对象、未启动或清理用户资源 |
| topology parity | Blocked | Docker topology 未能安全启动，因此不能宣称双模式网络业务 parity 或 18/18 parity |

Acceptance 报告中的安全/费用计数均保持为零：approval bypass、budget overrun、duplicate side effect、project
isolation violation、unsafe capability、sensitive leak、用户 MySQL 写入、用户项目读取、真实 provider/embedding
调用、currency cost，以及 warm-cache model/embedding 调用均为 `0`。模块化 readiness/HTTP 探针与 deterministic
business acceptance 分开记录，没有把局部探针称为真实网络 Agent workflow E2E。

### 规范范围说明

曾执行的 `ruff check ez_back_dev scripts` 与 `ruff format --check ez_back_dev scripts` 是超出 Aspect 3
登记 scope 的仓库级诊断，命中了 legacy、历史测试和既有脚本中的大量 import/format 漂移；没有用 broad formatter、
扩大 ignore 或自动接受当前值处理。已登记的 22 文件 active scope 已通过，未证明安全的 legacy/历史批次继续保留。

### 当前结论与恢复条件

当前状态仍为 `Aspect 8 已执行但未完成（Blocked）`。要继续而不破坏用户对象，必须由外部状态先释放固定的
`9090` 和 `3000` 监听，并保持现有版本、端口和拓扑不变；随后在同一 task-owned project、`--pull never` 和
synthetic env 下重新执行完整 10-service Docker 验收，再比较 modular 与 Docker 的同一 18-case 报告。若端口、
镜像、依赖或用户修改再次使证据不可证明，必须保留现场并继续报告 Blocked。此前创建的 task-owned Redis、
MySQL/Redis 依赖、runner 进程和临时应用资源均已精确清理；没有执行 prune、广泛 volume 删除、数据库 dump、
Redis dump、provider/embedding 调用或真实数据读取。

## 源码预发布准备复验（2026-09-02）

本节记录 `v0.1.0-preview.1` 源码预发布的实际准备结果。它不改写此前的
Aspect 1–8 证据、历史 fixture、SQL、prompt 或 Blocked 结论。

### GitHub 与 allowlist

- branch=`main`；HEAD 与 `origin/main` 仍为
  `8812be4fa73ab6274ec642fd5099be060aafb5d6`；ahead/behind=`0/0`。
- GitHub CLI 授权、仓库归属和默认分支只读核对通过；目标远程分支
  `codex/iteration5-source-preview`、tag `v0.1.0-preview.1` 和对应 Release
  均未发现。
- 仓库外 task-owned allowlist 共 711 条唯一、精确路径；9 条仓库外的历史隔离资产被排除。
  没有把 `.env`、上传项目、普通 volume、用户目录、node_modules、dist、cache、日志或 Docker
  registry 产物纳入 allowlist。迁移 fixture 中缺失的旧路径继续按历史迁移/删除证据处理，不作为新文件创建依据。
- 新增源码预发布说明，并仅窄范围更新根 README 与 Iteration 5 README；截至本节记录时尚未
  stage、commit、fetch、pull、push、tag、Release 或执行 Docker 操作。

### 本次复验门禁

| Gate | 结果 | 事实 |
| --- | --- | --- |
| version contract | Passed | 版本、镜像身份、lock 与质量工具字段检查通过 |
| style contract | Passed | 当前人工审查的 style contract 与 cumulative overlay 检查通过 |
| frontend structure | Passed | 无 unresolved active frontend structure reference |
| backend boundary / modular runtime / container / closeout checkers | Passed | Aspect 8 active overlay、baseline parent 与 migration review-record 已人工复核并同步；历史 fixture 未改写 |
| frontend source ESLint | Passed | source-only `eslint src --no-fix` 通过 |
| frontend type-check | Passed | `vue-tsc` 通过 |
| full pytest | Passed | 外部 task-owned Python 3.11 环境与显式 basetemp：`727 passed, 32 skipped` |
| Agent Eval / Acceptance / Benchmark | Passed (existing reviewed evidence) | task-owned 外部证据：Eval `104/104`、Acceptance `18/18`、Benchmark 两次隔离运行均通过；Acceptance dataset SHA-256 为 `44D8CAD27AA17365A6AA85300A2A7261275438AE162D3DA316371B0EFF4E1674` |
| current Eval / Acceptance / Benchmark rerun | Blocked / not repeated | 当前没有可证明归属的 task-owned Redis；未探测未知 Redis、未安装依赖、未访问用户 Redis |
| credential scan | Passed (existing reviewed evidence) | 使用既有外部扫描证据；本次不对包含普通 untracked 用户资产的工作区做全仓库读取扫描 |
| `git diff --check` | Passed | 无 whitespace error |
| Docker full-stack / dual-topology parity | Blocked | Docker Engine/Desktop 不可用；不重启、不改端口、不停止既有对象、不 build/up/down/pull |

已有 Benchmark 证据的两次 legacy p95 ratio 分别约为 `1.035`、`1.070`，OTel p95 ratio
分别约为 `1.025`、`1.033`，warm exact cache 门禁通过；真实 provider、embedding、MySQL
调用和费用计数保持为 `0`。模块化 readiness/HTTP 探针与 deterministic business acceptance
分开记录，没有把局部探针称为真实网络 Agent workflow E2E。

### 当前发布判断

仓库内可修复的 Aspect 8 active evidence 漂移已完成窄范围修复，且隔离 Python 3.11
完整 pytest 与所有静态 checker 已通过。源码预发布仍保留 Docker full-stack 与双拓扑 parity
为 `Blocked`；当前 Eval/Acceptance/Benchmark 复跑因缺少 task-owned Redis 未重复执行，发布
材料只引用已审查的 task-owned 外部证据，不把未运行的复跑写成新结果。

产品版本仍为 `0.1.0`，预期 GitHub 标签仍为 `v0.1.0-preview.1`。Docker 镜像不发布，
`removed_paths=[]`；没有读取真实 `.env`、上传项目、用户数据库、Redis、观测数据、普通
volume、provider 或 embedding，也没有产生付费调用。后续只允许在显式 allowlist 上创建源码
预发布分支和 Draft PR；不自动合并、不直接推送 `main`，不创建 Docker 镜像 release asset。

## Draft PR 首轮 CI 复验（2026-09-02）

- 源码预发布分支 `codex/iteration5-source-preview` 的首个提交为
  `351ed3ae58ae5a16322b82b984063ef7bb3cf749`，Draft PR 为
  `Jaily16/EzllmTest#1`。
- GitHub Actions run `33623365652` 在 clean Linux checkout 的
  `Check modular runtime contract` 失败；后续门禁按 workflow 依赖被正确停止，未执行
  Docker full-stack smoke。
- 失败原因已确认是历史 baseline 使用 Windows raw hash，而 clean checkout 使用 LF：
  `ezllmtest.sql` 的受保护内容 hash 与 canonical LF hash 不同，前端 Dockerfile 的人工
  overlay 也同时记录了 raw 与 normalized 两种 hash。没有发现业务、公共契约、依赖或敏感值漂移。
- 修复仅限 Aspect 8 active evidence：checker 对人工记录的 raw/normalized hash 做严格双重
 匹配，overlay 增加 SQL canonical LF hash；不修改 SQL 内容，不更新历史 Aspect 1–7 fixture，
  不放宽路径、敏感目录或自动接受规则。
- 修复后的 checker、contract、baseline、migration 和本日志会作为下一提交重新触发 CI；
  在新 run 通过前不宣称 CI 通过、不创建 tag/Release。Docker full-stack/parity 仍为
  `Blocked`，不重启、不 build/up/down/pull，不发布镜像。

## Draft PR CI 复验收口（2026-09-02）

本节只追加源码预发布分支上的真实复验结果，不改写历史 evidence、Aspect 1–7 fixture、SQL、prompt 或
用户资产。

| Commit / run | 结果 | 处理或限制 |
| --- | --- | --- |
| `991d801` / `33626681465` | Backend tests 失败 | clean checkout 的受保护目录元数据断言与 Windows/LF `.env.example` 尺寸断言失败；无业务回归 |
| `9149829` / `33626977160` | Closeout checker 失败 | active baseline contract test 的人工 overlay hash 未同步 |
| `526dc7c` / `33627239455` | Backend tests 失败 | `TestProject.py` 历史混合换行尺寸未覆盖；其余 758 个测试通过 |
| `8c04759` / `33627691876` | 非 Docker gates 通过；Docker smoke 失败 | 后端测试、Eval、Acceptance、Benchmark、前端质量门禁、静态 checker、Compose config 和凭据门禁均通过；Compose 构建完成且容器健康，但既有 Tempo trace 查询与容器内 Acceptance 探针未通过，故 Docker full-stack/parity 继续 `Blocked` |

最终本地隔离 Python 3.11 全量结果为 `727 passed, 32 skipped`；7 个只读 checker 均通过。此次修复仅更新
clean-checkout 测试兼容性和人工审查 evidence hash 链，不修改产品逻辑、公共 wire contract、版本真源或历史
fixture。未执行 Docker 镜像发布、registry 登录/推送、tag 或 GitHub Release；产品版本仍为 `0.1.0`，预发布仍
只能标记为 `Source Preview`，Iteration 5 仍为 `Aspect 8 已执行但未完成（Blocked）`。

没有读取真实 `.env`、上传项目、用户 MySQL/Redis/观测数据、普通 volume 或用户文件；没有产生 provider、
embedding 或付费调用。用户未跟踪文件 `docs/development/iteration-5/iteration-5-residual-remediation-prompt.md`
继续保留为用户资产，不进入提交。
