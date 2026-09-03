# Iteration 3 Aspect 7：跨产品无障碍、响应式与性能硬化

## 1. 范围与目标

Aspect 7 只处理跨页面的 WCAG 2.2 AA、响应式、状态播报、内容术语和前端资产性能。它不改变 19 个 workflow、路由守卫、REST/SSE wire format、缓存键、artifact revision、持久化/session-only、取消、stale、失败回滚或 regeneration lock，也不开始 Aspect 8 的全状态集成验收、closeout 与发布准备。

没有新增 npm/pip、字体、图标、测试框架或 UI 依赖；`package.json` 与 `package-lock.json` 保持不变。生产后端、SQL、真实 `.env`、模型、embedding、MySQL 和外网不在本次执行范围内。

## 2. WCAG 2.2 AA 硬化矩阵

| 检查面 | Aspect 7 基线 | 实施与验证 |
|---|---|---|
| 键盘与焦点 | 组件 focus 规则分散，路由切换不统一聚焦 | 3px 实色森林绿 `focus-visible`、2px offset、forced-colors fallback；路由渲染后聚焦当前 `main`，移动抽屉 Escape/遮罩/关闭仍恢复导航按钮 |
| 焦点不被遮挡 | sticky header 可能遮住程序性焦点 | heading、ID 与可聚焦主内容统一设置 header 高度加间距的 `scroll-margin-top` |
| 名称、角色和值 | ModelSelector 默认 ID 可重复，部分 select/radio 关联为间接包装 | 组件实例 UID 生成唯一 ID；label、description、required 直接关联实际 segmented/select/radiogroup |
| 必填与错误识别 | 必填主要依赖可见标题 | 必填 fieldset 同时提供屏幕阅读器“必填”，既有结构化错误继续使用独立 `role="alert"` |
| 状态消息 | 大网格与细粒度 streaming 容易重复播报 | Stepper、LLM、菜单使用独立 atomic polite 摘要；reasoning/token delta 不逐条播报，错误仍独立 alert |
| 目标尺寸 | 桌面控件 40px，移动端部分控件不足 44px | 767px 以下按钮、菜单、表单、折叠、分段控件和 skip link 至少 44px；320px 实测无可见小目标 |
| 320px reflow | segmented 依赖内部横向滚动 | 480px 两列、320px 单列；工作区 `scrollWidth === clientWidth`，无关键裁切 |
| reduced motion | 多处局部降级 | 全局动画/过渡压缩至 `.01ms`、单次播放并关闭 smooth scrolling；skeleton 与运行态同样降级 |
| 对比度与非文本对比 | Aspect 1 tokens 已设语义色 | focus 使用 `#2F7D4A` 实色；状态继续以文字加颜色表达，forced-colors 使用 CanvasText |
| 文本间距与长内容 | 长技术标识可能撑宽 | 项目 ID、代码、qualified detail 安全换行；结果继续使用自然文档流和阅读宽度 |

`FeedbackState` 的 `content/form/cards` skeleton 保留真实 loading 文案，装饰骨架 `aria-hidden` 并预留稳定高度。它只用于只读未知布局，不用于上传、finalize 或模型 SSE，也不伪造进度。

## 3. 路由呈现与状态播报

`routePresentation.ts` 统一入口、创建、说明、计划、菜单和八类测试路径的页面名。每次路由完成后标题更新为“页面名 | EzllmTest”，并在 Vue 渲染完成后聚焦页面 `<main tabindex="-1">`。MainView 复用同一份标题字典，不复制 route metadata，不改变既有 `beforeEach` 守卫。

Stepper 只播报当前运行阶段或完成数量，仍保留原 props、六状态、可见文案、`data-state` 和 `aria-current="step"`。LLM 面板只在连接、运行、完成、缓存、取消以及 current/total 分块变化时更新 atomic 摘要；错误继续由 `role="alert"` 播报。TestMenu 不再给八卡网格整体添加 `aria-live`，只提供一次“共 8 类工作区”的分类汇总。

## 4. 响应式浏览器结果

所有数据来自只绑定 loopback 的离线 fixture 和合成 PID，不调用模型、embedding、MySQL 或生产服务。计划、菜单与八类测试路由在每个基准视口逐路由检查，共 50 组。

| 视口 | 结果 |
|---|---|
| 320×800 | 额外高倍率等效 reflow：根与 main 均 `305/305`，可见交互目标全部至少 44px，segmented 单列 |
| 360×800 | 十路由根宽度均相等；移动抽屉 inert/trap/body lock/Escape/焦点恢复通过；Stepper 与 segmented 无内部溢出 |
| 768×1024 | 十路由根宽度均相等；抽屉关闭后主内容占满平板宽度，Stepper 为 `720/720` |
| 1024×768 | 十路由根宽度均相等；272px 固定侧栏和 main 都位于视口内 |
| 1440×900 | 十路由根宽度均相等；内容宽度约 1073–1088px，无重复 ID |
| 1920×1080 | 十路由根宽度均相等；内容稳定限制为 1200px，Stepper 为 `1200/1200` |

