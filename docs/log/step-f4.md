# step-f4 · F4 集成联调（HTTP/SSE 入口 + E1–E6 端到端）

> 任务：`t12`（attempt 2，`8dabcfb0-9f2e-460f-bd22-cd1c54a61f63`）｜执行：integrate / integrator｜日期：2026-11-18
> 边界：只新增 `claims/api.py`、`claims/demo_claim.py`、`claims/tests/test_f4_api.py`、本文件 + 更新 `docs/log/INDEX.md`。
> **未改** `server/**`、`claims/graph.py`、`claims/deep_agents/**`、`data/llm-wiki-claims/**`
> （证据：`git diff 40541d1 --stat -- server claims/graph.py claims/deep_agents data/llm-wiki-claims` → 空）。
> **结论先行：E1–E6 六条全部真跑通过（8/8 含前置断言与 wiki 汇合）；HTTP/SSE 面用 curl 实测通过。**

---

## 0. 前置断言（A1–A3）

```text
$ export PYTHONPATH=. && .venv-claims/bin/python claims/demo_claim.py 2>&1 | head -6
==============================================================================
F4 端到端 demo  ——  模拟理赔 · 合成数据
==============================================================================
[PASS] A 前置断言（解释器 / wiki / 轨迹隔离）  {"python": "/Users/.../.venv-claims/bin/python",
  "deepagents": true, "wiki_entries": 36, "trace_dir": ".../traces-claims",
  "trace_dir_isolated": true, "traces_before": 1176, "traces_after": 1176}
```

| 断言 | 判据 | 实测 |
|---|---|---|
| A1 解释器 | `.venv-claims/bin/python` 且 `deepagents` 可导入（D-22，否则"假绿"） | `exe=.venv-claims/bin/python`、`deepagents=True` |
| A2 wiki 语料 | `claims.wiki_retrieve.get_searcher().entries > 0`（D-21：空语料抛 `WikiCorpusEmpty`） | `entries=36`、`available=True` |
| A3 轨迹隔离 | 落 `traces-claims/`，且 `traces/` 零新增 | `traces_before=traces_after=1176`（`traces/` 目录条目仍 1183，含 7 个非 jsonl 条目未变） |

> 严格模式（`strict=True`）在 `.venv` 下会直接拒起；单测/演示若要跑规则模式必须显式
> `CLAIMS_ALLOW_RULES_ONLY=1`（见 `claims/api.py::assert_preflight`）。

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 职责 |
|---|---|---|
| `claims/api.py` | **新增**（≈470 行） | FastAPI 应用：`/health`、`/metrics`、`POST /claims/intake`、`GET /claims/{id}`、`POST /claims/{id}/resume`、`POST /claims/{id}/wiki-check`、`GET /claims/{id}/events`（SSE）。含前置断言、SPEC 错误码→HTTP 映射、`ClaimService`（可被 demo/测试直接调用） |
| `claims/demo_claim.py` | **新增**（≈420 行） | CLI 端到端：A 前置断言 + **E1–E6** + **D wiki 汇合**，逐项 PASS/FAIL，退出码即门禁 |
| `claims/tests/test_f4_api.py` | **新增**（8 例） | HTTP 面：前置断言/严格拒起/intake→interrupt→resume→paid/错误码映射（400/409/422）/wiki-check 落轨迹/SSE 重放+done/指标有样本行 |
| `docs/log/step-f4.md` | 新增 | 本文件 |
| `docs/log/INDEX.md` | 更新 | t12 行转"已完成"、§6.1 去掉"无 API/SSE 层"、§4 补 F4 数字 |

**接口一览（真实路径）**：`POST /claims/intake` → `{thread_id, claim_id, status, interrupt, state, http_status}`；
`POST /claims/{id}/resume`（`{decision, comment, reviewer_id}`）；`GET /claims/{id}`（含 `next`）；
`POST /claims/{id}/wiki-check`（`{query, top_k}`）；`GET /claims/{id}/events`（SSE）；`GET /metrics`；`GET /health`。

---

## 2. 关键决策与依据（先检索后动手）

### 2.1 外部来源（≥3，2026-11-18 实际抓取）

