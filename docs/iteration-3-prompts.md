# EzllmTest Iteration 3 New-Conversation Prompts

Use these prompts in order. The first prompt performs a read-only takeover and creates the shared UX baseline. Send the second prompt only after reviewing and accepting the takeover report. The second prompt starts planning for Aspect 1; it does not authorize work on later aspects.

## First Prompt — Read-only takeover and frontend experience report

```text
你现在接手 Windows 本地项目 D:\codex\EzllmTest_v2。GitHub main 已包含完成的 Iteration 1 和 Iteration 2；当前数据库结构统一位于根目录 ezllmtest.sql，共七张空表。后端为 Python 3.11/FastAPI（8130），前端为 Vue 3/TypeScript/Element Plus（8080），数据库名为 ezllmtest_dev。

Iteration 2 已建立 19 个 workflow catalog、项目创建/上传恢复、统一生命周期和路由守卫、测试计划/菜单优先流程、revision-aware artifact、RAG 索引复用、上下文/输出/思考预算，以及八类测试页的共享步骤状态。所有 preliminary analysis 都会持久化；unit_case、integration_case、api_case、functional_case、nonfunctional_case 是当前页面 session-only 最终结果；ui_case、db_case、acceptance_case 仍持久化。现有 REST/SSE、缓存、取消、延迟保存和数据库行为必须保护。

本轮只能进行 Iteration 3 的只读接手，不要开始实现。请完整阅读：

1. README.md、docs/iteration-2-closeout.md、docs/iteration-2-development-log.md；
2. docs/iteration-3-overview.md、docs/iteration-3-prompts.md；
3. ez_front_dev/package.json、App.vue、router、config、state 和 composables；
4. LoginView、CreateView、MainView、TestPlan、TestMenu；
5. WorkflowStepper、LlmExecutionPanel、LlmWorkflowExecution，以及八种测试页面；
6. 前端相关契约测试、.gitignore、.env.example（只能读取变量名，不能读取真实 .env）。

先执行只读的 git branch、git status、git diff --stat 和本地 origin/main 对比；不要 fetch、pull、stage、commit 或 push。静态检查布局、内联/重复样式、字体与资源、响应式断点、信息架构、状态文案、键盘/可访问性、长文本展示、加载/失败/取消/恢复反馈和前端测试能力。

如果本地服务已经在运行，可以使用浏览器只读查看和截图现有页面，但不要启动服务，不要创建/上传/删除项目，不要点击生成、重新生成或任何可能触发模型/embedding/数据库写入的操作。

请输出 Iteration 3 前端体验接手报告，至少说明：

- 当前用户从登录/创建、上传、计划、菜单到八种测试页的真实交互路径；
- 当前全局布局、视觉语言、组件复用和响应式的主要问题及证据；
- 进度、reasoning、正文、Token、缓存、保存、session-only、取消、失败和 stale 状态是否表达清楚；
- docs/iteration-3-overview.md 八个方面的依赖顺序是否合理，是否与当前代码冲突；
- Aspect 1 详细规划前必须保护的接口、状态语义、用户资产和验收基线；
- 当前缺少哪些自动化或浏览器验证能力，以及不新增依赖时可采用的验证方案。

严格限制：不修改任何文件，不运行测试/构建/服务/数据库命令，不安装依赖，不访问外部网络或真实模型/embedding/MySQL，不读取或输出凭证，不输出原始 git diff。报告完成后立即停下，等待我的第二句提示词。
```
## Second Prompt — Plan Aspect 1 only

```text
基于刚才的只读接手报告，进入计划模式，只为 docs/iteration-3-overview.md 的 Aspect 1“体验基线与设计系统基础”制定详细实施计划。不要规划或实施 Aspect 2–8，也不要开始修改代码，先把计划交给我确认。

计划必须：

- 重新核对当前 dirty worktree，所有既有内容都视为用户资产；
- 明确 Aspect 1 的文件范围、非目标、依赖和可回滚边界；
- 先建立页面×状态×视口的基线矩阵，覆盖登录、创建、主框架、计划、菜单、代表性测试页和 LLM 执行面板；
- 给出明确的视觉方向：专业、克制、可信赖的 AI 测试工作台，保留绿色品牌识别但避免大面积浅绿背景；
- 规划 CSS/Element Plus design tokens、中文正文字体、品牌字体、颜色、间距、圆角、阴影、内容宽度、层级、focus、motion 和 reduced-motion；
- 选择一个低风险 pilot surface 验证 tokens 与 360/768/1024/1440/1920 响应式规则，不提前重做应用壳、创建流程、测试计划、菜单或八类测试页；
- 按测试先行设计静态/组件契约和浏览器截图验证；若建议新增测试、图标、字体或 UI 依赖，必须单独说明必要性、版本兼容和成本，未经我批准不得安装；
- 保护 Iteration 2 的路由守卫、19 个工作流、REST/SSE、缓存/持久化、session-only 结果、取消、stale 和重新生成锁定行为；
- 不访问真实模型、embedding、MySQL 或真实 .env，不产生费用；
- 计划中包含聚焦检查、npm run lint、npm run build、凭证/生成物检查和浏览器验收标准；
- 计划确认后也只能实施 Aspect 1，完成时更新或创建 docs/iteration-3-development-log.md，然后停下等待下一方面指令；不提交、不推送，除非我另行明确要求。

先输出计划和关键设计决策，等待我确认，不要直接编辑文件。
```
