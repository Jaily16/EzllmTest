# Iteration 3：集成体验验收与迭代收口

## 1. 收口结论

Iteration 3 的 Aspect 1–8 已完成离线集成验收。当前发布状态为：**未提交、未推送、未发布**，等待用户决定后续版本控制与发布动作。

本次收口没有扩展产品能力，没有修改生产后端、SQL、REST/SSE wire format、数据库结构、workflow catalog、prompt、预算或 retention 规则。19 个 workflow、14 条现有路由（其中 13 条具备独立页面呈现）、路由守卫、缓存、artifact revision、延迟保存、取消、stale、失败回滚和 regeneration lock 均由原契约与新增收口契约共同保护。

验收只连接专用 `127.0.0.1` production 静态页与进程内合成 fixture。没有读取真实 `.env`，没有访问真实模型、embedding、MySQL、外网或真实项目，也没有产生费用。

## 2. Aspect 1–8 交付摘要

| Aspect | 交付结果 |
|---|---|
| 1 | 建立页面×状态×视口基线、`--ez-*` tokens、Element Plus bridge、全局基础样式和 WorkflowStepper pilot。 |
| 2 | 重构响应式应用壳：桌面固定侧栏、窄屏抽屉、键盘 trap/Escape/焦点恢复、1200px 内容上限。 |
| 3 | 建立共享页面、section、模型、操作、反馈与结果组件，统一 LLM progress/reasoning/Token/保存/取消/失败层级。 |
| 4 | 重构登录、项目创建、恢复、文档组上传、部分成功复用、项目 ID 指导与安全退出。 |
| 5 | 重构测试计划与八类测试菜单工作台，分离已保存版本和未保存草稿，发布统一测试类型 registry 与插图。 |
| 6 | 八类测试页采用统一 scaffold、阶段布局、显式恢复、qualified selector 与五/三 retention 边界。 |
| 7 | 完成 WCAG 2.2 AA、320px reflow、状态播报、按需 Element Plus、Logo 和 bundle 性能硬化。 |
| 8 | 补齐动态项目 `analysis_required → analysis_ready`、持久化失败回滚、跨状态/视口验收和 closeout。 |

## 3. 完整离线旅程与状态矩阵

| 场景 | 证据 | 结论 |
|---|---|---|
| 入口与返回项目 | 360px：label、格式错误 alert、标题、focus 与无溢出；页面加载无写入 | 通过 |
| 未完成项目恢复 | 768px：`RECOVERY_PID` 展示知识库/设计已上传，需求组待补充，项目 ID 与安全说明完整 | 通过 |
| 新项目与部分上传 | 浏览器确认创建表单、可见 file chooser 与安全切换；loopback multipart 完成 21 位项目 ID、需求第二文件一次 503、retry 只补剩余文件 | 通过；浏览器 `setFiles` 传输限制见已知限制 |
| finalize 与 analysis required | 合成项目三组齐全后 `documents_ready → setup_complete → analysis_required`，只开放 `/plan` | 通过 |
| analysis running → ready | 显式计划 SSE 事件为 meta/progress/summary/answer/menu/result/artifact/completed；完成后 `analysis_ready`、10 条工作区路径可用 | 通过 |
| ready / mixed menu | 1440px 始终 8 卡，6 张 available、2 张 not-recommended 且有原因 | 通过 |
| 八类工作区首次进入 | 1024px 逐页进入 unit/integration/API/UI/database/functional/nonfunctional/acceptance；标题、main focus、无重复 ID/溢出 | 通过 |
| cached recovery | persisted final 显式恢复后显示 `已从缓存恢复` 与 `已保存`，Token 未返回时不伪造数字 | 通过 |
| stale revision | 1920px 计划、菜单和单元/UI 两类 stale 一致，旧内容不冒充 fresh | 通过 |
| regeneration | 1024px 旧计划运行中持续可读，下游立即显示分析中；completed 后提升新版本并恢复菜单/路由 | 通过 |
| cancellation | 768px acceptance 慢流在 partial answer 后取消；正文保留，显示 cancelled/`本次未保存`，步骤回滚而未保存 | 通过 |
| structured-output error | 1024px database 返回 retryable 结构化 error；显示 alert、`本次未保存` 和 `可安全重试` | 通过 |
| persistence error | PID 8 先缓存恢复 `ui_info/ui_case`；regenerate 只发 meta/progress/answer/result/error，无 artifact/completed；旧 `UI-FIXTURE-001` 仍可见 | 通过 |
| session-only final | 360px API case 显示 `仅当前页面保留`；fixture 不发送 artifact，completed 为 `saved=false/from_cache=false` | 通过 |
| 320px 等效高倍率 | 根页面 `scrollWidth === clientWidth`；模型 segmented 可重排；实际 input 30px 由 44px wrapper 提供目标区且满足 WCAG 24px 最低值 | 通过 |

