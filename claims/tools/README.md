# claims/tools/ —— 理赔工具 / MCP server · 占位

> 状态：**C0 占位，无实现**。建立于 2026-11-17。

## 职责

为理赔流程提供**可被审计的工具**（优先做成真实 MCP server，走协议而非进程内直连）：

| 工具（占位命名，C4 定稿） | 作用 | 硬约束 |
|---|---|---|
| `verify_policy` | 核验保单有效性、险种覆盖 | 只读；越权读取他人保单=硬失败 |
| `assess_damage` | 定损项与金额计算 | 金额只能由服务端算，模型不得编造 |
| `settle_payment` | 生成模拟支付指令 | 幂等；重复请求返回同一条指令 |

## 与既有 MCP 的关系

`renewal-assistant/mcp_servers/` 是续保域的 MCP（`get_policy` / `query_quote`），**只读复用或复制模式，不修改**。
历史教训（评审已记录）：续保的 `mcp_bridge` 是**进程内函数直连**，`tools/list`、`tools/call` 从未经真实协议验证——理赔域不要重复这个坑，工具应以真实 MCP 协议通道实现并有协议层测试。

## 开工前置（硬规则）

按 `docs/log/hard-rules.md`：先检索 **≥3 个独立来源**（MCP 当前规范/spec 版本、Python SDK 用法、工具 schema 与错误码约定），记 URL + 检索时间 + 用途，再动手。

## 当前内容

无。此文件仅为目录占位与职责声明。
