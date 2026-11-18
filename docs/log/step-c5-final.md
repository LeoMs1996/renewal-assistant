# Step C5b — 独立最终复验（非作者视角）

| 项 | 值 |
|---|---|
| 任务 | t32 / C5b |
| 复验人 | dataset-lead（只写过 D1/R2/D2b 数据管线，**未参与** claims / wiki / F2–F4 任何代码） |
| 复验快照 | **2026-11-19 01:37:43 CST** |
| 代码基线 | `40541d1`（baseline） |
| 落定确认 | 快照前 15 分钟内 `claims/`、`data/llm-wiki-claims/`、`docs/log/`、`scripts/` **零文件被改动**（`find … -newermt "-15 minutes"` 空输出） |
| 产出 | 仅本文件。**未改任何代码 / wiki / 轨迹** |

---

## 0. 判定总表（三选一，无"基本通过"）

| # | 项 | 判定 | 一句话依据 |
|---|---|---|---|
| 1.1 | `.venv` 全量 pytest | **通过** | `148 passed, 2 skipped`（与期望逐字一致）|
| 1.2 | `.venv` `claims/tests` | **通过（附 P1 重要脚注）** | 快照时 `86 passed`；但 **00:57 首次运行时是 collection ERROR**，01:05:38 由 flow-engineer 修复（详见 §7 P1）|
| 1.3 | `.venv-claims` `claims/tests` + `deep_agents/tests` | **通过** | `168 passed` |
| 1.4 | `.venv` `deep_agents/tests`（预期失败）| **通过**（失败原因已核实） | `24 failed, 58 passed`，失败根因**唯一**：`No module named 'deepagents'` |
| 2 | 端到端门禁 ×2（我跑了 3 次） | **通过** | 3 次均 `PASS 8 / FAIL 0`；`traces-claims` 678→809→940→1071（每次 +131）|
| 3 | 隔离性三指标 | **通过** | `git diff` 空；`traces/` 1183 顶层 / 2090 递归，跑 demo 前后不变；`traces-claims` 仅 8 个 `CLM-*.jsonl` |
| 4 | wiki 两套 lint（复跑，不引用历史） | **通过** | `FAIL=0 WARN=0` / `ERROR=0 WARN=0`（各 36 页 36 索引行）|
| 4b | 6 条断言回 raw 逐字核对 | **通过** | 6/6 逐字一致（§4.2 对照表）|
| 5 | ruff 门禁 | **通过** | `All checks passed!` |
| 6.1 | 代码修改前有检索 + 时序 | **通过** | 4 份 `docs/research/**` 均有来源表；检索时间 00:00–00:52 **早于**产物 mtime 03:04 / 15:36 / 21:31 |
| 6.2 | 来源独立性 | **通过** | 6 个独立域名（hf-mirror / github / arxiv / huggingface.co / api.github.com / datasets-server），非同一域名刷 URL |
| 6.3 | 来源真影响实现 | **通过** | 4 个技术点均指到 `文件:行号`（§6.3）|
| 6.4 | 文档全程 + 决策可追溯 | **通过** | 28 份 step 日志；`decisions.md` **26/26** 条 D 编号均被至少 1 个非台账文件引用 |
| 6.5 | 只抽样不拉全量 | **通过** | `bytes_fetched=57,898,730`＝源的 `2.00%`；仓库内 **0 个 .tsv**；`data/ins-mmbench` 34 MB |
| 6.6 | 子 Agent 知情硬约束 | **通过** | 抽 3 份产物（d1/r3/f2）均复述"≥3 来源"；4 份 research 全部带 URL+时间+用途 |
| 7 | 陌生人按 `docs/README.md` 可复现 | **通过（附 2 个前提）** | 命令 ①–④ 全通；⑤ `e2e_smoke.sh` README 自陈未执行 |

> **一句判定：`可交付`。**
> 阻断项 0 个；登记 5 条非阻断发现（P1 为"已在复验期间修复的回归"，必须留档，因为它正是 C5b 存在的理由）。

---

## 1. 四套测试（原文）

快照 `2026-11-19 01:37:43`，全部我自己跑。

### 1.1 `.venv/bin/python -m pytest -o addopts="" -q`

