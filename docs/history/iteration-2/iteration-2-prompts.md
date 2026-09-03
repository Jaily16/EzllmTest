# EzllmTest Iteration 2 New-Conversation Prompts

Use the following prompts in order. The first prompt transfers context through a read-only audit. Send the second prompt only after the first response is complete and accepted.

## First Prompt — Read-only takeover and Iteration 2 readiness report

```text
你现在接手 Windows 本地项目 D:\codex\EzllmTest_v2。GitHub main 已包含完成的 Iteration 1：Python 3.11/FastAPI 后端运行在 8130，Vue 3 前端运行在 8080，MySQL 数据库为 ezllmtest_dev；GLM、通义千问、DeepSeek、Moonshot Kimi 和智谱 embedding-3 已在此前经过用户明确付费授权的真实连通性验证。平台当前已经实现测试计划优先流程，以及测试计划和其他 18 个 LLM 工作流的进度、思考、流式正文、Token 用量、取消和延迟保存。

本轮只能进行只读接手，绝对不要开始 Iteration 2 开发。请依次静态检查：

1. git branch、git status、git diff --stat、origin/main 同步状态；
2. README.md、docs/iteration-1-closeout.md、docs/iteration-1-tasks.md、docs/iteration-development-log.md；
3. docs/iteration-2-tasks.md、docs/iteration-2-prompts.md；
4. 后端项目创建/上传/项目状态、测试计划 SSE、通用 workflow SSE、DAO/InfoType、文档加载、retriever、模型 registry/streaming；
5. 前端 CreateView、projectAnalysis 状态、路由守卫、MainView/TestPlan/TestMenu，以及八种测试页面和通用流式 composable/组件；
6. 当前测试目录、凭证扫描脚本、.gitignore 和示例环境变量文件。

请输出一份 Iteration 2 接手报告，说明：

- 当前项目从创建、上传、分析、测试计划/菜单到各测试类型的真实状态流；
- 当前 19 个流式工作流、缓存/数据库写入和前端恢复行为；
- Iteration 2 Task 0–9 的依赖关系、风险和建议执行顺序；
- 当前重复模型调用、重复 embedding、重复上下文和高思考 Token 的主要来源；
- Task 0 开始前必须保护的兼容接口、数据库行为和 Git 用户资产；
- 计划文档与当前代码是否存在不一致。

严格限制：

- 不修改、创建、删除、暂存、提交、拉取或推送任何文件；
- 不安装/升级依赖，不运行测试、构建、服务、数据库命令或迁移；
- 不访问模型/embedding API，不产生费用；
- 不读取或输出 .env、API Key、数据库密码，只能读取 .env.example 和变量名；
- 不输出原始 git diff，先用 status/diff --stat；疑似凭证只报告文件和风险类型并脱敏；
- 如果工作区存在未提交内容，一律视为用户资产，不覆盖、不回滚。

报告完成后立即停下，等待我的第二句提示词。
```

## Second Prompt — Execute Iteration 2 Task 0 only

```text
执行 docs/iteration-2-tasks.md 的 Task 0：建立 workflow catalog 和可量化的离线 Token/调用基线。本轮只允许执行 Task 0，不要提前实施 Task 1–9。

执行要求：

- 先重新核对 Task 0 的文件范围、现有 19 个工作流操作和当前 dirty worktree；
- 按测试先行：先增加会失败的 workflow catalog 完整性测试，再实现最小 catalog；
- 离线基线必须使用 mock chat、mock embedding 和固定小/大文档，记录每个工作流的模型调用数、embedding 构建数、输入上下文 Token 与输出上限；
- 基线报告不能保存 prompt 正文、业务文档、reasoning 内容或凭证；
- 不改变现有 dispatcher、REST/SSE、数据库或前端行为；
- 不访问真实模型、embedding、MySQL 或外部网络，不产生费用；
- 不读取或修改真实 .env，不安装/升级依赖；
- 完成后运行 Task 0 聚焦测试和必要的静态检查，更新 docs/iteration-2-tasks.md 的 Task 0 状态以及 docs/iteration-2-development-log.md；
- 不提交、不推送 Git；不要执行 Task 1。最后报告改动、测试结果、基线结论和下一步风险，然后停下等待我的下一句提示词。
```
