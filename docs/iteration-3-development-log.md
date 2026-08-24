# Iteration 3 Development Log

## 2026-08-23 — Aspect 1：体验基线与设计系统基础

### 范围与边界

本次只实施全局设计基础、可复现体验基线和 `WorkflowStepper` pilot，没有开始 Aspect 2–8。未修改 router、state、composables、登录/创建/主框架/计划/菜单/八类测试页、LLM 面板、后端业务代码、SQL、workflow catalog、prompt 或预算。

没有安装依赖，没有修改 `package.json`/`package-lock.json`，没有 fetch/pull/stage/commit/push，没有访问外网、真实模型、embedding、MySQL 或真实项目数据，也没有打开或输出真实 `.env` 内容。

### 用户资产冻结

开始时：

- branch：`main`
- HEAD 与本地 `origin/main`：`5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`
- 既有 dirty：`README.md` 已修改；`docs/iteration-3-overview.md`、`docs/iteration-3-prompts.md` 未跟踪
- `ez_front_dev/node_modules` 与 `ez_front_dev/dist` 均存在，视为用户资产
- 8080、8130、18080、18130 均未监听

开始与结束哈希一致：

| 用户资产 | SHA-256 |
|---|---|
| `README.md` | `F2674360780908648E2EEF59DA6CCD8B6D236A7A4517D23C2E17BF58F186FE9D` |
| `docs/iteration-3-overview.md` | `C1E4B564F8C4DBF47AF2E6E0C2BE00FF04AB56416F74A2C892FD0B94902EB26E` |
| `docs/iteration-3-prompts.md` | `5997679D41832734E22648D52AE6667FC53C31C744F1A3E7C3060755D4A04201` |
| `ez_front_dev/package.json` | `769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3` |
| `ez_front_dev/package-lock.json` | `C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA` |

### 实施文件

创建：

- `ez_front_dev/src/styles/tokens.css`
- `ez_front_dev/src/styles/element-plus-theme.css`
- `ez_front_dev/src/styles/base.css`
- `scripts/frontend_fixture_server.py`
- `ez_back_dev/tests/test_frontend_experience_foundation.py`
- `docs/iteration-3-experience-baseline.md`
- `docs/iteration-3-design-system.md`
- `docs/iteration-3-development-log.md`

修改：

- `ez_front_dev/src/main.ts`
- `ez_front_dev/src/App.vue`
- `ez_front_dev/public/index.html`
- `ez_front_dev/src/components/WorkflowStepper.vue`

### 红绿测试过程

1. 首次 foundation 契约：`8 failed, 1 passed`。失败都对应尚未存在的样式/夹具/文档、旧 HTML 和 Stepper 缺少 ARIA。
2. 加入离线夹具后：`7 failed, 2 passed`，证明夹具安全与确定性契约转绿。
3. 实施样式和 Stepper 后、文档前：`1 failed, 8 passed`，仅缺文档。
4. 文档完成后：`9 passed`。
5. 项目 Python 3.11 环境下 foundation + 既有 frontend contracts：`36 passed in 1.38s`。
6. 完整离线后端门禁：`298 passed in 10.10s`。

曾误用默认 Python 3.12，收集阶段提示缺少 FastAPI/LangChain 等项目依赖；随后定位并改用既有 `D:\tool\anaconda3\envs\ezllmtest\python.exe`（Python 3.11.15）重跑成功。没有安装或更改任何依赖。

所有 pytest 运行均设置禁用环境文件自动加载、禁止 bytecode、内存 SQLite 与空 provider keys，并使用 `-p no:cacheprovider`；没有访问数据库或 provider。

### 浏览器验收

仅启动本任务的：

- 前端：`127.0.0.1:18080`
- 标准库离线 REST/SSE 夹具：`127.0.0.1:18130`

夹具使用三组固定 PID，覆盖 `analysis_required`、全测试类型可进入和 stale。浏览器验证包括登录、缓存计划、ready/stale 菜单、单元测试 stale、UI 测试 ready/completed、LLM running、取消、结构化失败、Token、saved 与未保存反馈。

`WorkflowStepper` 五视口最终 `clientWidth/scrollWidth`：

- 360：`25/25`
- 768：`433/433`
- 1024：`689/689`
- 1440：`1105/1105`
- 1920：`1600/1600`

运行态确认 `data-state="running"` 与 `aria-current="step"`；取消和结构化失败均转为 `failed`，下游保持 `locked`。stale 三步页面显示 completed/stale/stale，状态不只依赖颜色。

浏览器控制台：零 error。保留既有 Vue `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__` feature-flag warning，没有新增 warning。截图清单与每个视口结论见 `docs/iteration-3-experience-baseline.md`；二进制截图只在任务临时产物中，不进入 Git。

结束时已恢复浏览器默认视口、关闭临时页面、停止 18080/18130 服务，并确认两个端口均未监听。

### 构建与安全门禁

- `npm run lint`：通过，`No lint errors found`。
- `npm run build -- --dest <系统临时唯一目录>`：成功。
- 构建输出 63 个临时文件；验证目标位于系统临时目录且名称有 `ezllmtest-aspect1-` 前缀后已删除。
- 现有 `ez_front_dev/dist` 未被覆盖或清理。
- build 保留既有 2 类 warning：asset size limit、entrypoint size limit；另记录当前 Node 的 `fs.Stats` deprecation warning。
- `python scripts/scan_credentials.py`：最终通过，`Credential scan clean: tracked=167, staged=0, untracked=10`。
- `git diff --check`：通过。
- 真实 `.env`、`node_modules`、`dist`、任务截图和测试缓存均未进入 Git。

### 兼容性证明

- 19 个 workflow 和公共路由文件未修改。
- REST/SSE endpoint、请求/响应字段、模型标签、缓存、artifact、延迟保存、取消、stale、失败回滚和 regeneration lock 文件未修改。
- `WorkflowStepper` props、步骤顺序、六种状态名称和所有调用方保持不变。
- 五类 session-only case 与三类持久化 case 的语义未改变。
- Element Plus 仅通过 `:root` CSS variables 桥接，没有组件级 `.el-*` 覆盖。

### 已知限制与后续边界

- 360px 下 280px 固定侧栏让 main 只剩约 65px、Stepper 只剩 25px。pilot 已消除自身溢出并完整换行，但页面仍不可实用；只能由 Aspect 2 修复应用壳。
- 768px 下非 pilot main 内容仍有约 11px 内部溢出；不属于 Aspect 1。
- 登录大面积浅绿渐变、页面内联样式、500/620/800px 固定宽度、长文本层级和 LLM 面板重构均未提前处理。
- 当前未新增 Vitest、Vue Test Utils、Playwright 或 axe；继续使用 pytest 契约与真实浏览器人工/截图验证。

Aspect 1 到此停止；等待 Aspect 2 或其他明确指令。

## 2026-08-23 — Aspect 2：信息架构与响应式应用壳

### 范围与边界

本次只重构持久化工作区壳层，没有开始 Aspect 3–8。十条 workflow 路由、router metadata/guard、`projectAnalysis` 状态来源、登录/创建、测试计划、测试菜单、八类测试页、LLM 面板、后端、SQL、REST/SSE 与 19 个 workflow 均未修改。

没有安装依赖，没有修改 `package.json`/`package-lock.json`，没有 fetch/pull/stage/commit/push，没有读取真实 `.env`，也没有访问外网、真实模型、embedding、MySQL 或真实项目数据。

### 用户资产冻结

开始时：

- branch：`main`
- HEAD 与本地 `origin/main`：`5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`
- 8080、8130、18080、18130 均未监听
- Aspect 1 的全部 tracked/untracked 成果与既有 `README.md`、两份用户 Iteration 3 文档均记录 SHA-256，并作为用户资产保护

结束核对中，所有未列入 Aspect 2 修改范围的 dirty 文件哈希与开始值一致，包括 `README.md`、Aspect 1 基线、overview/prompts、foundation 测试、HTML/App/Stepper/main.ts、base/Element bridge。依赖清单仍为：