| # | 来源 | URL | 检索时间 | 支撑的决策 |
|---|---|---|---|---|
| S1 | FastAPI 官方 · Server-Sent Events 教程（经 Context7 取回 `fastapi.sse` 文档） | https://fastapi.tiangolo.com/tutorial/server-sent-events/ | 2026-11-18 21:47 | 用 **`response_class=EventSourceResponse` + `yield ServerSentEvent(...)`**，而不是手写 `data:` 行；`comment=` 即 keep-alive。**实测本机 `fastapi 0.162.4` 已内置 `fastapi.sse`**（C0 阶段"没有 EventSourceResponse"的旧结论作废，见 §6.1） |
| S2 | LangGraph 官方 · Interrupts（经 Context7 取回） | https://docs.langchain.com/oss/python/langgraph/interrupts | 2026-11-18 21:47 | `Command(resume=...)` **必须用同一 thread_id**，被中断节点从函数开头重跑 → 因此 HTTP 层的 `thread_id` 必须**先于 invoke 就确定**（见 §6.2 的真实缺陷） |
| S3 | sse-starlette README（生产实现） | https://github.com/sysid/sse-starlette | 2026-11-18 21:49 | 客户端断连检测、`ping`/keep-alive 防代理超时、`X-Accel-Buffering: no`；本次采用"comment 心跳 + 短跟随"，不引入新依赖 |

### 2.2 接口实读（不靠记忆）

- `ClaimGraph.invoke(claim_input, *, thread_id)` / `resume(decision, *, thread_id)` / `state(thread_id=...)`：`claims/graph.py:611-640`（含 I6-a/I6-b 的终态守卫：终态线程再 invoke 返回 `terminal=True` + `CLAIM_STATE_INVALID`）。
- `ClaimGraph.recorder(state, claim_id)`：`claims/graph.py:166`（按 claim 缓存 + 跨进程续号）→ `wiki-check` 复用它写 `record_type="retrieval"` 行。
- `claims.wiki_retrieve.retrieve(query, top_k)` 返回 `{hits, citations{total,ok,strict,rate}, grounding_rate, abstained, corpus}`（`claims/wiki_retrieve.py:471-496`）。
- `server.metrics.render()`（`server/metrics.py:243`）+ `server/trace.py:150` 的 `observe_record(row)` → **轨迹写一行，指标自动有一笔**，故 `/metrics` 不是空壳。
- 错误码表：`claims/state.py::ErrorCode`（14 项）与 SPEC §5 的 HTTP 状态列一一对应；`ERROR_HTTP` 是唯一映射点。

### 2.3 三个关键取舍

1. **`thread_id` = `claim_id`，且在 invoke 之前算好**：`claim_id` 由 SPEC §3.1 的
   `sha256(owner|policy|occurred_at|location)[:8]` 决定，是确定性的 → `ClaimService.claim_id_for()`
   先复算，再 `invoke(..., thread_id=claim_id)`。这样 `resume` 天然同线程（S2 的硬约束）。
2. **SSE = 重放 + 短跟随，不是常驻订阅**：`GET /events` 先重放已落盘轨迹（客户端拿到完整历史），
   未终态时最多跟随 `follow` 秒（默认 0，最大 30），期间每 0.2s 发一条 `comment: keep-alive`（S3）。
   好处：无状态、可水平复制、测试确定性；代价：**不是**实时 tail（见 §7 遗留）。
3. **不新增 record_type / 不新增 SSE event 名**（D-08）：SSE 的 `event:` 直接取行的
   `record_type`（11 种白名单），仅额外加一个终态哨兵 `event: done`；理赔语义仍在 `data.event.kind`
   （`claims.*`）。

---

## 3. E1–E6 逐场景（命令 + 输出原文）

统一入口：`export PYTHONPATH=. && .venv-claims/bin/python claims/demo_claim.py`
（`--only E5` 可单跑；`--json` 输出机器可读汇总）

### 3.1 总览（一次跑完）

```text
$ export PYTHONPATH=. && .venv-claims/bin/python claims/demo_claim.py 2>&1 | tail -4
==============================================================================
总计 8 项，PASS 8，FAIL 0，耗时 0.16s
```

### 3.2 E1 报案 → 核验 → 审核（interrupt）→ approve → 支付 → 完成

