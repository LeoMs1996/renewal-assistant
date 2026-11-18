# step-c5 · C5 终验（零回归 / 隔离性 / wiki 一致性 / 硬规则审计）

> 任务：`t14`（attempt 1，`b9047d8a-4347-4929-99e6-d4e7baed71b6`）｜执行：integrate / integrator
> 时间：2026-11-19 00:14–01:52（+0800）｜工作目录：`renewal-assistant/`
> 写作用域：只写本文件与 `docs/log/INDEX.md`；**不改代码、不改 wiki、不改他人日志**（发现问题只登记与报告）。

## 总判定：**通过**

> **判定经过（完整留痕，不删首轮失败原文）**：
> - **00:14 首轮**：A2 失败 —— `.venv` 下 `claims/tests` 收集报错（F4 的 `claims/api.py` 在 import 期跑严格前置断言）。
> - **01:05 第三方修复**：`claims/tests/conftest.py` 在收集阶段前 `setdefault("CLAIMS_ALLOW_RULES_ONLY","1")`（注释明写"fixture 里设置已经太晚"）。
> - **01:52 复核**：A/B/C 三组**全绿**（§H 有完整输出）。故最终判 **通过**，另登记 M-01（文档遗留）/ L-01（低危），均不阻断。

| 组 | 结论 | 一句话 |
|---|---|---|
| **A 零回归** | ✅ 通过（01:52 复核） | 续保 `148 passed, 2 skipped`；`.venv` `claims/tests` `86 passed`；`.venv-claims` 两套 `168 passed`；`testpaths` 未变 |
| **B 隔离性** | ✅ 通过 | 保护对象 diff 为空；`traces/` 1183 不变；两套 wiki 互不为前缀、各读 8 / 36 条 |
| **C wiki 一致性（t25 后复跑）** | ✅ 通过 | 两套 lint 均 0；自审 8 页 ×2 = 16 条断言，**0 FAIL** |
| **D 硬规则审计** | ⚠️ 5/6 通过 | 检索/独立性/来源影响实现/只抽样/子 Agent 知情 全通过；**"每条决策至少被 1 个 step 引用" 有 16 条不满足**（文档追溯性缺口 → M-01，不阻断） |

> 判据两问：**①"续保基线没被碰坏" = 是**；**②"理赔链路的每条结论都能回溯到出处" = 是** → 两条都为是，判**通过**。

---

## A. 零回归（两个解释器都跑）

### A.1 首轮（00:14）——A2 失败原文（留证，后续已修复）

```text
$ .venv/bin/python -m pytest -o addopts="" -q
148 passed, 2 skipped in 3.33s            ← ✅ 与 C0 基线完全一致

$ .venv/bin/python -m pytest claims/tests -o addopts="" -q
==================================== ERRORS ====================================
_________________ ERROR collecting claims/tests/test_f4_api.py _________________
claims/tests/test_f4_api.py:12: in <module>
    from claims import api as capi
claims/api.py:453: in <module>
    app = create_app()
claims/api.py:365: in create_app
    report = assert_preflight(strict=strict)
claims/api.py:128: in assert_preflight
    raise RuntimeError("；".join(problems))
E   RuntimeError: deepagents 不可导入（D-22）：请用 .venv-claims/bin/python 启动；若只要跑规则模式，请显式设 CLAIMS_ALLOW_RULES_ONLY=1
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.07s                          ← ❌ 首轮阻断（B-01，已由第三方于 01:05 修复）
```

### A.2 复核（01:52）——三组全绿

```text
$ .venv/bin/python -m pytest -o addopts="" -q
148 passed, 2 skipped in 1.76s            ← ✅
$ .venv/bin/python -m pytest claims/tests -o addopts="" -q
86 passed in 1.28s                        ← ✅（首轮阻断解除）
$ .venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
168 passed in 6.02s                       ← ✅

$ grep -A2 "\[tool.pytest.ini_options\]" pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests", "mcp_servers"]
addopts = "-q"                            ← ✅ D-06 口径未变；`git diff -- pyproject.toml` 为空
```

| 命令 | 期望 | 实测（01:52） | 判定 |
|---|---|---|---|
| `.venv` 默认 pytest | 148 passed, 2 skipped | `148 passed, 2 skipped in 1.76s` | ✅ |
| `.venv` `claims/tests` | 与基线对账（口径不变） | `86 passed in 1.28s`（00:14 曾 collection error，01:05 修复 conftest） | ✅ |
| `.venv-claims` 两套 | 全绿 | `168 passed in 6.02s` | ✅ |
| `testpaths` | 未被改 | `["tests","mcp_servers"]`，diff 为空 | ✅ |

