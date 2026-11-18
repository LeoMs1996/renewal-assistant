# R3 框架基线研究 · 执行日志

> 任务：**t3 [r3] — R3 框架基线研究：LangGraph 确定性流程 × Deep Agents 分工**
> 执行人：flow-engineer（AgentTeams `insurance-intel-2026`，attempt 2 / `attempt_id=68d82d74-19d3-4c2a-9749-0c98b1fe2fd7`）
> 执行时间：**2026-11-17T23:17 → 2026-11-18T00:5x（+0800）**
> 工作目录：`/Users/leoms/Documents/deepseek-harness-workspace/homework5`
> 交付物：`renewal-assistant/docs/research/r3-langgraph-deepagents.md`（结论）+ `renewal-assistant/docs/research/evidence/**`（证据）
> 说明：本文件按队长要求**边做边写**；末尾「补记」小节可追加，不改历史条目。

---

## 0. 一句话结论

**LangGraph 1.2.20 管确定性状态机（`interrupt()` 人工审核 + 独立节点的幂等键 + `SqliteSaver` 跨进程恢复），Deep Agents 0.7.39 作为唯一的「材料分析」子图调用点，输出结构化 JSON；业务决策与不可逆支付一律留在外层图。** 两条结论都有官方文档原文 + 本机实测双证据。

---

## 1. 时间线（含一次中断事故）

| 时间 | 动作 | 结果 |
|---|---|---|
| 23:17 | 建 `insurance-agent/docs/research/evidence/`，`curl` 抓官方渲染页 | 200，1.2MB（后证明 `.mdx` 源更好用） |
| 23:18 | `curl` 抓 7 个 docs 页面 + `pip index versions deepagents` + `uv pip install --dry-run` | ✅ 拿到 **deepagents 0.7.39** 与依赖改动清单 |
| 23:19 | GitHub API 列 `langchain-ai/docs` 的 `src/oss/deepagents` 与 `src/oss/langgraph` | ✅ 发现 20 份 `.mdx` 源文件（比 HTML 干净） |
| 23:20-23:55 | 批量下载 20 份 `.mdx` + `deepagents/graph.py` 源码 + PyPI JSON | ✅ 全部 200（3 个文件首轮被 reset，重试成功） |
| 00:00-00:20 | 读 `lg-interrupts` / `lg-fault-tolerance` / `lg-checkpointers` / `da-*` 关键段 | ✅ 提取行号级引用 |
| 00:20 | 查 `langchain 1.5.0` / `langgraph 1.2.20` PyPI 元数据 | ✅ 证明无版本硬冲突 |
| **约 00:25** | **attempt 1 在写文件时中断（心跳超时）** | ⚠️ 8MB 证据文件被队长救回并搬到新位置 |
| 00:26 | attempt 2 接管（`attempt_id=68d82d74`） | 已 claim / in_progress |
| 00:30-00:45 | 写 `probe_langgraph_api.py`，跑 5 组实测 | ✅ 见 §3 |
| 00:45-00:55 | 按队长裁决迁移：`insurance-agent/` → `renewal-assistant/docs/research/`；写结论文件 + 本日志 | ✅ `insurance-agent/` 已删除 |

> **事故复盘**：attempt 1 崩在"最后一次大文件写入"上。教训与对策：结论文件**按节写入/及时落盘**，不要攒到收尾一次性 write。本 attempt 已改为「结论 → 立即写盘 → 再补细节」。

---

## 2. 来源采集记录（≥3 独立来源要求 → 实际 15 条）

全部为**本次实际访问**，原始响应已落盘在 `renewal-assistant/docs/research/evidence/`：

| 类别 | 文件 | 原始 URL | 访问时间 |
|---|---|---|---|
| 官方文档源（HTML） | `lg-interrupts.html` | https://docs.langchain.com/oss/python/langgraph/interrupts | 23:19 |
| 官方文档源（MDX，权威） | `mdx/lg-interrupts.mdx` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/interrupts.mdx | 23:52 |
| 同上 | `mdx/lg-checkpointers.mdx` | .../src/oss/langgraph/checkpointers.mdx | 23:52 |
| 同上 | `mdx/lg-fault-tolerance.mdx` | .../src/oss/langgraph/fault-tolerance.mdx | 23:52 |
| 同上 | `mdx/lg-graph-api.mdx` | .../src/oss/langgraph/graph-api.mdx | 23:52 |
| 同上 | `mdx/lg-graph-api-control-flow.mdx` | .../src/oss/langgraph/graph-api-control-flow.mdx | 23:52 |
| 同上 | `mdx/lg-use-subgraphs.mdx` | .../src/oss/langgraph/use-subgraphs.mdx | 23:52 |
| 同上 | `mdx/lg-workflows-agents.mdx` | .../src/oss/langgraph/workflows-agents.mdx | 23:52 |
| 同上 | `mdx/lg-persistence.mdx` | .../src/oss/langgraph/persistence.mdx | 23:53 |
| 同上 | `mdx/da-overview.mdx` | .../src/oss/deepagents/overview.mdx | 23:52 |
| 同上 | `mdx/da-subagents.mdx` | .../src/oss/deepagents/subagents.mdx | 23:52 |
| 同上 | `mdx/da-human-in-the-loop.mdx` | .../src/oss/deepagents/human-in-the-loop.mdx | 23:52 |
| 同上 | `mdx/da-context-engineering.mdx` | .../src/oss/deepagents/context-engineering.mdx | 23:52 |
| 同上 | `mdx/da-going-to-production.mdx` | .../src/oss/deepagents/going-to-production.mdx | 23:52 |
| 同上 | `mdx/da-models.mdx` | .../src/oss/deepagents/models.mdx | 23:52 |
| **GitHub 源码** | `deepagents-graph.py` | https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/deepagents/graph.py | 00:05 |
| **PyPI JSON** | `pypi-deepagents-0.7.39.json` | https://pypi.org/pypi/deepagents/0.7.39/json | 00:02 |
| **PyPI JSON** | `pypi-langchain-1.5.0.json` | https://pypi.org/pypi/langchain/1.5.0/json | 00:20 |
| **PyPI JSON** | `pypi-langgraph-1.2.20.json` | https://pypi.org/pypi/langgraph/1.2.20/json | 00:20 |