```text
..........s............................................................. [ 96%]
......                                                                   [100%]
148 passed, 2 skipped in 2.55s
```
✅ 与期望 `148 passed, 2 skipped` 逐字一致。

### 1.2 `.venv/bin/python -m pytest claims/tests -o addopts="" -q`

**快照时（01:37）**：
```text
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 2.47s
```

**⚠️ 但我 00:57 第一次跑时它是红的**（原文）：
```text
claims/api.py:365: in create_app
    report = assert_preflight(strict=strict)
claims/api.py:128: in assert_preflight
    raise RuntimeError("；".join(problems))
E   RuntimeError: deepagents 不可导入（D-22）：请用 .venv-claims/bin/python 启动；若只要跑规则模式，请显式设 CLAIMS_ALLOW_RULES_ONLY=1
ERROR claims/tests/test_f4_api.py - RuntimeError: deepagents 不可导入（D-22）...
!!! Interrupted: 1 error during collection !!!
1 error in 0.48s
```
手动加 `CLAIMS_ALLOW_RULES_ONLY=1` 后可过（`86 passed`），说明**不是代码缺陷，是收集期环境缺省**。
**修复落地时间：`claims/tests/conftest.py` mtime = 2026-11-19 01:05:38**（不是我改的，是 flow-engineer 在 t31 期间补的 `_os.environ.setdefault("CLAIMS_ALLOW_RULES_ONLY","1")`）。详见 §7 P1。

### 1.3 `.venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q`

```text
........................................................................ [ 85%]
........................                                                 [100%]
168 passed in 6.59s
```
✅ 全绿（86 + 82 = 168）。

### 1.4 `.venv/bin/python -m pytest claims/deep_agents/tests -o addopts="" -q`（**预期失败**）

```text
24 failed, 58 passed in 0.37s
```
**失败原因核实（这是 D-22 的证据，我逐条归类）**：
```text
$ … | grep -oE "AnalysisUnavailable|ModuleNotFoundError|No module named 'deepagents'" | sort | uniq -c
  57 AnalysisUnavailable
  49 ModuleNotFoundError
  23 No module named 'deepagents'
```
- 首个失败的调用链：`claims/deep_agents/analyzer.py:202 → ModuleNotFoundError: No module named 'deepagents'`
- 继而被包装为：`claims.deep_agents.errors.AnalysisUnavailable: [ANALYSIS_UNAVAILABLE/DeepAgentsNotInstalled] deepagents 未安装或不可导入（本应装在 .venv-claims）`
- **24 个失败的原因全部同源（deepagents 缺失），无一例是"测试写错"或"逻辑回归"** → 符合预期，符合 D-22。

---

## 2. 端到端门禁（跑了 3 次，不是 2 次）

```bash
cnt() { cat traces-claims/*.jsonl | wc -l; }
PYTHONPATH=. .venv-claims/bin/python claims/demo_claim.py
```

| 次序 | 时刻 | 结果 | `traces-claims` 行数 | 增量 |
|---|---|---|---|---|
| 1 | 01:10 | `总计 8 项，PASS 8，FAIL 0，耗时 0.13s` | 678 → **809** | +131 |
| 2 | 01:11 | `总计 8 项，PASS 8，FAIL 0，耗时 0.19s` | 809 → **940** | +131 |
| 3 | 01:38 | `总计 8 项，PASS 8，FAIL 0，耗时 0.14s` | 940 → **1071** | +131 |

- **每次 +131 行，步长恒定** → 与 t31 的"轨迹累加（append-only）"解释一致：不覆盖旧轨迹，每次运行追加等量事件。
- `traces-claims/*.jsonl` 文件数 **恒为 8**（E1–E6 + D 共 8 个 `CLM-*.jsonl`）→ 是**同一批文件被追加**，不是新建文件。
- demo 自带的 A 断言也自报 `traces_before: 1176, traces_after: 1176`、`trace_dir_isolated: true` → 隔离自检通过。

---

## 3. 隔离性（三条硬指标）

```bash
$ git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md claims/SPEC-claims.md
（空输出）
```
✅ 基线保护域**零改动**。

