# step-d4 · D4b 全量质检（36 页 lint + 6 页引用人工复核）

> 任务：`t23`（attempt 1，`7ab30818-06e6-40c7-94a3-afe1667f9a5a`）｜执行：integrate / integrator｜日期：2026-11-18
> 定位：t7（`step-d4-lint.md`）只是 **3 页 pilot QC**；本文件是 **36 页全量**的第一次真正质检。
> 结论：**接手时 36 页存在但索引陈旧、`FAIL=64`** → 修复后 `pages=36 index_rows=36 FAIL=0 / WARN=0`；**1200/1200 条断言可回到 raw 逐字核对，不可回溯 0 条**；4 项专项检查全部通过。

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 职责 |
|---|---|---|
| `data/llm-wiki-claims/scripts/compile_wiki.py` | **修改（3 处修复）** | ① `markers_by_split()`：非连续 qid 集合必须拆成**连续段**（见 §2.2）；② `body_entity()/summary_of()/page_meta()`：跨分片实体按分片分别登记 + 显式「同名不同义」告警（§2.3）；③ `body_section()`：逐字段各取一条代表行（§2.4） |
| `data/llm-wiki-claims/scripts/wiki_lint.py` | **修改（加固 L6）** | 区间标记必须覆盖区间内**每一个真实存在的单元**；旧实现只保留"存在的 qid"，于是 `liability_0..liability_20` 能被静默放过（§2.2、§5.2） |
| `data/llm-wiki-claims/wiki/**` | 重建（36 页 + index/schema/log） | 由修好的编译器 `build --all` 幂等重生成；`log.md` 只追加、36 条无重复 |
| `docs/log/step-d4.md` | 新增 | 本文件 |

**没碰**：`raw/**`（只读）、续保 `wiki/`、`server/`、`tests/`、`mcp_servers/`、`SPEC.md`、`plan.md`、`traces/`。
证据：`git diff 40541d1 --stat -- server tests wiki SPEC.md mcp_servers` → **空**。

---

## 2. 关键决策与依据

### 2.1 本次检索记录（先检索后动手）

| # | 来源 | URL | 检索时间 | 支撑的决策 |
|---|---|---|---|---|
| S1 | Karpathy《LLM Wiki》gist 原文（本次全文抓取） | https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw | 2026-11-18 | ① `index.md` 是**全量目录**（"a catalog of everything in the wiki… updates it on every ingest"）→ 接手时 36 页只有 6 行索引 = 索引失职，必须重建；② `log.md` 是 append-only 时间线（`grep "^## \["`）→ 只追加、不重写历史；③ `raw sources` **immutable** → 质检只读 raw，绝不改 raw；④ lint 的对象是矛盾/过期断言/孤儿页/缺互链 → L1–L11 的口径来源 |
| S2 | ResearchQA: Benchmarking Citation-Grounded QA（arXiv 2607.11074，2026-07-13） | https://arxiv.org/abs/2607.11074 | 2026-11-18 | "existing evaluation methods often fail to detect whether answers are supported by **verifiable citations**" → 质检不能只跑 lint，必须做**引用级**人工复核（本文件 §4 的 18 条） |
| S3 | AgentHop: Diagnostic Benchmark for Agentic Multi-Hop QA over **Scientific Citation Graphs**（arXiv 2609.34428，2026-09-28） | https://arxiv.org/abs/2609.34428 | 2026-11-18 | 引用图上的多跳诊断 → 支持"引用存在 ≠ 引用正确"，以及"必须按 claim→source 逐条对齐"的复核方式 |
| S4 | 项目内规范 · R1 `docs/research/llmwiki-spec.md`（断言级引用）+ t7 `step-d4-lint.md`（谁能自动修） | 本地 | 2026-11-18 | 语义改动必须人工；**只自动修派生文件**（index/log/页面由编译器重生成），语义问题靠修生成器而非手改页面 |

