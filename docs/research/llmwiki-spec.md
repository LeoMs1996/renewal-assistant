# 理赔域 LLM-Wiki 萃取与维护规范（R1 定稿稿 v1.0）

> 状态：**可执行规范**（供 D2 抽样落盘、D3 萃取、D4 检索直接照做）。
> 建立：2026-11-18 ｜ 适用：`data/llm-wiki-claims/`（理赔域）｜ 不适用：续保 `renewal-assistant/wiki/`（保护对象，只读，见 H4/H5）。
> 本文件是 LLM-Wiki 三层架构中 **schema 层**的正式定义：它把「一个通用助手」约束成「守规矩的 wiki 维护者」[S1]。
> 落地位置：知识产物在 `data/llm-wiki-claims/wiki/`，原文证据在 `data/llm-wiki-claims/raw/`；规范与日志在 `docs/`。

---

## 1. 来源登记表（先检索后动手，H1/H2）

检索批次：**2026-11-17**（本机时间 23:0x–23:5x，单批次 MCP `read.fetch` / `search.run` 实际抓取；`search.run` 无证据的两次查询已放弃，未采信）。

| # | 来源（标题） | URL | 类型 | 检索时间 | 用于支撑的决策 |
|---|---|---|---|---|---|
| [S1] | Karpathy《LLM Wiki》idea file（gist 原文 raw） | https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw ｜页面 https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f | 一手 · 方法论原文 | 2026-11-17 | 三层架构与 raw 不可变；Ingest/Query/Lint 三操作；index.md 语义与规模经验（~100 源/数百页）；log.md 前缀格式与 grep 用法；lint 检查项清单（矛盾/过期断言/孤儿页/缺失页/缺互链）；「一个来源可能触碰 10–15 个页面」→ 并发纪律；wiki 即 git 仓库 |
| [S2] | 《8 万人收藏：Karpathy 的 LLM Wiki 到底是什么？完整拆解》 | https://juejin.cn/post/7625301482213130291 | 社区 · 中文拆解 | 2026-11-17 | index.md/log.md 各自职责的独立复述（交叉验证 S1）；目录约定 raw/assets + wiki；schema 文件写什么；前 5–10 篇为调校期；qmd 作为规模退化路径 |
| [S3] | `chenhz01/memory-wiki` README（独立实现，非 S1 作者） | https://github.com/chenhz01/memory-wiki ｜raw: https://raw.githubusercontent.com/chenhz01/memory-wiki/main/README.md | 社区 · 独立实现（含 lint 语义） | 2026-11-17 | lint 的具体检查项（孤儿未被索引、缺日期、标题重复、超长文件、相对链接断裂）；`lint` 退出码 1 → CI 门禁；log 只追加；ingest 不得静默覆盖；`last-verified` 新鲜度循环（过期知识比没有知识更危险） |
| [S4] | `tobi/qmd` README（原文点名的检索工具） | https://github.com/tobi/qmd ｜raw: https://raw.githubusercontent.com/tobi/qmd/main/README.md | 一手 · 工具官方文档 | 2026-11-17 | 规模超出 index 后的检索退化路径（BM25+向量+RRF+重排）；context 树帮助模型选文档；collection + metadata 过滤 |
| [S5] | Anthropic《How we built our multi-agent research system》 | https://www.anthropic.com/engineering/multi-agent-research-system | 一手 · 生产经验 | 2026-11-17 | 「需要共享同一上下文、agent 间依赖多的域不适合多智能体并行」→ 串行编译的依据；CitationAgent 保证 claim→source 对应；状态天然有状态、错误会累积 → 检查点；人工评审抓自动化抓不到的问题 |
| [S6] | `nashsu/llm_wiki` README（完整实现，声明忠于 S1） | https://raw.githubusercontent.com/nashsu/llm_wiki/main/README.md | 社区 · 生产级实现 | 2026-11-17 | 每页 YAML frontmatter + `sources[]` 溯源字段；**串行 ingest 队列**（显式防并发 LLM 调用）；两步式 ingest（先分析再生成）；上下文预算按比例分配（wiki 60% / 索引 5%）；review 队列用受限动作集防幻觉；`overview.md` 全局页 |
| [S7] | Anthropic《Effective context engineering for AI agents》 | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 一手 · 生产经验 | 2026-11-17 | 渐进披露（progressive disclosure）与 just-in-time 检索：先拿轻量标识符（路径/链接），运行时按需加载；context rot（token 越多召回越差）→ 必须有 L0–L3 分层与预算 |

