# EzllmTest

本地软件测试工作台：从项目资料准备、业务分析和测试计划，进入八类测试分析与用例生成。现有确定性工作流与受控单 Agent 共用项目、模型选择、审批、预算和结果保存边界。

> Iteration 7 以 e6c42a5f20a9a0003dc553cece16fd72a9f6aece 为基点。方面一至五已按各自范围完成；方面六本地收口完成，本提交用于普通快进发布。发布结果以交付时的引用核验为准。

## 主要能力

- 19 workflows、22 个类型化 Agent tools，保留 REST/SSE/MCP 协议。
- 项目资料与 revision 恢复、索引复用、缓存及八类测试工作区。
- 显式生成、审批和取消；失败或截断不覆盖有效结果。
- 独立 Python API/worker、Vue 前端和本地脱敏观测。

## 目录

| 目录 | 职责 |
| --- | --- |
| backend | Python 产品包、后端依赖和实际测试 |
| frontend | Vue 产品、前端配置工具和实际测试 |
| observability | 观测配置、简明说明和受保护数据 |
| infrastructure | 数据库结构与当前运行声明 |
| ops | 可选启动、状态及安全停机工具 |
| docs | 迭代历史、验证历史、项目设计三份文档 |

## 启动入口

在 D:\codex\EzllmTest_v6 使用已安装产品 Python 和 npm，显式选择原地三个配置文件。主方式是独立终端依次启动观测 API、产品 API、Agent API、不消费 worker 和前端；完整命令、角色矩阵及 Uvicorn/MCP 说明见[分终端启动](docs/project-design.md#startup)。

安全连接验收使用 worker --no-consume；它不会处理队列，也不注册正常 worker，因此没有普通 worker 时 Agent /ready=503 属于预期。正常消费可能立即执行已有任务，应明确允许后另行启动；[可选 runner](docs/project-design.md#maintenance)启动的是普通消费模式。

方面三已记录真实配置启动、Windows token 共享及未登录页面/脱敏观测验收；后端 54 项、前端 5 项及相关工具门禁通过。正常任务消费、真实生成和完整项目旅程未验证。方面六不复跑服务或模型；最终离线门禁见[验证记录](docs/validation-history.md#iteration7-aspect6)。

真实 .env、密钥、上传项目、数据库、日志与备份原地保护，不进入 Git 或源码清理。当前不使用 Docker、Compose、WSL 或容器服务。初始化 SQL 含删除表语句，不得直接覆盖已有数据库。

## 长期文档

- [项目说明与实现设计](docs/project-design.md#product)：架构、协议、配置、启动和维护。
- [迭代历史](docs/iteration-history.md#iteration-7)：决策、进度、历史原文及图片出处。
- [验证历史](docs/validation-history.md#evidence-classes)：原始证据等级、数值、方法、Blocked 和未验证项。

历史图片只提供固定提交链接；历史模型或性能结果不代表当前生产能力。