| 用户资产 | SHA-256 |
|---|---|
| `ez_front_dev/package.json` | `769EC529E786375A8DCDB5FCE27C1A4A44D5DDEDC3B9946E2850DEA8477BD5C3` |
| `ez_front_dev/package-lock.json` | `C93CDE311DB8675A62A781E20F613DD291D049743CF30A684EE3B94EA074DEAA` |

### 实施文件

创建：

- `ez_back_dev/tests/test_frontend_application_shell.py`
- `docs/iteration-3-application-shell.md`

修改：

- `ez_front_dev/src/views/MainView.vue`
- `ez_front_dev/src/styles/tokens.css`
- `scripts/frontend_fixture_server.py`
- `docs/iteration-3-design-system.md`
- `docs/iteration-3-development-log.md`

`MainView` 现在只有一份导航 DOM，包含 skip-link、64px sticky header、语义 aside/nav/main、项目摘要和本地路由标题映射。`<1024px` 使用最大 320px 的覆盖式抽屉，`>=1024px` 使用 272px 固定侧栏，内容最大 1200px 并居中。

导航新增内部 `loading` 表达：workflow status 返回前显示“加载中”，不会误报“已锁定”。current/completed/available/locked/stale/regenerating 的业务判定顺序继续保护 Iteration 2；八类测试路由已有结果时仍显示“可进入”。

移动抽屉增加 inert/aria-hidden、body scroll lock、初始焦点、Tab/Shift+Tab 循环、Escape/遮罩/关闭按钮恢复焦点、路由切换聚焦 main 和 1024px resize 清理。键盘契约实现过程中，真实浏览器发现 Element Plus menuitem 使用 roving tabindex；焦点循环因此显式纳入未禁用的 `role="menuitem"`，避免抽屉只剩关闭按钮可访问。

离线夹具新增 `--status-delay-ms`，范围 0–10000ms，只延迟 workflow status GET。server 仍为 Python 标准库、只绑定 `127.0.0.1`，不导入生产应用或环境配置。

### 红绿测试过程

1. 新应用壳契约首次运行：`6 failed`，对应旧 Element Plus 壳、缺少 loading/移动抽屉、shell tokens、状态延迟夹具和 Aspect 2 文档。
2. 实施壳层后：`3 failed, 3 passed`。其中两项是新测试自身把 `<el-menu-item>` 前缀误计为多个菜单、以及对合法多行调用做了过窄字符串匹配；修正为精确正则/语义片段后，剩余失败仅为待发布文档。
3. 文档前聚焦实现契约：`5 passed, 1 deselected`；Aspect 1 foundation + 既有 frontend contracts：`36 passed`。
4. 文档发布后应用壳契约：`6 passed`。
5. foundation + application shell + 既有 frontend contracts：`42 passed in 1.13s`。
6. 完整离线后端门禁：`304 passed in 10.19s`。

所有 pytest 都使用项目 Python 3.11，设置禁用环境文件自动加载、禁止 bytecode、内存 SQLite 与空 provider keys，并使用 `-p no:cacheprovider`。

### 浏览器验收

仅启动本任务的 `127.0.0.1:18080` 前端和 `127.0.0.1:18130 --status-delay-ms 1200` 离线夹具。使用三组固定 PID 覆盖 analysis required、ready 与 stale。

- 360×800：根宽 `360/360`；抽屉 312px；打开后焦点进入关闭按钮并锁定 body；Shift+Tab 到最后一个可进入菜单项；Escape 恢复导航按钮；隐藏 aside 为 inert。
- 768×1024：根宽 `768/768`；抽屉 320px；选择测试菜单后抽屉关闭、body 解锁、main 获得焦点。
- 1024×768：固定侧栏精确 272px；移动按钮隐藏；main 从 x=272 开始；根宽 `1009/1009`（15px 浏览器滚动条）。
- 1440×900：根宽 `1440/1440`；regeneration 期间 header 显示“测试计划重新生成中”，菜单与八类测试路由均为“分析中”且禁用。
- 1920×1080：根宽 `1905/1905`；内容宽度 1200px 并居中；单元/UI 为 stale，其余测试路由保持 available。

截图：`shell-mobile-loading-closed-360.png`、`shell-mobile-locked-open-360.png`、`shell-tablet-ready-open-768.png`、`shell-desktop-ready-1024.png`、`shell-desktop-regenerating-1440.png`、`shell-desktop-stale-1920.png`。二进制只保存在任务临时可视化目录，不进入 Git。

控制台零 error；仅保留 Aspect 1 已记录的 Vue `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__` feature-flag warning，没有新增 warning。结束时已重置浏览器视口、关闭临时页面并停止 18080/18130，两个端口均未监听。

### 构建与安全门禁

- `npm run lint`：通过，`No lint errors found`。
- `npm run build -- --dest <系统临时唯一 Aspect 2 目录>`：成功，63 个临时文件；校验目标仍位于系统临时目录且具有 `ezllmtest-aspect2-` 前缀后已安全删除。
- 现有 `ez_front_dev/dist` 未被覆盖或清理。
- build 保留既有 2 类 warning：asset size limit、entrypoint size limit；另保留当前 Node 的 `fs.Stats` deprecation warning。
- `python scripts/scan_credentials.py`：通过；`git diff --check`：通过。
- 真实 `.env`、`node_modules`、`dist`、截图、pytest 缓存与临时 build 均未进入 Git。

### 兼容性证明与遗留

- router、state、composables 与后端业务文件未出现在 Aspect 2 变更中。
- 十个显式 `:disabled="!isWorkflowRouteAllowed(...)"`、公共路径、测试页 available 先于 completed、regeneration lock 与初始化读取契约均由测试固定。
- 19 个 workflow、REST/SSE 字段、缓存、artifact、持久化/session-only、延迟保存、取消、stale 与失败回滚语义无变化。
- 360px 登录页旧固定宽度、页面内联样式、测试计划/菜单/八类测试页的局部布局与 LLM 面板仍属于 Aspect 3–8；本次只保证壳层不产生页面级横向滚动。

Aspect 2 到此停止；等待 Aspect 3 或其他明确指令。

## 2026-08-23 — Aspect 3：共享交互与反馈组件

### 范围与用户资产

本次只建立共享页面原语、统一 LLM 执行反馈层、结果替换确认 helper，并在 `UITest.vue` 进行单页 pilot。TestPlan/TestMenu、其余七类测试页布局、Login/Create、MainView、router/state、后端生产代码、SQL 和 Aspect 4–8 均未迁移。

开始时 branch 为 `main`，HEAD 与本地 `origin/main` 均为 `5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`。全部既有 dirty tracked/untracked 文件和依赖清单均记录 SHA-256，并作为用户资产保护。没有 fetch/pull/stage/commit/push，没有安装依赖，没有读取真实 `.env`，也没有访问真实模型、embedding、MySQL、外网或真实项目数据。

### 实施内容

新增六个 `src/components/workspace/` 组件：`WorkspacePageHeader`、`WorkspaceSection`、`ModelSelector`、`WorkflowActionBar`、`FeedbackState` 和 `ResultContainer`。它们只负责布局、语义和状态表达，不拥有路由、生成、保存或重试行为。tokens 新增 40px 控件高度与 72ch 阅读宽度，不添加全局 Element Plus 组件覆盖。

`LlmExecutionPanel` 保留原 props/cancel emit，将状态、模型、progress、缓存/保留边界、默认折叠 reasoning、Token 和终态反馈整理为固定层级。`useLlmStream` 只读取生产 SSE 已有的 `meta.persistence`；endpoint、事件名称、解析、取消控制器与完成时序未改变。artifact 显示“已保存”，五类 session-only case 显示“仅当前页面保留”，取消/失败显示“本次未保存”，partial output 在失败和取消后继续可见。

