# D5 准备性研究：检索接口实读 + 评测口径（落盘依据）

> 任务：t8 / D5（retrieval-engineer，attempt 1）。
> 硬规则：写代码前先检索 ≥3 个独立外部来源并把依据落盘；本文件即该依据。
> 时间：2026-11-17 23:20 ~ 2026-11-18 18:25（+0800）。
> 本文只记录「检索与评测方法」的决策依据；实现过程与实测输出见 `docs/log/step-d5.md`。

## 1. 结论摘要（先给结论，证据在后）

1. **语料根可注入，不必改 `server/wiki_search.py`**：`WikiSearch.__init__(wiki_dir=...)` 已参数化（第 361 行附近），
   `scripts/wiki_tool.py` 已有显式传目录的先例。理赔域只要 `WikiSearch(wiki_dir=claims.config.wiki_dir())`。
2. **但直接复用会在理赔 wiki 上加载到 0 条**：`WikiSearch._load()` 用的是 `wiki_dir.glob("*.md")`（**非递归**），
   而理赔 wiki 是 `docs/ sections/ entities/ faqs/` 四层子目录（36 页）。因此必须在 `claims/` 内**继承并重写 `_load`**，
   不能改上游（续保 `wiki/` 是扁平的，改上游会改变续保行为）。
3. **空语料必须显式失败**：上游 `available=False` 时 `search_with_score()` 静默返回 `([], [])`。
   对理赔域这是"检索不到东西但流程正常"的隐蔽故障，D5 包装层改为**构造即断言 `entries > 0`**，空目录/不存在目录一律抛错。
4. **小语料不上嵌入模型**：36 页 / 11.4 万字符量级，LLM-Wiki 的"读 index → 钻取条目 → 必要时全量上下文"足够；
   混合检索的增益在此规模下不可测（见 S4 的大规模对照：RRF 只比 BM25 高 3.5 个 MRR@5 点，而 rerank 高 10+ 点）。
   决策：**BM25 三通道 + RRF(k=60) + 全量上下文**，不引入向量模型；把"何时需要嵌入"写成显式复评条件。
5. **引用接地率按"能不能回到 raw 源逐字成立"算**，不是"答案看起来有引用"：复用 D3/D4 的断言级标记
   `⟦S:INS-MMBench:<qid>@<span>⟧`，逐条解析到 `raw/sources/*.json` 校验 span 可解析 + 值逐字出现在被引片段里。
   这是对 ALCE 的 citation recall/precision（NLI 判定）在**无模型、可复现**条件下的词法近似，口径差异写在 §4.3。

## 2. 来源登记表（外部检索证据）

| # | 来源 | URL | 检索时间（+0800） | 支撑的决策 |
|---|---|---|---|---|
| S1 | ir_measures 官方文档 `Measures`（信息检索指标库，实现对齐 TREC） | https://ir-measur.es/en/latest/measures.html | 2026-11-17 23:22 | Hit@k / MRR@k 的**标准定义**与命名（Success@k vs Recall@k 的区别） |
| S2 | ALCE: Enabling LLMs to Generate Text with Citations（EMNLP 2023，arXiv:2305.14627） | https://arxiv.org/abs/2305.14627 · https://arxiv.org/html/2305.14627v2 | 2026-11-17 23:25 | 引用质量两维口径：citation recall / citation precision 的定义与聚合方式 |
| S3 | Karpathy《LLM Wiki》idea file（gist raw，2026-04） | https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f | 2026-11-17 23:27 | 小语料（~100 sources）用 index.md 导航即可，**不需要 embedding RAG 基础设施**；Query 顺序=读 index→钻取 |
| S4 | SciClaimSeekers at CheckThat! 2026（arXiv:2607.24803，2026-07-06） | https://arxiv.org/abs/2607.24803v1 | 2026-11-17 23:24 | BM25 vs BM25+E5+RRF(k=60) vs +rerank 的**量化对照**（MRR@5 50.69 → 54.19 → 64.36） |
| S5 | Domain-specific information retrieval（FnT IR 2026，arXiv:2611.08228） | https://arxiv.org/abs/2611.08228 | 2026-11-18 18:24 | 领域检索的语料/查询形态与网页检索不同（长文档、长查询），作为"不能照搬开放域结论"的背景 |

### 2.1 直接引用的原文要点

- **S1（指标定义）**
  - `Success`：「1 if a document with at least rel relevance is found in the first cutoff documents, else 0.
    NOTE: Some refer to this measure as Recall@k. This software follows the TREC convention, where Recall@k is defined
    as the proportion of known relevant documents retrieved in the top k results.」
  - `R`（Recall@k）：「The fraction of relevant documents for a query that have been retrieved by rank k.」
  - `RR`（[M]RR）：「scores based on the reciprocal of the rank of the highest-scoring relevance document.
    An optional cutoff can be provided to limit the depth explored.」；别名表 `MRR → RR`。
  - 结论：本项目报的 **Hit@k 实际是 TREC 的 Success@k**（只要 top-k 里出现目标页即 1），文档里必须写清，
    避免与 Recall@k（分母=该查询全部相关页）混淆。
