# X1 集成前静态接口对账（6 条跨 agent 契约）

> 任务：t19（attempt 2）· 执行人：integrate / integrator（AgentTeams `insurance-intel-2026`）
> 时间：2026-11-18 16:36–16:50 (+0800)
> 对象：`renewal-assistant` 内理赔域（方案 C）——`claims/**`、`data/llm-wiki-claims/**`、`traces-claims/**`
> **本任务只审计、不改任何代码**。产出仅本文件。

## 0. 为什么先对账再联调

三条流水线由不同 agent 并行写成：F2（编排 `claims/graph.py`）、F3（Deep Agents `claims/deep_agents/`）、D2/D5（知识侧 `data/llm-wiki-claims/` + 检索层）。联调一旦失败，**无法区分是接口假设不一致还是逻辑错误**。
本文件只回答一个问题：**两边对同一个名字/同一份结构/同一个目录的理解是否一致**。逻辑正确性不在本次范围。

---

## 0.1 判定总表

| # | 接口 | 判定 | 问题数（blocker / degradation / cosmetic） |
|---|---|---|---|
| I1 | `claims/graph.py` → `claims.deep_agents.analyzer.run_analysis(docs, *, analyzer_version)` | **一致**（签名与返回结构均一致） | 1 / 1 / 1 |
| I2 | `MaterialsAnalysis` schema（SPEC §4.3 ↔ F2 `state.py` ↔ F3 `schema.py`） | **一致**（逐字一致，实测 shape 完全相等） | 0 / 0 / 0 |
| I3 | wiki 目录约定（`WIKI_DIR` vs `CLAIMS_WIKI_DIR` vs 实际语料根） | **无法判定**（D2/D3/D5 未完成；`data/llm-wiki-claims/wiki` 目前 0 条目）**+ 2 个可判定的不一致** | 1 / 1 / 0 |
| I4 | 轨迹写入（只写 `traces-claims/`、`record_type` ⊆ 11 种、`claims.*` 前缀） | **一致**（三条硬约束实测成立） | 0 / 2 / 0 |
| I5 | 4 个环境变量默认值与生效点（config.py ↔ SPEC §8.1） | **不一致**（`CLAIMS_WIKI_DIR` 未登记且无消费点；`DEEPAGENTS_PYTHON` 无生效点；`CLAIMS_DATA_DIR` 不覆盖 F3 工作区） | 0 / 3 / 1 |
| I6 | checkpoint 路径 / `durability="sync"` / `recursion_limit=40` / 同 thread 二次 invoke | **一致**（顶层配置形式与官方语义吻合）**+ 2 个语义缺口** | 0 / 2 / 0 |

**合计：blocker 2 · degradation 9 · cosmetic 2。**

> 两条 blocker 都不是"代码写错"，而是**环境前提没写进契约**：①Deep Agents 只在 `.venv-claims` 里存在，而文档没规定理赔流水线/测试必须在哪个解释器跑；②检索层一旦按续保默认构造 `WikiSearch()`，会读续保 `wiki/` 且随 cwd 静默变空。这两条都会让 e2e 的失败**看起来像业务 bug**。

---

## 1. 方法与证据约定

- 所有结论都带**命令 + 原文输出**。探针脚本放在 `/tmp/x1_probe*.py`（不入库），运行时把 `CLAIMS_TRACE_DIR` / `CLAIMS_CHECKPOINT_DB` / `CLAIMS_DATA_DIR` 全部指到 `tempfile.mkdtemp()`，**不写仓库**。
- 运行时探针均在 `PYTHONPATH=.` 下执行（`claims` 不是安装包，两个 `conftest.py` 也是这么加路径的）。
- 解释器：`.venv/bin/python`（续保基线环境，**无** `deepagents`）、`.venv-claims/bin/python`（F0 建的隔离环境，**有** `deepagents==0.7.39`）。
- 本次**未执行**的验证（留 C5/e2e）：真实 LLM 调用、Deep Agents 真跑（需凭证）、API/SSE 层（尚不存在）、`CLM-19`（`GraphRecursionError` 需构造循环 fixture）。

---

## 2. I1 · `run_analysis` 调用契约

### 契约要求

- F2 `claims/graph.py:9-11` 写明：`DEEPAGENTS_ENABLED=true` → 用 `claims.deep_agents.analyzer.run_analysis`，否则用本域 `rules_analyzer`。
- F3 `claims/deep_agents/analyzer.py:1-7` 写明：唯一入口签名 `def run_analysis(docs: list[dict], *, analyzer_version: str) -> dict`，"F2 已写死，签名逐字一致"。

### 实测证据

```text
$ PYTHONPATH=. .venv/bin/python -c "import inspect; from claims import graph; from claims.tools import rules_analyzer; from claims.deep_agents import analyzer as deep; ..."
claims.graph.run_analysis                => (docs: 'list[dict[str, Any]]', *, analyzer_version: 'str' = 'rules-1') -> 'dict'
claims.tools.rules_analyzer.run_analysis  => (docs: 'list[dict[str, Any]]', *, analyzer_version: 'str' = 'rules-1') -> 'dict'
claims.deep_agents.analyzer.run_analysis  => (docs: 'list[dict[str, Any]]', *, analyzer_version: 'str') -> 'dict[str, Any]'
```

