# step-d3 · LLM-Wiki 萃取执行（样张阶段交付日志）

> 任务：`t6`（attempt 1，`83ca011a-0a6b-42c0-a118-e7de2355442d`）｜执行：wiki-lead｜日期：2026-11-18
> **范围按船长本轮消息收窄**：只落「第 1 页 + 代表模式 + index.md/log.md 骨架 + lint」，不推 36 页；其余 33 页由 t20 承接。
> 实际落了 **3 页**（≤ 船长给的 3 页容差），原因见 §2.1：2 页才能证明 `related` 双向，3 页才能覆盖「18/36 是 section」这一主导模式。

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 职责 |
|---|---|---|
| `data/llm-wiki-claims/scripts/compile_wiki.py` | **新增**（≈22 KB） | 编译器：plan → 页面；`build --pages/--all`、`check`；持有 `wiki/.ingest.lock`；页面与 index 由输入完全决定；log 只追加 |
| `data/llm-wiki-claims/scripts/wiki_lint.py` | **新增**（≈13 KB） | lint：L1/L2/L3/L4/L5/L6/L7/L8/L10/L11，FAIL → exit 1 |
| `wiki/schema.md` | 新增 | 本语料根的 schema：9 必填 + `raw_refs`、`claim_type` 枚举、span 语法、正文约定、已知边界 |
| `wiki/index.md` | 新增 | 3 行（每页一行：链接/标题/类型/摘要/tags/updated）+ 4 条口径说明（含 `task_layer` 退化声明） |
| `wiki/log.md` | 新增 | 3 条 `## [2026-11-18] ingest \| <page_id>`，各带 `page/units/qids/result/lint` 五行，可 grep |
| `wiki/docs/ins-mmbench-agricultural.md` | 新增（页 1） | 抽样层登记页：12 条 agri 样本清单 + 字段齐全度 + 题干规约逐字 + 层级说明 + **图片重取前提** |
| `wiki/sections/agri-insured-subject.md` | 新增（页 2） | 章节页（18/36 的主导模式）：`species`/`count` 逐行事实 + 逐字规约 + 派生分布 |
| `wiki/faqs/agri.md` | 新增（页 3） | 问答页：只回答「本子集能支持到什么程度」，含「本页不回答什么」 |
| `docs/log/step-d3-compile.md` | 新增 | 本日志 |

**没碰**：`raw/**`（只读）、`wiki/`（续保，保护对象）、`server/`、`tests/`、`mcp_servers/`、`SPEC.md`、`traces/`、`claims/`、`plan.md`、`.env`。

---

## 2. 关键决策与依据

### 2.1 为什么是 3 页而不是 1 页（对船长收窄的执行说明）

| 页 | 作用 | 不做的风险 |
|---|---|---|
| `claims-doc-ins-mmbench-agricultural` | plan §4 的**第 1 页**，覆盖「doc 模式 + 12 条 source_refs + 图片前提 + 层级说明」 | 船长点名的第 1 页 |
| `claims-section-agri-insured-subject` | **18/36 页是 section**，格式错在这里会错 18 次 | 若只交 doc 页，最主导的模式没被评审 |
| `claims-faq-agri` | 与 doc 页构成 **双向 `related`** | 只交 1 页时 `related` 为空，L3「双向」规则无法被验证 |

三页同属 `agri` 分片，互连语义成立（总览 ↔ 章节 / 总览 ↔ 问答）。**未超船长给的 3 页阈值**，且没有触及第 4 页。

### 2.2 本步检索记录（2026-11-18）

| # | 来源 | URL | 检索时间 | 类型 | 支撑的决策 |
|---|---|---|---|---|---|
| D3-S1 | Karpathy《LLM Wiki》gist 原文 raw | https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw | 2026-11-18（14:15 批次，本步复核） | 一手 · 方法论 | ①「查答案先读 index、再下钻页面」→ 页面正文按「规约→事实表→聚合」组织，index 行必须有摘要；②log 前缀 `## [YYYY-MM-DD] <op> \| <title>` + `grep "^## \["` → 日志格式；③「一次处理一个来源」→ 编译顺序沿用 `ingest_order`；④raw 不可变 → 编译器只读 `raw/` |
| D3-S2 | `chenhz01/memory-wiki` README | https://github.com/chenhz01/memory-wiki | 2026-11-18（14:1x 批次，本步复核） | 社区 · 独立实现 | ①`lint` 以 **exit 1** 表达 FAIL → `wiki_lint.py` 用退出码做门禁；②ingest「never overwrites without `--force`」→ 编译器对不一致产物重写前先持锁、并在 `check` 里报「非幂等/被手改」；③index 一行一条 → index 列设计 |
| D3-S3 | `nashsu/llm_wiki` README | https://raw.githubusercontent.com/nashsu/llm_wiki/main/README.md | 2026-11-18（本步抓取） | 社区 · 生产实现 | ①**两步式 ingest**（先分析、再生成）→ 编译器分两段：先按 unit 收集证据 → 再渲染页面；②每页 YAML frontmatter → 强制 9 字段；③`sources[]` 溯源 → `source_refs`/`raw_refs` 双形式；④**serial ingest queue** → `.ingest.lock` 单写者 |

