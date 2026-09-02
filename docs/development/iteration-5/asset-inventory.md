# Iteration 5 Aspect 1：资产分类清单

本清单对应 `iteration5_asset_inventory_v1.json`。它是当前工作树的人工审查记录，不是删除授权；`reviewed` 表示分类已确认，仍不表示允许删除。

## 分类规则

| 分类 | 当前动作 |
|---|---|
| Protected user data | 只记录存在/声明存在；不读取、不记录大小、不计算 hash、不移动 |
| Protected product asset | 保留；只做静态引用和契约审计 |
| Historical evidence | 保留并 hash；归档必须保留链接和恢复映射 |
| Generated disposable | 进入候选 allowlist；先 dry-run，默认 report-only |
| Duplicate candidate | 保留，等待双重无引用和行为/内容证据 |
| Legacy candidate | 保留，等待 import、route、CI、runtime 和兼容 shim 证据 |
| Unknown | 保留并报告；不得为增加清理数量而处理 |

文件名、mtime、ignored 状态和外观老旧不能单独构成删除证据。

## Git 状态对象

### 本回合 dry-run 统计

`python scripts/iteration5_asset_inventory.py --repo-root . --dry-run` 只输出 JSON，不存在 apply 模式。当前报告包含 440 个资产记录；分类计数为：Protected user data 5、Protected product asset 265、Historical evidence 120、Generated disposable 18、Duplicate candidate 12、Legacy candidate 8、Unknown 12。

Git 的原始 ignored 记录数为 20,325；其中真实 `.env`、`example/`、IDE 状态和上传项目子路径在报告中只折叠为边界存在记录，不输出子文件名、大小或 hash。任务专用构建/pytest 临时目录在门禁后均已清理；既有 ignored 生成物没有被自动删除。

### Dirty tracked

- `README.md`：Protected product asset，存在用户修改和 release contract 引用，保留。
- `ez_back_dev/tests/test_iteration4_release_contracts.py`：Protected product asset，存在用户修改并保护历史 release hash，保留。

### Untracked

- `docs/iteration-5-overview.md`：Protected product asset，当前 Iteration 5 规划来源。
- `docs/iteration-5-prompts.md`：Protected product asset，当前执行协议来源。
- `ez_back_dev/tests/test_iteration5_planning_contracts.py`：Protected product asset，规划契约测试，不能覆盖或自动重生成。

### Ignored matching roots

