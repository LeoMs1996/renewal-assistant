# D5 实施日志：wiki 后续使用（检索层 + 问答 demo + 检索质量评测）

> 任务：t8 / D5（retrieval-engineer，attempt 1，2026-11-18）。
> 研究依据：`docs/log/prep-d5-retrieval.md`（≥3 外部来源 + 接口实读）。
> 边界：只新增 `claims/**` 与 `docs/**`；`server/ tests/ mcp_servers/ wiki/ SPEC.md claims/graph.py
> claims/deep_agents/**` 零改动（§3.5 有 `git diff` 证据）。

## 1. 改动清单

| 文件 | 行数 | 作用 |
|---|---|---|
| `claims/wiki_retrieve.py` | 525（新增） | 理赔检索层：`ClaimsWikiSearch`（继承 `server.wiki_search.WikiSearch`，重写 `_load` 支持嵌套目录）+ `retrieve()` + raw 级引用核查 + CLI |
| `claims/qa_demo.py` | 163（新增） | 问答 demo：extractive / llm 两模式，模式与降级显式标注，LLM 默认关闭 |
| `claims/eval_retrieval.py` | 204（新增） | 留出集评测：Hit@1 / Hit@5 / MRR@5 / 引用接地（ok + 逐字级）/ 负样本拒答；结果落 `claims/data/eval/` |
| `claims/tests/test_d5_wiki_retrieval.py` | 206（新增） | 20 条测试：语料隔离、空语料显式失败、引用回 raw（含 2 个负向控制）、指标公式、拒答、降级 |
| `docs/log/prep-d5-retrieval.md` | 155（新增） | 研究依据与口径（本轮代码前的落盘证据） |
| `docs/log/step-d5.md` | 本文件 | 实施四件套；D5b（t27）更正 index 观测并补 §3.6/§3.7 |
| `docs/log/step-d5-retrieval.md` | 指针 | 任务契约文件名 → 本文件 |

**没有改动**：`server/wiki_search.py`（续保在用）、`claims/config.py`（已有 `wiki_dir()`，直接用）、
`claims/graph.py`（F2d 在改）、`claims/deep_agents/**`（F3 领地）、`wiki/`、`SPEC.md`。

## 2. 决策与依据