**独立性说明**：S1 是原始方法论；S2/S3/S6 是三个互不相同的独立实现/解读（不同作者、不同站点）；S4 是工具官方文档；S5/S7 是厂商生产经验。不存在「同一站点三次」的情况。

**未采信**：两次 `search.run`（并发写入冲突、文档 lint 自动化）返回 0 条达标证据，已在 §11 登记为「待验证」，未据此写规则。

---

## 2. 目录结构与三层职责（Q1）

三层是这套方法的最小充分结构：**raw = 事实来源，wiki = 知识产物，schema = 约束** [S1]。

```text
data/llm-wiki-claims/
├── raw/                        # 事实层：不可变、只读（S1 原话：immutable，LLM 只读不改）
│   ├── imm-0001.json           # 一个来源一个文件：raw_id / source_* / span / text / license
│   ├── assets/                 # 图片落地目录（记 hash；不依赖外链）[S1][S2]
│   └── manifest.json           # 抽样清单：来源版本、seed、条数、sha256（可复现）
└── wiki/                       # 知识层：LLM 独占写，人审读
    ├── schema.md               # 规范层落地副本（本文件 §3–§10 的摘要版）
    ├── index.md                # 目录：脚本生成、幂等、禁手改（§4）
    ├── log.md                  # 追加账本：可 grep（§5）
    ├── overview.md             # 全局综述（可选；每次 ingest 后可重生）[S6]
    ├── docs/                   # type=doc      文档级页（一份材料的自述页）
    ├── sections/               # type=section  章节级页（条款/条款块）
    ├── entities/               # type=entity   实体页（险种、责任、材料、机构、指标）
    ├── faqs/                   # type=faq      高频问题页
    └── queries/                # type=query    问答沉淀页（好的回答要回写，S1）
```

**职责边界（硬性）**

| 规则 | 内容 | 依据 |
|---|---|---|
| R2.1 | `raw/` **只读**：除「新增新文件」外不得修改、重命名、覆盖既有文件；任何修正都以新增 `raw_id` 表达 | [S1]（immutable / source of truth）、[S3]（ingest 不得静默覆盖，需显式 `--force` 语义） |
| R2.2 | `wiki/` 由 LLM 维护、人只读审阅；人不得手改 `index.md`/`log.md`（脚本生成/追加） | [S1]、[S6]（human curates, LLM maintains） |
| R2.3 | 每条 wiki 断言必须能落回 `raw/` 的某个 `raw_id` + `span`；落不回去的不得写 | [S1]、[S6]（`sources[]` 溯源字段） |
| R2.4 | 与续保 `renewal-assistant/wiki/` **物理隔离**：写入续保目录 = 硬违规（H5），运行时用 `WIKI_DIR` 注入指向本目录 | 本项目约束（C0 `data/README.md`）+ [S1]（wiki 只是一个 git 目录 → 目录即边界） |
| R2.5 | 目录本身是 git 仓库工作区：可回滚、可 diff、可审计 | [S1]（wiki is just a git repo） |

---

## 3. 条目 schema（Q2）

### 3.1 YAML frontmatter

**必填 9 项**（缺一项 lint 直接 FAIL，§7）：

