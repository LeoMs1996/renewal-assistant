# MCP 服务 Agent 小结 — quote-server

## 1. 做了什么

- 实现 `mcp_servers/quote_server.py`：MCP 服务器 **quote-server**（stdio 传输），暴露 SPEC §3 的两个工具：
  - `get_policy(owner_id? | vin?)` — 读 synthetic 保单；出参脱敏（剔除 `owner.id_number` / `owner.phone`）；`found=false` 时仅返回 `{found:false, message:"未找到保单"}`；`expiring_soon = days_to_expiry <= 30`。
  - `query_quote(vin, coverage_selection, use_nature?, ncd_years_no_claim?)` — 按 SPEC §2.3 保费公式与 §3.2 六条规则报价。
- 编写 `mcp_servers/test_quote_server.py`：不走 LLM，直接断言工具函数 + 一段 stdio 真实链路冒烟（MCP client initialize → tools/call）。
- 新建项目 venv `.venv/` 并安装 `mcp`（系统 Python 3.14 受 PEP 668 限制）。

## 2. 关键决策与依据

### Context7 查到的 MCP Python SDK 文档要点

- **SDK 已是 2.x，FastMCP 更名**：`from mcp.server.fastmcp import FastMCP` 在 2.x 直接抛 ModuleNotFoundError，须改用 `from mcp.server import MCPServer`（迁移指南 py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver）。requirements.txt 中 `mcp` 未固定版本，装到的是 2.x。
- **`mcp.run()` 不传参默认 stdio 传输**；`@mcp.tool()` 装饰器注册工具，返回值注解为 `dict` 即结构化输出（Pydantic TypeAdapter 校验）。文档来源：py.sdk.modelcontextprotocol.io（servers/structured-output、run、api/mcp/server）。

### 业务决策

| 决策 | 依据 |
|---|---|
| 工具校验失败以**返回值** `{"error":{code,message}}` 表达（而非抛 MCP ToolError） | SPEC §3.2 明文规定错误统一格式，业务层需读到结构化错误码 |
| JQX（交强险）保费固定 950，不参与 NCD/用途/车龄系数；车龄系数仅作用于 CSX 部分 | SPEC §2.3 公式："车龄系数(仅车损险部分)"；交强险为法定固定保费 |
| `line_items[].premium` 为**系数调整后**的最终价（非基准价） | 比价场景（AC-05/06）需展示实际价差；SPEC §3.2 示例中数字为示意 |
| 幂等键 = vin + 归一化险种选择（解析出实际 sum_insured 后排序）+ 用途 + NCD | SPEC 规则 2："相同 coverage_selection 24h 内同 quote_id"；省略 sum_insured 与显式默认值应视为同入参 |
| NCD 缺省按 `policy.ncd_factor` 反推（OWN-1001: 0.85 → 2 年无赔） | SPEC §3.2 入参表原文 |
| DSX 缺省 sum_insured=100万；CSX 缺省沿用当前保单车损保额 | rates.json 无显式 default 字段，取最合理默认 |
| BLPS 无费率表条目 → 报 `RATE_NOT_FOUND`（rates.json base_premium 未定义 BLPS） | 保费只能来自费率服务，缺费率即报错，不得编造 |
| quote 存储为**进程内** dict；另导出 `get_quote` / `quote_is_stale` 供 server 侧 /confirm 复用 | SPEC 未要求报价跨进程持久化；24h 有效期内同进程幂等即可满足 |
| 报价附 `disclaimer: "模拟报价…"` | 备忘录硬规矩：所有输出标"模拟报价/合成数据" |

## 3. 验证证据

命令：

```bash
.venv/bin/python mcp_servers/test_quote_server.py
```

输出摘录（**54 通过 / 0 失败，退出码 0**）：

```
== 1. get_policy 基础与脱敏 ==
  ✓ owner 不含 id_number（脱敏） / ✓ owner 不含 phone（脱敏）
  ✓ days_to_expiry=24（2026-12-05 到期） / ✓ expiring_soon=true
  ✓ 查无此人：仅 {found:false, message}
== 2. query_quote 正常报价 ==
  ✓ ncd=0.85（按 ncd_factor 反推） / ✓ vehicle_age=1.05
  ✓ DSX 200万 = 1520×0.85 = 1292 / ✓ premium_total = 2242
  ✓ valid_until=created_at+24h
== 3/4. 幂等与新ID ==
  ✓ 同 quote_id / 同 quote_version；入参变化 → 新 quote_id、version=1
== 5. 三档三者险 ==  ✓ 50万/100万/300万 tiers 计价
== 6. 三种错误 ==  ✓ COVERAGE_DISCONTINUED(附CSX建议) / JQX_REQUIRED / RIDER_PREREQUISITE_MISSING(YWYW、BLPS)
== 7. 24h ==  ✓ 边界(now=valid_until 未过期) / 过期重报新ID / QUOTE_EXPIRED / QUOTE_VERSION_STALE / QUOTE_NOT_FOUND
== 8/9 ==  ✓ 网约车系数1.6（1180×0.85×1.6=1604.8）/ ✓ ncd_years_no_claim=0 → 1.0
== 10. ==  ✓ 注册 get_policy/query_quote 两工具
  ✓ stdio 链路：initialize + tools/call get_policy 脱敏返回
```

## 4. 遗留问题与交接

1. **BLPS（车身划痕险）无费率**：rates.json `base_premium` 未定义 BLPS 费率（保单里有该险种但费率表缺条目）。当前返回 `RATE_NOT_FOUND`。若 AC 需要 BLPS 报价，需在 rates.json 补条目（改数据须先升 SPEC 或确认数据文件可补）。
2. **quote 进程内存储**：server Agent 若在独立进程实现 `/confirm`，需通过 MCP client 调本服务器（同进程生命周期），或调用导出的 `get_quote` / `quote_is_stale(quote_id, quote_version)`（返回 QUOTE_NOT_FOUND/QUOTE_EXPIRED/QUOTE_VERSION_STALE/None）。跨进程持久化（落盘 JSON）如需要可后续加。
3. **SDK 2.x 兼容**：代码基于 `from mcp.server import MCPServer`（mcp 2.x）。requirements.txt 未锁版本；若其他 Agent 环境装到 mcp 1.x 需改回 `mcp.server.fastmcp.FastMCP`（仅一行 import + 实例化差异）。建议统一用 `.venv`。
4. **`_now` 可注入**：所有时间相关函数均接受 `now` 参数便于测试；生产路径用真实 `Asia/Shanghai` 时钟。
5. 环境注意：`.env.example` 中 `MCP_QUOTE_SERVER_URL` 指向 HTTP，而本实现按任务要求为 **stdio**；server Agent 接入时用 stdio client（`StdioServerParameters(command=".venv/bin/python", args=["mcp_servers/quote_server.py"])`）。