`UITest.vue` 保留 `ui_info`/`ui_case`、payload、恢复、stale、`keepPreviousOnFailure`、取消和 reset 逻辑，并采用全部共享页面组件。hydration loading 明确“不自动发起模型请求”，失败使用 alert 反馈但不自动重试。其余七类测试页没有采用新页面布局。

结果替换确认从 `useTestWorkflow` 抽到 `src/ui/confirmations.ts`，正文、标题、“重新生成/保留原结果”按钮和布尔返回行为保持不变。离线夹具补充 artifact/session persistence、五类 session-only 无 artifact/缓存/保存行为和单元测试三步的合成结果；新增受限 `--origin-port` 仅用于本机端口被占用时的离线浏览器验收，仍只允许 `127.0.0.1` origin。

### 红绿测试与构建

1. 新 shared interactions 契约首次运行：`8 failed`，对应共享组件、tokens、persistence、反馈层级、确认 helper、pilot、fixture 与文档尚不存在。
2. 主要实现后、文档前：`2 failed, 6 passed`；失败仅为 pilot 测试自身引号匹配和待发布文档。修正测试语义并发布文档后：`8 passed`。
3. 为 session-only 浏览器流程新增结构化离线结果契约，先得到 `1 failed, 7 passed`，补齐 fixture 后转绿；loopback origin 端口契约同样先红后绿。
4. foundation + application shell + shared interactions + 原 frontend contracts：`50 passed in 1.24s`。
5. 完整离线后端门禁：`312 passed in 8.85s`。
6. `npm run lint`：通过，`No lint errors found`。
7. `npm run build -- --dest <系统临时唯一 Aspect 3 目录>`：成功，63 个临时文件；验证目标路径后已删除，现有 `dist` 未覆盖。

浏览器和 fixture 端口回退验证完成后，最终门禁再次得到 `312 passed in 10.20s`、lint 零错误、凭证扫描 clean 和 `git diff --check` 通过。

首次组合契约误用了默认 Python 3.12，因环境缺少项目依赖在收集阶段停止；随后使用既有 Python 3.11 环境重跑通过，没有安装或更改依赖。build 只保留既有 asset size、entrypoint size 和 Node `fs.Stats` deprecation warning。

### 浏览器验收

主要 UI pilot 使用既有 `127.0.0.1:18080/18130` 离线服务。因为这两个端口在本 Aspect 启动前已由既有进程占用且不得停止，更新后 fixture 的 session/hydration 验收使用本任务专用 `18082/18131`；CORS origin 仍限定为 loopback。本任务启动的 18081/18082/18131 进程最终全部停止，既有 18080/18130 进程未触碰。

- 360×800：document/main 为 `360/360`；模型选择为 `294/294`，主按钮 294px，全宽单列，reasoning 默认不展开。
- 768×1024：document 为 `768/768`；hydration loading 为 `role=status`、`aria-busy=true`，明确不会自动生成；断开本任务 fixture 后，hydration error 为 `role=alert` 且工作区仍可见。
- 1024×768：session-only 完成显示“仅当前页面保留”及 Token 80/20/40/140；取消显示“已取消/本次未保存”并保留已接收 partial output；结构化错误显示“失败/本次未保存/可安全重试”。document scrollWidth 与 clientWidth 一致。
- 1440×900：运行态 55% 时显示“进行中”、模型身份、分块和 partial output，reasoning `aria-expanded=false`；展开后显示固定阶段文本，完成后出现 Token 四项与已保存反馈。document 为 `1425/1425`。
- 1920×1080：`ui_case` 缓存流显示“已从缓存恢复/已保存”，三处结果容器均显示“已保存”；document 为 `1905/1905`。

控制台零 error；两个离线页面各只有既有 Vue `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__` feature-flag warning，没有新增 warning。浏览器视口最终已 reset，临时 tabs 已关闭。

截图保存在仓库外 `aspect3/`：`ui-ready-360.png`、`ui-hydration-loading-768.png`、`ui-hydration-error-768.png`、`unit-session-only-panel-1024.png`、`llm-cancelled-partial-1024.png`、`llm-error-retryable-1024.png`、`llm-running-collapsed-1440.png`、`llm-reasoning-expanded-1440.png`、`ui-cached-saved-1920.png`。二进制不进入 Git。

### 兼容性与完成边界

- 19 个 workflow、公共路由、路由守卫、生产 REST/SSE、缓存、artifact revision、延迟保存、stale、失败回滚和 regeneration lock 保持不变。
- `WorkflowStepper` 的 props、六状态和实现未修改。
- 五类 session-only 与三类持久化 case 定义保持不变；fixture 契约证明 session-only 不发送 artifact、不缓存且 `saved=false`。
- `package.json`、`package-lock.json` 无变化，无新增 npm/pip、字体、图标、测试框架或 UI 依赖。

Aspect 3 到此停止；等待 Aspect 4 或其他明确指令。

## 2026-08-23 — Aspect 4：项目入口、恢复与文档引导

### 范围与用户资产

本次只重构 `LoginView`、`CreateView`、项目 setup 本地状态、onboarding 共享组件与离线夹具；MainView、TestPlan、TestMenu、八类测试页、LLM 组件、router、生产后端、DAO、SQL、workflow catalog 和 Aspect 5–8 均未修改。

开始时 branch 为 `main`，HEAD 与本地 `origin/main` 均为 `5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`。全部既有 dirty tracked/untracked 内容和依赖清单均记录 SHA-256，并作为用户资产保护。没有 fetch/pull/stage/commit/push，没有安装依赖，没有读取真实 `.env`，也没有访问真实模型、embedding、MySQL、外网或真实项目数据。

### 实施内容

新增 `OnboardingShell`、`ProjectIdDisplay` 与 `DocumentUploadGroup`。入口和创建页统一采用中性画布、白色表面和小面积森林绿强调；360/768 使用单列，桌面登录入口可双栏。项目 ID 始终显示完整 21 位值，复制结果通过 `aria-live` 反馈，并明确它是恢复入口且不应公开分享。

登录页现在区分“继续上次项目”“打开已有项目”“创建新项目”三个入口。项目 ID 先 trim 并校验 `Ez` 加 19 位数字，提交期间防重复；成功登录后读取只读 setup status，完成项目进入测试计划，未完成项目进入 `/create` 恢复。切换另一个未完成项目或清除本机恢复指针都必须确认，文案明确不会删除服务器项目和文档。未卸载完成的登录 GET 会被 AbortController 取消，失败状态留在表单内供显式重试。

`ProjectSetupState` 增加向后兼容的 `documentCounts`、`documentFiles` 与 `allowedActions`。服务端 basename 文件清单会被应用并持久化；旧 localStorage 缺失或非法字段会补默认值，遗留 running 状态恢复为 pending。文件名比较镜像后端规范化且不区分大小写；每个上传 POST 成功后立即记录，后续失败时继续保留，重试只发送未成功文件。

创建页校验 1–80 字项目名、危险字符、扩展名、大小和规范化重名。首次写入前确认项目名和三组文件数量，明确不会启动模型；上传进度按真实文件序号/总数显示。部分失败反馈会列出具体组、已复用和待重试文件。三个组完成后才读取 status 并调用既有 finalize；完成态显示“资料已确认，尚未开始模型分析”，只有用户明确点击才进入计划。上传/finalize 进行中阻止离开，未完成项目离开或清除本机恢复均有对应确认。

离线夹具新增显式 `--enable-onboarding`、`--origin-port` 和 `--fail-upload-once requirements`。它只绑定 `127.0.0.1`，只在进程内保存合成名称、basename、步骤和完成状态；multipart 内容有界读取但不保存字节。未启用 onboarding 时仍拒绝项目写路径，不提供 DELETE，也不导入生产后端或读取环境配置。

### 红绿测试与构建