```bash
$ find traces -type f | wc -l
2090
$ ls traces | wc -l
1183
$ ls traces-claims/*.jsonl | wc -l
8
```
| 指标 | 值 | 判定 |
|---|---|---|
| `traces/` **顶层条目**（任务书口径，= C0 基线 1183）| **1183** | ✅ 与基线一致 |
| `traces/` **递归文件数** | **2090** | ✅ 跑 demo 前后不变 |
| `traces/*.jsonl`（demo 自检口径）| **1176** | ✅ 跑 demo 前后不变 |
| `traces-claims/*.jsonl` | **8** | ✅ 仅理赔轨迹（`CLM-20261101…` 等 8 个 + README.md），无续保轨迹混入 |

**口径说明（避免误判）**：同一目录有三个合法计数——1183（顶层条目，含 `memory/`、`checkpoints.sqlite*`、2 个 json）、2090（递归全文件，含 `memory/` 子目录）、1176（仅顶层 `*.jsonl`，demo 用的口径）。**三者跑 demo 前后均不变**，隔离结论不受口径影响。

---

## 4. wiki 一致性（D-25 要求复跑，未引用 t23/t26 结论）

### 4.1 两套 lint（我自己跑，01:37 快照）

```text
$ python data/llm-wiki-claims/scripts/wiki_lint.py
pages=36 index_rows=36 FAIL=0 WARN=0

$ python data/llm-wiki-claims/scripts/wiki_claims_lint.py
=== wiki_claims_lint（独立实现）===
pages=36 index_rows=36 ERROR=0 WARN=0
```
✅ 两套独立实现均 0 错。⚠️ 同时注意：**0 错 ≠ 内容正确**（见 §4.3）。

### 4.2 我自己抽的 6 条断言，逐字回 raw 核对

抽样规则：4 类页（entities / faqs / sections / docs）各 ≥1，`labels.*` 与 `Lx-Ly` 两种跨度都要覆盖。
`qid → raw` 映射约定：`agri_0 → raw/sources/raw-agri-0000.json`（实测成立）。

| # | 页面（类型） | 断言 | raw 文件 | raw 实际值 | 判定 |
|---|---|---|---|---|---|
| 1 | `entities/claim-decision.md` | `property_0@labels.claim_decision` | `raw-property-0000.json` | `'Full compensation'` | ✅ wiki 表列同为 `Full compensation` |
| 2 | `entities/claim-decision.md` | `property_0@L1-L1` | 同上 | L1 = `You are an expert in property insurance assessment. Here are two satellite images of the same area. …` | ✅ wiki 第 21 行引文与 L1 **逐字相同** |
| 3 | `faqs/agri.md` | `agri_0@labels.species` | `raw-agri-0000.json` | `'grape'` | ✅ wiki 行 `grape \| 1 \| YES \| Partial Compensation` |
| 4 | `faqs/agri.md` | `agri_0@L13-L17` | 同上 | L13-L17 = `Please strictly output in this format: / 1. Crop species… / 4. Insurance decision: …` | ✅ wiki 引文块 5 行**逐字相同** |
| 5 | `sections/agri-compensation-tier.md` | `agri_0@labels.claim` | 同上 | `'Partial Compensation'` | ✅ wiki 表列同为 `Partial Compensation` |
| 6 | `docs/ins-mmbench-agricultural.md` | `agri_0@L1-L17` | 同上 | 全文 17 行（题干 + 保单条款 + 输出模板）| ✅ wiki 行记录 `1 \| 17` 且正文引述一致 |

**6/6 通过**，且每条断言的 `source.revision` 均为 `b77ea65c18c6…`（与 `data/ins-mmbench/manifest.json` 的 pin 一致）。
另核：`raw.sample` 与 `raw.labels` 字段与 D1 产物一致（`species=grape / count=1 / infection=YES / claim=Partial Compensation`）。

### 4.3 我自己加的限定（lint 绿不覆盖的部分）

- lint 只验**结构**（页↔索引 1:1、锚点可解析、无孤儿/缺失/重复），不验**语义真伪**。
- raw 与评测集**同源**：断言"能回溯到 raw"成立，但"结论正确"不在 lint 能力内 —— 与 `docs/README.md` §7 第 5 条自述一致，我复核认可。

---

## 5. lint 门禁

```text
$ .venv/bin/python -m ruff check claims/ data/llm-wiki-claims/scripts/
All checks passed!
```
✅（t29/t30 的 ruff 修复在我快照内仍然成立）

