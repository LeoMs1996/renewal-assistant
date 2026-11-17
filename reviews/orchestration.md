# 编排域评审与落地优化（Agent 编排 / LangGraph 状态机，2026-11-13 基线）

- 评审对象：`server/graph.py`（LangGraph **1.2.20** 状态机，11 业务节点 + 20 条边/条件边，官方 checkpointer 持久化、SSE 自定义事件通道）+ `server/app.py` 编排入口（`/chat` 驱动 `graph.stream`、`/confirm` 落单）
- 评审人：orchestration-reviewer-ds（域任务 t1）
- 基线：2026-11 当前最新 LangGraph 官方编排语义（durability / interrupt / fault tolerance / recursion limit）+ 安装包源码实测
- 硬约束遵守：**本文所有技术结论均来自下列本次检索与本次实测**（检索时间戳 2026-11-17 11:59–12:06 CST，团队基线时点 2026-11-13），未以训练记忆直接下结论；无法证实处标注「待验证」
- 历史上下文：上一轮（2026-11-13）已落地官方 checkpointer（SqliteSaver/InMemorySaver）、`_ThreadHandle` thread_id 注入、SPEC §3.2 规则 3 版本自增修复；本轮**不重做**这些，只审其遗留项 + 新发现的执行期缺口

## 一、检索基线（6 个官方来源 + 5 个独立工程侧来源 + 2 个安装包源码事实）

