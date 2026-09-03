# Iteration 3 设计系统基础（Aspect 1）

## 1. 视觉方向

EzllmTest 的方向是专业、克制、可信赖的 AI 测试工作台。绿色继续承担品牌、当前状态和关键动作，但普通页面以白色、中性灰表面和清晰边框为主，不得把大面积浅绿背景当作默认容器语言。

本基础只发布 `--ez-*` tokens、Element Plus 变量桥接、全局排版/可访问性规则和 `WorkflowStepper` pilot。页面采用和组件重构必须在对应 Aspect 中进行。

## 2. 颜色 tokens

| 类别 | Token | 值 | 用途 |
|---|---|---|---|
| 品牌 | `--ez-color-brand-50` | `#F1F7F3` | 当前/运行态浅表面 |
| 品牌 | `--ez-color-brand-100` | `#DCECE2` | 品牌弱边界 |
| 品牌 | `--ez-color-brand-300` | `#9FC6AB` | 品牌弱强调 |
| 品牌 | `--ez-color-brand-500` | `#2F7D4A` | 主色与关键动作 |
| 品牌 | `--ez-color-brand-600` | `#25673D` | hover/强调 |
| 品牌 | `--ez-color-brand-700` | `#1E5232` | dark-2/强强调 |
| 表面 | `--ez-color-canvas` | `#F5F7F6` | 页面画布 |
| 表面 | `--ez-color-surface` | `#FFFFFF` | 主表面 |
| 表面 | `--ez-color-surface-subtle` | `#F8FAF9` | 次级表面 |
| 文字 | `--ez-color-text-primary` | `#17211B` | 标题与正文主色 |
| 文字 | `--ez-color-text-secondary` | `#4B5B51` | 次级正文 |
| 文字 | `--ez-color-text-muted` | `#637369` | 辅助信息 |
| 边框 | `--ez-color-border` | `#D9E2DC` | 默认边框 |
| 边框 | `--ez-color-border-strong` | `#B9C8BE` | 强边框 |
| 语义 | `--ez-color-info` | `#2563EB` | ready/available |
| 语义 | `--ez-color-success` | `#237A45` | completed/saved |
| 语义 | `--ez-color-warning` | `#9A6700` | stale/需注意 |
| 语义 | `--ez-color-danger` | `#B42318` | failed/error |
| 语义 | `--ez-color-locked` | `#5F6F65` | locked/neutral |

语义底色分别为 info `#EFF6FF`、success `#ECF7F0`、warning `#FFF7E6`、danger `#FFF1F0`、locked `#F3F4F6`。契约测试直接计算这些文字/底色组合，普通字号对比度不得低于 4.5:1。

状态映射固定为：ready/available → info，running/current → brand，completed → success，stale → warning，failed → danger，locked → neutral。状态必须同时有可见文字，不得只依靠颜色。

## 3. 排版与字体

- 正文：`--ez-font-body` = `"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Helvetica Neue", Arial, sans-serif`。
- 品牌：`--ez-font-brand` = `"Quantify"` 加正文 fallback。
- 代码：Consolas、SFMono 和 Liberation Mono fallback。
- `Quantify` 与 `Gjhn` 使用 `font-display: swap`；`Gjhn` 仅兼容登录标语。
- `Ali` family 仅映射本地系统中文字体，不再下载 `AlimamaFangYuan.ttf`；仓库中的字体资产不删除。
- 字号阶梯：12/13/14/16/20/24/32px；正文默认 15px、行高 1.65。

业务正文必须使用系统中文栈；不得在页面内重新声明新的正文 `@font-face`，不得把品牌字体用于长文本。

## 4. 空间、形状和层级

| 组 | Tokens / 值 |
|---|---|
| 间距 | `--ez-space-1/2/3/4/6/8/10/12` = 4/8/12/16/24/32/40/48px |
| 圆角 | small 6px、medium 10px、large 14px、pill 999px |
| 阴影 | small `0 1px 2px rgba(23, 33, 27, .06)` |
| 阴影 | medium `0 8px 24px rgba(23, 33, 27, .08)` |
| 阴影 | large `0 16px 40px rgba(23, 33, 27, .12)` |
| 内容宽度 | compact 720px、default 960px、wide 1200px |
| 页面 gutter | 16px；768→24px；1024→32px；1440→40px；1920→48px |
| z-index | base 0、raised 10、sticky 100、overlay 2000 |

`.ez-page`、`.ez-content`、`.ez-content--compact`、`.ez-content--wide` 是迁移工具类；Aspect 1 不主动套用到旧页面，避免跨方面改变布局。

## 5. Focus、motion 与 reduced-motion

- `:focus-visible` 使用 3px `rgba(47, 125, 74, .36)` outline 和 2px offset；保留浏览器默认 focus 作为 fallback。
- motion 为 120/180/240ms，曲线 `cubic-bezier(.2, 0, 0, 1)`。
- `prefers-reduced-motion: reduce` 将动画和过渡缩短到 `.01ms`、限制单次播放，并关闭 smooth scrolling。
- running 只允许低强度状态提示；不得使用大范围闪烁、位移或无限旋转传达普通等待。