---

## 6. 硬规则审计（逐条给证据，不声称）

### 6.1 代码修改前有检索 + **检索时间必须早于产物 mtime**

| 产物 | mtime | 文件内记录的检索时间 | 时序判定 |
|---|---|---|---|
| `data/ins-mmbench/records.jsonl` | 11-18 **03:04** | `docs/research/ins-mmbench-access.md` 的 S1–S9：**00:00–00:32** | ✅ 早 2.5 h |
| `data/ins-mmbench/manifest.json` | 11-18 **15:36**（t17 增字段）| 同上 | ✅ |
| `docs/research/llmwiki-spec.md` | 11-18 **00:33** | S1–S? 检索时间 **2026-11-17** | ✅ 早 |
| `docs/research/r3-langgraph-deepagents.md` | 11-18 **00:33** | 来源表 15 行，S2 等标注 **2026-11-17 23:55** | ✅ 早 38 min |
| `docs/research/f0-deepagents-0739-install-evidence.md` | 11-18 **00:44** | 自述检索窗口 **UTC 16:34–16:52 = CST 00:34–00:52** | ⚠️ **部分晚于 mtime 10 分钟**（见 P5-注）|

> P5-注：f0 的检索窗口 00:34–00:52 与其文件 mtime 00:44 有重叠 → 说明该文件是**边检索边追加**的（先落一部分，检索完再补）。这不违反"先检索后动手"（其依赖的 R3 证据在 00:33 已完成，deepagents 安装动作发生在 00:52 之后，见其命令输出时间戳），但**说明"mtime 早于检索"不能当作唯一判据**。我按"检索窗口整体 vs 代码 mtime"复核：`.venv-claims` 创建时间晚于 00:52 → 时序仍成立。

**来源表齐备**：4 份 `docs/research/**` 全部含 URL + 检索时间 + 用途（ins-mmbench 9 行、r3 15 行、llmwiki 14 条 URL、f0 5 条 URL + 逐条时间）。

### 6.2 来源独立性（同一结论不得只挂同一域名的多个 URL）

`ins-mmbench-access.md` 的域名分布：
```
7  hf-mirror.com        2  github.com        2  arxiv.org
1  huggingface.co       1  api.github.com    1  datasets-server.huggingface.co
```
6 个独立域；核心结论（"只有 6 个 TSV / 无图片文件 / license=apache-2.0"）分别由 **hf-mirror API（数据面）+ arXiv 论文（规格面）+ GitHub README（作者声明面）** 三方交叉支撑 → ✅ 不是同域名堆 URL。
`r3-langgraph-deepagents.md` 同时引用 `docs.langchain.com`（官方文档）、本机 `evidence/probe-introspect.txt`（实测签名）、`.mdx` 源文件 → 一手 + 实测双证 ✅。

### 6.3 来源真影响实现（抽 4 个技术点，指到文件:行号）

| 技术点 | 研究依据（含出处行） | 落地位置（文件:行号） | 一致性 |
|---|---|---|---|
| `response_format=ToolStrategy(...)` | `docs/research/r3-langgraph-deepagents.md:322`（`response_format: ResponseFormat \| type \| dict \| None`）、`:343`（表格"结构化输出给外面回传"） | **`claims/deep_agents/analyzer.py:226`** `response_format=ToolStrategy(schema=MaterialsAnalysisDraft)` | ✅ 依据→实现直连 |
| `durability="sync"` | `r3…md:19`（幂等键须来自已持久化状态 + `durability="sync"`）、`:34`（官方 Checkpointers 文档 S2，2026-11-17 23:55） | **`claims/graph.py:621`** 与 **`:637`**（`invoke(..., durability="sync")`、`invoke(Command(resume=...), ..., durability="sync")`） | ✅ |
| `FilesystemBackend(root_dir=…)` | `r3…md:339`（`FilesystemBackend(root_dir=...)` 落盘语义）、`:443`（示例代码） | **`claims/deep_agents/materials.py:186`** `safe_workspace_root()`；`:9-11` 注释直接复述"`root_dir=None` 会默认取 cwd，仓库根有 `.env`" | ✅ **来源直接改写了实现选择**（强制显式传 root_dir）|
| `interrupt()` 必须是节点函数第一行 | `r3…md:17`（`interrupt(value, *, response_schema=None)` + `Command(resume=)` 为唯一官方写法）、`:18`（resume 从第一行重跑 → 副作用必须放 interrupt 之后且幂等，引 `lg-interrupts.mdx:1019/:1365`） | **`claims/graph.py:380-381`** 注释"① 第一行且唯一一处 `interrupt()`；**不得**包进 try/except"；`:5` 文档复述 | ✅ |

