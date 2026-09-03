# Iteration 3 Aspect 6：八类测试工作区

## 1. 目标与边界

Aspect 6 将单元测试、集成测试、API、UI、数据库、系统功能性、系统非功能性和验收测试迁移到同一工作区解剖结构。页面共享标题、WorkflowStepper、恢复反馈、阶段容器、模型选择、操作条、长文本和结果保留说明，但不合并 operation、payload 或真实业务选择。

页面加载只读取现有 workflow status 与当前标签页 `sessionStorage`，不自动发起 `/project/llm/workflow/stream`。跨标签页恢复必须由用户点击；该请求沿用 cache-aware SSE，只有模型、输入选择、source revision 和其他 artifact key 条件匹配时才保证缓存复用。

## 2. 固定页面结构

每页从上到下固定为：页面说明 → 工作流步骤 → hydration loading/error → 真实 operation 阶段。每个阶段内部顺序为：stale 提示、业务选择、模型选择、主要操作与重新生成、LLM 执行反馈、本阶段结果。

| 页面 | 阶段 | 特有输入 | 最终结果 |
| --- | --- | --- | --- |
| 单元测试 | `unit_menu → unit_info → unit_case` | 单元类型、qualified target、方法、格式；三阶段模型 | session-only |
| 集成测试 | `integration_menu → integration_info → integration_case` | 集成层级、对象、策略、格式 | session-only |
| API | `api_info → api_case` | 全部/指定 API、格式 | session-only |
| UI | `ui_info → ui_case` | 无目标选择 | persistent |
| 数据库 | `db_info → db_case` | 无目标选择 | persistent |
| 系统功能性 | `functional_info → functional_case` | 业务用例、格式 | session-only |
| 系统非功能性 | `nonfunctional_info → nonfunctional_case` | 质量属性 | session-only |
| 验收 | `acceptance_info → acceptance_case` | 无目标选择 | persistent |

单元测试保留 menu、analysis、case 三个独立模型。其余七页保留一个页面级模型值，但在每个可执行阶段就近显示，避免用户需要返回页面顶部核对当前模型。

## 3. qualified target 与选择变化

单元引用继续使用兼容格式 `显示名 ｜ qualified_name ｜ source`。界面同时展示显示名、完整限定名和来源；提交给后端的 `unit` 仍是未经改写的原始字符串，因此两个显示名相同的函数不会合并。

目标、方法、策略或输出格式改变时，仅把当前浏览器内已有的受影响步骤及其下游标为 stale。服务器 source revision 和 stale truth 不被前端覆盖。单元与集成范围重新生成期间暂时隐藏旧下游控件；失败或取消通过既有 `keepPreviousOnFailure` 恢复旧结果。

## 4. 恢复、隐藏与清空

- 当前标签页已有正文：直接显示，不调用 SSE，也不再提供重复执行同一 operation 的“继续分析”。
- 服务器报告 fresh persisted 完成但当前标签页没有正文：显示“恢复匹配的已保存结果”；用户点击后才调用 cache-aware SSE。
- stale 且本标签页无正文：不冒充可读取结果，只允许显式重新生成。
- `unit_case`、`integration_case`、`api_case`、`functional_case`、`nonfunctional_case`：明确标记“仅当前页面保留”，清空前确认，刷新或离开后无法恢复。
- `ui_case`、`db_case`、`acceptance_case`：明确标记 persistent/“已保存”。“隐藏当前结果”只切换本页显示，可立即“重新显示”，不会清空 controller、调用网络或删除服务器数据。

reasoning、progress、Token、取消、失败、partial answer、缓存和保存反馈继续由 Aspect 3 的共享 LLM 组件表达，reasoning 仍只在当前会话存在。

## 5. 响应式与基线矩阵

所有字段容器 `min-width: 0`；目标 select 宽度为 `min(100%, --ez-content-compact)`；radio group 可换行；长结果使用自然文档流、`white-space: pre-wrap` 与安全断词，不使用固定高度 textarea。

| 浏览器证据 | 360×800 | 768×1024 | 1024×768 | 1440×900 | 1920×1080 |
| --- | --- | --- | --- | --- | --- |
| 单元/集成 | qualified 单列 | 三阶段与长策略 | 固定侧栏内容区 | 多阶段阅读流 | 长限定名与宽屏留白 |
| API/UI | 全部/指定操作换行 | persistent 恢复 | session/persistent 对照 | 运行反馈 | 隐藏与重新显示 |
| 数据库/功能性 | 字段不溢出 | 长用例名 | 结构化失败 | 安全重试 | 长正文 |
| 非功能性/验收 | 类型与按钮单列 | stale | 取消 partial | retention | 宽屏内容上限 |

基线要求 `documentElement.scrollWidth === clientWidth`，首次加载不出现 workflow SSE；状态必须有文字，不只依靠颜色。Aspect 7 仍负责完整的 zoom、屏幕阅读器和跨产品无障碍硬化。

## 6. 保护与回滚

本 Aspect 不修改 router、MainView、TestPlan、TestMenu、生产 REST/SSE、workflow catalog、缓存键、数据库、prompt、预算或 package manifests。不访问真实模型、embedding、MySQL、外网或真实 `.env`。

回滚只撤销八页、testing primitives、`useTestWorkflow` 内部派生能力、partial 文本展示、确认 helper、离线 fixture、契约和本文件的 Aspect 6 增量；不得使用 `git reset` 或覆盖式 checkout。