动态合成项目的 loopback HTTP 旅程最终结果：项目 ID 长度 21；知识库/需求一/需求重试/设计均为 2001；需求二首次为 503；finalize 为 `setup_complete`；计划前为 `analysis_required`，计划后为 `analysis_ready`，`allowed_routes` 共 10 条。fixture 状态只存在于当前进程内，不落盘。

## 4. 浏览器视口证据

| 视口 | 代表场景 | 结果 |
|---:|---|---|
| 320×800 | 入口、模型 segmented 等效高倍率重排 | 根宽度一致，无页面级横向溢出 |
| 360×800 | analysis_required、session-only API final | 单列、操作全宽、保留边界可见 |
| 768×1024 | 恢复流程、acceptance cancelled partial | 抽屉壳、状态/partial 可读，无溢出 |
| 1024×768 | 八页 sweep、database structured error、regeneration | 固定侧栏、main focus、无重复 ID |
| 1440×900 | mixed menu、PID 8 persistence error | 8 卡状态与旧结果回滚清楚 |
| 1920×1080 | stale menu | 内容宽度 1200px，2 stale/6 available |

收口发现并修复一项真实缺陷：Element Plus 会给 segmented 的选中指示层写入 inline `display:block`，覆盖 Aspect 7 的窄屏隐藏规则，导致 360px 选中背景跨两行。`ModelSelector` 现在以限定的 `display:none !important` 禁用该装饰层，并继续由 `.is-selected` 项本身提供品牌背景。修复后指示层 computed display 为 `none`、高度 0，选中项为独立 44px，根页面仍无溢出。

关键截图保存在仓库外 `ezllmtest-aspect8-browser-20260823/`：

- `aspect8-analysis-required-360-fixed.png`
- `aspect8-cancelled-768.png`
- `aspect8-structured-error-1024.png`
- `aspect8-persistence-error-1440.png`
- `aspect8-stale-menu-1920.png`

浏览器控制台最终为零 error/warning。DOM 语义快照覆盖页面标题、heading、label、required、status/alert/live region、当前路由与当前步骤；首次进入八类页面只读取 status，没有自动 workflow SSE。

## 5. 自动化与构建门禁

- Aspect 1–8 与原 frontend contracts：93 项通过。
- 完整离线后端 tests：355 项通过。
- `npm run lint`：零 error、零 warning。
- production build：成功；仅保留 Vue CLI 默认 asset/entrypoint size 提示和 Node `fs.Stats` deprecation。
- 凭证扫描：clean；不打印命中原文。
- `git diff --check`：无空白错误；仅保留 Windows 工作区既有 LF/CRLF 提示。

最终 bundle 指标：

| 指标 | 结果 | Aspect 7 门禁 |
|---|---:|---:|
| source map | 0 | 必须为 0 |
| Logo | 81,689 bytes | ≤96 KiB |
| 最大初始 JS raw / gzip | 443,227 / 143,472 bytes | ≤900 KiB / ≤285 KiB |
| 初始 CSS raw / gzip | 111,092 / 19,519 bytes | ≤220 KiB / ≤34 KiB |
| index 初始资产 raw | 567,254 bytes | ≤1.20 MiB |
| 完整构建目录 | 1,580,498 bytes，46 文件 | ≤3 MiB |

`package.json` 与 `package-lock.json` 哈希保持不变，没有新增 npm/pip、字体、图标、测试框架或 UI 依赖。

## 6. 兼容性结论