```text
$ grep -n "from claims.deep_agents import analyzer\|result = deep_analyzer.run_analysis" claims/graph.py
54:            from claims.deep_agents import analyzer as deep_analyzer  # type: ignore
56:            result = deep_analyzer.run_analysis(docs, analyzer_version=analyzer_version)
```

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe1.py   （节选）
import claims.deep_agents => OK, __all__ = ['analyzer', 'errors', 'materials', 'prompts', 'schema', 'MaterialsAnalysis', 'MaterialsAnalysisDraft']
import deepagents => FAILED: ModuleNotFoundError
```

返回结构与 `rules_analyzer` 的一致性（详见 I2）：把 F2 的规则输出喂给 F3 的收口函数，shape 完全相等 —— 见 §3.2 的 `shape(rules) == shape(deep)` 输出。

### 判定：**一致**

- 参数名、位置、仅关键字约束三处均一致；F2 调用处恒显式传 `analyzer_version=`，因此 F3 无默认值不构成运行风险。
- `claims/deep_agents/__init__.py` 刻意不在 import 期加载 `deepagents`（F3 `analyzer.py:202` 为函数内延迟导入），所以 `.venv` 下 `import claims.deep_agents` 成功、只有真调用才抛——实测成立。
- F3 明确"不做静默降级，失败就抛，由 F2 决定是否退回规则"（`analyzer.py:496-517` docstring），与 F2 的 `try/except → rules_analyzer` 分工吻合。

### 不一致项

| ID | 等级 | 问题 | 建议修复方 + 位置 |
|---|---|---|---|
| I1-a | **blocker** | **Deep Agents 只在 `.venv-claims` 中存在，而契约没写"理赔流水线必须运行在哪个解释器"**。`.venv` 下 `DEEPAGENTS_ENABLED=true` 只会永久静默降级；`deep_agents/tests` 在 `.venv` 下 20 failed（全为 `ModuleNotFoundError: No module named 'deepagents'`），在 `.venv-claims` 下 75 passed。当前只有 `ARCHITECTURE.md:232` / `SPEC-claims.md:346` 把 `DEEPAGENTS_PYTHON` 说成"仅记录，不 subprocess"——**没有任何一处规定 e2e/CI 用哪个解释器**，这会让 t20 e2e 在默认 `.venv` 下得到"看起来正常、其实全程规则模式"的假绿。 | **F1（契约）**：在 `SPEC-claims.md` §8 增设一行「运行前提：整条理赔流水线（含 F3）必须用 `.venv-claims/bin/python` 启动；`.venv` 仅用于续保基线与 `claims/tests`」。**F4（联调）**：e2e 脚本显式用 `.venv-claims/bin/python`，并在启动时断言 `importlib.util.find_spec("deepagents")` 非空。 |
| I1-b | **degradation** | F2 用 `except Exception: pass`（`claims/graph.py:59-60`）把 F3 抛出的 `AnalysisUnavailable.error_type`（`DeepAgentsNotInstalled` / `AnalysisTimeout` / `AnalysisSchemaInvalid`）吞掉了，降级原因不可观测（轨迹面细节见 I4-b）。 | **F2**：`graph.py:59-60` 改为 `except Exception as exc:` 并把 `getattr(exc, "error_type", type(exc).__name__)` 带到后续的 `llm_degraded` 行上。 |
| I1-c | cosmetic | F2 的 `run_analysis` 有默认值 `analyzer_version='rules-1'`，F3 的同名参数**必填**。docstring 里的"签名逐字一致"严格说只在调用形态上成立（`graph.invoke` 走的是 F2 的包装）。 | F3 或 F2 任一方对齐即可；建议 F3 `analyzer.py:496` 加同默认值，或 F2 `graph.py:43` 去掉默认值。仅影响"直接调 F3"的写法。 |

---

## 3. I2 · `MaterialsAnalysis` schema 三方对账

### 契约要求

`SPEC-claims.md` §4.3（`:181-207`）给出的 JSON 结构 + 4 条硬约束（无金额字段、`quote` 必须逐字、`confidence` 非赔付概率、`analyzer.mode` 如实标注）。

### 实测证据

**（1）F2 规则实现产出 vs F3 pydantic schema**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe2.py
docs kinds = ['police_report', 'repair_quote']

--- rules_analyzer 输出顶层键 ---
['schema_version', 'claim_id', 'analyzer', 'documents', 'missing_items', 'coverage', 'cost']
analyzer = {'mode': 'rules_fallback', 'model': 'rules', 'version': 'rules-1'}
coverage = {'requested_docs': 2, 'analyzed_docs': 2}
cost     = {'tokens_in': 0, 'tokens_out': 0, 'tool_calls': 0}

--- 用 F3 的 pydantic schema 校验 F2 的 rules 输出 ---
model_validate => OK
dump 顶层键 = ['schema_version', 'claim_id', 'analyzer', 'documents', 'missing_items', 'coverage', 'cost']
assert_no_forbidden_fields => OK（无金额/决策字段）
documents[0] = {"doc_id": "doc-0001", "kind": "police_report", "facts": [{"key": "accident_time", "value": "2026年11月1日8时20分", "confidence": 0.9, "evidence": {"doc_id": "doc-0001", "span": "L1", "quote": "2026年11月...
```

**（2）F3 真实收口路径（`validate_and_enrich`）产出 vs F2 规则产出**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe7.py
顶层键 rules = ['schema_version', 'claim_id', 'analyzer', 'documents', 'missing_items', 'coverage', 'cost']
顶层键 deep  = ['schema_version', 'claim_id', 'analyzer', 'documents', 'missing_items', 'coverage', 'cost']
顶层键一致   = True

analyzer rules = {'mode': 'rules_fallback', 'model': 'rules', 'version': 'rules-1'}
analyzer deep  = {'mode': 'deepagents', 'model': 'fake:model', 'version': '9.9.9'}
coverage rules = {'requested_docs': 2, 'analyzed_docs': 2} | deep = {'requested_docs': 2, 'analyzed_docs': 2}
cost     rules = {'tokens_in': 0, 'tokens_out': 0, 'tool_calls': 0} | deep = {'tokens_in': 11, 'tokens_out': 22, 'tool_calls': 3}

doc 键一致      = True ['doc_id', 'kind', 'facts', 'consistency_notes', 'anomalies']
fact 键一致     = True ['key', 'value', 'confidence', 'evidence']
evidence 键一致 = True
整体 shape 一致 = True

pydantic required(顶层) = ['analyzer', 'coverage']
claim_id rules = '' | deep = ''
assert_no_forbidden_fields(deep) => OK（无金额/决策字段）

