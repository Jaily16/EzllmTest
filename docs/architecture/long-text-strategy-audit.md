# 长文本调用策略审计

日期：2026-08-21

## 决策结论

当前 19 个流式工作流采用三类处理方式：

- **全量抽取**：资料在应用安全预算内时直接 `stuff`，保留完整跨章节关系；超过预算时使用分层 `map-reduce`。
- **聚焦查询**：先按项目、语料和文档版本复用检索索引，去重并限制相关上下文，再执行一次 `stuff`。已经被检索限定的结果不再二次 `map-reduce`。
- **产物生成**：测试用例从已保存的分析产物、用户选择和少量知识库检索结果生成，使用 `artifact-stuff`，不重新塞入全部业务文档。

当前没有生产工作流采用 `refine`。这些任务需要合并相互独立、可能跨章节的证据；`refine` 会把结果绑定到文档顺序，并让前面结论被后续块反复改写。只有未来出现“按固定版本顺序逐步修订同一份文稿”的任务时，才应考虑 `refine`。

应用预算是跨供应商的保守上限，不等于模型宣传窗口：项目级全量输入为 64,000 Token，其他全量分析为 32,000 Token，测试用例产物为 16,000 Token。每次请求还会按模型预留输出、思考和至少 10% 的安全空间。

## 19 个工作流决策表

