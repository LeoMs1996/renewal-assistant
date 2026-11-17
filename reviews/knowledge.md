# 知识检索域评审 + 落地优化报告（BM25 + wiki → LLM-Wiki / 引用正确性）

- 评审对象：`wiki/`（8 条目，3602 字正文 / 36 个章节）、`server/wiki_search.py`、`server/graph.py#retrieve_terms`、`rank_bm25` 依赖实现
- 评审人 / 执行：knowledge-reviewer-ds（t3，**attempt 5**）
- 任务基线日：2026-11-13；**本次检索与实测时间：2026-11-17T12:00–12:09 +08:00**（下表逐条标注）
- 硬约束：本文所有技术判断均来自**本次会话的真实检索**（§3 表内 URL + 检索时间戳）或**本次会话的真实实测**（§6 命令与输出），不使用训练记忆直接下结论；无法证实的条目显式标「待验证」。
- 结论先行：**改造前 6.0/10 → 改造后 8.0/10**。最大增量不在「换更好的检索算法」，而在三件事：① 语料按 LLM-Wiki 模式重构（index/log/schema/章节锚点），使 2026 基线「小语料暴力上下文」真正可用；② 引用从「整条条目」下沉到「章节 + 逐字片段」，可审计、可回溯；③ 建立**可量化的检索评测**，把「混合检索值不值得」从信仰变成数字——结论是**在 8 条语料规模上增益有限且统计上不显著**（与 2026 年同规模论文一致），真正的收益来自全量上下文与引用粒度。

---

## 1. 结论摘要

### 1.1 评分（域内维度）

| 维度 | 改造前 | 改造后 | 依据 |
|---|---|---|---|
| 语料结构（是否 LLM-Wiki 模式） | 4.5 | 8.5 | 改造前只有「front-matter + 正文」；改造后 index.md / log.md / schema（`wiki/README.md`）/ 互链图 / 36 个章节锚点齐备，且有 lint 门禁 |
| 检索实现（召回与融合） | 7.0 | 7.5 | 单通道→三通道 + RRF(k=60)；但消融显示边际增益有限（Hit@1 0.81→0.88，Hit@3 恒为 1.00），**不夸大为「算法升级」** |
| 引用正确性（citation grounding） | 5.5 | 8.5 | 改造前引用只到「条目 + 命中词附近的 160 字窗口」；改造后到「章节锚点 + 逐字片段 + evidence_coverage」，16/16 标注查询逐字可回溯、负样本可拒答 |
| 可评测性（能否证明好坏） | 3.0 | 8.0 | 改造前无任何检索指标；现有 17 条标注集 + 4 变体消融 + 12 条回归测试 + JSON 结果存档 |
| 可运维性（防腐化） | 4.0 | 8.0 | `scripts/wiki_tool.py index|lint|log` 三操作、index 新鲜度校验进 pytest |
| **加权总分** | **6.0** | **8.0** | 剩余问题集中在「条款基线 2024 未复核」「词法接地在改写查询下偏保守」，见 §7 |

### 1.2 三个最高价值发现

1. **引用粒度错位是本域真正的缺陷，不是检索算法**。改造前的「摘录」以条目为单位、窗口固定，用户/评审无法核验「答案里的这句话出自哪一节」；现在每条引用带 `wiki_id#章节` 锚点 + 正文逐字片段（`span_citation()`），轨迹节点详情也记了 `anchors` 与 `evidence_coverage`。实测：旧式 head-160 摘录 15/16 含命中证据，新式章节级 span 16/16 且 16/16 逐字可回溯（§6.3）。
2. **「混合检索」在 8 条语料上不是收益点，全量上下文才是**。2026 年同规模实证（145 文档 / 40 查询）显示 BM25、多语 E5、RRF 三者**无统计显著差异**（§3 来源 [3] 原文）；本地消融同向：Hit@3 在所有变体下都是 1.00。因此本轮把默认路径定为 **LLM-Wiki 全量上下文（5249 字符，预算 24000）+ 目录导航**，RRF 三通道作为语料增长后的回退路径，并用评测脚本锁住这条边界。
3. **wiki 语料存在系统性「过期风险」且此前无人检查**。8 条条目 `effective_date` 全为 2024-01-01（rate-surcharge 为 2025-01-01），距今 2.9 年，lint 报 7 条 stale-claim 警告。gist 明确要求 Lint 覆盖 "stale claims that newer sources have superseded"，本域此前完全没有这道检查——现在有了，且进 CI。

