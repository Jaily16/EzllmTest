# 容器交付与运维边界

> [Verified] 历史资料：本文记录 Iteration 5 的容器设计，所述 Docker/Compose 与外部观测设施已从当前 V6 树移除，不是当前可执行入口。原始设施见[不可变 V5 快照](https://github.com/Jaily16/EzllmTest/tree/5cf1effb32a8efcd34902df05d27442f3586dc1c)；当前入口见[分模块运行](modular-runtime.md)。

本文描述 Iteration 5 Aspect 7 的容器交付约束。它只说明构建、权限、配置注入、健康检查和数据保留边界，不替代产品 API、Agent、MCP 或数据库契约。

## 运行组合

默认 `compose.yaml` 保持完整十服务栈：frontend、legacy-api、agent-api、worker、mysql、redis、otel-collector、prometheus、tempo 和 grafana。发布端口仍只绑定 loopback：前端 `8080`、legacy API `8130`、Agent API `8131`、Prometheus `9090` 和 Grafana `3000`。

需要较小的核心栈时，使用只标记观测服务的 `ops/compose/observability-profile.yaml`；不启用 profile 时运行 frontend、legacy-api、agent-api、worker、mysql 和 redis，显式 `--profile observability` 时再加入四个观测服务。切换组合时使用同一个 Compose project name，并先以同一组合执行普通 `down`；普通停机不要使用 `-v`。

```powershell
# 默认完整栈
docker compose --env-file D:\secure\ezllmtest-runtime.env up --build -d --wait

# 核心栈
docker compose --env-file D:\secure\ezllmtest-runtime.env `
  -f compose.yaml -f ops/compose/observability-profile.yaml `
  up --build -d --wait

# 核心栈 + 观测
docker compose --env-file D:\secure\ezllmtest-runtime.env `
  -f compose.yaml -f ops/compose/observability-profile.yaml `
  --profile observability up --build -d --wait
```

所有模块化或容器命令都必须显式指定绝对 env 文件；仓库不会把真实 `.env` 当作默认输入。`ops/compose/.env.example` 只用于离线配置解析和变量名示例，不提供真实凭证。

## 镜像与权限

后端使用固定 digest 的 Python 3.11 两阶段构建。dependencies stage 只安装 Linux runtime lock，运行阶段复制依赖和源码，使用固定 `10001:10001` 非 root 身份；root filesystem 只读，`/tmp` 由 Compose 提供临时写入，`/app/static/projects` 是唯一的持久可写项目挂载。

前端保留 Node 24 build stage 和固定 digest 的 nginx runtime，以 nginx 非 root 用户监听 8080。运行时需要的 nginx cache、临时目录和 PID 目录由镜像/Compose 显式提供；SPA fallback、静态资源路径、缓存策略和既有安全响应头保持不变。

应用服务统一使用 `cap_drop: [ALL]` 和 `no-new-privileges:true`。MySQL、Redis、OTel、Prometheus、Tempo 和 Grafana 保留各自镜像的 vendor 用户与启动脚本；本项目不擅自改变它们的权限模型，也不把宿主用户目录绑定进容器。

## 配置与 secret-file

后端兼容现有环境变量注入，并只对以下五个名称支持显式 `<NAME>_FILE`：`DATABASE_URL`、`ZHIPU_API_KEY`、`DASHSCOPE_API_KEY`、`DEEPSEEK_API_KEY` 和 `MOONSHOT_API_KEY`。

- 同时设置直接变量和对应 `_FILE` 会 fail closed。
- 文件缺失、不可读、含 NUL 或超过 8192 bytes 会失败；错误不输出值、文件路径、数据库 URL、模型名或项目 ID。
- 读取只去除一个末尾换行，不扫描目录、不寻找其他 `.env`、不读取上传项目或卷。
- 未设置 `_FILE` 时保留原有环境变量和默认值行为。
- Dockerfile 不复制 secret 文件；默认 Compose 不创建或保存 secret 文件。

`GET /health` 保持既有语义。`GET /ready` 是独立运维探针：legacy API 只读检查数据库连接，Agent API 检查 Redis 与 worker heartbeat；readiness 不触发 provider、embedding、RAG、Agent tool 或项目读取。

## 数据卷与升级

| 卷 | 数据职责 | 保护边界 |
| --- | --- | --- |
| `mysql_data` | MySQL 长期项目、revision 和 artifact 数据 | 不由本项目自动导出、迁移或删除 |
| `redis_data` | checkpoint、lease、event、idempotency 和恢复运行数据 | 不扫描、不清理、不重建 |
| `project_files` | 用户上传项目与静态项目文件 | 不读取、复制、chmod、chown 或覆盖 |
| `prometheus_data` | 指标历史 | 不由普通停机删除 |
| `tempo_data` | trace 历史 | 不由普通停机删除 |
| `grafana_data` | Grafana 配置与 dashboard 状态 | 不由普通停机删除 |

升级前由运维人员在仓库外，以自己的备份流程备份数据库、Redis 和项目文件。仓库不提供自动备份/恢复/迁移脚本；`ezllmtest.sql` 只适用于明确的空库初始化，不对已有库自动执行 DDL。

升级后的最小顺序是：先执行 `docker compose ... config --quiet`，再确认 `/health`、`/ready`、frontend `/` 和 worker heartbeat，随后运行版本契约、离线测试与凭证扫描。回滚只切换到人工确认的旧镜像 tag/digest，不自动覆盖数据卷。

普通停机只使用不带 `-v` 的 `docker compose down`。禁止 `docker volume prune`、广泛 `docker volume rm`、`docker system prune` 和对不明 project 执行 `down -v`。CI 的 `down -v` 仅允许出现在唯一的 `ezllm-aspect8-ci` disposable validation project，且该 project 不承载用户数据。

## 故障边界

- 构建缺少本地 digest 镜像时，应报告为 blocked，不自动 pull 或改写版本契约。
- 新 UID 无法访问已有用户卷时，不对该卷执行权限修复；记录为运维升级前置条件。
- profile、read-only、tmpfs 或非 root 导致 smoke 失败时，回滚当前镜像/Compose 批次，不把服务改回 root 或删除安全字段。
- 无法证明容器、镜像、卷或数据库归属时，保留对象并报告；不以达到清理数量为理由操作。