| # | 来源 | 关键基线要点 |
|---|---|---|
| 1 | [LangChain Docs · Graph API（recursion_limit / GraphRecursionError）](https://docs.langchain.com/oss/python/langgraph/graph-api-control-flow)（Context7 `/websites/langchain_oss_python_langgraph`，检索 2026-11-17） | 终止条件不可保证时须设 `recursion_limit`；超限抛 `GraphRecursionError`，示例明确要求 **catch 并处理该异常**，而非任其冒泡 |
| 2 | [LangChain Docs · Checkpointers（durability）](https://docs.langchain.com/oss/python/langgraph/checkpointers)（同上，检索 2026-11-17） | 执行方法接受 `durability` 参数控制落盘时机；示例 `graph.stream(..., durability="sync")` = 每个 superstep 开始下一步前**同步**落盘 |
| 3 | [LangChain Docs · Fault tolerance（RetryPolicy / node timeout）](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)（同上，检索 2026-11-17） | ① 节点级 `RetryPolicy`（`langgraph.types.RetryPolicy`）处理易抖动的步骤；② 节点 `timeout`（`TimeoutPolicy`）**仅对 async 节点生效，给 sync 节点设置会在编译期失败**，需 `langgraph>=1.2`（本机 1.2.20，满足） |
| 4 | [LangChain Docs · Interrupts（human-in-the-loop）](https://docs.langchain.com/oss/python/langgraph/interrupts)（同上，检索 2026-11-17） | 节点内 `interrupt()` 挂起 → 恢复必须用 **同一 thread_id + `Command(resume=...)`**；恢复时该节点从函数开头重跑（interrupt 之前的代码会重放） |
| 5 | [LangChain Docs · Time travel / fork](https://docs.langchain.com/oss/python/langgraph/use-time-travel)（同上，检索 2026-11-17） | `get_state_history` 可回放/分叉；interrupt 在 time travel 中会重新触发 |
| 6 | [LangGraph 错误文档 · GRAPH_RECURSION_LIMIT](https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT)（本机运行时异常信息原文引用，2026-11-17 实测产出） | 该错误码是框架公开语义，运维侧应能按码区分「图跑飞」与其他故障 |
| 7 | [Bhaskar-Kurasala/langgraph-production-patterns](https://github.com/Bhaskar-Kurasala/langgraph-production-patterns)（2026-07-13，web 检索 2026-11-17） | 生产必备原语清单：durable execution、OTel 可观测、HITL、multi-agent；每个模块以 assert 做 PROOF |
| 8 | [MettaSurendhar/agent-template-orchestrator-advanced-langgraph](https://github.com/MettaSurendhar/agent-template-orchestrator-advanced-langgraph)（2026-10-02，同次检索） | 生产级模板统一采用 **Postgres 持久化状态** + per-agent human review；SQLite 仅本地级 |
| 9 | [suhasagg/distributed-sql-agent-runtime](https://github.com/suhasagg/distributed-sql-agent-runtime)（2026-10-04，同次检索） | 生产 worker 必备：**retry policy by error class**、deadlines、circuit breakers、bulkheads、graceful shutdown |
| 10 | [thanhauco/agent-mesh](https://github.com/thanhauco/agent-mesh)（2026-09-05）/ [arikh/retail-support-platform](https://github.com/arikh/retail-support-platform)（2026-10-20）（同次检索） | 多智能体编排的落地形态参考（本项目判定 N/A，见 F8） |
| 11 | **安装包源码实测**：`.venv/.../langgraph/checkpoint/sqlite/__init__.py`（2026-11-17 实读） | docstring 原文：`Note: check_same_thread=False is OK as the implementation uses a lock to ensure thread safety.`（第 74–75 行）；实例字段 `self.lock = threading.Lock()`（第 100 行）；所有游标访问 `with self.lock:`（第 200 行）→ **Saver 自带线程安全** |
| 12 | **安装包源码实测**：`.venv/.../langgraph/_retry.py` + `types.py`（2026-11-17 实读） | `RetryPolicy` 默认 `retry_on=default_retry_on`：对 `ConnectionError`/httpx 5xx/未知异常重试，明确**不重试** `ValueError/TypeError/RuntimeError/OSError` 等；`max_attempts` 语义 = 总尝试次数（实测 3 → 3 次调用） |

版本事实（`importlib.metadata` 实测）：`langgraph 1.2.20`、`langgraph-checkpoint 4.3.1`、`langgraph-checkpoint-sqlite 3.1.3`、`langchain-core 1.8.0`。

## 二、评分

| 子项 | 得分 | 依据 |
|---|---|---|
| 拓扑与 SPEC §6.2 一致性 | 8.5/10（优化后 9.0） | 11 业务节点 / 20 条边与 SPEC 一致，三条事务性旁路在文件头书面登记（来源 1 的「显式拓扑」要求）；本轮补拓扑快照回归测试 |
| 持久化（checkpointer） | 8.0 → 9.0 | 官方 SqliteSaver + thread_id 注入已就位（来源 2）；但落盘时机未声明（默认 async），本轮显式化 |
| 故障韧性（重试/超时/降级） | 5.0 → 8.0 | 节点级重试**结构性失效**（异常被内层吞掉，F1）→ 已在正确层次落地分层重试（来源 3、9）；节点超时因全是 sync 节点不可用（F5，P1） |
| 执行期错误语义 | 6.0 → 9.0 | `GraphRecursionError` 原本落进兜底 `except Exception` → SSE `INTERNAL`；现已翻译为 `GRAPH_RECURSION_LIMIT` + 终态 `finish_reason=error`（来源 1、6） |
| 并发安全 | 6.0 → 8.5 | 旧 `_RUN_LOCK` 名义串行、实际无效且无必要（F2，探针 + 来源 11）→ 已删除；SQLite 仍非多副本方案（来源 8） |
| HITL / `interrupt()` | 5.0 | 跨轮确认靠「重入图 + sessions.json 双写」，未用官方 `interrupt()`/`Command(resume=)`（来源 4）；迁移需 SPEC + 前端协同（F4，未落地） |
| 可回归性（编排） | 6.0 → 9.0 | 新增 `tests/test_orchestration.py` 25 条断言（拓扑快照/参数注入/递归翻译/重试分层/并发/防回归） |
| 多智能体编排 | N/A | 单会话单车主、无并行子任务，supervisor/swarm 式扇出无业务收益（判定理由见 F8），不引入 |
| **域总评** | **7.0/10 → 8.3/10** | 执行期「韧性 + 错误语义 + 并发声明」三类缺口补上；HITL 原语与双写收敛留 P1 |

## 三、Findings（按严重度；全部来自本次检索 + 本次实测）

| # | 严重度 | 问题 | 证据 | 状态 |
|---|---|---|---|---|
| F1 | **high** | **节点级 `RetryPolicy` 结构性失效**：`llm.py` 的 `chat`/`chat_tool_json` 用 `except Exception` 降级为规则模式，`graph._call_tool` 又把桥接异常收进 `{"error": {...}}` 返回值 → 图节点**永不抛异常** → 官方节点级重试（来源 3）即使加上也永远不会触发。故障被降级成「看起来成功的输出」 | 源码实测：`server/llm.py:80-92,140-142`（吞异常）；`server/graph.py:_call_tool` 原实现 `except Exception → TOOL_INTERNAL`。运行期旁证：`/tmp/srv8611.log` 中 6 路并发时 GLM 返回 `429 Too Many Requests` 数十次（SDK 自带重试日志 `Retrying request to /v1/messages`），但每路 `/chat` 仍 `finish=await_user` 且无任何降级标记 | ✅ 已修复（分层重试）：`_call_tool` 区分 `mcp_bridge.ToolError`（业务错误，**不重试**，保「询价次数」类契约）与传输/协议类异常（指数退避重试，`RENEWAL_TOOL_MAX_ATTEMPTS`，默认 3）；测试 `test_tool_retry_transient_vs_business` 断言 3 次 vs 1 次 |
| F2 | **high** | **`_RUN_LOCK` 无效且无必要（文实不符）**：注释声称「串行化对共享 sqlite 连接的图运行 / sqlite3 单连接跨线程写存在竞态 → 用进程内运行锁串行化」。实测该锁只覆盖「生成器对象构造」，`.stream()` 是惰性生成器 → 图执行全在锁外，两路并发流实际并行跑；同时 Saver 内部自带 `threading.Lock`（来源 11）→ 该锁从头到尾没有任何保护作用，只制造安全感 | 探针实测（`/tmp/probe_lock.py`）：`stream()` 返回后立即 `_RUN_LOCK.acquire(blocking=False)` 成功 = `True`；此时 inner 尚未产出 = `True`；两路并发总墙钟 `0.31s`（串行应 ≈0.60s）→ 实际并行。包源码第 74/100/200 行 | ✅ 已修复：删除 `_RUN_LOCK`，注释按包源码事实重写；新增 4 线程共库并发用例 + `test_no_ineffective_run_lock` 防回归 |
| F3 | **high** | **checkpoint 落盘时机未声明 + 递归超限退化成 `INTERNAL`**：① 全链路 `graph.stream/invoke` 未传 `durability`（默认 `async`，来源 2），「确认投保/落单」这类写路径在崩溃窗口内中间态语义不确定；② `app.py` 显式传 `recursion_limit=40`，但 `GraphRecursionError` 未被单独处理，会落到 `except Exception` → SSE `error.code=INTERNAL`，运维无法区分「模型/工具炸了」与「图跑飞了」（来源 1、6 要求显式处理） | 源码实测：`server/app.py:chat()` 仅传 `config={"recursion_limit": 40}`；`graph._ThreadHandle` 无 durability/recursion 兜底。端到端实测（修复前）无法造出超限分支；修复后 `RENEWAL_RECURSION_LIMIT=1` 启动即可复现（见第五节） | ✅ 已修复：`_ThreadHandle` 统一注入 `durability`（`RENEWAL_GRAPH_DURABILITY`，**默认 `sync`**）与 `recursion_limit` 天花板语义（可降不可升，`RENEWAL_RECURSION_LIMIT`）；`_stream_guarded` 把 `GraphRecursionError` 翻译为 `error{code:GRAPH_RECURSION_LIMIT}` + `values{finish_reason:error, exit_reason:recursion_limit}` |
| F4 | **medium** | **未采用官方 HITL 原语**：`await_confirm` 节点只是置 `await_flag` 后 `END`（挂起靠图外状态），次轮从 `START→intake` 重入，在 `retrieve_terms` 分支里凭 `confirmed` 跳到 `confirm`。官方语义是 `interrupt()` + `Command(resume=...)` + 同一 thread_id（来源 4），且 interrupt 前代码会重放——本项目当前「重入即重放」实际靠 idempotent 工具兜住。此外状态真相双写（`sessions.json` 与 checkpoint 两份），`app.py` 仍以 `sessions.load()` 为本轮初始 State | 源码实测：`server/graph.py:await_confirm_node`（置 flag 返回）、`route_after_await_confirm`、`route_after_retrieve_terms` 的 `confirmed → confirm`；`server/app.py:chat()` `session_state = sessions.load(...)` | 📋 未落地（P1，需 SPEC 版本 + 前端/测评协同）：跨轮语义当前有 `tests/test_persistence.py`（10 断言）+ 本轮 25 断言守护，破坏性重构不在本轮强制项；迁移方案见第六节 |
| F5 | **medium** | **无节点级超时**：官方 `add_node(timeout=...)`/`TimeoutPolicy` **只支持 async 节点，给 sync 节点设置会在编译期失败**（来源 3）。本项目 11 个节点全是 sync 函数（在 `run_in_executor` 线程池里被逐 chunk 驱动），因此拿不到节点级 deadline；单节点 LLM 卡死只能靠 SSE keepalive（`: ping`）保连接，无法中断本轮 | 源码实测：`build_graph()` 全部节点为 `def xxx(state)` 同步函数；`app.py` 用 `loop.run_in_executor(None, _next_chunk, stream)` 逐块推进 | 📋 建议 P1：节点改 `async def` 后接 `TimeoutPolicy(run_timeout=...)`；在此之前以 provider 侧 `timeout` + 本域 F1 重试兜底（来源 3、9 的 deadlines 项） |
| F6 | **medium** | **LLM 降级不可观测**：`llm.py` 降级时只改写了文本前缀（`【规则模式兜底：…】`），轨迹 `llm_response` 记录**不含 `mode` 字段** → 「本轮是否真的用了模型」在 traces 里查不到；429 风暴下统计成功率会失真 | 源码实测：`graph._llm_result_trace()` 仅记 `output/tokens_in/tokens_out`；`llm.LLMResult.mode` 未落轨迹。旁证：`/tmp/srv8611.log` 429 数十次而全部 turn 正常返回 | 📋 建议 P1（跨域）：`record_type=llm_response` 增 `mode`（或独立 `llm_degraded` 记录）+ 计数指标。**本轮未改**：`SPEC §5` 轨迹字段属契约，改字段须升 SPEC 并与 platform（Otel/指标）/eval（断言）协同 |
| F7 | **low** | 拓扑无回归断言：前一轮遗留「加一条节点/边快照测试防误改拓扑」未做，`build_graph()` 的 20 条边只能靠人眼比对 SPEC | 源码实测：`tests/` 下无任何 graph 拓扑用例 | ✅ 已修复：`tests/test_orchestration.py::test_topology_snapshot`（11 节点集合 + 20 条 `(source,target,conditional)` 快照），并做敏感度自证（人为错改快照 → 2 条断言翻红） |
| F8 | info | **多智能体编排评估结论 N/A（不引入）**：2026 工程实践里 supervisor/swarm/subgraph 扇出适用于「多专家 + 并行子任务」（来源 7、10）；本项目是单车主、单会话、串行 11 节点的任务型状态机，`compare` 需要的两张报价（原方案/新方案）存在**同一报价服务的幂等窗口**，并行 fan-out 会引入撞号与「询价次数」契约风险 | 业务事实：SPEC §6.2 拓扑 + `eval/cases/AC-05`（询价幂等 1 次）；来源 7、10 的分工前提 | ✅ 结论：暂不引入；若未来做「多车主批量续保」再评估 subgraph/`Send` 扇出 |

## 四、落地改动（changedPaths）

| 文件 | 改动 |
|---|---|
| `server/graph.py` | ① **F1** `_call_tool` 分层重试：`mcp_bridge.ToolError`（业务）立即返回、绝不重试；传输/协议类异常指数退避重试（`TOOL_MAX_ATTEMPTS`，env `RENEWAL_TOOL_MAX_ATTEMPTS`）。② **F2** 删除无效 `_RUN_LOCK`（stream/invoke/get_state 三处 `with` 一并移除），按包源码事实重写并发注释；`_make_checkpointer` docstring 同步更正。③ **F3** 新增 `GRAPH_DURABILITY`（env `RENEWAL_GRAPH_DURABILITY`，默认 `sync`）与 `RECURSION_LIMIT`（env `RENEWAL_RECURSION_LIMIT`，默认 40），`_ThreadHandle._config` 注入 thread_id + recursion_limit（天花板语义：`max(1, min(asked, RECURSION_LIMIT))`）、`stream/invoke` 注入 durability。④ **F3** 新增 `_stream_guarded`：`GraphRecursionError` → 协议内 `error{code:GRAPH_RECURSION_LIMIT}` + 终态 `values{finish_reason:error, exit_reason:recursion_limit}`。⑤ `_ThreadHandle` docstring 重写为「编排执行入口」并写明三项职责与并发结论 |
| `tests/test_orchestration.py`（新增） | 6 组 / 25 条断言：拓扑快照（F7）、执行期参数注入含天花板钳制（F3）、`GraphRecursionError` 翻译（F3）、工具重试分层（F1）、4 线程共库并发 + thread 隔离（F2）、`_RUN_LOCK` 防回归。脚本方式与 pytest 均可运行（不在模块层 `sys.exit`） |

兼容性：`app.py` 与 `eval/run.py` **零改动**——`_ThreadHandle` 仍是 `stream/invoke/get_state` 三方法契约，`durability` 走 `kwargs.setdefault` 不覆盖调用方显式值；SSE 事件集未新增类型（`error`/`done` 均为 SPEC §4.1 既有事件），错误码新增取值 `GRAPH_RECURSION_LIMIT`（SPEC 未枚举错误码全集，属新增取值而非破坏）。

## 五、验证证据（2026-11-17 实测，命令 + 输出）

```bash
# 1) 编排域单元测试（新增）
$ .venv/bin/python tests/test_orchestration.py
[1] 拓扑快照（11 业务节点 + 边/条件边）
  ✓ 业务节点集合 = ['await_confirm','clarify','compare','confirm','fallback','get_policy',
                    'intake','parse_needs','quote','retrieve_terms']（期望 11 个，SPEC §6.2）
  ✓ 快照中的边全部存在（缺失 []）
  ✓ 没有快照外的隐式新边（新增 []）
  ✓ 边快照条数 = 20（20）
[2] _ThreadHandle 注入 thread_id / recursion_limit / durability      ✓ ×8（含天花板钳制）
[3] GraphRecursionError → 协议内 error 事件（不退化成 INTERNAL）      ✓ ×4
[4] _call_tool 重试：瞬时故障重试、业务错误不重试
  ✓ 瞬时故障重试到成功：attempts = 3（期望 3）
  ✓ 业务错误不重试：attempts = 1（期望 1）
[5] 多线程并发驱动同一 SqliteSaver（无全局串行锁也能安全）            ✓ ×4
[6] 防回归：无效的进程级 _RUN_LOCK 不得被重新引入                      ✓
通过 25 / 25     # EXIT=0
$ .venv/bin/python -m pytest tests/test_orchestration.py -q   → 6 passed

# 2) 快照敏感度自证（人为错改快照，断言必须翻红）
$ .venv/bin/python - <<'PY'   # 去掉一条真实边 + 加一条伪边后重跑 test_topology_snapshot
  ✗ 快照中的边全部存在（缺失 [('intake', 'confirm', True)]）
  ✗ 没有快照外的隐式新边（新增 [('compare', 'await_confirm', False)]）
敏感度验证：FAIL=2

# 3) 既有套件无回归
$ .venv/bin/python tests/test_persistence.py            → 通过 10 / 10
$ .venv/bin/python tests/test_llm_normalization.py      → 结果：15 通过 / 0 失败
$ .venv/bin/python -m pytest tests/test_security.py -q  → 13 passed

# 4) F2 探针（修复前）：锁未覆盖图执行
1) stream() 返回后立即抢 _RUN_LOCK 成功 = True
2) 此时图尚未执行（inner 未产出）: True
3) 两个并发流总墙钟 0.31s（串行应≈0.60s，并行≈0.30s）
4) inner.stream 被调用次数 = 2

# 5) 端到端：跨轮确认链路 + 4 路并发（独立端口 8612，实 LLM 模式）
$ RENEWAL_RATE_LIMIT_PER_MIN=100000 .venv/bin/python -m uvicorn server.app:app --port 8612 &
$ curl -s localhost:8612/health
{"status":"ok","llm_mode":"llm","wiki_entries":8,"graph":"langgraph","nodes":11}
== 1) 跨轮确认链路（本轮 quote → 次轮确认 → confirmed）==
   t1: events=27 quote×1 finish=await_user
   t2: confirmed×1 finish=end
   跨轮语义: PASS
== 2) 4 路并发（删除全局锁后仍无异常）==
   墙钟 4.1s  异常=[]
   #0..#3 events=27 quote=True finish=await_user
   并发语义: PASS

# 6) durability=sync 落盘核验（SQLite checkpoint 表）
   thread orch-confirm: checkpoint 行数=16 最新=1f1e23bf-…
   thread orch-conc-0 : checkpoint 行数=9  最新=1f1e23c0-…
   thread orch-conc-1 : checkpoint 行数=9  最新=1f1e23c0-…

# 7) 端到端：recursion_limit 触顶 → 协议内错误码（独立端口 8613，规则模式）
$ RENEWAL_RECURSION_LIMIT=1 RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python -m uvicorn server.app:app --port 8613 &
   error 事件: [{'code': 'GRAPH_RECURSION_LIMIT', 'message': '图执行超过 superstep 上限，本轮已中止：
                Recursion limit of 1 reached without hitting a stop condition. …'}]
   done: {'trace_id': 'trc-20261117120512-drcjn0', 'finish_reason': 'error'}
   判定: PASS        # 修复前该路径只会得到 error.code=INTERNAL（app.py 兜底 except）

# 8) 全量评测回归（独立端口 8614，实 LLM 模式）
$ .venv/bin/python eval/run.py --port 8614
--- AC-05 … AC-14、SEC-01 … SEC-05 逐例 PASS（输出略，原文见报告）---
=== 评测完成：19/19 PASS，hard 失败 0 条，总耗时 54.1s ===
报告：eval/report-20261117-120517.md
```
> 已在**最终代码状态上复跑确认**（独立端口 8615，新增只有 `dispatch` 类型注解）：`19/19 PASS，hard 失败 0，54.7s`，报告 `eval/report-20261117-120728.md`。
评测回归：19/19 PASS（hard 失败 0），说明本轮编排改动**未改变任何业务可观测行为**——这也符合预期：F1 只在故障路径生效、F3 只改落盘时机与超限错误码、F2 只删了无效锁。

> 评测框架自身的 `--diff` 提示「基线模式=rule vs 本次=llm：不可比」——这是 eval 域（McNemar 成对检验，`eval/README-eval.md`）的跨模式基线保护，不是本轮编排改动造成的；LLM 模式下仍能全绿正是 F1/F6 描述的「静默降级」在起作用（provider 429 时回到规则模式且无标记）。
>
> 跨域观察（非本域）：CI 门禁 `mypy`（`pyproject.toml [tool.mypy] files=` 只含 config/middleware/sessions/trace）当前在 `server/metrics.py` 上报 11 处错误 → CI 的 mypy 步骤会红；`server/graph.py` 本就不在门禁文件列表内（注释：「业务图的动态 State 暂不纳入」），本轮把 `_call_tool` 的分发表补上 `dict[str, Callable[..., dict]]` 注解后其 mypy 错误 18 → 17。

测试服务（8611/8612/8613/8614/8615）均已关闭（端口探测全 closed）；常驻 8000 未被本域触碰——评审期间 `ps aux | grep [u]vicorn` 在收尾时已无任何进程（8000 在开工时即无常驻实例，非本轮所致）。

## 六、结论与遗留

**结论**：编排域的「状态机骨架 + 官方持久化」在上一轮已达标（拓扑与 SPEC §6.2 一致、checkpoint 跨进程可读）；本轮真正的缺口不在图设计，而在**执行期语义**——① 三层 `except Exception` 把故障与业务错误一起吞掉，使 2026 官方韧性原语（RetryPolicy）结构性失效（F1）；② 落盘时机与递归超限两个「静默不确定」没有显式声明（F3）；③ 一个名声与实际不符的全局锁（F2）；④ 骨架级回归保护缺失（F7）。前四项已落地并有断言守护，域评分 **7.0 → 8.3**。

**遗留（按优先级）**：

1. **P1 收敛双写（状态真相）**：`app.py` 仍以 `sessions.load()` 构造本轮初始 State，checkpoint 只是「影子真相」；迁移路径：`app.py` 改为 `get_graph().get_state(thread_id)` 取上下文 → `sessions.py` 退化为历史归档（文件头已留废弃计划）。需同时回归 `/chat` 全链路 + eval 19 例（14 AC + 5 SEC）。
2. **P1 引入官方 HITL 原语**：`await_confirm` 改 `interrupt(payload)` + 次轮 `Command(resume=...)`，仍需同一 `thread_id`（来源 4）；前置条件：SPEC 升版（`await_user` 语义不变但内部实现变更）+ 前端「确认」交互契约确认 + eval AC-06/AC-13 断言复核。
3. **P1 节点级超时（deadline）**：需节点 `async` 化后启用 `TimeoutPolicy`（来源 3，本项目 sync 节点编译期不支持）；在此之前以 F1 重试 + provider timeout 兜底。
4. **P1 降级可观测（跨域）**：`llm_response` 轨迹增 `mode`/`llm_degraded` 记录 + 计数指标；须与 SPEC §5、platform（OTel GenAI）、eval（断言）协同，本轮未动契约字段。
5. **P2 持久化后端**：SQLite 仅本地/单机（来源 8），多副本生产换官方 PostgresSaver；`_cleanup_old_checkpoints` 的 30 天保留策略已在位。
6. **待验证**：`interrupt()` 在本项目「SSE 逐帧流式 + 线程池驱动」形态下的中断/恢复行为（是否出现半帧、是否需要 `stream_events` v3 API）未实测——迁移时必须先做原型，不得直接改主线。

---

## 七、F6 落地：LLM 静默降级可观测化 + 严格模式（t11，2026-11-17）

> 本节是本报告 F6（P1「LLM 降级不可观测」）的闭环。触发者不是本域自测，而是**评测域 t7 的实测**：
> `.env` 指向的 glm-4.6 因额度失效持续 429，`server/llm.py` 静默回退规则模式且仍返回 200，
> 一轮对话 11 次 `llm_response` 全是规则兜底，评测与 CI 却全绿——**故障被伪装成成功**。

### 7.1 根因：三条「异常 → 回退 → 仍 200」的路径（不止一条）

| # | 位置 | 旧行为 | 后果 |
|---|---|---|---|
| S1 | `LLMClient.chat()`（compare / fallback 节点用） | `except Exception` → 返回 `mode="rule"` 文本，仅改文案前缀 | 建议/条款回答变成模板文，**SSE 与轨迹都看不出** |
| S2 | `LLMClient.chat_tool_json()`（parse_needs 用） | `except Exception` → `(None, None)` | 需求解析静默降级为关键词规则，**连 llm_response 行都不写** |
| S3 | `LLMClient.stream_chat()`（token 流式通道） | `except Exception` → 逐字符吐规则文本 | 同上，且事后无法区分 |
| S4 | 调用点 `graph.py` | `_llm_result_trace()` 只记 `output/tokens_*`，**不记 `mode`** | 即便想事后取证，轨迹里也没有「是否真的用了模型」 |
| S5 | `/chat` 路由 | 无任何开流前检查 | 严格语义缺失：不可能"失败就是失败" |

关键结构性原因与 F1 同源：**内层 `except Exception` 把故障吸收成"正常返回值"**，于是任何图级/框架级韧性手段都不会触发，可观测性也无从谈起。

### 7.2 改动（changedPaths）

| 文件 | 改动 |
|---|---|
| `server/llm.py` | 新增 `LLM_UNAVAILABLE` 常量、`LLMUnavailableError`（带 `node/error_type/message`）、`LLMResult.degraded/error_type/error_message`；新增 `_on_failure()`（登记 + 严格模式抛错）、`_degraded_text()`、`preflight()`（严格模式开流前探活，成功结果缓存 30s，探活本身关掉 SDK 重试）；`chat`/`chat_tool_json`/`stream_chat` 三个失败分支全部改为「登记降级 → 严格模式抛错 / 宽松模式带 `degraded=True` 返回」；三方法增加 `node` 形参（降级记录带真实节点名）。**`available=False`（无凭证 / `RENEWAL_FORCE_RULE_MODE=1`）保持不打标记**——那是配置选择的规则模式，不是故障降级 |
| `server/graph.py` | `RenewalState` 增 `llm_degraded`；`_llm_result_trace()` 增 `mode` + `degraded` + `error_type`；新增 `_llm_event()`（发既有 `llm_response` + 降级时追加 `llm_degraded` 事件与轨迹，返回标记）；三个 LLM 调用点（parse_needs / compare / fallback）改用该助手并传真实 node 名；`_stream_guarded()` 增 `except LLMUnavailableError` → `error{code=LLM_UNAVAILABLE}` + `values{finish_reason=error, exit_reason=llm_unavailable}` |
| `server/app.py` | `/chat` 增加依赖 `strict_llm_guard`（严格模式探活在**响应开始前**执行 → 失败走异常处理器回 **HTTP 503 + `LLM_UNAVAILABLE`**，这是"非 200"唯一可靠实现方式，SSE 一旦开流状态码不可回改）；SSE 生成器增 `except LLMUnavailableError`（开流后失败）→ `error{LLM_UNAVAILABLE}` + `done{finish_reason=error}`；`done` 帧增可选字段 `degraded`；`/health` 增 `llm_strict` / `llm_degraded_total` |
| `server/trace.py` | `record()` 增可选字段 `mode/degraded/error_type`（不传则不出现，向后兼容）；`RECORD_TYPES` 增 `llm_degraded`；模块 docstring 同步（原文写"禁止自创字段"，现按 SPEC v1.0.5 登记） |
| `server/config.py` | 新增 `llm_strict()`（`RENEWAL_LLM_STRICT=1/true/yes/on`） |
| `tests/test_llm_degradation.py`（新增） | 7 组 / 27 断言：宽松留痕、tool_json 降级、严格抛错、显式规则模式不误报、`_llm_event` 双标记、`_stream_guarded` 翻译、探活（含非严格模式零额外调用） |
| `SPEC.md` → **v1.0.5** | §4.1 新增 `llm_degraded` 事件 + `done.degraded` + `error.error_type`；**新增 §4.6「LLM 降级可观测与严格模式」**；§5 新增 `mode/degraded/error_type` 字段与 `llm_degraded` 记录类型；§8 版本记录写明**全部为追加式变更、默认配置下对外行为不变** |

契约影响：**新增事件/字段均为可选追加**，旧客户端忽略未知事件即可；19 条评测用例与既有 12 类 SSE 事件语义不变。

### 7.3 验证证据（实跑，独立端口；真实 `.env` 未读未改）

故障注入方式：进程级环境变量覆盖（`ANTHROPIC_BASE_URL=http://127.0.0.1:9` + 假 token），跑完即弃。

```bash
# ① 单元：27/27
$ .venv/bin/python tests/test_llm_degradation.py
  [1] 宽松模式：失败 → degraded=True（含原因与错误类型）        ✓×5
  [2] chat_tool_json 失败 → (None, 带 degraded 的 LLMResult)    ✓×3
  [3] 严格模式：失败 → 抛 LLMUnavailableError（不返回兜底文本）  ✓×4
  [4] 显式规则模式（无凭证）：不是降级，严格模式也不报错        ✓×3
  [5] _llm_event → llm_response(mode=rule) + llm_degraded        ✓×6
  [6] LLMUnavailableError → error{LLM_UNAVAILABLE} + 终态 error  ✓×3
  [7] 探活：provider 不可达 → ok=False；非严格模式 skipped       ✓×3
通过 27 / 27   # EXIT=0

# ② 端到端（宽松模式，8621，provider 不可达）——SSE 证据
   HTTP=200 事件数=30
   llm_response: [('parse_needs','rule'), ('compare','rule')]
   llm_degraded: [('parse_needs','LLM_UNAVAILABLE','APIConnectionError'),
                  ('compare','LLM_UNAVAILABLE','APIConnectionError')]
   done: {'trace_id': 'trc-20261117121514-cz25o7', 'finish_reason': 'await_user', 'degraded': True}

# ② 轨迹 JSONL 证据（同一次对话）
   {'seq': 11, 'record_type': 'llm_response', 'node': 'parse_needs', 'mode': 'rule', 'degraded': True, 'error_type': 'APIConnectionError'}
   {'seq': 12, 'record_type': 'llm_degraded', 'node': 'parse_needs', 'degraded': True, 'error_type': 'APIConnectionError'}
   {'seq': 23, 'record_type': 'llm_response', 'node': 'compare',     'mode': 'rule', 'degraded': True, 'error_type': 'APIConnectionError'}
   {'seq': 24, 'record_type': 'llm_degraded', 'node': 'compare',     'degraded': True, 'error_type': 'APIConnectionError'}

# ③ 端到端（严格模式，8622，同一故障注入）
$ env RENEWAL_LLM_STRICT=1 ... uvicorn --port 8622 &
$ curl -s /health
{"status":"ok","llm_mode":"llm","llm_strict":true,"llm_degraded_total":0,...}
   POST /chat → HTTP=503（0.1s）  Content-Type: application/json
   {"error": {"code": "LLM_UNAVAILABLE",
              "message": "LLM 不可用（APIConnectionError）：Connection error.；严格模式不允许静默降级（RENEWAL_LLM_STRICT=1）"}}
   判定: PASS   # 非 200，且错误码明确

# ④ 反例回归：显式规则模式（8623，RENEWAL_FORCE_RULE_MODE=1）不得误报降级
   HTTP=200 events=24   llm_response: []   llm_degraded: []
   done: {'finish_reason': 'await_user', 'degraded': False}   → PASS

# ⑤ 回归全绿
$ .venv/bin/python tests/test_orchestration.py            → 通过 25 / 25
$ .venv/bin/python -m pytest tests/ mcp_servers/          → 83 passed, 2 skipped
$ .venv/bin/python -m ruff check .                        → All checks passed!
$ RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python eval/run.py --port 8631
  → === 评测完成：19/19 PASS，hard 失败 0 条，总耗时 1.8s ===
  → 回归基线对比：退化翻转 b=0 / 修复翻转 c=0，单侧 p=1 → ✅ 无显著退化
```

### 7.4 与 t7 结论的对应关系（该缺陷现在会怎样表现）

| 场景 | t7 实测（修复前） | 修复后（宽松模式，默认） | 修复后（`RENEWAL_LLM_STRICT=1`） |
|---|---|---|---|
| provider 429 / 连接失败 | 200 + 规则兜底，`llm_response` 无 `mode` 字段 → **完全不可见** | 200，但每次降级都有 `llm_degraded` 事件 + 轨迹行，`llm_response.mode=rule`，`done.degraded=true` | **HTTP 503 `LLM_UNAVAILABLE`**（开流前探活）或 SSE `error{LLM_UNAVAILABLE}`（开流后） |
| 评测统计「模型成功率」 | 只能看 `tokens_in` 是否为空，间接猜 | 可直接按 `mode=="rule" and degraded` 计数；`/health.llm_degraded_total` 给进程级计数 | 失败即失败，不会污染通过率 |
| CI 门禁 | 全绿但实际未验证模型链路 | 仍全绿（宽松模式不改变结果），但报告/轨迹可查降级次数；**建议 eval 域后续补一条断言：LLM 模式下 `llm_degraded` 出现即告警/失败** | 全红（明确失败）——CI 若要验证真模型链路，应改用严格模式跑 |

**覆盖范围（诚实边界）**：严格模式覆盖 `/chat` 主链路（探活 + 开流后翻译 + done 终态）；
`/confirm`、`/policy`、`/trace` 不调用 LLM，无需覆盖；`stream_chat` 通道目前未被图调用（保留同规处理）。
探活成功缓存 30s，因此最坏情况下严格模式在开流后仍可能遇到故障——此时按 §4.6 只能推 SSE `error`（HTTP 状态已发出，协议上不可回改）。

### 7.5 未纳入本轮的跨域项（t3 → t10）

知识检索域 t3 提出：`retrieve_terms` 在 `evidence_coverage == 0`（引用无 in-corpus 覆盖）时，
应路由到澄清节点（追问或说明知识库未覆盖），而不是给出空引用答案。
**本轮不做**：该改动需要新增 `retrieve_terms → clarify` 条件边（拓扑 + `route_after_retrieve_terms`
分支变更），属状态机语义变更而非"降级可观测"，且会牵动 SPEC §6.2 与 topological 快照测试。
按 captain 口径记为**跨域遗留**，留给 t10 集成评估统一决策（届时需同步更新 `tests/test_orchestration.py`
的 20 条边快照与 SPEC §6.2）。

### 7.6 附带修复（供 t12 lint 门禁）

`server/llm.py::stream_chat` 此前只加了 `node` 的**使用**却漏了**形参**，被 t12 全仓 `ruff`
以 `F821 Undefined name 'node'` 抓到（若无此修复，流式通道一旦降级会 `NameError` 硬崩）。
本轮已补 `node: str = "stream_chat"` 形参；`ruff check .` 现全仓零告警。

### 7.7 跨域协同记录（t12 MCP 域独立复核 + 平台指标建议）

**独立复核（mcp-reviewer-ds，t12）**——非本域自证，属第三方复现：

- `.venv/bin/python -m ruff check .` → `All checks passed!`（exit 0）；`--select F821` 单独跑亦全通过；
- `pytest` → 83 passed / 2 skipped（exit 0）；
- **MCP 域回归**：`pytest tests/test_mcp.py` → 7 passed / 1 skipped，确认协议层语义（`isError` / `ToolError` / `annotations`）未受本轮 LLM 降级改造影响；
- 实读 `server/llm.py:220-226`：`stream_chat(..., node: str = "stream_chat")` 与第 254 行 `self._on_failure(node, exc)` 一致，与 `chat`(159) / `chat_tool_json`(213) 三处形参对齐。

**分层确认（双方一致）**：MCP 侧「工具业务错误 → `isError:true` + content 携带 `{code,message}`」是**协议级错误通道**；
LLM 侧「模型调用失败 → 降级留痕 / 严格模式失败」是**应用级降级**。两者不应共用出口——本轮改造未触碰
`mcp_bridge` 与 `quote_server` 的错误语义，`_call_tool` 的「ToolError 不重试 / 传输类重试」分层保持 t2 的原始意图。

**平台域建议（采纳，记为 P2，不在本轮范围）**：若将来把 `llm_degraded` 接入 `/metrics`，
标签只能用 **低基数维度**（`node` / `error.type`），**禁止**用 `trace_id` / `session_id`（高基数会打爆时间序列）。
该结论来自 t8 平台工程域的 Prometheus 命名实践。当前 `/health.llm_degraded_total` 是聚合计数，不含任何标签，无此风险。