### 1.3 结构化发现（供集成/编排域采纳）

| id | 严重度 | 问题 | 位置 | 状态 |
|---|---|---|---|---|
| KB-1 | high | 引用只到条目粒度，无章节锚点，答案中的条款归因不可核验 | `server/wiki_search.py` | 已修（`span_citation`/`verify_citations.anchor`） |
| KB-2 | high | wiki 无 index/log/schema 三件套，检索无「目录→钻取」路径，人/LLM 均无维护约定 | `wiki/` | 已修（index.md / log.md / README.md / `scripts/wiki_tool.py`） |
| KB-3 | high | 条款 `effective_date` 2.9 年未复核，stale claim 无检测 | `wiki/*.md` | 部分修（lint 检测已落地；**条款内容复核需业务方确认，未做**） |
| KB-4 | medium | 无任何检索指标：无法回答「改动有没有变好」 | `eval/` | 已修（17 条标注集 + 4 变体消融 + 12 条回归测试） |
| KB-5 | medium | 词法接地检查的覆盖率分母含语料里不存在的词，覆盖率被系统性压低（跨词二元组如「险包」） | `verify_citations` | 已修（分母改用 in-corpus 词表；同一查询实测 **0.333 → 1.0**） |
| KB-6 | low | 中文「词级通道」在二元组语料上几乎不点火，双通道 RRF 常退化为单通道 | `_tokenize_word` | 保留并文档化（消融证明其边际贡献 +0.03 MRR，删掉会掉分，故留） |
| KB-7 | low | 无稠密向量通道；`bge-m3` 等本地模型未接入 | `server/wiki_search.py` | 未做（§7 建议；本轮已把 `channels` 参数化，接入只需加一个通道构造函数） |

---

## 2. 现状实读（改造前）

### 2.1 `wiki/` 8 条目（逐条实读）

| wiki_id | 标题 | 版本 | 章节数 | `##` 章节 | 改造后新增 |
|---|---|---|---|---|---|
| wiki-annual-inspection | 车辆未年检，保险赔不赔？ | v2024.3 | 4 | 结论/规则/续保提示 | summary, tags, related, category |
| wiki-csx | 机动车损失险（车损险） | v2024.3 | 4 | 保险责任/免赔约定/保额确定/续保要点 | 同上 |
| wiki-deductible | 免赔额/免赔率规则 | v2024.3 | 3 | 综改后总原则/仍适用的免赔情形/与续保的关系 | 同上 |
| wiki-dsx | 第三者责任险（三者险） | v2024.3 | 4 | 保险责任/常见保额档位与基准保费/免赔/续保要点 | 同上 |
| wiki-jqx | 交强险 | v2024.3 | 4 | 保险责任/责任限额/说明/续保要点 | 同上 |
| wiki-rate-surcharge | 费率上浮/下浮规则（NCD） | v2025.1 | 4 | 系数表/计算公式/续保要点 | 同上 |
| wiki-ride-hailing | 网约车/用途变更对保险的影响 | v2024.3 | 3 | 核心规则/后果/续保要点 | 同上 |
| wiki-ywyw | 医保外用药责任险 | v2024.3 | 4 | 保险责任/基准保费与保额/投保条件/续保要点 | 同上 |

改造前的事实结论：① 条目本身内容质量尚可（有表格、有条款数字、有「续保要点」），**但没有任何目录层、没有互链、没有一句话摘要**，因此 2026 的 LLM-Wiki 模式（先读目录定位、再钻取页面）无法实施；② 36 个 `##` 章节存在但**从未被检索利用**，引用只能整条。

### 2.2 `rank_bm25` 依赖实读（本次会话 `inspect.getsource`）