---

## B. 隔离性（三条实证）

### B1 保护对象零改动

```text
$ git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md
（无输出）                                     ← ✅
```

### B2 轨迹目录

```text
$ ls traces | wc -l        → 1183   （其中 *.jsonl 1176；与 C0 基线"1183 条目"一致）
$ ls traces-claims | wc -l → 9      （8 个 CLM-*.jsonl + README.md）
```

- 理赔轨迹全部 `CLM-*.jsonl` 命名，**没有**续保 `sess-*`/`trace-*` 混入。
- F4 实测期间 `traces/` 的 jsonl 计数 `1176 → 1176` 未变（`docs/log/step-f4.md §0` A3 断言）。

### B3 两套 wiki 物理隔离 + 各读自己的语料

```text
续保 wiki = /Users/.../renewal-assistant/wiki
理赔 wiki = /Users/.../renewal-assistant/data/llm-wiki-claims/wiki
互不为前缀: True
续保 WikiSearch entries = 8    | wiki_dir = wiki
理赔 get_searcher entries = 36 | wiki_dir = /Users/.../data/llm-wiki-claims/wiki
互不串台: True
```

- 续保 `WikiSearch()`（默认 `server.config.WIKI_DIR`）仍解析到 8 条合成条款；理赔解析到 36 页 —— 无互相读串（D-02 / D-21）。

---

## C. wiki 一致性（**t25 完成后复跑**，不引用 t23 历史结论）

```text
$ python data/llm-wiki-claims/scripts/wiki_lint.py
pages=36 index_rows=36 FAIL=0 WARN=0      exit=0     ← ✅
$ python data/llm-wiki-claims/scripts/wiki_claims_lint.py
pages=36 index_rows=36 ERROR=0 WARN=0     exit=0     ← ✅
$ wc -c data/llm-wiki-claims/wiki/index.md → 5867     （上限 6144，余量 277 B）
$ grep -c "^| \[" data/llm-wiki-claims/wiki/index.md → 36
```

### C.1 自审：4 类页各 2 页 × 2 条断言（16 条，脚本直读 raw，不复用任何 lint）

| # | 类型 | 页 | 断言标记 | raw 源与证据 | 判定 |
|---|---|---|---|---|---|
| 1 | doc | `docs/ins-mmbench-agricultural.md` | `⟦qid=agri_0@L1-L17⟧` | `raw-agri-0000` L1 起（题干全 17 行） | **PASS（定位级）** |
| 2 | doc | `docs/ins-mmbench-agricultural.md` | `⟦qid=agri_1@L1-L17⟧` | `raw-agri-0001` L1 起 | **PASS（定位级）** |
| 3 | doc | `docs/ins-mmbench-auto.md` | `⟦qid=claim_0@L1-L14⟧` | `raw-claim-0000` L1 起（14 行） | **PASS（定位级）** |
| 4 | doc | `docs/ins-mmbench-auto.md` | `⟦qid=claim_1@L1-L14⟧` | `raw-claim-0001` L1 起 | **PASS（定位级）** |
| 5 | section | `sections/agri-insured-subject.md` | `⟦qid=agri_0@L9-L9⟧` | L9 = `1. Identify the Crop Species…`，引用块逐字一致 | **PASS 逐字** |
| 6 | section | `sections/agri-insured-subject.md` | `⟦qid=agri_0@L15-L15⟧` | L15 = `2. Fruit cluster count: <a specific number>` | **PASS 逐字** |
| 7 | section | `sections/claim-loss-amount.md` | `⟦qid=claim_0@L7-L7⟧` | L7 = `5. If eligible for a claim, calculate the final claimable am…` | **PASS 逐字** |
| 8 | section | `sections/claim-loss-amount.md` | `⟦qid=claim_0@L4-L4⟧` | L4 = `2. If damaged, assess the severity…` | **PASS 逐字** |
| 9 | entity | `entities/compensation-tier.md` | `⟦qid=claim_0@L1-L1⟧` | L1 = 题干首行（含 cost/coverage） | **PASS 逐字** |
| 10 | entity | `entities/compensation-tier.md` | `⟦qid=claim_0@L9-L14⟧` | L9–L14 输出格式块 6 行逐字 | **PASS 逐字** |
| 11 | entity | `entities/report-consistency.md` | `⟦qid=health_0@L5-L5⟧` | L5 = `2. Scan Result Match…` | **PASS 逐字** |
| 12 | entity | `entities/report-consistency.md` | `⟦qid=health_0@L9-L13⟧` | L9–L13 输出格式块 5 行逐字 | **PASS 逐字** |
| 13 | faq | `faqs/agri.md` | `⟦qid=agri_0@L13-L17⟧` | L13–L17 逐字 | **PASS 逐字** |
| 14 | faq | `faqs/agri.md` | `⟦qid=agri_0@labels.species⟧` | `labels.species='grape'` | **PASS 逐字取值** |
| 15 | faq | `faqs/claim.md` | `⟦qid=claim_0@L9-L14⟧` | L9–L14 逐字 | **PASS 逐字** |
| 16 | faq | `faqs/claim.md` | `⟦qid=claim_0@labels.Cost_of_vehicle⟧` | `labels.Cost_of_vehicle='44900.0'` | **PASS 逐字取值** |

