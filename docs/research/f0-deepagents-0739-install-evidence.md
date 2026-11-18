# F0 检索依据：deepagents 0.7.39 安装与兼容性（先检索后动手）

> 任务：t15 / F0 环境隔离。硬规则要求「任何代码修改前必须先经 ≥3 个独立外部来源检索并落盘依据」。
> 本文件记录**用于做决策**的来源，全部带 URL + 检索时间 + 用途。R3（`docs/research/r3-langgraph-deepagents.md`）已查到的内容不复述，此处只记录**我为本任务独立复核 0.7.39 这一具体版本**的证据。
> 检索时间均为 2026-11-18（UTC 16:34–16:52，即 Asia/Shanghai 00:34–00:52）。

## S1 — PyPI JSON API：deepagents 0.7.39 的机器可读约束

- URL：`https://pypi.org/pypi/deepagents/0.7.39/json`
- 检索时间：2026-11-17T16:34Z（Asia/Shanghai 2026-11-18 00:34）
- 原始字段（逐字）：

```
name: deepagents version: 0.7.39
requires_python: <4.0,>=3.11
requires_dist:
  - langchain<2.0.0,>=1.5.0
  - langchain-core<2.0.0,>=1.8.1
  - langchain-anthropic<2.0.0,>=1.7.10
  - langchain-google-genai<5.0.0,>=4.4.3
  - langsmith>=0.14.17
  - packaging>=23.2
  - wcmatch>=11.0
  - langchain-aws<2.0.0,>=1.9.3; extra == "aws"
  - langchain-quickjs>=0.3.12; extra == "quickjs"
  - av>=18.0.0; extra == "video"
  - pillow>=12.3.0; extra == "video"
license: MIT
upload_time(0.7.39): 2026-11-16T15:55:09
```

- **用于决策 1（Python 版本）**：`requires_python <4.0,>=3.11`，本机解释器为 **3.14.2**（`.venv-claims/bin/python -V`）→ 满足，无需额外 Python。
- **用于决策 2（为什么要隔离 venv）**：硬依赖 `langchain-core>=1.8.1`，而续保共享 `.venv` 锁定 **langchain-core==1.8.0** → **装在共享环境必然触发升级**，故采用整份 venv 复制隔离（主 Agent 裁决 A1）。
- **用于决策 3（依赖面）**：`langchain-anthropic` 与 `langchain-google-genai` 是**硬依赖**（非 extra），即使用不到 Anthropic/Google 也会被装进来（见 L4 遗留）。

## S2 — Deep Agents 官方文档：v0.7 任务规划改为 opt-in（对应断言 A4）

- URL：`https://docs.langchain.com/oss/python/deepagents/overview`
- 检索时间：2026-11-17T16:38Z（Asia/Shanghai 00:38），HTTP 200，773 870 bytes
- 原文摘录（逐字，正文文本抽取）：

> 「Task planning is an opt-in harness capability that lets agents maintain a structured task list during execution. **Starting in v0.7 task planning is opt-in only. In earlier versions, task planning middleware was included by default.**」
>
> 「Pass `TodoListMiddleware` to the `middleware` parameter to give the agent a `write_todos` tool for maintaining a structured task list during execution.」
>
> 示例：`from langchain.agents.middleware import TodoListMiddleware` / `create_deep_agent(model=..., middleware=[TodoListMiddleware()])`

- **用于决策 4**：确认 R3 §4「todo planning 自 0.7 起 opt-in」成立，且**中间件来自 `langchain.agents.middleware` 包**，不在 `deepagents` 里（`import deepagents` 的公开符号中确实没有 `TodoListMiddleware`）。

## S3 — 官方文档：`execute`（shell）工具仅 sandbox backend 提供（对应断言 A2）

- URL：同 S2（`https://docs.langchain.com/oss/python/deepagents/overview`），同一快照
- 原文摘录（逐字）：

> 内置文件系统工具表：`execute` | Run shell commands in the environment (**available with sandbox backends only**)