1. 新 onboarding 契约首次运行：`7 failed`，对应组件、登录分流、setup 新字段、逐文件重试、显式夹具与文档均尚未实现。
2. 完成实现和文档后聚焦契约：`7 passed in 0.06s`。
3. foundation + application shell + shared interactions + onboarding + 原 frontend contracts：`57 passed in 1.27s`。
4. 完整离线后端门禁：`319 passed in 8.90s`。
5. `npm run lint`：通过，`No lint errors found`。
6. `npm run build -- --dest <系统临时唯一 Aspect 4 目录>`：成功，65 个临时文件；验证目标位于系统临时目录后已安全删除，现有 `dist` 未覆盖。

所有 pytest 使用项目 Python 3.11、禁用 `.env` 自动加载和 bytecode、使用内存 SQLite、空 provider keys 与 `-p no:cacheprovider`。build 只保留既有 asset/entrypoint size 和 Node `fs.Stats` deprecation warning。

### 浏览器验收

浏览器只连接本任务专用 loopback 前端/夹具。标准 `18080/18130` 已被既有进程占用时使用 `18082/18131`，没有停止或修改既有进程；验收结束后仅停止本任务启动的进程。上传内容为仓库外的小型合成文本，完成后已删除。

- 360×800：登录错误为持久可见 alert，focus 可见；document 为 `345/345`，无页面级横向溢出。
- 768×1024：新建项目为单列，三组输入和操作按钮不扩张页面；项目名、扩展名、重复文件与移除确认均可键盘操作。
- 1024×768：预置未完成 PID 登录后进入 `/create`；知识库和设计已上传清单准确，只有需求组仍提供文件输入。
- 1440×900：需求组首个文件成功、第二个失败；页面明确显示失败组、已复用文件和待重试文件，重试只提交剩余文件。
- 1920×1080：三组完成后才 finalize；项目 ID 可复制并有安全保存指导，完成弹窗要求显式进入计划。完整固定 PID 登录直接进入计划。

浏览器网络流程没有 LLM、embedding 或遗留 type-analyze 请求；创建/上传/finalize 都只发生在用户确认和显式操作后。控制台零 error；仅保留既有 Vue `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__` feature-flag warning。截图保存在仓库外：`aspect4-login-error-360.png`、`aspect4-recovery-1024.png`、`aspect4-partial-failure-1440.png`、`aspect4-complete-1920.png`，不进入 Git。

### 兼容性与完成边界

- 19 个 workflow、路由守卫、生产 REST/SSE、缓存、artifact revision、session-only、取消、stale、失败回滚和 regeneration lock 保持不变。
- doctype 1/2/3、上传顺序、登录/add/upload/setup-status/finalize endpoint 与 envelope 保持不变。
- `package.json`、`package-lock.json` 无变化，无新增 npm/pip、字体、图标、测试框架或 UI 依赖。
- 真实 `.env`、`node_modules`、现有 `dist`、截图、合成上传文件、pytest cache 和临时 build 均未进入 Git。

Aspect 4 到此停止；等待 Aspect 5 或其他明确指令。

## 2026-08-23 — Aspect 5：测试计划与测试菜单工作台

### 范围与用户资产

本次只重构 `TestPlan.vue`、`TestMenu.vue`、规划领域 registry/卡片、只读 bundle 恢复、重新生成确认和离线 planning fixture；八类测试页面、MainView、onboarding、共享 LLM 组件、router、生产后端、SQL 与 Aspect 6–8 均未修改。

开始时 branch 为 `main`，HEAD 与本地 `origin/main` 均为 `5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`。全部既有 dirty 内容作为用户资产保护。结束核对显示 README、Aspect 1–4 文档、MainView、UITest、LLM 组件、Stepper、composables 的 SHA-256 均与开始时一致；`package.json` 仍为 `769EC529...`，`package-lock.json` 仍为 `C93CDE31...`。

没有 fetch/pull/stage/commit/push，没有安装依赖，没有读取真实 `.env`，也没有访问真实模型、embedding、MySQL、外网或真实项目数据。标准 `18080/18130` 已有进程始终未触碰。

### 实施内容

`projectAnalysis.ts` 新增 `fetchProjectAnalysisBundle`，并发读取现有 info type 1/22/23。摘要与计划必须为非空字符串，菜单接受对象或 JSON 字符串但必须包含九个 boolean 字段；请求支持 AbortSignal，失败不会回退到 SSE。

`TestPlan.vue` 采用共享工作台组件，区分正在只读恢复、analysis-required 空状态、当前已保存版本、stale 旧版和“本次未保存草稿”。页面加载只读取 workflow status 与 bundle GET。只有显式生成或确认重新生成才调用现有 `/project/llm/plan/stream`；只有正文、菜单完整且 `saved=true`、`ready=true` 时提升新版本。失败、取消与不完整完成保留旧 bundle 和已收到草稿，并在 `finally` 恢复 regeneration lock。

`TestMenu.vue` 从 `TEST_WORKSPACES` 固定渲染八类工作区，不再把测试计划作为第九张卡片。状态优先级为 regenerating、not-recommended、stale、locked、available；`completed_operations` 只补充“已有可恢复结果”，不会把可进入状态冒充为已完成。`TestWorkspaceCard` 使用 article、空 alt 装饰图、可见状态/原因、下一步和单一 RouterLink，网格为 auto-fit 260px。

八张插图逐张使用内置 `image_gen` 生成，第一张单元测试作为后续风格锚点。提示词分别要求：独立代码模块与检查标记；互联模块与连接桥；双端点与双向箭头；浏览器轮廓、指针与检查标记；数据圆柱、放大镜与检查标记；业务流程节点与检查路径；性能仪表、盾牌与脉冲；目标、握手与最终检查标记。所有提示词共同约束透明背景、几何线面、强轮廓、森林绿/炭黑/中性灰与少量蓝/琥珀、无文字/数字/商标/水印/场景。机械缩放后均为 256×256 RGBA PNG，单张 55–79 KiB，八张合计 567857 bytes。

离线夹具新增 mixed menu、首次 retryable 失败与 project-analysis-stale 三个固定 PID、进程内 `PlanningFixtureState`、info GET 与 0–10000ms 的 `--plan-delay-ms`。只有 completed 完整送达才更新合成 bundle；首次失败包含 partial summary/answer 且无保存。夹具仍只绑定 `127.0.0.1`、不落盘、不导入生产后端。

### 红绿测试与构建

1. 新 planning cockpit 契约首次运行：`8 failed`，对应只读 bundle、计划/菜单工作台、registry/卡片、插图、fixture 与文档尚未完成。
2. 计划页、菜单页与状态层实现后：4 项通过，剩余 4 项仅为插图、fixture、文档和测试自身的接口字段计数错误；修正计数断言并完成其余实现后：`8 passed`。
3. foundation + application shell + shared interactions + onboarding + planning cockpit + 原 frontend contracts 首次回归发现 2 项旧菜单静态契约；通过保留 `statusForTestType`/三态兼容表达并避免将 completed 当主状态后：`65 passed in 1.27s`。
4. 完整离线后端门禁：最终 `327 passed in 8.95s`；聚焦契约最终 `8 passed in 0.08s`。
5. 首次组合测试误用了缺少项目依赖的默认 Python 3.12，收集阶段即停止；改用既有 `ezllmtest` Python 3.11 环境后通过，没有安装或更改依赖。
6. `npm run lint`：通过，`No lint errors found`。
7. `npm run build -- --dest <系统临时唯一 Aspect 5 目录>`：最终成功，62 个临时文件；两个经验证位于系统临时根目录的 build 目录均已安全删除，现有 `dist` 未覆盖。

build 只保留既有 asset size limit、entrypoint size limit 和 Node `fs.Stats` deprecation warning。凭证扫描为 clean；`git diff --check` 通过。

### 浏览器验收

浏览器只连接本任务专用 `127.0.0.1:18082/18131`；所有交互使用六个固定合成 PID。验收完成后关闭临时 tab、reset viewport，并只停止本任务进程。端口复核为 18082/18131 已关闭，既有 18080/18130 仍在监听。