- workflow catalog 仍为 19 项；公共 route path 和 `beforeEach` 路由守卫保持不变。
- SSE endpoint、事件名与字段未变；新增 PID 8 只属于离线 fixture。
- 所有 preliminary analysis 继续持久化。
- `unit_case`、`integration_case`、`api_case`、`functional_case`、`nonfunctional_case` 继续为 session-only。
- `ui_case`、`db_case`、`acceptance_case` 继续持久化。
- 持久化失败不发送 artifact/completed，不替换旧有效结果。
- project-analysis regeneration 继续立即锁定菜单和八类工作区，只有 ready 成功后解锁。
- 取消、失败、stale、缓存键、artifact revision 与 delayed saving 的 Iteration 2 语义保持不变。

## 7. 已知限制

- 未连接真实 provider、embedding 或 MySQL；离线验收不能替代付费模型质量、供应商错误和生产数据库验证。
- 内嵌浏览器能触发可见 file chooser，但把本机临时文件注入页面的 `setFiles` 在当前运行环境超时。multipart 部分失败/重试和动态项目生命周期已用同一 loopback fixture 真实 HTTP 请求闭环验证；仓库仍没有可复现的浏览器 E2E runner。
- 真实 1280px/200% zoom 仍未被当前内嵌浏览器可靠暴露；320 CSS px 等效重排已自动验证。
- Windows Narrator 的可听输出仍不能被自动采集；DOM 语义快照已覆盖辅助技术所需角色、名称和值，Narrator 音频需人工复核。
- Vue CLI 仍报告默认 asset/entrypoint 体积建议与 Node deprecation；自定义 bundle 预算全部通过，没有通过调高 warning 阈值掩盖。

## 8. 发布状态

Iteration 3 当前状态：**已完成离线验收，等待用户决定发布**。仓库保持 dirty，未 stage、未 commit、未 fetch、未 pull、未 push，也未部署任何版本。

## 9. 私有仓库发布前真实代表性旅程

用户在 2026-08-25 明确批准把 Iteration 3 发布到 `Jaily16/EzllmTest` 的 `PRIVATE` 仓库 `main`。本节是离线 closeout 之后的增量证据，不改写上文 `355 passed`、bundle 或浏览器矩阵等历史数据。

发布截图使用全新虚构的“Aurora 任务协作平台”资料，通过真实本地 MySQL、`GLM-4.7` 与智谱 `embedding-3` 完成一次 chat+embedding 预检，并顺序执行：

`project_analysis → unit_menu → unit_info → unit_case → api_info → api_case → ui_info → ui_case`

八个高层工作流全部成功，未触发 regenerate 或重试。项目分析、所有 preliminary analysis 以及 `ui_case` 按既有 artifact 规则保存；`unit_case` 与 `api_case` 按既有 session-only 规则只保留在当前页面会话。reasoning 始终折叠，发布材料未记录请求 payload、完整项目 ID、provider 异常或模型内部推理。

十张脱敏 PNG 与 manifest 位于 `docs/images/readme/`，覆盖入口、项目资料、计划运行、计划保存、八类菜单、单元分析、单元用例、API session-only、UI persisted 与 390px 移动导航。全部图片为真实页面渲染，使用确定性 RGBA 重编码；项目 ID 已遮盖或位于视口外，单图与总量均受发布契约约束。

发布目标保持为 GitHub `PRIVATE` / `main`；不创建 tag 或 GitHub Release，不修改仓库可见性，不 force push。最终远端 SHA、测试门禁和 README 图片加载状态由发布任务交付记录给出。

发布前门禁最终为 `365 passed`，`npm run lint` 零错误；排除 `.env*` 的隔离 production build 与 bundle checker 通过：0 source map、最大初始 JS 443,227 / 143,472 bytes raw/gzip、初始 CSS 111,209 / 19,536 bytes、入口资产 570,992 bytes、完整目录 1,541,886 bytes（47 文件）。凭证扫描 clean，SQL 数据写入语句为 0，package manifests 哈希与冻结值一致。保留的 warning 仅为 Vue CLI 默认 asset/entrypoint 体积建议和 Node `fs.Stats` deprecation。