- **用于决策 5**：R3 §4「FilesystemBackend 不执行 shell」的方向正确；文档口径是「`execute` 工具只在 sandbox backend 下出现」。我的探针进一步收紧了措辞（见研究结论 N1：实现内部仍会 fork `rg`）。

## S4 — GitHub 官方仓库 README（定位与能力边界）

- URL：`https://raw.githubusercontent.com/langchain-ai/deepagents/main/README.md`（渲染页：`https://github.com/langchain-ai/deepagents`）
- 检索时间：2026-11-17T16:35Z（Asia/Shanghai 00:35），7 393 bytes
- 原文摘录（逐字）：

> 「Deep Agents is an open source agent harness — an opinionated agent that runs out of the box. Extend, override, or replace any piece.」
>
> 「**Production-ready** — built on LangGraph (streaming, persistence, checkpointing) with first-class tracing, evaluation, and deployment via LangSmith」
>
> Features：「**Sub-agents** — delegate tasks to agents with isolated context windows」「**Filesystem** — read, write, edit, or search over pluggable local, sandboxed, or remote backends」「**Shell access** — run commands in your sandbox of choice」

- **用于决策 6**：确认「Deep Agents = LangGraph 之上的 harness」这一 R3 §3 命题有官方一手出处；并确认 shell 能力被官方表述为「in your sandbox of choice」（即需显式选 sandbox/shell backend）。

## S5 — 本地安装产物（针对 0.7.39 构建的最权威证据）

第三方来源给的是**约束**，实际装进来的 **METADATA 与源码**才是这个构建的事实。检索时间 2026-11-17T16:49Z。

- `.../.venv-claims/lib/python3.14/site-packages/deepagents-0.7.39.dist-info/METADATA`：与 S1 完全一致（`Requires-Python: <4.0,>=3.11`；`langchain-core<2.0.0,>=1.8.1`）。
- `.../langchain-1.5.0.dist-info/METADATA`：`Requires-Dist: langgraph<1.3.0,>=1.2.12`
  → **项目现有 `langgraph==1.2.20` 落在该区间内，因此 pip 完全没有升级 langgraph**（dry-run 的 "Would install" 列表里无 langgraph）。这是「与项目 langgraph 1.2.20 兼容」的**直接证据**。
- `.../google_genai-3.4.0.dist-info/METADATA`：`Requires-Dist: tenacity<9.2.0,>=8.2.3`
  → **tenacity 9.2.1 → 9.1.4 降级的真因**，不是 langchain-core（其约束是 `tenacity!=8.4.0,>=8.1.0`），而是 `langchain-google-genai → google-genai` 链上的 `<9.2.0` 上限。

## S6 — 版本存在性/可下载性交叉验证

- URL：`https://pypi.org/pypi/tenacity/json`，检索时间 2026-11-17T16:47Z
- 结果：`tenacity` 最新为 **9.2.1**（requires_python `>=3.10`，两个 wheel 均 `yanked: False`）
- **用于结论 N2**：9.1.4 不是「9.2.1 被 yank」导致，而是被上一条 S5 的 `<9.2.0` 上限**主动降级**——说明降级是确定性的、可解释的，不是偶发。

## 结论摘要（供 t9 / F3 引用）

| 编号 | 结论 | 依据 |
|---|---|---|
| N0 | 装 deepagents==0.7.39 需新增 **13 个包**，`langgraph` 保持 1.2.20 不变 | S5 + dry-run "Would install" |
| N1 | FilesystemBackend **不向模型暴露 shell**（无 `execute` 工具、无 `shell=True`）；但其 `grep` 实现会用 **argv 列表** fork `rg`（`-F` 固定字符串 + `--` 终止符），并有纯 Python 回退 → 表述应为「模型不可执行任意命令」，而非「进程绝不 fork 子进程」 | S3 + S5 源码 `backends/filesystem.py` |
| N2 | tenacity 降级由 `google-genai<9.2.0` 触发，非 yank、非 langchain-core | S5 + S6 |
| N3 | 续保 148 tests 在 langchain-core 1.8.1 + tenacity 9.1.4 下**零回归** | 见 `docs/log/step-f0.md` 双跑原文 |