| 字段 | 取值约束 | 用途 | 依据 |
|---|---|---|---|
| `id` | `claims-<type>-<slug>`，全局唯一、不复用 | 引用键、index 链接、`related` 目标 | [S1][S3] |
| `type` | 枚举 `doc｜section｜entity｜faq｜query` | 分目录、分模板 | [S1]（摘要页/实体页/概念页/对照页）、[S3]（type 亲和度） |
| `title` | 中文短标题 ≤ 30 字，与文件名 slug 对应 | index 标题列 | [S3][S6] |
| `domain` | 枚举 `claims`（本期唯一值）；跨域用**数组**，主域在首位，如 `domain: [claims, policy]` | 跨域标签、检索过滤 | 本项目决策（船长要求 `domain=claims`）+ [S4]（metadata 过滤是规模化的前提） |
| `summary` | 一句话 ≤ 80 字，不得含引用标记 | index 摘要列、检索字段 | [S1]（one-line summary）、C0 `wiki/README.md` 约定 |
| `tags` | 逗号分隔 3–6 个，小写/中文均可，不造新词优先复用 | 检索、聚类 | [S1]（Dataview 可查 tags） |
| `source_refs` | `raw_id` 列表，**每个都必须真实存在**；至少 1 条 | 溯源入口 | [S6]（`sources: []`）、C0 `raw/README.md`（无 raw_id 不得入库） |
| `updated` | ISO 日期 `YYYY-MM-DD` | index Updated 列、新鲜度检查 | [S1][S3]（`last-verified`/缺日期即 lint 项） |
| `related` | 其它 `id` 列表，**必须双向** | 互链、孤儿检测 | [S1]（cross-references 已就位是核心价值）、[S3]（断链检查） |
| `status` | 枚举 `draft｜verified｜conflicted｜stale` | 冲突/过期的显式状态 | [S1]（lint 找矛盾与过期断言）、[S3]（腐烂要变成「有名字的状态」） |

**可选**：`version`、`effective_date`、`confidence: high|medium|low`、`reviewed_by`、`image_refs`（图片 ID 列表）、`supersedes`（被哪个 `raw_id` 取代）。

> 说明：原方法论里 frontmatter 是「可选增强」[S1]，本项目把它提升为**强制**——理由是下游 D4 的检索与评测需要机器可读字段（与 [S6] 的做法一致：每页 YAML frontmatter）。

### 3.2 类型模板（骨架，D3 直接套）

```markdown
<!-- type=doc：一份输入材料的自述页 -->
---
id: claims-doc-imm-0001
type: doc
title: <材料标题>
domain: claims
summary: <≤80 字：这份材料讲了什么、可用在哪>
tags: 理赔, 定损
source_refs: [imm-0001]
updated: 2026-11-18
related: [claims-entity-...]
status: draft
---
# <材料标题>
## 关键信息         ← 每条断言后带 §6 的引用标记
## 适用边界
## 相关条目
```

```markdown
<!-- type=section：条款/报告里的一个章节块（最常用） -->
id: claims-section-imm-0001-l12
type: section
title: <章节标题>
domain: claims
summary: <这一节的核心规则一句话>
tags: ...
source_refs: [imm-0001]
anchors: [{raw_id: imm-0001, span: "L12-L18"}]   ← 可选，正文标记已有则冗余可省
```

```markdown
<!-- type=entity：实体页（险种/责任/材料/指标/机构）-->
id: claims-entity-ding-sun
type: entity
title: 定损
domain: claims
summary: 定损是核定损失金额的环节，输出定损单，是赔付计算的前置。
aliases: [损失核定]          ← 消歧用：别名词不新开页
related: [claims-entity-pei-fu]
```

```markdown
<!-- type=faq：高频问题页（一问一页，答案带引用）-->
id: claims-faq-0007
type: faq
title: 事故后多久内必须报案？
domain: claims
question: 事故发生后超过 48 小时报案，保险公司还赔吗？
answer_short: <≤60 字结论>      ← 检索直出用
```

```markdown
<!-- type=query：问答沉淀页（S1：好回答回写成页）-->
id: claims-query-20261118-01
type: query
title: 人伤案件中误工费的核定依据
domain: claims
asked_at: 2026-11-18
```