| # | 决策 | 依据 / 被否决方案 |
|---|---|---|
| D5-01 | **继承**上游并重写 `_load()`，不改上游 | 上游 `_load()` 是 `glob("*.md")` 非递归；理赔 wiki 是 `docs/ sections/ entities/ faqs/` 四层（36 页）。直接传目录 → 0 条且不报错。改上游会影响续保（其 wiki 是扁平的），违反隔离铁律 |
| D5-02 | **构造即断言**语料非空，否则抛 `WikiCorpusEmpty` | 上游 `available=False` 时 `search_with_score()` 静默返回 `([], [])`；队长 X1 实测 `cd /tmp` 后 entries=0 且无异常。测试覆盖：目录不存在 / 空目录 / 只有无 frontmatter 文件，三者都必须抛错 |
| D5-03 | 默认融合通道 `("word","index")`，**不用**上游 `bigram` 全量通道 | 上游 `_tokenize_bigram` 把英文词拆成单字母（`auto` → a/u/t/o），理赔 wiki 是「中文正文 + 英文枚举值」，单字母噪声会让 4 个仅差一个英文词的 doc 页互相压制。§3.3 消融表：`(word,index)` 把 `seen` 的 Hit@1 从 0.67 提到 0.83，`rewritten` Hit@1 不变；代价是 `rewritten` MRR@5 0.845→0.827（14 条样本上的 ±1 条抖动，不作为主依据）。**理由是可解释的机制，不是调参**；`channels=` 可覆盖 |
| D5-04 | 引用接地 = **标记 → raw 源逐字**，两级强度 | 复用 D3 的断言级标记 `⟦S:INS-MMBench:<qid>@<span>⟧`；解析到 `raw/sources/*.json`。`value/verbatim`=逐字级；`field/range`=存在性/可解析级。长表格单元格截断（`The vehicles does not n…`）按「值前 16 字符逐字出现」判存在性，否则会把正常截断误判为编造。负向控制：把 `grape` 改成 `banana` → `ok=0`；把题干预引块改成中文 → `ok=0` |
| D5-05 | 拒答门槛 `MIN_TERM_SUPPORT=0.3`（查询内容词在命中页全文中的支持率） | 负样本必须「低分或无匹配」，不能硬凑。4/4 负样本 support ≤0.222 全部拒答；代价是 14 条改写查询中 5 条（support 0.20–0.286）也被拒答——**金融合规口径下宁可拒答**；阈值随结果输出（`min_term_support`）供复查 |
| D5-06 | 指标按 TREC/ir_measures 口径：`Hit@k = Success@k`，`MRR@k` 超出 k 记 0 | 依据 S1 原文（见 prep §2.1）。**测试抓到一个真 bug**：初版 MRR 把 rank=6 也算 1/6，已修（`test_metrics_formula`） |
| D5-07 | 引用的「逐字级」单列，不和「存在性」混成一个数 | ALCE（S2）分开报 citation recall/precision；本项目只做 precision 侧的词法近似，**不做 NLI 蕴含**，不声称等价 |
| D5-08 | 查询集三分：`rewritten`（主）/`seen`（title 拷贝，泄漏上界）/`negative`（拒答） | 队长 2026-11-18 的循环论证提醒：wiki 页从 54 条 raw question 抽出，若直接拿原题干查=背题。结果分开报，不合成总分 |
| D5-09 | LLM 问答默认关闭（`CLAIMS_QA_LLM=1` 或 `--mode llm` 才开） | 避免 CI/评测意外出网与不可复现；无凭证时**降级 extractive** 并输出 `degraded=True, error_type=NoCredentials`（对齐 SPEC-claims §9 降级留痕） |

来源（本轮实现引用的外部证据，均落盘于 prep 文档）：

- S1 ir_measures `Measures`（Success@k / R@k / RR 定义）— https://ir-measur.es/en/latest/measures.html — 2026-11-17 23:22
- S2 ALCE（citation recall / precision）— https://arxiv.org/abs/2305.14627 — 2026-11-17 23:25
- S3 Karpathy LLM-Wiki（~100 sources 用 index 导航即可，无需 embedding RAG）— https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f — 2026-11-17 23:27
- S4 SciClaimSeekers 2026（BM25 50.69 → +RRF 54.19 → +rerank 64.36 MRR@5）— https://arxiv.org/abs/2607.24803v1 — 2026-11-17 23:24
- S5 Domain-specific IR（FnT IR 2026）— https://arxiv.org/abs/2611.08228 — 2026-11-18 18:24

## 3. 命令与真实输出

### 3.1 检索评测（主指标）

```bash
.venv/bin/python -m claims.eval_retrieval
```

```
语料：36 页 / 122995 字符 {'doc': 4, 'entity': 9, 'faq': 5, 'section': 18} sha256:47c81f21fa949ae2
截断：Hit@5 / MRR@5，引用接地看 top-3，拒答门槛 term_support<0.3

| 查询集 | 条数 | Hit@1 | Hit@5 | MRR@5 | 引用接地 | 逐字级 | 拒答 |
|---|---|---|---|---|---|---|---|
| rewritten | 14 | 0.714 | 1.0 | 0.827 | 1.0 | 0.852 | — |
| seen | 6 | 0.833 | 1.0 | 0.875 | 1.0 | 0.85 | — |
| negative | 4 | 0.0 | 0.0 | 0.0 | — | — | 4/4 |
```

结果文件：`claims/data/eval/d5-retrieval-20261118-*.json`（`claims/data/**` 已 gitignore，运行态不入库；
每条查询的 `got/rank/abstained/support/citations` 都在 JSON 里，可复现）。