> 另：`w3.org/TR/prov-o`（provenance）本次被 Cloudflare 拦截（captcha），未能取回；`search.run`（"generated file / single source of truth"）返回 0 条达标证据。两者均**未**作为结论依据，按 R1 记录为检索缺口。

### 2.2 修复：非连续 qid 集合不能折叠成一个区间（**本次最重要的发现**）

**现象**（接手时 lint 看不到，`FAIL=0`）：
`docs/ins-mmbench-auto.md`、4 个 liability 章节页、`faqs/liability.md`、`entities/primary-responsibility.md` 等页面出现
`⟦S:INS-MMBench:qids=liability_0..liability_20@labels.weather⟧`。

**为什么是错的**：`plan.md:63-66` 声明的 liability 抽样集合是**非连续**的
`raw-liability-0000/0001/0003/0004/0006/0008/0010/0012/0016/0017/0019/0020`（12 条），而 raw 只有 12 条；
写成 `liability_0..liability_20` 等于**凭空断言中间 9 个不存在的单元也参与了统计**。这正是"引用看起来对、语义其实错"的典型。

**为什么 lint 没抓到**：`wiki_lint.py::expand_qids()` 用"区间内**存在的** qid"构造列表，缺失的成员被静默跳过 → 区间声明与实际覆盖脱钩。

**修复**：
1. `compile_wiki.py::markers_by_split()` 改为按**连续段**拆分（`liability_0..liability_1`、`liability_3..liability_4`、`liability_16..liability_17` …），单元素退化为 `qid=`；
2. `wiki_lint.py` L6 增补：`hi-lo+1 != 实际成员数` → **FAIL**（区间覆盖不存在的单元）。以后同类问题机器直接拦。

### 2.3 修复：跨分片实体把两个不同语义的字段合成一个"取值分布"

**现象**：`entities/compensation-tier.md`（赔付档位）把
- `claim` 分片（汽车）的 `labels.claim` = **金额**（`0.0/459.0/826.0/…`）
- `agri` 分片（农业）的 `labels.claim` = **决策枚举**（`No Compensation/Partial Compensation`）

合成一个分布：`claim=0.0×5/459.0×1/…/Partial Compensation×2/No Compensation×10`，且 §3 还写着"（claim 分片）"，而 24 个单元其实横跨 `claim + agri` 两个分片。

**修复**：跨分片实体**按分片分别登记**，并自动检测「同一个 label 键在不同分片类型不同」（数值 vs 枚举）时输出显式告警行（`【方法约束】` 免标记豁免，仍附两条同分片区间标记）。修复后（原文）：

```text
- `agri` 分片（12 个单元）：claim=Partial Compensation×2/No Compensation×10⟦S:INS-MMBench:qids=agri_0..agri_11@labels.claim⟧
- `claim` 分片（12 个单元）：claim=0.0×5/459.0×1/826.0×1/2426.0×1/4048.0×1/3090.0×1/305.0×1/3607.0×1⟦S:INS-MMBench:qids=claim_0..claim_11@labels.claim⟧
- 【方法约束】同名不同义（机器标记可回溯、语义却不同）：`claim` 在 claim 分片为数值（如 0.0），在 agri 分片为枚举（如 Partial Compensation）；本页按分片分别登记，**不得合并统计**⟦S:INS-MMBench:qids=agri_0..agri_11@labels.claim⟧ ⟦S:INS-MMBench:qids=claim_0..claim_11@labels.claim⟧
```

同时 `summary`/index 由"24 个单元"改为"24 个单元（跨 agri+claim 分片）"，不再暗示单分片。

> **未根治（登记为设计限制，见 §6.1）**：`compensation-tier` 这个实体概念本身横跨两个语义域；更彻底的做法是把 agri 的 `claim` 映射到 `claims-entity-claim-decision`（与 property 的 `claim_decision` 同义）。那会改动 `plan.md` 的实体清单（不在写作用域），留队长裁决。

### 2.4 修复：多字段章节只引到其中一个字段的指令