### 3.3 命名与消歧

| 规则 | 内容 | 依据 |
|---|---|---|
| R3.1 | 文件名 = `id` 去掉 `claims-` 前缀 + `.md`，只允许 `[a-z0-9-]`；一个主题一页 | [S3]（slug 化、标题重复是 lint 项） |
| R3.2 | 别名不新开页，写进 `aliases`；一个词多义时**先拆页**（如「定损」vs「核损」），用满一段时间再决定是否合并 | 本项目决策（对应原方法论「一词多义先拆后合」的经验，[S1] 未展开 → 标为本项目规则） |
| R3.3 | 章节标题即引用锚点，同一文件内不得重复；引用粒度 `id#章节标题` | [S1]（页面互链/章节引用）、C0 `wiki/README.md` 锚点约定 |
| R3.4 | `domain` 只用枚举值；新域必须先改本文件再写页面（schema 先行，不允许「先写后补枚举」） | 本项目决策 |

---

## 4. index.md 规范与 token 预算（Q3）

### 4.1 行格式（每页一行）

```markdown
## <分类：按 type 分组>

| wiki_id | 标题 | 类型 | 一句话摘要 | tags | updated |
|---|---|---|---|---|---|
| [`claims-section-imm-0001-l12`](sections/imm-0001-l12.md) | 免赔率约定 | section | 全车盗抢绝对免赔 20%，约定区域外出险加扣 10%。 | 免赔, 盗抢 | 2026-11-18 |
```

- 一行一页：**链接（可点）+ 标题 + 类型 + 一句话摘要 + tags + updated**；分组按 `type` [S1]（organized by category）。
- 摘要列必须等于该页 frontmatter 的 `summary`（单一事实来源，避免两处漂移）。
- `index.md` **由脚本重建**，幂等（同输入同输出），人不得手改 [S1][S6]；重建后行序按 `type` → `id` 字典序，保证 diff 稳定。
- 顶部放 3 行固定头：条目数、总字数、生成时间 + 「勿手改」提示。

### 4.2 为什么 index 优先而不是一上来就向量检索

原方法论的规模经验：`index.md` 在 **~100 个来源 / 数百页** 的规模下「works surprisingly well」，模型先读索引再下钻即可，不需要 embedding RAG [S1]；中文拆解也复述了同一结论（「不需要 RAG，秘密在两个文件」）[S2]。超出这个量级才引入检索工具，官方建议是本地 Markdown 混合检索引擎（BM25+向量+RRF+重排）[S4]。

→ 本项目策略：**先 index（L0），评测不达标再上 `server/wiki_search.py`（RRF）**；向量检索作为最后选项，且必须用 `Hit@1` / `MRR@5` / 引用接地率量化收益，不得凭感觉加 [S4]（对照基准可量化）+ 本项目评测口径。

### 4.3 渐进披露 L0–L3 与 token 预算

依据：模型必须「先拿轻量标识符、运行时按需加载」，且 token 越多召回越差（context rot），所以必须分层 + 设预算 [S7]；实现侧的预算按比例切分（wiki 页面 60% / 索引 5% / 系统提示 15% / 对话 20%）[S6]。

| 层 | 取什么 | 预算（单次查询） | 何时进入 | 依据 |
|---|---|---|---|---|
| **L0** | `index.md` 全量 | ≤ **3k tokens**（≈6 KB 中英混排）；索引超限即触发分卷告警 | 每次查询必读 | [S1][S6] |
| **L1** | 命中页的 frontmatter + 全部标题（不含正文） | ≤ **800 tokens / 页**，一次 ≤ 5 页 | L0 定位到候选页 | [S7]（渐进披露） |
| **L2** | 命中页正文 + 断言引用标记 | ≤ **4k tokens / 页**；全部 L2 合计 ≤ 上下文 **60%** | L1 选出 1–3 页 | [S6]（60% 预算）、[S1]（drill into pages） |
| **L3** | `raw/` 某 `raw_id` 的 `span` 逐字片段（+ 图片 ID） | 单次 ≤ **2 条**、≤ **1.5k tokens**；**禁止整篇 raw 注入** | 仅当需要核验引文逐字性、或回答要引用原文时 | [S7]（just-in-time）、[S1]（raw 不可变，只读片段） |