```text
[PASS] E1 报案→核验→审核→支付→paid  {"claim_id": "CLM-20261101-e5fbc58d", "interrupt": true,
 "status_intake": "review_pending", "status_final": "paid", "payable_amount": 2100.0,
 "charge_count": 1, "trace_file": ".../traces-claims/CLM-20261101-e5fbc58d.jsonl",
 "trace_rows": 42, "record_types": ["node_end","node_start","tool_call","tool_result"],
 "kinds": ["claims.intake_accepted", ..., "claims.review_requested", "claims.review_approved",
           "claims.payment_key_reserved", "claims.payment_charge", "claims.payment_charged",
           "claims.closed", ...]}
```

- 判据全部成立：中断发生、终态 `paid`、`charge_count=1`、轨迹文件存在且 `record_type ⊆ 11 种白名单`。
- 金额链路可核：定损 1200+800+600=2600 − 免赔 500 = **2100.0**，由 `claims/tools/logic.py::assess_amount` 服务端计算。

### 3.3 E2 跨进程恢复（A 停在 interrupt → B 新实例同 DB resume）

```text
[PASS] E2 跨进程恢复（新实例同 DB resume）  {"claim_id": "CLM-20261102-63d1ade4",
 "process_A_charge": 0, "process_B_charge": 1, "total_charge": 1,
 "status_before_resume": "review_pending", "status_after_resume": "paid"}
```

- `charge` **总计 1 次**（A 进程 0 + B 进程 1）；A 关闭 sqlite 连接后 B 用同一 DB 读回 `review_pending`。

### 3.4 E3 重复提交幂等

```text
[PASS] E3 重复提交幂等（不再 charge）  {"claim_id": "CLM-20261103-674819eb",
 "status_first": "paid", "status_second": "paid", "second_terminal": true,
 "second_error_codes": ["CLAIM_STATE_INVALID"], "charge_first": 1, "charge_after_repeat": 1}
```

- 第二次 invoke 直接返回终态快照 + `CLAIM_STATE_INVALID`（D-17），**没有再次 charge**。

### 3.5 E4 reject 路径

```text
[PASS] E4 reject → rejected，无支付  {"claim_id": "CLM-20261104-af56d2b9",
 "status_final": "rejected", "charge_count": 0,
 "has_review_rejected": true, "has_payment_charged": false}
```

### 3.6 E5 支付超时 → 查单（不重发）

```text
[PASS] E5 支付超时→查单（不重发）  {"claim_id": "CLM-20261105-a3acd452",
 "status_final": "paid", "charge_count": 1, "gateway_ops": ["charge", "query"],
 "has_payment_unknown": true, "has_payment_reconciled": true}
```

- `charge` 只被调用 **1 次**（超时后**不重发**），随后 `query` 查单一次并确认成功 → `paid`。

### 3.7 E6 降级路径（`DEEPAGENTS_ENABLED=false`）

```text
[PASS] E6 降级路径（rules_fallback + error_type）  {"claim_id": "CLM-20261106-7f0a31ba",
 "analyzer_mode": "rules_fallback", "analysis_degraded": true, "degraded_rows": 2,
 "error_type": "DeepAgentsDisabled", "error_class": "", "mode_field": "rules_fallback",
 "code": "ANALYSIS_UNAVAILABLE"}
```

- 轨迹里 `claims.llm_degraded` 行**带 `error_type="DeepAgentsDisabled"`**（D-16 落实，不是 `Unknown`）。

---

## 4. 两条流水线汇合（D）：问题 → wiki 页 → raw 引用

### 4.1 CLI（`demo_claim.py --only D`）

```text
[PASS] D wiki 汇合（问题→页→raw 引用，且落轨迹）  {"claim_id": "CLM-20261107-c5cbe7fd",
 "query": "农业保险赔付档位怎么确定",
 "top_hit": {"wiki_id": "claims-faq-agri", "title": "农业保险赔付档位如何确定？",
             "anchor": "claims-faq-agri", "span": "# 农业保险赔付档位如何确定？\n\n> 本页只回答…",
             "verbatim": true},
 "hits": 3, "grounding_rate": 1.0, "abstained": false, "trace_retrieval_rows": 2}
```

### 4.2 HTTP（`POST /claims/{id}/wiki-check`，服务跑在 8131）