> 复用与新增说明：D3-S1/S2 是本步复核（R1/R2/D2 已引），D3-S3 为本步新抓。三条互相独立（原始方法论 / 独立实现 / 生产实现），且都直接约束了「引用粒度、日志、锁、frontmatter」这四项决策。

### 2.3 决策：每页如何做到「不得生成无来源断言」

正文只允许两类内容，**没有第三类**：

1. **逐字引用块**：`> ` 开头，紧跟 `⟦S:INS-MMBench:qid=<qid>@L<a>-L<b>⟧`；lint 会把 `> ` 后的文本与 raw 该行区间**逐字比对**（忽略行尾空白）。
2. **样本事实表行**：每行末尾带字段级标记 `@labels.<key>`，一个字段一个标记。

聚合陈述（"12/12 条均具备…"）**不许裸写**：一律用区间标记 `⟦S:INS-MMBench:qids=agri_0..agri_11@labels.species⟧`，且区间集合必须 ⊆ 本页 `source_refs`（lint L6 校验超集）。这样 D4 拿到任何一句话都能反查到具体样本与字段。

### 2.4 决策：引用标识用 `INS-MMBench:qid=`，并保留 `raw_refs`

船长要求「如 `INS-MMBench:qid=...`」，R1 spec 要求 `raw_id`。两者是机械双射（`qid=<split>_<idx>` ↔ `raw_id=raw-<split>-<idx:04d>`），因此：
- frontmatter `source_refs`：**qid 形式**（船长要求、D4 核对入口）；
- frontmatter `raw_refs`：raw_id 形式（R1 spec 形式，脚本可直读）；
- 正文标记：`qid` 形式。
lint 双向校验：`source_refs` 的每个 qid 必须在 manifest 中存在（L6），`raw_refs` 必须匹配 `raw-<split>-<4位>`（L1）。

### 2.5 决策：`claim_type` 定义为理赔业务类型枚举

`claim_type ∈ {auto_claim, auto_liability, agricultural_claim, health_underwriting, property_claim, cross_cutting}`，由分片映射而来；entity 页与跨任务页取 `cross_cutting`。
**被否决**：把 `claim_type` 当作「断言类型（fact/rule/concept）」——与 `type`（doc/section/entity/faq）语义重叠，会造成两个字段互相打脸。若船长本意是后者，我按此枚举改造只需改 `CLAIM_TYPE` 一处映射并重跑。

### 2.6 决策：`related` 只在「已编译」页面之间建边，并保证双向

`attach_related()` 只在本次编译集合内连边（doc↔section/faq 同分片、section↔section 同分片），因此样张阶段不会有指向未编译页的断链；t20 编译剩余页时，重跑即自动补齐（边由集合决定，不手工维护）。
**被否决**：把 `plan.md` §4 的计划邻居直接写进 `related` → 立刻产生 L3 断链 FAIL（这正是船长担心的「整齐地错 36 次」）。

### 2.7 决策：三条硬纪律落到脚本

| 纪律 | 落地 |
|---|---|
| 一次只编译一个来源 | 编译顺序取 `manifest.ingest_order`；log 逐页记录 `units` 全列表，顺序可核对 |
| 单写者 | `wiki/.ingest.lock`；已存在则**直接失败**（不抢写），`finally` 里清理 |
| 幂等 | 产物无时间戳/随机数（`updated` 固定 `2026-11-18`）；`build` 与 `check` 共用同一渲染路径；log 只追加缺失条目 |

---

## 3. 验证证据（命令 + 真实输出）

### 3.1 船长 6 条核对项

| # | 项 | 结果 |
|---|---|---|
| 1 | frontmatter 9 必填（`id/type/title/domain/summary/tags/source_refs/updated/related` + `status`）+ `claim_type` | ✅ lint L1 全通过（缺一即 FAIL，见 §3.3-B） |
| 2 | span 级引用（不许粗引用） | ✅ 36 个 `@labels.*` + 逐字块的 `@L9-L9`/`@L13-L17`/`@L1-L17`；无「来源：raw-xxx」形态 |
| 3 | 逐字子串 | ✅ lint 把 `>` 块与 raw 行区间逐字比对；**破坏一个字符即 FAIL**（§3.3-A） |
| 4 | index 行齐全（链接/标题/类型/摘要/tags/updated） | ✅ 3 行，且摘要列 == frontmatter `summary`（L10） |
| 5 | log 可 grep（raw_id / 页 id / 事务结果） | ✅ `grep -c '^## \['` = 3；每条含 `page/units/qids/result/lint` |
| 6 | lint 0 FAIL 且可重跑 | ✅ `FAIL=0`，exit 0；连跑两次 7 个 md sha256 一致 |