**硬性**：L3 必须按 `span` 取片段，不得为了省事把整份 raw 灌进上下文；回答里出现的每个原文引用都要能在 L3 片段中逐字命中（§6）。

---

## 5. log.md 规范（Q4）

### 5.1 行格式

```markdown
## [2026-11-18] ingest | imm-0001 车险理赔实务（节选）
- raw_id: imm-0001 ｜ pages: L12-L18 ｜ 新建: 2 页 ｜ 更新: 3 页 ｜ 冲突: 0
- 操作者: d3-ingest-agent ｜ 锁: acquired 23:41:02 / released 23:41:37
```

- 每条以 `## [YYYY-MM-DD] <op> | <title>` 开头（**同前缀、可 grep**）[S1]；正文行用 `k: v`，方便正则解析。
- 只允许**追加**，禁止改动既有行 [S1]（append-only）[S3]。
- grep 纪律：`grep "^## \[" log.md | tail -5` 取最近 5 次操作 [S1]；`grep " ingest | " log.md | wc -l` 数已编译来源；`grep -c "conflict:" log.md` 查冲突次数。

### 5.2 op 枚举（只允许这 6 个）

| op | 何时必须写 | 依据 |
|---|---|---|
| `ingest` | **每编译一个 raw 来源写一条**（成功/失败都写；失败写 `result: failed` + 错误码） | [S1]（log 记录每次摄入） |
| `query` | 查询被回写成 `type=query` 页时写；纯查询不写（避免噪声） | [S1]（good answers filed back） |
| `lint` | 每次 lint 必写，带 `fail=0 warn=N` 计数 | [S1]（lint passes 入账） |
| `fix` | 任何自动修复（重建 index、补齐字段、删无效 related）必须写，列修了什么 | [S3]（腐烂要可见）、[S6]（受限动作集） |
| `schema` | 修改本规范/`schema.md`/枚举值 | 本项目决策（schema 变更必须可追溯） |
| `retract` | 撤回条目/断言、标记 `status: stale` 或 `conflicted` | [S1]（矛盾与过期是 lint 的核心对象） |

**为什么必须写日志**：它是 wiki 演化的时间线，也是让 LLM 理解「最近做了什么」的唯一低 token 通道 [S1]；同时它把「记忆腐烂」变成可命名、可检查的状态 [S3]。

---

## 6. 引用与溯源（Q5）——断言级，不是页面级

### 6.1 标注语法（页面内）

| 场景 | 写法 | 说明 |
|---|---|---|
| 文本断言 | `…绝对免赔率 20%。⟦S:imm-0001@L12-L18⟧` | 标记作用于**所在行/所在 bullet**；一行多个断言必须拆行，不许一个标记管一片 |
| 逐字引用 | 断言行下一行用 `> 「原文…」⟦S:imm-0001@L14⟧` | 引用块内文字必须是 raw 该 span 的**逐字子串** |
| 图片证据 | `⟦S:imm-0001@img-02⟧`，并在 frontmatter `image_refs: [img-02]` | 图片落在 `raw/assets/` 并记 sha256 [S1][S2] |
| 表格内 | 单元格末尾 `⟦S:imm-0003@L40⟧` | 表格里也要能逐格回溯 |

### 6.2 硬性要求（防幻觉）