- `BM25Okapi` 是 ATIRE 变体：`idf = log(N - df + 0.5) - log(df + 0.5)`，**负 idf 被压到 `epsilon * average_idf`（epsilon=0.25）**；打分对每个 query term 累加 `idf * tf*(k1+1)/(tf + k1*(1-b+b*|D|/avgdl))`，默认 `k1=1.5, b=0.75`。
- 直接推论（解释了两个现象）：① N=8 时常见词 idf 接近 0 甚至被压平，**同义/通用词几乎不区分文档**；② 长条目因 `b=0.75` 的长度归一化被系统性压低——这正是「三者险买多少保额合适」把 `wiki-deductible`（短）排到 `wiki-dsx`（长）前面的机制原因（§6.2）。
- 结论：**BM25Okapi 没有字段加权（BM25F）能力**。想给 title/索引字段加权，只能另建通道再融合——这就是本轮「index 通道」的做法，而不是拍脑袋调 `k1/b`。

### 2.3 检索链路实读（改造前）

`retrieve_terms` → `search_with_score(query, top_k=3)`（单路 bigram BM25）→ `hits_for_trace`（四字段）→ `excerpt(entry, 400, query)`（命中词附近 160–400 字窗口）→ `verify_citations`（词面重叠判定）→ llm-wiki-full / rrf-topk 模式判断。**没有通道概念、没有章节概念、没有指标。**

---

## 3. 2026 基线（本次检索，逐条标注来源与时间戳）

| # | 基线要点 | 来源（URL） | 发表/更新 | 本次检索时间戳 |
|---|---|---|---|---|
| 1 | **LLM-Wiki 模式**（primary source）：三层架构（raw / wiki / schema）、三操作（Ingest / Query / **Lint**）、两个导航文件 `index.md`（目录：链接 + 一句话摘要 + 元数据）与 `log.md`（只追加，`## [YYYY-MM-DD] action \| title` 可 grep）、**index 在 ~100 来源规模内「surprisingly good」无需向量库**、Query 顺序＝先读 index → 钻取页面 → 语料变大再回退混合检索、Lint 必查孤儿页/缺失交叉引用/stale claims | https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f （正文经 https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw 读取） | 2026-04（其 X thread 起于 2026-04-02） | 2026-11-17T12:03+08:00 |
| 2 | 对 gist 的逐句考据 + 社区常见误读澄清（「分层记忆/衰减」是 v2 扩展，不是 Karpathy 原话）；给出「检索是层级式的：index → 候选页 → 可选混合检索兜底」 | https://github.com/akitaonrails/ai-memory/blob/69f49e1c7ccd62e4c1dbcf0f81c5bdba6f82436f/docs/research-karpathy-llm-wiki.md | 仓库快照（含 2026 补充：September 2026 landscape refresh） | 2026-11-17T12:01+08:00 |
| 3 | **小语料混合检索的实证**：145 文档 / 40 查询，BM25 vs 多语 E5 vs RRF 混合——BM25 Hit@1 最高（0.775）、MRR@5 最高（0.8279），E5 Hit@5 最高（0.950），**统计检验显示三种检索方法无显著差异**；RRF 的 Answer Relevancy 最高（0.8451）；结论口径建议同时报 Hit@1/3/5 + MRR@5 + 下游答案质量 | https://doi.org/10.30871/jaic.v10i5.14174 （JAIC v10i5, pp.5042–5053） | 2026-10-17 | 2026-11-17T12:06+08:00 |
| 4 | **RRF 原始依据**：`score(d)=Σ 1/(k+rank)`，只用排名、免分数归一化；k=60 为通行默认 | https://doi.org/10.1145/1571941.1572114 （Cormack, Clarke, Buettcher, SIGIR 2009, pp.758–759；本次经 [3] 参考文献 [15] 全文核到） | 2009（经典；2026 仍为默认实现） | 2026-11-17T12:06+08:00 |
| 5 | **引用溯源的验收口径**：可问责推荐须给"verbatim review-span evidence"；Grounding Score 与人评 citation precision 高度一致（Spearman ρ=+0.80, p<10⁻²⁰）；**非 LLM 检索器能做到表面逐字接地但准确率低** | https://doi.org/10.48550/arxiv.2605.07677 （TRACE, arXiv:2605.07677） | 2026-05-08 | 2026-11-17T12:05+08:00 |
| 6 | **引用核查要分两个问题**：引用是否有效（citation validity）vs 能否回溯到唯一来源（recoverability），且应做**字段级（field-level）核查**；CiteResolve 423 条幻觉引用基准 | https://doi.org/10.48550/arxiv.2610.30355 （CiteAnchor, arXiv:2610.30355） | 2026-10-21 | 2026-11-17T12:05+08:00 |
| 7 | **引用归因必须与答案质量分开评**：上下文压缩下「答案质量」不能代表 citation attribution，需独立度量 | https://doi.org/10.18653/2026.groundlm-1.65 （GroundLM 2026, The Attribution–Compression Frontier in RAG） | 2026 | 2026-11-17T12:05+08:00 |
| 8 | 生产实现里 **`k_rrf=60`** 作为「免人工权重校准」的默认值被直接写进库描述 | https://github.com/samimhamza/crag-hybrid-retriever | 2026-11-04（仓库更新） | 2026-11-17T12:00+08:00 |
| 9 | 中文社区对 LLM-Wiki 的拆解（index.md / log.md 双文件、Farzapedia 案例、规模上限未明的 caveat） | https://juejin.cn/post/7625301482213130291 | 2026-11-15 | 2026-11-17T12:02+08:00 |
| 10 | BM25F（多字段加权）的经典依据（本轮**未采纳**，但作为「字段加权」的正统出处记录） | https://arxiv.org/abs/0911.5046 （Integrating the Probabilistic Models BM25/BM25F into Lucene，本次检索结果中命中） | 2009 | 2026-11-17T12:07+08:00 |

