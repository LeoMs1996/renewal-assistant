# 后端阶段小结（server/）

- 日期：2026-11-12 · 产出：后端Agent · 契约：SPEC.md v1.0.0（未改动）

## 一、做了什么

实现 `server/` 全部五个模块（+2 辅助模块），服务运行于 **http://127.0.0.1:8000**（后台常驻，`server.app:app`）：

| 文件 | 职责 |
|---|---|
| `config.py` | .env 手动解析（零额外依赖）；路径/HOST/PORT；LLM 双套变量名兼容（`ANTHROPIC_BASE_URL/AUTH_TOKEN/MODEL_NAME` 优先，回退 `ANTHROPIC_API_KEY/ANTHROPIC_MODEL`） |
| `llm.py` | GLM Anthropic 兼容客户端（`anthropic` SDK + `base_url`）；非流式 `chat` + 流式 `stream_chat`（token 增量）；**缺配置/调用失败自动降级规则模式并显式标注**，不崩溃 |
| `trace.py` | `TraceRecorder`：轨迹 JSONL，字段严格按 SPEC §5（ts/trace_id/session_id/seq/record_type/node/event/input/output/latency_ms/tokens_in/tokens_out/error），record_type 白名单校验；`read_trace` 供 GET /trace |
| `wiki_search.py` | BM25（rank-bm25）：front-matter 解析（id/version/effective_date/source）+ 中文二元组分词（单字+bigram）+ 英文数字词；`search_with_score` 返回 Top-K；`hits_for_trace` 输出严格 `[{wiki_id, source, version, score}]` |
| `mcp_bridge.py` | 直连 `mcp_servers/quote_server.py` 函数（不起子进程）；`{"error":{code,message}}` → `ToolError`；quote_server 未实现时 get_policy 降级本地实现（语义同 SPEC §3.1，含脱敏），**query_quote 不降级**（保费只能来自报价服务） |
| `quote_book.py` | 报价登记簿（`traces/quotes.json`，已加 .gitignore）；register/get/is_expired/create_order（订单幂等：同 quote_id 重复确认返回同 order_id） |
| `graph.py` | LangGraph 状态机骨架：SPEC §6 全部 10 节点 + 边拓扑（含条件路由：intake 意图分流、confirm QUOTE_EXPIRED→quote 回环），节点返回占位输出，**编排 Agent 只填节点函数体、勿改拓扑** |
| `app.py` | REST：POST /chat SSE（事件按 SPEC §4.1 逐字段）、GET /policy/{owner_id}、GET /trace/{trace_id}、POST /confirm（409/404/422 全分支）、GET /health（SPEC 外运维端点） |

另：`.env.example` 追加 GLM 三变量（注释态）；`.gitignore` 追加 `traces/quotes.json`；创建 `server/__init__.py`、`mcp_servers/__init__.py`（空，供 MCP Agent 复用包结构）。

## 二、关键决策与依据（含 Context7 文档要点）

1. **SSE 用 `StreamingResponse(media_type="text/event-stream")` 手写编码**而非 FastAPI 新版 `EventSourceResponse`：Context7（/websites/fastapi_tiangolo）显示 `fastapi.sse.EventSourceResponse` 是较新版本才有的 API，且 SPEC §4.1 要求自定义 `event:` 行；手写 `_sse()` 生成器版本兼容性最稳。
2. **LangGraph 用法按 1.x 当前 API**：Context7（/websites/langchain_oss_python_langgraph）确认 `StateGraph(State).add_node/add_edge(START,…)/add_conditional_edges(node, router, [候选])/compile()`；路由函数返回节点名或 `END`；`TypedDict(total=False)` 做 State 以支持节点局部更新。
3. **get_policy 本地降级、query_quote 不降级**：`/policy` 端点在 MCP server 未就绪时也要可测（自测要求 OWN-1001/OWN-9999），本地实现严格复刻 SPEC §3.1（脱敏 id_number/phone、`days_to_expiry<=30 → expiring_soon`）；但保费数字是硬规矩（备忘 #3），宁可报错也不本地算价。
4. **`run_in_executor` 中迭代生成器必须用哨兵而非抛 StopIteration**：Python 3.14 禁止 StopIteration 穿透 Future（实测报 "StopIteration interacts badly with generators"），已改 `_next()` 返回 `_DONE` 哨兵。
5. **/confirm 校验顺序**：404 存在性 → 422 OWNER_MISMATCH（vin 归属）→ 409 QUOTE_EXPIRED（AC-12 优先级）→ 409 QUOTE_VERSION_STALE → 成功（幂等下单）。越权读他人保单确认 = 硬失败 422。
6. **chat 骨架期即输出真实数据**：SSE 演示流已接真实 get_policy 桥接 + 真实 BM25 检索（citations 带来源+版本）+ 临期提示（AC-01 提前可验），编排 Agent 只需把 stub 段替换为 graph 流式执行。

## 三、验证证据（命令 + 输出摘录，退出码均 0）

```
# /policy/OWN-1001
found: True | expiring_soon: True | days: 23 | owner keys: [...无 id_number/phone]
# /policy/OWN-9999 → {"found":false,"message":"未找到保单"} [HTTP 404]
# /confirm 全分支：
QT-EXPIRED  → {"error":{"code":"QUOTE_EXPIRED",...}}  [409]
QT-NOPE     → {"error":{"code":"QUOTE_NOT_FOUND",...}} [404]
OWN-1002 越权 → {"error":{"code":"OWNER_MISMATCH",...}} [422]
version=0   → {"error":{"code":"QUOTE_VERSION_STALE",...}} [409]
QT-VALID    → {"order_id":"ORD-20261112-1346",...} [200]
幂等重放    → 同一 order_id ORD-20261112-1346
# /chat SSE：node_start×2 node_end×2 tool_call tool_result token×86 message done（无 error）
#   message 内容含"距到期仅 23 天"提示 + 【规则模式】标注 + 模拟报价声明
#   citations: [('wiki-annual-inspection','v2024.3'), ('wiki-jqx','v2024.3'), ('wiki-ride-hailing','v2024.3')]
# /trace/{trace_id}：rows=9 | seq 连续: True | record_types 覆盖 9 种 | trace_id/session 一致: True
# /trace 不存在 → [404]；/health → {"llm_mode":"rule","wiki_entries":8,"graph":"stub"}
```

## 四、遗留问题与交接

1. **mcp_servers/quote_server.py 尚未实现**（并行 Agent 负责）：函数签名约定已写在 `mcp_bridge.py` 文件头（`get_policy(owner_id=None, vin=None)` / `query_quote(vin, coverage_selection, use_nature=None, ncd_years_no_claim=None)`），返回 `{"error":{code,message}}` 即被桥接层转为异常。实现后无需改 server 代码，get_policy 本地降级自动停用。
2. **编排 Agent 接入点**：`graph.py` 各节点函数体（TODO 标注）；`app.py` `/chat` 的 stub 段（intake 占位 → 替换为 `graph.get_graph()` 流式执行，`/health` 的 `graph` 字段同步改 `"langgraph"`）；checkpointer（重启续跑）未接，建议 SQLite。
3. **LLM 当前为规则模式**（无 .env 凭证）：填入 `ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN/MODEL_NAME` 后自动切换，无需改码。
4. **`/chat` 骨架流暂不产生 `quote`/`await_confirm`/`confirmed` SSE 事件**（依赖编排与报价链路），12 种事件类型编码函数 `_sse` 已就绪。
5. 服务常驻 8000 端口（`/tmp/renewal-server.log`）；测试用的报价/订单/轨迹已清理（quotes.json 置空）。