**共 16 条，FAIL 0**。审计脚本 `/tmp/c5_audit.py`（不入库）：直读 `raw/sources/*.json` 解析
`labels.*` / `L a-L b` / JSON 路径，逐字比对页面引用块（仅统一行首尾空白）。

> 与 t23 的差异：t23 报 `1200/1200 可回溯`；本次**不引用**该结论，而是重跑 lint + 自抽 16 条，结论一致（0 漂移）。
> index 体积 t25 报 6018 B → 本次 **5867 B**（t25 之后仍有改动），仍在 6144 限内。

---

## D. 硬规则审计（逐条给证据）

### D1 代码修改前有检索：URL + 检索时间 + 用于哪项决策（且时间早于产物）

| 研究文档 | URL 条数 | 独立域名 | 检索时间戳 | 对应产物 mtime | 时序 |
|---|---|---|---|---|---|
| `docs/research/llmwiki-spec.md`（R1） | 14 | 6（gist / gist.githubusercontent / github / raw.githubusercontent / juejin.cn / anthropic.com） | 2026-11-17 ×8、11-18 ×6 | `data/llm-wiki-claims/plan.md` 11-18 16:39 | ✅ 早于 |
| `docs/research/ins-mmbench-access.md`（R2） | 21 | 5（hf-mirror / datasets-server.huggingface.co / arxiv.org / github.com / api.github.com） | 2026-11-18 ×11 | `data/ins-mmbench/manifest.json` 11-18 15:36 | ✅ 早于 |
| `docs/research/r3-langgraph-deepagents.md`（R3） | 17 | 3（docs.langchain.com / pypi.org / raw.githubusercontent.com） | 11-11 ×2、11-16 ×4、11-17 ×6、11-18 ×12 | `claims/graph.py` 11-18 17:16、`analyzer.py` 09:49 | ✅ 早于 |
| `docs/research/f0-deepagents-0739-install-evidence.md`（F0） | 5 | 4（docs.langchain.com / github.com / pypi.org / raw.githubusercontent.com） | 11-16 ×1、11-17 ×5、11-18 ×2 | `.venv-claims/` 11-18 01:0x | ✅ 早于 |

### D2 来源互相独立

每份文档 ≥3 个**不同域名**（见 D1"独立域名"列；R3 的 3 个域名分属官方文档站 / PyPI / 源码 CDN，不是同站三连）。**通过**。

### D3 来源真的影响了实现（3 个技术点 → 代码行）

| 技术点 | 代码行 | 对应来源 | 说明 |
|---|---|---|---|
| `response_format=ToolStrategy(schema=MaterialsAnalysisDraft)` | `claims/deep_agents/analyzer.py:226` | R3 §8 + `docs/research/evidence/mdx/da-*.mdx`；台账 E-03 | 不是只靠 prompt：把"只输出事实+出处"下沉到 API 层强约束 |
| `durability="sync"` | `claims/graph.py:621`（invoke）、`:470`（resume） | `evidence/mdx/lg-checkpointers.mdx` + SPEC §8 S2 | 与 `recursion_limit` 一起走顶层 config 键 |
| `FilesystemBackend(root_dir=…)` + `safe_workspace_root()` 断言 | `claims/deep_agents/analyzer.py:228-229`、`claims/deep_agents/materials.py:185` | `evidence/mdx/da-backends.mdx` | `root_dir=None` 会退化成 cwd（仓库根有 `.env`）→ 永远显式传 + 越界断言 |

### D4 文档全程记录

- **每个 step 日志存在且非空**：`docs/log/step-*.md` 26 份，除 4 个**指针文件**外均 ≥20 行
  （`step-d2.md` 9 行 / `step-f1-arch.md` 9 行 / `step-f2-flow.md` 10 行 / `step-d5-retrieval.md` 12 行，
  均为"指路到 canonical 文件"，非空非缺陷；`docs/log/INDEX.md §2` 已标注）。
