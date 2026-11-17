# MCP 域：评估 → 优化 → 验证总结

> 检索时间：2026-11-13（Asia/Shanghai）｜子 Agent：MCP 协议验证｜状态：已落地并通过实测

## 1. 2026 基准

| 基准 | 结论要点 | 来源 |
|---|---|---|
| MCP stdio 传输 | 客户端以**子进程 stdio** 承载 server；消息为 JSON-RPC，逐行（newline-delimited）；生命周期由客户端拉起/关闭 | [Model Context Protocol · stdio transport（2026-07-28）](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) |
| MCP Python SDK | `ClientSession` + `stdio_client` 为标准用法；需在异步任务内 enter/exit | 通过 Context7 查 `/modelcontextprotocol/python-sdk`（检索 2026-11-13），并以实际 `mcp==2.3.0` 运行验证为准 |

## 2. 优化前的差距

| 问题 | 隐蔽性 | 说明 |
|---|---|---|
| **协议通道形同虚设** | **高** | `mcp_bridge` 在进程内直接 import `quote_server` 调函数，`tools/list`、`tools/call`、`initialize` 握手**从未真实发生**；SDK 升级导致的协议漂移无法被发现 |
| 规则 3 版本自增为死代码 | 中 | 见编排域总结（根因是幂等短路过早返回） |
| 无 stdio 链路测试进入 CI | 中 | 单测只覆盖函数级，覆盖不到子进程/握手 |

## 3. 已实施改动

1. **`server/mcp_bridge.py` 支持双传输**：
   - `MCP_TRANSPORT=stdio`：用 `ClientSession` + `stdio_client` 拉起**真实子进程**，走 JSON-RPC；
   - 默认 `inprocess`：保持原进程内直连（演示/低延迟）。
   - 常驻后台线程持有 `ClientSession`，避免每次调用重建子进程与握手（代码注释已标注：多线程生命周期管理属遗留项）。
2. **`_unwrap()` 统一错误映射**：把 MCP 工具返回的 `error.code/message` 转成 `ToolError`，保持 REST 层错误码契约不变。
3. **`mcp_servers/quote_server.py` 规则 3 修复**：幂等短路加 `rates_version` 前置条件（详见编排域）。
4. **CI 增加 stdio 专项**：`MCP_TRANSPORT=stdio python mcp_servers/test_quote_server.py`（第 10 节即 `initialize + tools/call` 冒烟）。

## 4. 验证证据

```
MCP_TRANSPORT=stdio python -c "mcp_bridge.get_policy(owner_id='OWN-1001')"
  → found=True（经真实子进程 + JSON-RPC 握手返回，非进程内调用）

MCP_TRANSPORT=stdio python mcp_servers/test_quote_server.py
  → 54 通过 / 0 失败
  → 含「注册了 get_policy / query_quote 两个工具」「stdio 链路：initialize + tools/call get_policy 脱敏返回」

默认 inprocess
  → 54 通过 / 0 失败（向后兼容未破坏）
```

## 5. 遗留项

| 项 | 说明 | 建议 |
|---|---|---|
| 默认仍是 inprocess | 生产若依赖协议隔离，应默认 stdio | 部署配置显式设 `MCP_TRANSPORT=stdio`，并在 `/health` 暴露当前传输方式 |
| 常驻线程生命周期 | 进程退出时子会话未优雅关闭 | 加 `atexit` / FastAPI `shutdown` 钩子关闭 `ClientSession` |
| 无工具 schema 漂移检测 | 工具参数改动无告警 | CI 里记录 `tools/list` 快照，变更即 diff 报警 |
| 单工具 | 仅 `get_policy`/`query_quote` | 后续可加 `quote_status`、`order_status` 等，但需先扩 SPEC |