F2 的降级判定条件 result.get('schema_version') 对 F3 输出来说 = True
```

**（3）F2 状态字段类型**

```text
claims/state.py:  materials_analysis: dict[str, Any] | None
SPEC-claims.md §4.1:  | `materials_analysis` | `MaterialsAnalysis \| None` | `analyze_materials` | §4.3 |
```

### 判定：**一致（零偏差）**

逐项核对结果：

| 层级 | SPEC §4.3 | F2 `state.py` | F3 `schema.py` | 结论 |
|---|---|---|---|---|
| 顶层 | 7 键（`schema_version`/`claim_id`/`analyzer`/`documents`/`missing_items`/`coverage`/`cost`） | `dict[str, Any] \| None`（不约束结构） | 7 键同名同序（`schema.py:150-164`） | 一致 |
| `analyzer` | `{mode, model, version}`，`mode ∈ {deepagents, rules_fallback}` | 由实现填 | `AnalyzerInfo`，`mode: Literal["deepagents","rules_fallback"]`（`schema.py:125-132`） | 一致（且 Literal 强于 SPEC 的枚举描述） |
| `documents[]` | `{doc_id, kind, facts, consistency_notes, anomalies}` | — | 同名 5 键（`schema.py:94-103`） | 一致 |
| `facts[]` | `{key, value, confidence, evidence}` | — | 同名 4 键（`schema.py:78-86`） | 一致 |
| `evidence` | `{doc_id, span, quote}` | — | 同名 3 键（`schema.py:68-75`） | 一致 |
| `missing_items[]` | `{key, why}` | — | 同名（`schema.py:106-112`） | 一致 |
| `coverage` | `{requested_docs, analyzed_docs}` | — | 同名，均有 `ge=0`（`schema.py:135-139`） | 一致 |
| `cost` | `{tokens_in, tokens_out, tool_calls}` | — | 同名，有默认值（`schema.py:142-147`） | 一致 |
| 必填/嵌套 | `analyzer`、`coverage` 必填 | — | `required = ['analyzer','coverage']`（实测） | 一致 |
| 边界 | 顶层**无**金额/决策字段 | 未泄漏 | `ConfigDict(extra="forbid")` + `assert_no_forbidden_fields` | 一致（F3 更强） |
| `claim_id` | 由编排层填 | F2 `graph.py:195` 写入 | 默认 `""`（分析层不认 claim） | 一致 |

**语义对齐的两处细节（不算不一致，记录备查）**：
1. `analyzer.version`：SPEC 举例 `"0.7.39|rules-1"`。F2 传进去的 `analyzer_version` 恒为 `rules_analyzer.RULES_VERSION`（`"rules-1"`），但 F3 **故意不把它写进 `analyzer.version`**（`analyzer.py:501-503` 明确说明"那个字段必须是分析器真实版本，否则降级可观测性失真"），改用 `importlib.metadata.version("deepagents")`。这是**对 SPEC 举例的合理收窄**，建议 F1 在 §4.3 补一句"`version` = 分析器实现真实版本，不是调用方传入值"。
2. `facts[*].value` 允许任意 JSON 值（`schema.py:57-62` 的 `_ensure_json_value` + `:90-91` 的字段校验器），SPEC 也写 `value` 无类型限制——一致。

---

## 4. I3 · wiki 目录约定（**核心风险项**）

### 契约要求（三方三种写法）

| 出处 | 写法 |
|---|---|
| F1 契约 `SPEC-claims.md` §7（`:335`） | 知识检索用 `from server.wiki_search import WikiSearch`；`WIKI_DIR=data/llm-wiki-claims/wiki` |
| F1 契约 `SPEC-claims.md` §8.1（`:341-352`） | 环境变量表里**没有** `CLAIMS_WIKI_DIR`（只有 `CLAIMS_TRACE_DIR`/`CLAIMS_CHECKPOINT_DB`/`CLAIMS_DATA_DIR`/`CLAIMS_AMOUNT_REVIEW_THRESHOLD`/`CLAIMS_DEDUCTIBLE`/`CLAIMS_MAX_PAYABLE`/`DEEPAGENTS_ENABLED`/`DEEPAGENTS_PYTHON`） |
| F2 实现 `claims/config.py:63-64` | `def wiki_dir() -> Path: return _path("CLAIMS_WIKI_DIR", REPO_ROOT/"data"/"llm-wiki-claims"/"wiki")` —— **定义了，但全仓库无人调用** |

### 实测证据

**（1）语料根是否可注入：可注入，但默认走续保**

```text
$ sed -n '185,200p' server/wiki_search.py
class WikiSearch:
    def __init__(self, wiki_dir: Path | None = None, channels: tuple[str, ...] = DEFAULT_CHANNELS):
        self.wiki_dir = wiki_dir or config.WIKI_DIR
```

**（2）默认值 = 续保 `wiki/`，且是**相对路径**（`.env` 里的 `WIKI_DIR=./wiki` 覆盖了 `BASE_DIR/"wiki"` 这个绝对默认）**

```text
$ grep -n "^TRACE_DIR\|^WIKI_DIR" .env
9:TRACE_DIR=./traces
13:WIKI_DIR=./wiki

$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe5.py
cwd = /Users/leoms/Documents/deepseek-harness-workspace/homework5/renewal-assistant
server.config.WIKI_DIR = wiki | absolute = False
WikiSearch()  .wiki_dir = wiki | entries = 8 | available = True
search_with_score('免赔额') = [('wiki-deductible', '《合成机动车保险免赔额与免赔率适用规则（虚构）》', 'v2024.3', 0.0492), ...]

