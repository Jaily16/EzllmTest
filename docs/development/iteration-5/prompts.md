# EzllmTest Iteration 5 新对话提示词

> **状态：待启动。** 按顺序使用以下两条提示词。第一条只允许只读接手；确认接手报告后，再发送第二条，只规划 Aspect 1。不得把两条提示词合并成一次实施请求。

Iteration 5 的固定节奏为：

```text
只读核验 → 单 Aspect 计划 → 用户确认 → 单 Aspect 实施 → 完整门禁 → 停止等待
```

## 第一条提示词：Iteration 5 只读接手

```text
你现在只读接手 Windows 本地项目 D:\codex\EzllmTest_v2。Iteration 1–4 已完成；Iteration 4 已交付 Python/FastAPI + LangGraph 单 Agent、22 个类型化工具、Redis 持久执行、Agent 工作台、loopback MCP、RAG/Eval/OpenTelemetry、Vite、Docker Compose 和 GitHub Actions，并完成离线门禁与隔离真实模型合成 E2E。Iteration 5 尚未开始实施，目标是进行工程治理：安全清理本地与源码遗留、统一依赖和版本说明、规范代码风格与中文注释、按长期产品职责整理目录和重复实现，并最终保留 Docker 完整部署与前后端/数据库分步骤模块化部署两种运行方式。不要开始清理、重构或安装依赖。

当前必须保护：19 个 workflow、22 个工具、legacy/Agent REST 与 SSE、MCP schema；revision-aware artifact/cache/RAG；Token/上下文预算；stale、取消、延迟保存、失败回滚和 regeneration lock；所有 preliminary analysis 持久化；五类 session-only 与三类 persisted final；LangGraph HITL、严格 JSON checkpoint、租约/幂等/恢复；MySQL/Redis 数据职责；页面加载零隐式付费调用；approval bypass、重复副作用和跨项目泄漏为零。

完整阅读：

1. README.md；
2. docs/iteration-4-overview.md、docs/iteration-4-closeout.md、docs/iteration-4-live-model-acceptance.md，以及 Iteration 4 development log 的最终收口部分；
3. docs/iteration-5-overview.md 和 docs/iteration-5-prompts.md；
4. requirements、package.json/package-lock、Python/Node/Dockerfile、compose.yaml、GitHub Actions、Vite/ESLint/TypeScript 配置、.gitignore 与所有 .env.example；只读取变量名和占位符，绝不读取真实 .env；
5. backend 的 app/config/routes、workflow catalog、Agent runtime/checkpoint/coordinator/tool/context/RAG/Eval/telemetry、DAO、SQL 与启动入口；
6. frontend 的 router/state/composables/components/views/styles/assets 与 Agent 工作台；
7. tests、fixtures、scripts、ops 和 docs 目录结构，重点识别 iteration/aspect 命名、重复资产、旧模板、legacy/compatibility 层、平面 service 目录和多处版本说明。

先执行只读 Git 预检：branch、status、diff --stat、diff --name-status、HEAD 与本地 origin/main 对比。记录 dirty、untracked 和 ignored 项的路径与分类；只对普通源码或明确可再生文件记录大小和必要哈希。对真实 `.env`、上传项目、数据库/Redis/观测数据和其他用户文件只记录“存在且受保护”，不得读取、计算内容哈希或输出大小。当前工作区的任何既有内容都视为用户资产。

本回合不得 fetch、pull、stage、commit、push；不得删除、移动、重命名或格式化任何文件；不得运行测试、build、服务、Docker、数据库、provider、embedding 或安装命令；不得读取真实 .env、真实项目、MySQL/Redis 数据或 Docker volume。可以只读查看公开官方文档，核对 Python/Node/框架/容器工具的当前支持状态。

请输出 Iteration 5 只读接手报告，所有结论使用以下标签：

- Verified：当前产品架构、代码/测试/文档/交付结构、版本来源和现有门禁；
- Protected：用户数据、历史证据、公共契约和不可静默改变的行为；
- Candidate：可再生垃圾、重复资产/实现、过期注释、迭代式命名、旧模板、兼容层和目录重组候选；每项说明为什么只是候选而非可直接删除；
- Approved：Iteration 5 八个 Aspect 的目标和依赖顺序；
- Proposed：版本单一真源、中文注释尺度、后端/前端目标边界与两种部署拓扑；
- Missing：引用图、删除证据、版本兼容 spike、格式门禁、迁移映射和双模式验收中的缺口。

报告至少回答：

1. 哪些 ignored/untracked 内容属于明确可再生垃圾，哪些可能是用户数据；
2. 哪些 tracked 文件或命名看似遗留，但必须先通过 import、路由、动态加载、测试、文档链接、Docker/CI 和运行时引用证明；
3. 当前版本信息分布在哪些 executable manifest 和手写文档中，如何避免建立第二份冲突真源；
4. 现有后端平面 service、前端组件/资产、测试 fixture 和迭代文档的结构性问题；
5. Docker 完整栈与分模块运行当前各自具备什么、还缺什么；
6. Aspect 1 的文件范围、风险、依赖与后续 Aspect 顺序是否和当前代码冲突。

完成只读接手报告后立即停止，等待我的第二条提示词。不要给出实现 diff，也不要开始计划 Aspect 2–8。
```

