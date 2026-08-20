# EzllmTest

基于 LLM 的软件测试计划与测试用例生成平台。仓库包含 Vue 3 前端、FastAPI 后端、MySQL 样例数据库，以及七个示例项目的文档。

## 本地运行环境

- Windows 10/11
- Conda，Python 3.11
- Node.js 24、npm 11
- MySQL 8.x
- 至少一个聊天模型 API Key（智谱、阿里云百炼、DeepSeek 或 Moonshot）
- RAG/向量检索需要智谱 API Key（`embedding-3` 是当前唯一 embedding 提供商）

前端默认运行在 `http://localhost:8080`，后端默认运行在 `http://localhost:8130`。

## 1. 创建 Conda 环境并安装后端依赖

在项目根目录打开 PowerShell：

```powershell
conda create --name ezllmtest python=3.11 -y
conda activate ezllmtest
python -m pip install --upgrade pip
python -m pip install -r .\ez_back_dev\requirements.txt
python -m pip check
```

当前依赖已迁移到 Python 3.11、Pydantic 2、SQLAlchemy 2、`langchain-core==1.5.6`、`langchain-openai==1.5.2`、`langchain-text-splitters==1.1.2` 和 `openai==3.3.0`。应用不再依赖旧的 `langchain`、`langchain-community`、Chroma 或 FAISS 包装器。

如果是在旧的 LangChain 0.2 环境中原地升级，并且 `pip check` 报告旧元包冲突，可在这个项目专用 Conda 环境中执行：

```powershell
python -m pip uninstall -y langchain langchain-community
python -m pip install --upgrade -r .\ez_back_dev\requirements.txt
python -m pip check
```

## 2. 创建本地配置

```powershell
if (-not (Test-Path .\.env)) { Copy-Item .\.env.example .\.env }
if (-not (Test-Path .\ez_front_dev\.env)) { Copy-Item .\ez_front_dev\.env.example .\ez_front_dev\.env }
notepad .\.env
```

只在根目录 `.env` 中填写真实凭证，不要修改或提交 `.env.example`：

```dotenv
DATABASE_URL=mysql+pymysql://ezllmtest_v2_app:replace_with_your_database_password@127.0.0.1:3306/ezllmtest_dev?charset=utf8mb4

ZHIPU_API_KEY=replace_with_your_zhipu_api_key
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
ZHIPU_CHAT_MODEL=glm-4.7
ZHIPU_EMBEDDING_MODEL=embedding-3

DASHSCOPE_API_KEY=replace_with_your_dashscope_api_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen3.5-plus

DEEPSEEK_API_KEY=replace_with_your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_CHAT_MODEL=deepseek-v4-flash

MOONSHOT_API_KEY=replace_with_your_moonshot_api_key
MOONSHOT_BASE_URL=https://api.moonshot.ai/v1
MOONSHOT_CHAT_MODEL=kimi-k2.5

BACKEND_HOST=localhost
BACKEND_PORT=8130
CORS_ORIGINS=http://localhost:8080
LANGCHAIN_TRACING_V2=false
```

聊天模型注册表如下。前端显示具体模型 ID，但提交给后端的公共标签保持兼容：

| Provider 参数 | 前端显示 | 后端公共标签 | API Key 环境变量 |
| --- | --- | --- | --- |
| `zhipu` | `glm-4.7` | `GLM-4.7` | `ZHIPU_API_KEY` |
| `alibaba` | `qwen3.5-plus` | `通义千问` | `DASHSCOPE_API_KEY` |
| `deepseek` | `deepseek-v4-flash` | `DeepSeek` | `DEEPSEEK_API_KEY` |
| `moonshot` | `kimi-k2.5` | `Moonshot Kimi` | `MOONSHOT_API_KEY` |