```text
$ curl -s -X POST http://127.0.0.1:8131/claims/CLM-20261109-e7ac0260/wiki-check \
       -H 'content-type: application/json' -d '{"query":"农业保险赔付档位怎么确定","top_k":3}'
hits= 3
top= claims-faq-agri | anchor= claims-faq-agri | verbatim= True
citations= {'total': 101, 'ok': 101, 'strict': 95, 'rate': 1.0, 'strict_rate': 0.941}
trace_row.kind= claims.wiki_retrieved
```

- **101 条引用全部可回溯（ok=101/101）**，其中 95 条达到逐字级（`strict_rate=0.941`）。
- 命中页 id / anchor / span / citations **写进轨迹**（`record_type="retrieval"`，白名单内）；
  若检索拒答或空语料，`abstained/degraded` 会显式落痕（`claims/api.py::ClaimService.wiki_check`），不静默跳过。

---

## 5. 验收命令（E）——四条全部实测

```text
# ① CLI 端到端
$ export PYTHONPATH=. && .venv-claims/bin/python claims/demo_claim.py
总计 8 项，PASS 8，FAIL 0，耗时 0.16s

# ② 续保基线（零回归）
$ .venv/bin/python -m pytest -o addopts="" -q
148 passed, 2 skipped in 1.56s

# ③ 理赔两套测试（含新增 8 例 F4 HTTP 测试）
$ .venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
168 passed in 5.62s

# ④ 指标不是空壳（真起 uvicorn + curl）
$ curl -s http://127.0.0.1:8131/metrics | grep -c 'renewal_'
130
$ curl -s http://127.0.0.1:8131/metrics | grep -E '^renewal_(chat_requests_total|tool_calls_total|llm_requests_total)' | head -1
renewal_tool_calls_total{node="execute_payment"} 1
```

HTTP 面完整链路（真起服务，端口 8131）：

```text
$ curl -s http://127.0.0.1:8131/health
{"ok": true, "preflight": {"python": ".../.venv-claims/bin/python", "deepagents": true,
 "wiki_entries": 36, "trace_dir": ".../traces-claims", "trace_dir_isolated": true, ...}}

$ curl -s -X POST .../claims/intake -d @payload.json
{"thread_id": "CLM-20261109-e7ac0260", "claim_id": "CLM-20261109-e7ac0260",
 "status": "review_pending", "interrupt": {"kind": "claim_review", "payable_amount": 2100.0,
 "line_items": [{"name": "前保险杠", "amount": 1200.0, "evidence": {"doc_id": "doc-0002",
 "span": "L1", "quote": "前保险杠：1200元"}}, ...], "allowed_decisions": ["approve","reject"],
 "synthetic": true}, "http_status": 200}

$ curl -s -X POST .../claims/CLM-20261109-e7ac0260/resume -d '{"decision":"approve",...}'
{"claim_id": "CLM-20261109-e7ac0260", "status": "paid", "interrupt": null,
 "state": {..., "payment_key": "pay-319aed641713ef6ca44b8d846128d457",
           "payment_id": "PAY-70b1d27c70", "approval_version": 1, "approval_mode": "manual"}, "http_status": 200}

$ curl -s -N .../claims/CLM-20261109-e7ac0260/events | head -4
event: node_start
data: {"seq": 1, "record_type": "node_start", "node": "intake", "event": {"kind": "claims.intake_accepted"}, ...}
id: 1
event: node_end
data: {"seq": 2, "record_type": "node_end", "node": "intake", "latency_ms": 0.351, ...}
```

### 5.1 一次完整轨迹片段（E1，`traces-claims/CLM-20261101-e5fbc58d.jsonl`）

> ⚠️ **下面引的 `42` 是 2026-11-18 23:06 那一刻的快照，不是固定值。**
> 轨迹是**只追加**的：同一个 demo payload 每次跑都得到**同一个 `claim_id`**（SPEC §3.1 确定性），
> 于是每轮事件都追加进同一个文件。行数随运行次数线性增长——读法见 §5.2。