- **S2（引用质量）**
  - citation recall：对每条 statement 取 0/1，`iff` 有引用且 `NLI(concat(citations), statement)=1`，再对 statement 平均；
    与 AIS（Attributable to Identified Sources）框架一致。
  - citation precision：对每条 citation 取 0/1；citation "irrelevant" 定义为
    (a) 单独不能支撑该 statement，且 (b) 去掉它后其余引用仍能支撑；precision=1 以 recall=1 为前提。
  - 结论：引用质量必须**分开**报 recall（答案是否被引用支撑）与 precision（是否有冗余/无关引用）；
    本项目只做"precision 侧"的逐字可回溯核查，且**明确声明没有做 NLI entailment**。
- **S3（LLM-Wiki 小语料）**
  - 「This works surprisingly well at moderate scale (~100 sources, ~hundreds of pages) and avoids the need for
    embedding-based RAG infrastructure.」
  - Query：「The LLM searches for relevant pages, reads them, and synthesizes an answer with citations.」
  - 结论：36 页语料用 index/条目导航 + 词法检索是**符合该模式的设计**，不是"降级方案"。
- **S4（混合检索量化）**
  - 原文：BM25 基线 **64.36% MRR@5**（含 rerank）对比中提到「13.67-point jump over BM25 and 10.17 points over the
    unranked hybrid」——即 BM25 50.69、BM25+E5+RRF(k=60) 54.19、再加 Qwen rerank 64.36（英文 dev set）。
  - 结论：**RRF 融合的增益（+3.5）远小于 rerank（+10.2）**；在只有几十页的语料上，融合带来的可测增益更小。
    若要继续提升，优先考虑 rerank 而不是"再加一路向量召回"。

## 3. `server/wiki_search.py` 实读结论（接口与三处坑）

实读版本：2026-11-17 21:41 的工作区版本（renewal-assistant/server/wiki_search.py，438 行）。

### 3.1 可直接复用的能力（不重造）

| 能力 | 入口 | 说明 |
|---|---|---|
| 三通道 BM25 | `WikiSearch._load` + `_tokenize_bigram` / `_tokenize_word` | `bigram`（中文字符二元组+单字+英文词）、`index`（title+summary+tags+related+category+章节标题）、`word`（英文/数字词+中文整段） |
| RRF 融合 | `_rrf_fuse(ranked_lists, k=60)` | 只用排名，`score(d)=Σ 1/(k+rank)`，免分数归一化 |
| 检索 | `search_with_score(query, top_k, channels)` | 返回 `(entries, scores)` |
| 章节定位 | `section_for(entry, query)` | 章节内命中词最多者胜 |
| 逐字片段 | `excerpt(entry, width, query)` / `span_citation(entry, query)` | 返回正文逐字子串 + `anchor=wiki_id#section` + `verbatim` |
| 词法接地 | `verify_citations(query, entries)` | grounded=查询内容词是否出现在条目里；coverage=命中词/语料内可命中词 |
| 全量上下文 | `llm_wiki_context(entries, char_budget=24000)` / `wiki_nav(entries)` | LLM-Wiki 暴力上下文 + 紧凑目录 |
| 轨迹字段 | `hits_for_trace(entries, scores)` | 严格 `[{wiki_id, source, version, score}]`（SPEC §5） |

### 3.2 三个坑（D5 必须处理）

1. **语料根**：`__init__(wiki_dir=None)` → `self.wiki_dir = wiki_dir or config.WIKI_DIR`；`config.WIKI_DIR` 是
   `env("WIKI_DIR", <repo>/wiki)`，**默认指向续保 8 条条款**。`get_searcher()` 是模块级单例，永远读续保 wiki。
   → 理赔域**不得**用 `WikiSearch()` / `get_searcher()`，必须显式传 `claims.config.wiki_dir()`。
2. **非递归加载**：`_load()` 用 `self.wiki_dir.glob("*.md")`，只扫一层。理赔 wiki 是四层子目录
   （`docs/ sections/ entities/ faqs/`，36 页），直接传目录会得到 **0 entries 且不报错**。
   → 在 `claims/` 内子类化并重写 `_load`（`rglob`），不改上游。
3. **空语料静默**：`search_with_score` 首行 `if not self.available: return [], []`。空目录/路径写错 = 静默空结果。
   → 包装层构造时断言 `entries > 0` 且 `_index` 非空，抛 `WikiCorpusEmpty` / `WikiRankerUnavailable`。

### 3.3 隔离边界

- 只 import `server.wiki_search`（读），不修改；`server/`、`tests/`、`mcp_servers/`、`wiki/`、`SPEC.md` 保持零 diff。
- 不碰 `claims/graph.py`（F2d 在改）、不碰 `claims/deep_agents/**`（F3 领地）。
- 理赔 wiki 根：`claims.config.wiki_dir()`（默认 `data/llm-wiki-claims/wiki`，可被 `CLAIMS_WIKI_DIR` 覆盖）。

## 4. 评测口径（可复现定义）

### 4.1 检索指标（依据 S1）

