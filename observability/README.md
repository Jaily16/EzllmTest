# 本地观测服务

[Verified] 本目录保存本地观测配置示例和 ignored SQLite 运行数据。独立服务绑定 `127.0.0.1:8140`，前端入口为 `/observability`。

[Approved] 在本机按 `.env.example` 手动填写 `.env`，并通过 `--observability-env-file` 显式选择。数据库路径必须是 `observability/data` 内的绝对 `.sqlite3` 路径。

[Protected] 本地数据库、ingestion token 和真实配置不得进入 Git、截图或开发记录。服务只接收允许清单内的 Agent 元数据，不保存 prompt、completion、reasoning、项目文档、工具参数/结果、SQL、Redis 内容、凭据或 traceback。

[Approved] 数据保留 7 天，总上限 100,000 行，其中 spans 50,000、metrics 30,000、logs 20,000。清理不迁移或删除 MySQL、Redis 和既有外部观测数据。

[Verified] 当前运行路径不再使用 OTLP、Collector、Prometheus、Tempo、Grafana 或 LangChain/LangSmith 外部追踪。