```text
$ wc -l traces-claims/CLM-20261101-e5fbc58d.jsonl        → 42   （← 2026-11-18 23:06 快照；现已不是 42）
$ head -2 ...
{"ts": "2026-11-18T23:05:55.229+08:00", "trace_id": "CLM-20261101-e5fbc58d", "session_id": "sess-f4",
 "seq": 1, "record_type": "node_start", "node": "intake", "event": {"kind": "claims.intake_accepted"},
 "input": null, "output": null}
{"ts": "...", "seq": 2, "record_type": "node_end", "node": "intake", "event": null, ...,
 "latency_ms": 0.4229}
$ tail -2 ...
{"ts": "...", "seq": 41, "record_type": "node_start", "node": "finalize",
 "event": {"kind": "claims.closed", "payment_id": "PAY-aae691a6d8"}, ...}
{"ts": "...", "seq": 42, "record_type": "node_end", "node": "finalize", ..., "latency_ms": 0.06}

$ python3 -c "…统计…"
Counter({'node_start': 19, 'node_end': 19, 'tool_call': 2, 'tool_result': 2})
可回溯字段齐备: True     seq 连续: True
```

> 42 = 当时两次运行（首次 20 行 + 第二次 22 行）的累加；第二次多出的 2 行是同 payload 触发 `claims.intake_duplicate` 的事件。
> `seq` 跨进程续号（`graph.recorder()` 先数已有行再续），所以 seq 是**全文件单调递增**的。

### 5.2 轨迹是“追加式”的（读之前必看）

**实测（2026-11-19 01:53）**：同一个文件已经变成 **162 行 / 8 轮**：

```text
$ python3 -c "…按 claims.intake_accepted 切轮…"
rows= 162  rounds= 8
starts(0-based)= [0, 22, 42, 62, 82, 102, 122, 142]
每轮行数= [22, 20, 20, 20, 20, 20, 20, 20]
每轮 seq 起点= [1, 23, 43, 63, 83, 103, 123, 143]
```

**为什么增长**：① `claim_id` 由 `sha256(owner|policy|occurred_at|location)[:8]` 确定性推出（SPEC §3.1）；
② `TraceRecorder` 以 `trace_id=claim_id` 命名文件且**只追加不截断**（D-08 / C0 基线§4）；
③ `seq` 续号而不是重置。于是“跑 N 次 demo → 同一个文件 N 轮”。

**这是设计使然，不是 bug**：审计日志一旦被截断，“可重放/可回溯”就不成立（CLM-20 的前提）。
本次**没有**修改追加行为、也不清理历史轨迹（写作用域明确排除 `traces-claims/**`）。

**因此 E1 的断言判据是「结构」而不是「行数」**（`claims/demo_claim.py`）：

| 断言 | 判据 | 会/不会受累加影响 |
|---|---|---|
| `record_type ⊆ 11 种白名单`（直接对 `server.trace.RECORD_TYPES` 取子集） | 结构 | 不受 |
| `kinds` 必含 `claims.review_requested` / `claims.review_approved` / `claims.payment_charged` / `claims.closed` | 结构（集合包含） | 不受 |
| `payable_amount == 2100.0`、`charge_count == 1`、`status == paid` | 业务值 | 不受（每轮独立 gateway/DB） |
| `seq 连续`（另写脚本校验：`rows[i]['seq'] == i+1`） | 结构 | 不受（全文件单调） |
| **行数 `== N`** | —— | **demo 里没有任何行数断言**（`grep -n "trace_rows\\|rows ==\\|len(rows)" claims/demo_claim.py` 只命中 **detail 上报字段**，不参与 `ok` 判定） |

**怎么从轨迹分辨单轮边界**（三种，任选）：

```bash
# ① 按 intake_accepted 切轮（最直观：每次报案恰好一条）
python3 - <<'PY'
import json
rows=[json.loads(l) for l in open('traces-claims/CLM-20261101-e5fbc58d.jsonl')]
k=[(r.get('event') or {}).get('kind') for r in rows]
starts=[i for i,x in enumerate(k) if x=='claims.intake_accepted']
for n,s in enumerate(starts,1):
    e = starts[n] if n < len(starts) else len(rows)
    print(f'round {n}: 行 {s+1}..{e}  seq {rows[s]["seq"]}..{rows[e-1]["seq"]}  终态={rows[e-1]["event"]}')
PY

# ② 看 seq 区间：每轮 seq 起点 = 上一轮末尾 +1（本例 1/23/43/63/83/103/123/143）
# ③ 看 claims.closed（每轮一条）与 claims.payment_charged 配对定位结尾
```

