# 脚手架阶段小结（scaffold）

- 日期：2026-11-11 · 产出：脚手架Agent · 契约：SPEC.md v1.0.0

## 已完成

1. **目录结构**：`web/ server/ mcp_servers/ wiki/ synthetic/ skills/ eval/cases/ traces/ docs/summaries/ docs/` 全部就位。
2. **合成数据**（`synthetic/`，均带 `dataset:"synthetic"` 标注）：
   - `owner.json`：两位车主（张伟 OWN-1001 / 李静 OWN-1002），含身份、车架号、到期日；**OWN-1001 到期 2026-12-05（临近）**，OWN-1002 到期 2027-06-20。
   - `policy.json`：两张原保单（v2024.3），险种结构为交强险 + 车损险 + 三者 100 万 + 医保外用药 + 车上人员（李静另附加划痕险）。
   - `rates.json`（v2025.1）：各险种基准保费（三者按 50/100/200/300 万档位）、NCD 系数表、用途系数（网约车 1.6）、车龄系数、医保外用药附加险、**停售险种标记（发动机进水险-已停售 等 3 项，附 replacement 指向 CSX）**。
3. **条款知识库**（`wiki/`，8 条 Markdown，front-matter 含 id/version/effective_date/source 虚构条款名）：交强险、车损险、三者险、医保外用药、免赔额、未年检赔付、网约车用途变更、费率上浮规则。
4. **技能**：`skills/renew_compare.md`，七步流程（读原保单→解析需求→取报价→保障差异表→价格→依据→等待确认）。
5. **配置**：`.env.example`、`requirements.txt`（fastapi/uvicorn/langgraph/mcp/rank-bm25/anthropic/httpx）、`.gitignore`（.env、traces/*.jsonl、__pycache__ 等）。
6. **SPEC.md v1.0.0**（唯一契约）：项目概述、三份 JSON Schema、MCP 工具 `get_policy`/`query_quote` 出入参与**报价版本+24h 有效期规则**、REST API（`POST /chat` SSE 12 种事件格式、`GET /policy/{owner_id}`、`GET /trace/{trace_id}`、`POST /confirm` 及 409/404/422 错误码）、轨迹 JSONL 12 字段表、状态机 11 节点 + 边定义、**AC-01~AC-14 验收场景清单**。

## 验证

```
$ python -c json.load …
synthetic/owner.json OK v1.0.0
synthetic/policy.json OK v1.0.0
synthetic/rates.json OK v2025.1
cross-ref owners<->policies OK     # owner.current_policy_id 均能关联到 policy
wiki 条目数：8
```

## 交接给后续 Agent 的要点

- 一切字段名/接口签名以 **SPEC.md** 为准，改动先改 SPEC 并升版本号。
- `mcp_servers/` 实现 quote-server 时注意 6 条报价规则（幂等、版本自增、24h 过期、停售/交强/附加险前置校验）。
- `server/` 实现时：SSE 事件与轨迹 JSONL 字段严格对照 SPEC §4.1/§5；`get_policy` 出参脱敏（不含 id_number/phone）。
- `eval/cases/` 按 AC-01~AC-14 逐条落用例。
