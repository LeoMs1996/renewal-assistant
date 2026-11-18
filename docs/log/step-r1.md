# step-r1 · R1 LLM-Wiki 萃取规范研究（交付日志）

> 任务：`t1`（attempt 2，`2faa2190-1d6d-4d97-a97e-0e93301b53ae`）｜执行：wiki-lead｜日期：2026-11-18
> 交付物：`docs/research/llmwiki-spec.md`（v1.0，**唯一**代码/配置级改动为新增文档）

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 一句话职责 |
|---|---|---|
| `docs/research/llmwiki-spec.md` | **新增** | 理赔域 LLM-Wiki 可执行规范：三层目录、frontmatter、index/log、断言级引用、lint L1–L11、串行纪律、10 条硬纪律（供 D3 直接照做） |
| `docs/log/step-r1.md` | **新增** | 本日志（四件套：做了什么 / 决策与依据 / 验证证据 / 遗留交接） |

**没有改动**：`server/`、`tests/`、`mcp_servers/`、`SPEC.md`、`wiki/`、`traces/`、`data/` 下任何文件（`data/llm-wiki-claims/` 与 `data/ins-mmbench/` 仍是 C0 占位）。本步不写代码、不建 wiki 条目——那属 D2/D3。

---

## 2. 关键决策与依据（决策 → 来源 → 影响）

检索批次：**2026-11-17**（本机 23:0x–23:5x；工具 `web_call read.fetch` / `web_call search.run`）。以下 7 条互相独立（不同作者/站点）。

| # | 来源 | URL | 检索时间 | 支撑的决策 |
|---|---|---|---|---|
| S1 | Karpathy《LLM Wiki》gist 原文 raw | https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw | 2026-11-17 | 三层架构、raw 不可变、Ingest/Query/Lint、index 规模经验、log 前缀、lint 项、10–15 页写放大、wiki=git |
| S2 | juejin 中文拆解 | https://juejin.cn/post/7625301482213130291 | 2026-11-17 | 交叉验证 index/log 职责、raw/assets 约定、调校期、qmd 退化路径 |
| S3 | chenhz01/memory-wiki | https://github.com/chenhz01/memory-wiki | 2026-11-17 | lint 检查项与 `exit 1` 门禁、log 只追加、禁静默覆盖、freshness 循环 |
| S4 | tobi/qmd README | https://github.com/tobi/qmd | 2026-11-17 | 规模超 index 后的混合检索退化路径、metadata 过滤 |
| S5 | Anthropic 多 agent 研究系统 | https://www.anthropic.com/engineering/multi-agent-research-system | 2026-11-17 | 共享上下文域不宜并行 → 串行编译；CitationAgent → 断言级溯源 |
| S6 | nashsu/llm_wiki | https://github.com/nashsu/llm_wiki | 2026-11-17 | 每页 frontmatter + `sources[]`、串行 ingest 队列、预算 60/5/15/20、受限动作集 |
| S7 | Anthropic context engineering | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 2026-11-17 | 渐进披露与 just-in-time、context rot → L0–L3 与预算 |

### 2.1 关键决策

