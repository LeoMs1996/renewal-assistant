<!-- CH4 -->
## 4. 【重点】LLM-Wiki 实现过程

> **本章证据**：2026-11-24 11:51–11:54（+0800）本次 `ls` / `grep` / `read`（主文件 1–125 行对齐口吻，其余窗口 ≤37 行）+ 1 条 pytest（§4.5）；行号均为 grep 真实返回，找不到的写「未找到证据」。本章结构：4.1 选型 → 4.2 两套实现对照 → 4.3 实现过程（5 步）→ 4.4 已知限制 → 4.5 验证。

### 4.1 为什么是 LLM-Wiki 而不是向量 RAG

**SPEC 层面只有正向选择，没有否决句。** `SPEC.md:11`「结合 BM25 检索的条款知识库（wiki/）输出**带条款依据**的续保方案比较」、`SPEC.md:36`「rank-bm25（条款检索，中文字符二元组分词）」、`SPEC.md:365`「`retrieve_terms` | BM25 检索 wiki/ 条目，取 Top-3」；`docs/设计方案.md:135` 锁定依赖 `rank-bm25 0.2.2`。在 `SPEC.md`、`docs/设计方案.md`、`docs/log/decisions.md`、`docs/log/step-d5*.md` 中 grep「向量 / embedding」，**未找到证据**——没有任何一条显式写「不用向量库」。

**能找到的「为什么」在 11-17 知识检索域评审** `reviews/knowledge.md`：① 模式出处是 Karpathy《llm-wiki.md》——「三层架构（raw / wiki / schema）、三操作（Ingest / Query / Lint）、两个导航文件 `index.md` … 与 `log.md`（只追加 … 可 grep）」（`:77`；`wiki/README.md:4` 登记同一 gist，检索 2026-11-17）；② 稠密向量「在 145 文档规模上它未必带来显著提升，建议等语料 >100 条再评估，而不是现在堆栈」（`:219`，登记为 KB-7 low「未做」，`:40`）；③ 二元组分词「是零依赖选择，代价是跨词二元组噪声（『险包』『换车』）……本轮四次替代实验均无增益，故不改」（`:222`）。

### 4.2 两套实现对照表

| 维度 | ① 续保域 `wiki/` | ② 理赔域 `data/llm-wiki-claims/` |
|---|---|---|
| 条目数 | 8 条目；`ls` 实测共 **11 个 md**（+ README / index / log） | **36 页** = sections 18 + entities 9 + docs 4 + faqs 5（`ls` 实测；`docs/log/step-d2-normalize.md:59`），另有 index / log / README / schema 4 个非页文件（`scripts/wiki_claims_lint.py:38`） |
| 来源 | 人手写合成条款，`source:` 标「（虚构）」（`wiki/deductible.md:5`） | INS-MMBench 54 条 → `raw/sources/` 54 个不可变源单元（`ls` 实测；`docs/log/step-d2.md:7`） |
| front-matter 字段 | `id, version, effective_date, source, updated, category, tags, related, summary`（`wiki/README.md:19-29` 强制模板） | `id, type, title, domain, insurance_line, summary, tags, source_refs, raw_refs, updated, related, status`（`wiki/sections/agri-compensation-tier.md:1-14`）；lint 必填 `REQ`（`scripts/wiki_claims_lint.py:39`） |
| 检索方式 | 三通道 BM25（bigram / index / word）+ RRF 融合，Top-3（`server/wiki_search.py:208-210`、`:178`） | `ClaimsWikiSearch(ws.WikiSearch)`「复用（不重写）」三通道 + `RRF(k=60)`（`claims/wiki_retrieve.py:211`、`:13`） |
| 引用校验 | `span_citation`（`wiki_id#章节` 锚点 + 逐字 span + `verbatim`）→ `verify_citations` 词法接地 + coverage（`server/wiki_search.py:307-317`、`:361-389`） | 另加 `verify_raw_citations`（`claims/wiki_retrieve.py:425`）：按 `⟦S:INS-MMBench:qid=…@L1-L1⟧` 标记回查 raw 行号（页面示例 `wiki/sections/agri-compensation-tier.md:22`） |
| lint / 编译 | `scripts/wiki_tool.py`（187 行；index / lint / log，`wiki/README.md:6`） | `scripts/normalize_raw.py` 604 → `scripts/compile_wiki.py` 990（`m1 / mrange` 生成标记，`:122/:126`）→ `scripts/wiki_lint.py` 487 + `scripts/wiki_claims_lint.py` 403（`wc -l` 实测） |
| 所在域 / 代码位置 | 续保 `server/wiki_search.py`（429 行），节点 `retrieve_terms`（`SPEC.md:365`） | 理赔 `claims/wiki_retrieve.py`；`WIKI_DIR` 环境变量隔离、不改代码（主文件 §1.6 D-02） |
| 测试 | `tests/test_wiki_retrieval.py` 12 个 `test_`（`:42-135`） | `claims/tests/test_d5_wiki_retrieval.py` **≥3 个**（`:31/42/47`；`head -15` 截断，未见全貌） |

