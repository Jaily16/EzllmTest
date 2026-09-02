# Iteration 3 应用壳与信息架构（Aspect 2）

## 1. 范围与保护边界

Aspect 2 只重构持久化项目工作区壳层。它不改变登录、创建、测试计划、测试菜单、八类测试页或 LLM 执行面板的业务 DOM，不开始 Aspect 3–8，也不修改 router、`projectAnalysis` state、REST/SSE、缓存、artifact、持久化/session-only、取消、stale、失败回滚或 regeneration lock。

应用初始化仍只有两项读取：项目登录信息与 `loadProjectWorkflowStatus`。壳层不发起模型、embedding 或数据库写入请求。十条 workflow 路由与 `isWorkflowRouteAllowed` 禁用条件保持 Iteration 2 契约。

## 2. 信息架构

页面采用一份导航 DOM，并固定为以下语义层级：

1. “跳到主要内容”链接；
2. 64px sticky header：品牌、当前路由标题、项目名称与生命周期状态；
3. `aside#workspace-navigation` 项目导航；
4. `main#workspace-main` 与最大 1200px 的居中内容容器。

导航分组顺序固定为：

1. 业务分析与测试规划：测试计划、测试菜单；
2. 八种测试工作区；
3. 平台说明；
4. 创建新项目、返回开始界面。

完整项目名称、21 位 PID、已完成数与 stale 数放在项目摘要卡中。header 的路由标题由 `MainView.vue` 本地只读 path-label map 派生，没有添加 route metadata。

## 3. 状态来源与显示语义

导航只消费既有 `workflowStatusLoaded`、`projectAnalysisRegenerating`、`projectWorkflowStatus`、`completedOperations`、`staleOperations`、`route.path` 与 `isWorkflowRouteAllowed`。

| 内部状态 | 可见文案 | 语义 |
|---|---|---|
| `loading` | 加载中 | workflow status 尚未返回，不误报已锁定 |
| `completed` | 已完成 | 规划类 artifact 已完成 |
| `current` | 当前 | 当前路由，同时暴露 `aria-current="page"` |
| `locked` | 已锁定 | 既有路由守卫不允许进入 |
| `stale` | 已过期 | 当前 revision 已使相关结果过期 |
| `available` | 可进入 | 已解锁测试页；即使已有保存结果仍保持 Iteration 2 语义 |
| `regenerating` | 分析中 | 下游在测试计划重新生成期间临时锁定 |

所有状态同时使用文字、颜色与当前项左侧指示，不只依赖颜色。测试计划自身在 regeneration 期间仍为当前可见页面；菜单与八种测试类型继续禁用。

## 4. 响应式规则

- `<1024px`：左侧覆盖式抽屉，宽度 `min(320px, calc(100vw - 48px))`，正文使用完整视口宽度。
- `>=1024px`：272px 固定侧栏，移动导航按钮隐藏。
- gutter：360 使用 16px；768 使用 24px；1024/1440/1920 分别使用 32/40/48px。
- header、aside、main、菜单文本和 PID 均设置 `min-width: 0`、省略或安全换行。
- `router-view` 外层限制为 1200px 并居中；旧 `el-row`、`el-col`、card、select、segmented 只能在内容层内收缩。segmented 在空间不足时内部横向滚动，不扩大页面根宽度。

应用壳使用 `overflow-x: clip` 作为页面级护栏，但不把旧页面的固定宽度问题宣称为已完成；页面内部布局仍由对应后续 Aspect 处理。

## 5. 键盘、焦点与 motion

- 导航按钮提供 `aria-expanded` 与 `aria-controls="workspace-navigation"`。
- 隐藏抽屉同时设置 `inert` 与 `aria-hidden`，不可通过 Tab 进入。
- 打开后锁定 body 滚动，并把初始焦点放到关闭按钮。
- Tab/Shift+Tab 在关闭按钮和可进入菜单项之间循环；锁定项不进入循环。
- Escape、遮罩和关闭按钮关闭抽屉，并把焦点还给导航按钮。
- 选择路由后关闭抽屉并聚焦 `main`，不改变原 tab 顺序。
- resize 到 1024px 自动清理抽屉与 body lock。
- `prefers-reduced-motion: reduce` 关闭抽屉位移、skip-link 和壳层按钮 transition。

## 6. 五视口浏览器矩阵

浏览器只连接 `127.0.0.1:18080` 与标准库离线夹具 `127.0.0.1:18130 --status-delay-ms 1200`。三组固定 PID 分别覆盖 analysis required、ready 与 stale；没有访问真实后端、模型、embedding、MySQL 或真实 `.env`。

| 视口 | 状态与操作 | DOM/布局结果 | 截图 |
|---|---|---|---|
| 360×800 | analysis required；抽屉关闭/打开；Shift+Tab；Escape | 根宽 `360/360`；抽屉 312px；打开后焦点在关闭按钮、body lock=true；Shift+Tab 到“返回开始界面”；Escape 后焦点回导航按钮，隐藏 aside 为 inert | `shell-mobile-loading-closed-360.png`、`shell-mobile-locked-open-360.png` |
| 768×1024 | ready；打开抽屉并选择测试菜单 | 根宽 `768/768`；抽屉 320px；路由切换后 aside hidden+inert、body 解锁、`main` 获得焦点 | `shell-tablet-ready-open-768.png` |
| 1024×768 | ready/current | 272px 固定侧栏从 x=0 到 272；移动按钮 `display:none`；main 从 x=272 开始；根宽 `1009/1009` | `shell-desktop-ready-1024.png` |
| 1440×900 | 测试计划 regeneration lock | 根宽 `1440/1440`；header 显示“测试计划重新生成中”；菜单与八类测试项均显示“分析中”并禁用 | `shell-desktop-regenerating-1440.png` |
| 1920×1080 | stale/current | 根宽 `1905/1905`；内容宽度精确 1200px 并在 main 中居中；单元/UI 显示“已过期”，其余测试页“可进入” | `shell-desktop-stale-1920.png` |

五个视口均满足 `documentElement.scrollWidth === clientWidth`，header、aside、main 位于可见边界。浏览器控制台零 error；仅出现 Aspect 1 已记录的 Vue feature-flag warning，没有新增 warning。截图是任务临时产物，不进入 Git。

## 7. 已知遗留与回滚

- 登录页在 360px 的旧固定宽度仍会产生自身溢出；它属于后续登录/入口体验 Aspect，不由本应用壳改写。
- 测试计划、菜单卡片及八类测试页的内联样式、固定宽度、局部长文本和移动重排仍属于 Aspect 3–8。
- 旧 segmented 在窄屏改为组件内部可滚动，选项不会扩大页面根宽度；其完整移动交互设计不在 Aspect 2。
- 没有新增依赖、路由 metadata、业务状态、自动请求或第二份导航 DOM。

回滚只撤销 `MainView.vue`、三项 shell tokens、夹具延迟参数及 Aspect 2 文档/契约增量。不得使用 `git reset` 或覆盖式 checkout，不涉及数据库、用户项目、`node_modules`、现有 `dist` 或 Aspect 1 历史基线。