1. **frontmatter 从「可选增强」升为强制 9 项**（含 `domain` / `source_refs`）。S1 里 frontmatter 是可选的，但 D4 的检索/评测需要机器可读字段，且 S6 的实现是「每页 YAML frontmatter + `sources[]`」。→ spec §3.1。
2. **目录 `raw/` 只读、`wiki/` LLM 独占写**，并对齐 C0 已定的 `data/llm-wiki-claims/{raw,wiki}`（不改 C0 布局）。S1 原话 immutable。→ spec §2 R2.1/R2.2。
3. **引用做到断言级**（`⟦S:<raw_id>@<span>⟧`），并用 lint 做「quote 必须是 raw 子串」的机器校验。依据：船长要求断言级 + S5（claim→source 逐条对应）+ S6（溯源字段）；「子串校验」为本项目加的工程手段（spec 已标注为本项目决策，未冒充外部结论）。
4. **index.md 脚本重建、禁手改、行内含 链接/标题/类型/摘要/tags/updated**。S1（link + 一行摘要 + 可选元数据 + 按分类）+ S6（index 是导航入口）；C0 `wiki/README.md` 已要求「脚本生成、幂等、不手改」。
5. **L0–L3 分层与预算 3k/800/4k/1.5k**。依据 S7（渐进披露、context rot）+ S6（60% wiki / 5% index 的比例）；具体数值标注为**设计假设**，待 D4 评测校准（spec §11）。
6. **log 行格式 `## [YYYY-MM-DD] <op> | <title>` + 6 个 op 枚举**。S1 给出该前缀与 `grep "^## \["` 用法；op 枚举由本项目按「哪些操作必须留痕」收敛。
7. **一次只编译一个来源：持锁串行、固定事务顺序**。三条独立依据：S1（每次 ingest 触碰 10–15 页 + index + log）、S5（共享上下文域不适合并行多 agent）、S6（持久化串行 ingest 队列显式防并发）。→ spec §8。
8. **lint 分「可自动修 / 必须人工」**：只自动修纯派生文件（index 重建、log 追加、`updated` 补齐、`stale` 打标），语义改动一律人工；自动修必须写 `fix` 日志。依据 S3（腐烂要变成有名状态）+ S6（受限动作集防幻觉）+ S5（人工评审补自动化盲区）。→ spec §7。

### 2.2 被否决的方案及原因

| 被否决 | 原因 |
|---|---|
| 一上来就启用向量/RRF 检索 | S1 的规模经验是 index 在 ~100 源/数百页足够；过早引入会掩盖引用问题，且无法归因。先 index，评测不达标再退到 `server/wiki_search.py`（S4 的混合检索是最后选项）。 |
| 页面级引用（每页列 `source_refs` 就够） | 船长明确要求断言级；页面级无法定位到具体哪句话由哪段原文支撑，正是幻觉最容易藏身处（S5 的 CitationAgent 也是逐条 claim 对齐来源）。 |
| 并行 ingest 提速 | S1 的写放大（10–15 页/来源）+ S5（共享上下文不宜并行）+ S6（串行队列）三条独立证据都指向串行；并行会 lost update 并产出半成品互链。 |
| 让 LLM 自动合并重复页/改断言 | 语义变更不可逆且易幻觉；S6 的做法是给人工**受限动作集**。本规范只允许自动修派生文件。 |

### 2.3 未采信（诚实记录）

两次 `search.run` 未返回达标证据：①「并发写入导致索引冲突」②「文档 lint 自动化可修边界」（返回 `no_page_content` / `weak_support`，仅有低相关排行榜/百科噪声）。→ 未据此写任何规则；§8/§7 的相关结论只由 S1/S3/S5/S6 支撑。已在 spec §11 登记。

---

## 3. 验证证据（命令 + 真实输出）

执行环境：`renewal-assistant/`，2026-11-18 00:33，同一批次执行，全部 `exit 0`。

```bash
$ grep -c '^## ' docs/research/llmwiki-spec.md
17
$ grep -c '^\[S[0-9]\]: http' docs/research/llmwiki-spec.md
7
$ awk '/^## 10\./{f=1} /^## 11\./{f=0} f' docs/research/llmwiki-spec.md | grep -cE '^[0-9]+\. \*\*'
10
$ grep -nE '^## (2|3|4|5|6|7|8)\. ' docs/research/llmwiki-spec.md
30:## 2. 目录结构与三层职责（Q1）
64:## 3. 条目 schema（Q2）
162:## 4. index.md 规范与 token 预算（Q3）
200:## 5. log.md 规范（Q4）
229:## 6. 引用与溯源（Q5）——断言级，不是页面级
253:## 7. lint 规范（Q6）
275:## 8. 并发纪律：为什么一次只编译一个来源（Q7）
$ wc -l docs/research/llmwiki-spec.md docs/log/step-r1.md
     348 docs/research/llmwiki-spec.md
      97 docs/log/step-r1.md
$ git status --short -- wiki traces server tests SPEC.md
（空输出）
$ git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md
（空输出，exit 0）
$ find data/llm-wiki-claims -type f | sort
data/llm-wiki-claims/raw/.gitkeep
data/llm-wiki-claims/raw/README.md
data/llm-wiki-claims/wiki/.gitkeep
data/llm-wiki-claims/wiki/README.md
$ ls -l docs/research/llmwiki-spec.md
-rw-------  1 leoms  staff  28151 11月 18 00:33 docs/research/llmwiki-spec.md
```

