# 验证历史

> 本文是历史审计索引，不是新的测试执行报告。最初采集于 2026-09-03，Iteration 6 补充于 2026-09-07，Iteration 7 文档归并于 2026-09-09。原 Iteration 6 evidence baseline 为 b34a188ac1b5c98e869837009561f47363336821；S23 是后续收口补充，具体 Blob OID 单列。不可变 V5 来源为 5cf1effb32a8efcd34902df05d27442f3586dc1c。

## 目录

- [证据等级与保护口径](#evidence-classes)
- [完整来源清单](#source-inventory)
- [历史结果与测量方法](#historical-results)
- [性能、体积和真实合成验收](#performance-model)
- [Iteration 6 补充](#iteration-6)
- [Iteration 7 分方面记录](#iteration-7)
- [方面五本次核验](#iteration7-aspect5)
- [方面六本次核验](#iteration7-aspect6)
- [限制与解释](#limitations)

<a id="evidence-classes"></a>
## 证据等级与保护口径

下表保留原等级定义与英文术语：A 为冻结结构化证据，B 为有冻结证据关联的 tracked 正文，C 为未能在仓库内独立审计的记录，D 为缺失或 Blocked，P 为主动排除的受保护资料。

| Class | Label | Meaning |
| --- | --- | --- |
| A | `[Verified]` frozen structured evidence | A tracked JSON fixture or manifest directly contains the stated value. |
| B | `[Verified]` corroborated tracked narrative | A canonical tracked document records the event and is linked or hashed by frozen evidence. |
| C | `[Candidate]` recorded result | A tracked log cites a repository-external report that is not available in this repository for independent audit. |
| D | `[Missing]` / `Blocked` | The run was not completed, the raw evidence is unavailable, or the repository cannot prove the claim. |
| P | `[Protected]` | The source is deliberately excluded from content, size, and hash inspection. |

class C 不提升为 A/B；历史通过不等于当前工作树通过。离线契约、真实配置 readiness、浏览器展示、真实模型合成旅程及生产质量是不同证据层，不能互相替代。

原文中“Aspect 2 未读取/哈希或运行”和“Aspect 3 移除验证源码”描述 Iteration 6 当时的文档整理步骤，非 Iteration 7 同名方面。原历史步骤未读取真实环境、项目、MySQL/Redis/观测数据、归档、隔离资料、日志或仓库外报告，也未运行测试/build/服务/容器/provider/embedding。Iteration 7 方面三后来获准的真实配置加载和 SQLite 正常生命周期单独记录，不反向改写历史保护声明。

本次方面四只读取获准普通文档、源码及声明；真实 .env、秘密引用、项目、数据库、日志和旧备份正文均不是核验输入。

<a id="source-inventory"></a>
## 完整来源清单

原策略 sha256_canonical_lf_v1：文本规范为 UTF-8/LF 和一个末尾换行；JSON 解码后按键排序、紧凑序列化。Blob OID 指向记录时的精确 Git 对象。历史 manifest 自有哈希口径单独保留，不被本轮原始字节备份哈希覆盖。

旧相对文档链接现固定到本地核对的提交；被移除的验证源码仍固定到 V5 快照。S01–S23、Blob OID、哈希及原表均保留。链接替换只是出处维护，不是重新执行证据。S23 对应 e6c42a5 收口对象；总表早期 baseline 不应被误读为该补充已经存在于 b34a188。

| ID | Canonical source | Blob OID | `sha256_canonical_lf_v1` |
| --- | --- | --- | --- |
| S01 | [Iteration 4 measurement protocol](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-measurement-protocol.md) | `789d5307a8c6cb22833ad6d5c558d3c93ef91028` | `7b31343bda8dcd9dcaa4643ee5ad883821014b70722ef150daa27764e4909d9a` |
| S02 | [Iteration 4 development log](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-development-log.md) | `605883eb168709ba96f1587a1a596fedc14608d0` | `f0880178e1b9911f197a7cf98d0991262cbbd17f4121f11bc66d8645d3746b8f` |
| S03 | [Iteration 4 closeout](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-closeout.md) | `eddb4d9dee7ed91661480f15e73985fbd3099f03` | `309d5cc938f06a13761aaeb365c5eef9c1c96958fafb168f4d317642354d8ea7` |
| S04 | [Iteration 4 live-model acceptance](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-live-model-acceptance.md) | `d6e4565ac3d580b6f8ffce6dcd10304296fce67c` | `e085676e0594bbef5045b6852934ceba024b2e3fd68c3acb6f9e0984c24778af` |
| S05 | [Iteration 4 Eval/security contract](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-aspect-6-eval-security-contract.md) | `b38f3ef51100ad9211b04f93cd1584cde4c0d09c` | `213a23edeaa1045966554dac96361e4059733e554a7fdd4d2ae27b08a02d1286` |
| S06 | [Iteration 4 observability/delivery contract](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/history/iteration-4/iteration-4-aspect-7-observability-delivery-contract.md) | `9d15b1dbb797536cf045612778a41a36bf445029` | `7e8cd895e041f9e2c43129eb0d61489236d949621c0b95f2e96dd9084626f476` |
| S07 | [Acceptance dataset](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_agent_acceptance_v1.json) | `30c5798a3a59b127c2ab90dcff78d1af26ecc8a5` | `6b6e6c8205c8fe2c2a44777e087ca555fc4872a71d32b9d2a55bbb17dfc60e74` |
| S08 | [Eval dataset v2](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_agent_eval_v2.json) | `7b80a5e4c8d93b77ab53182f3dec4896adcf8496` | `4240f1a0e63241f8661f6111875b3428d0b64ba7f0a0c841621db6c66f3ec14b` |
| S09 | [Aspect 6 gate](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect6_gate_v1.json) | `10af3c361b739b25459b2c6e8d8a6a743ac6d5d9` | `e45b601372557a2caad8d7d80529375555c816d0046336f96a58b3a0a0954700` |
| S10 | [Aspect 6 manifest](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect6_manifest_v1.json) | `f7f6f815423f1b4c63c4fe918630a77d10b32198` | `9bc830fe5be3f99d9106aaddbe3080323962ecced0a59845824c7f7e5e8ed6b2` |
| S11 | [Aspect 7 pre-change performance](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect7_prechange_performance_v1.json) | `6eaedde6378c277df6ea5f6e42590e4857b6b11b` | `8c486712a8f33044c0f18d4eb1eb747e1f8de206d13a0ca1b2f341070edd69ad` |
| S12 | [Aspect 7 performance gate](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect7_performance_gate_v1.json) | `076d58e9782dd2e629b452726ac064cea990a4b4` | `ab9593258111f170a25ced2955ea441a9a7379717583b2a8e80f571c6cedb6ff` |
| S13 | [Aspect 8 gate](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect8_gate_v1.json) | `5dc2db148be74ba838117566fc1110975fb7032c` | `032792dc6803e1730a945a9dffb1f97541cc285db9a459601de990cb88926647` |
| S14 | [Aspect 8 manifest](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_aspect8_manifest_v1.json) | `1dcd842e22e4b671fc16ba4c6e08145bb47040f2` | `068c76a9c531f8d2178bddcbcabe8ba38181761a2a5b6fbb440c4de7b988fadb` |
| S15 | [Iteration 4 release manifest](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/historical/iteration4/iteration4_release_manifest_v1.json) | `747f42ca0fa5342ec236d52aa157517315793405` | `8a3bd176e77c85d7393e1e84040f8d181a5c938267e8d98b64fb89f25a4b9235` |
| S16 | [Iteration 5 development log](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/development/iteration-5/development-log.md) | `124bcb325d7c673beed782a18418bb69dd82acfc` | `8264d42d22df130d98a78bc3725bbb0f1db664831662d6129423a9d5e8f6e505` |
| S17 | [Iteration 5 closeout](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/development/iteration-5/closeout.md) | `e00f7280ef32fa0627166e2268abbf61df99f742` | `ecd0aa21e99575eb263224cfa44adfc5fd7adeaaf06649f15f7ac814ddb0f321` |
| S18 | [Iteration 5 source preview](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/development/iteration-5/source-preview-v0.1.0-preview.1.md) | `93d31abaa9fadd6efe571b9d9d4f3fe7ea5f9524` | `61566abaf2de40bf49ee5481c119fb9fde8f239010bc11a290b054edbfe8ca71` |
| S19 | [Iteration 5 dual-mode baseline](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/tests/fixtures/current/iteration5/iteration5_dual_mode_acceptance_baseline_v1.json) | `44db1809339a1cfb64ac7b9306935390eaa2b77b` | `a2f76a5c8a464a7a7c75cb8c5140d9d7bfdf874c12f4c3c0a92906ec9d5e0683` |
| S20 | [Benchmark CLI](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/app/agentBenchmark.py) | `0d435b1a347f3b7720ba79881d89b96c3bed585b` | `96fb1630bcbb98406ac1837b1dd2b44ea0a21d67cc18a3d8590b99ee9d196f5f` |
| S21 | [Benchmark runner](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/service/agentBenchmarkRunner.py) | `18e4ccf82743e1f4859814bb427cbc35d02de17a` | `711006c36af2112d231c2a42b5c02c3bf62efcc6e3e9c861f2e8546f65c2b0b2` |
| S22 | [Benchmark contracts](https://github.com/Jaily16/EzllmTest/blob/5cf1effb32a8efcd34902df05d27442f3586dc1c/ez_back_dev/service/agentBenchmarkContracts.py) | `6d09f5454ba47eda06ee4ce3129ad4ea6611f100` | `c3b39420f82d5d1b5339ff5144cd20656386a4aa9da0dacb977f8d380de0ab02` |
| S23 | [Iteration 6 closeout](https://github.com/Jaily16/EzllmTest/blob/e6c42a5f20a9a0003dc553cece16fd72a9f6aece/docs/iteration-6-closeout.md) | `0852b878adab8ff658e833aed6031f505dfcc6ee` | `5d87a93c8fa8e7a34938823539d6ffb15ac0f9e5a6e8aa2f017d7410139a6f8e` |

Aspect 8 manifest 对 S07 记录的 SHA-256 为 `44d8cad27aa17365a6aa85300a2a7261275438ae162d3da316371b0eff4e1674`，同时对应原始文件和 canonical-LF 文本；表中 S07 则是 canonical-JSON。两值策略不同，必须并列保留。[S07, S14]

<a id="historical-results"></a>
## 历史结果与测量方法

冻结性能环境为 Windows build 26200、AMD64、Python 3.11.15、Node 24.18.0、Docker client/server 28.0.4，是当时采集值，本方面未启动或复现该环境。[S11]

固定 protocol 使用 seed 20260827、5 次 warm-up 后测量 30 次、不丢离群值、并发 1/4、small/large 合成输入及 nearest-rank p50/p95。相对门槛要求同机器、fixture、命令、并发和环境；绝对时间不能跨机器比较。[S01, S12]

历史命令为 `python -m app.agentEval --suite all --format json`、`python -m app.agentAcceptance`、`agentBenchmark --suite all --telemetry compare --format json`。这些是固定历史离线接口，当前不按旧模块路径执行；不支持任意 provider、项目或输出路径。使用版本化合成数据并报告真实 provider、embedding、MySQL、项目读取计数，是确定性矩阵，不是生产压力/容量测试。[S02, S20, S21, S22]

以下时间线完整保留原表，与中文说明共同阅读：

| Stage | Evidence and interpretation |
| --- | --- |
| Iteration 4 Aspect 6 | Deterministic fake Eval froze 39 core, 47 security, and 18 reliability cases: `104/104` total. Performance was explicitly deferred to Aspect 7. [S09] |
| Iteration 4 Aspect 7 | The first real wall-clock parent baseline and the fixed performance/telemetry/frontend gate were frozen separately. [S11, S12] |
| Iteration 4 Aspect 8 | Acceptance `18/18`, Eval `104/104`, a later benchmark sample, browser checks, isolated Compose, telemetry, safety, and zero-cost counters were frozen together. [S13, S14] |
| Iteration 4 closeout | Deterministic offline gates were followed by separately authorized real-model synthetic quality and an isolated synthetic Agent E2E. [S03, S04, S15] |
| Iteration 5 closeout | Source-preview validation was attempted in changing local and hosted environments. Some gates passed in task-owned environments, but Docker full-stack/parity remained blocked. Raw task-owned reports are not in this repository. [S16, S17, S18] |
| Iteration 6 closeout | Current-tree static/local gates and a separately authorized, bounded real-model/embedding/RAG smoke were consolidated. Static facts are auditable from the final tree; smoke details remain class C because raw runtime reports and protected data are not committed. [S23] |

### 确定性正确性与安全

[Verified] Aspect 6 的 39 core、47 security、18 reliability 合计 104/104。适用的任务成功、trajectory、工具选择、结构化输出、恢复和攻击阻断率为 1.0；approval bypass、duplicate side effect、项目隔离违规、预算超限、unsafe capability、敏感泄露和 warm exact-cache 模型/embedding 调用为零。RAG recall@4、MRR、nDCG@4 和 citation coverage 为 1.0，项目泄露为零。[S05, S08, S09, S10]

[Verified] Aspect 8 Acceptance 为 18/18，task success、trajectory 和 recovery 为 1；同批保留 Eval 104/104、零安全违规和零 warm-cache 调用。local 与 isolated-Compose 是该次历史上下文，不保证当前拓扑可用。[S07, S13, S14]

[Candidate] Iteration 5 记录 727 passed, 32 skipped、Eval 104/104 和 Acceptance 18/18，source-preview 重述这些值；S19 保存 18-case 数据集和公开契约数量，但原始执行报告在仓库外，所以仍为 C。[S16, S18, S19]

### Iteration 1–3 早期记录

Iteration 1 收口记录 131 项后端通过，lint/build 通过；Iteration 2 收口记录 275 passed, 1 deselected，真实 schema 变更和付费 A/B 未执行；Iteration 3 记录后端 355 项、前端 contracts 93 项通过。它们是[对应历史正文](iteration-history.md#historical-sources)中的记录，本方面未复跑，也不新授予 A/B 等级。

Iteration 2 的 C/E/I/O 分别为 chat 调用、文档索引 embedding 构建批次、累计输入上下文 Token、累计输出上限；query embedding 不计入 E。小样本 overflow=0、大样本 overflow=4，所有 I/O 与 DAO 使用替身。下表保留收口比较；完整逐 operation 原表也保留在其后，均不是供应商账单。

| Profile | 场景 | Task 0 | Iteration 2 完成值 |
| --- | --- | ---: | ---: |
| Small | 19 个隔离首轮合计 | 40/13/21804/1138688 | 39/13/20408/230400 |
| Large | 19 个隔离首轮合计 | 71/13/387179/1392640 | 39/13/227588/230400 |
| Small | 相同请求重复合计 | 19/5/9319/475136 | 15/0/6738/76800 |
| Large | 相同请求重复合计 | 19/5/51965/475136 | 15/0/46352/76800 |
| Small | `project_analysis` 首轮 | 3/0/2560/73728 | 2/0/1633/10240 |
| Large | `project_analysis` 首轮 | 9/0/60399/122880 | 2/0/35113/10240 |

| Operation | Small first execution | Large first execution | Identical repeat |
| --- | --- | --- | --- |
| `project_analysis` | summary → plan → menu | summary map×4 → reduce → plan map×2 → reduce → menu | complete bundle cache |
| `unit_menu` | analysis → structured menu | map×2 → reduce → structured menu | structured menu only |
| `unit_info` | design retrieval/index → analysis → method structure | same graph with larger retrieved context | same full graph |
| `unit_case` | knowledge×2 → final case | same graph with larger knowledge context | final case only |
| `integration_menu` | fallback unit analysis → structured menu | fallback unit map×2 → reduce → structured menu | structured menu only |
| `integration_info` | design retrieval/index → analysis | same graph with larger retrieved context | same full graph |
| `integration_case` | knowledge×3 → final case | same graph with larger knowledge context | final case only |
| `api_info` | analysis → structured list | map×2 → reduce → structured list | structured list only |
| `api_case` | design retrieval/detail → knowledge → final case | same graph with larger contexts | design retrieval/detail → final case |
| `ui_info` | analysis | map×3 → reduce | text cache |
| `ui_case` | knowledge → final case | same graph with larger knowledge context | final case only |
| `db_info` | analysis | map×2 → reduce | text cache |
| `db_case` | knowledge → final case | same graph with larger knowledge context | final case only |
| `functional_info` | analysis → structured list | map×12 → reduce → structured list | structured list only |
| `functional_case` | requirement retrieval/detail → knowledge → final case | same graph with larger contexts | requirement retrieval/detail → final case |
| `nonfunctional_info` | requirement retrieval/index → analysis → structured list | same graph with larger retrieved context | structured list only |
| `nonfunctional_case` | knowledge → final case | same graph with larger knowledge context | same full graph |
| `acceptance_info` | analysis | map×2 → reduce | text cache |
| `acceptance_case` | knowledge → final case | same graph with larger knowledge context | final case only |

| Operation | Small first | Small repeat | Large first | Large repeat |
| --- | ---: | ---: | ---: | ---: |
| `project_analysis` | 3/0/2560/73728 | 0/0/0/0 | 9/0/60399/122880 | 0/0/0/0 |
| `unit_menu` | 2/0/1922/40960 | 1/0/1076/8192 | 4/0/23815/57344 | 1/0/1076/8192 |
| `unit_info` | 2/1/1009/40960 | 2/1/1009/40960 | 2/1/8837/40960 | 2/1/8837/40960 |
| `unit_case` | 3/1/1462/98304 | 1/0/499/32768 | 3/1/24742/98304 | 1/0/499/32768 |
| `integration_menu` | 2/0/1899/40960 | 1/0/1053/8192 | 4/0/23792/57344 | 1/0/1053/8192 |
| `integration_info` | 1/1/746/32768 | 1/1/746/32768 | 1/1/8574/32768 | 1/1/8574/32768 |
| `integration_case` | 4/1/2147/131072 | 1/0/711/32768 | 4/1/37067/131072 | 1/0/711/32768 |
| `api_info` | 2/0/735/40960 | 1/0/203/8192 | 4/0/21769/57344 | 1/0/203/8192 |
| `api_case` | 3/2/1573/98304 | 2/1/1084/65536 | 3/2/22243/98304 | 2/1/10114/65536 |
| `ui_info` | 1/0/485/32768 | 0/0/0/0 | 4/0/19880/57344 | 0/0/0/0 |
| `ui_case` | 2/1/829/65536 | 1/0/340/32768 | 2/1/12469/65536 | 1/0/340/32768 |
| `db_info` | 1/0/486/32768 | 0/0/0/0 | 3/0/21346/49152 | 0/0/0/0 |
| `db_case` | 2/1/830/65536 | 1/0/351/32768 | 2/1/12470/65536 | 1/0/351/32768 |
| `functional_info` | 2/0/673/40960 | 1/0/212/8192 | 14/0/22451/139264 | 1/0/212/8192 |
| `functional_case` | 3/2/1396/98304 | 2/1/920/65536 | 3/2/19356/98304 | 2/1/7240/65536 |
| `nonfunctional_info` | 2/1/940/40960 | 1/0/237/8192 | 2/1/3490/40960 | 1/0/237/8192 |
| `nonfunctional_case` | 2/1/662/65536 | 2/1/662/65536 | 2/1/12302/65536 | 2/1/12302/65536 |
| `acceptance_info` | 1/0/758/32768 | 0/0/0/0 | 3/0/19845/49152 | 0/0/0/0 |
| `acceptance_case` | 2/1/692/65536 | 1/0/216/32768 | 2/1/12332/65536 | 1/0/216/32768 |

| Profile | Execution | Chat calls | Embedding builds | Input-context tokens | Summed output cap |
| --- | --- | ---: | ---: | ---: | ---: |
| Small | First | 40 | 13 | 21804 | 1138688 |
| Small | Repeat | 19 | 5 | 9319 | 475136 |
| Large | First | 71 | 13 | 387179 | 1392640 |
| Large | Repeat | 19 | 5 | 51965 | 475136 |

| Operation | Small first | Small repeat | Large first | Large repeat |
| --- | ---: | ---: | ---: | ---: |
| `project_analysis` | 2/0/1486/40960 | 0/0/0/0 | 6/0/38929/73728 | 0/0/0/0 |

| Operation | Small first | Small repeat | Large first | Large repeat |
| --- | ---: | ---: | ---: | ---: |
| `unit_menu` | 2/0/1922/40960 | 0/0/0/0 | 4/0/23815/57344 | 0/0/0/0 |
| `unit_info` | 2/1/1009/40960 | 0/0/0/0 | 2/1/8837/40960 | 0/0/0/0 |
| `unit_case` | 3/1/1462/98304 | 0/0/0/0 | 3/1/24742/98304 | 0/0/0/0 |
| `integration_menu` | 2/0/1899/40960 | 0/0/0/0 | 4/0/23792/57344 | 0/0/0/0 |
| `integration_info` | 1/1/746/32768 | 0/0/0/0 | 1/1/8574/32768 | 0/0/0/0 |
| `integration_case` | 4/1/2147/131072 | 0/0/0/0 | 4/1/37067/131072 | 0/0/0/0 |
| `api_info` | 2/0/735/40960 | 0/0/0/0 | 4/0/21769/57344 | 0/0/0/0 |
| `api_case` | 3/2/1573/98304 | 0/0/0/0 | 3/2/22243/98304 | 0/0/0/0 |
| `ui_info` | 1/0/485/32768 | 0/0/0/0 | 4/0/19880/57344 | 0/0/0/0 |
| `ui_case` | 2/1/829/65536 | 0/0/0/0 | 2/1/12469/65536 | 0/0/0/0 |
| `db_info` | 1/0/486/32768 | 0/0/0/0 | 3/0/21346/49152 | 0/0/0/0 |
| `db_case` | 2/1/830/65536 | 0/0/0/0 | 2/1/12470/65536 | 0/0/0/0 |
| `functional_info` | 2/0/673/40960 | 0/0/0/0 | 14/0/22451/139264 | 0/0/0/0 |
| `functional_case` | 3/2/1396/98304 | 0/0/0/0 | 3/2/19356/98304 | 0/0/0/0 |
| `nonfunctional_info` | 2/1/940/40960 | 0/0/0/0 | 2/1/3490/40960 | 0/0/0/0 |
| `nonfunctional_case` | 2/1/662/65536 | 0/0/0/0 | 2/1/12302/65536 | 0/0/0/0 |
| `acceptance_info` | 1/0/758/32768 | 0/0/0/0 | 3/0/19845/49152 | 0/0/0/0 |
| `acceptance_case` | 2/1/692/65536 | 0/0/0/0 | 2/1/12332/65536 | 0/0/0/0 |

| Operation | Small first | Small repeat | Large first | Large repeat |
| --- | ---: | ---: | ---: | ---: |
| `project_analysis` | 2/0/1486/40960 | 0/0/0/0 | 6/0/38929/73728 | 0/0/0/0 |
| `unit_menu` | 2/0/1922/40960 | 0/0/0/0 | 4/0/23815/57344 | 0/0/0/0 |
| `unit_info` | 2/1/970/40960 | 0/0/0/0 | 2/1/1929/40960 | 0/0/0/0 |
| `unit_case` | 3/1/1384/98304 | 0/0/0/0 | 3/1/10846/98304 | 0/0/0/0 |
| `integration_menu` | 2/0/1899/40960 | 0/0/0/0 | 4/0/23792/57344 | 0/0/0/0 |
| `integration_info` | 1/1/707/32768 | 0/0/0/0 | 1/1/1666/32768 | 0/0/0/0 |
| `integration_case` | 4/1/2030/131072 | 0/0/0/0 | 4/1/16223/131072 | 0/0/0/0 |
| `api_info` | 2/0/735/40960 | 0/0/0/0 | 4/0/21769/57344 | 0/0/0/0 |
| `api_case` | 3/2/1495/98304 | 0/0/0/0 | 3/2/7197/98304 | 0/0/0/0 |
| `ui_info` | 1/0/485/32768 | 0/0/0/0 | 4/0/19880/57344 | 0/0/0/0 |
| `ui_case` | 2/1/790/65536 | 0/0/0/0 | 2/1/5521/65536 | 0/0/0/0 |
| `db_info` | 1/0/486/32768 | 0/0/0/0 | 3/0/21346/49152 | 0/0/0/0 |
| `db_case` | 2/1/791/65536 | 0/0/0/0 | 2/1/5522/65536 | 0/0/0/0 |
| `functional_info` | 2/0/673/40960 | 0/0/0/0 | 14/0/22451/139264 | 0/0/0/0 |
| `functional_case` | 3/2/1318/98304 | 0/0/0/0 | 3/2/6844/98304 | 0/0/0/0 |
| `nonfunctional_info` | 2/1/901/40960 | 0/0/0/0 | 2/1/1696/40960 | 0/0/0/0 |
| `nonfunctional_case` | 2/1/623/65536 | 0/0/0/0 | 2/1/5354/65536 | 0/0/0/0 |
| `acceptance_info` | 1/0/758/32768 | 0/0/0/0 | 3/0/19845/49152 | 0/0/0/0 |
| `acceptance_case` | 2/1/653/65536 | 0/0/0/0 | 2/1/5384/65536 | 0/0/0/0 |

| Profile | Operation | First C/E/I/O/R | Regenerated C/E/I/O/R |
| --- | --- | ---: | ---: |
| Small | `unit_info` | 2/1/970/40960/321 | 2/0/970/40960/321 |
| Small | `api_case` | 3/2/1495/98304/642 | 3/0/1495/98304/642 |
| Small | `functional_case` | 3/2/1318/98304/642 | 3/0/1318/98304/642 |
| Small | `nonfunctional_info` | 2/1/901/40960/321 | 2/0/901/40960/321 |
| Large | `unit_info` | 2/1/1929/40960/1282 | 2/0/1929/40960/1282 |
| Large | `api_case` | 3/2/7197/98304/6324 | 3/0/7197/98304/6324 |
| Large | `functional_case` | 3/2/6844/98304/6148 | 3/0/6844/98304/6148 |
| Large | `nonfunctional_info` | 2/1/1696/40960/1106 | 2/0/1696/40960/1106 |

| Operation | Small first | Small repeat | Large first | Large repeat |
| --- | ---: | ---: | ---: | ---: |
| `project_analysis` | 2/0/1633/10240 | 0/0/0/0 | 2/0/35113/10240 | 0/0/0/0 |
| `unit_menu` | 2/0/2157/20480 | 0/0/0/0 | 2/0/18897/20480 | 0/0/0/0 |
| `unit_info` | 2/1/964/9728 | 0/0/0/0 | 2/1/1923/9728 | 0/0/0/0 |
| `unit_case` | 3/1/1356/15360 | 3/0/1356/15360 | 3/1/10818/15360 | 3/0/10818/15360 |
| `integration_menu` | 2/0/1997/9728 | 0/0/0/0 | 2/0/18737/9728 | 0/0/0/0 |
| `integration_info` | 1/1/707/8192 | 0/0/0/0 | 1/1/1666/8192 | 0/0/0/0 |
| `integration_case` | 4/1/1988/16896 | 4/0/1988/16896 | 4/1/16181/16896 | 4/0/16181/16896 |
| `api_info` | 2/0/729/9728 | 0/0/0/0 | 2/0/17469/9728 | 0/0/0/0 |
| `api_case` | 3/2/1481/15360 | 3/0/1481/15360 | 3/2/7183/15360 | 3/0/7183/15360 |
| `ui_info` | 1/0/485/8192 | 0/0/0/0 | 1/0/17225/8192 | 0/0/0/0 |
| `ui_case` | 2/1/776/13824 | 0/0/0/0 | 2/1/5507/13824 | 0/0/0/0 |
| `db_info` | 1/0/486/8192 | 0/0/0/0 | 1/0/17226/8192 | 0/0/0/0 |
| `db_case` | 2/1/777/13824 | 0/0/0/0 | 2/1/5508/13824 | 0/0/0/0 |
| `functional_info` | 2/0/667/9728 | 0/0/0/0 | 2/0/17407/9728 | 0/0/0/0 |
| `functional_case` | 3/2/1304/15360 | 3/0/1304/15360 | 3/2/6830/15360 | 3/0/6830/15360 |
| `nonfunctional_info` | 2/1/895/9728 | 0/0/0/0 | 2/1/1690/9728 | 0/0/0/0 |
| `nonfunctional_case` | 2/1/609/13824 | 2/0/609/13824 | 2/1/5340/13824 | 2/0/5340/13824 |
| `acceptance_info` | 1/0/758/8192 | 0/0/0/0 | 1/0/17498/8192 | 0/0/0/0 |
| `acceptance_case` | 2/1/639/13824 | 0/0/0/0 | 2/1/5370/13824 | 0/0/0/0 |

| Profile | Operation | First C/E/I/O/R | Regenerated C/E/I/O/R |
| --- | --- | ---: | ---: |
| Small | `unit_info` | 2/1/964/9728/321 | 2/0/964/9728/321 |
| Small | `api_case` | 3/2/1481/15360/642 | 3/0/1481/15360/642 |
| Small | `functional_case` | 3/2/1304/15360/642 | 3/0/1304/15360/642 |
| Small | `nonfunctional_info` | 2/1/895/9728/321 | 2/0/895/9728/321 |
| Large | `unit_info` | 2/1/1923/9728/1282 | 2/0/1923/9728/1282 |
| Large | `api_case` | 3/2/7183/15360/6324 | 3/0/7183/15360/6324 |
| Large | `functional_case` | 3/2/6830/15360/6148 | 3/0/6830/15360/6148 |
| Large | `nonfunctional_info` | 2/1/1690/9728/1106 | 2/0/1690/9728/1106 |

Iteration 3 的独立离线旅程、视口和 bundle 表保留原数据；此处记录当时结果，不把 fixture 标识当作现有用户项目，也不复现其业务写入。

| Aspect | 交付结果 |
|---|---|
| 1 | 建立页面×状态×视口基线、`--ez-*` tokens、Element Plus bridge、全局基础样式和 WorkflowStepper pilot。 |
| 2 | 重构响应式应用壳：桌面固定侧栏、窄屏抽屉、键盘 trap/Escape/焦点恢复、1200px 内容上限。 |
| 3 | 建立共享页面、section、模型、操作、反馈与结果组件，统一 LLM progress/reasoning/Token/保存/取消/失败层级。 |
| 4 | 重构登录、项目创建、恢复、文档组上传、部分成功复用、项目 ID 指导与安全退出。 |
| 5 | 重构测试计划与八类测试菜单工作台，分离已保存版本和未保存草稿，发布统一测试类型 registry 与插图。 |
| 6 | 八类测试页采用统一 scaffold、阶段布局、显式恢复、qualified selector 与五/三 retention 边界。 |
| 7 | 完成 WCAG 2.2 AA、320px reflow、状态播报、按需 Element Plus、Logo 和 bundle 性能硬化。 |
| 8 | 补齐动态项目 `analysis_required → analysis_ready`、持久化失败回滚、跨状态/视口验收和 closeout。 |

| 场景 | 证据 | 结论 |
|---|---|---|
| 入口与返回项目 | 360px：label、格式错误 alert、标题、focus 与无溢出；页面加载无写入 | 通过 |
| 未完成项目恢复 | 768px：`RECOVERY_PID` 展示知识库/设计已上传，需求组待补充，项目 ID 与安全说明完整 | 通过 |
| 新项目与部分上传 | 浏览器确认创建表单、可见 file chooser 与安全切换；loopback multipart 完成 21 位项目 ID、需求第二文件一次 503、retry 只补剩余文件 | 通过；浏览器 `setFiles` 传输限制见已知限制 |
| finalize 与 analysis required | 合成项目三组齐全后 `documents_ready → setup_complete → analysis_required`，只开放 `/plan` | 通过 |
| analysis running → ready | 显式计划 SSE 事件为 meta/progress/summary/answer/menu/result/artifact/completed；完成后 `analysis_ready`、10 条工作区路径可用 | 通过 |
| ready / mixed menu | 1440px 始终 8 卡，6 张 available、2 张 not-recommended 且有原因 | 通过 |
| 八类工作区首次进入 | 1024px 逐页进入 unit/integration/API/UI/database/functional/nonfunctional/acceptance；标题、main focus、无重复 ID/溢出 | 通过 |
| cached recovery | persisted final 显式恢复后显示 `已从缓存恢复` 与 `已保存`，Token 未返回时不伪造数字 | 通过 |
| stale revision | 1920px 计划、菜单和单元/UI 两类 stale 一致，旧内容不冒充 fresh | 通过 |
| regeneration | 1024px 旧计划运行中持续可读，下游立即显示分析中；completed 后提升新版本并恢复菜单/路由 | 通过 |
| cancellation | 768px acceptance 慢流在 partial answer 后取消；正文保留，显示 cancelled/`本次未保存`，步骤回滚而未保存 | 通过 |
| structured-output error | 1024px database 返回 retryable 结构化 error；显示 alert、`本次未保存` 和 `可安全重试` | 通过 |
| persistence error | PID 8 先缓存恢复 `ui_info/ui_case`；regenerate 只发 meta/progress/answer/result/error，无 artifact/completed；旧 `UI-FIXTURE-001` 仍可见 | 通过 |
| session-only final | 360px API case 显示 `仅当前页面保留`；fixture 不发送 artifact，completed 为 `saved=false/from_cache=false` | 通过 |
| 320px 等效高倍率 | 根页面 `scrollWidth === clientWidth`；模型 segmented 可重排；实际 input 30px 由 44px wrapper 提供目标区且满足 WCAG 24px 最低值 | 通过 |

| 视口 | 代表场景 | 结果 |
|---:|---|---|
| 320×800 | 入口、模型 segmented 等效高倍率重排 | 根宽度一致，无页面级横向溢出 |
| 360×800 | analysis_required、session-only API final | 单列、操作全宽、保留边界可见 |
| 768×1024 | 恢复流程、acceptance cancelled partial | 抽屉壳、状态/partial 可读，无溢出 |
| 1024×768 | 八页 sweep、database structured error、regeneration | 固定侧栏、main focus、无重复 ID |
| 1440×900 | mixed menu、PID 8 persistence error | 8 卡状态与旧结果回滚清楚 |
| 1920×1080 | stale menu | 内容宽度 1200px，2 stale/6 available |

| 指标 | 结果 | Aspect 7 门禁 |
|---|---:|---:|
| source map | 0 | 必须为 0 |
| Logo | 81,689 bytes | ≤96 KiB |
| 最大初始 JS raw / gzip | 443,227 / 143,472 bytes | ≤900 KiB / ≤285 KiB |
| 初始 CSS raw / gzip | 111,092 / 19,519 bytes | ≤220 KiB / ≤34 KiB |
| index 初始资产 raw | 567,254 bytes | ≤1.20 MiB |
| 完整构建目录 | 1,580,498 bytes，46 文件 | ≤3 MiB |

其限制包括浏览器 setFiles 超时、200% zoom 不能可靠获取、Narrator 音频需人工核对；multipart 部分失败重试由同一 loopback fixture HTTP 验证。320 CSS px 等效重排不能被改称实际 200% zoom 通过，历史 Vue CLI warnings 仍保留。

<a id="performance-model"></a>
## 性能、体积和真实合成验收

### Parent 与 Aspect 7 的冻结值

| Metric | Parent value | Aspect 7 value | Ratio / interpretation | Source |
| --- | ---: | ---: | ---: | --- |
| Legacy health p95 | `2.334699966 ms` | `2.4266999680548906 ms` | `1.0394054925175469`, limit `1.15` | S11, S12 |
| Agent capabilities p95 | `1.703799935 ms` | — | Parent observation only | S11 |
| Frontend build p50 | `10495.1107 ms` | `622.8593 ms` | — | S11, S12 |
| Frontend build p95 | `12393.5751 ms` | `788.016 ms` | `0.06358262193448927` | S11, S12 |
| Dev-ready p50 | `1330.2352 ms` | `415.2436 ms` | — | S11, S12 |
| Dev-ready p95 | `1768.7087 ms` | `743.3997 ms` | `0.4203064642583598` | S11, S12 |
| OTel enabled/disabled p95 | — | — | `1.0217368988998805`, limit `1.05` | S12 |

Aspect 7 产生 62 个 case/mode 结果，导出 telemetry 并通过两个相对门槛；warm exact-cache 模型/embedding 增量为零，所有 real-provider、embedding、MySQL、project-read 和货币成本计数均为零。[S12]

| Bundle metric | Vue CLI parent | Vite gate | Vite / parent |
| --- | ---: | ---: | ---: |
| Largest initial JS | `443227 B` (`143472 B` gzip) | `293597 B` (`98954 B` gzip) | `0.6624077504303664` non-gzip |
| Initial CSS | `111209 B` (`19536 B` gzip) | `115218 B` (`19717 B` gzip) | `1.0360492406190147`; gzip `1.0092649467649468` |
| Initial total | `571421 B` | `527792 B` | `0.923648238339158` |
| Full build | `1587799 B` | `1474835 B` | `0.9288549747165731` |
| File count | `49` | `65` | Descriptive only |

两次构建 source map 均为零、相同 Logo 为 25193 B；字节数绑定各自冻结 manifest 和工具链，时间值仍只作同机器比较。[S11, S12]

### 后续样本不得覆盖前一批

Aspect 8 的 legacy ratio=1.083736659134018（limit 1.15）、OTel ratio=1.014521458310483（limit 1.05），warm-cache gate 通过，是另一批样本。[S13]

Iteration 4 正文随后记录最终本地 1.0276695194994545 / 1.0258291744311046，托管 CI 跨平台修复重跑 0.947102356927876 / 1.0256611149561863（legacy / OTel）；属于 tracked narrative，不重写 S12/S13。[S02]

[Candidate] Iteration 5 两次 isolated run 约为 legacy 1.035、1.070，OTel 1.025、1.033。原始报告缺失，只保留正文与原精度。[S16]

### 真实模型合成验证

[Verified] 首次获准 planner quality 完成 6 次调用但严格规划为 0/6，真实 RAG top-1 为 3/3；provider 边界修复后相同规划案例的工具选择、结构化输出和 regenerate 绑定为 6/6，RAG 再次 3/3。包括预检/首次运行的累计为 13 chat、9 embedding；未返回货币费用，不估算。[S04, S15]

[Verified] 单独批准的 ui_info → ui_case E2E 完成两次审批、两个 artifact、一次 RAG 查询/引用，最终 ledger 为四次模型、两次 embedding、两次工具和两步，最终耗时 96163.598 ms。四次调试/最终 E2E 累计 14 chat、6 embedding；合成临时输入/存储下用户 MySQL/项目读取、重复副作用、stored reasoning、凭据暴露和 public/checkpoint 内容泄露均为零。[S04]

确定性门禁、planner/RAG quality、合成 Agent E2E 三层不能互相代替；它们不证明客户项目质量、生产负载/持久化或货币成本基线。[S03, S04]

### 浏览器、观测、容器及 CI 历史

Aspect 7 检查五个视口、零横向溢出与控制台错误、44 px 审批目标、Escape/焦点恢复、disabled/instrumented trace。历史隔离 Compose 为 10 个健康服务、10 Tempo traces、Prometheus collector up=1、两个 Grafana data sources、dashboard ezllm-agent-overview、非 loopback host 421。[S12]

Aspect 8 另记 10/10 健康、九层 Tempo span、零禁止属性/敏感日志命中、低基数标签、Prometheus/Tempo datasource，以及该批容器、网络和卷的清理；均为历史运行事实。[S13]

[Candidate] Iteration 5 记录 Actions commit/run 8c04759 / 33627691876：非 Docker 门禁通过，Docker smoke 在 Tempo trace query 和 in-container Acceptance 失败；原托管报告未冻结。[S16]

[Missing] Docker full-stack 和双拓扑业务 parity 仍 Blocked；旧尝试包括固定端口冲突，以及 ignored 依赖缺 formatter binary。未改端口或停用户进程来制造通过。[S16, S17, S18] 当前工程不启动容器，旧结果不构成当前运行指引。

<a id="iteration-6"></a>
## Iteration 6 补充

[Verified] S23 历史记录保留 19 workflows、22 typed tools、62 FastAPI routes、REST/SSE/MCP 和七张 SQL 表；163 Python 文件内存编译、902 函数中文 docstring，前端 561 节点分类、461 必须目标有中文 JSDoc。type-check、ESLint、Prettier、临时 production build 通过且未改变仓库 dist。

这里的 62 是历史记录值。Iteration 7 方面二实际注册清单为产品 42、Agent 11、观测 10，共 63，与旧实现清单逐项核对；不通过删除接口凑数，也不把历史行改成 63。

S23 记录显式三份配置、五模块、本地 readiness（数据库/Redis/worker）通过；观测七天、100000 行，排除 prompt/completion/reasoning、项目与工具载荷、SQL/Redis 内容、异常和秘密。该记录不证明容量或 SLA。

[Candidate] 2026-09-07 最小合成烟测：一次 GLM 分析原子保存/恢复，1085 输入、4499 总 Token；embedding-3 返回 2048 个有限维度，约 2.38 s；legacy RAG 首次约 45.69 s 超时，默认 RAG chat 最小 timeout 调整到 300 秒后唯一重试约 56.15 s 成功并持久化两个预期知识结果，provider 自动 retry 仍为零。原始报告、项目标识、正文、向量不提交，仍为 C。[S23]

未运行生产压力、持续负载、客户数据、完整项目浏览器或完整 Agent E2E，不提供货币成本基线或正式生产就绪结论。

<a id="iteration-7"></a>
## Iteration 7 分方面记录

以下来自本轮备份的未提交总纲、架构文档和运行指南，是本机实施记录；旧批次 evidence 正文未在方面四重新读取或哈希。记录的已通过项不因此升级成 A/B 冻结证据，也不冒充本方面重新执行。

| 方面 | 已记录结果 | 本方面解释 |
| --- | --- | --- |
| 一 | 两份原规划备份；新分支同基点；目录职责确认，V2 精确批次排除核验通过 | 文档/Git 保护结果，不是产品测试 |
| 二 | 41 后端、5 前端；type-check/lint/人工 build；63 注册路由、19 workflows、22 tools；Windows IPC 人工场景 | 离线替身，未连接真实配置/数据服务 |
| 三 | 54 后端、5 前端；type-check/lint/人工 build；五个 Python 角色真实配置、MySQL SELECT 1/Redis PING | 配置检查不证明账户额度或模型质量 |
| 三：运行 | 四端口回环监听；观测/产品 ready=200，Agent ready=503；持续/单次 no-consume 心跳 | 不注册正常 worker、不消费历史任务，503 为预期限定状态 |
| 三：IPC | 403 拒绝缺失/错误 token；人工事件投递、旧凭据拒绝、轮换/重取/恢复通过；观测退出期间产品可用 | 只记录布尔结果，不记录 token 值/哈希 |
| 三：浏览器 | 首页、介绍、未登录重定向、脱敏观测列表和刷新通过 | 无项目登录/历史 Trace 详情；未保存正文截图或网络归档 |
| 三：退出 | 本轮进程、四端口和管道退出，两个验收心跳过期；V2/引用保护核验通过 | SQLite 正常生命周期获准，不声称其字节不变 |
| 四 | 133 份原件备份核验；127 份旧文件、13 个空 docs 子目录退出；三份文档归并完成 | 本方面文档与引用核验，不代表新的产品或模型验收 |

历史接手阶段中文说明为 163/902/902（Python 文件/函数/中文说明）及 56/561/461（前端文件/函数节点/必须说明）；重组后记录为 172 个 Python 产品文件、1103 函数节点、1018 中文 docstring。不可机械要求新结构函数数与旧结构相等；模板质量改进属于方面五。旧 runner 47 函数没有中文说明的接手事实不应被误标为当前全项目覆盖率。

八项 Python 安装/声明差异继续保留：pydantic 2.13.4/2.13.5、toollib 2.2.5/2.2.6、redis 6.4.0/8.1.0、langchain-core 1.5.6/1.6.1、langchain-openai 1.5.2/1.6.0、openai 3.3.0/3.6.0、numpy 1.26.4/2.4.6、pypdf 6.16.1/6.16.2。本方面未检查环境是否再次变化或安装工具。

运行指南另有无网络模型预算/保存补充记录：228 个 profile/request/context 组合、216 次共享 stream 调用、八类 case dispatcher 的 DeepSeek/K3 请求；Session double 验证长正文、缓存恢复、更新、回滚、取消、截断，SDK 使用内存 transport。元数据白名单曾在创建 Session 前拒绝新增字段，并已在当时修复；该错误不能被解读为 MySQL 不可用，旧草稿未自动补存。这些记录不证明真实长结果落库或真实模型可用。

方面四本次执行：保留并核对 19 张历史证据表、原 validation-history 关键字面值；54 处本地链接和 43 个固定提交对象检查通过；围栏、表格列、显式锚点及指定 Markdown 的 UTF-8、无 BOM、LF、末尾换行与尾部空白检查通过。前端 README 仅替换获准的六处引用，保留原格式。runtime JSON 除两项文档引用外解析结果完全一致；旧文件退出后 runner 离线用例 1 passed（0.08 s），git diff --check 通过。该测试使用隔离临时目录和禁用自动插件加载的 pytest，不重跑产品全套、前端构建或任何服务。

方面四保护核验通过：docs 仅三文件、无子目录；普通目录检查排除依赖、项目、数据、日志与旧备份后无空目录。V6 白名单外状态不变，暂存区为空，HEAD/既有引用不变，远程引用再次核对无漂移；V2 精确排除本轮批次后与实施前内存快照一致。最终 335 tracked 删除、17 tracked 修改、246 untracked 包含前两方面输入；没有提交或发布，方面五、六未开始。

本轮原件和逐文件去向见[来源与恢复](iteration-history.md#historical-sources)。V2 比较只证明指定 Git-visible 范围，不能冒充受保护资产的全量字节审计。


<a id="iteration7-aspect5"></a>
### 方面五：本次注释核验记录

以下是 2026-09-09 本机实际执行记录，尚未提交，归入 C / Candidate；不因有本地 JSON 就变成仓库内冻结 A 证据。方面二 41 项、方面三 54 项等原有阶段结果继续保留，下面的次数来自本次运行。

| 检查 | 本次结果与口径 |
| --- | --- |
| 后端离线套件 | 54 passed，7.71 s；禁用无关 pytest 自动插件，使用 -B、无缓存 provider 和本批次临时目录 |
| 前端离线用例 | 5 passed，最终一次 Node 报告 duration_ms=571.7496；人工 SSE、配置、状态与路由 fixture |
| 前端工具 | vue-tsc --noEmit、eslint src --no-fix 通过；未运行完整 build |
| Python 执行结构 | 185 文件逐一比较移除获准 docstring、忽略位置后的 AST；签名、装饰器、常量及普通字符串一致 |
| 公开描述 | Python 类及路由 docstring 原始字节一致；三组完整 OpenAPI/schema、19 workflows、22 MCP tools、resources 与元数据快照逐字节一致 |
| 前端执行结构 | 68 文件用 TypeScript 解析与无普通注释打印结果比较；Vue template/style 内容及属性原字节不变，JSDoc 指令一致 |
| 包装、SQL、CSS | 七份文件只插入普通说明；移除精确新增片段即恢复原字节，PowerShell 语法解析错误为零 |
| 格式 | 72 份前端相关文件对比原件，新增格式问题为零；shims-vue.d.ts 的原有 Prettier 问题保留，不全库重排 |
| 运行边界 | 8140、8180、8230、8231 无监听；未启动产品服务、浏览器或外部依赖 |
| 文件保护 | 264 份普通原件副本校验通过；未读取、哈希或复制真实配置及受保护数据 |

首次后端执行为 49 passed、5 failed、5 warnings（7.73 s）。失败发生在帮助子进程输出解码，父进程的 -X utf8 未传递到子解释器；不将这个工具调用问题写成产品功能回归。用户允许后，只在临时测试父子环境设置 PYTHONUTF8=1，五个帮助用例重试为 5 passed、18 deselected（0.62 s），随后完整套件 54 passed。原失败与重试文件保留在本批次 evidence，不覆盖为“首次全部通过”。

本次静态数字：Python 产品 175 文件/1112 函数/1023 个中文 docstring；后端测试 9/45/5；runner 1/46，中文 docstring 从 0 到 2，其他函数使用普通中文注释覆盖。函数数保持相同是本次仅注释改动的结果，不是后续重组必须满足的目标。前端 src 561 个函数体、tools 4、tests 14，另有 23 个类型签名。职责分类见[方面五收口](iteration-history.md#iteration7-aspect5)，不可把中文计数当作质量通过率。

本次直接修正了“UTC 时间带时区”的不准注释（实际去除 tzinfo）、空检索器被描述为下游调用，以及遥测严格校验被误写成静默过滤等说明。只修正文字，未改变实现。旧同步生成路径仍有输出异常文本的历史代码，本次未以真实数据触发或扩展修改；后续如需改错误处理须独立明确行为范围。

验证与原件位置：D:\codex\EzllmTest_v2\_archive\iteration-7\aspect-5-20260909T072901645445Z-160ae57111864994a3468c361a97fadd。原始字节备份 SHA-256 与历史 sha256_canonical_lf_v1 各自独立，不重算覆盖历史值。主要记录为 manifest.json、evidence/python-classification.json、frontend-classification.json、python-structure.json、frontend-final-structure.json、frontend-format-directives.json、public-contract-before.json、public-contract-final.json 和 validation-results.json。原始 V2 Git-visible 快照保持在本轮内存中，未输出敏感路径清单。

最终保护核验通过：V6 白名单外普通文件和 Git-visible 状态未变，暂存区为空，HEAD、既有本地及远程引用未变；V2 排除本轮精确批次后的 Git-visible 状态、分支和 HEAD 与原始内存快照一致。受保护路径仅核对存在性，不声称全量字节一致。当前 Git-visible 状态为 335 个 tracked 删除、37 个 tracked 修改、246 个 untracked，保留前序方面输入；本方面未提交或发布。真实模型、embedding、正常任务消费、生成写入、浏览器、压力和完整 build 均未在方面五执行。方面六未开始。


<a id="iteration7-aspect6"></a>
### 方面六：最终离线门禁与发布核验

以下为本机方面六实际执行结果；原始细节在仓库外批次中，仍按 C / Candidate 记录，不因提交汇总正文升级历史证据等级。

| 检查 | 本次结果 |
| --- | --- |
| 后端完整离线套件 | 54 passed，7.63 s；临时 PYTHONUTF8=1、禁用无关插件和缓存，临时数据在本批次 |
| 前端现有 Node 测试 | 5 passed，569.8476 ms |
| 类型、lint、格式 | type-check、无自动修复 lint、遵循现有忽略规则的 format:check 均通过 |
| 人工配置构建 | Vite 8.2.2，1202 modules，957 ms；退出码 0，输出在本批次 scratch/frontend-dist |
| 暂停与最小修复 | 原有测试文件两处尾随空格导致 Git 检查失败；用户授权追加备份后仅去空格，执行 AST 不变，相关用例 1 passed（3.59 s） |
| 暂存检查的第二次暂停 | 24 份新 Python 源码末尾多余空行；用户授权追加备份后仅保留一个末尾 LF，完整 AST（含 docstring）不变，随后重新检查暂存内容 |
| 资产清理 | 五份 Git 对象和副本校验通过；无当前消费者，逐文件退出后仅删除四个已空目录 |

构建显式使用人工 frontend.env 和现有 Vite 配置，关闭 dotenv 自动发现；外部输出目录是新目录，Vite 提示不会自动清空它，未使用强制清空选项。已有 frontend/dist 未作为此次输出。格式检查继续遵守 shims-vue.d.ts 等原有声明豁免，不称全库无豁免格式通过。

方面五关于 assets 为空的观察已在[方面六更正](iteration-history.md#iteration7-aspect6)说明；保留原记录的历史性质，不将其作为本次删除证据。历史 62 条路由和本轮注册 63 条、19 workflows、22 tools 继续按各自口径记录，未为了对齐计数删除接口。

提交前普通文件、备份副本、目录和保护核验通过；61 处本地链接、46 个固定 Git 对象和原有 21 个 Markdown 表格块完整保留（包含各阶段新增表格，不改写历史证据表的计数口径）。最终提交树、Git 检查、远程 main/iteration7 相等及本地 main 快进结果分别记录在本机批次 D:\codex\EzllmTest_v2\_archive\iteration-7\aspect-6-20260909T084355004418Z-53288bc6bb2449a5bdda63064b8b2615 的 evidence；尚未完成推送时不写为发布成功。V2 仅排除本轮精确批次进行 Git-visible 状态比较，受保护资产仅核对存在性，不声称全量字节一致。

本方面没有启动产品服务、浏览器或真实配置验收，没有模型、embedding、真实生成或压力操作。方面三的只读与不消费验收是历史限定结果；正常 worker 消费、真实项目 MCP、Linux IPC、reload/多 worker 等未验证范围保持。

<a id="limitations"></a>
## 限制与解释

历史根层 `docs/iteration-4-*.md` 为重定向入口，原文和目标关系已在本轮逐文件映射中保留；长期正文不再保留这些重定向文件。

- 无证据证明生产压力、持续负载、容量/饱和、生产流量故障切换、客户数据质量、安全认证或正式 SLA。
- 仓库外 Iteration 5/6 原始报告不能在本基线独立审计；保持其等级和精度，不因重复引用升级。
- 历史 Docker/Tempo/in-container Acceptance/parity 与动态 CI 状态不作为当前可用性结论，本方面也不访问托管状态。
- 绝对时间不能跨机器对比；比率依赖同机协议。ready、受控 ASGI、fake 边、浏览器 fixture 和有限烟测均不证明完整当前网络 Agent 旅程。
- Iteration 7 尚未验证正常队列消费、登录后项目页、真实生成/embedding、真实项目 MCP、压力、Linux IPC、reload/多 worker。裸 Uvicorn 三组命令仅提供等价指引，真实启动用 python -m。
- 真实环境值、凭据、上传、用户持久化、旧观测 payload/log/trace 和模型正文受保护，不作为本方面输入。GitHub 私有链接仅核对本地提交对象，HTTP 可访问性未验证。