### 6.4 文档全程 + 决策可追溯

```text
docs/log/step-*.md 数量：28
decisions.md 定义 D 编号：26 条（D-01 … D-26）
全仓（除 decisions.md 自身）被引用：26 条
未被任何其他文件引用：无
```
✅ 与 C5 的结论不同：C5（`INDEX.md` §5）统计"孤立决策 20 条（编号未被 step 日志引用）"，我按**全仓**（含 `claims/*.py`、`SPEC-claims.md`、`scripts/*.py`、`wiki/*.md`）复算，**26/26 全部有引用**。
→ 差异原因：C5 只 grep 了 `docs/log/step-*.md` 与 `docs/research/*.md`（得 12/26），我扩大到全仓文件类型。**我的口径更宽，故结论更松；两者不矛盾，C5 的"编号未回引"是事实，但"D 编号无落点"不成立**（C5 自己也用"代码/产物证据"二分补上了，见其 §5 表）。

### 6.5 只抽样不拉全量

```text
manifest.totals.network_bytes_fetched = 57,898,730
manifest.totals.source_bytes_total    = 2,900,191,262
manifest.totals.network_ratio         = 0.019964   （2.00%）
splits 求和 = 57,898,730（与 totals 一致）

$ find . -name "*.tsv" -not -path "./.git/*"
（空）

$ du -sh data/ins-mmbench
34M
```
✅ 任务书要求的 `57,898,730` 与实测一致；仓库内**无任何 .tsv**（全量文件从未落盘）✅。

### 6.6 子 Agent 知情硬约束

抽 3 份成员产物：
| 产物 | 是否复述"≥3 来源 + URL + 时间" | 证据 |
|---|---|---|
| `docs/log/step-d1.md` | ✅ | §4.8 "MCP 检索依据（硬规则 ≥3 来源，URL + 检索时间 + 用于哪项决策）"，6 行表 |
| `docs/log/step-r3.md` | ✅ | 3 处提及，含来源表 |
| `docs/log/step-f2.md` | ✅ | 按"≥3"复述检索要求 |
| `docs/research/r3-langgraph-deepagents.md` | ✅ | 15 行来源表，含官方文档 + 一手 `.mdx` + 本机实测签名 |

---

## 7. 发现清单（0 阻断 / 5 条登记）

### P1（**重要，须留档**）—— F4 曾在 20:32→01:05 的窗口内破坏 `docs/README.md` 命令 ①-2

- **现象**：`.venv/bin/python -m pytest claims/tests` 在 **00:57 我首次运行时 collection ERROR**（`RuntimeError: deepagents 不可导入（D-22）`）。
- **根因**：`claims/api.py:365 create_app()` 在**模块导入期**调 `assert_preflight(strict=strict)`；`strict = not CLAIMS_ALLOW_RULES_ONLY`，默认 `True`。F4 的 `test_f4_api.py` 一被收集就 import `claims.api` → 直接抛。
- **时间线（全部 mtime 实测）**：
  | 时刻 | 事件 |
  |---|---|
  | 11-18 20:32 | C5 复核 `.venv claims/tests` = **78 passed**（此时 `claims/api.py` 尚未引入导入期 preflight）|
  | 11-18 23:21 | `claims/api.py` 落地（F4，t12）→ 引入导入期 preflight |
  | 11-18 23:58 | `claims/tests/test_f4_api.py` 落地（8 例）|
  | 11-19 00:57 | **我首次复验 → collection ERROR**（发现该回归）|
  | 11-19 01:05:38 | flow-engineer 在 `claims/tests/conftest.py` 补 `_os.environ.setdefault("CLAIMS_ALLOW_RULES_ONLY","1")` → 修复 |
  | 11-19 01:37 | 我复跑 → **86 passed** ✅ |