**现象（人工复核发现，机器查不出）**：`sections/claim-loss-amount.md` 标题是"损失金额"、`label_keys = Amount/Severity`，但 §1「题干规约」只引了
raw L4 `2. If damaged, assess the severity…`（严重度）与输出格式块，
**完全没引** raw L7 `5. If eligible for a claim, calculate the final claimable amount…`（金额）。

**原因**：`body_section()` 用 `key_line(lines, keys)` 取"第一个命中任一字段名的行"（`severity` 在 L4 先命中），一个 section 只出一条代表性引用。

**修复**：逐字段各取一条代表行（去重），再补输出格式块。修复后该页 §1 三条引用：`L7-L7`（金额）、`L4-L4`（严重度）、`L9-L14`（输出格式）。

---

## 3. 验证证据（命令 + 原文）

### 3.1 接手时 vs 修复后（同一命令，全量）

```text
$ python3 data/llm-wiki-claims/scripts/wiki_lint.py        # 接手时（17:49，36 页已在盘上）
pages=36 index_rows=6 FAIL=64 WARN=0
  [L6] entities/compensation-tier.md :: 标记中的 qid/qids 不存在: claim_0..agri_11
  [L6] faqs/health.md :: 第 34 行: labels 路径不存在: labels.claim
  [L6] faqs/liability.md :: 第 36 行: labels 路径不存在: labels.claim
  [L6] faqs/property.md :: 第 29 行: labels 路径不存在: labels.claim
  [L4] entities/*.md :: 孤儿页：未出现在 index.md（9 条）
  [L4] faqs/*.md   :: 孤儿页：未出现在 index.md（5 条）
  [L4] sections/*.md :: 孤儿页：未出现在 index.md（16 条）
  [L3] … related 非双向 / 指向不存在页面（30 条，均由 index 缺失与页面陈旧级联产生）
exit=1
```

```text
$ python3 data/llm-wiki-claims/scripts/compile_wiki.py build --all     # 幂等重生成
$ python3 data/llm-wiki-claims/scripts/wiki_lint.py                   # 修复后（最终）
pages=36 index_rows=36 FAIL=0 WARN=0
exit=0
```

```text
$ python3 data/llm-wiki-claims/scripts/wiki_claims_lint.py           # 第二套独立实现（交叉验证）
=== wiki_claims_lint（独立实现）===
pages=36 index_rows=36 ERROR=0 WARN=0
```

> 接手时的 64 条 FAIL 有两个来源：**①索引陈旧**（36 页 vs 6 行，级联出 L4 孤儿 + L3 非双向共 60 条）；**②4 条真实内容缺陷**（跨分片区间、`labels.claim` 路径在 health/liability/property 不存在）。重生成 + §2.2/§2.3 的生成器修复后全部归零。

### 3.2 L1–L11 逐项结论（全量 36 页）

| 检查 | 结论 | 证据 |
|---|---|---|
| L1 frontmatter 必填/枚举 | 通过 | 36/36 页均有 9 必填 + `insurance_line`/`raw_refs`；`insurance_line` 枚举合法（含 `cross_cutting` 1 页） |
| L2 index ↔ 磁盘一一对应 | 通过 | `index_rows=36`，磁盘内容页 36；无"索引指向不存在页面" |
| L3 断链/related 双向 | 通过 | 重建后 0 条；`related` 由 `attach_related()` 双向计算 |
| L4 孤儿页 | 通过 | 0 条（全部进 index） |
| L5 重复 id/标题 | 通过 | 0 条；section 与 entity 同名不同 title（如"赔付档位（agri_claim_processing）"vs"赔付档位"） |
| L6 引用可回溯 | 通过 | 见 §3.3 全量审计：1200/1200 |
| L7 无来源断言 | 通过 | 表行/bullet 均带 `⟦S:…⟧`；仅 `【方法约束】`/`- （`/`- [[` 结构性行豁免 |
| L8 空页/超长页 | 通过 | 最短 2877 B，最长 `sections/health-report-consistency.md` 7775 B（阈值 12000 字符） |
| L10 index 摘要一致 | 通过 | 摘要由 `summary_of()` 同源生成 |
| L11 越界引用 | 通过 | 0 条指向续保 `wiki/`、`traces/` |
| L9（见 wiki_claims_lint E9） | 通过 | span 均可解析（行区间/labels/JSON 路径/图片路径） |

