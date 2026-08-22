# EzllmTest Iteration 2 Offline Workflow Cost Baseline

## Scope

This report records the pre-optimization behavior of the separate
`project_analysis` stream and all 18 generic streamed operations. It is an
offline deterministic baseline, not a provider billing report or quality
benchmark.

The fixture uses one synthetic project ID, in-memory `InfoType` values, one
fixed small-document profile (`overflow=0`), and one fixed large-document
profile (`overflow=4`). Each operation is measured in isolation on its first
execution and then on an identical repeated execution against the same
in-memory state.

Chat streaming, embeddings, document loading, model metadata, and DAO access
are mocked. Socket-based external connections and provider-client creation are
test failures. No prompt body, document body, model output, reasoning content,
credential, or provider exception is stored in this report.

## Metric Definition

Each numeric cell is `C/E/I/O`:

- `C`: chat-completion call count.
- `E`: vector-index embedding build count, measured as document-embedding
  batches used to construct an in-memory index. Query embeddings are not
  counted as index builds.
- `I`: summed input-context tokens across chat calls, counted with the
  repository's existing `gpt-3.5-turbo` tiktoken counter.
- `O`: summed configured output-token caps across chat calls. This is a
  maximum budget, not actual generated output.

The synthetic token count is a stable comparison proxy. It must not be read as
the exact tokenizer or invoice usage of GLM, Qwen, DeepSeek, or Kimi.

## Current Call Graphs

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

## Per-Operation Measurements

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

## Isolated Aggregate

These totals sum isolated operation measurements; they are not an end-to-end
user-session forecast because each operation starts with its own clean
in-memory state.

| Profile | Execution | Chat calls | Embedding builds | Input-context tokens | Summed output cap |
| --- | --- | ---: | ---: | ---: | ---: |
| Small | First | 40 | 13 | 21804 | 1138688 |
| Small | Repeat | 19 | 5 | 9319 | 475136 |
| Large | First | 71 | 13 | 387179 | 1392640 |
| Large | Repeat | 19 | 5 | 51965 | 475136 |

## Baseline Findings

- The complete project-analysis bundle is the only full workflow result that
  already resumes with zero chat and zero embedding work.
- `ui_info`, `db_info`, and `acceptance_info` also avoid chat work on an
  identical repeat because their text result is directly reusable.
- `unit_menu`, `integration_menu`, `api_info`, `functional_info`, and
  `nonfunctional_info` repeat structured extraction even when their text
  analysis is cached.
- `unit_info` and `integration_info` repeat both chat and index construction.
- API and functional cases retain one document-index build on repeat because
  selected-object detail is not persisted.
- `nonfunctional_case` has no reusable knowledge or final artifact and repeats
  its complete two-call, one-index graph.
- Large functional analysis is the strongest map-stage multiplier in the
  fixture: 14 chat calls and a summed output cap of 139264 tokens.
- All case workflows still regenerate the final case body. Current knowledge
  caching reduces some repeated calls but does not resume the final result.

## Reproduction Gate