**连跑两次的实测（2026-11-19 01:5x，这是本任务的幂等性证据）**：

```text
# 跑前：E1 轨迹 162 行 / 8 轮
$ PYTHONPATH=. .venv-claims/bin/python claims/demo_claim.py     # 第 1 次
总计 8 项，PASS 8，FAIL 0，耗时 0.12s        exit=0
# → E1 轨迹 182 行，E1 上报 "trace_rows": 182

$ PYTHONPATH=. .venv-claims/bin/python claims/demo_claim.py     # 第 2 次
总计 8 项，PASS 8，FAIL 0，耗时 0.11s        exit=0
# → E1 轨迹 202 行 / 10 轮，E1 上报 "trace_rows": 202

$ python3 -c "…逐轮切分 + seq 校验…"
rows= 202  rounds= 10
每轮行数= [22, 20, 20, 20, 20, 20, 20, 20, 20, 20]    ← 每次运行恰好 +20 行
seq 连续 = True                                        ← 从 1 到 202 无缺口
```

**两次都 PASS 8 / FAIL 0**：行数从 162→182→202（+20/次）但**没有任何断言因此变红**，
这正好反向证明“判据是结构不是行数”。`trace_rows` 只出现在 detail JSON 里，供人看，不参与 `ok` 计算。

**一句话结论**：**“轨迹行数随运行次数增长”是设计使然，不需要改**（审计只追加 + 确定性 claim_id）。
唯一的例外是**文档**：任何把“行数”写成固定事实的句子都会误导读——已在本节与 §5.1 标注快照口径，
并明确“判据是结构不是行数”。**不需要改代码**（本次 `claims/demo_claim.py` **零修改**）。

---

## 6. 失败与修复记录

### 6.1 旧结论作废：`fastapi.sse` 在本机可用

C0 阶段的评审记录里写过"`EventSourceResponse` 是新版专属 API，故用手写 `StreamingResponse`"。
本次实测 `fastapi 0.162.4` → `from fastapi.sse import EventSourceResponse, ServerSentEvent` **可用**，
因此 F4 直接用官方 SSE 类（S1），不再手写 `data:` 行。**旧结论仅对旧版本成立**。

### 6.2 自研缺陷（本任务内发现并修）：`thread_id ≠ claim_id` 导致 HTTP resume 永不成功

- **现象**：`test_intake_interrupt_approve_paid_via_http` 第一次跑就红——`GET /claims/{id}` 的
  `next` 是 `[]`（应为 `["review_gate"]`），`POST /resume` 返回 **409**。
- **根因**：`ClaimService.intake()` 最初用"payload 的 hash"当 `thread_id`，而 `resume()` 用
  `claim_id` 当 `thread_id` → 两者不是同一个线程；LangGraph 无法改 thread_id（S2）。
- **修复**：新增 `ClaimService.claim_id_for(payload)`，按 SPEC §3.1 在 invoke **之前**复算确定性的
  `claim_id`，直接用作 `thread_id`。修完 8 例测试全绿。
- 教训：**thread_id 是外部契约的一部分**，必须由确定性规则推出，不能"先起名再改名"。

### 6.3 演示脚本的两个坑（已修，属工具而非业务）

1. **幂等键跨运行污染**：固定 payload 连跑两次，第二次命中上一次的幂等登记 → `CLAIM_DUPLICATE`
   （CLM-02 的正常行为，但会让 E1 无法重复验证）。修：demo 默认把 `CLAIMS_DATA_DIR` 指到一次性
   临时目录（轨迹仍写 `traces-claims/`，证据留仓）。
2. **断言写死 record_type 子集**：最初只允许 `{node_start, retrieval, llm_degraded, tool_call, tool_result}`，
   漏了 D-18 新增的 `node_end` → E1 假红。修：直接对 `server.trace.RECORD_TYPES` 取子集，
   **让断言跟着白名单走**，而不是抄一份。

### 6.4 未发现 F2/F3 缺陷（如实记录）

本次联调没有发现需要回给 flow-engineer / deepagents-engineer 的缺陷：
- 终态守卫（I6-a/I6-b）在 HTTP 面同样生效（E3 + 测试 `test_resume_rejects_bad_decision_and_terminal_thread`）；
- 降级可归因（I4-b/D-16）在 E6 拿到 `error_type="DeepAgentsDisabled"`；
- 指标接线（D-18）真实生效：`renewal_tool_calls_total{node="execute_payment"} 1`；
- `claims.payment_charge` 事件在 SPEC §6.3（`:306`）有登记，不是新增语义。