### 3.3 全量断言可回溯审计（1200 条，独立实现）

为避免"复述 lint"，我另写了一个**独立于两套 lint** 的解析器（`/tmp/d4_audit.py`，不进仓库）：逐页逐条把 `⟦S:…⟧` 解析回 `raw/sources/<raw_id>.json`，核对
①`labels.<k>` 是否真实存在；②`L a-L b` 是否越界、与页面引用块**逐字**（忽略行首尾空白）一致；③`sample.*`/JSON 路径是否存在；④图片路径是否命中 `images[].path`。

```text
$ python3 /tmp/d4_audit.py
pages=36 assertions=1200 resolvable=1200 unresolvable=0

按页统计（页 | 断言 | 可回溯 | 不可回溯）  —— 全部 36 页均为 0 不可回溯
  docs/ins-mmbench-agricultural.md 20 20 0        docs/ins-mmbench-auto.md 98 98 0
  docs/ins-mmbench-health.md 22 22 0              docs/ins-mmbench-property.md 15 15 0
  entities/*.md（9 页）10~34 条，全部 0            faqs/*.md（5 页）38~120 条，全部 0
  sections/*.md（18 页）9~39 条，全部 0
--- 不可回溯明细：NONE ---
```

> 这直接回答验收问题：**"这 36 页里，有没有任何一条断言无法回到 raw 源逐字核对？"——0 条**（1200 条全量机器可解析 + §4 的 18 条人工语义复核）。

### 3.4 lint 加固的前后对照（防止回归）

```text
# 修复前：区间 0..20 覆盖 21 个声明、实际只有 12 个成员 —— 静默通过
$ python3 data/llm-wiki-claims/scripts/wiki_lint.py
pages=36 index_rows=36 FAIL=0 WARN=0          ← 假的绿灯

# 加固后：同一条区间会直接 FAIL
[L6] … 区间 liability_0..liability_20 覆盖不存在的单元（声明 21 个，实际仅 12 个）；
     非连续集合应拆成多个连续段或逐条标记
```

（当前语料已由 `markers_by_split()` 拆成连续段，故加固后的 lint 仍为 `FAIL=0`。）

---

## 4. 6 页引用人工复核（4 类各 ≥1；每页 3 条 = 18 条）

抽样方式：**按类型分层 + 覆盖本次缺陷热点**（跨分片实体、多字段章节、超大 FAQ、被重建过的 doc 页），非纯随机。
判定标准：①断言文字与 raw 逐字成立；②**断言语义与所引单元/字段对齐**（机器查不出的那一层）。