**诚实读法**：
- `rewritten` Hit@5=1.0 但 Hit@1=0.714：14 条里 4 条目标页不在第 1（rank 2/3/4），不是"全对"；
- `seen` 0.833 < 1.0：4 个 doc 页标题只差一个英文词，词法检索分不清（见 D5-03），**这是能力上限的真实暴露**；
- 引用接地 1.0 / 逐字级 0.85：所有引用都能解析回 raw；15% 属"字段存在性/表格截断"级，不是取值逐字；
- 5/14 改写查询被判"依据不足"（support<0.3），**保守拒答**是设计选择，不是漏检（Hit 指标仍算命中）。

### 3.2 问答 demo

```bash
.venv/bin/python -m claims.qa_demo "农业保险赔付档位怎么确定"
.venv/bin/python -m claims.qa_demo "新能源车电池自燃怎么赔"
```

```
问题：农业保险赔付档位怎么确定
模式：extractive（degraded=False）
语料：36 页，sha256 47c81f21fa949ae2
证据：['claims-faq-agri', 'claims-entity-compensation-tier', 'claims-section-agri-compensation-tier']
引用接地：101/101（率 1.0，逐字级 0.891）
答案引用可解析：3/3
【依据】… [claims-faq-agri] …（引用接地 55/55；逐字级 49/55） …

问题：新能源车电池自燃怎么赔
模式：extractive（degraded=False）
引用接地：213/213（率 1.0，逐字级 0.887）
答案引用可解析：0/0
【依据不足】claims wiki 未覆盖该问题（查询词最高支持 0.0，门槛 0.3）。不给出结论，避免编造。
```

LLM 模式（本轮未配凭证，**未验证真实模型输出**）：`--mode llm` 在无凭证时输出
`mode=extractive, degraded=True, error_type=NoCredentials`（测试覆盖）。

### 3.3 通道消融（解释 D5-03；同一评测集，`Hit@1/Hit@5/MRR@5`）

| 通道 | rewritten | seen | 负样本拒答 |
|---|---|---|---|
| `(bigram,)` | 0.71/1.00/0.827 | 0.50/1.00/0.681 | 4/4 |
| `(word,)` | 0.00/0.00/0.000 | 0.83/1.00/0.875 | 4/4 |
| `(index,)` | 0.71/1.00/0.827 | 0.67/1.00/0.764 | 4/4 |
| `(bigram, word)` | 0.71/1.00/0.827 | 0.50/1.00/0.708 | 4/4 |
| **`(word, index)`（采用）** | **0.71/1.00/0.827** | **0.83/1.00/0.875** | **4/4** |
| `(bigram, index, word)`（上游默认） | 0.71/1.00/0.845 | 0.67/1.00/0.764 | 4/4 |

`(word,)` 单通道中文改写查询全灭（`_tokenize_word` 把整段中文当一个词），说明 `index` 通道负责中文导航；
`bigram` 只贡献英文分词的噪声。

### 3.4 测试与静态检查

```bash
.venv/bin/python -m pytest claims/tests            # 78 passed in 1.49s
.venv/bin/python -m pytest                         # 148 passed, 2 skipped in 2.14s（续保基线不变）
.venv/bin/python -m ruff check claims/wiki_retrieve.py claims/qa_demo.py claims/eval_retrieval.py claims/tests/test_d5_wiki_retrieval.py
# All checks passed!
```

D5 专项 20 条：`test_loads_claims_wiki_only` / `test_claims_wiki_dir_differs_from_renewal` /
`test_renewal_searcher_untouched` / 3 条空语料显式失败 / `test_raw_citation_valid_and_fabricated`（负向控制）/
`test_raw_citation_missing_source` / `test_line_range_span_requires_verbatim_quote`（负向控制）/
4 条负样本拒答 / `test_metrics_formula` / `test_eval_report_shape` / 3 条 demo 模式与降级。