Moonshot 的 Key 必须与平台地区匹配：国际平台 Key 使用 `https://api.moonshot.ai/v1`；中文平台 Key 使用 `https://api.moonshot.cn/v1`。二者混用会返回 401。为避免数据库 URL 转义问题，数据库密码建议只使用英文字母和数字。所有 `.env` 变体均已被 Git 忽略，真实 Key 不得写入前端、源码、日志或聊天记录。

## 3. 创建数据库用户与数据库

先登录 MySQL；命令会提示输入现有 `root` 密码：

```powershell
mysql -u root -p
```

在 MySQL 控制台执行以下 SQL，并将 `YOUR_DB_PASSWORD` 替换为与 `.env` 相同的密码：

```sql
CREATE DATABASE IF NOT EXISTS ezllmtest_dev
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'ezllmtest_v2_app'@'localhost'
  IDENTIFIED BY 'YOUR_DB_PASSWORD';
ALTER USER 'ezllmtest_v2_app'@'localhost'
  IDENTIFIED BY 'YOUR_DB_PASSWORD';
GRANT ALL PRIVILEGES ON ezllmtest_dev.* TO 'ezllmtest_v2_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

回到项目根目录，导入完整样例数据：

```powershell
cmd /c "mysql -u root -p ezllmtest_dev < ezllmtest.sql"
```

验证六张表和七个样例项目：

```powershell
conda activate ezllmtest
Set-Location .\ez_back_dev
python .\scripts\verify_database.py
Set-Location ..
```

## 4. 安装前端依赖

```powershell
Set-Location .\ez_front_dev
npm ci
Set-Location ..
```

Node 24 下 `@achrinza/node-ipc` 可能打印 `EBADENGINE` 警告；只要 `npm ci` 最终成功即可继续。

## 5. 启动项目

打开第一个 PowerShell 窗口启动后端：

```powershell
Set-Location D:\codex\EzllmTest_v2\ez_back_dev
conda activate ezllmtest
python .\serve.py
```

打开第二个 PowerShell 窗口启动前端：

```powershell
Set-Location D:\codex\EzllmTest_v2\ez_front_dev
npm run serve
```

浏览器访问 `http://localhost:8080`。可使用样例项目 ID：

```text
Ez1800887156818837504
```

后端 API 文档位于 `http://localhost:8130/docs`，健康检查位于 `http://localhost:8130/health`。

项目分析会先进入测试计划页面。`POST /project/llm/plan/stream` 使用 SSE 展示文档加载、分块分析、汇总生成和数据库保存进度，并在一次可恢复流程中保存业务摘要、测试计划和测试菜单。分析完成前，测试菜单和后续测试类型处于锁定状态。

单元、集成、API、UI、数据库、功能、非功能和验收测试通过 `POST /project/llm/workflow/stream` 执行 18 个分析/用例工作流。各步骤均展示真实进度、模型思考、流式正文、Token 用量和取消操作；多步骤页面会把执行面板显示在当前所点击按钮下方。页面离开、取消或模型错误会终止请求，只有完整生成结束后才保存可复用结果。所有原有 GET/POST/PUT LLM 接口继续保留。

流式模型使用均衡预算：中间分块最多 8192 token，最终汇总最多 32768 token，Qwen 思考预算为 8192 token。分类 token 用量仅展示厂商实际返回的数据，不进行本地估算。

## 6. 测试与模型连通性

后端离线测试不会调用智谱 API：

```powershell
Set-Location D:\codex\EzllmTest_v2\ez_back_dev
conda activate ezllmtest
python -m pytest .\tests -q
```

凭证扫描不会打印命中值或原始行：

```powershell
Set-Location D:\codex\EzllmTest_v2
python .\scripts\scan_credentials.py
```

真实模型 smoke test 可能产生费用，必须显式选择 provider 并确认费用。缺少任一参数时脚本不会创建模型客户端：

