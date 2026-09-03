# Iteration 3 体验基线（Aspect 1）

## 1. 范围与证据规则

本文冻结 Iteration 3 开始时的页面、状态和视口基线。Aspect 1 只修复全局设计基础与 `WorkflowStepper` pilot；应用壳、创建流程、测试计划、测试菜单、八类工作区和 LLM 执行面板的结构性问题归入 Aspect 2–8。

证据分为两类：

- **B（Browser）**：使用 `127.0.0.1:18080` 前端与 `127.0.0.1:18130` 离线固定夹具，在真实浏览器中渲染；没有连接生产后端、模型、embedding 或数据库。
- **S（Static）**：通过 Vue SFC、状态 composable、路由与契约测试确认；创建和上传相关状态未在浏览器中执行，避免任何项目写入。

固定视口为 `360×800`、`768×1024`、`1024×768`、`1440×900`、`1920×1080`。截图是任务临时产物，不进入 Git。

## 2. 页面 × 状态 × 视口矩阵

| 表面 / 状态 | 360×800 | 768×1024 | 1024×768 | 1440×900 | 1920×1080 |
|---|---|---|---|---|---|
| 登录：默认、校验错误、请求中、失败 | B：固定定位容器宽约 429px，从 x=80 开始，右侧表单被裁切；输入 wrapper focus 为品牌绿。校验、请求和失败由 S 记录。 | S：固定负 margin 和 230px 输入仍限制弹性。 | B/S：可完成离线登录，但主动作和输入依赖内联尺寸。 | B：品牌可见，仍保留大面积浅绿渐变，留给 Aspect 4。 | S：内容不采用最大宽度容器，超宽屏信息密度偏低。 |
| 创建：空表单、部分恢复、组运行/失败、完成弹窗 | S：500/620/800px 固定尺寸在窄屏存在裁切风险；本 Aspect 未创建或上传项目。 | S：步骤和表单可能出现局部拥挤。 | S：恢复、失败重试与完成语义保持 Iteration 2。 | S：当前固定布局可用但层级松散。 | S：内容宽度无统一约束。 |
| 主框架：status loading、analysis required、ready、stale、regenerating | B：280px 侧栏令 main 仅约 65px，内容不可实用；属于 Aspect 2。 | B：main 约 473px，非 pilot 内容仍有约 11px 内部溢出。 | B：ready 壳可用，侧栏长期占 280px。 | B：层级清楚但浅绿 header、侧栏和大空白仍不统一。 | B：main 很宽，缺少内容最大宽度。 |
| 测试计划：未生成、缓存恢复、流式、取消/失败、重新生成锁定 | S：窄屏固定控件和模型选择器风险明显。 | S/B：模型 segmented 可能压缩或横向溢出。 | B：缓存恢复文案、保存提示存在。 | B：已保存缓存恢复截图；正文宽度仍未收束。 | S：长行和大面积空白风险保留。 |
| 测试菜单：loading、ready/available、locked、stale | S：卡片与侧栏叠加后难以使用。 | S：固定卡片宽度降低可用空间。 | B/S：状态文字可见，不只靠颜色。 | S：可进入/锁定/stale 语义保持。 | B：ready 菜单完整可见，但卡片排布未形成工作台密度。 |
| 单元测试：三步 ready/completed/stale、session-only final 边界 | S：壳层挤压仍主导体验。 | S：三步 grid 可换行，非 pilot 控件仍可能溢出。 | B：stale 三步状态可见，第二、三步均标为“已过期”。 | S：session-only 最终结果边界保持，不新增持久化。 | B：stale Stepper 无溢出，超宽卡片留白较多。 |
| UI 测试：两步、running reasoning、saved/cached final | B：Stepper 自身单列且无内部溢出，但被 280px 壳层压成逐字竖排；实用性归 Aspect 2。 | B：running/locked 状态、进度和取消入口可见。 | B：ready/locked 两步层级清楚。 | B：离线完成态包含 reasoning、Token 和已保存反馈。 | B：两步自动平分空间，状态文本完整。 |
| LLM 执行面板：connecting、progress、reasoning、usage、saved、cancelled、error | S：connecting 由 composable 契约覆盖；窄屏面板留给 Aspect 3/7。 | B：running 25%、当前分块、reasoning 占位和取消入口同时可见。 | B：取消后明确“本次结果未保存”，步骤转为失败。 | B：结构化 error 明确可重试与未保存；完成态显示 4 类 Token。 | S：长正文宽度和信息密度尚未收束。 |

## 3. 状态表达基线

