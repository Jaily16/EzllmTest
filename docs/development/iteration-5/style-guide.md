# Iteration 5 Aspect 3 工程规范

本文是当前活跃代码的工程规范。可执行 manifest、lock 和跨工具链版本契约仍是版本真源；本文件只说明规则和门禁，不复制精确依赖版本。

## 适用范围

Aspect 3 使用显式 baseline 路径清单。清单之外的文件不会因为一次格式化命令被递归改写。历史 Iteration 文档、release/baseline fixture、`HelloWorld.vue`、`FounctionalTest.vue`、legacy service、二进制资产、上传项目、真实环境文件和本地生成物均不属于批量格式化范围。

新增或修改的活跃文件必须在 review 中加入 scope，并通过相同的只读契约和门禁。无法证明只发生格式变化的文件进入人工审查，不通过扩大忽略范围解决。

## Python

Python 3.11 代码使用锁定的 Ruff formatter/linter。formatter 负责缩进、换行、引号、尾逗号和最终换行；import 排序单独审查。初始 lint 只覆盖 `E4`、`E7`、`E9`、`F` 和 `I`，不以一次治理引入行为风险较高的规则集。

标识符、公共 JSON 字段、CLI 参数、日志 event 和协议名称保持英文。既有 camelCase 文件、legacy 名称和公共兼容符号不因风格治理自动重命名。

## TypeScript、Vue、配置和文档

TypeScript/Vue 使用已有 ESLint 与 `vue-tsc` 进行语义检查，Prettier 负责格式。JSON、YAML、CSS 和 Markdown 使用同一套 Prettier 选项。Vue router 的懒加载、模板资源路径、CSS class、环境变量名和 SSE event key 属于人工审查面。

配置、manifest、Compose、Actions 和文档必须使用 UTF-8、LF 和最终换行。`.gitattributes` 不触发全仓库 renormalize；历史混合换行文件只有在明确批次和 diff 审查后才能处理。

## 中文说明尺度

中文 docstring/comment 只解释维护者不容易从代码直接推断的约束：REST/SSE/MCP 公共契约、数据模型、revision/artifact/cache/RAG 绑定、Token/context budget、stale/cancel/delayed-save/rollback/regeneration lock、approval/lease/idempotency/recovery、严格 JSON checkpoint、telemetry 脱敏以及 MySQL/Redis 职责。

说明优先回答“为什么、边界是什么、失败会怎样”。显然的赋值、getter、逐行翻译和 prompt/用户正文不添加注释；不在注释中写密钥、密码、真实项目资料、provider 值或易变版本。

## 本地门禁

在仓库根目录运行：

```text
python scripts/check_style_contract.py --check --format text
python -m ruff check <baseline 中明确的 Python 文件>
python -m ruff format --check <baseline 中明确的 Python 文件>
```

在 `ez_front_dev` 目录运行：

```text
npm ci --ignore-scripts --no-audit --no-fund
npm run format:check
npm run lint -- --no-fix
npm run type-check
npm run build
```

`format` 只允许在人工审查 dry-run 后显式执行；CI 只执行 check，不写回工作区，不自动接受当前值，也不自动提交。

## 保护边界

任何规范调整都必须保持 19 个 workflow、22 个工具、legacy/Agent REST/SSE/MCP、revision-aware artifact/cache/RAG、预算、审批、checkpoint、租约、幂等、恢复、MySQL/Redis 职责和两种当前启动方式不变。页面加载不得新增隐式付费调用。历史 evidence、用户文件、真实 `.env`、数据库/Redis/观测数据和普通 Compose volume 不读取、不格式化、不移动。
