# Iteration 3 Aspect 4：项目入口、恢复与文档引导

## 1. 范围与目标

Aspect 4 把登录、已有项目恢复、新项目创建和三类文档上传整理为一条连贯 onboarding 旅程。首次用户应能明确选择“创建新项目”，返回用户应能通过项目 ID“打开已有项目”或继续本机保存的恢复状态。

本 Aspect 不改 router、应用壳、测试计划、测试菜单、八类测试页、LLM 执行层或生产后端。Aspect 5–8 的页面结构、工作流迁移和内容呈现不在本次范围。

## 2. 真实入口与恢复路径

登录页有三个互不混淆的入口：

1. 浏览器存在 setup 状态时，显示“继续上次项目”、完整项目 ID、保留状态和复制操作；页面加载本身不发请求。
2. “打开已有项目”先校验 `Ez` 加 19 位数字，再读取 login 和 setup status。`setup_complete` 进入测试计划，未完成项目进入 `/create`。
3. “创建新项目”进入全新资料流程；若本机已有恢复指针，必须先明确确认清除。清除只影响浏览器，不会删除服务器上的项目或文档。

切换到另一个未完成项目也必须确认。取消确认不会覆盖 localStorage，旧项目 ID 会在确认文案中保持可见。

## 3. 创建、上传与部分恢复

三个文档组继续对应生产 doctype：测试知识库 1、业务需求 2、开发设计 3。三组均至少需要一个文件，顺序仍为知识库 → 需求 → 设计 → status → finalize。

- 项目名称为 1–80 字符，拒绝斜杠和控制字符。
- 支持 txt、pdf、md、doc、docx；知识库单文件 50MB，需求和设计单文件 10MB。
- 上传进度只显示真实的当前文件序号、总文件数和文件名，不伪造字节百分比。
- 每个文件成功后立即在 `documentFiles` 中持久化；部分上传失败会指出具体文档组。
- 重试使用与生产后端一致的文件名规范化规则，跳过已成功文件。已上传文件固定标记“已上传并将在重试时复用”。
- 本地 `File` 对象不会写入 localStorage，刷新后未上传文件必须重新选择；服务端已完成文件仍通过 setup status 恢复。
- 三组资料确认后显示“项目资料已确认，尚未开始模型分析”。进入测试计划仍需显式按钮，不会自动启动模型分析。

项目 ID 始终使用等宽字体完整显示，支持复制，并提醒用户妥善保存且不要公开分享。本 Aspect 不增加项目 ID 下载文件。

## 4. 组件契约

- `OnboardingShell`：提供品牌区、唯一 `<h1>`、主内容和可选 secondary slot；无业务请求和路由逻辑。
- `ProjectIdDisplay`：负责项目 ID、复制、保存指导和 `aria-live` 结果；每个实例使用独立 heading ID。
- `DocumentUploadGroup`：使用 `modelValue/update:modelValue` 管理受控文件列表，展示状态、服务端文件、待上传文件、进度和错误；不拥有上传、retry 或 finalize 判断。
- `FeedbackState` 与 `WorkflowActionBar`：继续复用 Aspect 3 的状态语义与移动端按钮规则。

页面和状态层继续拥有所有写入判断。共享组件不得隐式注册项目、上传文档、确认资料或触发模型。

## 5. 响应式与可访问性矩阵

| 视口 | 入口/创建布局 | 重点验收 |
|---|---|---|
| 360×800 | 单列卡片、全宽操作、文档组纵向排列 | 无横向滚动；label、alert、文件名完整换行 |
| 768×1024 | 单列创建流程，扩大 gutter | 文件选择、确认框、恢复错误和键盘 focus 可用 |
| 1024×768 | 登录入口可双栏；恢复页保持 960px 阅读列 | 已完成组无 file input，服务端文件清单明确 |
| 1440×900 | 内容居中，失败组保持单一阅读焦点 | 部分上传成功、失败原因、复用文件和待重试文件同时可见 |
| 1920×1080 | 1200px 外层、960px 表单列 | 完成 dialog、项目 ID 复制、步骤和显式前往计划清晰 |

所有表单使用语义化 `<form>`、显式 label、Enter 提交和持久错误反馈。loading 使用 status，错误使用 alert；状态不只依赖颜色。上传或 finalize 进行中阻止路由离开并注册 `beforeunload`，结束时清理监听器。全局 focus-visible 与 reduced-motion 继续由 Aspect 1 基础提供。

## 6. 离线夹具和安全边界

离线创建闭环必须显式使用：

```text
python scripts/frontend_fixture_server.py --port 18130 --origin-port 18080 --enable-onboarding --fail-upload-once requirements
```

未启用 `--enable-onboarding` 时，夹具继续拒绝 add/upload/finalize。启用后只在当前 Python 进程内保存合成项目名、规范化文件名、完成阶段和一次性失败状态；文件正文不保留，进程退出即清空。fixture 只绑定 `127.0.0.1`，不读取 `.env`、不导入生产后端、不访问 MySQL、模型或 embedding。

## 7. 兼容性与非目标

- 生产路径、响应 envelope、三类 doctype、finalize 时序和 `projectSetup.ts` 原公开方法保持兼容。
- localStorage 新字段对旧快照补默认值；遗留 `running` 在恢复时降为 `pending`，再由服务端 status 校准。
- 19 个 workflow、路由守卫、REST/SSE、缓存、artifact revision、session-only、取消、stale 和 regeneration lock 不变。
- 不新增依赖、字体、图标、测试框架或后端接口；不修改 package manifests。
- 不实施 Aspect 5–8，不重做测试计划、测试菜单、其他工作区或 LLM 反馈层。