## 6. Element Plus 桥接

`element-plus-theme.css` 只在 `:root` 映射 CSS variables，不得写 `.el-button`、`.el-card` 或其他组件级选择器覆盖。

主色映射包括 `--el-color-primary`、light-3/5/7/8/9 与 dark-2，避免 Element Plus 派生色残留默认蓝色。桥接还覆盖 success、warning、danger/error、info，页面/浮层/填充表面，主次文字、边框、font family/base size、圆角和三档 shadow。

导入顺序固定为：Element Plus 原始 CSS → `tokens.css` → `element-plus-theme.css` → `base.css`。后续组件优先消费 `--ez-*`；只有 Element Plus 内部变量才消费 `--el-*`。

## 7. WorkflowStepper pilot 规则

- 公共 props 仍为 `steps` 与 `activeOperation`；六状态、步骤顺序和中文状态文案保持不变。
- 每个 `<li>` 暴露 `data-state`；当前操作暴露 `aria-current="step"`。
- grid 使用 `repeat(auto-fit, minmax(min(100%, 180px), 1fr))`。
- 卡片必须 `min-width: 0`、允许长文本换行，并在极窄容器中降为单列；pilot 自身不得制造横向滚动。
- 数字序号是装饰，状态由文字和语义色共同表达。
- pilot 不得增加按钮、点击事件、路由行为或业务状态。

## 8. 依赖、边界与回滚

Aspect 1 不新增 npm/pip、字体、图标、测试框架或 UI 依赖；`package.json` 与 `package-lock.json` 必须保持不变。

不得改变路由守卫、19 个 workflow、REST/SSE 字段、缓存与延迟保存、持久化/session-only 边界、取消、stale、失败回滚和 regeneration lock。离线 fixture 不是生产 API，不得被应用或后端导入，仅绑定 `127.0.0.1`。

回滚边界是三份样式导入、`App.vue`/HTML/Stepper 的局部改动及 Aspect 1 新文件；不涉及数据库、用户项目、字体/图片、现有 `dist` 或 `node_modules`，不得使用 `git reset` 或覆盖式 checkout。

## 9. Aspect 2 应用壳采用规则

Aspect 2 发布三项壳层尺寸 tokens：

| Token | 值 | 用途 |
|---|---|---|
| `--ez-shell-header-height` | `64px` | sticky header 与桌面可视高度计算 |
| `--ez-shell-sidebar-width` | `272px` | `>=1024px` 固定项目导航 |
| `--ez-shell-drawer-width` | `320px` | `<1024px` 覆盖式抽屉上限 |

应用壳以白色 header/aside、中性画布和细边框为主；品牌绿只用于当前项、关键状态和焦点。内容容器消费 `--ez-content-wide`，在可用空间达到上限时保持 1200px 并居中。

断点唯一值为 1024px：低于它使用 `min(320px, calc(100vw - 48px))` 抽屉，高于或等于它使用 272px 侧栏。页面 gutter 继续消费 Aspect 1 的 16/24/32/40/48px tokens，不在页面内复制新尺寸。

壳层可以提供 `min-width: 0`、`max-width: 100%` 和页面级防溢出护栏，但不得借此重做测试计划、菜单、测试页或 LLM 面板。窄屏 segmented 可在自身内部滚动，不能把页面根宽度撑大。后续页面采用必须保留 `header/aside/nav/main`、skip-link、`inert`、焦点恢复和 reduced-motion 契约。

## 10. Aspect 3 共享交互采用规则

Aspect 3 增加 `--ez-control-height: 40px` 和 `--ez-reading-measure: 72ch`。前者统一操作控件最低高度，后者限制说明文字的阅读宽度；二者不改变 Element Plus 的全局组件默认值。

页面信息层级优先采用 `WorkspacePageHeader`、`WorkspaceSection`、`ModelSelector`、`WorkflowActionBar`、`FeedbackState` 和 `ResultContainer`。这些组件只负责布局、语义和状态表达，不拥有路由、生成、保存、缓存或重试行为。页面必须继续显式传入禁用条件和点击处理器。

`LlmExecutionPanel` 固定按状态/模型、progress、缓存与保留边界、默认折叠 reasoning、Token、终态说明的顺序展示。reasoning 统一标记“仅本次会话”，不得复制进 result 或浏览器持久化。artifact 显示“已保存”，session-only 显示“仅当前页面保留”，取消和失败显示“本次未保存”。

局部 scoped 样式可以为共享组件调整 Element Plus 子控件的排列，但 `element-plus-theme.css` 仍只允许 `:root` 变量映射；禁止新增全局 `.el-*` 覆盖。共享组件不得引入原始色值、固定页面宽度或新的字体资源。

## 11. Aspect 4 Onboarding 采用规则