| 工作流 | 长文本来源 | 当前策略 | 超限处理和理由 |
| --- | --- | --- | --- |
| `project_analysis` | 全部需求与设计资料 | `stuff` ≤ 64K | 超限后分层 `map-reduce`；项目测试范围需要完整跨文档证据 |
| `unit_menu` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`；需要穷举模块、组件、类和服务 |
| `unit_info` | 所选单元相关设计资料 | `retrieval-stuff` | 先检索指定单元，避免无关模块占用上下文 |
| `unit_case` | 单元分析产物、方法选择、测试知识 | `artifact-stuff` ≤ 16K | 不重新读取全量设计资料 |
| `integration_menu` | 已保存的单元菜单；缺失时为全部设计资料 | `artifact-stuff`；回退全量时 `stuff` ≤ 32K | 全量回退超限后分层 `map-reduce` |
| `integration_info` | 系统/子系统选择为全设计；具名对象为相关设计 | 全量 `stuff` ≤ 32K；具名对象 `retrieval-stuff` | 只有系统级穷举超限时分层 `map-reduce` |
| `integration_case` | 集成对象分析、策略选择、测试知识 | `artifact-stuff` ≤ 16K | 依赖规范化上游产物，不重复全量设计资料 |
| `api_info` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，用于穷举 API |
| `api_case` | API 分析产物；指定 API 时补充相关设计 | `artifact-stuff` + `retrieval-stuff` | 只检索选中 API，不对检索结果再 map |
| `ui_info` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，用于穷举页面和交互 |
| `ui_case` | UI 分析产物和测试知识 | `artifact-stuff` ≤ 16K | 不重复全量设计资料 |
| `db_info` | 全部设计资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，使用数据库语义切分器 |
| `db_case` | 数据库分析产物和测试知识 | `artifact-stuff` ≤ 16K | 不重复全量设计资料 |
| `functional_info` | 全部需求资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，用于穷举用例和业务规则 |
| `functional_case` | 功能分析产物；指定用例时补充相关需求 | `artifact-stuff` + `retrieval-stuff` | 只检索选中用例，不对检索结果再 map |
| `nonfunctional_info` | 与性能、安全、兼容性等问题相关的需求 | `retrieval-stuff` | 这是聚焦问题，不应摘要全部需求后再回答 |
| `nonfunctional_case` | 非功能分析产物、方法选择和测试知识 | `artifact-stuff` ≤ 16K | 只合并所选方法需要的上下文 |
| `acceptance_info` | 全部需求资料 | `stuff` ≤ 32K | 超限后分层 `map-reduce`，保留验收条件覆盖 |
| `acceptance_case` | 验收分析产物和测试知识 | `artifact-stuff` ≤ 16K | 不重复全量需求资料 |

所有需要结构化列表或菜单的流程仍可能在正文分析后增加一次结构化解析调用；这不是第二次长文档分析。相同文档版本和选择命中完整产物缓存时，恢复路径保持 0 次模型调用和 0 次 embedding 构建。

## 模型上下文兼容性

| 平台标签 / 默认模型 | 记录的上下文窗口 | 记录的最大输出 | 与应用预算的关系 |
| --- | ---: | ---: | --- |
| GLM-4.7 / `glm-4.7` | 200K | 128K | 最小窗口基准；64K/32K/16K 均留有充足输出与思考余量 |
| 通义千问 / `qwen3.5-plus` | 1M | 65,536 | 覆盖全部应用预算；最终阶段思考预算仍限制为 4,096 |
| DeepSeek / `deepseek-v4-flash` | 1M | 384K | 覆盖全部应用预算；map/结构化阶段显式关闭 thinking |
| Moonshot Kimi / `kimi-k2.5` | 256K | 32,768（应用保守值） | 覆盖全部应用预算；保留输出、思考和安全空间后仍高于 64K |

能力记录来源：[GLM-4.7 官方文档](https://docs.bigmodel.cn/cn/guide/models/text/glm-4.7)、[Qwen3.5 Plus 官方文档](https://help.aliyun.com/zh/model-studio/qwen3-5-plus)、[DeepSeek 官方定价与模型规格](https://api-docs.deepseek.com/quick_start/pricing/)、[Moonshot Kimi 官方论坛的 K2.5 上下文说明](https://forum.moonshot.ai/t/on-99-plan-but-ran-out-of-quota-in-3-days/287)。LangChain/LangGraph 的对应模式参考：[map-reduce/Send](https://docs.langchain.com/oss/python/langgraph/use-graph-api)、[检索与文本切分](https://docs.langchain.com/oss/python/langchain/retrieval)、[长上下文的注意力与成本问题](https://docs.langchain.com/oss/python/concepts/memory)。

这里的能力元数据与平台默认模型绑定。如果管理员通过环境变量把某个标签改成窗口更小的其他部署，必须同步更新模型能力元数据；系统不会读取供应商账户来自动推断私有部署窗口。

## CC4C 测试菜单误判修复

原逻辑由模型摘要直接决定 `unit_test` 和 `integration_test`。CC4C 的需求与设计资料合计约 42K Token，旧的 14,500 Token 阈值触发多次短 map 摘要，模块、分层、接口和调用关系可能在摘要中丢失，最终把两项写成 `false`。

现在项目分析在 64K 内直接读取完整资料，并在模型菜单之后增加只修复假阴性的确定性证据守卫：

- 单元测试：子系统、模块/组件、类/函数/服务、分层四类信号中至少两类；
- 集成测试：架构、边界接口、多单元、调用/依赖/交互四类信号中至少三类，且必须包含关系信号；
- 守卫只允许把有充分证据的 `false` 修复成 `true`，绝不会把模型的 `true` 改成 `false`。

运行时只保留信号类别和菜单布尔值，不保存命中的业务原文。新分析会把修复后的菜单按原 JSON 结构写入现有产物和兼容 `InfoType` 行；读取旧缓存或项目状态时也会在内存中修复路由权限，因此不需要修改 REST/SSE、数据库表或前端守卫协议。

## 分层 map-reduce 的安全行为

- 指令与业务上下文分离计量，业务上下文缩减不会截断输出格式和结构化约束。
- 过大的源块继续按当前业务切分器拆分，保持原顺序，不丢中间章节。
- map 摘要先按 reduce 预算分批归并，再逐层归并到一次最终 reduce；所有层级都计入调用和 Token 用量。
- 同步旧接口使用相同策略适配器和分层归并，保留原函数签名与返回结构。
- 如果单份 map 输出已经超过 reduce 输入预算，或八层内不能收敛，调用明确失败；不会静默截断业务证据。

## 离线基线

固定小/大文档、mock chat、mock embedding 的最新首次执行总计为：

| 夹具 | Chat 调用 | Embedding 构建 | 输入上下文 Token | 输出上限合计 |
| --- | ---: | ---: | ---: | ---: |
| Small | 39 | 13 | 20,408 | 219,648 |
| Large | 39 | 13 | 227,588 | 219,648 |

Large 夹具在安全窗口内优先保留完整输入，因此输入 Token 高于旧的有损摘要路径，但模型调用和输出上限显著下降。所有 19 个工作流的同版本重复执行仍为 `0/0/0/0`。基线仅保存工作流名、夹具名和数字计数，不含 prompt 正文、业务文档、reasoning、向量、凭证或供应商异常正文。