每组同时验证：无重复 ID、路由标题正确、当前 main 获得焦点、可见 landmark 不越界。控制台为零 error/warning，原 Vue hydration mismatch feature-flag warning 已消失。页面首次只执行现有只读恢复，不自动调用 workflow SSE。

1280px 的自动化会话尝试发送浏览器 200% zoom 快捷键，但内嵌浏览器显式 viewport 模式不暴露页面缩放倍率，`visualViewport.scale` 仍为 1；因此本报告不把该动作冒充为 200% 实测。320 CSS px 的等效高倍率重排和所有断点已自动验证，真实浏览器 200% 缩放保留为 Aspect 8/人工验收项。

Windows Narrator 的音频输出无法由当前隔离浏览器自动化可靠采集，同时 Windows 自动化安全边界禁止操控承载该页面的 Codex 窗口。因此本次使用浏览器 accessibility tree 对页面切换、heading、label、required、status/alert/live region、当前路由与当前步骤做无安装烟雾验证；Narrator 的可听结果仍需人工复核，未伪报通过。

截图位于仓库外临时目录 `ezllmtest-aspect7-browser-20260823`：`aspect7-drawer-360.png`、`aspect7-plan-768.png`、`aspect7-unit-1024.png`、`aspect7-menu-1440.png`、`aspect7-unit-1920.png`，不会进入 Git。

## 5. Element Plus 与资产性能

生产入口不再导入完整 Element Plus runtime、完整图标集或 `element-plus/dist/index.css`。`plugins/elementPlus.ts` 直接注册实际使用的 21 个组件及各自 CSS、16 个 MainView 图标，并导出按需 `ElMessage`/`ElMessageBox`。测试页的 `Refresh`/`Right` 保持命名导入；未路由的 HelloWorld `ElImage` 不进入生产注册表。

原基线为 vendor JS 约 1.16 MiB、CSS 311 KiB、Logo 688,067 bytes。新 `ezlogo-workbench.png` 为 192×192 RGBA、81,689 bytes，原 Logo 保留。

| 指标 | Aspect 7 构建 | 门禁 |
|---|---:|---:|
| 最大初始 JS raw / gzip | 443,202 / 143,473 bytes | ≤900 KiB / ≤285 KiB |
| 初始 CSS raw / gzip | 111,092 / 19,519 bytes | ≤220 KiB / ≤34 KiB |
| index 初始资产 raw | 567,225 bytes | ≤1.20 MiB |
| 完整构建目录 | 1,580,460 bytes | ≤3 MiB |
| source map | 0 | 必须为 0 |

`scripts/check_frontend_bundle.py <dist>` 是零依赖门禁，校验 source map、Logo、初始 JS/CSS、index 引用资产和完整目录。`productionSourceMap: false` 与 Vue production hydration mismatch flag 在现有 webpack 配置中显式设置；没有通过抬高警告阈值掩盖 bundle warning。

## 6. 内容术语

- 用户文案统一使用“API 接口”“前端 UI”“项目 ID”。
- 用户不再看到 `cache-aware SSE` 或 `artifact` 术语，改为“按当前模型与输入查找并恢复已保存结果”。
- 八类最终结果标题使用“模型生成的……”。
- “模型推理 · 仅本次会话”、Token、缓存、保存、session-only、取消、失败和 stale 的精确语义保持不变。

## 7. 已知限制与 Aspect 8 边界

- 自动化已验证 320px 等效高倍率重排，但没有可验证的内嵌浏览器 200% zoom 控制；该项需人工复核。
- 自动化 accessibility tree 已覆盖语义与状态区域，但 Narrator 音频结果不能被当前工具可靠断言；该项需人工复核。
- Aspect 7 不做 Aspect 8 的跨全状态集成矩阵、closeout、发布准备或真实 provider 验证。
- 原字体和旧图片完整保留；未删除 starter 文件，也未修改 package manifests。

## 8. Aspect 8 人工项处置

Aspect 8 继续把真实 1280px/200% zoom 与 Windows Narrator 可听输出列为非阻塞人工复核项，没有把工具无法观测的结果虚报为通过。自动证据保持为 320 CSS px 等效高倍率重排、五个标准视口、DOM 语义快照、focus/heading/label/status/alert/live region 与零重复 ID。

收口浏览器矩阵另发现 Element Plus segmented 的选中装饰层会通过 inline `display:block` 覆盖窄屏规则，导致 360px 选中背景跨两行。该问题已在共享 `ModelSelector` 做最小修复，并由 Aspect 8 契约、production build 和 360px computed style/截图复验；其他 Aspect 7 规则未改写。
