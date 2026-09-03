# 分模块运行与运维协议

## 适用范围

该入口用于不启动完整 Docker Compose 栈时，按固定依赖顺序运行本地 legacy API、Agent API、worker 和前端。MySQL 与 Redis 由操作者或既有基础设施管理；MCP 和观测组件保持显式可选，不会被默认 runner 自动发现或启动。

默认顺序为：

```text
MySQL（只读预检）→ Redis（只读预检）→ legacy API → Agent API → worker → frontend
```

默认地址为：

| 模块 | 地址/端口 | 归属 | 就绪依据 |
| --- | --- | --- | --- |
| MySQL | `DATABASE_URL` | 外部管理 | `SELECT 1` 与表名只读检查 |
| Redis | `AGENT_REDIS_URL` | 外部管理 | `PING` |
| legacy API | `127.0.0.1:8130` | runner 管理 | `GET /ready` |
| Agent API | `127.0.0.1:8131` | runner 管理 | `GET /ready` |
| worker | 无 HTTP 端口 | runner 管理 | Redis worker heartbeat |
| frontend | `127.0.0.1:8080` | runner 管理 | `GET /` |

MCP 仍使用现有的显式 `python -B -m app.mcpServer` 入口，并要求操作者明确提供可信项目作用域。通用 runner 不扫描项目、不猜测 project scope，也不把项目 ID 写入状态或日志。观测组件仍使用现有 Compose 配置，不由该入口管理。

## 配置安全边界

`preflight` 和 `start` 必须明确指定一个绝对 env 文件：

```powershell
python -B scripts/modular_runtime.py preflight --repo-root D:\codex\EzllmTest_v2 --env-file D:\secure\ezllmtest-runtime.env
python -B scripts/modular_runtime.py start --repo-root D:\codex\EzllmTest_v2 --env-file D:\secure\ezllmtest-runtime.env
```

也可以使用 Windows 包装：

```powershell
.\ops\modular\run.ps1 preflight --env-file D:\secure\ezllmtest-runtime.env
.\ops\modular\run.ps1 start --env-file D:\secure\ezllmtest-runtime.env
```

portable shell：

```sh
./ops/modular/run.sh preflight --env-file /secure/ezllmtest-runtime.env
./ops/modular/run.sh start --env-file /secure/ezllmtest-runtime.env
```

入口不会默认寻找仓库根 `.env` 或前端 `.env`，不会打印变量值，也不会把 provider key、密码、数据库 URL、Redis URL 或项目资料写入日志。backend 子进程显式设置 `PYTHON_DOTENV_DISABLED=true`；frontend 使用 runner 创建在系统临时目录中的空 `envDir`，只继承允许的 `VUE_APP_*` 和 `VITE_*` 变量。

`ops/compose/.env.example` 只用于完整 Compose 的变量名和占位说明，不会被模块 runner 自动合并。

## 只读预检

预检只验证配置、loopback 地址、端口、MySQL、Redis 和既有 Compose 对齐关系。数据库探针只执行 `SELECT 1` 和 `information_schema` 表名查询；Redis 探针只执行 `PING`。不会执行 SQL 初始化、迁移、DDL、业务表读取、Redis 扫描、provider 调用或 embedding 调用。

缺表、权限不足或依赖未启动时，预检以非零状态结束；操作者应由数据库管理员审核后单独处理初始化，不要把 `ezllmtest.sql` 直接用于已有用户数据库。

## 启动、状态与停止

```powershell
.\ops\modular\run.ps1 status --run-id <run-id>
.\ops\modular\run.ps1 ready --run-id <run-id>
.\ops\modular\run.ps1 stop --run-id <run-id>
```

`start` 返回不包含敏感值的 run ID。进程状态和子进程日志只写入系统临时目录下的 task-owned run 目录，不写入仓库。`stop` 只处理该 run 创建且 PID、创建时间、工作目录、可执行文件和命令指纹均匹配的进程，顺序为 frontend、worker、Agent API、legacy API；这就是模块化入口的安全停机协议。

无法证明进程归属时，`stop` 拒绝操作并报告 `ownership_unproven`。MySQL、Redis、Compose 容器、named volume、上传项目和观测数据永远不属于该 stop 协议。

## Readiness 协议

两个 API 新增的 readiness 响应使用 `iteration5-readiness-v1`。旧 `/health` 响应保持不变。

legacy API 成功时：

```json
{
  "schema_version": "iteration5-readiness-v1",
  "service": "legacy-api",
  "status": "ready",
  "checks": {"database": "ok"}
}
```

Agent API 成功时：

```json
{
  "schema_version": "iteration5-readiness-v1",
  "service": "agent-api",
  "status": "ready",
  "checks": {"redis": "ok", "worker": "available"}
}
```

全部成功返回 HTTP 200；依赖不可用返回 HTTP 503。失败响应不包含异常、连接地址、凭证、项目 ID或用户数据。

## 与完整 Compose 的关系

完整 Compose 入口、服务名、端口、网络、数据卷和观测配置保持原样。模块化入口不调用 Compose，不停止 Compose 服务，也不操作 Compose volume；两种方式只共享现有应用入口和配置名称。
