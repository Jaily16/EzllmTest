# Iteration 3 Aspect 3：共享交互与反馈组件

## 1. 范围与边界

Aspect 3 建立共享页面原语、LLM 执行反馈层和统一的结果替换确认模式，并仅在 UI 测试页进行布局 pilot。共享 LLM 组件的既有调用方会自动获得新的反馈层级，但测试计划、测试菜单和其余七类测试页不在本次迁移范围内。

本 Aspect 不改变 19 个 workflow、路由与守卫、REST/SSE endpoint、缓存与 artifact revision、延迟保存、session-only 边界、取消、stale、失败回滚或 regeneration lock。reasoning 只存在于当前前端会话，默认折叠，不进入结果、浏览器存储或后端持久化。

Aspect 4–8 继续分别负责登录/创建、计划/菜单、八类测试页全面迁移和后续体验工作；不得用共享组件发布为由提前重做这些表面。

## 2. 组件契约

| 组件 | 输入与输出 | 语义和使用约束 |
|---|---|---|
| `WorkspacePageHeader` | title，eyebrow/description 可选，actions slot | 工作区壳已有页面级 h1，因此内容标题使用 h2；不承载路由或请求行为 |
| `WorkspaceSection` | title，description/busy 可选，default/actions slots | 输出 section 和 aria-busy；只管理信息层级与表面 |
| `ModelSelector` | `v-model: ModelLabel`、options、disabled、label/description | fieldset/legend 提供可访问名称；窄屏仅控件内部滚动 |
| `WorkflowActionBar` | ariaLabel 和 default slot | 输出具名按钮组并负责换行；不代理点击、禁用或生成判断 |
| `FeedbackState` | loading/empty/error、title/description、busy/compact、action slot | loading/empty 为 status，error 为 alert；不自动重试 |
| `ResultContainer` | title、description、default/stale、persistent/session-only | 只表达结果和保留边界；不修改、保存或复制内容 |
| `LlmExecutionPanel` | 保留原 props 与 cancel emit；meta 扩展 persistence | 统一进度、模型、reasoning、Token、缓存/保存和终态反馈 |
| `LlmWorkflowExecution` | 保留原 props 与 cancel emit | running/error/cancelled 时继续显示已收到的 partial output |

共享组件必须使用 `--ez-*` tokens，不在全局写 Element Plus 组件覆盖，不使用页面级固定宽度。`--ez-control-height: 40px` 统一操作控件最低高度，`--ez-reading-measure: 72ch` 限制说明文字阅读宽度。

## 3. LLM 反馈层级和状态文案

固定阅读顺序为：当前状态与模型 → progress/current/total → 缓存和保留边界 → 默认折叠 reasoning → Token → 完成、取消或失败说明 → partial output。

| 条件 | 主状态 | 辅助状态 | 结果说明 |
|---|---|---|---|
| connecting | 正在连接 | 无 | 尚未收到后端进度 |
| running | 进行中 | 无 | 可以取消；已接收正文持续保留在页面中 |
| `from_cache=true` | 已完成 | 已从缓存恢复、已保存 | 未发起新的模型生成 |
| artifact 完成 | 已完成 | 已保存 | 可由服务器恢复并供下游使用 |
| session 完成 | 已完成 | 仅当前页面保留 | 刷新或离开后不可恢复 |
| cancelled | 已取消 | 本次未保存 | 已接收 partial output 仍可查看 |
| error | 失败 | 本次未保存 | retryable 时显示“可安全重试” |

reasoning 标题固定为“模型推理 · 仅本次会话”。折叠时 reasoning 增量不得造成页面跳动；展开后允许容器内部纵向滚动并安全换行。Token 始终按输入、思考、正文、总量四项展示，厂商未返回时显示明确文字而非零值。

## 4. 操作与确认规则

- 每个操作区只有一个主要动作；继续/生成使用 primary，重新生成使用 warning plain，取消使用 danger plain，重置使用 neutral/info plain。
- 所有禁用状态继续来自既有 `canRunStep`、`isRunning`、路由守卫和 regeneration lock，不由视觉组件重新计算。
- 替换有效结果前统一调用 `confirmResultReplacement(label)`；确认文案和“重新生成/保留原结果”按钮保持 Iteration 2 行为，取消返回 `false`。
- empty/error 的 action slot 由调用方显式提供；共享组件不得自行发送 REST、SSE 或模型请求。

## 5. UI 测试页 pilot

UI 测试页采用全部六个页面原语，但保留 `ui_info`、`ui_case`、模型列表、payload、缓存恢复、stale、`keepPreviousOnFailure`、取消与 reset 逻辑。hydration loading 明确说明不会自动发起模型请求；hydration error 只报告当前状态，不自动重试。

`ui_info` 和 `ui_case` 均为 artifact，结果容器显示“已保存”。五个 session-only case 的页面本次不迁移，其完成反馈由共享 LLM 面板根据现有 SSE `meta.persistence=session` 显示“仅当前页面保留”。

## 6. 视口与浏览器验收矩阵

| 视口 | Pilot 验收重点 |
|---|---|
| 360×800 | 单列 section、模型选择内部滚动、按钮全宽、reasoning 默认折叠 |
| 768×1024 | hydration loading/error、键盘 focus、partial output 换行 |
| 1024×768 | session-only、取消和失败状态可见且不只依赖颜色 |
| 1440×900 | running progress、模型身份、reasoning、Token 四项层级 |
| 1920×1080 | 缓存恢复、已保存结果、长文本和内容宽度 |

所有视口要求 document 无横向溢出，模型选择、按钮、取消和 reasoning 折叠可用键盘操作，reduced-motion 下关闭运行态脉冲与等待旋转，控制台不得出现新增 error/warning。截图只作为仓库外临时验证产物，不提交到 Git。

## 7. 测试、依赖与回滚

不新增 Vitest、Vue Test Utils、Playwright、axe、npm/pip、字体、图标或 UI 依赖。自动化由 pytest 静态/SFC/fixture 契约、既有完整离线回归、lint 和临时目录 build 组成；真实浏览器只连接 `127.0.0.1:18080/18130` 离线服务。

回滚仅撤销 Aspect 3 的共享组件、LLM 反馈增量、UI 测试 pilot、确认 helper、fixture、tokens 和文档/测试；不使用 `git reset` 或覆盖式 checkout，不涉及数据库与用户项目资产。