### 3.5 零回归与隔离证据

```bash
git diff --stat -- server tests mcp_servers wiki SPEC.md claims/graph.py claims/deep_agents
# （输出为空）
```

- `server/wiki_search.py`：未改；`server.wiki_search.get_searcher()` 仍指向续保 `wiki/`（有测试断言）；
- `claims/graph.py`、`claims/deep_agents/**`：未触碰；
- 未写 `traces/`、`wiki/`；demo/评测不写 `claims/data/` 以外的位置（评测 JSON 在 `claims/data/eval/`，已 gitignore）。
### 3.6 `_load()` 重写的边界（上游零改动，只在 `claims/` 包一层）

**为什么必须重写**：上游 `server/wiki_search.py::WikiSearch._load()` 用 `self.wiki_dir.glob("*.md")`
**只扫一层**。理赔 wiki 是 `docs/ sections/ entities/ faqs/` 四层嵌套（36 页），直接
`WikiSearch(wiki_dir=claims_wiki)` 会得到 `entries=0`；而 `search_with_score()` 在 `available=False`
时**静默返回 `([], [])`** —— 流水线不会报错，只会「检索不到东西但一切正常」。

D5 的做法：在 `claims/wiki_retrieve.py` 里 `class ClaimsWikiSearch(ws.WikiSearch)`，**只重写 `_load()`**
（`rglob` + 跳过 `index/log/schema/README` + 补 `page_type` / `rel_path` 两个理赔页字段），
BM25 建索引、RRF(k=60)、`search_with_score`、`span_citation`、`verify_citations`、`llm_wiki_context`
全部复用上游。**不是复制一份检索器，也不是 fork 上游。**

**边界证据（上游零改动）**：

```bash
git diff --stat -- server/
# （输出为空）
```

- `server/wiki_search.py` 不在 `git status` / `git diff` 中（D5b 复核时仍为空）；
- 行为隔离有测试：`test_renewal_searcher_untouched` 断言 `server.wiki_search.get_searcher()` 仍是续保单例、
  `wiki_dir` 仍指向续保 `wiki/`、与理赔 entries 无交集；
- 风险边界：若上游将来自己把 `_load()` 改成 `rglob`，本子类的重写只是变成冗余，不会互相破坏。

### 3.7 D5b 复跑：index 重构不影响指标（2026-11-18 20:45 首测 / 21:08 终验）

**t26 已完成**（状态板 completed；`index.md` 5867 B，20:07 写入）：index 行格式已改为
「id | 标题 | 短标签 | tags | updated」（不再有 type 列）。本节的 baseline 与受控实验均在该**最终版**
index 上执行；检索层的 `page_type` 取自页面 frontmatter、不读 index 表，因此格式无关。

**页面指纹**：`content_sha256 = 47c81f21fa949ae2`（36 页 / 122995 字符）—— 与 D5 首次评测**完全一致**，
说明 t25/t26 没改页面内容。`index.md` 现状：数据行 36（`^|` 总行 44 = 36 数据 + 8 表头/分隔），
两套 lint 均 0 error。

**复跑结果（与 §3.1 逐位一致）**：

| 查询集 | 条数 | Hit@1 | Hit@5 | MRR@5 | 引用接地 | 逐字级 | 拒答 |
|---|---|---|---|---|---|---|---|
| rewritten | 14 | 0.714 | 1.0 | 0.827 | 1.0 | 0.852 | — |
| seen | 6 | 0.833 | 1.0 | 0.875 | 1.0 | 0.85 | — |
| negative | 4 | 0.0 | 0.0 | 0.0 | — | — | 4/4 |

**受控实验（不依赖 t26 的完成时机，直接证明 index 与检索无关）**：把 wiki 复制到临时目录后
（`CLAIMS_RAW_DIR` 指回真实 raw）：