对每个查询 `q`，取 top-K（K=5）返回页 id 列表 `R_q`，目标页集合 `G_q`（多值表示业务等价、任一命中即算对）：

- `Hit@1(q) = 1[∃ g ∈ G_q : rank(g | R_q) = 1]`（TREC 的 `Success@1`）
- `Hit@5(q) = 1[∃ g ∈ G_q : rank(g | R_q) ≤ 5]`（`Success@5`；**不是** Recall@5）
- `RR@5(q) = 1/rank(first hit | R_q)`，无命中记 0；`MRR@5 = mean_q RR@5(q)`
- 聚合：**按查询宏平均**，分母不含负样本（负样本单列 abstention）。

### 4.2 引用接地率（claims 专用，逐字回到 raw）

对返回的每条引用标记 `⟦S:INS-MMBench:<qid 或 qids=a..b>@<span>⟧`：

1. **可解析**：qid → `raw/sources/raw-<split>-<idx:04>.json` 存在（`<split>_<idx>` 拆分后 zero-pad 到 4 位）；
2. **span 成立**：
   - `Lx-Ly`：行区间在该单元题干行数内，且标记前的引用块逐行出现在 `content.question.text` 中；
   - `labels.X`：`labels` 中存在键 `X`，且该键的值**逐字**出现在被引用的 wiki 行里（聚合标记则要求每个 qid 的取值都出现在页内）；
   - 图片路径：出现在 `images[].path`；`answer_status`：raw 顶层存在该字段。
3. `引用接地率 = 通过校验的引用条数 / 返回证据里的引用总条数`（precision 视角）。

> 与 ALCE（S2）的差异：ALCE 用 NLI 判"引用能否蕴含 statement"，本实现用**逐字 + JSON 路径可解析**判"引用能否
> 回到 raw 源成立"。后者更弱（不做语义蕴含）但**完全确定、可复现、无需模型**；因此只报 precision 侧，
> **不声称等价于 ALCE 的 citation recall**。

### 4.3 防循环论证（队长 2026-11-18 提醒）

wiki 页是从 54 条 raw `question` 抽出来的，若查询直接取原题干，Hit@1 只证明"自己检索自己"。
本评测把查询集**分三类分别报数**：

| 类别 | 构造方式 | 作用 |
|---|---|---|
| `seen` | 直接取页面标题（title 拷贝） | 数据泄漏的**上界**，仅作对照，不代表检索能力 |
| `rewritten` | 改写成自然中文问法（换词序/同义表达，不贴原题干） | **主指标** |
| `negative` | 问 wiki 未覆盖的主题（如"新能源车电池自燃"） | 期望无接地结果/拒答，不进 Hit/MRR 分母 |

## 5. 决策与被否决方案

| 决策 | 采纳/否决 | 理由 |
|---|---|---|
| 继承 `WikiSearch` 并重写 `_load`（rglob） | ✅ 采纳 | 复用 BM25/RRF/引用逻辑，同时修掉非递归与空语料静默；上游零改动 |
| 改 `server/wiki_search.py` 支持递归 | ❌ 否决 | 续保 `wiki/` 扁平，改上游=改续保行为，违反隔离铁律 |
| 引入 BGE-M3 / embedding 混合检索 | ❌ 本轮否决 | 36 页量级回归不到增益（S3/S4）；且会引入模型依赖与不可复现因素。复评条件写在 §6 |
| 用 `wiki/index.md` 做导航检索 | ❌ 本轮否决 | 截至 2026-11-18 18:06，index.md 只登记 6 页而磁盘有 36 页（t20 正在生成，见 §6），不可作为检索入口；条目导航由 `wiki_nav()` 从磁盘页生成 |
| 引用接地用 `verify_citations` 的词法覆盖 | ⚠️ 仅作辅助 | 它判"查询词是否出现在条目"，不判"引用能否回到 raw"；与 raw 级校验并列输出，不混为一个数 |

## 6. 限制与待验证（必须写进最终报告）

1. **语料处于生成中**：2026-11-18 18:06 磁盘 36 页（4 doc/18 section/9 entity/5 faq），但 `index.md` 仍写着
   "当前条目数：6"且只列 6 行 —— t20 的 index 尚未重生成（或正在写）。**检索按磁盘页加载，不读 index**；
   最终评测数字必须在 index/log 与 36 页一致后重跑一次。
2. **数据泄漏**：见 §4.3；`seen` 与 `rewritten` 必须分开报，不能只报高的那个。
3. **规模**：36 页 / 11.4 万字符，Hit@1 的置信区间很宽（每条查询 1/12 量级的抖动），只报点估计 + 明确样本量。
4. **复评嵌入模型的条件**（写成可执行判据，避免"凭感觉"）：
   - 页面数 > 300，或全量上下文 > 2× `llm_wiki_context` 预算（当前预算 24000 字符）；
   - 或 `rewritten` 查询的 Hit@1 连续两轮 < 0.8 且 miss 集中在"同义改写/跨语言"。
5. **引用接地率不含答案生成质量**：D5 的 demo 若走 LLM 模式，生成文本的正确性不在本指标内（本轮不报准确率，
   依据 D1 结论：54 条 `answer` 全为 null）。
