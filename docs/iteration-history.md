# 迭代历史

> 更新：2026-09-09。本文整理目标、变化、决策和收口边界；具体数值及证据等级以[验证历史](validation-history.md#evidence-classes)为准，当前运行方法见[项目设计](project-design.md#startup)。历史“未提交”“待启动”等状态只描述当时的记录，不覆盖本页当前状态。

## 目录

- [Iteration 1：复现与流式工作流](#iteration-1)
- [Iteration 2：可恢复结果与成本控制](#iteration-2)
- [Iteration 3：工作台体验](#iteration-3)
- [Iteration 4：受控 Agent](#iteration-4)
- [Iteration 5：工程治理与未完成交付](#iteration-5)
- [Iteration 6：本地运行与中文说明](#iteration-6)
- [Iteration 7：可读性迭代](#iteration-7)
- [方面五记录](#iteration7-aspect5)
- [方面六记录](#iteration7-aspect6)
- [历史截图](#historical-images)
- [来源与原件恢复](#historical-sources)

<a id="iteration-1"></a>
## Iteration 1：复现与流式工作流

在 Windows 复现 Python/FastAPI、Vue/MySQL 组合，迁移到 LangChain Core 1.x/LCEL、Pydantic 2、SQLAlchemy 2，建立四供应商模型注册和脱敏错误。项目入口改为先生成摘要、计划和推荐菜单，再开放下游测试；通用 stream 覆盖八类测试的 18 个操作。

延迟原子保存、取消、进度/推理/正文/用量展示保持原 REST、响应信封、项目标识和 InfoType 兼容。历史收口记录后端 131 项通过，lint/build 通过；最后流式回归没有真实模型调用。早期单独获准的供应商连通性烟测，不构成 19 workflows × 四家模型的完整付费 E2E。

当时的遗留包括按 InfoType 的粗粒度缓存、重复 embedding、上下文重发及恢复不统一，成为 Iteration 2 输入。50 项生成文件处理是索引清理、保留本机副本；不是后来清理数据的授权。

<a id="iteration-2"></a>
## Iteration 2：可恢复结果与成本控制

建立 19 workflow catalog、revision-aware artifact、资料组上传恢复、统一准备状态、项目初始分析合并、索引复用及阶段预算。缓存按项目、revision、提示词版本、模型与输入选择隔离；失败重生成不覆盖有效资产。

六张旧表保持，新工作流表形成七表声明；原始初始化 SQL 含 DROP TABLE IF EXISTS，不能直接覆盖现有数据库。Task 9 收口记录真实 MySQL 结构变更和付费 A/B 未执行；后来的发布/修复记录应按各自时间阅读。

后续明确五类 final 为 session-only，UI/数据库/验收 final 持久化；qualified reference 解决同名对象选择歧义，菜单可进入与是否推荐分离。长文本分为全量抽取、聚焦检索和产物生成，完整精确缓存免除重复模型与 embedding。

离线收口记录 275 passed、1 deselected，固定 small/large 成本指标是模拟 C/E/I/O，不是供应商账单。被 deselect 的历史资料完整性断言仍保留原因，不能改成零失败全量执行。

<a id="iteration-3"></a>
## Iteration 3：工作台体验

八个方面依次完成体验基线、设计 tokens、响应式应用壳、共享交互、项目创建/恢复、计划与菜单、八类工作区、可访问性及收口。保留 19 workflows、路由守卫、缓存、revision、取消、stale、延迟保存与 regeneration lock。

历史离线结果为 355 项后端和 93 项前端契约通过，浏览器覆盖 320–1920 CSS px 的代表状态。窄屏 segmented 背景跨行缺陷通过限定装饰层规则修复；页面状态仍表达旧结果有效性、当前草稿与实际保存结果。

原收口不等于真实模型验收。浏览器文件注入超时、200% zoom 不能可靠暴露、Narrator 音频未采集仍是明确限制；multipart/恢复旅程以同一 loopback fixture 验证。后来 README 的真实 provider 代表性截图属于另一条合成旅程，不能替代 Agent E2E。

<a id="iteration-4"></a>
## Iteration 4：受控 Agent

在确定性 workflow 上增加单 Agent 编排、22 个类型化工具、可信 project scope、审批、预算、Redis 恢复、workbench、MCP、RAG/Eval 和观测。付费/持久化/regenerate 的审批绑定 plan、project、revision、model、arguments、context 与 budget，任一变化使旧审批失效。

Checkpoint 使用严格 JSON，不用 pickle、动态构造器或不受控 import；恢复先检查 fencing、幂等和有效 artifact，不确定的 session-only 结果进入 outcome_unknown，不能自动重复付费。Redis 丢失不破坏 MySQL 中有效结果。

历史证据分三层：确定性 Acceptance 18/18 与 Eval 104/104；真实 planner 从 0/6 修复为 6/6、RAG 3/3；另行批准的 ui_info → ui_case 合成 Agent E2E。数值、调用次数和环境分别保留，不合并成同一次测试。

容器、Tempo/Prometheus/Grafana 与托管 CI 是当时交付背景，当前仓库不支持据此启动容器。历史性能比较仅在固定机器/fixture/环境下有效，不能推导当前容量、客户项目质量或实时 CI 状态。

<a id="iteration-5"></a>
## Iteration 5：工程治理与未完成交付

目标是资产分类、精确依赖/版本、工程规范、领域归位、前端结构、配置隔离和双模式交付。留下的旧版本 JSON 仍引用 ez_back_dev/ez_front_dev、Dockerfile、Compose 和已退出 CI；这些已不属于当前执行真源。

Aspect 8 的历史收口为“已执行但未完成（Blocked）”。本地缺包、固定端口冲突、容器全栈和双拓扑业务 parity 未闭环；不能把 readiness、静态 ASGI 或 source-preview 记录改称完整网络 Agent E2E。仓库外报告引用的 727 passed/32 skipped、Eval 104/104、Acceptance 18/18 保持 class C。

V5 不可变归档为 5cf1effb32a8efcd34902df05d27442f3586dc1c。本轮不移动该归档，不安装依赖重跑历史环境，不把历史容器操作抄入当前启动步骤。

<a id="iteration-6"></a>
## Iteration 6：本地运行与中文说明

以固定 V5 来源建立 V6，收敛源码与数据边界、三份显式配置、模块运行器、模型选择和独立总预算、本地 SQLite 观测以及中文注释。移除外部观测和容器执行链，MySQL/Redis 仍是外部依赖。

历史注释核对为 163 个 Python 文件、902 个函数；前端 56 个文件、561 个函数节点，其中 461 个必须覆盖目标有中文 JSDoc，其余有排除分类。历史文档写 62 条 FastAPI 路由，Iteration 7 后来的实际注册核对为 63，两种记录分开保存。

当时本地 readiness 与结构/配置/预算/观测/前端门禁通过；另行获准的合成烟测记录 GLM 保存恢复、有限 embedding 和一次 RAG 超时后的唯一成功重试。原始运行报告和受保护内容未提交，所以烟测保持 class C，不提升为冻结执行 fixture。

当前基线提交为 e6c42a5f20a9a0003dc553cece16fd72a9f6aece。历史源码链接修复后的未提交正文，与该提交的旧版本并非完全相同；完整工作树原件见本轮备份规则。

<a id="iteration-7"></a>
## Iteration 7：可读性迭代

| 方面 | 状态 | 已确认结果与下一步边界 |
| --- | --- | --- |
| 一：目录与工作基线 | 完成 | 六目录职责确认；新建 codex/iteration7，基点不变；不新增占位目录 |
| 二：三端源码重组 | 完成 | 单产品包、五入口、业务归属、旧 facade 退出；后端 41/前端 5 项离线回归和工具检查 |
| 三：配置与只读验收 | 按限定范围完成 | 不消费 worker、真实配置、Windows IPC/重启重取、未登录页面与脱敏观测；后端 54/前端 5 项 |
| 四：长期文档归并 | 完成 | 三份长期文档、133 份原件备份、127 份旧文件退出；文档引用、runner 与保护核验通过 |
| 五：中文可读性深化 | 已完成 | 职责注释、执行结构与公开契约比较、离线检查及保护核验通过 |
| 六：最终清理与发布 | 本地收口完成 | 精确资产清理、最终离线门禁；本提交用于普通快进发布，远程结果以交付核验为准 |

方面一确认 backend/frontend/observability/infrastructure/ops/docs 的职责，runner 从 scripts 归 ops，前端配置工具归 frontend，基础设施仅保留有效声明。临时提示词与详细过程不再作为长期入口，原件完整备份。

方面二将 Python 源码归 backend/src/ezllmtest，领域 public/ports 明确跨域关系，ORM 归业务所有者，通用连接延迟创建；前端 pages 归 feature、共享业务状态归 entities。原数据目录保持。Windows IPC 修复了服务端提前断开导致客户端身份核验失败的竞态。

方面三明确 --no-consume 不创建消费组、不读取/认领/确认队列，不装配模型执行能力。独立 TTL 心跳不注册正常 worker；Agent /ready=503 是该范围内的预期结果。观测重启换 token、旧凭据拒绝、缓存清空、有界重取及产品 fail-open 已记录通过。SQLite 正常生命周期获准，不声称数据库字节不变。

浏览器只验证无登录项目的首页、介绍、工作台重定向及脱敏观测；既有恢复提示未打开，改用无恢复记录的 localhost 站点。验收后进程、管道与心跳退出。正常任务消费、真实模型/embedding/生成、真实项目 MCP、压力、Linux IPC、reload/多 worker 均未验证。

### 本方面实施记录

方面四开始时为 codex/iteration7、HEAD e6c42a5f20a9a0003dc553cece16fd72a9f6aece、无 upstream、暂存区为空；210 个 tracked 删除、15 个 tracked 修改、246 个 untracked 条目与方面三收口数量一致，不据此声称原文逐字节无漂移。

133 份普通原件已精确备份：115 份 docs Markdown、10 张图片、1 份图片清单及七个直接消费者/旧 JSON。原白名单为 132 份；引用检查发现 frontend/README.md 的六处链接后暂停，经用户确认追加该原件，只修正六处文档引用。已解码检查正文，43 份明确重定向的目标与循环检查通过，全部原件有章节去向和退出条件。用户选择保留结论、完整原证据表与出处，不全文拼接过程日志。

当前运行说明集中到 project-design；旧 ops JSON 仅保留固定提交出处。runtime 声明只调整运行指南和历史版本出处两个字段，与本方面原件比较的其余解析结果完全一致。

已逐文件退出 125 份 docs 原件和两个 ops JSON，再非递归删除 13 个已检查为空的 docs 子目录。docs 恰有三份长期 Markdown，无子目录；排除依赖、项目、数据、日志与旧备份的普通目录空目录检查结果为零。保留 19 张历史证据表及原验证文档关键字面值；54 处本地链接、43 个固定 Git 对象和围栏、表格、显式锚点、UTF-8/LF 检查通过。退出后仅运行相关 runner 离线用例，1 passed（0.08 s）；未运行整套产品测试或构建、服务或浏览器。

最终 Git 可见状态为 335 个 tracked 删除、17 个 tracked 修改、246 个 untracked 条目；这些包括方面二、三既有修改，不是本方面独自产生。暂存区为空，分支与 HEAD 基点不变，全部既有本地引用及重新查询的远程基线未变，无提交或发布。V6 白名单外普通文件及 Git-visible 状态保持，V2 精确排除本批次后的 Git-visible 状态、分支与 HEAD 与实施前内存快照一致；该核验不表示受保护资产的全量字节一致。

方面五、六只接收以上事实与未验证项，不自动恢复容器、模板目录、真实任务验收或发布授权。


<a id="iteration7-aspect5"></a>
### 方面五：中文说明与可读性深化

本方面仅更新注释和维护说明，未重命名、拆分函数或修改表达式、控制流、提示词、页面文案、配置值、依赖及 JSON 契约。入口配置、Windows IPC、租约与审批、预算、恢复、项目 revision、检索复用、生成保存、前端草稿与有效结果、SSE 和进程归属的说明随现有职责补齐。公开类/路由描述保留原始字节；过时的“旧 import facade 仍存在”等模块说明已纠正。

本次审阅清单为 265 份普通文件：264 份原件逐文件备份，纯 template 的 AboutView 不改也不纳入备份。最终修改 249 份文件；其中 170 份 Python、68 份前端脚本/声明或 Vue、七份包装/SQL/独立 CSS，以及四份长期说明/README。15 份已备份原件在审阅后保留不变，不为满足计数制造修改。没有删除文件、目录或新建产品源码。

| 分类 | Python（185 文件，1203 节点） | 前端（68 文件，602 节点） |
| --- | --- | --- |
| 已有有效说明或由所属接口覆盖 | 36 | 158 |
| 补充完成 | 173 | 89 |
| 重写完成 | 974 | 300 |
| 有具体理由的豁免 | 20 | 55 |

Python 计数包含两个同名 overload 声明，不能按函数名去重后漏掉；前端包含 579 个函数体与 23 个类型签名。豁免限于纯取值、转换和展示派生，涉及 IO、审批、预算、保存、取消、队列、token 或进程归属的节点有对应说明。分类与中文出现次数是不同口径，详见[本次验证](validation-history.md#iteration7-aspect5)和[注释规范](project-design.md#chinese-comments)。

后端本次 54 项、前端本次 5 项离线用例通过，类型检查、无自动修复 lint 和执行结构/公开契约比较通过。最初五个帮助子进程用例因父子进程编码不一致失败；已保留失败记录，用户允许仅为临时测试设置 PYTHONUTF8=1 后重跑通过，没有修改持久环境。未运行完整前端构建、服务、浏览器或真实配置验收。

本机追加批次：D:\codex\EzllmTest_v2\_archive\iteration-7\aspect-5-20260909T072901645445Z-160ae57111864994a3468c361a97fadd。manifest.json 保留 264 份原始字节 SHA-256 与副本校验；evidence 记录逐节点分类、公开契约及前后结构比较。本批次为本机未提交记录，不提升历史证据等级，旧备份未展开或重新计算哈希。

收口保护核验通过：V6 暂存区为空，HEAD、分支及既有引用未变；V2 排除本轮精确备份批次后，Git-visible 状态、分支和 HEAD 与实施前内存快照一致。这不构成受保护资产的全量字节一致性证明。方面六仍未开始。当前检查记录 frontend/src/assets 为空，仅记录、不删除。方面五没有在 V6 创建目录或删除文件，未新增无用途空目录；Git 本身不能记录空目录来源，不用本次观察改写方面四的历史统计。


<a id="iteration7-aspect6"></a>
### 方面六：最终清理与发布交接

本地收口完成，本提交用于普通快进发布。远程发布和本地 main 同步的最终结果，以交付时重新查询的引用及本机 evidence/release-result.json 为准；本文不提前声明推送成功，也不嵌入自身提交 SHA。

本方面从 codex/iteration7、基点 e6c42a5f20a9a0003dc553cece16fd72a9f6aece、无 upstream 和空暂存区接续方面二至五的累计修改。初始 Git-visible 状态为 335 个 tracked 删除、37 个 tracked 修改、246 个 untracked；这些不是本方面独自产生。没有切换工作树或修改产品行为。

**前序检查更正：**方面五将 frontend/src/assets 记录为空是错误结论。方面六复核发现该目录实际含五份 tracked 字体和图片，均与基点 Git Blob 一致，当前代码使用 shared/assets 等所属资源。经用户确认，逐项核对静态、CSS、动态路径和工具/文档消费者并精确备份后，才删除五份原件，再非递归删除四个确认变空的目录；没有将非空目录按空目录处理。

| 退出资产 | 基线 Blob OID | 历史出处 |
| --- | --- | --- |
| AlimamaFangYuan.ttf | d7dc77355ff92e48d8b15411708d364e4934d1d0 | [固定原件](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/frontend/src/assets/static/font/AlimamaFangYuan.ttf) |
| SanJiBangKaiJianTi.ttf | f3fa82366c633d4485589acd8f9483436dbba4f8 | [固定原件](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/frontend/src/assets/static/font/SanJiBangKaiJianTi.ttf) |
| ezlogo-workbench.png | daceb7c40b6011e19981e2cdff3ee26e228447f9 | [固定原件](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/frontend/src/assets/static/image/ezlogo-workbench.png) |
| ezlogo.png | bf0426e9011368943e549e0773e7f20d083e3b1b | [固定原件](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/frontend/src/assets/static/image/ezlogo.png) |
| logo.png | f3d2503fc2a44b5053b0837ebea6e87a2d339a43 | [固定原件](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/frontend/src/assets/static/image/logo.png) |

.prettierignore 仅退出 assets 及六条旧源码规则；shims-vue.d.ts 的已有格式豁免继续保留。首次暂存前检查发现 backend/tests/test_contracts.py 第 8、37 行存在原有尾随空格，按计划暂停。用户随后允许补充备份，仅删除两个空白行中的空格；Python AST 一致，相关契约用例重跑通过。没有格式化其他源码。

正式暂存检查随后发现 24 份新 Python 源码末尾多余空行，再次按计划暂停。用户确认后逐份补充备份，仅删除多余末尾换行、保留一个 LF；包含 docstring 的完整 AST 保持一致。原始失败、精确清单和重试结果均保留。

本轮普通原件由十份经两次授权追加至三十五份，均按原始字节复制并校验 SHA-256。本机恢复位置：D:\codex\EzllmTest_v2\_archive\iteration-7\aspect-6-20260909T084355004418Z-53288bc6bb2449a5bdda63064b8b2615。既有备份未展开或重新哈希，真实配置、根 .env.aspect3.local、项目、数据、日志、依赖及已有 frontend/dist 原地保护。构建仅使用本批次人工配置和新输出目录。

本次离线结果及限制见[方面六验证](validation-history.md#iteration7-aspect6)。发布只创建一个 iteration7 提交，普通原子推送同一提交到远程 iteration7/main；确认远程后设置 upstream，并检查旧值与祖先关系后快进本地 main。V6 保持 iteration7，iteration6 与 V5 归档不移动。不 force-push、fetch、创建 tag 或 GitHub Release。

<a id="historical-images"></a>
## 历史截图

以下为 Iteration 3 的虚构 Aurora 项目代表性旅程，截图生成于 2026-08-25，非当前界面截图，也不是 Iteration 4 Agent E2E 证据。图片已从 docs 退出，链接固定到经过对象核对的历史提交；不自动加载图片。视口、operation、模型、时间与脱敏方式见[原始图片清单](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/manifest.json)。

| 截图 | 路由 | 视口 | operation / 模型 | 脱敏说明 |
| --- | --- | --- | --- | --- |
| [01-login.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/01-login.png) | / | 1440×900 | none / none | none |
| [02-project-setup.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/02-project-setup.png) | /create | 1440×900 | project_setup / none | project ID masked |
| [03-plan-running.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/03-plan-running.png) | /plan | 1440×900 | project_analysis / GLM-4.7 | project ID masked |
| [04-plan-saved.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/04-plan-saved.png) | /plan | 1440×900 | project_analysis / GLM-4.7 | project ID masked |
| [05-test-menu.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/05-test-menu.png) | /menu | 1440×900 | project_analysis / GLM-4.7 | project ID masked |
| [06-unit-analysis.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/06-unit-analysis.png) | /unit | 1440×900 | unit_info / GLM-4.7 | project ID masked |
| [07-unit-cases.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/07-unit-cases.png) | /unit | 1440×900 | unit_case / GLM-4.7 | project ID outside viewport |
| [08-api-session-only.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/08-api-session-only.png) | /api | 1440×900 | api_case / GLM-4.7 | project ID masked |
| [09-ui-persisted.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/09-ui-persisted.png) | /ui | 1440×900 | ui_case / GLM-4.7 | project ID outside viewport |
| [10-mobile-navigation.png](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/images/readme/10-mobile-navigation.png) | /ui | 390×844 | ui_case / GLM-4.7 | project ID masked |

<a id="historical-sources"></a>
## 来源与原件恢复

| 内容 | 固定历史出处 |
| --- | --- |
| Iteration 1 完成与遗留 | [收口](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-1/iteration-1-closeout.md) |
| Iteration 2 决策与成本 | [收口](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-2/iteration-2-closeout.md)、[逐工作流基线](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-2/iteration-2-token-baseline.md) |
| Iteration 3 体验与限制 | [收口](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-3/iteration-3-closeout.md) |
| Iteration 4 受控 Agent | [收口](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-closeout.md)、[真实合成验收](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-live-model-acceptance.md) |
| Iteration 5 Blocked | [收口](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/development/iteration-5/closeout.md)、[source preview](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/development/iteration-5/source-preview-v0.1.0-preview.1.md) |
| Iteration 6 | [基线提交收口原文](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/iteration-6-closeout.md) |
| 旧运行/版本 JSON | [旧 runtime](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/ops/modular-runtime-contract.json)、[旧版本契约](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/ops/version-contract.json) |
| 更早过程、计划、提示词 | [基线完整 docs 树](https://github.com/Jaily16/EzllmTest/tree/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs)，非当前启动指南 |

历史链接表示对应提交的原文，不保证等于本轮实施前的工作树内容。七份原件与 HEAD 的字节不同，其中包括两份未提交规划文档；它们的精确原件均保留在本轮 before，而不是虚构新的 GitHub 提交。

本机恢复批次：D:\codex\EzllmTest_v2\_archive\iteration-7\aspect-4-20260909T064721917641Z-a322db08b41b4901bce32e31d5300d8b。该路径是本机追加备份，不要求其他开发者能访问。manifest.json 列出全部 133 份原件的原始字节 SHA-256 和复制校验；evidence/migration-map.json 列出每份原路径、重定向正文、目标章节、历史对象、与 HEAD 是否逐字节相同及保留约束。源码中提及的旧批次只确认存在，未展开或重新哈希。

本轮原始字节哈希与验证历史的 sha256_canonical_lf_v1、各历史 manifest 的自有口径不同，不覆盖原证据哈希。GitHub 私有页面的 HTTP 可访问性本轮未验证；本地对象存在性与类型已核对。两份临时规划的原始提示词通过精确原件保留，长期文档承接其决策和后续交接。