Run only the offline Task 0 tests from `ez_back_dev` with dotenv disabled and
provider keys empty:

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:ZHIPU_API_KEY=''
$env:DASHSCOPE_API_KEY=''
$env:DEEPSEEK_API_KEY=''
$env:MOONSHOT_API_KEY=''
& 'D:\tool\anaconda3\envs\ezllmtest\python.exe' -m pytest tests/test_workflow_catalog.py tests/test_workflow_cost_baseline.py -q
```

The test fails if any network/provider client is created or if any locked
current call, embedding, input-token, or output-cap measurement changes. The
original Task 0 project-analysis values remain recorded above and in the test
fixture as the before-comparison.

## Task 4 Project-Analysis Measurement

Task 4 changes only the initial `project_analysis` graph. The original Task 0
measurement above remains the before-baseline. The same fixed documents,
token counter, mock chat, zero-embedding harness, and repeated-run sequence
now record:

| Operation | Small first | Small repeat | Large first | Large repeat |
| --- | ---: | ---: | ---: | ---: |
| `project_analysis` | 2/0/1486/40960 | 0/0/0/0 | 6/0/38929/73728 | 0/0/0/0 |

The small graph is now one structured digest call plus one streamed plan call.
The large fixture selects four chunks, performs four compact evidence-map
calls, one structured digest reduce, and one streamed plan call. Neither path
has a separate menu call or a second plan map/reduce chain.

Compared with Task 0:

- Small: chat calls `3 → 2` (-33.3%), input-context tokens `2560 → 1486`
  (-42.0%), and summed output cap `73728 → 40960` (-44.4%).
- Large: chat calls `9 → 6` (-33.3%), input-context tokens `60399 → 38929`
  (-35.5%), and summed output cap `122880 → 73728` (-40.0%).
- An identical repeat with the same source revision, prompt version, input
  hash, and model label remains `0/0/0/0`, now backed by the revision-aware
  `project_analysis_bundle` artifact instead of revisionless legacy rows.

No prompt, synthetic document, model output, reasoning content, credential,
or provider exception is stored in this measurement section.

## Task 5 Generic-Workflow Resume Measurement

Task 5 leaves every first-execution call graph unchanged and adds a complete,
revision-aware artifact before the legacy cache can be reused. The same mock
chat, mock embedding, fixed small/large documents, and isolated repeated-run
sequence now record the following for the 18 generic workflows:

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

Across all 19 operations after Tasks 4 and 5, the isolated first-execution
totals are unchanged from the Task 4 measurement: small
`39/13/20730/1105920` and large `68/13/365709/1343488`. The identical-repeat
totals are now `0/0/0/0` for both profiles, compared with the Task 0 generic
repeat totals of small `19/5/9319/475136` and large
`19/5/51965/475136`.

The artifact stores the final result plus only the catalog-declared normalized
selection. It does not store prompt text, source document bodies, streamed
reasoning, credentials, provider exceptions, or transport-only metadata.

## Task 6 Retrieval-Reuse and Bounded-Context Measurement

Task 6 keeps the Task 5 final-artifact lookup ahead of document loading and
retrieval. An identical request therefore remains `0/0/0/0`. First executions
now use revision-scoped in-process indexes and bounded, de-duplicated selected
context. The current locked `C/E/I/O` measurements are:

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

To isolate index reuse from final-artifact reuse, the following second run
explicitly regenerates the same operation at the same source revision. Its
metric is `C/E/I/O/R`, where `R` is summed selected-context tokens after score
filtering, whitespace normalization, content-hash de-duplication, and the
per-retrieval token cap.

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

The regenerated runs remove every repeated index build (`1 or 2 → 0`) while
selecting the same bounded context. Compared with Task 5, large-fixture input
context falls from `8837 → 1929` for unit information, `22243 → 7197` for a
named API case, `19356 → 6844` for a named functional case, and `3490 → 1696`
for nonfunctional analysis. Across all 19 isolated first executions, summed
input context changes from `20730 → 20106` for the small fixture and
`365709 → 260009` for the large fixture; chat calls, first-build counts, and
output caps are unchanged.

Only numeric counters and operation/profile labels are recorded. This section
contains no prompt, source document, model output, reasoning, credential, raw
exception, vector, or embedding value.

## Task 7 Stage-Budget Measurement

Task 7 resolves every model call to `map`, `structured`, or `final`. Map and
structured stages disable provider thinking (or select the provider's lowest
supported effort); final analysis and case stages use balanced reasoning.
Qwen's enabled final-stage thinking budget is capped at 4,096 tokens and never
exceeds that call's output cap. Project analysis uses output caps
`1024/2048/8192`, generic analysis uses `1024/1536/8192`, and case workflows
use `1024/1536/12288` for map/structured/final stages. `unit_menu` is the one
exhaustive structured-output exception: its qualified-reference menu uses a
`12288` structured cap so large class/function inventories are not cut off while
JSON is still open; mechanical reasoning remains disabled.

The current locked `C/E/I/O` measurements are:

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

Same-revision forced regeneration still isolates Task 6 index reuse. Here `R`
is the selected RAG-context token count:

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

After the long-text policy correction, summed first-execution input context is
`20408` for the small fixture and `227588` for the large fixture. The large
fixture deliberately trades more complete one-call input for fewer lossy map
summaries: total first-run chat calls are `39` in both profiles and summed
output caps are `230400`. Persisted artifact repeats remain zero calls and zero
embedding builds. The five selected-target final-case operations are now
session-only by product policy; a cross-page repeat intentionally performs
`15/0/6738/76800` for the small fixture and `15/0/46352/76800` for the large
fixture. Their shared revision-scoped retrieval indexes still avoid a repeated
embedding build.

The preflight gate retains the instruction head and business-context tail when
an input must be reduced. Its progress event includes only before/after token
counts. SSE `meta`, `usage`, and `completed` expose only sanitized budget and
numeric usage/call fields. No prompt, source document, model output, reasoning
content, credential, raw exception, vector, or embedding value is recorded.