- 360×800：analysis-required 只显示空状态、模型选择和“生成并保存”；document 为 `360/360`，加载未触发生成。
- 768×1024：retryable 失败同时显示持久 alert、LLM “失败/本次未保存/可安全重试”和 partial 草稿；document 为 `753/753`。
- 1024×768：stale 旧 bundle 在重新生成期间持续可见；取消后仍存在，取消反馈完整，regeneration lock 已清理；document 为 `1024/1024`。
- 1440×900：mixed menu 精确渲染 8 卡，6 张 available、2 张 not-recommended；八图 natural size 均为 256×256、alt 为空；document 为 `1425/1425`。
- 1920×1080：2 张 stale、6 张 available，内容区为 1200px；document 为 `1905/1905`。卡片主状态和辅助结果文案分离。

浏览器控制台零 error；仅保留既有 Vue `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__` feature-flag warning。截图保存在仓库外：`aspect5-plan-empty-360.png`、`aspect5-plan-failure-draft-768.png`、`aspect5-plan-cancel-old-version-1024.png`、`aspect5-menu-mixed-1440.png`、`aspect5-menu-stale-1920.png`，另有八图 contact sheet；均未进入 Git。

### 兼容性与完成边界

- 19 个 workflow、公共路由、路由守卫、生产 REST/SSE wire format、模型 registry、缓存、artifact revision、延迟保存、session-only、取消、stale、失败回滚和 regeneration lock 保持不变。
- `package.json`、`package-lock.json` 无变化，无新增 npm/pip、字体、图标、测试框架或 UI 依赖。
- 旧测试类型图片完整保留，只停止在 TestMenu 中引用；八类测试页面没有迁移。
- 真实 `.env`、`node_modules`、现有 `dist`、截图、pytest cache 和临时 build 均未进入 Git。

Aspect 5 到此停止；等待 Aspect 6 或其他明确指令。

## 2026-08-23 — Aspect 6：八类测试工作区

### 范围与用户资产

本次只统一八类测试页的页面骨架、阶段编排、恢复反馈、选择控件、结果展示与响应式规则，并扩展测试工作流 composable、session-only 确认、自然长文本展示和离线 workspace fixture。router、MainView、TestPlan、TestMenu、onboarding、生产后端、SQL、workflow catalog、prompt、预算及 Aspect 7–8 均未修改。

开始时 branch 为 `main`，HEAD 与本地 `origin/main` 均为 `5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`。开始时 55 个 dirty tracked/untracked 文件均记录 SHA-256，并全部作为用户资产保护；`package.json` 为 `769EC529...`，`package-lock.json` 为 `C93CDE31...`。没有 fetch/pull/stage/commit/push，没有安装依赖，没有读取真实 `.env`，也没有访问真实模型、embedding、MySQL、外网或真实项目数据。

### 实施内容

新增 `TestWorkspaceScaffold`、`TestFieldGroup`、`TestTargetSelector`、`TestResultText` 与 `TestRetentionNotice`。八页统一使用页面头、`WorkflowStepper`、hydration loading/error、按真实 operation 顺序排列的 `WorkspaceSection`、就近模型与操作、LLM 面板、保留提示和 `ResultContainer`。共享组件只负责展示、语义和响应式，不接管业务调度。

单元测试仍使用三个阶段独立模型；其余七页保留页面级模型，并在每个可执行阶段就近展示同一值。19 个 operation 的顺序与 payload 字段保持不变；API 继续区分“全部接口”和“指定接口”两种 payload。单元和集成范围重新生成时隐藏旧下游控件，失败或取消恢复原内容。

`qualifiedReferences.ts` 只解析现有 `显示名 ｜ qualified_name ｜ source` 格式，请求继续提交完整原始值。同名目标在选择器中同时显示 qualified name 与来源文件。`useTestWorkflow` 新增 hydration、可见结果、显式持久化恢复判定和本地 stale 标记；hydrate 仍只执行现有 status GET，不新增 SSE。依赖步骤变 stale 后，下游执行会被锁定，避免使用旧输入继续生成，但不会篡改服务器 revision truth。

fresh persisted step 若服务器已完成而当前页面无正文，会显示“恢复匹配的已保存结果”；只有用户显式点击才调用既有 non-regenerate cache-aware SSE。已显示结果不再提供重复“继续分析”。stale 且未恢复正文时要求显式重新生成。五类 session-only 最终结果清空前调用统一确认；取消后结果保持。UI、数据库和验收的持久化最终结果只在本页隐藏并可立即重新显示，不调用 SSE、reset、DELETE 或保存接口。

`LlmWorkflowExecution` 的 partial answer 改为自然文档流、`pre-wrap` 和安全换行；原 props、cancel emit、显示条件及失败/取消保留 partial 的语义不变。离线夹具新增固定 workspace PID `Ez3000000000000000007`，提供全部持久化 preliminary、三类 persisted final、五类 session-only 的正确结果结构；单元 fixture 含两个显示名相同但 qualified/source 不同的目标。

### 红绿测试与构建

1. 新 Aspect 6 契约首次运行：`8 failed, 1 passed`，对应共享组件、八页统一骨架、恢复/保留语义、qualified helper、fixture 与文档尚未实现。
2. 完成主要实现后，聚焦 frontend 合约为 `44 passed`；Aspect 1–6 全部 frontend contracts 最终为 `74 passed in 1.34s`。
3. 完整离线后端门禁最终为 `336 passed in 9.05s`。
4. `npm run lint`：通过，零 error、零 warning。
5. `npm run build -- --dest <系统临时唯一 Aspect 6 目录>`：成功，未覆盖现有 `dist`；只保留既有 asset/entrypoint size 与 Node `fs.Stats` deprecation warning。

所有 pytest 使用项目 Python 3.11、禁用 `.env` 自动加载和 bytecode、使用内存 SQLite、空 provider keys 与 `-p no:cacheprovider`。首次红灯误用系统 Python 3.12 后，所有正式门禁均切回既有 `ezllmtest` Python 3.11 环境；没有安装或更改依赖。

### 浏览器验收

浏览器只连接本任务隔离的 loopback 前端/夹具。发现 18080/18130 已有中午启动的进程后，将本任务服务迁移至已确认空闲的 `18082/18131`，不停止或修改既有进程。验收数据全部来自固定合成 PID；显式恢复/生成只访问离线 fixture。

- Unit 360×800 / 1920×1080：移动端单列且 document 为 `345/345`；宽屏 qualified 选择器完整展示同名目标。模型控件在自身边界内处理窄屏，不扩张页面。
- Integration 768×1024 / 1440×900：三阶段 Stepper 与第一阶段恢复入口可读，两次均为 `scrollWidth === clientWidth`。
- API 360×800 / 1024×768：移动与固定侧栏下均无横向溢出，并继续保留全部/指定两个入口。Database 1024×768 / 1440×900 同样通过。
- UI 768×1024 / 1920×1080：两个 persisted 阶段均只提供显式恢复；在 1440×900 交互补测中，最终结果隐藏后按钮变为“重新显示”，结果正文消失，重显后正文原样返回且未重置工作流。
- Functional 360×800 / 1440×900 与 Nonfunctional 768×1024 / 1920×1080：长文本、阶段入口和 session-only 边界不扩张页面。
- Acceptance 1024×768 / 1920×1080：固定侧栏与宽屏内容均通过，宽屏保持 1200px 阅读上限，最终结果继续标记为持久化。
- 单元同名函数选择器同时显示 `fixture.auth.create(request)` / `auth-service.py` 与 `fixture.billing.create(request)` / `billing-service.py`，未丢失 qualified/source。
- API session-only 结果显示“仅当前页面保留”；点击清空后出现明确确认，选择“保留结果”后 dialog 关闭且 `API-FIXTURE-001` 仍可见。

页面首次加载均只出现 status GET，没有自动 workflow SSE；只有显式恢复或生成后才出现 POST。五个代表视口均满足根页面 `scrollWidth === clientWidth`。浏览器控制台零 error；只有既有 Vue `__VUE_PROD_HYDRATION_MISMATCH_DETAILS__` feature-flag warning。截图保存在仓库外 `ezllmtest-aspect6-browser-20260823/`：`unit-360.png`、`ui-1440.png`、`acceptance-1920.png`、`unit-qualified-1920.png`，不进入 Git。