WikiSearch(wiki_dir=data/llm-wiki-claims/wiki) .entries = 0 | available = False | total_chars = 0
search_with_score('免赔额') = ([], [])
```

**（3）同一个 `WikiSearch()`，换个 cwd 就静默空返回（无异常、无告警）**

```text
$ cd /tmp && PYTHONPATH=<repo> <repo>/.venv/bin/python -c "from server.wiki_search import WikiSearch; ..."
cwd = /private/tmp
server.config.WIKI_DIR = wiki
WikiSearch().wiki_dir = wiki | entries = 0 | available = False
search_with_score(免赔额) = ([], [])
```

**（4）理赔语料目录当前内容 = 0 条目**

```text
$ find data/llm-wiki-claims -type f
data/llm-wiki-claims/wiki/.gitkeep
data/llm-wiki-claims/wiki/README.md
data/llm-wiki-claims/raw/.gitkeep
data/llm-wiki-claims/raw/README.md
```

**（5）理赔域当前没有任何代码调用 `WikiSearch` 或 `wiki_dir()`**

```text
$ grep -rn "wiki_dir\|WikiSearch\|CLAIMS_WIKI_DIR\|WIKI_DIR" claims/ --include=*.py
claims/config.py:4:`WIKI_DIR` 环境变量机制在这里被复用，但理赔域自己解析路径，避免依赖
claims/config.py:13:- `CLAIMS_WIKI_DIR`              默认 `<repo>/data/llm-wiki-claims/wiki`
claims/config.py:63:def wiki_dir() -> Path:
claims/config.py:64:    return _path("CLAIMS_WIKI_DIR", REPO_ROOT / "data" / "llm-wiki-claims" / "wiki")
```

### 判定：**无法判定（依赖 D2/D3 语料 + D5 检索层）＋ 2 个可判定的不一致**

不能判的部分：D2/D3 尚未产出任何 wiki 条目（上面 (4) 只有 `.gitkeep`/`README`），D5 检索层尚未落地，所以"理赔检索是否命中、引用是否可回溯"无从对账。

能判的部分（两条都可复现）：

| ID | 等级 | 问题 | 建议修复方 + 位置 |
|---|---|---|---|
| I3-a | **blocker** | **检索层的默认语料根是续保 `wiki/`，且随 cwd 变化。**D5 只要写 `WikiSearch()`（不传参），理赔检索就会**读续保 8 条条款**；从仓库外 cwd 启动则 `entries=0`、`search_with_score` 返回 `([], [])`——**静默空结果，不报错**。这与"隔离铁律"（`SPEC-claims.md` §8："不得写 `traces/`、`wiki/`"）和 C0 基线（`docs/log/step-c0-baseline.md` §4：`wiki/**` 只读）直接冲突。 | **D5**：构造处必须显式传参 `WikiSearch(wiki_dir=claims.config.wiki_dir())`，并在 `entries == 0` 时**显式报错**（不要让空语料静默通过）。**F2**：把 `claims/config.py:63` 的 `wiki_dir()` 变成唯一入口并被 D5 使用。**F1**：§7 的 `WIKI_DIR=data/llm-wiki-claims/wiki` 改为 `CLAIMS_WIKI_DIR`（或反过来说明二者等价映射，见 I3-b）。 |
| I3-b | degradation | **同一件事两个变量名**：契约 §7 写 `WIKI_DIR`（续保 env），F2 实现写 `CLAIMS_WIKI_DIR`，而 §8.1 的配置表**一个都没登记** `CLAIMS_WIKI_DIR`。三者并存时无法判断"哪个是权威"。且 `server.config` 的 `.env` 解析把 `WIKI_DIR=./wiki` 直接吃进来（`server/config.py:44`），把绝对路径默认降级成 cwd 相对——本次实测的 cwd 敏感性就是这么来的。 | **F1**：在 §8.1 补 `CLAIMS_WIKI_DIR` 一行，并在 §7 注明"理赔域不读 `server.config.WIKI_DIR`"。**F2**：`claims/config.py:64` 保持默认，但在 docstring 写明"唯一权威"。**（不建议改 `server/config.py`，那是保护对象）** |

> 补充：`data/llm-wiki-claims/wiki/README.md` 已经把"必须 `export WIKI_DIR=$PWD/data/llm-wiki-claims/wiki`"写进去了——但那用的是**续保变量名**，且没有人真的消费 `CLAIMS_WIKI_DIR`。文档口径本身也在参与这个不一致。

---

## 5. I4 · 轨迹写入

### 契约要求

`SPEC-claims.md` §6.2（`:266-268`）：
1. 必须复用 `server/trace.py::TraceRecorder`，**只允许既有 11 种 `record_type`**，不得新增；
2. 理赔语义全部放 `event.kind`，**强制 `claims.` 前缀**，无前缀要 `raise ValueError`；
3. 轨迹落 `traces-claims/`，`traces/` 不许写。

### 实测证据

**（1）11 种白名单（续保侧，未改动）**

```text
$ .venv/bin/python -c "from server.trace import RECORD_TYPES; print(len(RECORD_TYPES)); print(sorted(RECORD_TYPES))"
11
['assistant_message', 'error', 'llm_call', 'llm_degraded', 'llm_response', 'node_end', 'node_start', 'retrieval', 'tool_call', 'tool_result', 'user_message']
```

**（2）理赔实际写入的 `record_type` 全集（多次端到端运行后）**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe4.py     （节选）
record_type 全集 = ['node_start']
是否存在 record_type=llm_degraded 行 = False
是否存在 event.kind=claims.llm_degraded 行 = True
轨迹行是否带 error_type 字段 = [False]
```

**（3）`claims.*` 前缀守卫确实生效**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe6.py     （节选）
=== 前缀守卫（无 claims. 前缀必须 raise）===
raise ValueError: 非法 event：review_approved（必须以 claims. 开头）
```

**（4）`event.kind` 全集（自动快赔 + 人工审核 + 补件三条路径合起来）**

```text
['claims.assessed', 'claims.auto_approved', 'claims.closed', 'claims.intake_accepted',
 'claims.intake_duplicate', 'claims.intake_invalid', 'claims.llm_degraded',
 'claims.materials_analyzed', 'claims.materials_missing', 'claims.payment_charged',
 'claims.payment_key_reserved', 'claims.review_requested', 'claims.review_approved']
```

**（5）落点隔离：注入 `CLAIMS_TRACE_DIR` 后，续保 `traces/` 零写入**

```text
$ ls traces | wc -l        → 1183（探针前后均为 1183）
$ ls -la traces-claims/    → 只有 .gitkeep + README.md（仓库内无任何理赔轨迹残留）
$ git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md   → 空
```

**（6）PII 不进轨迹（弱证据，但方向正确）**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe4.py     （节选，材料里塞了手机号/身份证）
轨迹中 13800138000 出现次数 = 0 | 110101199001011234 出现次数 = 0
```

> 注意这是**弱证据**：材料正文从来没进轨迹（`input`/`output` 恒 `null`），所以"没出现"不等于"脱敏逻辑正确"。真正的 PII 断言要看 `server.trace` 的 `redact_row`（续保侧既有）与 CLM-17 用例。

### 判定：**一致（三条硬约束全部成立）**，但发现 2 个语义缺口

| ID | 等级 | 问题 | 建议修复方 + 位置 |
|---|---|---|---|
| I4-a | **degradation** | **每条新案的第一行 `claims.intake_accepted` 落到 `unknown.jsonl`，不是 `CLM-*.jsonl`。** 原因：`intake` 里在算出 `claim_id` 之后调用 `self.record(state, ...)`，而 `state` 此时还没有 `claim_id`；`recorder()` 用 `state.get("claim_id") or "unknown"` 建录制器（`claims/graph.py:105-120`），于是这一行写进了 `unknown.jsonl`。实测每次新案都复现，多条案子的 intake 行全混在同一个 `unknown.jsonl` 里。 | **F2**：`claims/graph.py:156` 改为 `self.recorder({**state, "claim_id": claim_id}).record(...)`，或让 `intake` 先 `return` 后在 `node_end` 统一记。**影响**：CLM-20「同 claim_id 轨迹可重放」会缺首行，审计视图分裂；`unknown.jsonl` 无界增长。 |
| I4-b | **degradation** | **降级行不是 `llm_degraded` 行，且丢失降级原因。** SPEC §9（`:360`）明确"任何降级都要在轨迹留 `llm_degraded` 行（`error_type="DeepAgentsUnavailable"`）"。实测该行是 `record_type="node_start"` + `event.kind="claims.llm_degraded"`，**没有 `error_type` 字段**；且 F2 用 `except Exception: pass`（`claims/graph.py:59-60`）吞掉了 F3 抛出的 `AnalysisUnavailable.error_type`（如 `DeepAgentsNotInstalled` / `AnalysisTimeout` / `AnalysisSchemaInvalid`）。后果：C5 排查"为什么全降级"时只能看到"降级了"，看不到"为什么降级"。 | **F2**：`claims/graph.py:205-206` 改为 `self.recorder(state).record("llm_degraded", node=node, mode="rules_fallback", error_type=<捕获到的 error_type>)`（`llm_degraded` 在 11 种白名单内，不违反 §6.2）；`graph.py:59-60` 的 `except` 改为捕获 `exception as exc` 并把 `getattr(exc, "error_type", type(exc).__name__)` 带出去。 |

---

## 6. I5 · 环境变量默认值与生效点

### 契约要求

`SPEC-claims.md` §8.1（`:341-352`）8 个变量；本次只核对任务书点名的 4 个（其余顺带核对）。

### 实测证据

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe1.py     （未注入任何环境变量）
deepagents_enabled()      = False
deepagents_python()       = /Users/.../renewal-assistant/.venv-claims/bin/python
trace_dir()               = /Users/.../renewal-assistant/traces-claims
checkpoint_db()           = /Users/.../renewal-assistant/claims/data/checkpoints.sqlite
data_dir()                = /Users/.../renewal-assistant/claims/data
wiki_dir()                = /Users/.../renewal-assistant/data/llm-wiki-claims/wiki
amount_review_threshold() = 3000.0
```

生效点（静态 + 运行时）：

| 变量 | config.py 默认 | SPEC §8.1 | 实际生效点 | 结论 |
|---|---|---|---|---|
| `DEEPAGENTS_ENABLED` | `false`（`config.py:43`） | `false` | `graph.py:52` `if config.deepagents_enabled()` | ✅ 一致（实测 `true` 后果见 I1-a：`.venv` 下永久降级） |
| `DEEPAGENTS_PYTHON` | `<repo>/.venv-claims/bin/python`（`config.py:46-48`） | `.venv-claims/bin/python`（"仅记录"） | **无任何调用点**（`grep -rn "deepagents_python(" claims/` 只命中定义本身） | ⚠️ cosmetic：默认值一致（相对 vs 绝对），但"记录用"这个用途也没实现 |
| `CLAIMS_CHECKPOINT_DB` | `claims/data/checkpoints.sqlite`（`config.py:59-60`） | 同 | `graph.py:95` `config.checkpoint_db()` → `SqliteSaver` | ✅ 一致（实测注入后 db 落在 `$CLAIMS_CHECKPOINT_DB`） |
| `CLAIMS_AMOUNT_REVIEW_THRESHOLD` | `3000.0`（`config.py:75-77`） | `3000` | `graph.py:399` `route_risk(... threshold=config.amount_review_threshold())` | ✅ 一致（实测设为 `0` 时必进 `review_gate`） |
| `CLAIMS_TRACE_DIR` | `traces-claims`（`config.py:51-52`） | `traces-claims` | `graph.py:97` | ✅ 一致 |
| `CLAIMS_DATA_DIR` | `claims/data` | `claims/data` | 只覆盖 checkpoint/幂等登记/缓存（`config.py:91`）；**不覆盖 F3 材料工作区** | ⚠️ degradation（见 I5-c） |
| `CLAIMS_WIKI_DIR` | `data/llm-wiki-claims/wiki`（`config.py:63-64`） | **未登记** | **无任何调用点** | ⚠️ 与 I3-b 同一问题 |
| `CLAIMS_DEDUCTIBLE` / `CLAIMS_MAX_PAYABLE` | `500` / `20000` | `500` / `20000` | `graph.py:227-229` | ✅ 一致 |

### 判定：**不一致**

| ID | 等级 | 问题 | 建议修复方 + 位置 |
|---|---|---|---|
| I5-a | **degradation** | `CLAIMS_WIKI_DIR` 在实现里存在、在契约 §8.1 里不存在，且无消费点（同 I3-b，从"配置表完整性"角度看是文档缺口）。 | **F1** `SPEC-claims.md:341-352` 补一行；**F2** 让 `wiki_dir()` 被真实调用（D5）。 |
| I5-b | cosmetic | `DEEPAGENTS_PYTHON` 无生效点：既没有 subprocess（SPEC 允许），也没有任何日志/轨迹记录（SPEC 说"仅记录"）。 | **F2** 在 `ClaimGraph.__init__` 或 `analyze_materials` 的 `llm_degraded` 行里带上 `deepagents_python` 值即可闭环。 |
| I5-c | **degradation** | **`CLAIMS_DATA_DIR` 不是"材料根"的唯一真相。** SPEC §8.1 把它描述为「材料/缓存/幂等登记根目录」，但 F3 的材料工作区硬编码在 `claims/deep_agents/materials.py:165-168`（`materials_root()` = `claims/data/materials`），**完全无视 `CLAIMS_DATA_DIR`**。实测把 `CLAIMS_DATA_DIR` 指到 `/tmp` 后，`materialize()` 仍拒绝工作区并报 `MATERIAL_MISSING/UnsafeWorkspaceRoot`：`工作区必须位于 .../claims/data/materials 之内，实际为 /private/var/.../x1-i2-*`。 | **F3**：`materials.py:165-168` 改为 `Path(os.environ.get("CLAIMS_DATA_DIR", default))/"materials"`（并保留 `safe_workspace_root` 的越界断言）；或 **F1** 在 §8.1 把 `CLAIMS_DATA_DIR` 的适用范围收窄为"checkpoint/缓存/幂等"，另立 `CLAIMS_MATERIALS_DIR`。**这条会让 `claims/tests` 的 `tmp_env` 夹具看起来"隔离了"，实际 F3 材料仍写仓库** —— 集成时容易误判。 |
| I5-d | **degradation** | **F3 引入了 6 个未在 SPEC §8.1 登记的环境变量**：`DEEPAGENTS_MODEL`、`DEEPAGENTS_TIMEOUT_S`、`DEEPAGENTS_MAX_ATTEMPTS`、`DEEPAGENTS_RECURSION_LIMIT`、`DEEPAGENTS_SUBAGENTS`、`CLAIMS_ANALYSIS_KEEP_WORKSPACE`（`analyzer.py:110-125`），另有 `ANTHROPIC_*`/`MODEL_NAME` 复用（`analyzer.py:168-170`）。契约缺登记 → C5 "环境变量清单"无法逐条验收。 | **F1**：§8.1 增补这 6 行（含默认值：`120.0`/`2`/`40`/`true`/`false`）。 |

---

## 7. I6 · 检查点与并发

### 契约要求

- 入口 `durability="sync"`、`recursion_limit=40` 走**顶层 config 键**（`SPEC-claims.md` §3.1 `:107`；`claims/graph.py:6`）。
- checkpoint 本域私有 `claims/data/checkpoints.sqlite`（§8 `:337`）。
- 同一 thread 二次 invoke 的语义见 §3.2（补件续跑）。

### 外部依据（本次检索，判定"顶层 config 键"是否正确的基准）

- LangGraph 官方文档（经 Context7 取回）：`durability` 是**执行方法的参数**（`graph.invoke(input, config, durability="sync")`），语义为"在下一步开始前同步落盘；新 thread 会先提交输入检查点（step `-1`）与 step `0`，再执行第一个用户节点" —— 与 §3.1「受理即落盘」一致。
- `recursion_limit` 是**运行 config 里的键**（`graph.invoke({...}, {"recursion_limit": 4})`），超限抛 `GraphRecursionError`。

### 实测证据

**（1）实参形态（静态）**

```text
$ grep -n "cfg = {\|durability=" claims/graph.py
464:        cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
465:        return self.graph.invoke(claim_input, cfg, durability="sync")
469:        cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
470:        return self.graph.invoke(Command(resume=decision), cfg, durability="sync")
```

**（2）人工中断 + 跨实例（新 `ClaimGraph` 同 DB = 伪跨进程）resume**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe6.py     （阈值 0 强制人工）
首轮 status        = review_pending
__interrupt__ 存在 = True
state.values.status = review_pending | state.next = ('review_gate',)

--- 另建 ClaimGraph（同 DB）---
进程 B get_state().values.status = review_pending | next = ('review_gate',)
resume 后 status   = paid | approval_version = 1 | payment_key = pay-3cb65bce55b3b1f16372cf9d
网关 charge 次数   = 1
全部 attempt 记录  = [{"op": "charge", "payment_key": "pay-3cb65bce...", "amount": 2100.0}]

=== checkpoint DB 实况 ===
表 = ['checkpoints', 'writes']
  checkpoints 行数 = 12
  writes 行数 = 48
```

**（3）同一 thread 补件续跑（契约 §3.2 语义）**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe4.py     （节选）
首轮 status = need_info | missing_docs = ['repair_quote'] | __interrupt__ = None | state.next = ()
补件后 status = paid | payable = 2100.0 | payment_key = pay-03f6113d025ca76849db | state.next = ()
```

**（4）终态线程再 invoke / 再 resume**

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe9.py
第1次 invoke: status = paid | approval_version = 1 | charge 次数 = 1
第2次 invoke: status = paid | approval_version = 1 | charge 次数 = 2
第3次 invoke: status = paid | charge 次数 = 3 | gateway.attempts 条数 = 3
terminated 后 state.next = ()
3 次 invoke 后轨迹行数 = 22 | claims.closed（结案）次数 = 3
ALLOWED_TRANSITIONS 是否含 paid 起点 = False
guard_transition('paid','verifying') => CLAIM_STATE_INVALID
```

```text
$ PYTHONPATH=. .venv/bin/python /tmp/x1_probe6.py     （节选，已 paid 后再 resume）
=== 二次 resume（同一 thread 已 paid 再 resume）===
status = paid | errors = []
```

**（5）两套测试并存时是否冲突**

```text
$ .venv/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
20 failed, 101 passed in 0.56s          （20 个失败全是 ModuleNotFoundError: No module named 'deepagents'）

$ .venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
121 passed in 3.72s

分环境拆开：
.venv          claims/tests 46 passed        | deep_agents/tests 20 failed, 55 passed
.venv-claims   claims/tests 46 passed        | deep_agents/tests 75 passed
```

### 判定：**一致（配置形式与官方语义吻合；中断/恢复/补件续跑均按契约工作）** ＋ 2 个语义缺口 ＋ 1 条环境 blocker（与 I1-a 同源，不重复计数）

| ID | 等级 | 问题 | 建议修复方 + 位置 |
|---|---|---|---|
| I6-a | **degradation** | **终态线程再 invoke 会重跑全流程并再次调用 `gateway.charge`**（实测 3 次 invoke → charge 3 次）。钱没重复扣是因为**网关按 `payment_key` 去重**（`payment_gateway.py:41-44` 返回既有记录），但：①`ALLOWED_TRANSITIONS` 里没有 `paid` 起点，`guard_transition('paid','verifying')` 本应报 `CLAIM_STATE_INVALID`，实际却因 `intake` 先把 `status` 重置成 `intake` 而**绕过守卫**；②轨迹里出现 3 次 `claims.closed`，审计视图被污染。 | **F2**：`graph.py:380-384` 的 `route_after_intake` 增加终态守卫——`if str(state.get("status")) in Status.TERMINAL: → END + CLAIM_STATE_INVALID`（需先保留旧 status，可在 `intake` 开头读 `prev = state.get("status")` 并在返回时带回错误）。 |
| I6-b | **degradation** | **同一 thread 二次 `resume` 静默成功**（返回 `status=paid, errors=[]`），没有 `CLAIM_STATE_INVALID`/`REVIEW_DECISION_INVALID`。人工重复点"通过"不会报错，也无法从返回值看出"这次决策被忽略"。 | **F2**：`graph.py:467-470` `resume()` 先查 `self.state(thread_id).next`，若为空（无待恢复中断）直接 `raise ClaimError(CLAIM_STATE_INVALID, "无待恢复的中断")`。 |
| I6-c | —（与 I1-a 同源，不重复计数） | 两套测试在 `.venv` 下 20 failed / 在 `.venv-claims` 下全绿——**"同一 thread 二次 invoke"这类跨进程语义要验，必须用 `.venv-claims`**；否则 C5 会看到 20 个与契约无关的假红。 | 同 I1-a：在 SPEC §8 写明运行前提，e2e/CI 显式用 `.venv-claims/bin/python`。 |

---

## 8. 问题清单（按等级汇总，便于派单）

### blocker（2）

| ID | 一句话 | 修复方 | 落点 |
|---|---|---|---|
| **I1-a**（I6-c 同源，不重复计） | Deep Agents 只在 `.venv-claims`；契约未规定运行解释器 → e2e 可能"假绿"（全程规则模式）或"假红"（20 failed） | F1（写契约）+ F4（e2e 脚本断言） | `SPEC-claims.md` §8 新增"运行前提"；e2e 启动即断言 `find_spec("deepagents")` |
| **I3-a** | 检索层默认读续保 `wiki/`，且 cwd 相对 → 静默空结果，违反隔离铁律 | D5（显式传 `wiki_dir` + 空语料报错）+ F2（提供唯一入口） | `WikiSearch(wiki_dir=claims.config.wiki_dir())`；`server/wiki_search.py` 不改 |

### degradation（9）

| ID | 一句话 | 修复方 |
|---|---|---|
| I1-b | `except Exception: pass` 吞掉 `AnalysisUnavailable.error_type`，降级原因不可观测 | F2 `graph.py:59-60` |
| I3-b | `WIKI_DIR` / `CLAIMS_WIKI_DIR` 双轨，§8.1 未登记 | F1 §7/§8.1 + F2 docstring |
| I4-a | 新案首行 `claims.intake_accepted` 落到 `unknown.jsonl` | F2 `graph.py:156` |
| I4-b | 降级行不是 `llm_degraded` 行、无 `error_type` | F2 `graph.py:205-206` |
| I5-a | `CLAIMS_WIKI_DIR` 无消费点（同 I3-b 的配置面） | F1 + F2/D5 |
| I5-c | `CLAIMS_DATA_DIR` 不覆盖 F3 材料工作区（硬编码 `claims/data/materials`） | F3 `materials.py:165-168`（或 F1 收窄语义） |
| I5-d | F3 的 6 个 env 未在 SPEC §8.1 登记 | F1 |
| I6-a | 终态线程再 invoke 重跑全流程、再调 `charge`、绕过状态守卫、重复 `claims.closed` | F2 `graph.py:380-384` |
| I6-b | 二次 `resume` 静默成功 | F2 `graph.py:467-470` |

### cosmetic（2）

| ID | 一句话 | 修复方 |
|---|---|---|
| I1-c | `run_analysis` 默认值不对称（F2 有、F3 无） | F2/F3 任一方 |
| I5-b | `DEEPAGENTS_PYTHON` 无生效点（连"记录"都没记录） | F2 |

---

## 9. 依赖与"无法判定"项

| 项 | 依赖 | 现状证据 | 解除条件 |
|---|---|---|---|
| I3 全部内容类判定（命中率、引用可回溯） | **D2/D3**（wiki 语料）+ **D5**（检索层） | `data/llm-wiki-claims/wiki/` 只有 `.gitkeep` + `README.md`（0 条目）；`grep WikiSearch claims/` 无命中 | D2 产出条目 + D5 落地检索后重跑本文件 §4 的 3 条命令 |
| I4 的 SSE/事件面（`tool_call`/`await_confirm`/`token`） | **F4/API 层** | `claims/` 里没有 FastAPI 路由、没有 `server.app` 接入 | API 层落地后对 `SPEC-claims.md` §6.1 逐 event 核对 |
| I6 的 CLM-19（`recursion_limit=40` 真触发） | 需构造循环 fixture | 本次只验"配置键在顶层、形态正确" | 新增 CLM-19 用例后以 `GraphRecursionError` 断言 |
| 真实 Deep Agents 路径（`mode="deepagents"`） | 需模型凭证 + `.venv-claims` | `.venv-claims` 有 `deepagents==0.7.39`，但本次未调用真实模型（F3 用假模型离线验） | t20 e2e 用 `.venv-claims` + `.env` 凭证跑一次 |

---

## 10. 附录：非本次 6 条契约的旁见（交给 C5，勿在 X1 修）

1. **`server.metrics` 完全未接入理赔域**：`SPEC-claims.md` §7 声称复用 `server.metrics.observe_record / finish_turn`，`grep -rn "server.metrics" claims/` 无命中。→ 理赔在续保的 Prometheus 面板里"不可见"。
2. **§3.2 的 `analysis_key` 缓存未实现**：`claims/config.py:71-72` 定义了 `analysis_cache_dir()`，但全仓库无 `analysis_key` 计算、无缓存读写。→ 同案重跑会重复消耗 token（Deep Agents 路径下是真实成本）。
3. **`claims/data/materials/` 有 2 个测试残留工作区**（`analysis-o_jfruvk`、`analysis-y62k4os6`）：已被 `.gitignore:75 claims/data/**` 忽略，但 C5 前建议清理，避免"看起来有未提交产物"。
4. **保护对象零污染（好消息）**：`git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md` **空输出**；`traces/` 计数 1183 未变；`traces-claims/` 仓库内仍只有 `.gitkeep` + `README.md`（本次探针全部写 tmp）。

---

## 11. 检索依据（本次抓取，判定标准的外部来源）

| # | 来源 | URL | 检索时间 | 用于支撑的判定 |
|---|---|---|---|---|
| S1 | LangGraph 官方文档 · checkpointers / durability（经 Context7 MCP 取回） | https://docs.langchain.com/oss/python/langgraph/checkpointers | 2026-11-18 | I6：`durability` 是**执行方法参数**、`"sync"` = 下一步前同步落盘 + 新 thread 先提交输入检查点 → 判定 F2 的 `invoke(..., durability="sync")` 形态正确、且与 §3.1「受理即落盘」语义吻合 |
| S2 | LangGraph 官方文档 · 控制流 / recursion_limit（经 Context7 MCP 取回） | https://docs.langchain.com/oss/python/langgraph/graph-api-control-flow | 2026-11-18 | I6：`recursion_limit` 是运行 config 的键、超限抛 `GraphRecursionError` → 判定 F2 把它放进 `cfg` 而不是方法参数是正确的 |
| S3 | Pact · Introduction（contract testing：按"共享理解的契约"逐点校验，而不是靠整体集成测试） | https://docs.pact.io/ | 2026-11-18 | §1/§0 方法论：为什么"先静态对账再联调"、为什么每条结论要落到"接口点 + 双向证据" |
| S4 | 项目内规范 · C0 基线（`docs/log/step-c0-baseline.md` §4 保护对象 / §8 来源） | 本地文件 | 2026-11-18 | I4/I3 判定"是否越界"的基准（`wiki/`、`traces/`、`server/` 只读） |

> S1/S2 均为本次通过 Context7 MCP 实时取回的官方文档片段（非内置记忆）；S3 为契约测试方法的权威说明。S4 是团队内既有基线，用于"隔离铁律"的判定。

---

## 12. 复跑方式（C5 / 后续 agent 照抄）

```bash
cd renewal-assistant
# 0) 互不污染地跑（全部写 tmp）
export PYTHONPATH=.

# 1) 签名与默认值
.venv/bin/python /tmp/x1_probe1.py      # 若脚本已删，见本文件 §2/§6 的等价 -c 命令

# 2) schema 三方对账（规则输出 → F3 pydantic；F3 收口 → shape 对比）
.venv/bin/python /tmp/x1_probe2.py
.venv/bin/python /tmp/x1_probe7.py

# 3) 端到端（自动快赔 / 人工审核 / 补件续跑 / 终态再 invoke）
.venv/bin/python /tmp/x1_probe3.py
.venv/bin/python /tmp/x1_probe4.py
.venv/bin/python /tmp/x1_probe6.py
.venv/bin/python /tmp/x1_probe9.py

# 4) wiki 语料根与 cwd 敏感性
.venv/bin/python /tmp/x1_probe5.py
cd /tmp && PYTHONPATH=<repo> <repo>/.venv/bin/python -c "from server.wiki_search import WikiSearch; print(len(WikiSearch().entries))"

# 5) 两套测试并存
.venv/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
.venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
```

> 探针脚本在 `/tmp` 下，重启后可能消失；所有断言都可以用本文件里的 `-c` 片段重建（每节都贴了命令行与输出）。

---

## 13. 变更记录

| 时间 | 变更 | 作者 |
|---|---|---|
| 2026-11-18 16:50 | 初版：6 条接口全量对账（blocker 2 / degradation 9 / cosmetic 2），I3 因 D2/D3/D5 未完成判"无法判定" | integrate（t19 attempt 2） |