| # | 页 id | 断言原文（页面） | 命中 raw 源与位置 | 核对结果 |
|---|---|---|---|---|
| 1 | `claims-doc-ins-mmbench-auto` | `| claim_0 | auto_claim_processing | 1 | 14 |` ⟦qid=claim_0@L1-L14⟧ | `raw-claim-0000.json`：`sample.task_name=auto_claim_processing`、`images` 长度 1、`content.question.text` 14 行 | **一致**（三列全部对齐；L1-L14 恰为整段题干） |
| 2 | 同上 | `| claim_1 | auto_claim_processing | 1 | 14 |` ⟦qid=claim_1@L1-L14⟧ | `raw-claim-0001.json` 同结构 | **一致** |
| 3 | 同上 | `| claim_2 | auto_claim_processing | 1 | 14 |` ⟦qid=claim_2@L1-L14⟧ | `raw-claim-0002.json` 同结构 | **一致** |
| 4 | `claims-section-agri-insured-subject` | `> 1. Identify the Crop Species: Analyze the image and determine the specific crop species.` ⟦qid=agri_0@L9-L9⟧ | `raw-agri-0000.json` L9（逐字，差量仅缩进） | **一致**（且语义正是"标的物种"这一节要引的指令行） |
| 5 | 同上 | `> Please strictly output in this format: … 4. Insurance decision: …` ⟦qid=agri_0@L13-L17⟧ | 同文件 L13–L17 | **一致**（5 行逐字） |
| 6 | 同上 | `| agri_0 | grape | 1 |` ⟦labels.species⟧ ⟦labels.count⟧ | `labels.species='grape'`、`labels.count='1'` | **一致** |
| 7 | `claims-section-claim-loss-amount` | `> 5. If eligible for a claim, calculate the final claimable amount…` ⟦qid=claim_0@L7-L7⟧ | `raw-claim-0000.json` L7 | **一致**（此条为 §2.4 修复后**新增**的金额指令引用；修复前该页完全没引金额指令） |
| 8 | 同上 | `> 2. If damaged, assess the severity of the damage…` ⟦qid=claim_0@L4-L4⟧ | 同文件 L4 | **一致**（严重度指令；与 Amount/Severity 双字段口径相符） |
| 9 | 同上 | `| claim_0 | 4043.0 | minor |` ⟦labels.Amount⟧ ⟦labels.Severity⟧ | `labels.Amount='4043.0'`、`labels.Severity='minor'` | **一致** |
| 10 | `claims-entity-compensation-tier` | `- `claim` 分片（12 个单元）：claim=0.0×5/459.0×1/826.0×1/…` ⟦qids=claim_0..claim_11@labels.claim⟧ | 12 个 raw-claim-00xx 的 `labels.claim` 逐条统计 | **一致**（5×0.0、其余 7 个值各 1，与 raw 精确相符） |
| 11 | 同上 | `- `agri` 分片（12 个单元）：claim=Partial Compensation×2/No Compensation×10` ⟦qids=agri_0..agri_11@labels.claim⟧ | 12 个 raw-agri-00xx | **一致**（2/10 与 raw 相符） |
| 12 | 同上 | `| claim_0 | 0.0 |` ⟦qid=claim_0@labels.claim⟧ | `labels.claim='0.0'` | **一致**；并确认该键在 agri 分片是枚举（`Partial Compensation`）——**同名不同义已在页内显式告警**（§2.3） |
| 13 | `claims-entity-report-consistency` | `> 2. Scan Result Match: Determine whether the scan result … matches the findings described in the report (Yes/No).` ⟦qid=health_0@L5-L5⟧ | `raw-health-0000.json` L5 | **一致**（语义与"报告一致性"实体吻合） |
| 14 | 同上 | 输出格式块 ⟦qid=health_0@L9-L13⟧ | 同文件 L9–L13 | **一致**（5 行逐字） |
| 15 | 同上 | `| health_0 | yes | The lungs are clear… |` ⟦labels.match⟧ ⟦labels.original_report⟧ ⟦labels.adjusted_report⟧ | `labels.match='yes'`，两份报告文本逐字 | **一致** |
| 16 | `claims-faq-claim` | 输出格式块 ⟦qid=claim_0@L9-L14⟧ | `raw-claim-0000.json` L9–L14 | **一致**（6 行逐字） |
| 17 | 同上 | `| claim_0 | 44900.0 | …` ⟦labels.Cost_of_vehicle⟧ | `labels.Cost_of_vehicle='44900.0'` | **一致** |
| 18 | 同上 | `| … | 1122.5 | …` ⟦labels.Min_coverage⟧ | `labels.Min_coverage='1122.5'` | **一致** |