1. 把 36 行 index 摘要全部改成 `MUTATED-nn` → 三分集指标**完全相同**，`per_query` 逐条相同；
2. 直接删除 `index.md` → 三分集指标**完全相同**，`per_query` 逐条相同；
3. 两种变体的页面 `content_sha256` 均仍为 `47c81f21`（只改 index，不动页面）。

原因：`_load()` 按文件名跳过 `index.md`，导航层由 `wiki_nav()` 从 entries 现场生成，检索输入里没有 index。
**结论：t26 的 index 摘要格式变更（含将来再改 index 排版）不会改变任何检索/引用指标；**
真正需要 index 的是「LLM 先读目录再钻取」的阅读模式（D4 的 E2 守的是这条链路）。

> 注：`prep-d5-retrieval.md` §6.1 里的「index 只 6 行」与本节结论冲突，以本节为准（prep 是实施前快照，未回改）。

## 4. 遗留与交接

1. **`index.md` 过时观测已更正（D5b）**：D5 日志写的「index 只列 6 行」是 **t25 重构 index 过程中的并发中间态**
   （18:06 时页面已 36、index 尚未重生成），不是最终状态。复核现状：`pages=36`、index 数据行 36、
   两套 lint 均 0 error（队长独立复核同值）。D5b 复跑：页面 `content_sha256=47c81f21` 与 D5 一致，
   三分集指标逐位一致；受控实验（改摘要 / 删 index）`per_query` 仍逐条相同（见 §3.7）——
   **t26 只改 index 摘要不会影响检索指标**。
   **教训（保留）**：读别人正在写的产物前，先确认对方任务已完成，或至少做两次间隔快照确认
   mtime/sha256 稳定；本次 D5b 用「3 秒双快照 + 只依赖磁盘页、不读 index」两条来规避。
   同类风险提示：并发读中间态得到的「阻塞」结论，上报前应先复验一次（本次是假阳性）。
2. **33 页新页未过 D4 全量 lint**：D5 的 raw 级核查在 3 页 pilot 上 0 失败；对 36 页做全量核查时，
   初版有 5 类 `labels.causes / original_report / adjusted_report` 误报，根因是**长表格单元格截断**
   （值前 16 字符逐字出现），已按"存在性级"接受。建议 D4 把 lint 的 E9 从"键存在"升级为
   "键存在 + 值（或截断前缀）出现在被引行"，与 D5 `verify_raw_citations` 对齐。
3. **样本量小**：14 / 6 / 4 条，Hit@1 的 ±1 条就是 0.07 的抖动，只能看方向不能看小数点；本轮不做显著性检验。
4. **中英词表鸿沟（未解决，已登记）**：wiki 页正文是中文、字段值是英文（葡萄 ↔ `grape`），
   纯词法检索对"葡萄"类查询只能靠共现词命中。**本轮不引入嵌入模型**（依据 S3/S4：36 页量级收益不可测，
   且会引入模型依赖）；复评条件写在 prep §6.4（页数 >300 / 上下文超 2× 预算 / 改写查询 Hit@1 连续两轮 <0.8）。
5. **F4 集成接口**：请用 `from claims import wiki_retrieve as wr; wr.get_searcher()` 与 `wr.retrieve(q, top_k)`；
   **不要**用 `server.wiki_search.get_searcher()`（读续保 wiki）。`retrieve()` 返回
   `{query, corpus, hits[], citations{total,ok,strict,rate,strict_rate}, grounding_rate,
   strict_verbatim_rate, min_term_support, best_term_support, abstained}`。
6. **真实模型路径未验证**：本轮 `CLAIMS_QA_LLM` 未开启、无凭证；LLM 模式的提示词与降级路径有单测，
   但"真实 GLM 输出质量"**未验证**，不得在文档里写成已验证。
7. **`claims/wiki.py` 别名未建**：队长建议名是 `claims/wiki.py`，正式交付按任务契约用
   `claims/wiki_retrieve.py`；若集成方按旧名 import，加一行 re-export 即可（本轮不加，避免两个入口）。