### 4.3 实现过程（按步骤）

1. **条目格式设计**：续保 9 字段 front-matter，`related`「必须双向互指」、`summary`「≤80 字」且「也进检索索引字段」（`wiki/README.md:27-28`）；理赔用枚举把页面类型与状态锁死——`type ∈ {doc, section, entity, faq, query}`、`status ∈ {draft, verified, conflicted, stale}`（`scripts/wiki_claims_lint.py:41-42`）。
2. **检索（BM25 + RRF）**：`_load` 只读 `*.md`、剔除 `index.md / log.md`「导航文件不是知识条目」（`server/wiki_search.py:198-200`），建三通道语料（`:208-210`）；`_rrf_fuse`「只用排名不用原始分，免归一化」（`:179`）；理赔侧继承不重写、k=60（`claims/wiki_retrieve.py:13`、`:211`）。
3. **引用校验**：`span_citation` 返回锚点 + 160 字宽逐字片段 + `verbatim` 布尔（`server/wiki_search.py:307-317`）；`verify_citations`「词法级引用核查（entailment-lite）… ALCE 式引用支撑校验的无模型近似」，coverage 分母「只算语料里真的出现过的词」（`:362-367`）；理赔再按标记回查 raw（`claims/wiki_retrieve.py:425`）。
4. **lint / 编译器**：续保 `scripts/wiki_tool.py` 三操作，`test_wiki_lint_has_no_errors`（`tests/test_wiki_retrieval.py:42`）把「lint 零错误」钉进测试；理赔是生成式流水线 raw → `normalize_raw.py` → `compile_wiki.py` → 36 页，再过 `wiki_claims_lint.py`（必填 `:39`、枚举 `:41-43`、`err / warn :51/:55`）。「lint L1–L11」字样仅见 `docs/log/step-r1.md:12`，`wiki_claims_lint.py` 内 grep `L[0-9]+` **无命中**。
5. **11-17 三层重构（续保）**：`wiki/log.md:5`「[2026-11-17] maintain | 知识检索域整改：为 8 条目补 summary/tags/related/category 与章节锚点，生成 index.md」。三层 = **raw sources（人写，不可变）→ wiki（LLM 维护、人审）→ schema（人 + LLM 共演进）**（`wiki/README.md:12-14`）；为何：把「一个通用助手」约束成「守规矩的 wiki 维护者」（`:3`）并让约定机器可执行（`:6`）。**别混淆**：理赔域的「三层」是 `plan.md` 的内容切分「保险类型 → 任务层级 → 主题」，日志如实标注「任务层级在本子集退化」（`docs/log/step-d2-normalize.md:56`）。

### 4.4 已知限制

- `grep -rn -E 'TODO|FIXME|已知|限制|不支持' wiki/ data/llm-wiki-claims/README* server/wiki_search.py` → **0 命中**（本次实测）；以下为别处登记的限制，照抄不补。
- 词法接地「对**改写/同义查询**会误判未接地」（`reviews/knowledge.md:220`）；无稠密向量通道、`bge-m3` 未接入（`:40`、`:219`）；二元组跨词噪声「险包」「换车」（`:222`）。
- 理赔第三层主题「是『按字段聚类』，不是语义主题发现」，证据薄的主题只许页内标注、不得改 `plan.md`（`docs/log/step-d2-normalize.md:151`）。
- 主文件 §0.4 写 `wiki/`「12 个 md」，本次 `ls wiki/` 实测 **11 个**；本文不替任何一方改，只登记。
- 「为什么不用向量」的显式否决句、理赔 lint 的 L1–L11 编号：**未找到证据**（§4.1、§4.3 第 4 步）。

### 4.5 验证

```text
$ date '+%F %T' && .venv/bin/python -m pytest tests/ -k wiki -q 2>&1 | tail -3
2026-11-24 11:53:43
............                                                             [100%]
```

`tail -3` 实际只返回上面 2 行（本次实测，原样贴）：12 个点 = `tests/test_wiki_retrieval.py` 的 12 个 `test_`（`:42-135`），无 F / E 字符；**没有 `N passed` 汇总行**——`-q` 叠加吞掉 pytest 汇总行，与主文件 §8.1 登记的现象一致，按任务书只跑这一次、不换参数重跑。`tests/ -k wiki` 不收集 `claims/tests/`，理赔侧用例本次未跑。
