# wiki/ 维护约定（Schema 层）

> 本文件是 LLM-Wiki 三层架构里的 **schema 层**：把「一个通用助手」约束成「守规矩的 wiki 维护者」。
> 模式出处：Karpathy《llm-wiki.md》idea file（2026-04，primary source；检索 2026-11-17）
> <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>。
> 机器可执行的约定由 `scripts/wiki_tool.py`（index / lint / log）与 `tests/test_wiki_retrieval.py` 落实。

## 三层与职责

| 层 | 位置 | 谁写 | 说明 |
|---|---|---|---|
| raw sources | 条款原文（合成虚构条款） | 人 | 不可变，是事实的 source of truth |
| wiki | `wiki/*.md` | LLM 维护、人审 | 结构化、互链、可 grep 的 Markdown |
| schema | 本文件 | 人 + LLM 共演进 | 约定：front-matter 字段、锚点、引用格式、维护操作 |

## 条目格式（强制）

```markdown
---
id: wiki-xxx                 # 唯一，正文与轨迹里的引用键
version: v2024.3             # 条款版本（SPEC §5 引用字段）
effective_date: 2024-01-01   # 生效日，ISO；过期会被 lint 标为 stale claim
source: 《合成…条款（虚构）》  # 条款出处，引用必须带上
updated: 2026-11-17          # 最近维护日
category: 险种条款            # index.md 的分组依据
tags: 车损险, 保障范围        # 目录/检索字段，逗号分隔
related: wiki-deductible, wiki-annual-inspection   # 必须双向互指
summary: 一句话摘要（≤80 字）  # index.md 的「一句话摘要」列，也进检索索引字段
---

# 标题

## 章节标题
正文……（章节标题即引用锚点，同一文件内不得重复）
```

正文末尾保留 `## 相关条款` 段，用 `[[wiki-id]]` 写显式交叉引用（gist：交叉引用本身就是综合）。

## 引用格式（citation）

- 条目级：`wiki-csx`
- 章节级（推荐）：`wiki-csx#续保要点` —— 由 `server/wiki_search.py: span_citation()` 产出
- 轨迹 `retrieval` 事件的 `output` 仍严格是 `[{wiki_id, source, version, score}]`（SPEC §5），
  锚点与逐字片段只进 `node_end` 详情与 prompt，不污染事件契约。

## 三个操作

| 操作 | 命令 | 何时做 |
|---|---|---|
| Ingest | 手改条目 → `python scripts/wiki_tool.py index` → `... log "ingest \| 来源标题"` | 新增/更新条款条目后 |
| Query | `llm_wiki_context()` 全量注入，或 `WikiSearch.navigate()` 目录→钻取 | 运行时检索 |
| Lint | `python scripts/wiki_tool.py lint` | 每次改条目后；CI 里作为门禁 |

lint 覆盖 gist 点名的健康项：front-matter 缺字段、`related` 非双向/指向不存在条目、
正文 `[[link]]` 断链、章节标题重复（锚点冲突）、孤儿页（无入链）、
`effective_date` 过期（stale claim）、`index.md` 与条目不一致。

## 规模判断（何时该上检索）

gist 的经验值：`index.md` 在 ~100 来源 / 数百页规模内「surprisingly good」，不需要向量库。
本仓库 8 条目 / ~9KB 处于该区间，因此默认走**全量上下文 + 目录导航**；
`server/wiki_search.py` 的三通道 RRF 与 `navigate()` 是语料增长后的回退路径（有评测脚本量化，
见 `eval/knowledge_retrieval_eval.py` 与 `reviews/knowledge.md`）。