**检索通道说明**（如实记录，便于复现）：本轮 `web_call search.run` 全部失败——
`exa: Unknown MCP server 'exa'`、`ddg: fetch failed`、`github: fetch failed; gh is not logged in`（见 `web_call sources.status` 输出：只有 `seam/bing/v2ex/arxiv/wikipedia/hackernews` 等 ready）。
因此改用 **`web_call read.fetch`（MCP web-reader 通道）** 读官方页（成功，返回了 `docs.langchain.com/oss/python/langgraph/interrupts` 全文），再叠加 **`curl` + `raw.githubusercontent.com` + `pypi.org` JSON** 直取原文落盘。
→ 这不是"凭记忆"，而是**换通道取原文**；每条结论在结论文件里都能指到 evidence 文件的具体行。

---

## 3. 本机实测（这部分是别人无法用旧博客反驳的硬证据）

探针脚本：`renewal-assistant/docs/research/evidence/probe_langgraph_api.py`（非生产代码，只为取证）。

```bash
P=renewal-assistant/docs/research/evidence
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py introspect   # API 签名/版本
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py cleanup      # 清空 sqlite
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py phase1       # 进程 A：跑到 interrupt
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py phase2       # 进程 B：全新解释器 resume
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py recursion    # recursion_limit
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py durability   # durability 三档
```

| 组 | 输出文件 | 关键结果 |
|---|---|---|
| 版本/签名 | `probe-introspect.txt` | langgraph 1.2.20 / checkpoint 4.3.1 / checkpoint-sqlite 3.1.3 / langchain-core 1.8.0；`interrupt(value, *, response_schema=None)`、`Command(*, graph, update, resume, goto)`、`SqliteSaver(conn, *, serde)`、`RetryPolicy(...)`、`TimeoutPolicy(...)`、`CompiledStateGraph.invoke(..., durability=None)`、`Interrupt{value,id,response_schema}` |
| interrupt 暂停 | `probe-phase1.txt` | `next=('review',)`；state 里 `trace=['intake']`；`checkpoint_id` 已写；DB 4096 字节 |
| **跨进程恢复** | `probe-phase2.txt` | 新解释器 `get_state()` → `next=('review',)`、state 完整；`Command(resume=True)` 续跑成功；**`intake` 没有重跑**（trace 只有一次 `intake`），被中断的 `review` 重跑 |
| recursion | `probe-recursion.txt` | `recursion_limit=7` → `GraphRecursionError: Recursion limit of 7 reached without hitting a stop condition` |
| durability | `probe-durability.txt` | 挂 checkpointer 后 `sync/async/exit` 均被接受；**`"bogus"` 也被静默接受（无校验）**；不挂 checkpointer 时传 `sync` 会 `AttributeError: 'SyncPregelLoop' object has no attribute '_put_checkpoint_fut'` |
| 迁移后复跑 | 本日志 00:50 一次 | 从新路径 `renewal-assistant/docs/research/evidence/` 重跑 phase1+phase2，结果与上表一致（`phase1 next: ('review',)`、`phase2 recovered next: ('review',)`） |

**探针踩到的一个真坑（值得写进 t10）**：`from __future__ import annotations` + **函数内局部定义的 `TypedDict`** 作为 `add_conditional_edges` 的 path 函数注解时，LangGraph 会 `get_type_hints()` 推断 schema 而抛 `NameError: name 'S' is not defined`。→ **状态类必须定义在模块顶层**。首次运行 `probe-recursion` 就是因此失败，已改为模块级 `LoopState` 后通过（这条不是文档结论，是本机实测，已记入结论文件 §2）。

---

## 4. 交付物清单与验收自查