- **判定**：**已修复，当前通过**。但它精确印证了 C5b 的存在理由——"C5 的零回归结论在后续改动后失效"，且失效窗口内（23:21→01:05，约 1h44m）文档命令是**不可用**的。
- **建议（交责任方，我不改）**：① `docs/README.md` 命令 ①-2 增加半句注释"（`claims/tests/conftest.py` 会自动设 `CLAIMS_ALLOW_RULES_ONLY=1`；若手工 `python -c` 导入 `claims.api` 需自行设置）"；② 把"import 期 preflight 不得让纯单测变红"写进 SPEC-claims §8.0。

### P2 —— `INDEX.md` 第 98 行路径写错

`**F2c** DEEPAGENTS_ENABLED 默认值守卫 … `claims/conftest.py`（会话级护栏）` —— 实测**该文件不存在**；实际守卫在 **`claims/tests/conftest.py`**（`find` 结果：`tests/conftest.py`、`mcp_servers/conftest.py`、`claims/tests/conftest.py`、`claims/deep_agents/tests/conftest.py`）。建议改正路径。非阻断（不影响运行）。

### P3 —— D-22 证据里的失败数已过期

`decisions.md` D-22 写"`.venv` 下 `claims/deep_agents/tests` **20 failed**（全 `ModuleNotFoundError`）"；现在实测 **24 failed, 58 passed**（测试数在 t29/t31 后增长）。**根因结论不变**（全部 `deepagents` 缺失），仅计数需刷新。建议在 D-22 备注"计数随测试增长，以执行时为准"。

### P4 —— C5（t14）§4.1 的三个数字已全部过期

| 指标 | C5 记录（19:18，20:32 复核） | 我实测（01:37） | 变化原因 |
|---|---|---|---|
| `.venv` 全量 | 148 passed / 2 skipped | **148 / 2** | 一致 ✅ |
| `.venv claims/tests` | 78 passed | **86 passed** | +8 = F4 的 8 个 API 测试 |
| `.venv-claims deep_agents/tests` | 82 passed | **82 passed** | 一致 ✅ |

→ **不是 C5 说谎，是并发开发让数字漂移**；C5 自己在 §4.2 就警告过"引用这些数字必须带时间戳"。我的 `168 passed` = 86+82，可作为**当前口径**替换其 §4.1。

### P5 —— `traces/` 计数有三个合法口径，文档只写了 1183

1183（顶层条目）/ 2090（递归文件）/ 1176（顶层 `*.jsonl`，demo 自检用）。三者跑 demo 前后均不变，**隔离结论不受影响**，但建议在 `docs/README.md` 或 SPEC 里写明"基线 1183 指 `ls traces | wc -l`"，避免下一个复验人误判为污染。

### 非发现（复核 C5 已登记项，我认同）

- `step-d2.md` / `step-d5-retrieval.md` / `step-f1-arch.md` / `step-f2-flow.md` 是**指针文件**（0 代码块），content 在 canonical 同名文件 → 我复核一致，非缺陷。
- `D-13` 编号缺失 → 我复核确认缺号，未见勘误说明；`decisions.md` 台账仍待补。
- `insurance-agent/` 陈旧引用 → 我已在 t28 清除我负责的 2 个文件；其余域已由他人处理（本次复验未再发现指向不存在目录的引用）。

---

## 8. 与 C5（t14）结论的明确对照

| 项 | C5（t14，integrator 自审） | 我（C5b，独立） | 对照 |
|---|---|---|---|
| `.venv claims/tests` | 78 passed | **86 passed**（且中途 1h44m 为红）| **不一致**：C5 快照后的 F4 改动使数字与可用性都变了。C5 结论"零回归"在其时点成立，在交付时点需刷新 |
| `claims/deep_agents/tests`（`.venv`）| "20 failed（全 ModuleNotFoundError）" | 24 failed / 58 passed（全同源）| 计数不同、**根因一致** |
| 隔离性 | 通过 | 通过（并澄清 1183/2090/1176 三口径）| 一致 |
| wiki lint | FAIL=0 / ERROR=0 | FAIL=0 WARN=0 / ERROR=0 WARN=0 | 一致（我额外做了 6 条断言逐字核对）|
| ruff | 通过 | All checks passed! | 一致 |
| D 编号覆盖 | "孤立决策 20 条"（仅 grep step 日志）| 全仓复算 **26/26 有引用** | **口径不同**：C5 的"编号未回引"是事实，但"无落点"不成立（C5 自己已用代码证据二分补足）|
| 数据抽样 | 57,898,730 / 2.00% | 同（并核 splits 求和一致）| 一致 |