### 兼容性与完成边界

- 19 个 workflow、公共路由、路由守卫、生产 REST/SSE wire format、缓存键、artifact revision、延迟保存、取消、失败回滚和 regeneration lock 保持不变。
- 五类 session-only 与三类持久化 final 的边界保持不变；未增加生产接口、数据库或存储写入。
- `package.json`、`package-lock.json` 无变化，无新增 npm/pip、字体、图标、浏览器测试框架或 UI 依赖。
- 真实 `.env`、`node_modules`、现有 `dist`、截图、pytest cache 和临时 build 均未进入 Git。

Aspect 6 到此停止；等待 Aspect 7 或其他明确指令。

## 2026-08-23 — Aspect 7：跨产品无障碍、响应式与性能硬化

### 范围与用户资产

本次只实施 WCAG 2.2 AA、跨页面响应式、状态播报、内容术语和前端资产性能硬化；未开始 Aspect 8。开始时 branch 为 `main`，HEAD 与本地 `origin/main` 均为 `5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`。72 个既有 dirty 文件逐一记录 SHA-256 并作为用户资产保护；`package.json` 为 `769EC529...`，`package-lock.json` 为 `C93CDE31...`。

没有 fetch/pull/stage/commit/push，没有安装依赖，没有读取真实 `.env`，没有访问真实模型、embedding、MySQL、外网或真实项目数据。生产后端、SQL、fixture 协议、路由路径/守卫和工作流语义没有修改。

### 实施内容

新增 `accessibility.css`，集中实现 3px 实色 focus、forced-colors、44px 移动端目标、sticky header focus scroll margin、320px reflow 与 reduced-motion。`ModelSelector` 使用实例 UID 生成唯一 ID，并在 480px/320px 使用两列/单列；必填 fieldset、目标 select 和 description 直接关联真实控件。

新增 `routePresentation.ts`，统一 13 条入口/工作区路由标题；既有 `beforeEach` 守卫保持不变，`afterEach` 在渲染完成后更新“页面名 | EzllmTest”并聚焦当前 main。MainView、Onboarding 和 About 补齐一致 landmark 与焦点目标，移动抽屉的 trap、inert、body lock、Escape 和焦点恢复保持原行为。

`FeedbackState` 增加向后兼容的 `none/content/form/cards` skeleton；创建恢复、计划恢复、菜单恢复与八页 hydration 只在未知只读布局使用。WorkflowStepper、LLM 面板和 TestMenu 改用简短 atomic polite summary，reasoning/token delta 和整张卡片网格不再造成重复播报。用户术语统一为 API 接口、前端 UI、项目 ID 和“按当前模型与输入查找并恢复已保存结果”，内部 operation/endpoint/payload/artifact 字段不变。

新增 `plugins/elementPlus.ts`，按需注册 21 个组件、各自 CSS、16 个壳层图标和 message/message-box service；`main.ts` 移除完整 Element Plus、完整图标集和全量 CSS。`vue.config.js` 关闭 production source map 并显式设置 Vue hydration mismatch flag。新 192×192 RGBA Logo 为 81,689 bytes，原 688,067-byte Logo 保留。

### 红绿测试与构建

1. 新 hardening 契约首次运行有 `11 failed`，准确覆盖完整 Element Plus、重复 ID、focus、live summary、skeleton、Logo、bundle checker 和文档缺口。
2. 主要实现后聚焦契约为 10 项通过、仅 hardening 文档尚缺；发布文档并更新过期的 ModelSelector 横向滚动断言后，Aspect 1–7 与原 frontend contracts 最终 `85 passed in 1.45s`。
3. 完整离线后端门禁最终 `347 passed in 9.12s`。
4. `npm run lint` 通过，零 error、零 warning。
5. 最终 production build 成功；过程中发现的 6 条 CSS import-order warning 通过统一共享组件副作用导入顺序消除。最终只剩 Vue CLI 既有 asset/entrypoint size 两条 warning 和 Node `fs.Stats` deprecation，没有抬高阈值或 `ignoreOrder`。
6. bundle checker 通过：source map 0；最大初始 JS 443,202 raw / 143,473 gzip；初始 CSS 111,092 / 19,519；index 初始资产 567,225；完整目录 1,580,460 bytes、46 文件。

凭证扫描为 clean（tracked 167、staged 0、untracked 44）；`git diff --check` 无错误，仅显示工作区既有 LF/CRLF 提示。package manifests 哈希与开始时一致。Aspect 1–6 冻结资产只有批准的 Aspect 7 文件发生预期变化；overview/prompts、历史文档、插图、fixture、state/composable、旧字体/图片和现有 `dist` 没有意外变化。

### 浏览器验收

隔离服务仅绑定 `127.0.0.1:18280/18281`，数据为固定合成 PID。计划、菜单和八类测试在 360/768/1024/1440/1920 五个基准视口逐路由检查，共 50 组：全部满足根 `scrollWidth === clientWidth`、无重复 ID、main/aside 位于视口、路由标题正确且切换后 main 获得焦点。1920px 内容宽度为 1200px，Stepper 为 `1200/1200`；360px Stepper/segmented 同样无内部溢出。

额外 320×800 验证根与 main 均为 `305/305`，无小于 44px 的可见交互目标。移动抽屉打开、Escape、inert、body lock 与焦点恢复通过；TestMenu 只保留一次性八类摘要；Stepper 的完成摘要为 atomic polite。控制台零 error/warning，Aspect 6 记录的 Vue feature-flag warning 已消失。页面首次恢复仅出现 GET，没有自动模型 SSE。

截图保存在仓库外 `ezllmtest-aspect7-browser-20260823/`：`aspect7-drawer-360.png`、`aspect7-plan-768.png`、`aspect7-unit-1024.png`、`aspect7-menu-1440.png`、`aspect7-unit-1920.png`。

内嵌浏览器显式 viewport 不提供可验证的页面 zoom 控制，尝试 200% 快捷键后 `visualViewport.scale` 仍为 1；因此只把 320 CSS px 等效高倍率重排记为自动通过，真实 1280px/200% 保留为人工复核。Windows 自动化安全边界禁止操控承载页面的 Codex 窗口，Narrator 音频也无法被当前工具可靠采集；本次完成 browser accessibility tree 的 heading、label、required、status/alert/live region、当前路由/步骤烟雾验证，但没有虚报 Narrator 可听结果。

### 完成边界与清理

最终关闭本任务浏览器 tab、reset viewport，并只停止 21:59 启动的任务进程。18280/18281 已关闭；中午启动的用户进程 18080/18130 仍监听且未触碰。四个经逐一验证位于系统临时根目录、名称以 `ezllm-aspect7-` 开头的 build 目录已安全删除，仓库现有 `dist` 未覆盖。

19 个 workflow、公共路由、路由守卫、REST/SSE wire format、缓存、artifact revision、延迟保存、五/三 retention 边界、取消、stale、失败回滚和 regeneration lock 保持不变。Aspect 7 到此停止；等待 Aspect 8 或其他明确指令。

## 2026-08-23 — Aspect 8：集成体验验收与迭代收口

### 范围、资产与红绿过程

