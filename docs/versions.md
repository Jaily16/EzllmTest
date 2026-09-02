# 当前版本与升级契约

本页是唯一主动维护的精确版本说明。机器校验入口是
[`ops/version-contract.json`](../ops/version-contract.json)；安装和运行时仍以
各自的 executable manifest、lockfile、Dockerfile digest 与 GitHub Actions
commit SHA 为最终执行真源。版本契约只负责检查这些真源是否组成同一兼容组合，
不会自动接受当前环境值或改写任何文件。

## 运行时

| 表面         | 当前精确值                | 执行真源                                                                   |
| ------------ | ------------------------- | -------------------------------------------------------------------------- |
| Python       | 3.11.15                   | `ez_back_dev/Dockerfile`、`.github/workflows/iteration4-offline.yml`       |
| Node.js      | 24.18.0（24 LTS 线）      | `ez_front_dev/Dockerfile`、`.github/workflows/iteration4-offline.yml`      |
| npm          | 11.x（随 Node 24 工具链） | `ez_front_dev/package-lock.json` 的 `lockfileVersion: 3` 与 CI 的 `npm ci` |
| 产品 release | 0.1.0                     | `ez_front_dev/package.json`、`compose.yaml` 应用镜像标签                   |

Python 只保留 3.11 运行时线；补丁版本升级必须先在隔离环境完成 resolver、
import smoke、`pip check` 和完整离线门禁。Node 只保留 24 LTS 线；升级必须先
完成干净 `npm ci`、`npm ls --depth=0`、lint、type-check 和 build。

## Python 依赖

- 人工维护的直接依赖输入：`ez_back_dev/requirements.in`。
- Linux（Ubuntu、Docker、CI）锁：`ez_back_dev/requirements.txt`。
- Windows 本地锁：`ez_back_dev/requirements-windows.txt`。
- 锁生成器：`pip-tools==7.6.1`、`pip-compile --generate-hashes`。
- 两个锁的安装策略均为 `python -m pip install --require-hashes -r <lock>`。
- Windows 与 Linux 只允许有明确的平台差异；Windows-only 包不能进入 Linux 锁。

当前直接依赖版本如下；传递依赖和每个可安装发行文件的 SHA-256 只在两个锁中
维护：

| 依赖                                   | 版本    | 依赖                               | 版本   |
| -------------------------------------- | ------- | ---------------------------------- | ------ |
| fastapi                                | 0.141.1 | uvicorn[standard]                  | 0.52.4 |
| pydantic                               | 2.13.5  | sqlalchemy                         | 2.0.52 |
| pymysql                                | 1.2.0   | python-multipart                   | 0.0.32 |
| python-dotenv                          | 1.2.3   | toollib                            | 2.2.6  |
| mcp                                    | 2.1.1   | langgraph                          | 1.2.11 |
| langgraph-checkpoint                   | 4.2.0   | redis                              | 8.1.0  |
| opentelemetry-api                      | 1.44.0  | opentelemetry-sdk                  | 1.44.0 |
| opentelemetry-exporter-otlp-proto-grpc | 1.44.0  | opentelemetry-semantic-conventions | 0.65b0 |
| langchain-core                         | 1.6.1   | langchain-openai                   | 1.6.0  |
| langchain-text-splitters               | 1.1.2   | openai                             | 3.6.0  |
| numpy                                  | 2.4.6   | pypdf                              | 6.16.2 |
| docx2txt                               | 0.9     | tiktoken                           | 0.14.0 |
| pytest                                 | 9.1.1   | httpx                              | 0.28.1 |

## 前端依赖

`ez_front_dev/package.json` 保存精确直接版本，`ez_front_dev/package-lock.json`
保存 lockfile v3 的完整传递依赖。Vue runtime、`@vue/compiler-sfc`、compiler-core、
compiler-dom、compiler-ssr 和 shared 保持同一 3.5 minor 线。

| 依赖                          | 版本   | 依赖                             | 版本       |
| ----------------------------- | ------ | -------------------------------- | ---------- |
| vue                           | 3.5.42 | @vue/compiler-sfc                | 3.5.42     |
| element-plus                  | 2.14.5 | @element-plus/icons-vue          | 2.3.2      |
| axios                         | 1.20.0 | lodash                           | 4.18.1     |
| vue-router                    | 4.6.4  | vue-class-component              | 8.0.0-rc.1 |
| vue-clipboard3                | 2.0.0  | core-js                          | 3.50.0     |
| vite                          | 8.2.2  | @vitejs/plugin-vue               | 6.0.8      |
| typescript                    | 6.0.3  | vue-tsc                          | 3.3.11     |
| eslint                        | 10.9.1 | eslint-plugin-vue                | 10.10.0    |
| @eslint/js                    | 10.0.1 | @types/lodash                    | 4.17.25    |
| @typescript-eslint/parser     | 8.68.0 | @typescript-eslint/eslint-plugin | 8.68.0     |
| @vue/eslint-config-typescript | 14.9.0 |                                  |            |

TypeScript 仍保持 6.0.3：当前 `@typescript-eslint` 兼容范围不允许在本方面
直接升级到 TypeScript 7；vue-router 5 和 Vue 2 线的 `vue-class-component` 也不
属于本方面的兼容升级。