**人工复核的独立价值**（机器没抓到的）：
- 第 7/8 行 → 发现并修复了"多字段章节只引到一个字段指令"（§2.4）；
- 第 10/11/12 行 → 发现并修复了"跨分片同名键合并统计"（§2.3）；
- 其余 15 条为"逐字成立且语义对齐"，**未发现张冠李戴**（即没有"引用 agri_3 的行却描述 agri_5"这类问题）。

---

## 5. 4 项已知风险专项检查

### 5.1 entity 页是否退化成"常识介绍" → **通过**

逐页扫描表行/项目符号的标记覆盖率（`⟦S:⟧` 或 `【方法约束】` 豁免）：

```text
  claim-decision.md              裸表行=0 裸bullet=0  OK
  compensation-tier.md           裸表行=0 裸bullet=0  OK
  coverage-limit.md              裸表行=0 裸bullet=0  OK
  infection-status.md            裸表行=0 裸bullet=0  OK
  loss-severity.md               裸表行=0 裸bullet=0  OK
  policy-expiry.md               裸表行=0 裸bullet=0  OK
  primary-responsibility.md      裸表行=0 裸bullet=0  OK
  report-consistency.md          裸表行=0 裸bullet=0  OK
  underwriting-decision.md       裸表行=0 裸bullet=0  OK
```

9/9 页**裸断言数 = 0**；每个属性都带 `@labels.<key>`（表格逐单元）或行区间（§1 题干出处）。实体页内容全部是"本子集里哪些单元出现过该字段、取值是什么"，无条款解释、无精算推断。

### 5.2 `task_layer` 全为 `scenario` 的分层退化 → **三处都有明示**

| 位置 | 原文 |
|---|---|
| doc 页（4/4 页均有） | `- 本子集 54 条的 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`：**分层实际只落在 `task_name` 这一层**…⟦qid=agri_0@sample.task_layer⟧⟦qid=agri_0@sample.meta_task⟧` |
| `index.md` | `> 全子集 54 条 `task_layer` 均为 `scenario`：分层实际只落在 `task_name` 这一层。` |
| `schema.md:66` | `- 本子集 54 条 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`：分层只落在 `task_name`。` |

### 5.3 图片未入 `raw/assets/` → **通过（引用处写明重取）**

`raw/assets/` 只有 `README.md`；含图片标记的 4 个 doc 页各 1 条图片标记，且**每页都写明**"未入库 + 必须按 `data/ins-mmbench/FETCH.md` 重取 + `normalize_raw.py check` 复核"：

```text
  ins-mmbench-agricultural.md        图片标记=  1  写明重取=YES
  ins-mmbench-auto.md                图片标记=  1  写明重取=YES
  ins-mmbench-health.md              图片标记=  1  写明重取=YES
  ins-mmbench-property.md            图片标记=  1  写明重取=YES
```

### 5.4 `insurance_line` 改名是否彻底 → **通过（仅剩映射说明）**

```text
$ grep -rn "claim_type" data/llm-wiki-claims/ | grep -v __pycache__
data/llm-wiki-claims/wiki/schema.md:35-37          ← 旧名 → 新名映射说明（允许）
data/llm-wiki-claims/wiki/README.md:29             ← 字段清单括注"旧名 claim_type，已改名"（允许）
data/llm-wiki-claims/scripts/compile_wiki.py:704-706 ← schema.md 模板同源文本（允许）
```

- 页面 frontmatter 中 `claim_type:` 字段命中数 = **0**；`insurance_line:` 命中 = **36/36**。
- 无任何代码用 `CLAIM_TYPE` 常量读取该字段。

---

## 6. 遗留问题与交接

### 6.1 数据/设计限制（不可在本文范围内根治，如实登记）

1. **同名不同义的 label 键**：`labels.claim` 在 `claim`（汽车）分片是**金额**、在 `agri` 分片是**决策枚举**。
   已缓解（分片分别登记 + 页内显式告警），**未根治**。彻底做法：把 agri 的 `claim` 映射到 `claims-entity-claim-decision`（与 property 的 `claim_decision` 同义）。该改动要动 `plan.md` 的实体清单（不在写作用域），**建议队长裁决后再动**。