| 路径 | 分类 | 处理 |
|---|---|---|
| `.env` | Protected user data | 只确认存在；不读取、不哈希、不输出大小 |
| `.pytest_cache/` | Generated disposable | 候选；不默认清理 |
| `example/` | Protected user data | 不读取、不哈希、不输出大小 |
| `ez_back_dev/.DS_Store` | Generated disposable | 只允许精确路径候选 |
| `ez_back_dev/.idea/` | Protected user data | 保留本地 IDE 状态 |
| `ez_back_dev/.pytest_cache/` | Generated disposable | 候选；不默认清理 |
| `ez_back_dev/app/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/chain/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/dao/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/llm/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/model/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/prompt/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/scripts/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/service/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/static/.DS_Store` | Generated disposable | 只允许精确路径候选 |
| `ez_back_dev/static/projects/` | Protected user data | 上传项目目录，绝不处理 |
| `ez_back_dev/test/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/tests/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/tools/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/vectorstore/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_back_dev/vectorstore/faiss/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |
| `ez_front_dev/.env` | Protected user data | 只确认存在；不读取、不哈希、不输出大小 |
| `ez_front_dev/dist/` | Generated disposable | 可重建但默认保留 |
| `ez_front_dev/node_modules/` | Generated disposable | 可由既有 lock 重建但默认保留 |
| `scripts/__pycache__/` | Generated disposable | 候选；需枚举精确路径 |

Ignored 子文件使用 `Generated disposable` 继承分类，但不允许把上述描述性路径直接作为递归删除目标。

## Tracked 候选与引用证据

| 对象 | 分类 | 已知证据 | 当前动作 |
|---|---|---|---|
| `ez_front_dev/src/components/FounctionalTest.vue` | Legacy candidate | router 动态 import；frontend contract/shared interaction/workspace tests | 保留；只能做兼容 rename candidate |
| `ez_front_dev/src/components/HelloWorld.vue` | Legacy candidate | 当前未发现 active source import，但仍需动态加载、文档、CI、历史审计 | 保留 |
| `ez_front_dev/src/views/HomeView.vue` | Legacy candidate | 当前未发现 active router/reference，但不能只凭静态搜索删除 | 保留 |
| 旧 logo 与旧 test image 资产 | Duplicate candidate | branding regression、rollback 文档、active registry 检查 | 保留 |
| `ez_back_dev/test/` 与 `ez_back_dev/tests/` | Legacy candidate | pytest、Actions、fixture、历史测试引用 | 保留；不合并目录 |
| `legacyLongTextService.py`、`llm*TestService.py` | Legacy candidate | legacy router、Agent tool executor 和 provider boundary | 保留 |
| `InfoType.py`、旧 DAO/model、SQL | Protected product asset | legacy route、旧表字段、artifact prerequisite | 保留，不作为遗留删除 |
| `iteration4/aspect` runtime IDs、Compose tags、测试/fixture 名称 | Legacy candidate | runtime contract、MCP、telemetry、Compose、历史证据 | 保留；协议 ID 不能按注释清理 |
| `LANGGRAPH_STRICT_MSGPACK` | Unknown/legacy config candidate | 当前实现使用严格 JSON；外部 env 引用尚未证明 | 保留并报告 |

## 外部资源和容器层

以下对象只从 Compose、`.env.example` 和 SQL 声明建立记录，未连接或 inspect：

- MySQL service、`mysql_data` volume、`ezllmtest.sql` schema：Protected product asset / Protected user data 分层处理。
- Redis service、`redis_data` volume、Agent Redis namespace：Protected user data。
- `project_files` volume、`static/projects/`：Protected user data。
- Prometheus、Tempo、Grafana volumes：Protected user data。
- frontend、legacy-api、agent-api、worker、mysql、redis、otel-collector、prometheus、tempo、grafana：Protected product asset 的交付声明。
- 全局系统临时目录：Unknown/Protected user data；仅允许 task-owned 临时根，不做全局扫描。

## 引用审计矩阵

每个候选必须有以下结果；任一项无法证明即保留：

1. Python import、相对 import、`importlib`、字符串 registry 和公共 CLI。
2. Vue router、懒加载、模板组件、CSS `url()` 和 asset registry。
3. pytest 收集、fixture 路径、Actions 测试命令和 release hash。
4. Markdown 链接、图片链接、历史文档和回滚说明。
5. Dockerfile COPY/ADD/CMD/ENTRYPOINT、Compose build/context/volume/config/env。
6. GitHub Actions、scripts 和 npm/Python 入口。
7. workflow catalog、tool registry、MCP URI、schema/policy version、Agent capability 和 frontend API route。

## 清理策略

allowlist 当前为 report-only，见 `iteration5_cleanup_allowlist_v1.json`：

- 候选种类包括 pycache、pyc、pytest/cache、coverage、dist、node_modules、明确生成的日志、benchmark、trace、screenshot。
- 真实日志、trace、benchmark、screenshot 若无法证明为 deterministic fixture 产物，转为 Protected user data 或 Unknown。
- 扫描器先枚举实际对象，再生成精确路径记录；禁止模糊 glob 直接递归删除。
- 任何路径必须解析并确认位于批准根目录内，拒绝 repo root、`.git`、`.env`、上传目录、`example`、volume、symlink、junction 和路径穿越。
- Aspect 1 本回合不执行清理；因此当前所有候选均保留。