## 工程规范工具

质量工具只安装在开发/CI 环境，不进入生产 runtime image；精确版本由
`ops/version-contract.json` 的 `quality_tools` 校验，配置和 hash lock 是执行真源。

| 工具      | 版本   | 执行真源                                                                       |
| --------- | ------ | ------------------------------------------------------------------------------ |
| Ruff      | 0.16.5 | `ez_back_dev/requirements-dev.txt`、`ez_back_dev/requirements-dev-windows.txt` |
| pip-tools | 7.6.1  | dev lock 的生成命令与 migration evidence                                       |
| Prettier  | 3.9.6  | `ez_front_dev/package.json`、`ez_front_dev/package-lock.json`                  |
| ESLint    | 10.9.1 | `ez_front_dev/package.json`、`ez_front_dev/eslint.config.mjs`                  |
| vue-tsc   | 3.3.11 | `ez_front_dev/package.json`、`ez_front_dev/package-lock.json`                  |

Ruff formatter/lint、Prettier check、ESLint 和 `vue-tsc` 都在 CI 以只读检查方式运行；
格式化命令不会自动接受 baseline，也不会写回 CI workspace。规则、人工审查范围和
中文说明注册表见 [`docs/development/iteration-5/style-guide.md`](development/iteration-5/style-guide.md)。

## 容器与 Compose

应用镜像使用产品 release 标签；外部镜像保留可读 tag，同时必须使用 immutable
digest。Compose 的十个 service、loopback 端口、命名卷和网络职责不在 Aspect 2
重新设计。

| 对象                  | 精确引用                                                                                                               |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| backend 应用          | `ezllmtest/backend:0.1.0`                                                                                              |
| frontend 应用         | `ezllmtest/frontend:0.1.0`                                                                                             |
| backend base          | `python:3.11.15-slim@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff`                          |
| frontend build base   | `node:24.18.0-alpine@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd`                          |
| frontend runtime base | `nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de`                            |
| MySQL                 | `mysql:8.4@sha256:b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb`                                    |
| Redis                 | `redis:8.2.8-alpine@sha256:a7859ed111db3c1f5404a973a4747505d559fb5ca32d37e447afc0ef845a2103`                           |
| OTel Collector        | `otel/opentelemetry-collector-contrib:0.159.0@sha256:1f2c54a30e713fac6b3ae77a1ec84010c2007e29ced8ec666214fc2f6739c1cc` |
| Prometheus            | `prom/prometheus:v3.12.0@sha256:69f5241418838263316593f7274a304b095c40bcf22e57272865da91bd60a8ac`                      |
| Tempo                 | `grafana/tempo:2.10.7@sha256:032b3acb51ed02c4b801473d54bb63e9e9f13738d215126d9843c30283794f4b`                         |
| Grafana               | `grafana/grafana:13.1.3@sha256:ab5cb380e3ff3172d6c8bd2e7cfd31cce977d2881b260e1f5bc089bf0b759b43`                       |

Compose 完整栈仍使用仓库的 `compose.yaml` 与 `ops/compose/.env.example` 进行
配置检查。模块化启动入口仍由现有后端/前端启动说明负责；Aspect 2 只确认版本
变更没有替换入口、端口、服务名或变量名。

## GitHub Actions

`.github/workflows/iteration4-offline.yml` 的 action 必须使用完整 commit SHA，
并保留经过人工核对的 release comment：

| Action               | commit                                     | release comment |
| -------------------- | ------------------------------------------ | --------------- |
| actions/checkout     | `3d3c42e5aac5ba805825da76410c181273ba90b1` | v7.0.1          |
| actions/setup-python | `5fda3b95a4ea91299a34e894583c3862153e4b97` | v7.0.0          |
| actions/setup-node   | `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` | v6.4.0          |

CI 使用 Python 3.11.15、Node 24.18.0、Redis 的上述 digest，以及 Linux 哈希锁。
它继续运行 credential scan、完整 pytest、Agent Eval/Acceptance/Benchmark、前端
lint/type-check/build 和 Compose 配置/交付门禁。CI 不读取真实 `.env`，不接入真实
provider、embedding、用户项目或用户数据库。

## 升级与回滚规则

1. 先在仓库外的任务专属隔离环境做单组 resolver/import/build/Compose spike。
2. 人工审查输入、锁、digest、Action SHA 与兼容性结果，再更新 executable source。
3. 运行 `python scripts/check_version_contract.py --check`，它只读检查并以非零码报告缺失、漂移和未知值。
4. 通过完整离线门禁后，才可把本组版本写入开发日志和 migration fixture。
5. 回滚时只恢复仍保持本次修改后 SHA-256 的文件；用户在执行期间修改过的文件必须保留并报告。

Iteration 1–4 的 closeout、manifest、真实模型验收和旧版本文字是
`Historical evidence`，不是当前安装真源；它们的原始内容与 hash 不因本页更新而
改写。Aspect 2 不升级产品 release，不修改生产源码、SQL、REST/SSE/MCP、workflow
或 Agent 数据/恢复语义。