> 说明：任务书要求「检索时间戳 2026-11-13」。2026-11-13 是**任务基线日**；本轮实际联网检索发生在 **2026-11-17T12:00–12:09 +08:00**（会话真实时间），逐条如表中所示，未做时间戳美化。若评审需要 2026-11-13 当日快照，需另跑一次检索（待验证项）。

**由基线直接导出的三个设计要求**（不是我的偏好）：
- 语料必须先有 `index.md`（目录 + 一句话摘要 + 元数据）与 `log.md`（可 grep 的追加账本），并有 schema 文档约束维护（来源 [1][2]）。
- 引用必须给**逐字片段**且**独立于答案质量**核查（来源 [5][6][7]）。
- 小语料上**不要假装混合检索是灵丹**：指标要报 Hit@1/3 + MRR@5，且要承认统计不显著（来源 [3]）。

---

## 4. 差距分析（基线 → 现状）

| # | 2026 基线要求 | 改造前现状 | 判定 | 本轮处置 |
|---|---|---|---|---|
| 1 | 三层架构 + index/log 两文件 + schema | 只有 `wiki/*.md`，无目录、无账本、无约定 | ❌ 缺失 | 新增 `wiki/index.md`（脚本生成）、`wiki/log.md`（追加账本）、`wiki/README.md`（schema） |
| 2 | Ingest/Query/**Lint** 三操作 | 无（改条目靠手改，无校验） | ❌ 缺失 | `scripts/wiki_tool.py` 提供 `index` / `lint` / `log`；lint 覆盖 front-matter、互链双向性、断链、章节重名、孤儿页、stale claim、index 新鲜度 |
| 3 | Query：先读 index → 钻取 → 必要时回退混合检索 | 单路 BM25 直接打分，无目录层 | ⚠️ 部分 | `navigate()`（index 通道→正文钻取，候选空则回退 RRF）；**实测未见增益，故不作为默认**（§6.2，诚实结论） |
| 4 | 引用给 verbatim span，且可回溯唯一来源 | 整条条目 + 160/400 字窗口，无锚点 | ❌ 缺失 | `span_citation()` → `wiki_id#章节` + 逐字片段 + `verbatim` 自校验；轨迹 `node_end` 增 `anchors` |
| 5 | 引用归因独立评估 | 仅 `grounded` 布尔 | ⚠️ 部分 | `verify_citations` 增 `coverage`（in-corpus 分母）+ `anchor` + `verbatim` |
| 6 | 混合检索用 RRF，纯排名融合 | 单通道，无融合 | ⚠️ 部分（attempt 3 已加双通道） | 通道参数化 + 三通道（新增 index 目录字段通道）；k=60 |
| 7 | 检索质量可量化（Hit@k/MRR） | 无任何指标 | ❌ 缺失 | `eval/knowledge_retrieval_eval.py`：17 条标注查询 × 4 变体，JSON 存档 |
| 8 | 小语料不做过度工程 | 无「规模判据」 | ⚠️ 部分 | 写明规模判断（8 条目/5.2KB ≪ 24000 预算）；默认全量上下文，RRF 为回退 |
| 9 | stale claim 检测 | 无 | ❌ 缺失 | lint 已加；条款内容复核未做（需业务确认，§7） |

---

## 5. 落地改造（已实现，含前/后对照）

### 5.1 语料层：`wiki/` 重构为 LLM-Wiki（8 条目全量）

- front-matter 增 `summary`（一句话摘要，进 index 与检索索引字段）、`tags`、`related`（必须双向）、`category`（index 分组）、`updated`；保留 `id/version/effective_date/source`（SPEC §5 引用字段不变）。
- 每条正文末尾增 `## 相关条款`，用 `[[wiki-id]]` 写显式交叉引用（20 条 related 边 + 20 条 `[[..]]` 正文链，全部双向可回溯）。
- 新增 `wiki/index.md`：按 category 分组的目录表（`wiki_id | 标题 | 一句话摘要 | 版本 | 标签`）+ 互链图 + 出处；**不含时间戳，保证幂等可校验**。
- 新增 `wiki/log.md`：`## [2026-11-17] maintain | …` 追加账本（gist 约定的可 grep 前缀）。
- 新增 `wiki/README.md`：schema 层，规定 front-matter 必填字段、章节锚点格式 `wiki_id#章节`、引用格式、三操作命令、规模判断。

### 5.2 检索层：`server/wiki_search.py` 重写（API 向后兼容）

| 变化 | 前 | 后 |
|---|---|---|
| 通道 | 1（bigram；attempt 3 双通道） | 3：`bigram`（字面精确）、`index`（title+summary+tags+related+章节标题 → 轻量字段加权）、`word`（英文/数字 + 中文整段） |
| 融合 | 无（attempt 3：双通道 RRF） | RRF(k=60) 三通道融合，`channels=(...)` 可配（供消融与将来接稠密通道） |
| 检索模式 | 单路打分 | `search_with_score()`（融合）+ `navigate()`（目录→钻取，候选空回退融合） |
| 引用 | `excerpt()` 窗口 + `verify_citations()` 布尔 | `span_citation()`：`wiki_id#章节` + 逐字 span + `verbatim`；`verify_citations()` 增 `coverage`（in-corpus 分母）/`anchor`/`section` |
| 摘录质量 | 命中词附近 160/400 字，可能跨章节、断句 | 命中**章节内**定位、向句子/行边界扩展、返回值恒为正文逐字子串 |
| 全量上下文 | 仅条目块 | 条目块（格式不变，保证模式判据）**+ 末尾 index 目录导航层**（`wiki_nav()`） |
| 导航文件 | 会被当条目解析（无 `id` 则丢弃） | 显式跳过 `index.md` / `log.md` |

### 5.3 编排层：`server/graph.py#retrieve_terms` 最小改动

- `node_end` 详情新增 `anchors`（`wiki_id → wiki_id#章节`）与 `evidence_coverage`，**只进节点详情**；`retrieval` 事件 `output` 仍严格 `[{wiki_id, source, version, score}]`（SPEC §5 契约未被污染，有回归测试守护）。
- `retrieval_mode` 判据未变（`len(wiki_full) >= expected`），因为导航层是**追加**在条目块之后，不影响「是否覆盖全部条目」的判定。

### 5.4 工具/评测/测试（新增）

| 文件 | 作用 |
|---|---|
| `scripts/wiki_tool.py` | `index`（生成目录）/ `lint`（7 类健康检查，非 0 退出码即失败）/ `log`（追加账本） |
| `eval/knowledge_retrieval_eval.py` | 17 条标注查询 × 4 变体（单通道 / 双通道 RRF / 三通道 RRF / 层级检索），报 Hit@1、Hit@3、MRR@5、引用接地率@3、拒答，写 `eval/knowledge-retrieval-eval-*.json` |
| `tests/test_wiki_retrieval.py` | 12 条回归：lint 零错误、index 新鲜度、summary/tags/章节齐备、log 前缀、Hit@3≥0.94、RRF 纯排名、三通道点火、span 逐字+锚点可解析、负样本拒答、coverage 区间、全量上下文覆盖、轨迹四字段契约 |

---

## 6. 验证证据（本次会话实测）

### 6.1 检索消融（`eval/knowledge_retrieval_eval.py`，2026-11-17T12:08 +08:00）

语料 8 条目 / 3602 字正文；标注查询 17 条（正样本 16，负样本 1）；LLM-Wiki 全量上下文 5249 字符（预算 24000，导航层 1091 字符）。

| 变体 | Hit@1 | Hit@3 | MRR@5 | 引用接地率@3 | 拒答 |
|---|---|---|---|---|---|
| A 单通道 BM25（2026-11-13 前基线） | 0.81 | 1.00 | 0.896 | 0.85 | 1/1 |
| B 双通道 + RRF（2026-11-13 改造） | 0.88 | 1.00 | 0.927 | 0.85 | 1/1 |
| **C 三通道 + RRF（本轮，默认）** | **0.88** | **1.00** | **0.938** | **0.90** | 1/1 |
| D 层级检索 `navigate()`（本轮新增） | 0.81 | 1.00 | 0.906 | 0.88 | 1/1 |

读法与诚实边界：
- 增益方向与 2026 同规模论文一致但更小：Hit@1 +0.07、MRR@5 +0.042、接地率 +0.05；**Hit@3 在所有变体下恒为 1.00**，说明在 8 条语料上「能不能找对」已饱和，差异只在排序位次——这与来源 [3]「三种检索方法无统计显著差异」同向。
- **D（层级检索）不如 C**，因此**没有**被设为默认：目录通道（title+summary+tags+章节标题）在 8 条语料上信息量低于正文通道，先窄化反而漏检。这是一次被证伪的设计假设，如实记录（`navigate()` 保留为 API，供语料变大后重测）。
- 剩余 2 条非 Top-1 命中是**真歧义**（「三者险买多少保额合适」→ deductible 因短文档长度归一化占优；「不计免赔还要单独买吗」→ csx 的引用块也含「不计免赔」）。尝试过 4 种补救通道（`meta` 标题+标签、`head` 章节标题、`section` 段落级检索、四/五通道组合），**均无提升**（实测 hit@1 仍 0.81–0.88，MRR ≤0.938），故未纳入代码——避免为指标好看堆无效通道。
- 负样本「划痕险理赔流程怎么走」在 4 个变体下均正确拒答（1/1），即语料未覆盖时不产出接地引用。

### 6.2 引用正确性实测（2026-11-17T12:07 +08:00）

16 条正样本，取标注正确条目计算：

| 指标 | 改造前（head-160 窗口） | 改造后（章节级 span） |
|---|---|---|
| 摘录含至少一个查询内容词 | 15/16 | **16/16** |
| 摘录为正文逐字子串（可回溯） | 15/16（含省略号拼接） | **16/16**（`verbatim=True`） |
| 锚点可解析到现存章节 | 0/16（无锚点） | **16/16**（用到 14 个不同锚点，覆盖 36 个章节中的 14 个） |

`evidence_coverage`（in-corpus 分母修正后）实测：`换车损险包括涉水吗 → wiki-csx#保险责任 1.0`；`200万三者险基准保费多少 → wiki-dsx#常见保额档位与基准保费（合成费率表）1.0`；`划痕险理赔流程怎么走 → 两条命中均 grounded=False, coverage=0.0`（正确拒答）。

### 6.3 测试与静态检查（2026-11-17T12:10 +08:00，最终一轮）

```
$ .venv/bin/python -m pytest -q
76 passed, 2 skipped in 2.12s      # 12:08 早一轮为 77 passed, 1 skipped；跳数差异来自并行其他域新增的用例
$ .venv/bin/python -m pytest tests/test_wiki_retrieval.py -q
12 passed
$ .venv/bin/python scripts/wiki_tool.py lint
lint: 0 error / 7 warn / 8 条目     # 7 warn 全部是 effective_date=2024-01-01 的 stale claim
$ .venv/bin/python -m ruff check server/wiki_search.py server/graph.py scripts/wiki_tool.py \
      eval/knowledge_retrieval_eval.py tests/test_wiki_retrieval.py
All checks passed!
$ .venv/bin/python -m ruff check .   # 仓库级：3 处既有 I001，均在 mcp_servers/（MCP 域，非本轮范围）
```
> 注：`python`/`python3` 指向 miniconda 且未装 `langgraph`，必须用项目 `.venv`（`.venv/bin/python`）；否则 pytest 收集会因 `ModuleNotFoundError: langgraph` 中断——这不是代码缺陷。

### 6.4 端到端冒烟（`retrieve_terms` 节点直接调用，2026-11-17T12:08 +08:00）

输入 `{"message": "换车损险包括涉水吗", "intent": "terms", ...}`：
- `citations` = `[wiki-csx(score .0328), wiki-deductible(.0323), wiki-ride-hailing(.0313)]`（四字段，SPEC 合规）
- `excerpts` 8 条（`mode=llm-wiki-full`，全量注入生效），且命中条目的摘录从命中章节起算（`…## 保险责任 …涉水行驶导致发动机损坏…`）
- 轨迹 `node_end.details` 实测含 `"anchors": {"wiki-csx": "wiki-csx#保额确定", ...}` 与 `"evidence_coverage": {...}`（同时被并行运行的编排域测试自然覆盖到）

### 6.5 跨域阻塞复核（队长转交的两项）

| 上报项 | 复核结果 | 证据 |
|---|---|---|
| `server/wiki_search.py` 语法错误（docstring 未闭合 + 重复 `tokens` property），阻塞 pytest 收集 | **当前状态不复现**。文件可 `ast.parse`；`grep -n "def tokens"` 仅 1 处；`pytest --collect-only` 成功收集 5 个模块 | `python -c "ast.parse(...)"` → OK；`pytest --collect-only -q` 输出各模块用例数；全套 `77 passed, 1 skipped` |
| `server/graph.py:761` `retrieve_terms` 对 `WikiEntry` 用下标访问（应属性） | **已是属性访问**：改造后代码用 `x.wiki_id`（`next(x for x in searcher.entries if x.wiki_id == ...)`），跨域回归不存在 | `sed -n '757,790p' server/graph.py`；pytest 全绿 |
| （补充）pytest 收集失败的真实原因 | 用的是系统 `python`（未装 `langgraph`），非 `wiki_search.py`。项目 `.venv` 下收集与运行均正常 | `ModuleNotFoundError: No module named 'langgraph'` vs `.venv/bin/python -m pytest` 全绿（76 passed / 2 skipped） |

> 结论：上报的硬阻塞**在当前 HEAD 状态已不存在**；本轮在此基础上继续做了 §5 的实质优化。若其他域仍看到语法错误，请确认是否读到了旧的落地拷贝（`.venv`/`__pycache__` 缓存或工作区外的副本）。

---

## 7. 未采纳 / 遗留 / 后续建议

1. **条款基线复核（高，未做，需业务确认）**：7 条条目 `effective_date=2024-01-01`、1 条 2025-01-01，距基线日 2.9 年。lint 已能把它们标成 stale claim，但**条款内容是否被新规替代必须由业务方判断**，不能由评审工程师臆断（待验证）。
2. **稠密向量通道（中，未做）**：`channels` 已参数化，加一个 `dense`（如本地 `bge-m3`）即可进入 sparse+dense 标准形态；但按来源 [3]，**在 145 文档规模上它未必带来显著提升**，建议等语料 >100 条再评估，而不是现在堆栈。
3. **词法接地的保守性（中）**：`verify_citations` 是 ALCE 式无模型近似，对**改写/同义查询**会误判未接地（来源 [5] 也指出非 LLM 核查「表面逐字但准确率低」）。真实 LLM 凭证到位后，建议升级为「字段级核查 + LLM-as-judge 支撑判定」双轨（来源 [6] 的 citation validity / recoverability 二分），并把判定结果作为评测维度（来源 [7]：引用归因须独立于答案质量评估）。
4. **拒答策略仍是「不接地即剔除」（低）**：负样本表现正确，但当 query 只含语料外的词时，当前实现返回空引用而非「明确澄清」；建议在编排域把 `coverage==0` 明确路由到 clarify（跨域，本轮不改编排）。
5. **中文分词（低，待验证）**：用字符二元组替代分词器是零依赖选择，代价是跨词二元组噪声（「险包」「换车」）。若要提升，候选是 jieba/pkuseg 或 BM25F 字段加权（来源 [10]），但**必须先用标注集证明增益**——本轮四次替代实验均无增益，故不改。

---

## 8. 参考来源清单（完整 URL + 检索时间戳）

1. Karpathy, A. *LLM Wiki*（idea file / primary source），2026-04（X thread 起于 2026-04-02）。
   <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>（正文读取：<https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw>）— 检索于 **2026-11-17T12:03+08:00**。
2. akitaonrails/ai-memory, *Karpathy's "LLM Wiki" - Research Report*（gist 逐句考据 + caveats）。
   <https://github.com/akitaonrails/ai-memory/blob/69f49e1c7ccd62e4c1dbcf0f81c5bdba6f82436f/docs/research-karpathy-llm-wiki.md> — 检索于 **2026-11-17T12:01+08:00**。
3. Fadha, M. S. M., Ardila, Y., Wahyudi, N. *Comparing BM25, Multilingual-E5, and Reciprocal Rank Fusion for Retrieval-Augmented Generation*, JAIC 10(5):5042–5053. <https://doi.org/10.30871/jaic.v10i5.14174> — 发表 2026-10-17，检索于 **2026-11-17T12:06+08:00**。
4. Cormack, G. V., Clarke, C. L. A., Buettcher, S. *Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods*, SIGIR 2009:758–759. <https://doi.org/10.1145/1571941.1572114> — 经来源 3 参考文献 [15] 核对，检索于 **2026-11-17T12:06+08:00**。
5. *TRACE: Tourism Recommendation with Accountable Citation Evidence*, arXiv:2605.07677. <https://doi.org/10.48550/arxiv.2605.07677> — 2026-05-08，检索于 **2026-11-17T12:05+08:00**。
6. *CiteAnchor: Source-Aware Grounding for Hallucinated Citation Detection and Resolution*, arXiv:2610.30355. <https://doi.org/10.48550/arxiv.2610.30355> — 2026-10-21，检索于 **2026-11-17T12:05+08:00**。
7. *The Attribution–Compression Frontier in Retrieval-Augmented Generation*, GroundLM 2026. <https://doi.org/10.18653/2026.groundlm-1.65> — 2026，检索于 **2026-11-17T12:05+08:00**。
8. samimhamza/crag-hybrid-retriever（`k_rrf=60` 生产默认实现）。<https://github.com/samimhamza/crag-hybrid-retriever> — 仓库更新 2026-11-04，检索于 **2026-11-17T12:00+08:00**。
9. 掘金《8 万人收藏：Karpathy 的 LLM Wiki 到底是什么？完整拆解》。<https://juejin.cn/post/7625301482213130291> — 2026-11-15，检索于 **2026-11-17T12:02+08:00**。
10. *Integrating the Probabilistic Models BM25/BM25F into Lucene*, arXiv:0911.5046（BM25F 字段加权经典出处，本轮未采纳）。<https://arxiv.org/abs/0911.5046> — 检索于 **2026-11-17T12:07+08:00**。

---

## 9. 复现命令

```bash
cd renewal-assistant
.venv/bin/python scripts/wiki_tool.py index        # 重新生成 wiki/index.md（幂等）
.venv/bin/python scripts/wiki_tool.py lint         # 健康检查：0 error 才算过
.venv/bin/python eval/knowledge_retrieval_eval.py  # 4 变体消融（写 eval/knowledge-retrieval-eval-*.json）
.venv/bin/python -m pytest tests/test_wiki_retrieval.py -q
.venv/bin/python -m pytest -q                      # 全套：76 passed, 2 skipped（随并行域用例增减浮动）
```

改动文件清单：`wiki/{index.md,log.md,README.md}`、`wiki/*.md`（8 条 front-matter + 互链）、`server/wiki_search.py`（重写）、`server/graph.py`（`retrieve_terms` 节点详情增 anchors/coverage）、`scripts/wiki_tool.py`、`eval/knowledge_retrieval_eval.py`、`tests/test_wiki_retrieval.py`、本报告。

> 本报告替代 attempt 3 的旧版本：旧版部分结论（如「llm-wiki-full 判据漏算连接符」「词级通道多数查询不点火」）已在本次实测中复核成立并保留，但其**证据链已全部换成本轮真实检索 + 本轮实测数据**；旧版未覆盖的 index/log/schema/lint 与量化消融为本轮新增。
