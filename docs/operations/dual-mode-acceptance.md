# Aspect 8 双模式集成验收

> [Verified] 历史资料：本文记录 Iteration 5 的未完成双拓扑验收流程；相关 harness、Compose 与 fixture 已从当前 V6 树移除，不得将以下命令当作当前运行入口。当前限制见[验证历史](../validation-history.md)。

本手册描述 Iteration 5 的两种验收拓扑。它们使用同一份不可变的 Iteration 4 historical Acceptance dataset；网络/进程探针和确定性业务验收分别记录，不能把 `/health` 或 `/ready` 当作 Agent workflow E2E。

## 固定输入与安全边界

- 契约：[`ops/iteration5-dual-mode-acceptance-contract.json`](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ops/iteration5-dual-mode-acceptance-contract.json)
- dataset：`ez_back_dev/tests/fixtures/historical/iteration4/iteration4_agent_acceptance_v1.json`
- case 数：18；provider：`deterministic_fake`
- 报告目录必须是仓库外的绝对路径；脚本自行创建 synthetic env，不接受真实 `.env`。
- 不读取用户项目、真实 MySQL/Redis/观测数据或普通 named volume；不访问 provider/embedding。
- 报告只保存脱敏字段和摘要 hash，不保存请求正文、traceback、凭证、连接 URL、项目 ID或用户内容。

## 调用方式

```powershell
python -B scripts/run_iteration5_dual_mode_acceptance.py modular `
  --repo-root D:\codex\EzllmTest_v2 `
  --report-dir D:\codex\EzllmTest_v2_aspect8_reports

python -B scripts/run_iteration5_dual_mode_acceptance.py docker `
  --repo-root D:\codex\EzllmTest_v2 `
  --report-dir D:\codex\EzllmTest_v2_aspect8_reports

python -B scripts/run_iteration5_dual_mode_acceptance.py both `
  --repo-root D:\codex\EzllmTest_v2 `
  --report-dir D:\codex\EzllmTest_v2_aspect8_reports
```

脚本使用 `subprocess` argv、`shell=False` 和固定工作目录。报告目录、临时 env、Compose override、task-owned project 和镜像 tag 均在仓库外且可精确归属。

## Modular topology

先检查 task-owned project 和 `8080/8130/8131/23306/26379` 未被占用，再启动只包含 task-owned MySQL/Redis 的 disposable Compose project。模块化 runner 按 legacy API → Agent API → worker → frontend 启动，反向停止；MySQL/Redis 永远不是 runner-owned。验证 `/health`、`/ready`、frontend `/`、worker heartbeat，然后执行 deterministic Acceptance。无法证明 PID、命令、工作目录或 project 归属时拒绝停止/清理。

## Docker topology

使用默认 `compose.yaml` 的完整 10-service 栈和唯一 task-owned project。要求本地已有所需 digest 镜像并使用 `--pull never`；缺少镜像或固定端口被占用时直接记录 `Blocked`。验证十个服务、API health/readiness、frontend、Prometheus、Tempo、Grafana、容器最小权限和 worker heartbeat，再在 task-owned `agent-api` 容器中执行同一 deterministic Acceptance。清理只针对本次 project、container、network、volume 和应用镜像 tag。

## 结果比较

比较只包含 dataset id/hash、18 个 case、suite/scenario、terminal status、trajectory、metrics、hard-gate failures 和安全/费用计数。忽略 topology、hostname、Python patch、容器名和 run id。必须证明两种拓扑的 case 与 trajectory 一致，approval bypass、duplicate side effect、project isolation violation、budget overrun、unsafe capability、sensitive leak、real provider、real embedding、user database、user project 和 currency cost 全为零。

## 普通停机与验收清理

普通用户停机不得使用 `down -v`、`volume prune` 或广泛删除。CI/Aspect 8 的 `down --volumes` 只允许用于已记录、唯一、无用户数据的 task-owned project；无法证明归属时保留现场并报告。备份、恢复、真实数据库迁移和用户卷操作不由本手册或 harness 自动执行。

## Blocked 处理

任何 gate 为 `Blocked` 或 `Unknown` 时保留报告、hash 和现场摘要，状态只能是 `Blocked`/`Incomplete`。不得通过跳过 case、扩大 ignore、伪造 zero counter、改端口、安装依赖或重写历史 evidence 来达成完成。
