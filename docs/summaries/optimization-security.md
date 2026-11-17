# 安全域：评估 → 优化 → 验证总结

> 检索时间：2026-11-13（Asia/Shanghai）｜子 Agent：安全加固｜状态：已落地并通过实测

## 1. 2026 基准（先查证，后动笔）

| 基准 | 结论要点 | 来源 |
|---|---|---|
| OWASP API Security Top 10（2023 版） | API1 BOLA：对象级越权是首要风险，**身份必须由凭证派生，不得采信请求自报的 owner 字段**；API2 认证失效；API4 无限制资源消耗；API8 安全配置错误 | [OWASP DevGuide · API Top 10](https://devguide.owasp.org/en/07-training-education/07-api-top-ten/)、[OWASP API Top 10 风险白皮书（Akamai 转载）](https://www.akamai.com/site/en/documents/white-paper/2024/owasps-top-10-api-security-risks.pdf) |
| OWASP DoS Cheat Sheet | 限流要做在便宜校验的最外层、定义单 IP 最大 ingress 速率 | [OWASP DRAFT Denial of Service Cheat Sheet](https://wiki.owasp.org/index.php?title=DRAFT_Denial_of_Service_Cheat_Sheet) |

> 「CSP 具体指令取值」与「密钥轮换周期」两条本轮**未抓到权威原文**，相关取舍标注为**待验证**，不作为结论依据（实现按最小暴露面收紧，可后续对齐）。

## 2. 优化前的差距

| 风险 | 严重度 | 证据 |
|---|---|---|
| 全部端点零鉴权，任何人可读写任意车主保单 | high | `/policy/{owner_id}`、`/confirm`、`/chat` 无凭证校验 |
| `owner_id` 由请求体自报 → API1 BOLA 可直接越权 | high | `POST /confirm` 只校验 quote↔owner，不校验调用者 |
| `/trace/{trace_id}` 路径拼接未校验 → `../` 可读任意 `.jsonl` | high | `trace_mod.read_trace()` 直接拼路径 |
| 无任何限流、无安全响应头 | medium | 无中间件 |

## 3. 已实施改动

1. **新增 `server/middleware.py`**（三个中间件，全部**纯 ASGI**）：
   - `AuthMiddleware`：`X-API-Key` → owner 派生（`RENEWAL_API_KEYS="key:owner"`）；路径或请求体里的 `owner_id` 与凭证不符 → 403；`/trace/{id}` 白名单 `^trc-\d{14}-[a-z0-9]{6}$` → 400；演示模式（未配密钥）放行并回 `X-Auth-Mode: demo`。
   - `RateLimitMiddleware`：单 IP 滑动窗口（默认 60/min），超限 429 + `Retry-After`。
   - `SecurityHeadersMiddleware`：CSP / nosniff / X-Frame-Options / Referrer-Policy，**挂在最外层**，保证 401/403/429 也带齐。
2. **`server/app.py`**：中间件顺序改为 `SecurityHeaders → RateLimit → Auth → 路由`；`GET /trace/{id}` 接入 `trace_owner_allowed()` 内容级归属校验（轨迹含他人 `owner_id` → 403 `TRACE_FORBIDDEN`）。
3. **新增 `tests/test_security.py`**（13 条）：401/403/400/429、错误响应带安全头、演示模式标记、轨迹归属规则单测。

## 4. 关键回归与修复（本次最重要的一条经验）

首版中间件用了 Starlette `BaseHTTPMiddleware`，**实测把 `/chat` SSE 流打断**：

```
RuntimeError: Unexpected message received: http.request
```

Starlette 官方已记录 `BaseHTTPMiddleware` 的多个已知缺陷（含请求体重放/流式响应问题）：[Kludex/starlette PR #1640 · Document BaseHTTPMiddleware bugs](https://github.com/Kludex/starlette/pull/1640)、[a2wsgi issue #45 · BaseHTTPMiddleware 与 ASGI 互操作问题](https://github.com/abersheeran/a2wsgi/issues/45)。

**处置**：三个中间件改写为纯 ASGI（只观察/改写 `send` 消息，需要读 body 时用一次性回放包装，之后委托原 `receive`），SSE 恢复正常收尾。该约束已写入 `SPEC §4.5 实现约束`。

## 5. 验证证据（均为本机实测）

```
# 契约行为
POST /chat 无密钥                              → 401
POST /chat 密钥 k1(OWN-1001) + body OWN-1002    → 403 OWNER_FORBIDDEN
GET  /trace/..%2F..%2F.env                     → 400 TRACE_ID_INVALID
GET  /health（演示模式）                        → 200 + X-Auth-Mode: demo
GET  /health 响应头                             → CSP / nosniff / DENY / no-referrer

# 测试
pytest tests/test_security.py                  → 13 passed
pytest tests/ mcp_servers/                     → 16 passed
eval SEC-02 / SEC-04 / SEC-05                  → 全部 PASS（注入未改写入参、穿越全拦）
```

## 6. 遗留项

| 项 | 说明 | 建议 |
|---|---|---|
| 限流为单进程内存实现 | 多副本部署时每副本独立计数 | 换 Redis 滑动窗口（`RATE_LIMITED` 契约不变） |
| CSP 仍需 `'unsafe-inline'` | 前端是单文件内联 JS/CSS | 拆外链 JS 后改 nonce/hash，去掉 unsafe-inline |
| 演示模式默认放行 | 未配密钥即零鉴权 | 生产启动时检测 `ENV=prod` 且无密钥则拒绝启动 |
| 无密钥轮换与审计日志 | 密钥静态、鉴权失败未落审计 | 接入审计事件 + 密钥多版本并存（待验证最佳实践原文） |