| 语义 | 当前证据 | Aspect 1 结论 | 后续归属 |
|---|---|---|---|
| progress / connecting | `LlmExecutionPanel` 有标签、百分比、分块；初始“正在连接后端”由 composable 提供。 | 保持字段和文案，不重排面板。 | Aspect 3、7 |
| reasoning | 明示“仅当前会话展示”，空态与流式段落都存在。 | 不把合成夹具文本作为产品内容；不修改 session 语义。 | Aspect 3、6 |
| 正文与长文本 | textarea 和流式正文均可保留内容，但宽度、行长和折叠层级不一致。 | 仅提供内容宽度 tokens，页面尚未采用。 | Aspect 3、5、6、7 |
| Token | 完成态区分输入、思考、正文、总 Token；缓存态可为未知。 | 不改变字段或空值策略。 | Aspect 3 |
| cache | 测试计划明确“已读取数据库中保存的结果”。 | 保持缓存与 SSE 契约。 | Aspect 3、5 |
| saved | 成功态明确保存；取消和失败明确未保存。 | 不改变延迟保存和 artifact 语义。 | Aspect 3 |
| session-only | 五类最终 case 仅在当前页面会话保留；reasoning 也仅当前会话展示。 | 不新增浏览器或服务端持久化。 | Aspect 6 |
| cancel | 取消后保留已接收内容，步骤失败，提示“本次结果未保存”。 | 离线浏览器夹具已复现。 | Aspect 3 |
| failed | 结构化 error 显示失败原因、可重试与未保存边界。 | Stepper 以文字和 danger 语义色同时表达。 | Aspect 3 |
| stale | 主框架、菜单和 Stepper 均有“已过期”文字。 | Stepper 映射 warning，不只靠颜色。 | Aspect 5、6 |
| regeneration lock | 路由与状态契约仍在重新生成期间只允许 `/plan`。 | 没有改路由、state 或调用方。 | Aspect 5 |

## 4. WorkflowStepper pilot 前后数据

| 视口 | 改动前 client/scroll | 改动后 client/scroll | 结论 |
|---|---:|---:|---|
| 360×800 | 25 / 150 | 25 / 25 | pilot 不再制造额外横向滚动；壳层只给 25px，文本被迫逐字换行。 |
| 768×1024 | 448 / 448 | 433 / 433 | 两列自适应；全局 box-sizing 改变可用宽度，pilot 无溢出。 |
| 1024×768 | 689 / 689 | 689 / 689 | 两列、完整标签和状态。 |
| 1440×900 | 1105 / 1105 | 1105 / 1105 | 两列自动扩展，无固定空列。 |
| 1920×1080 | 1600 / 1600 | 1600 / 1600 | 两列自动扩展，长宽下仍完整。 |

pilot 已确认：

- DOM 暴露六种 `data-state` 值；当前步骤使用 `aria-current="step"`。
- 数字序号为装饰信息并设置 `aria-hidden="true"`，状态仍有可见中文文字。
- ready/available 为 info，running/current 为品牌绿，completed 为 success，stale 为 warning，failed 为 danger，locked 为中性灰。
- reduced-motion 静态契约会关闭 running 呼吸动画。

## 5. 证据清单

改动前：

- `before-login-360.png`、`before-login-1440.png`
- `before-stepper-360.png`、`before-stepper-768.png`、`before-stepper-1024.png`、`before-stepper-1440.png`、`before-stepper-1920.png`

改动后：

- `after-login-focus-360.png`
- `after-stepper-360.png`、`after-stepper-768.png`、`after-stepper-1024.png`、`after-stepper-1440.png`、`after-stepper-1920.png`
- `after-unit-stale-1024.png`、`after-unit-stale-1920.png`
- `after-llm-running-768.png`、`after-llm-cancelled-1024.png`、`after-llm-error-1440.png`
- `after-plan-cached-1440.png`、`after-menu-ready-1920.png`

## 6. 已知问题与回归边界

- 280px 固定侧栏是 360px 主内容不可用的首要原因；Aspect 1 不修改 `MainView`。
- 登录、创建、计划、菜单和测试页仍有 230/500/620/800px 等固定或内联尺寸；本 Aspect 只记录，不提前重做。
- 登录页仍使用大面积浅绿渐变；新的设计方向已经通过 tokens 和 pilot 建立，页面迁移留给对应 Aspect。
- 768px 下 main 的非 pilot 内容仍可能有约 11px 内部溢出；Stepper 本身通过验收。
- 全局 focus 与 Element Plus primary focus 已转为品牌绿；完整 Tab 顺序、所有控件的键盘操作与自动化 a11y 扫描仍需 Aspect 7。
- 当前没有 Vitest、Vue Test Utils、Playwright 或 axe 依赖；Aspect 1 采用 pytest 静态/SFC 契约加真实浏览器截图，不新增依赖。