| 规则 | 内容 | 依据 |
|---|---|---|
| R6.1 | 引用必须到 **`raw_id` + `span`** 粒度；无 `span` 的引用无效 | C0 `raw/README.md`（无 raw_id/span 不得入库）+ [S6]（`sources[]` 溯源） |
| R6.2 | 引文必须**逐字**取自 raw（lint 做子串校验，§7 L6）；转述必须标「转述」且仍指向同一 span | 本项目决策（把「证据」变成机器可验证的东西）；动机来自 [S5]（CitationAgent 逐条把 claim 对到来源）+ [S3]（引用断裂是最典型的腐烂） |
| R6.3 | **无证据不写断言**（fail-closed）：查不到出处的事实句一律删除，不写「大概」「通常」 | [S3]（过期/无据记忆比没有更危险）、[S1]（raw 是 source of truth） |
| R6.4 | 页面级 `source_refs` 与正文断言必须**一致**：正文出现的 `raw_id` ⊆ `source_refs` | 本项目决策（双向可查） |
| R6.5 | 两个来源冲突时**不合并**：并列两条断言 + `status: conflicted` + 写 `log` 的 `retract`/`ingest` 条目，交人工裁决 | [S1]（lint：页面间矛盾、新来源取代旧断言） |
| R6.6 | 答案要引用「条目章节 + 原文片段」两级，检索侧输出 `id#章节` + 逐字片段 | C0 `wiki/README.md`（引用逐字可回溯是质量门） |

---

## 7. lint 规范（Q6）

执行方式：`python scripts/wiki_tool.py lint --wiki data/llm-wiki-claims/wiki`（D3 落地时新增脚本；不得改续保脚本）。**FAIL 级问题 `exit 1`**，可直接接 CI [S3]。

| ID | 检查项 | 级别 | 可自动修？ | 修法 / 为什么 |
|---|---|---|---|---|
| L1 | frontmatter 缺必填字段 / `type`、`status`、`domain` 值不在枚举 | FAIL | 部分 | `updated` 缺失可补「今天」并记 `fix`；`type`/`domain` 不可推断 → **人工** |
| L2 | `index.md` 与实际文件不一致（缺行/多行/摘要漂移） | FAIL | **是** | 幂等重建 index（index 是纯派生文件，可安全重写）[S1][S6] |
| L3 | 失效链接：`related` 指向不存在 `id`、正文 `[[link]]` 断链、index 链接 404 | FAIL | 部分 | 删无效 `related` 元素 → 可自动 + 必须记 `fix`；正文断链含语义 → **人工** |
| L4 | 孤儿页：无任何入链且不在 index | FAIL | 否 | 要么补入链/入索引，要么删除；判断属内容决策 → **人工** [S1][S3] |
| L5 | 重复页：`id` 冲突、`title` 重复、`aliases` 与其它页 `title` 撞车 | FAIL | 否 | 合并涉及内容取舍 → **人工**（脚本只报告候选对）[S3] |
| L6 | 引用不可回溯：`raw_id` 不存在、`span` 越界、quote 非 raw 子串、`source_refs` 与正文不一致 | FAIL | 否 | 必须回读原文重写 → **人工/重跑 ingest** [S6][S5] |
| L7 | 断言无引用：正文出现事实句但该行无 `⟦S:…⟧` | WARN→（正式库）FAIL | 否 | 补证或删句（fail-closed）[S1][S3] |
| L8 | 空页/超长页：正文 < 100 字，或 > 9000 字、断言 > 40 条 | WARN | 部分 | 超长自动给「拆分建议」但不执行 [S3]（overlong files 是腐烂信号） |
| L9 | 过期：`updated` 超 180 天，或 `raw` 有新版本 `supersedes` | WARN | 部分 | 自动打 `status: stale` 并记 `fix`；是否重编 **人工** [S3]（freshness 循环）、[S1]（stale claims） |
| L10 | 预算超限：`index.md` > 3k tokens、单页 > 4k tokens | WARN | 是（仅提示） | 自动生成分卷/拆分建议，不自动执行 [S6][S7] |
| L11 | 越界写入：出现指向 `renewal-assistant/wiki/` 的路径引用或复制内容 | FAIL | 否 | 硬违规，删除并登记事故（H5）[本项目] |