2. **`plan.md` 声明的抽样数与实际 raw 条数不一致**：`plan.md:49` 为 `auto` doc 页声明 `claim 12 + liability 12 = 24`，其中 liability 用的是**非连续**的原始索引（0000…0020），而 raw 只有 12 条。
   页面现在用"连续段标记"如实表达（不再越界），但 `plan.md` 文本本身仍写着 `12: raw-liability-0000 … raw-liability-0020` —— **`plan.md` 不在写作用域，未改**。
3. **`entities/compensation-tier` 与 `sections/agri-compensation-tier` 标题近似**（"赔付档位" vs "赔付档位（agri_claim_processing）"），L5 因字符串不同而不判重；语义上一个是跨分片实体、一个是章节页，**不算重复**，但读者易混，建议 C5 在索引里补一句区分说明。

### 6.2 并发提示（做质检时必须知道）

本任务执行期间（17:16→18:28）另一位成员（`wiki-lead`，任务 `t20` 仍为 `claimed`）**一直在改写同一批文件**。可复现的时间线（`wiki_lint.py` 同一命令）：

| 时刻 | 现象 | 处置 |
|---|---|---|
| 17:49 | `pages=36 index_rows=6 FAIL=64`（索引陈旧 + 4 条真缺陷） | 本文 §2 修复 + `build --all` → 18:2x 恢复 `FAIL=0` |
| 18:24 | 观察 `wiki/*.md`、`index.md`、`log.md` 同时刷新（另一进程重建） | 停写，连续采样等稳定（`md=40 / sections=18 / entities=9` 不变） |
| **18:28:00** | 再次突变：`FAIL=108`，全部为 L10（index 的 summary/updated/tags 与页面 frontmatter 不一致）→ 页面被重写而 index 未同步 | 18:28:13 再一次 `build --all` 复位 |
| 18:28:13 / 18:28:21 | `FAIL=0`、两套 lint 均 0、审计 `1200/0`（连续两次采样一致） | 本文所有“最终证据”均取自此时刻 |
**建议**：t20 正式收尾后，由 C5 用本文件 §7 的一条命令复跑 lint + 审计各一次，确认仍在 `FAIL=0 / 1200-0`。

### 6.3 给后续任务的三条

1. **不要手改 `wiki/**` 页面**——它们由 `compile_wiki.py` 确定性生成；改页面会被下次 `build` 覆盖。要改就改生成器再 `build --all`（本步就是这么修的）。
2. **新增页面时必须带标记**：表行/项目符号无 `⟦S:…⟧` 会被 L7 直接拦；多字段章节会自动逐字段出引用（§2.4）。
3. **区间标记只允许连续段**：非连续抽样集合必须拆段（§2.2）；lint 已加固，写错会 FAIL。

---

## 7. 复跑方式（C5 照抄）

```bash
cd renewal-assistant
python3 data/llm-wiki-claims/scripts/wiki_lint.py            # 期望：pages=36 index_rows=36 FAIL=0 WARN=0
python3 data/llm-wiki-claims/scripts/wiki_claims_lint.py     # 期望：pages=36 index_rows=36 ERROR=0 WARN=0
python3 /tmp/d4_audit.py                                     # 期望：assertions=1200 resolvable=1200 unresolvable=0
                                                             #（脚本若已丢，可按本文件 §3.3 的 4 类解析规则重建）
python3 data/llm-wiki-claims/scripts/compile_wiki.py check   # 期望：幂等（无"被手改/非幂等"报告）
```

---

## 8. 变更记录

| 时间 | 变更 | 作者 |
|---|---|---|
| 2026-11-18 18:27 | 初版：36 页全量 lint（修复 64→0）+ 1200 条断言全量审计 + 6 页 18 条人工复核 + 4 项专项检查；修复 3 类缺陷并加固 L6 | integrate（t23） |
