# 运维入口

[Verified] 当前 V6 使用 [分模块运行协议](modular-runtime.md)：显式加载三份本地配置，按顺序启动 observability API、legacy API、Agent API、worker 与 frontend。MySQL/Redis 由外部管理；端口为 8140、8230、8231 与 8180。

[Protected] 启停只按本轮 run ID 和进程归属执行，不修改 V2、用户数据、原有 env、已有数据库或其他进程。用户另行授权的模型来源只按白名单只读提取，不导入旧基础设施配置。runner 不改 Windows 用户/系统环境变量，不自动安装或迁移。

[Verified] [container-delivery.md](container-delivery.md) 和 [dual-mode-acceptance.md](dual-mode-acceptance.md) 仅保留历史说明，其旧设施已从 V6 移除，不是当前可执行交付入口。不得运行其中历史 Compose 指令。当前观测入口是独立 loopback API 和 SQLite，不使用外部 Collector/Prometheus/Tempo/Grafana/LangSmith tracing。

[Verified] 当前交付、验证与边界见 [Iteration 6 收口报告](../iteration-6-closeout.md)，历史方法与结果见 [验证历史](../validation-history.md)。五模块本地切换、中文观测与函数注释语义等价门禁均已完成。

本目录不保存真实环境值、数据库连接值、项目 ID、用户日志或进程状态文件。
