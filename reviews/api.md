# API 与 SSE 域评审 + 落地优化报告（2026-11-13）

评审人：api-reviewer（AgentTeams t5，attempt 4）· 评审对象：renewal-assistant `server/app.py`（FastAPI 0.162.4）· SPEC §4 REST 契约。

## 一、检索基线（2026-11-13 检索，全部为本次实读）

| # | 来源 | 关键结论 |
|---|---|---|
| 1 | [FastAPI 官方教程 · Server-Sent Events (SSE)](https://fastapi.tiangolo.com/tutorial/server-sent-events/) | FastAPI **0.135.0 起内置原生 SSE**：`from fastapi.sse import EventSourceResponse, ServerSentEvent`，端点声明为 async 生成器 + `response_class=EventSourceResponse`；官方明确支持 `id`（浏览器重连回传 `Last-Event-ID`）、`retry`、`comment` 字段与 POST SSE；框架路由层内置 keepalive 与结构化收尾。检索时间 2026-11-13。 |
| 2 | [FastAPI 官方参考 · SSE EventSourceResponse/ServerSentEvent](https://fastapi.tiangolo.com/reference/sse/) + 本地实测 `site-packages/fastapi/sse.py`、`routing.py`（0.162.4 源码逐行实读） | 路由层 `_keepalive_inserter` 在生成器空闲 `_PING_INTERVAL=15s` 时自动插入 `": ping\n\n"` 注释行；生产者/内存流/取消由 anyio 任务组结构化收尾（注释引用 PEP 789）；wire 格式字段顺序为 comment→event→data→id→retry（SSE 规范不依赖字段顺序）；`ServerSentEvent` 校验 id 单行无 `\0`、data/raw_data 互斥。 |
| 3 | [MDN · Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) | 服务端须 `Content-Type: text/event-stream`、每事件以空行结尾；自定义 `event:` 字段映射 `addEventListener`；`: ` 注释行可作心跳；**HTTP/1.1 下浏览器每域名最多 6 条 SSE 连接（Chrome/Firefox 均标记 Won't fix），HTTP/2 默认 100 流**；代理场景需 `X-Accel-Buffering: no` 类响应头防缓冲。检索时间 2026-11-13。 |
| 4 | [WHATWG HTML § Server-sent events（wire 格式规范，经 MDN/教程引证）](https://html.spec.whatwg.org/multipage/server-sent-events.html) | 字段顺序无关、`id` 触发重连回传 `Last-Event-ID`、注释行忽略——本次迁移兼容性的规范依据（fastapi/sse.py `format_sse_event` docstring 直接引用该节）。 |

## 二、项目现状实读（server/app.py 改造前）

- `POST /chat`：**手写 SSE 管线**——`_sse()` 手拼 wire 字符串、`asyncio.Queue` + 手写 producer 任务 + `asyncio.wait_for(15s)` 手写心跳 + 手动 `producer.cancel()`；历史上正是这段手写收尾出过「哨兵元组永不匹配→连接挂死」缺陷（代码注释自认，2026-11-13 修复）。项目依赖已锁 fastapi 0.162.4，却完全没用 0.135+ 的原生 SSE 能力——**框架能力与使用方式严重脱节**。
- 事件序号 `id:` 逐帧递增 ✓；`Last-Event-ID` 仅记录不续传，以 `X-Resume-Supported: false` 显式声明（诚实契约，可接受）。
- `GET /policy` / `GET /trace`：trace_id 白名单正则（防路径穿越）+ 内容级 owner 校验（API1 BOLA）已在中间件层收口 ✓。
- `POST /confirm` 幂等：同 quote_id 重复确认返回同一 order_id（quote_book 线程锁 + 覆盖式登记 + 旧版本不回写）✓；409 过期/版本、404/422 语义完整。

## 三、差距结论与本次落地优化

**核心差距（High）**：手写 SSE 管线复刻了框架已原生提供且实现更正确的全部机制（心跳、背压流、结构化取消、wire 编码）。手写版本的重连/挂死类缺陷风险（已发生过一次）属于可整体消除的自造复杂度。

**已落地（server/app.py，本次唯一改动文件）**：
1. `/chat` 端点改为 async 生成器 + `response_class=ChatSSEResponse`（`EventSourceResponse` 子类，合并 `Cache-Control: no-cache`/`X-Accel-Buffering: no`/`X-Resume-Supported: false` 三个响应头）——对齐 FastAPI 官方 SSE 教程写法（来源 1）。
2. 帧产出改 `yield ServerSentEvent(event=..., data=..., id=str(seq))`：wire 编码交给 `format_sse_event`（单行/`\0` 校验免费获得）；12 种业务事件与 `id:` 递增契约不变（SSE 字段顺序无关，来源 2/4）。
3. 删除手写 `asyncio.Queue`/producer 任务/`wait_for(15s)` 心跳/手动 cancel（约 −60 行）：空闲 15s 心跳 `": ping"` 由路由层 `_keepalive_inserter` 自动接管（来源 2，本地源码实测确认）；同步 LangGraph 迭代仍走 `run_in_executor` 线程池。
4. 异常路径语义保留：任何异常 → `error` 事件 + `done(finish_reason="error")`，连接协议不中断。

**验证**：`pytest tests/test_sse.py -q` → **2 passed**（含「流必须自然收尾、末事件 done、id 递增」回归断言）；全量 `pytest tests/` 中仅 `test_persistence.py::test_restart_semantics_sqlite` 失败，故障点在 `server/graph.py:761 retrieve_terms`（`WikiEntry` 对象不可下标——知识检索域并行改动引入），与本域改动无关（本域仅动 server/app.py，且该失败在本次改动前后的运行路径不经过 app.py SSE 代码）。

**未落地（记录为建议）**：
- Last-Event-ID 真续传：需服务端按序号缓冲/重放事件，涉及会话存储改动，超出本域单文件边界；现状「不支持 + 显式声明 + 前端全量重发」是诚实且安全的折中（来源 1「Resuming with Last-Event-ID」节）。
- `retry:` 字段（建议重连间隔 ms）：SPEC §4.1 未定义，前端用 fetch 流自管重连，加了无消费方，暂不加。
- HTTP/1.1 6 连接限制（来源 3）：生产部署走 HTTP/2 或限并发 SSE 即可，属平台域。

## 四、域评分

| 项 | 改造前 | 改造后 | 依据 |
|---|---|---|---|
| SSE 实现方式 | 5/10 手写管线（曾出挂死缺陷） | 8/10 官方原生管线 | 来源 1/2 |
| 断线/心跳契约 | 7/10 手写心跳+显式不支持续传 | 8/10 同上，框架级心跳 | 来源 2/3 |
| REST 语义（/policy /trace /confirm） | 8/10 | 8/10（未动，本就达标） | 实读 |
| 幂等 | 8/10 | 8/10 | 实读 quote_book |

综合：API 域 **8/10**（原 6.5/10；剩余缺口主要是续传与多进程限流/订单存储，跨域依赖）。