入口与创建页使用 `OnboardingShell`，以中性 canvas、白色 surface、细边框和小面积森林绿强调替代旧全屏浅绿渐变。普通入口最大宽度为 1040px，创建流程外层消费 `--ez-content-wide`，实际表单列消费 `--ez-content-default`；页面 gutter 继续沿用五档全局 tokens。

`ProjectIdDisplay` 是项目恢复凭证的唯一共享表达：必须完整显示 ID、提供复制反馈和安全保存说明。同页存在多个实例时必须传入不同 `titleId`，避免重复 heading ID。

`DocumentUploadGroup` 只管理受控文件列表和状态呈现。服务端文件、当前待上传文件、进度和失败必须分层显示；completed 组不渲染 file input，防止误操作。组件不得拥有注册、上传、finalize、重试或路由判断。

Onboarding 页面可复用 `FeedbackState` 与 `WorkflowActionBar`，但不得使用 `WorkspacePageHeader`，因为入口页没有应用壳提供的 `<h1>`。所有创建和上传写入都必须由有明确名称的按钮及确认摘要触发；页面加载、恢复和登录不得启动模型分析。

## 12. Aspect 5 测试计划与测试菜单采用规则

测试计划与测试菜单优先采用 Aspect 3 的页面头、section、反馈和结果容器。只读恢复、已保存版本与本次未保存草稿必须分层；长正文使用 `white-space: pre-wrap` 的自然文档流，不使用只读 textarea 或固定高度内部滚动区。

`TestWorkspaceCard` 是八类测试入口的规划领域组件。卡片状态按 regenerating、not-recommended、stale、locked、available 的优先级派生，状态必须同时提供可见文字和原因。主状态“可进入”与辅助进度“已有可恢复结果”不得混用，session-only 类型不得推断服务器保存状态。

卡片网格采用 `repeat(auto-fit, minmax(min(100%, 260px), 1fr))`，图片以 64–88px 呈现。v2 插图统一为 256×256 透明 PNG、强几何轮廓、森林绿/炭黑/中性灰主色和少量蓝/琥珀；无文字、水印或背景场景，作为装饰使用空 alt。旧图片保留但不再用于规划工作台。

## 13. Aspect 6 八类测试工作区采用规则

八类测试页使用 `TestWorkspaceScaffold` 组织页面头、WorkflowStepper 和 hydration 反馈；真实 operation 仍由页面使用 `WorkspaceSection` 顺序表达。共享 testing primitives 只拥有语义、布局和受控输入，不代理 workflow dispatch、payload、保存、取消或路由。

阶段顺序固定为 stale/恢复提示、业务选择、模型、操作、执行反馈和本阶段结果。已在当前标签页显示的结果不得通过“继续”按钮重复请求；服务器 fresh persisted 完成但本页无正文时，才显示显式 cache-aware 恢复。stale 且无正文时只允许重新生成。

`TestTargetSelector` 使用完整字符串作为 value；qualified reference 只改变可见标签。目标 select 不设置固定像素宽度，radio group 允许换行，长文本使用 `TestResultText` 自然展开。五类 session-only final 清空前确认；三类 persistent final 只允许本地隐藏和重新显示，不发网络或删除请求。

## 14. Aspect 7 跨产品硬化采用规则

全局样式顺序固定为按需 Element Plus 组件 CSS，再依次加载 `tokens.css → element-plus-theme.css → base.css → accessibility.css`。`accessibility.css` 是 focus、forced-colors、移动端触控目标、scroll margin、320px reflow 与 reduced-motion 的唯一横向规则入口；业务组件不得再次定义另一套全局 focus ring。

焦点使用 `--ez-focus-color: #2F7D4A` 的 3px 实线与 `--ez-focus-offset`；767px 以下关键交互目标消费 `--ez-touch-target: 44px`，桌面控件继续消费 `--ez-control-height: 40px`。模型分段选择在 480px 以下两列、320px 单列，不再通过横向滚动完成重排。技术标识、qualified detail 和项目 ID 必须安全换行。

只读未知布局可使用 `FeedbackState` 的 `content/form/cards` skeleton；骨架必须装饰性隐藏、保留真实 loading 文案和稳定高度。上传、finalize、模型 SSE 和任何已知进度禁止使用 skeleton。reduced-motion 下骨架、抽屉、Stepper 和运行态动画都必须降级。

页面标题必须来自 `routePresentation.ts`，形式为“页面名 | EzllmTest”；路由渲染后聚焦当前 `main`。状态播报使用独立、简短、atomic polite summary，不能把整个卡片网格、reasoning 流或 token 增量设为 live region；错误仍使用独立 alert。

生产 Element Plus 采用 `plugins/elementPlus.ts` 白名单注册。新增组件或图标前必须先证明生产路由真实使用，并同步组件 CSS、静态契约与 bundle 门禁；运行时 message/message-box 只从内部模块导入。新初始资源必须继续满足 `check_frontend_bundle.py` 的 raw/gzip 和完整目录预算。