## 第二条提示词：只规划 Aspect 1

```text
基于刚才的只读接手报告，进入计划模式，只为 Iteration 5 Aspect 1“基线盘点、资产分类与安全清理边界”制定详细实施计划。不要规划或实施 Aspect 2–8，不要删除或修改任何文件，先把计划交给我确认。

计划必须：

- 重新核对 branch、HEAD、origin/main 和完整 dirty worktree；所有既有内容均视为用户资产；
- 明确 Aspect 1 的文件范围、非目标、依赖、测试先行顺序、验证门禁和可回滚边界；
- 在任何清理前冻结 19 workflow、22 tools、legacy/Agent REST/SSE/MCP、artifact/revision/RAG/cache/retention、审批/预算/恢复和两种当前启动方式；
- 记录 requirements、package manifests/lock、Dockerfile、compose、GitHub Actions、SQL、公共入口与关键契约文件的规范化 SHA-256；
- 设计 tracked、untracked、ignored、外部数据库、Docker container/image/volume 和系统临时目录的分层资产清单；
- 对每个对象使用 Protected user data、Protected product asset、Historical evidence、Generated disposable、Duplicate candidate、Legacy candidate 或 Unknown 分类，并记录来源、大小、引用证据、拟议动作和恢复方法；
- 绝不读取真实 .env 内容；不得扫描或输出 API Key/密码值；不得读取上传项目、用户 MySQL/Redis、普通 Compose 命名卷或真实项目文档；
- 把 __pycache__、pyc、pytest/cache、coverage、dist、日志、临时 benchmark/trace/screenshot 等作为候选 allowlist，而不是使用模糊 glob 直接递归删除；
- 所有删除设计必须支持 dry-run，解析并验证绝对路径位于批准根目录；Windows 上不得跨 shell 拼接删除目标，不得使用 reset --hard、checkout --、clean -fdx 或针对仓库根的递归删除；
- 对 HelloWorld、FounctionalTest、重复 logo/测试图片、legacy 模块、iteration/aspect 测试与 fixture、旧注释和重复版本文字建立引用审计方法；仅文件名、mtime、ignored 状态或“看起来旧”不能作为删除证据；
- 引用审计必须覆盖 Python import/动态 import、Vue router/懒加载、模板与 CSS 资源、测试收集、fixture、文档链接、Docker COPY/config、Compose、GitHub Actions、脚本和公共 CLI 入口；
- 规划一个版本表面清单，枚举 Python/npm/Docker/Actions/README/注释中的版本，但 Aspect 1 不升级依赖、不选择新包管理器、不改 manifest；
- 规划当前仓库架构图、目录职责和迁移约束，为 Aspect 4–5 提供证据，但 Aspect 1 不移动生产代码或历史文档；
- 测试先行设计静态保护契约、清理分类器、dry-run、安全路径、敏感目录拒绝、历史 evidence hash、生成物扫描和幂等清理测试；
- 明确拟新增的 Iteration 5 inventory/baseline fixture、契约文档和 docs/iteration-5-development-log.md，禁止提供“自动接受当前值”的无审查更新命令；
- 计划聚焦测试、完整 pytest、Agent Eval/Acceptance/Benchmark、前端 lint/type-check/build、Compose config、credential scan、git diff --check、链接/hash 和最终生成物检查；
- 默认使用离线 deterministic fixture；不访问真实 provider、embedding、MySQL、远程 Redis、真实项目或外网，不产生费用；
- 若发现未知内容、路径越界、用户修改、数据库/卷或无法证明无引用的候选，必须保留并报告，不能为了达到清理数量而删除；
- 计划确认后也只能实施 Aspect 1；完成时更新 docs/iteration-5-development-log.md，然后停止等待 Aspect 2；
- 不 stage、commit、fetch、pull 或 push，除非我另行明确授权。

计划需给出关键清理决策、精确文件/目录范围、dry-run 输出结构、保护规则、回滚方式和完成条件。等待我确认，不要直接编辑、清理或运行任何命令。
```