### 3.2 实测输出

```text
$ python3 data/llm-wiki-claims/scripts/compile_wiki.py build --pages claims-doc-ins-mmbench-agricultural,claims-section-agri-insured-subject,claims-faq-agri
wrote wiki/docs/ins-mmbench-agricultural.md  4185 bytes
wrote wiki/faqs/agri.md  2212 bytes
wrote wiki/index.md  1551 bytes
wrote wiki/schema.md  3614 bytes
wrote wiki/sections/agri-insured-subject.md  3600 bytes
wrote wiki/log.md（append-only）
build exit=0

$ python3 data/llm-wiki-claims/scripts/wiki_lint.py
pages=3 index_rows=3 FAIL=0 WARN=0
lint exit=0

$ # 幂等：两次构建
IDEMPOTENT OK (7 个 md 文件)

$ grep -c '^## \[' data/llm-wiki-claims/wiki/log.md
3
## [2026-11-18] ingest | claims-doc-ins-mmbench-agricultural
## [2026-11-18] ingest | claims-section-agri-insured-subject
## [2026-11-18] ingest | claims-faq-agri

$ # index ↔ 磁盘
index 与磁盘一一对应

$ # source_refs → manifest 可追溯
docs/ins-mmbench-agricultural.md      refs=12 例: agri_0 → raw-agri-0000 (records_line=1)
faqs/agri.md                          refs=12 例: agri_0 → raw-agri-0000 (records_line=1)
sections/agri-insured-subject.md      refs=12 例: agri_0 → raw-agri-0000 (records_line=1)
合计 36/36 条 source_refs 可在 manifest 中解析

$ git status --short -- wiki traces server tests SPEC.md mcp_servers
（空输出）
$ git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md
（空输出）
```

### 3.3 负向控制：证明 lint 不是空转

| 注入的错误 | lint 输出 | exit |
|---|---|---|
| A. 把引用块里 `Species` 改成 `Specie` | `[L6] sections/agri-insured-subject.md :: 逐字引用块与 raw 不一致（L9-L9）` | 1 |
| B. 删掉 `claim_type:` 行 | `[L1] faqs/agri.md :: 缺少必填字段: claim_type` / `[L1] … claim_type 枚举非法: None` | 1 |
| C. 删掉 `faqs/agri.md` | `[L2] index.md :: 索引指向不存在的页面: faqs/agri.md` / `[L3] docs/… :: related 指向不存在的页面: claims-faq-agri` | 1 |
| D. 注入一条编造断言 bullet | `[L7] sections/agri-insured-subject.md :: bullet 无来源标记: - 农业保险赔付上限通常为保额的 80%…` | 1 |

四次注入后均用 `build` 复原，复原后 `FAIL=0`（§3.2 末行）。**这条最值得看**：D 项就是「编造断言」的现场拦截。

---

## 4. 遗留问题与交接

| # | 事项 | 承接方 | 说明 |
|---|---|---|---|
| 1 | 剩余 33 页（doc/section/entity/faq） | **t20** | 直接 `build --all` 即可产出（脚本已支持），但**建议按 plan §4 顺序分批**：先 agri 剩余 4 页 → claim 6 → liability 6 → health 6 → property 5 → entity 5 + doc 3 |
| 2 | 实体页（entity）正文模板尚未实现 | t20 | `BUILDERS` 目前只有 doc/section/faq；entity 页需要「跨分片概念 + 双向 related」的正文，需新增 `body_entity()`。**未实现就 `build --all` 会 KeyError**——这是有意留的显式失败，不是隐藏 bug |
| 3 | `claim_type` 语义待船长确认 | 船长 / t20 | 现按「理赔业务类型」实现（§2.5）。若本意是「fact/rule」，改 `CLAIM_TYPE` 映射一处即可 |
| 4 | 图片引用前提已写进正文 | 已做 | doc 页 §5 写明「未入库 + 需按 `FETCH.md` 重取 + `normalize_raw.py check` 复核 + sha256」 |
| 5 | `task_layer` 退化声明已三处写明 | 已做 | doc 页 §4、index.md 头部、schema.md §6 |
| 6 | lint L9（过期）/L10 预算 未实现 | t20 / D5 | L9 需要跨批次时间轴才有意义；L10 的 token 预算（index ≤3k）目前 index 仅 1.5 KB，暂不触发 |
| 7 | `updated` 固定为 2026-11-18 | 后续 | 为幂等而固定；t20 若跨天编译，需把 `UPDATED` 提为参数并同步更新已编译页（否则 L1 的 ISO 校验仍过，但「新鲜度」语义会失真） |

**交接一句话**：t20 只需 `python3 data/llm-wiki-claims/scripts/compile_wiki.py build --all`（先补 `body_entity`），随后 `python3 …/wiki_lint.py` 必须 `FAIL=0`；任何手改页面都会被 `check`/lint 判为非幂等或 L6 不一致。