---

## 7. 遗留与交接

1. **SSE 是"重放 + 短跟随"，不是实时 tail**：`follow` 最大 30 秒；要真正常驻推送需引入
   订阅表/消息总线（本次刻意不做，避免在 F4 里加状态）。
2. **API 是独立进程**：`claims/api.py` 没有挂进 `server/app.py`（`server/**` 属保护对象）。
   启动方式：`PYTHONPATH=. .venv-claims/bin/python -m uvicorn claims.api:app --port 8131`。
   **必须 `.venv-claims`**，否则严格模式拒起（这是有意的）。
3. **真实 Deep Agents 路径未在本任务跑**：E1–E6 与 HTTP 全部在 `DEEPAGENTS_ENABLED=false`
   （规则模式）下完成，为的是确定性与不耗 API。F3 的真实模型路径见 `docs/log/step-f3.md`
   （`DEEPAGENTS_MODEL=project` 9.2s 跑通）。**因此"HTTP × 真实 Deep Agents"这个组合仍未验证**。
4. **前端未建**：SSE 只验证到 `curl` 层；浏览器 `EventSource`、断线重连（`Last-Event-ID`）未实现/未测。
5. **指标命名空间与续保共享 `renewal_*`**：这是既有约定（`server/metrics.py` 的应用前缀），
   若要把两条业务线分开看板，需要加 `domain="claims"` 标签 —— 属观测面改造，不在 F4 范围。
6. **`claims/tests` 未并入默认 `testpaths`**（D-06）：验证时必须显式写路径，见 §5 ③。
7. **全仓 `ruff check .` 不是全绿（既有问题，非 F4 引入）**：本次三条新文件 individually 通过，
   但全仓扫描有 **25 条既有错误**，分布在 `claims/deep_agents/**`（UP037/F401/I001）、
   `data/llm-wiki-claims/scripts/**`（E702/F401/F841）、`docs/research/evidence/**`（I001/F401）、
   `claims/tests/{conftest,test_flow,test_f2d_degradations}.py`（E402/F401）。
   这些文件属 F3 / wiki-lead / flow-engineer 的写作用域，**F4 未自行修改**；
   C5 若要拿 `ruff` 作门禁，需先按责任方清零（建议各自 `ruff check --fix` 后回归）。
   **状态（2026-11-19 01:5x 复核）**：F4 新增的三个文件仍为 `All checks passed!`；全仓既有错误已由 captain 分派
   flow-engineer（claims 域）与 wiki-lead（wiki 脚本域）分别处理，另含 `docs/research/evidence/**` 的排除决策。
   **F4b 不修 ruff，只保留记录**。
8. **读轨迹时请先看 `§5.2`**：同一 `claim_id` 的轨迹是**跨运行累加**的（本例已 162→202 行 / 8→10 轮）。
   不要把“42/202 行”当固定值，也不要手工删历史轨迹（审计只追加；`traces-claims/**` 不在 F4b 写作用域）。
---

## 8. 复跑方式（C5 可直接抄）

```bash
cd renewal-assistant
export PYTHONPATH=.

# 端到端六场景（唯一入口，退出码即门禁）
.venv-claims/bin/python claims/demo_claim.py            # 期望：PASS 8 / FAIL 0

# 测试矩阵
.venv/bin/python -m pytest -o addopts="" -q                                   # 148 passed, 2 skipped
.venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q   # 168 passed

# HTTP 面（真起服务；端口自选，勿占 8000）
CLAIMS_DATA_DIR=$(mktemp -d) CLAIMS_AMOUNT_REVIEW_THRESHOLD=0 DEEPAGENTS_ENABLED=false \
  .venv-claims/bin/python -m uvicorn claims.api:app --port 8131 &
curl -s localhost:8131/health
curl -s -X POST localhost:8131/claims/intake -H 'content-type: application/json' -d @payload.json
curl -s -N localhost:8131/claims/<claim_id>/events | head -20
curl -s localhost:8131/metrics | grep -c 'renewal_'
```