**自动修复的边界（重要）**：只自动修 **纯派生、可逆** 的东西（index 重建、log 追加、`updated` 补齐、`status: stale` 打标）。任何**内容语义**变更（合并页、改断言、删引用）必须人工确认——实现侧应对照 [S6] 的做法：给人工的是**受限动作集**（如 `Create Page / Deep Research / Skip`），不允许 LLM 自创动作，这正是防幻觉的工程手段 [S6]；同时 [S5] 的经验是「自动化评测会漏，人工评审能抓到源选择偏差」。

---

## 8. 并发纪律：为什么一次只编译一个来源（Q7）

**结论：串行、单写者、持锁。** 三条独立理由：

1. **写放大与共享文件冲突**：一个来源平均会触碰 **10–15 个页面**，并且每次都要更新 `index.md` 与 `log.md` [S1]。两个 ingest 并行 → 同时写 index/log/共享实体页 → 后写覆盖先写（lost update），且互链变成半成品。
2. **这类域本身不适合并行 agent**：需要「所有 agent 共享同一上下文」或「agent 之间依赖很多」的域，当前不适合多智能体架构 [S5]——知识编译正是典型：第 2 个来源的结论依赖第 1 个来源已落地的实体页与互链。
3. **实现侧的经验做法就是串行队列**：持久化 ingest 队列显式「serial processing prevents concurrent LLM calls」，并带崩溃恢复与重试 [S6]。

**实操（D3 照做）**

| 步骤 | 动作 |
|---|---|
| 1 | 取锁 `wiki/.ingest.lock`（写 `pid` + 开始时间）；取不到锁则排队，**不得抢写** |
| 2 | 固定事务顺序：读 raw → 建/改条目 → 双向维护 `related` → 重建 `index.md` → 追加 `log.md` → 跑 lint → 释放锁 |
| 3 | 失败处理：条目写入视为一个事务；失败则按 `git` 回滚该次改动并写 `ingest … result: failed`，不留半成品 |
| 4 | 同一 `raw_id` 不得重复编译：先查 `log.md` 是否已有 `ingest | <raw_id>`（幂等）[S6]（SHA256 缓存跳过未变更来源） |
| 5 | 读操作（检索/查询）不受锁限制——多读单写 |

---

## 9. 与 D4 检索的接口约定

- 检索入口顺序固定：**L0 index → 选页 → L2 正文 → （必要时）L3 raw 片段**（§4.3）。
- 输出契约：`[{wiki_id, source, version, score}]`（沿用仓库既有事件契约，不改），章节锚点与逐字片段只进节点详情与 prompt。
- 复用既有能力时**只导入不改源码**：`WIKI_DIR=data/llm-wiki-claims/wiki` 注入，`server/wiki_search.py` 的 RRF 作为规模化回退路径（与 [S4] 的混合检索思路一致，但本阶段默认不启用）。
- 评测口径：`Hit@1` / `MRR@5` / **引用接地率**（回答引用的片段必须在条目章节内逐字命中）；接地率不达标一律先修引用，不许靠调排序分数掩盖。

---

## 10. 本项目的 10 条硬性萃取纪律（D3 直接执行）

> 前置硬约束：一切写入只允许落在 `data/llm-wiki-claims/`；禁止写 `renewal-assistant/wiki/`、`traces/`（H5）。