```powershell
Set-Location D:\codex\EzllmTest_v2\ez_back_dev
python .\scripts\smoke_llm.py --provider zhipu --confirm-cost
python .\scripts\smoke_llm.py --provider alibaba --confirm-cost
python .\scripts\smoke_llm.py --provider deepseek --confirm-cost
python .\scripts\smoke_llm.py --provider moonshot --confirm-cost
```

`embedding-3` 是一笔额外的智谱调用，需再增加显式开关：

```powershell
python .\scripts\smoke_llm.py --provider zhipu --confirm-cost --with-embedding
```

前端检查：

```powershell
Set-Location D:\codex\EzllmTest_v2\ez_front_dev
npm run lint
npm run build
```

## 迁移与兼容性说明

- 旧 `langchain.chains`/retriever/storage 调用已迁移为 LangChain Core 1.x runnable/LCEL。
- Pydantic v1 兼容层和 `.dict()` 已迁移到 Pydantic 2。
- SQLAlchemy 声明模型已迁移到 2.x API，同时保留原六张表、列名、主键和七个样例项目。
- RAG 改为请求级内存向量库，防止不同项目之间共享全局检索数据。
- 文档加载直接使用 `pypdf`、`docx2txt` 和文本读取，不再依赖 `langchain-community`。
- FastAPI 路径、请求字段、`{status, reason, data}` 响应信封及前端调用方式保持兼容。

## 迭代文档

- Iteration 1 完成报告：[`docs/iteration-1-closeout.md`](docs/iteration-1-closeout.md)
- Iteration 1 任务与过程记录：[`docs/iteration-1-tasks.md`](docs/iteration-1-tasks.md)、[`docs/iteration-development-log.md`](docs/iteration-development-log.md)
- Iteration 2 流程与 Token 效率计划：[`docs/iteration-2-tasks.md`](docs/iteration-2-tasks.md)
- 新对话第一、第二提示词：[`docs/iteration-2-prompts.md`](docs/iteration-2-prompts.md)

## 已知限制

- 真实 provider smoke 只证明 Key、Base URL、模型 ID 和模型工厂可用，不代表十个 FastAPI 业务页面都已经逐接口完成真实付费 E2E。
- RAG 仍统一使用智谱 `embedding-3`；选择其他聊天模型时也需要智谱 Key 才能执行向量检索流程。
- Task 6 已通过静态 SQL 和假引擎证明数据库兼容及验证脚本只读，但没有在自动验收中连接真实 MySQL。
- `npm run lint` 当前为零错误、零警告；生产构建仍有 Node `fs.Stats` 弃用提示和字体、Logo、vendor 包体积建议，但构建成功。
- 当前工作流缓存尚未全面按文档版本、提示词版本、用户选择和模型建立统一键；重复 RAG 请求仍可能重新构建向量索引。Iteration 2 将以离线调用/Token 基线验证这些优化。
- 凭证扫描覆盖当前 tracked、staged 和非忽略 untracked 文本，不重写或扫描完整 Git 历史。历史中出现过的 Key 必须在供应商控制台撤销或轮换。

## 常见问题

- `/health` 显示 `database: error`：检查 MySQL 服务、数据库用户密码和 `DATABASE_URL`。
- `/health` 显示 `llm_configured: false`：检查根目录 `.env` 中的 `ZHIPU_API_KEY`。
- 前端无法访问后端：确认后端监听 `8130`，前端 `.env` 中 `VUE_APP_API_BASE_URL` 为 `http://localhost:8130`。
- 修改前端 `.env` 后必须重启 `npm run serve`。
- Moonshot 返回 401：确认中文平台 Key 配置 `.cn` 地址，国际平台 Key 配置 `.ai` 地址。
- smoke 脚本提示费用未确认：检查账户余额后显式增加 `--confirm-cost`，不要通过修改脚本绕过费用门。
- 仓库历史曾包含 LangSmith 凭据；应在 LangSmith 后台撤销或轮换该 Key。当前代码默认关闭跟踪，也不会再写入凭据。