**分歧要点（我认为比附和更有价值的那条）**：C5 把"`.venv` 下 `claims/tests` 78 passed"当作稳定口径写进 `INDEX.md §4.1`，**但 F4 两小时后落地就把它打破了，且打破方式不是数字变化而是直接不可运行**。这说明"以测试数字为交付凭据"必须绑定"命令 + 时间戳 + 解释器"，否则下一小时就失效。C5 自己 §4.2 也有此自省，但 §4.1 的结论式排版仍会让读者误以为那是终态。

---

## 9. 判据回答：陌生人拿仓库能复现吗？

**能** —— 按 `docs/README.md §3.2` 的命令 ①–④ 逐条实测均通过（快照 01:37:43）：

| README 命令 | 我的实测 |
|---|---|
| ①-1 `.venv pytest -q` | `148 passed, 2 skipped` ✅ |
| ①-2 `.venv pytest claims/tests` | `86 passed` ✅（依赖 `claims/tests/conftest.py` 的 `setdefault`，该兜底已在库内，陌生人无需知道这个变量）|
| ①-3 `.venv-claims pytest claims/deep_agents/tests` | `82 passed` ✅（合跑 168）|
| ② demo（库级）| `PASS 8 / FAIL 0` ✅ |
| ③ wiki 检索 + 评测 | README 自陈已实测（`Hit@1=0.714 / MRR@5=0.827 / 接地=1.0`）；我未复跑模型调用，但 `demo` 的 D 项已覆盖检索链路（`grounding_rate=1.0`）|
| ④ 两套 wiki lint | `FAIL=0` / `ERROR=0` ✅ |
| ⑤ `scripts/e2e_smoke.sh` | README **明确标注"本次未执行"** → 不构成复现承诺；我同样未执行（会起 uvicorn、抢端口）|

**两个前提（不构成阻断，但交付时应告知）**：
1. **必须两套解释器**：`.venv`（148 基线）+ `.venv-claims`（deepagents）。用错会得到"假绿"或 24 条假红（README §3.1 已写明）。
2. **⑤ 端到端冒烟未验证**：HTTP/SSE 层的实证只到 `claims/demo_claim.py`（库级 8 项）+ `test_f4_api.py`（8 例）。README §5 已如实声明，故不算隐瞒；但"陌生人照文档全跑通"在 ⑤ 上是**未验证**而非**已验证**。

---

## 10. 复验方法学（便于下一个人重放）

```bash
cd renewal-assistant
# 快照
date '+%F %T %Z'; git log --oneline -1
find claims data/llm-wiki-claims docs/log scripts -newermt "-15 minutes" -type f | grep -v __pycache__   # 应为空=已落定

# 四套测试
.venv/bin/python -m pytest -o addopts="" -q
.venv/bin/python -m pytest claims/tests -o addopts="" -q
.venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
.venv/bin/python -m pytest claims/deep_agents/tests -o addopts="" -q          # 预期 24 failed（deepagents 缺失）

# 端到端 ×2（记录 traces-claims 行数增量）
cnt(){ cat traces-claims/*.jsonl | wc -l; }; B=$(cnt)
PYTHONPATH=. .venv-claims/bin/python claims/demo_claim.py | tail -2; echo "delta=$(( $(cnt) - B ))"

# 隔离 + lint + wiki
git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md claims/SPEC-claims.md   # 空
ls traces | wc -l; find traces -type f | wc -l; ls traces-claims/*.jsonl | wc -l
.venv/bin/python -m ruff check claims/ data/llm-wiki-claims/scripts/
python data/llm-wiki-claims/scripts/wiki_lint.py
python data/llm-wiki-claims/scripts/wiki_claims_lint.py
```

> 写作用域自查：本文件是本次唯一写入。`git status --porcelain` 中 `claims/`、`data/`、`traces-claims/` 的变动均为**他人/历史产物**，我未触碰（demo 产生的 `traces-claims` 追加属既定行为，且 `traces/` 零变化）。