| 项 | 路径 | 状态 |
|---|---|---|
| 结论文档 | `renewal-assistant/docs/research/r3-langgraph-deepagents.md`（591 行） | ✅ |
| 证据目录 | `renewal-assistant/docs/research/evidence/`（23 文件：20×mdx + graph.py + 4×pypi/探针） | ✅ |
| 本日志 | `renewal-assistant/docs/log/step-r3.md` | ✅ |
| 旧路径清理 | `homework5/insurance-agent/` **已删除**（`ls` 返回 No such file or directory） | ✅ |

**任务卡 5 项必答 → 结论文件对应章节**：

| 任务卡要求 | 落在结论文件 |
|---|---|
| 1. LangGraph 关键 API（StateGraph / add_conditional_edges / interrupt / Command(resume) / SqliteSaver / durability / recursion limit） | §2（签名实测）+ §3.4（SqliteSaver）+ §4（recursion_limit） |
| 2. 确定性业务写法（interrupt 审核 / 幂等键 / retry / 失败边界） | §3.1 / §3.2 / §3.3 |
| 3. Deep Agents 版本与 API（create_deep_agent 签名 / subagents / filesystem / planning / HITL / 嵌套） | §5.1-§5.7 |
| 4. 两者集成官方推荐（节点内 vs 子图 / 状态传递 / 中断语义） | §6.1 / §6.2 / §6.3 |
| 5. 已知坑（模型要求 / token / 轮次） | §5.7 |
| 完成判据：拓扑草图（含 interrupt 位置 + Deep Agents 调用点） | §7（mermaid + 逐位置依据表） |

**队长追加 6 问 → 结论文件对应章节**：

| 队长问题 | 落点 |
|---|---|
| Q1 `interrupt`/`checkpointer` 官方签名与语义 | §2 + §3.1（签名实测 + 官方原文行号） |
| Q2 sqlite checkpointer 重启恢复语义与坑 | §3.4（含两进程实测 + 7 条坑表） |
| Q3 包名/版本/安装方式/是否就是 LangGraph 图 | §5.1 + §5.2（`-> CompiledStateGraph` 为源码事实） |
| Q4 子代理/文件系统/待办如何在流程内被调用 | §5.4（`task` 工具，不是节点）+ §5.5 + §6.3 代码骨架 |
| Q5 人在回路 + 支付类不可逆操作推荐模式 | §3.2（幂等键）+ §3.3（error_handler 查单）+ §5.6（`interrupt_on` 风险分级）+ §7 拓扑 |
| Q6 官方是否有"把业务决策交给 agent"的反例 | §8（5 条原文举证 + 明确结论：**没有**） |

---

## 5. 需要队长裁决的事项（已在结论文件 §10 详列）

1. **A1 是否安装 `deepagents==0.7.39`**：`uv pip install --dry-run` 实测会 **新增 13 包、升级 `langchain-core 1.8.0→1.8.1`、降级 `tenacity 9.2.1→9.1.4`**。建议装独立 venv `.venv-claims` + `DEEPAGENTS_ENABLED` 开关；不批准也能用规则引擎降级版完整交付。
2. **A2 模型供应商**：Deep Agents 要求 tool-calling 强模型；`model` 必须显式传（`None` 自 0.5.3 已 deprecated）。
3. **A3 审核三态**（approve/reject/request_more）：建议用**单个** `interrupt()` + 分支，不要新增 interrupt（resume 按索引匹配，多 interrupt 易错）。
4. **A4 per-thread 子图**：建议 `checkpointer=None`（per-invocation，继承父 checkpointer，支持 interrupt），不留 agent 全轨迹 checkpoint。

---

## 6. 与 C0 隔离机制的衔接（队长通知第 3 点）

队长转达 integrator 结论：`server/config.py:42/44` 已支持 `TRACE_DIR` / `WIKI_DIR` 环境变量，理赔域可**零侵入复用** `server/trace.py` / `server/wiki_search.py`：

```bash
TRACE_DIR=traces-claims
WIKI_DIR=data/llm-wiki-claims/wiki
```

→ 对 R3 的影响：**框架基线不需要改续保任何一行**。§7 拓扑里的 `close`（结案归档）与 LLM-Wiki 萃取落盘，直接走这两个环境变量注入的目录；`SqliteSaver` 的 DB 也放在理赔域自己的目录（如 `claims/data/checkpoints.sqlite`），与续保的 checkpoint（若有）隔离。

---

## 7. 复现清单（一条命令验全部）

```bash
cd /Users/leoms/Documents/deepseek-harness-workspace/homework5
P=renewal-assistant/docs/research/evidence
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py introspect | head -20
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py cleanup
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py phase1
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py phase2
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py recursion
renewal-assistant/.venv/bin/python $P/probe_langgraph_api.py durability
# 证据文件完整性
ls renewal-assistant/docs/research/evidence | wc -l      # 期望 23
ls renewal-assistant/docs/research/evidence/mdx | wc -l  # 期望 20
```

---

## 补记（append-only）

- **2026-11-18 00:5x**：per 队长裁决，交付根从 `homework5/insurance-agent/` 迁到 `renewal-assistant/`；结论文档改名 `r3-langgraph-deepagents.md`；`insurance-agent/` 已删除；探针在新路径复跑一次，结果一致。