**判读**

- **节数 17**（验收要求 ≥7）✓；Q1–Q7 七个必答问题各占一节（第 30/64/162/200/229/253/275 行）✓
- **来源链接 7 条**（S1–S7 的 reference-style 定义），正文每条规则后的 `[S#]` 直接指向 URL，满足「每条规则带来源链接」✓
- **§10 内恰好 10 条编号硬纪律** ✓。注：全文 `grep -cE '^[0-9]+\. \*\*'` 为 13，多出的 3 条是 §8「为什么串行」的三条理由（同为编号列表），不是纪律条目
- **隔离成立**：`git diff 40541d1 -- server tests mcp_servers wiki SPEC.md` 为空；`data/llm-wiki-claims/` 仍只有 C0 的 4 个占位文件；`wiki/`、`traces/` 零改动 ✓
- `git status` 里的 `.gitignore` 修改与 `claims/`、`data/`、`traces-claims/` 等未跟踪项属**其它成员的并行产出**（C0 起的骨架），不是本步改动；本步只新增 `docs/research/llmwiki-spec.md` 与 `docs/log/step-r1.md`
- **证据时效说明**：上面 `wc -l` 中的 `97 docs/log/step-r1.md` 是本段被写入**之前**的实测值；本文件随后追加了本节，当前行数已变大（`docs/research/llmwiki-spec.md` 的 348 行不变）。其它数字（17 / 7 / 10 / 空 diff / 4 个占位文件）均可在当前工作区复现。

---

## 4. 遗留问题与交接

| # | 事项 | 承接方 | 说明 |
|---|---|---|---|
| 1 | 按 spec §3 写首个真实条目（D3） | D3 ingest Agent | 先做 1 条 `type=section` 走通全链路（写页 → 重建 index → 追加 log → lint=0），再批量 |
| 2 | `scripts/wiki_tool.py`（index/lint/log 三子命令） | D3 | **不得修改**续保既有脚本；新增脚本须 `WIKI_DIR` 注入，硬编码路径视为违规 |
| 3 | L0–L3 预算数值校准（3k/800/4k/1.5k） | D4 | 用 Hit@1 / MRR@5 / 引用接地率校准；spec 已标为「设计假设」 |
| 4 | 断言级引用的 token 成本 | D3 → D4 | 首版建议 `section` 页强制、`doc` 页允许段落级，跑完评测再定 |
| 5 | 「并发写入冲突」方向缺外部证据 | 后续任务 | 若需更强依据，应检索 git 的 append-only/单写者实践或 CRDT 文档；当前不阻塞 |
| 6 | 与续保 `wiki/README.md` 的关系 | 全体 | 该文件属保护对象（H4）。本步在收到船长隔离指令**之前**曾读过它一次（用于了解既有约定）；**未写入、未复制其正文**，spec 的字段集合以 S1/S6 与 C0 的 `data/llm-wiki-claims/wiki/README.md` 为据。若要求严格零读取，请指示，我可在后续任务中改由 C0 文档单独推导。 |

**交接一句话**：D3 直接照 `docs/research/llmwiki-spec.md` §10 的 10 条纪律执行；`data/llm-wiki-claims/` 目前仍是空骨架，第一条 ingest 会创建 `wiki/index.md`、`wiki/log.md`、`wiki/schema.md` 与首条目。
