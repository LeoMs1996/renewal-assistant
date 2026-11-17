# 集成Agent总结（integration）

> 阶段：端到端集成验证与缝隙修补 · 2026-11-12 · 服务规则模式（无 .env，LLM 降级标注）

## 一、做了什么

1. **AC 场景全链路串测**（`scripts/e2e_smoke.sh`，可重复执行，自管 uvicorn 于独立端口 8123，不占用 SPEC 的 8000）：
   - A1 查保单：`GET /policy/OWN-1001` → `expiring_soon=true`（23 天）、`policy_version` 返回、`id_number`/`phone` 不出参（脱敏）；`OWN-9999` → 404 `found=false`（AC-01/02/04）
   - A2 比价：续保 + 三者险 100万→200万 → 节点链 `intake→get_policy→parse_needs→retrieve_terms→quote→compare→await_confirm` 完整，`get_policy`/`query_quote` 真实调用，DSX=200万按 tiers 计价，输出保障差异表（AC-05/06）
   - A3 改保额 200万→300万 → 触发重新询价，新方案 DSX=300万
   - A4 加附加险 医保外用药 → 新报价含 YWYW 行项（5万保额/51元）
   - A5 条款问答（未年检）→ 命中 wiki-annual-inspection、message 带 citation（wiki_id/source/version 齐全）、不进比价、`finish_reason=end`（AC-11）
   - A6 轨迹：`GET /trace/{trace_id}` 可回放、seq 从 1 连续（AC-14）
2. **重启恢复 + 确认幂等**：kill 服务再起后，重启前的 trace 仍可回放；`POST /confirm` 成功且重复确认返回**同一 order_id**（幂等）；错误码矩阵 422 OWNER_MISMATCH / 409 QUOTE_VERSION_STALE / 404 QUOTE_NOT_FOUND 全对；同会话对话内说"确认"→ SSE `confirmed` 事件，order_id 与 `/confirm` 一致（session 的 awaiting_confirm 状态跨重启仍在）。
3. **前端实测（Chrome DevTools MCP）**：打开 `http://127.0.0.1:8000/` 跑一轮完整对话（比价→报价卡→差异表→条款依据→待确认卡→轨迹自动回放），**控制台零报错**。
4. **跨模块缝隙修复 1 处**（见下），脚本连跑 3 次全部通过（退出码 0），幂等性复现（同 quote 同 order_id）。

## 二、关键决策与依据

- **缝隙：前端页面无人挂载（已修）**。`web/index.html` 全部用同源相对路径（`/chat`、`/policy`、`/confirm`、`/trace`），但 `server/app.py` 没有任何静态路由，`GET /` 返回 404（浏览器实测确认 `{"detail":"Not Found"}`）。SPEC §1.1 定义 `web/` 为"SSE 对话工作台"，属于跨模块（server↔web）缝隙。修复：`app.py` 新增 `GET /`（`include_in_schema=False`）返回 `FileResponse(config.BASE_DIR / "web" / "index.html")`。未动 SPEC：单文件入口不引入新字段/接口，无需升版本。
- **smoke 自管端口 8123 而非 8000**：脚本可重复执行且不干扰常驻演示服务；端口/健康检查/进程清理全部内置（trap EXIT），`PORT` 环境变量可覆盖。
- **重启恢复验证设计**：阶段 A 把 `session_id/quote_id/quote_version` 写入临时 state 文件，kill → 重启 → 阶段 B 用**重启前**的 quote 直接 `/confirm` 成功且幂等，一次断言同时覆盖"报价仍在（traces/quotes.json 持久化）"与"只生成一个 order_id"两个验收点；再用对话内"确认"验证 session 状态（traces/sessions/*.json）跨重启。
- **Context7 文档要点**：本阶段为纯集成验证，无新 API 用法；沿用 server.md 已查证结论（LangGraph 1.x `stream(stream_mode=["custom","values"])`、FastAPI `StreamingResponse` 手写 SSE），未新增依赖，故本轮无需新查询。
- 事件格式核对：SSE 12 种事件（node_start/node_end/tool_call/tool_result/token/message/quote/clarify/await_confirm/confirmed/error/done）字段与 SPEC §4.1 逐一对齐，未发现事件/字段不一致的其他缝隙。

## 三、验证证据

- `./scripts/e2e_smoke.sh 8123`（连续 3 次）→ 全部 ✅，末行 `✅ E2E smoke 全部通过（AC 链路 + 重启恢复 + 确认幂等）`，退出码 0
- 关键输出摘录：
  - `临期提醒 expiring_soon=true（23 天）`、`OWN-9999 → 404 found=false（不编造）`
  - `节点链完整 ['intake','get_policy','parse_needs','retrieve_terms','quote','compare','await_confirm']`
  - `新方案含 YWYW 行项 [{'code':'YWYW',...,'premium':51.0}]`
  - `message 带 citation（wiki-annual-inspection）`
  - `POST /confirm 200 → ORD-20261112-1266` / `重复确认幂等：同一 order_id ORD-20261112-1266`
  - `越权 → 422 OWNER_MISMATCH`、`旧版本 → 409 QUOTE_VERSION_STALE`、`不存在 → 404`
- 前端：页面标题"车险续保助手 · 对话工作台"正常渲染；一轮对话后出现报价卡（QT-20261112-0001 / 2479.22 元）、差异表、条款依据（4 条 wiki citation）、"待确认投保方案"卡、右侧轨迹自动回放 24 条；`list_console_messages` → **no console messages found**（无报错无警告）。

## 四、遗留问题与交接

1. **`.env` 未配置** → 全程规则模式（`/health` 如实标注 `llm_mode=rule`）。填入 GLM 凭证后建议重跑 `scripts/e2e_smoke.sh` 做一次 LLM 模式回归。
2. `GET /` 修复后需保持 8000 端口的常驻服务重启才生效（本轮已重启，已验证 200）。
3. AC-12（报价真实过期 24h）未在 smoke 中模拟时钟穿越——过期分支的 `/confirm` 409 QUOTE_VERSION_STALE/QUOTE_EXPIRED 逻辑已在错误码矩阵与 graph confirm 节点覆盖，如需真过期用例可手改 `traces/quotes.json` 的 `valid_until` 后重放（脚本未做，避免污染共享状态）。
4. 其余未覆盖的 AC（07/08/09/10 纠正类、OWN-1002 非临期）在编排Agent的 `scripts/demo_chat.py` 与其总结中有对应验证，本脚本聚焦用户指定的串测链路。
