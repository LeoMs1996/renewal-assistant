# 编排域（LangGraph）：评估 → 优化 → 验证总结

> 检索时间：2026-11-13（Asia/Shanghai）｜子 Agent：编排持久化｜状态：已落地并通过单测

## 1. 2026 基准

| 基准 | 结论要点 | 来源 |
|---|---|---|
| LangGraph Persistence | 编译器接受 `checkpointer`；调用需带 `config={"configurable": {"thread_id": ...}}`，`thread_id` 是 checkpoint 主键；持久化以 thread 为单位延续状态 | [LangChain Docs · Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) |
| `SqliteSaver` | SQLite 落盘的官方 checkpointer，适合单机/演示与测试；Python 包为 `langgraph-checkpoint-sqlite` | [API Reference · langgraph.checkpoint.sqlite.SqliteSaver](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver) |

## 2. 优化前的差距

| 差距 | 影响 |
|---|---|
| 会话状态只靠自写 `sessions.json`，非官方通道 | 状态与图执行脱节，回放/时间旅行能力缺失 |
| `app.py` 每轮从 JSON 快照重组 `initial State` | 应用层与编排层耦合，语义散落 |
| SPEC §3.2 规则 3（版本自增）注释存在但**永不生效** | 文实不符：`quote_version` 恒为 1 |

## 3. 已实施改动

1. **接入官方 checkpointer**（`server/graph.py`）：`SqliteSaver`（`traces/checkpoints.sqlite`），缺包降级 `InMemorySaver`；编译时 `builder.compile(checkpointer=...)`。
2. **零改动兼容层** `_ThreadHandle`：`app.py` 历史上调用 `compiled.stream(initial, config={...})` 不带 `thread_id`，包装层从 `initial["session_id"]` 注入 `thread_id`（经 `sessions._safe` 归一化），避免改动 `app.py` 契约。
3. **`server/sessions.py` 明确降级为兼容层**：保留 history 裁剪（尾部 20 条）与 ephemeral 键过滤等应用层语义；文件头写明「废弃计划：app.py 迁移到 `get_graph().get_state(thread_id)` 后仅保留 history 归档」。
4. **修复规则 3 死代码**（`mcp_servers/quote_server.py`）：根因不是缺自增代码，而是**幂等短路过早返回**——规则 2 未比较 `rates_version`，导致「费率表升版」场景永远走不到自增分支。修法：幂等条件加 `quote["rates_version"] == _RATES_DATA["version"]`。

## 4. 验证证据

```
# 持久化（tests/test_persistence.py，3 条）
同 thread_id 两轮 invoke        → budget 沿用、DSX 保额保留（跨轮累积生效）
不同 thread_id                  → 状态隔离，互不串扰
重建 checkpointer + 重编译图    → 历史线程状态仍可读（SQLite 落盘有效）
get_graph() 兼容层              → 缺 configurable 时注入 thread_id；已指定则不覆盖
pytest tests/test_persistence.py → 3 passed

# 规则 2 / 规则 3（直接调用 quote_server）
同入参连续两次          → 同 quote_id、同版本（规则 2 幂等）
把 rates.version 改版后再询 → 同 quote_id、版本 1→2（规则 3 生效）
版本已是最新时再询       → 版本不变（幂等继续生效）
```

## 5. 遗留项

| 项 | 说明 | 建议 |
|---|---|---|
| 双写仍存在 | `sessions.json` 与 checkpoint 同时落盘，前者是 `/chat` 实际恢复来源 | 按 sessions.py 头顶的废弃计划迁移 `app.py`，只留一份真相 |
| SQLite 不适合多副本 | 文件锁 + 单机语义 | 生产换 Postgres 官方 checkpointer |
| 未使用 `interrupt()` | 当前「等待用户确认」用 `await_flag` + 会话状态表达 | 若要做真正的人类介入暂停/恢复，采用官方 `interrupt()`/`Command(resume=...)`（版本行为需再查证 → **待验证**） |
| 无图级回归 | 拓扑改动无自动断言 | 加一条「节点/边快照」测试，防误改拓扑 |