- **每条决策至少被 1 个 step 引用**：❌ **不满足**（M-01）。`decisions.md` 现有 25 条 D + 3 条 E，**16 条**未被任何
  `step-*.md` 按编号引用：`D-02, D-05, D-07, D-09, D-10, D-11, D-12, D-19, D-20, D-23, D-24, D-25, D-26, E-01, E-02, E-03`。
  已有替代证据链：`docs/log/INDEX.md §3.2` 对每条做了"产物反查"（多数有代码/产物证据）。属**文档追溯性缺口**，
  不阻断两条判据，登记为 M-01。

### D5 数据集只抽样不拉全量

```text
bytes_fetched 合计 = 57,898,730 B = 57.9 MB ; k 合计 = 54 ; records 合计 = 54
raw/ 体积 = 33 MB（仅 5 个分片子集目录）
$ find data/ins-mmbench -name "*.tsv" -o -name "*.parquet" → 空（无全量文件）
```

- 占**整份数据集**（6 个 .tsv = 2,900,191,262 B）：**2.00%** ✅（与任务书一致）。
- 占 **manifest 中 5 个被抽样源文件**（1,356,037,796 B）：4.27% —— 两个分母都列出，避免误读。

### D6 子 Agent 知情（抽查 3 位成员）

| 成员 | 证据 |
|---|---|
| retrieval-engineer（D5） | `docs/log/step-d5.md:4`：「研究依据：`prep-d5-retrieval.md`（**≥3 外部来源** + 接口实读）」 |
| deepagents-engineer（F3） | `docs/log/step-f3.md:31`：「官方 overview 与 subagents 文档均在 **§检索依据** 留档」 |
| dataset-lead（D1） | `docs/log/step-d1.md` 含 6 条 MCP 依据（URL+时间），并在 §4.9 用实测数据修正抽样偏差 |

---

## E. 问题登记（责任方与处置）

| ID | 级别 | 问题 | 处置 |
|---|---|---|---|
| **B-01** | blocker → **已解除** | `.venv` 下 `claims/tests` 因 `claims/api.py` import 期严格断言而无法收集（F4/t12 引入；t24 台账记录 19:18 为 78 passed）。 | **01:05 第三方已修**：`claims/tests/conftest.py:21-27` 在收集前 `setdefault("CLAIMS_ALLOW_RULES_ONLY","1")`。**残余风险（低）**：`python -c "import claims.api"` 在 `.venv` 下裸导入仍会抛（有意严格模式）；彻底方案（import 无副作用 / `--factory` + lifespan 内断言）未做，记入遗留。 |
| M-01 | medium（不阻断） | 16 条决策编号未被 step 日志回引（D-02/05/07/09/10/11/12/19/20/23/24/25/26、E-01..03）。 | 建议各决策作者在对应 step 末尾**只追加**一行「关联决策：D-xx」；或保留 `INDEX §3.2` 的产物反查表作为替代证据链。 |
| L-01 | low | 4 个指针文件 <20 行，易被误判"该步无证据"。 | `INDEX §2` 已标注；可选在指针首行加「本文件为指针」。 |

> 按任务纪律：本文件**不写"基本通过"**。首轮 A2 失败原文保留在 §A.1，修复与复核在 §A.2 / §H。

---

## F. 复跑方式（任何人可自证）

```bash
cd renewal-assistant
git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md          # 期望：空
.venv/bin/python -m pytest -o addopts="" -q                             # 期望：148 passed, 2 skipped
.venv/bin/python -m pytest claims/tests -o addopts="" -q                # 期望：86 passed
.venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q  # 期望：168 passed
python data/llm-wiki-claims/scripts/wiki_lint.py                        # 期望：FAIL=0
python data/llm-wiki-claims/scripts/wiki_claims_lint.py                 # 期望：ERROR=0
ls traces | wc -l                                                       # 期望：1183
```

---

## G. 变更记录

| 时间 | 变更 | 作者 |
|---|---|---|
| 2026-11-19 00:50 | 初版：A/B/C/D 四组实测；首轮判**不通过**（B-01 阻断，M-01/L-01 登记） | integrate（t14） |
| 2026-11-19 01:52 | 复核：B-01 已由第三方（conftest，01:05）修复；A/B/C 三组全绿 → 最终判**通过**，M-01/L-01 转为遗留 | integrate（t14） |