1. **一次只编译一个来源**：持 `wiki/.ingest.lock` 串行执行，读完一个 `raw_id` 才允许取下一个；读操作不受限。[S1][S5][S6]
2. **无 `raw_id` + `span` 不入库**：任何片段没有稳定 ID 与原文定位，一律不得进入 wiki 条目。[S1] + C0 `raw/README.md`
3. **断言级引用**：每条事实断言所在行必须以 `⟦S:<raw_id>@<span>⟧` 结尾；没有标记的事实句视为错误，删句而不是补「据说」。[S7]（按需取原文）+ 本项目 fail-closed 决策
4. **引文逐字**：`>` 引用块中的文字必须是 raw 该 span 的逐字子串，禁止改写后仍标为引用；转述必须写明「转述」。[S5]（claim→source 对应）+ 本项目机器校验决策
5. **frontmatter 九项必填齐全**（`id/type/title/domain/summary/tags/source_refs/updated/related`），`domain` 只取枚举值 `claims`（跨域用数组、主域在前）。[S6] + 本项目决策
6. **一页一主题**：正文 ≤ 9000 字且断言 ≤ 40 条，超限先拆页再写；别名进 `aliases`，不新开页。[S3]（超长即腐烂）
7. **无入链不入库**：新页必须至少有 1 条入链，`related` 必须双向写入；孤儿页视为未完成。[S1][S3]
8. **每次 ingest 必写日志**：`## [YYYY-MM-DD] ingest | <raw_id> <title>`，正文带新建/更新页数、冲突数、锁起止时间。[S1]
9. **index 只由脚本重建**：ingest 后必须重建并核对「条目数 = 文件数」；人手不得改 `index.md`，摘要列必须与 frontmatter `summary` 完全一致。[S1][S6]
10. **lint FAIL=0 才算落地**：每个 ingest 后跑 lint；L1/L2/L3/L4/L5/L6/L11 任一 FAIL 必须清零（自动修只能动派生文件，语义改动交人工），冲突一律 `status: conflicted` 并列两条、禁止自行合并。[S1][S3][S6]

---

## 11. 遗留与待验证（不粉饰）

| 项 | 状态 | 说明 |
|---|---|---|
| 断言级引用的**成本** | 待验证 | 逐条标记会显著增加 token 与生成时间；本轮未量化。D3 首版建议先在 `type=section` 页强制、`doc` 页允许段落级，跑评测后再决定是否全量强制。 |
| 「一次只编译一个来源」的**吞吐** | 待验证 | 串行是正确性优先的选择 [S5][S6]；若 D2 抽样条数多（>50），需要评估批处理窗口，但**不得并发写同一 wiki 目录**。 |
| 自动修复的**可接受边界** | 待验证 | 本文件只允许派生文件自动修（index/log/stale 标记）；是否需要更多自动修，等 lint 在真实语料上跑 2–3 轮后按实际误报率决定。 |
| L0–L3 预算数值 | 设计假设 | 3k/800/4k/1.5k 是依据 [S6] 的 60/5/15/20 比例与本项目上下文上限推算的**初始值**，需用 `Hit@1`/`MRR@5`/接地率校准。 |
| 两次检索 0 证据 | 已知缺口 | 「并发写入冲突」「文档 lint 自动化」两方向 `search.run` 未返回达标证据（`no_page_content`/`weak_support`），因此 §8/§7 的相关结论只由 [S1][S3][S5][S6] 支撑，未引用该两方向任何未读到的内容。 |
| 与既有 `renewal-assistant/wiki/README.md` 的关系 | 边界说明 | 该文件属保护对象（H4）；本规范§3 的字段集合与它**在 `summary/tags/related/category` 上相容**（这一点由 C0 的 `data/llm-wiki-claims/wiki/README.md` 明文要求），但本规范不依赖、不修改、不复制其内容。 |

---

## 12. 变更记录

| 日期 | 版本 | 变更 | 依据 |
|---|---|---|---|
| 2026-11-18 | v1.0 | 首次定稿：三层/目录、frontmatter 九必填、index 行格式与 L0–L3、log op 枚举、断言级引用、lint L1–L11、串行编译纪律、10 条硬纪律 | §1 全部来源（S1–S7） |

<!-- 参考链接（reference-style）：文中 [S#] 即指向以下 URL -->

[S1]: https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw
[S2]: https://juejin.cn/post/7625301482213130291
[S3]: https://github.com/chenhz01/memory-wiki
[S4]: https://github.com/tobi/qmd
[S5]: https://www.anthropic.com/engineering/multi-agent-research-system
[S6]: https://github.com/nashsu/llm_wiki
[S7]: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
