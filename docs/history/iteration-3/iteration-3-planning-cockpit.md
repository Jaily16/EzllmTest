# Iteration 3 Aspect 5：测试计划与测试菜单工作台

## 1. 范围与边界

Aspect 5 只重构 `TestPlan`、`TestMenu`、规划领域 registry/卡片和离线浏览器夹具，不修改 router、MainView、onboarding、共享 LLM 组件、八类测试页或生产后端。Aspect 6–8 不在本次范围内。

页面继续保护 19 个 workflow、既有 REST/SSE wire format、缓存、artifact revision、延迟保存、session-only、取消、stale、失败回滚和 regeneration lock。页面加载不会自动调用模型；只有“生成并保存”或确认后的“重新生成”才可 POST 现有计划 SSE。

## 2. 测试计划只读恢复

计划页先并发调用三个既有只读接口：`/project/info/{pid}/1`、`/22`、`/23`。摘要与计划必须是非空字符串；菜单可为 JSON 字符串或对象，但必须包含九个 boolean 字段。请求可由 `AbortSignal` 取消，读取失败只显示可恢复错误，不回退到模型请求。

状态分层如下：

- `analysis_required` 且没有旧 bundle：显示空状态、模型选择和显式生成入口。
- 已保存 bundle：分别显示“业务文档的初步分析与总结”“建议测试计划”“推荐测试类型”。
- `project_analysis` stale：继续只读展示上一版，三个结果均标记“已过期”，资料版本缺失时显示“未提供版本标识”。
- 重新生成：上一版始终留在“当前已保存版本”；新流的 summary/answer 放在“本次未保存草稿”。
- 只有 completed、`saved=true`、`ready=true`、正文与九字段菜单完整时，草稿才提升为当前已保存版本。
- 取消、失败或不完整完成：保留旧版和已收到草稿；`finally` 恢复 regeneration lock。

重新生成确认明确说明菜单与八类工作区临时锁定、成功替换、失败/取消保留旧版，以及下游 stale 只服从服务器状态，前端不推断。

## 3. 测试菜单信息架构

菜单始终从 `TEST_WORKSPACES` 渲染全部八类测试，不再把测试计划作为第九张卡片；页头提供返回计划入口。每张 `TestWorkspaceCard` 是独立 `article`，包含标题、英文名、装饰插图、可见状态、原因、下一步和单一非嵌套链接。

状态优先级固定为：

1. `regenerating` → 分析中；
2. menu=false → 未推荐；
3. operation family stale → 已过期；
4. route 不允许 → 已锁定；
5. 其他 → 可进入。

“可进入”描述生命周期权限，不表示整个测试工作区已完成。`completed_operations` 只可补充“已有可恢复结果”；五类 session-only case 不推断持久化结果。未推荐类型仍展示，并说明需要重新生成、确认计划后才可能开放。

## 4. 卡片、插图和响应式规则

卡片网格使用 `repeat(auto-fit, minmax(min(100%, 260px), 1fr))`。360px 为单列，768/1024 通常为双列，1440/1920 自动形成三至四列；卡片和长文本均 `min-width: 0`、安全换行，不制造页面级横向滚动。

八张插图由内置 `image_gen` 分别生成，以单元测试图为风格锚点。最终资源为 256×256 透明 PNG，统一使用深森林绿、炭黑、中性灰和少量蓝/琥珀；无文字、数字、品牌、商标、水印、UI 截图或背景场景。页面以 64–88px 展示，`alt=""`，标题承担可访问名称。旧测试图片保留但不再引用。

## 5. 页面 × 状态 × 视口验收矩阵

| 视口 | 测试计划重点 | 测试菜单重点 | Aspect 5 验收 |
|---|---|---|---|
| 360×800 | analysis-required 空状态、模型选择、显式生成与失败反馈 | 八卡单列、状态和原因换行 | document 宽度不溢出，按钮和 focus 可见 |
| 768×1024 | 只读恢复、自然长文本、retryable 失败与草稿 | 双列或自适应列 | 页面加载网络记录无计划 SSE |
| 1024×768 | 重新生成确认、旧版持续可读、取消后解锁 | 固定应用壳内卡片不扩张 main | 取消/失败不清空旧 bundle |
| 1440×900 | 保存版本和草稿层级 | mixed menu：六类可进入、两类未推荐 | 全部八卡存在，状态不只依赖颜色 |
| 1920×1080 | stale 旧版、资料版本辅助信息 | stale/已有结果辅助文案、三至四列 | 内容宽度受壳层约束且居中 |

全部视口还需验证 Tab/Enter、确认框 focus、返回链接、长文本选择、控制台无新增 error/warning，以及插图在约 80px 下可区分且不裁切。浏览器只使用 loopback 离线数据，截图保存在仓库外。

## 6. 离线夹具与安全

离线夹具新增三个 21 位固定 PID：mixed menu、首次 retryable 计划失败、project analysis stale 但旧 bundle 可恢复。规划状态只存在于进程内；只有完整 `completed` 送达后才更新合成 bundle。`--plan-delay-ms` 限制在 0–10000ms，仅用于取消验证。

夹具继续只绑定 `127.0.0.1`，不落盘、不导入生产后端、不读取真实 `.env`，也不访问模型、embedding、MySQL 或外网。前端 bundle 恢复只执行 GET；页面加载不得隐式访问计划 SSE。

## 7. 回滚与后续

回滚只撤销 Aspect 5 对计划页、菜单页、planning registry/卡片、fixture 和两份追加文档的增量，并删除八张 v2 插图和本契约测试。旧图片始终保留，不使用 `git reset` 或覆盖式 checkout，不涉及数据库或用户项目资产。

TestPlan/TestMenu 完成本方面采用后停止。八类测试页的批量迁移、内容结果呈现和后续体验改造属于 Aspect 6–8，必须等待单独指令。
