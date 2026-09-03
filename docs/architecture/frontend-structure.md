# 前端、测试、资产与文档结构迁移

本文档是 Iteration 5 Aspect 5 的结构映射与审计记录。它描述路径职责，不改变 REST/SSE/MCP、路由、工作流、Agent 状态、预算、持久化或部署契约。

## 前端职责

Vite 根入口仍保留在 `ez_front_dev/src/App.vue`、`ez_front_dev/src/main.ts`、`ez_front_dev/index.html` 和类型声明文件。原有平面目录的 active 文件迁入以下 canonical 层：

- `src/app/router`：路由表和 lazy import。
- `src/features/onboarding`：登录、创建项目、上传文档和项目初始化。
- `src/features/planning`：计划与测试菜单。
- `src/features/testing`：八类测试页面、测试工作区组件、workflow composable、测试图片。
- `src/features/agent`：Agent 工作台、事件解析和工作台状态。
- `src/features/workspace`：主工作区及流程步进器。
- `src/features/about`：About 页面。
- `src/features/legacy`：仍需保留但不属于 active 业务路径的 legacy 示例。
- `src/shared`：跨 feature 复用的组件、composable、配置、插件、样式和 UI 辅助。

`src/views/HomeView.vue` 仍保留在原位，直到仓库内外引用、动态加载和历史证据均可证明其可迁移；它不是本批次的删除对象。

## 路由与懒加载映射

路由 URL、meta、workflow operation 和页面加载策略保持原值：

| URL | canonical page | 备注 |
|---|---|---|
| `/` | workspace `MainView.vue` | 根入口不隐式触发付费调用 |
| `/about` | about `AboutView.vue` | lazy load |
| `/create` | onboarding `CreateView.vue` | lazy load |
| `/menu` | planning `TestMenu.vue` | lazy load |
| `/plan` | planning `TestPlan.vue` | lazy load |
| `/unit`, `/integration`, `/api`, `/ui` | testing 对应页面 | workflow operation 不变 |
| `/database`, `/functional`, `/nfunctional`, `/acceptance` | testing 对应页面 | `FunctionalTest.vue` 为规范拼写 |
| `/agent` | agent `AgentWorkbench.vue` | approval/cancel/recover 行为不变 |

旧 `FounctionalTest.vue` 已由 `FunctionalTest.vue` 取代；active source、router、测试和文档运行入口不得继续引用旧拼写。未能解析的外部消费者必须保留并报告。

## 测试与 fixture 映射

测试物理分层不改变收集范围：

- `ez_back_dev/tests/contract/frontend`：前端静态和页面契约。
- `ez_back_dev/tests/contract/backend`：公共后端契约。
- `ez_back_dev/tests/contract/iteration5`：Iteration 5 当前控制契约。
- `ez_back_dev/tests/unit`：当前单元行为。
- `ez_back_dev/tests/integration`：跨服务和 workflow 行为。
- `ez_back_dev/tests/acceptance`：Agent 离线验收和质量入口。
- `ez_back_dev/tests/historical/iteration3`、`historical/iteration4`：历史 evidence 测试，继续参与 pytest。
- `ez_back_dev/tests/support`：仓库路径和 fixture 解析辅助，不改变 fixture 生命周期。

fixture 迁移规则为 `fixtures/current/{agent,rag,iteration5}` 与 `fixtures/historical/{iteration3,iteration4}`。历史 fixture 的 raw bytes、父链和 hash 不变；旧 Aspect 1–4 evidence fixture 不被重生成。

## 活动与历史资产

活动资产使用 canonical 路径：

- `src/shared/assets/brand/ezlogo-workbench-v2.png`：主工作区和 onboarding。
- `src/features/testing/assets/illustrations/test-types-v2/*.png`：八类测试工作区。
- `src/shared/assets/fonts/Quantify.ttf`、`GjhnGZcrG5SS.woff`、`GjhnGZcrG5SS.woff2`：样式引用。
- `public/favicon.png`：HTML favicon，保持原位。

旧 logo 和未使用字体因历史文档/回滚证据仍保留。旧九张测试图片经过静态引用、活动 registry 和隔离 Vite bundle 审计后，从源目录移入任务专用外部 quarantine；`removed_paths` 仅登记这九个精确路径，保留可恢复副本。任何新的资产删除都必须先有相同级别的引用证据和人工审查。

## 文档路径映射

| 原路径族 | canonical 路径 |
|---|---|
| `docs/iteration-1-*.md` | `docs/history/iteration-1/` |
| `docs/iteration-2-*.md` | `docs/history/iteration-2/` |
| `docs/iteration-3-*.md` | `docs/history/iteration-3/` |
| `docs/iteration-4-*.md` | `docs/history/iteration-4/` |
| `docs/iteration-5-overview.md` 等六份当前资料 | `docs/development/iteration-5/` |
| `docs/iteration-development-log.md` | `docs/history/iteration-development-log.md` |
| `docs/long-text-strategy-audit.md` | `docs/architecture/long-text-strategy-audit.md` |

历史文档正文只存在于 canonical 路径。每个移动前根路径保留一个不含正文的 Markdown redirect stub，写明原路径、canonical target 和本文件映射链接。stub 不复制历史正文，也不改变历史正文中的相对链接。

## 保护项、未知项与删除记录

以下内容在本 Aspect 保持不变：Aspect 1–4 baseline/migration fixture、Iteration 3/4 fixture、release evidence、prompt 正文、SQL、版本/依赖契约、后端生产逻辑、公共路由和 wire schema、用户数据、`.env`、数据库/Redis/观测数据及普通 volume。

当前 `removed_paths` 仅为：

```text
ez_front_dev/src/assets/static/image/acceptanceTest.png
ez_front_dev/src/assets/static/image/apiTest.png
ez_front_dev/src/assets/static/image/databaseTest.png
ez_front_dev/src/assets/static/image/functionalTest.png
ez_front_dev/src/assets/static/image/integrationTest.png
ez_front_dev/src/assets/static/image/nonfunctionalTest.png
ez_front_dev/src/assets/static/image/testPlan.png
ez_front_dev/src/assets/static/image/UITest.png
ez_front_dev/src/assets/static/image/unitTest.png
```

这些文件未被覆盖，精确副本位于任务专用外部 quarantine，并在 Aspect 5 migration fixture 中登记。旧 logo、旧字体、`HomeView.vue`、`HelloWorld.vue` 和任何无法证明无引用的对象继续保留。外部消费者、未知动态加载和路径越界均按 Unknown 处理，不以清理数量为目标。

## 回滚约束

回滚只使用任务专用 backup/quarantine 中的精确对象，并且仅当工作区当前 hash 仍等于对应批次 post hash 时执行。用户在执行期间修改的路径不得覆盖；新增 stub、fixture 或目录文件只有在路径和 post hash 同时匹配本批次生成物时才允许移除。禁止使用 Git destructive command、广泛 glob 或仓库根递归删除。