本次只补完整离线旅程、持久化失败、收口缺陷和文档，不扩展产品能力。开始时 branch 为 `main`，HEAD/local `origin/main` 均为 `5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind `0/0`。Aspect 1–7 全部 dirty 文件及 package manifests 已逐一记录 SHA-256，并作为用户资产保护。

新增收口契约首次为 `4 failed, 3 passed`，准确覆盖缺少动态 workflow status 联动、PID 8、closeout 与 README；fixture 实现后只剩文档红灯。浏览器发现 360px segmented inline indicator 覆盖问题后，先追加失败断言，聚焦测试变为 `3 failed, 5 passed`，再用 `display:none !important` 做共享组件最小修复并复验 computed style。

### Fixture 与集成旅程

新增 `PERSISTENCE_FAILURE_PID = Ez3000000000000000008`、`PlanningFixtureState.has_generated()` 与 `workflow_status_for_request()`。动态 onboarding 项目 finalize 后、计划生成前保持 `analysis_required`；只有完整 plan `completed` 送达并写入进程内 planning state 后才变为 `analysis_ready`。

PID 8 可缓存恢复旧 `ui_info/ui_case`。`ui_case + regenerate=true` 固定发送 meta/progress/answer_delta/result/retryable error，不发送 artifact/completed；浏览器确认旧 `UI-FIXTURE-001`、partial 草稿、`本次未保存` 与“保存失败，上一份有效结果仍保留”同时可读，没有成功保存表达。

loopback multipart/REST/SSE 闭环生成 21 位 PID，需求第二文件首次 503、重试 2001，最终 `documents_ready → setup_complete → analysis_required → analysis_ready`，规划流包含完整八事件，最终 10 条工作区路径可用。所有状态只存在于本任务进程，不落盘。

### 浏览器证据与缺陷修复

专用 production 静态页/fixture 使用 18282/18132；既有 18080/18130 未触碰。浏览器验证入口、未完成恢复、analysis-required、mixed menu、八页首次进入、cached/stale/regeneration、cancelled partial、structured error、persistence error 和 session-only final。所有已测页面满足根宽度一致、无重复 ID、路由标题/main focus 正确；控制台零 error/warning。

代表截图：`aspect8-analysis-required-360-fixed.png`、`aspect8-cancelled-768.png`、`aspect8-structured-error-1024.png`、`aspect8-persistence-error-1440.png`、`aspect8-stale-menu-1920.png`，均位于仓库外。

可见 file chooser 能正常触发，但当前内嵌浏览器把临时文件注入页面时超时；因此没有虚报浏览器 bytes upload。相同合成文件的部分成功、只重试剩余文件、finalize 与计划推进已由 loopback HTTP 实际请求完成。

### 最终门禁与完成边界

- Aspect 1–8 frontend contracts：`93 passed`。
- 完整离线后端：`355 passed`。
- lint：零 error、零 warning；production build 成功。
- bundle：0 source map；最大初始 JS 443,227/143,472 raw/gzip；CSS 111,092/19,519；初始总量 567,254；完整目录 1,580,498 bytes、46 文件。
- 凭证扫描 clean；`git diff --check` 无空白错误；package manifests 哈希不变。

真实 `.env`、模型、embedding、MySQL、外网、真实项目和仓库 `dist` 均未访问或覆盖。任务浏览器、18132/18282、临时 junction/build/合成文件在完成门禁后清理；18080/18130 保持原状态。不 stage、commit、fetch、pull 或 push。Iteration 3 标记为“已完成离线验收，等待用户决定发布”。

## 2026-08-24 — 收口后修复：首个拖拽文档触发递归更新

`DocumentUploadGroup` 原先把 `el-upload` 的 `file-list` 双向绑定到可写 computed；其 getter 每次用 `filter()` 创建新数组。首个文件拖入后，Element Plus 回写列表、父组件更新与新数组引用互相触发，最终出现 `Maximum recursive updates exceeded`。

修复改为把父级 `modelValue` 作为稳定的受控 `file-list` 直接传入，并通过明确的 `update:file-list` 事件向上更新；已上传文件仍由既有上传成功记录和父级列表移除流程处理，未改变上传顺序、重名校验、部分成功复用、恢复或 finalize 语义。全仓 writable computed 审计只发现 `ModelSelector` 与 `TestTargetSelector` 两处直接透传标量 prop，不存在同类派生数组反写。

新增 onboarding 回归契约先失败再转绿；聚焦测试 `8 passed`，完整离线测试 `356 passed`，`npm run lint` 通过。排除 `.env*` 的临时生产构建和 bundle checker 均通过；仅保留既有 Vue CLI 体积提示与 Node `fs.Stats` deprecation。没有修改依赖清单、生产后端、接口、数据库或工作流语义。

## 2026-08-24 — 收口后修复：长 qualified name 聚焦重叠与裁切

共享 `TestTargetSelector` 在 Element Plus filterable 单选框获得焦点时，同时渲染透明态的已选 placeholder 和空过滤输入框；两者占用相同起始位置，导致输入光标压住长 qualified name。下拉项和关闭态控件又采用单行省略，用户无法核对同名目标的完整来源。

修复集中在共享选择器，因此同步覆盖单元、集成、API、功能与非功能测试页：聚焦过滤时隐藏重复 placeholder，关闭态继续使用安全省略；控件下方始终展示当前选择的完整标签和 qualified/source 详情；下拉项允许自然换行并保持至少 44px 交互高度。`aria-describedby` 同时关联字段说明和当前完整选择，请求仍提交原始完整 value，未修改 payload 或 qualified/source 区分语义。

新增长目标回归契约先失败再转绿；工作区聚焦测试 `10 passed`，完整离线测试 `357 passed`，`npm run lint` 通过。排除 `.env*` 的临时生产构建通过 bundle checker：0 source map、最大初始 JS 443,227 bytes、初始 CSS 111,092 bytes、完整目录 1,589,590 bytes。浏览器在 360px 与桌面视口验证聚焦 placeholder 为 hidden、长下拉项自动换行、根页面无横向溢出且控制台零 error/warning。没有修改依赖清单、生产后端、REST/SSE、数据库或工作流语义。

用户随后复测发现键盘聚焦、下拉关闭以及点击切换瞬间仍有遗漏：这些状态中的已选 placeholder 没有 Element Plus 的 `is-transparent` class，旧选择器无法命中。回归契约再次先红后绿，规则改为基于共享控件原生 `:focus-within` 隐藏整个 placeholder 层，不再依赖 Element Plus 的瞬时内部 class。浏览器复现确认该精确状态的 placeholder class 仅为 `el-select__placeholder` 时仍计算为 hidden，失焦后恢复 visible；完整离线测试仍为 `357 passed`，lint、隔离 production build 和 bundle checker 继续通过。

进一步按用户截图复核发现，`:focus-within` 虽消除了叠字，却让选择完成后仍保持焦点的控件暂时隐藏已选文字；同时全局 focus 规则会让 Element Plus 内部原生 input 和外层 composite wrapper 各画一次 outline，形成左侧小框与外层焦点环重叠。最终修复改为监听既有 `visible-change`：下拉打开时隐藏 placeholder 并显示搜索光标；选择完成、下拉关闭且焦点保留时立即显示已选文字，只把空过滤输入的 caret 设为透明。全局无障碍样式同时禁止 Element Plus 内部 focus proxy 绘制第二个 outline，外层 3px 可见焦点环继续保留。

仓库审计确认所有生产 `<el-select>` 均通过该共享组件，修复覆盖单元、集成、API、功能和非功能测试页。聚焦契约 `21 passed`，完整离线测试 `357 passed`，lint 和隔离 production build 通过；浏览器确认选择完成瞬间 `activeElement` 仍为 combobox、已选 placeholder 已为 visible、caret 为 transparent、内部 outline 为 none，点击外部前后文字一致且根页面无横向溢出。

## 2026-08-24 — 品牌资产更新：采用 B05 Logo

用户从 30 个纯图形候选中选择 B05：以断开的圆环构成字母 E 负形，延续森林绿与深绿色品牌识别。候选由内置图像生成能力制作；最终应用阶段只使用本地确定性图像处理恢复真实透明通道、居中裁切和等比缩放，没有再次调用外部模型或读取任何 API key。

新增 `ezlogo-workbench-v2.png`（192×192 RGBA，图形最大边界 168px）与 `favicon.png`（48×48 RGBA），应用壳继续使用 38px、登录/创建入口继续使用 52px。`public/index.html` 显式声明 48px favicon。原 `ezlogo-workbench.png`、`ezlogo.png` 和 `logo.png` 全部保留，便于无损回滚；生产 Vue 源码不再引用旧 workbench Logo。

本次只更新品牌图片及引用，没有修改路由、状态、REST/SSE、缓存、工作流、数据库或依赖清单。新增独立 Logo 契约覆盖 PNG 签名、尺寸、RGBA Alpha、体积、图形边界、生产引用、favicon 与旧资产保留。

Logo 与 hardening 聚焦契约 `14 passed`，Aspect 1–8 加品牌契约的纯前端离线门禁 `71 passed`；`npm run lint` 零错误。排除 `.env*` 的临时 production build 成功，bundle checker 通过：source map 0，Logo 25,193 bytes，最大初始 JS 443,227/143,472 raw/gzip，初始 CSS 111,209/19,536，入口资产 571,051，完整目录 1,538,551 bytes、47 文件。只保留既有 Vue CLI 体积提示与 Node `fs.Stats` deprecation。

完整后端 pytest 也已尝试，但当前系统 Python 缺少仓库既有 FastAPI、LangChain、OpenAI、toollib、pypdf 等依赖，测试在收集阶段停止；遵守本轮不安装依赖约束，没有改变本机环境。该限制不影响上述纯前端契约、lint、production build 与 bundle 验收结果。

浏览器仅访问本任务 loopback 合成服务：360px 登录入口、1024px 创建页与固定侧栏应用壳、1920px 应用壳均无根页面横向溢出；Logo 自然尺寸 192×192，入口渲染 52×52，壳层渲染 38×38。favicon 和构建哈希 Logo 均成功加载，应用壳控制台零 error/warning。未触发计划或 workflow SSE，没有访问真实模型、embedding、MySQL、外网或真实项目。

## 2026-08-24 — 收口后修复：测试结果绑定生成时选择

单元测试页原先只判断某个 operation 是否已有结果，没有比较当前单元与生成该结果时保存的 selection。因此切换待测单元、测试方法或输出格式后，上一选择的正文和已完成执行面板仍会继续显示；集成、API、功能与非功能测试页存在相同模式。

修复集中在 `useTestWorkflow`：按各步骤既有 `selectionFields` 规范化比较当前选择与生成时选择，提供结果可见性、任意两次选择匹配及可逆 selection stale 协调。切到不同选择时只暂时隐藏旧结果并把受影响步骤标为 stale；切回原选择时恢复切换前状态和旧结果，不删除 session-only 内容、不请求缓存、不触发 SSE。如果服务器本来已标记 stale，切回后仍保持服务器 stale 语义。`useLlmWorkflow` 同时保留最近一次执行 payload，使已完成、失败或取消后的执行反馈也只在对应选择下显示。

五个存在业务选择的页面全部接入共享机制：单元的目标/方法/格式，集成的类型/对象/策略/格式，API 的全部或指定范围/目标/格式，功能的业务用例/格式，以及非功能的测试类型。API 选择“全部接口”时同步清除单接口选择，避免控件与结果范围互相矛盾。UI、数据库和验收页没有此类业务目标选择，未做无关改动。

新增回归契约先红后绿；工作区聚焦测试 `11 passed`，Aspect 1–8、品牌与本次修复的纯前端离线门禁 `72 passed`，`npm run lint` 零错误。排除 `.env*` 的隔离 production build 成功，bundle checker 通过：0 source map、最大初始 JS 443,227/143,472 raw/gzip、初始 CSS 111,209/19,536、入口资产 570,988、完整目录 1,541,123 bytes。只保留既有 Vue CLI 体积提示与 Node `fs.Stats` deprecation。

浏览器使用 loopback 合成 PID 实际完成单元范围恢复、第一目标分析、切换到第二目标、再切回第一目标：切走后旧正文/下游阶段/旧执行面板计数均为 0，重新分析按钮可用；切回后正文、下游和执行反馈均恢复，步骤由“已过期/已锁定”恢复为“已完成/可开始”。功能测试页也完成配对抽查，控制台零 error/warning。没有访问真实 `.env`、模型、embedding、MySQL、外网或真实项目，也没有修改 REST/SSE、retention、缓存或依赖清单。

## 2026-08-25 — Iteration 3 私有 main 发布准备

### 远端与用户资产

开始时 branch 为 `main`，本地 HEAD 与 fetch 后的 `origin/main` 均为 `5f9c1646f94a5fa56edba232da02619f51aa3f19`，ahead/behind 为 `0/0`。GitHub CLI 通过官方网页重新授权；目标 `Jaily16/EzllmTest` 已核验为 `PRIVATE`，默认分支为 `main`。没有修改可见性、权限或分支保护，也没有使用 pull 或 force。

Aspect 1–8、B05 Logo 和收口后修复的全部 dirty 内容逐一记录 SHA-256 并视为用户资产。`package.json` 与 `package-lock.json` 仍为既有哈希，没有安装或新增 npm/pip 依赖。

### 真实 provider 与 MySQL 代表性旅程

使用系统临时目录中的虚构“Aurora 任务协作平台”测试知识、需求和设计文档；源文件未进入仓库。先执行一次显式付费预检，`GLM-4.7` 返回成功、`embedding-3` 返回 2048 维向量。随后通过真实 Vue 页面、FastAPI 与本地 MySQL 完成创建、三组上传、finalize，并执行：

`project_analysis → unit_menu → unit_info → unit_case → api_info → api_case → ui_info → ui_case`

所有 8 个高层工作流成功，没有 retryable error、重复提交、regenerate 或 provider 切换。单元选择 `TaskService` 类和 Markdown 输出，API 覆盖全部接口；`unit_case`、`api_case` 显示 session-only，`ui_case` 显示 persisted artifact。每个阶段 reasoning 默认折叠；截图与日志不保存 prompt、请求体、完整项目 ID、API key 或 provider 异常详情。

### README 截图与发布契约

`docs/images/readme/` 新增 10 张真实页面 PNG 与 JSON manifest：1440×900 桌面图覆盖入口、创建、计划运行/保存、菜单、单元、API、UI；390×844 覆盖移动导航。Windows System.Drawing 只用于确定性 RGBA 重编码和项目 ID 遮盖，不改写模型正文。图片合计低于 8 MiB，单图低于 1.2 MiB，无 PNG 文本或 EXIF metadata。

新增 `test_readme_release.py`，先以 README 章节、manifest、发布文档缺失得到 4 个预期失败，再实施 README、图片清单与文档增量。契约同时保护 19 个 workflow、原 Iteration 2/3 README 片段、无机器绝对路径、无完整项目 ID、无疑似凭证和图片目录无临时产物。

发布目标为 `Jaily16/EzllmTest` 的 `PRIVATE` `main`。完成全部离线测试、lint、隔离 build、bundle、credential、SQL 与 staged 审计后，使用两个正常提交并执行非 force push；不创建 tag 或 GitHub Release。

### 发布门禁结果

- README release 契约：首次 `4 failed`，实现后 `4 passed`。
- 完整离线测试：首次发现两个历史模板契约与 selection-aware 显示条件表达不一致；以等价嵌套守卫修复后最终 `365 passed in 9.08s`，没有放宽测试。
- `npm run lint`：零 error、零 warning。
- 无 `.env*` 临时镜像 production build：成功；bundle checker 为 source map 0、最大初始 JS 443,227 / 143,472 bytes raw/gzip、CSS 111,209 / 19,536 bytes、入口资产 570,992 bytes、完整目录 1,541,886 bytes（47 文件）。
- 凭证扫描：clean（tracked 167、staged 0、untracked 49）；SQL 数据写入语句为 0；README/manifest 中完整项目 ID 与本机绝对路径匹配均为 0。
- `package.json`、`package-lock.json` 哈希与冻结值一致；临时 build、junction 与三份合成源文档已清理，任务专用 8081/8131 已停止。

构建仅保留 Vue CLI 默认 asset/entrypoint size 提示与 Node `fs.Stats` deprecation，没有抬高预算或隐藏 warning。
