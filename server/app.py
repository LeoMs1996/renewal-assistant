"""FastAPI 应用（REST 契约 = SPEC §4）。

- POST /chat        SSE：驱动 server/graph.py 的 LangGraph 状态机，
                    graph.stream(stream_mode=["custom","values"])（LangGraph 1.x，
                    Context7 查证），节点内 get_stream_writer() 发出的自定义事件
                    在此翻译为 SPEC §4.1 的 12 种 SSE 事件并写轨迹 JSONL（§5）。
- GET  /policy/{owner_id}
- GET  /trace/{trace_id}
- POST /confirm     409 QUOTE_EXPIRED / 409 QUOTE_VERSION_STALE /
                    404 QUOTE_NOT_FOUND / 422 OWNER_MISMATCH
- GET  /health      运维探活（SPEC 外辅助端点）

硬规矩：保费只来自报价服务；输出标注模拟报价/合成数据；代码不含密钥。
"""
from __future__ import annotations

import asyncio
import json
import random
import string
import time
from collections.abc import AsyncIterable
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from . import config, mcp_bridge, quote_book, security, sessions, wiki_search
from . import graph as graph_mod
from . import trace as trace_mod
from .llm import LLM_UNAVAILABLE, LLMUnavailableError, get_client
from .middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    security_log,
    trace_owner_allowed,
)

app = FastAPI(
    title="车险续保助手（模拟报价 · 合成数据）",
    version="0.2.0-orchestration",
)

# 安全中间件（SPEC v1.0.4）。执行顺序 = 后添加者在最外层：
#   SecurityHeaders（最外，保证 401/403/429 也带安全头）
#   → RateLimit（便宜校验先拒）→ Auth → 路由。
#   依据 OWASP DoS Cheat Sheet「validation that is cheap in resources first」。
#   /health 与 / 在 AuthMiddleware.AUTH_EXEMPT_PATHS 中豁免鉴权。
#   三者均为纯 ASGI 中间件（BaseHTTPMiddleware 会中断 SSE 流，见 middleware.py）。
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ------------------------------------------------------------- 前端静态页
# 跨模块缝隙修复（集成Agent）：web/index.html 用同源相对路径（/chat 等），
# 但此前无路由挂载它，GET / 404。补上单一入口页（SPEC §1.1 web/ 为 SSE 工作台）。
@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(config.BASE_DIR / "web" / "index.html")


# ------------------------------------------------------------------ 工具
# SSE 帧序列化/心跳/收尾改用 FastAPI 原生管线（fastapi.sse，0.135+，检索于
# 2026-11-13 https://fastapi.tiangolo.com/tutorial/server-sent-events/）：
#   - ServerSentEvent(event/data/id) 自动编码为 wire 格式（event→data→id 顺序，
#     与旧手写 id→event→data 顺序不同，但 SSE 规范不依赖字段顺序，逐行解析兼容）；
#   - 路由层 _keepalive_inserter 在生成器空闲 15s 时自动插入 ": ping" 注释行
#     （原手写 asyncio.wait_for(15s) 心跳由框架接管）；
#   - 生产者/内存流/取消收尾由路由层任务组结构化处理（PEP 789 语义），
#     替代原手写 asyncio.Queue + 手动 producer.cancel()。

def _new_trace_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"trc-{stamp}-{rand}"


def _err(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message}})


class LLMUnavailableHTTP(Exception):
    """严格模式（SPEC v1.0.5）下探活失败：由上一行异常处理器转成 503。"""

    def __init__(self, probe: dict):
        self.probe = probe
        super().__init__(probe.get("message") or "LLM unavailable")


@app.exception_handler(LLMUnavailableHTTP)
async def _llm_unavailable_handler(_request: Request, exc: LLMUnavailableHTTP):
    """503 + `{"error": {"code": "LLM_UNAVAILABLE", ...}}`（非 200，N13 验收点）。"""
    probe = exc.probe
    return _err(LLM_UNAVAILABLE,
                f"LLM 不可用（{probe.get('error_type')}）：{probe.get('message')}；"
                "严格模式不允许静默降级（RENEWAL_LLM_STRICT=1）", 503)


@app.exception_handler(RequestValidationError)
async def _validation_handler(_request: Request, exc: RequestValidationError):
    """422 + 契约错误体（`{"error": {"code", "message"}}`）。

    安全域（t9，2026-11-17）：FastAPI 默认的 `{"detail": [...]}` 与本项目契约
    不一致，且会把完整入参回显进响应体（OWASP LLM02:2025 所指“通过错误信息
    泄露”）。这里只回字段位置与错误类型，**不回显原值**。
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    kind = str(first.get("type", "invalid"))
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "INVALID_INPUT",
                           "message": f"请求参数不合法：{loc or 'body'}（{kind}）"}})


def strict_llm_guard() -> None:
    """依赖：严格模式开流前探活。

    依赖在路径函数体（含 SSE 生成器）开始前执行 → 失败时响应尚未开始，
    因此能真正返回 503；宽松模式直接放行（零额外上游调用）。
    """
    client = get_client()
    if not client.strict:
        return
    probe = client.preflight()
    if not probe.get("ok"):
        raise LLMUnavailableHTTP(probe)


# ------------------------------------------------------------- 请求模型
# 安全域（t9，2026-11-17）：入参形状校验前移到模型层（OWASP LLM10:2025 的
# Input Validation：输入不得超合理尺寸；同时也避开超长消息把 prompt/轨迹放大）。
# 不合规一律 422 + 契约错误体（见下方 RequestValidationError 处理器）。
_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    session_id: str = Field(pattern=_ID_PATTERN)
    owner_id: str = Field(pattern=_ID_PATTERN)
    message: str = Field(min_length=1, max_length=security.max_message_chars())


class ConfirmRequest(BaseModel):
    session_id: str = Field(pattern=_ID_PATTERN)
    quote_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    quote_version: int = Field(ge=0, le=10_000)
    owner_id: str = Field(pattern=_ID_PATTERN)

# ---------------------------------------------------------------- /chat
class ChatSSEResponse(EventSourceResponse):
    """SSE 响应（FastAPI 原生 EventSourceResponse）+ 代理友好响应头。

    - Cache-Control: no-cache / X-Accel-Buffering: no：MDN SSE 指南要求，
      防中间代理缓冲掐断流（检索于 2026-11-13）。
    - X-Resume-Supported: false：显式声明不支持按 Last-Event-ID 续传，
      前端据此做全量重发而非等待续传。
    """

    def __init__(self, content, status_code: int = 200,
                 headers: dict | None = None, **kwargs):
        merged = {"Cache-Control": "no-cache",
                  "X-Accel-Buffering": "no",
                  "X-Resume-Supported": "false"}
        merged.update(headers or {})
        super().__init__(content, status_code=status_code,
                         headers=merged, **kwargs)


@app.post("/chat", response_class=ChatSSEResponse)
async def chat(req: ChatRequest, request: Request,
               _guard: None = Depends(strict_llm_guard),
               ) -> AsyncIterable[ServerSentEvent]:
    trace_id = _new_trace_id()
    rec = trace_mod.TraceRecorder(trace_id=trace_id, session_id=req.session_id)

    # 会话快照 → 本轮初始 State（跨轮上下文：需求版本/报价/历史/状态）
    session_state = sessions.load(req.session_id)
    initial: dict = dict(session_state)
    initial.update({
        "session_id": req.session_id,
        "trace_id": trace_id,
        "owner_id": req.owner_id,
        "message": req.message,
        # 每轮重算的临时键
        "steps": 0, "intent": "", "confirmed": False, "confirm_error": None,
        "finish_reason": "", "error": None, "exit_reason": None,
        "corrections": [], "out_of_scope": None, "wanted_wiki_ids": [],
        "citations": [], "excerpts": {}, "clarify_questions": [],
        "await_flag": False, "needs_sufficient": True, "need_quote": False,
    })

    compiled = graph_mod.get_graph()

    # Last-Event-ID：本服务未实现按事件序号续传，安全忽略该头并以
    # X-Resume-Supported: false 声明（前端据此做全量重发而非等待续传）。
    _lei = request.headers.get("last-event-id")
    if _lei:
        rec.record("user_message",
                   input=f"[reconnect Last-Event-ID={_lei}, resume unsupported]")

    # 安全域（t9）：入模前清洗（去控制/零宽字符、限长），并把注入检测结果
    # 记进轨迹的 event 字段（不进 record_type，SPEC §5 字段集不变）。
    # 检测结果只做「标记 + 加固」，不做硬拒绝（误报会把正常话术判死，
    # OWASP LLM01 的缓解措施是约束与隔离，不是过滤）。
    scan = security.scan_untrusted(req.message)
    rec.record("user_message", input=security.sanitize_input(req.message),
               event={"security": scan} if scan["level"] != "none" else None)
    if scan["level"] == "high":
        security_log({"path": "/chat", "method": "POST",
                      "client": (request.client.host if request.client else "-")},
                     "prompt_injection_suspected", score=scan["score"],
                     signals=",".join(scan["signals"]))

    loop = asyncio.get_event_loop()
    stream = compiled.stream(
        initial, config={"recursion_limit": 40},
        stream_mode=["custom", "values"],
    )
    final_state: dict = dict(initial)
    _t0 = time.monotonic()  # 会话级耗时观测起点（renewal_chat_duration_seconds）
    seq = 0  # SSE 事件序号（id: 字段），断线重连时前端以 Last-Event-ID 回传

    def _frame(event: str, data: dict) -> ServerSentEvent:
        nonlocal seq
        seq += 1
        return ServerSentEvent(event=event, data=data, id=str(seq))

    def _next_chunk(it):
        sentinel = object()
        try:
            return (True, next(it))
        except StopIteration:
            return (False, sentinel)

    try:
        while True:
            # 同步 LangGraph 迭代放线程池；空闲 15s 时路由层 keepalive
            # 自动下发 ": ping"（原手写队列+wait_for 心跳已删，由框架接管）。
            ok, chunk = await loop.run_in_executor(None, _next_chunk, stream)
            if not ok:
                break
            mode, payload = chunk
            if mode == "custom" and isinstance(payload, dict):
                # 自定义事件 → 轨迹记录 + SSE 帧
                trace_spec = payload.get("trace")
                if isinstance(trace_spec, dict):
                    rec.record(trace_spec.pop("record_type"),
                               node=trace_spec.pop("node", None), **trace_spec)
                data = payload.get("data")
                if data is not None:
                    yield _frame(payload.get("event", "custom"), data)
            elif mode == "values" and isinstance(payload, dict):
                final_state = payload  # 取最后一份完整 State

        # 会话级上下文持久化 + 对话历史归档
        sessions.save(req.session_id, final_state)
        sessions.append_history(req.session_id, "user", req.message)
        if final_state.get("assistant_reply"):
            sessions.append_history(req.session_id, "assistant",
                                    final_state["assistant_reply"])

        finish = final_state.get("finish_reason") or "end"
        from . import metrics as metrics_mod  # 平台工程：会话级 RED + agent 级 semconv 指标
        # 一轮收口：renewal_chat_* + gen_ai.invoke_agent.duration/tool_calls/inference_calls
        # （后者需要轮内计数，故由 metrics 侧按 trace_id 聚合后统一 observe）。
        metrics_mod.finish_turn(trace_id, time.monotonic() - _t0, "done")
        # v1.0.5：降级标记进 done 帧（可选字段，旧客户端忽略），与轨迹双证据
        yield _frame("done", {"trace_id": trace_id, "finish_reason": finish,
                              "degraded": bool(final_state.get("llm_degraded"))})
    except LLMUnavailableError as exc:  # 严格模式：LLM 失败 → 明确错误码（v1.0.5）
        rec.record("error", error={"code": LLM_UNAVAILABLE,
                                   "message": str(exc)[:500]})
        from . import metrics as metrics_mod
        metrics_mod.finish_turn(trace_id, time.monotonic() - _t0, "error")
        yield _frame("error", {"code": LLM_UNAVAILABLE, "message": str(exc)[:500],
                               "error_type": getattr(exc, "error_type", None)})
        yield _frame("done", {"trace_id": trace_id, "finish_reason": "error"})
    except Exception as exc:  # 任何异常 → SSE error 事件，不中断连接协议
        rec.record("error", error={"code": "INTERNAL",
                                   "message": f"{type(exc).__name__}: {exc}"})
        from . import metrics as metrics_mod
        metrics_mod.finish_turn(trace_id, time.monotonic() - _t0, "error")
        yield _frame("error", {"code": "INTERNAL",
                               "message": f"{type(exc).__name__}: {exc}"})
        yield _frame("done", {"trace_id": trace_id, "finish_reason": "error"})


# ---------------------------------------------------------------- /policy
@app.get("/policy/{owner_id}")
async def policy(owner_id: str):
    try:
        result = mcp_bridge.get_policy(owner_id=owner_id)
    except mcp_bridge.ToolError as e:
        return _err(e.code, e.message, 400)
    if not result.get("found"):
        return JSONResponse(status_code=404,
                            content={"found": False, "message": "未找到保单"})
    return result


# ---------------------------------------------------------------- /trace
@app.get("/trace/{trace_id}")
async def get_trace(trace_id: str, request: Request):
    rows = trace_mod.read_trace(trace_id)
    if rows is None:
        return _err("TRACE_NOT_FOUND", f"轨迹 {trace_id} 不存在", 404)
    # 内容级归属校验（OWASP API1 BOLA）：轨迹里出现别的 owner_id 即拒绝。
    # auth_owner 由 AuthMiddleware 从 API-Key 派生，绝不采信请求参数。
    if not trace_owner_allowed(rows, getattr(request.state, "auth_owner", None)):
        return _err("TRACE_FORBIDDEN", "轨迹包含其他车主数据，无权查看", 403)
    return rows


# ---------------------------------------------------------------- /confirm
@app.post("/confirm")
async def confirm(req: ConfirmRequest):
    quote = quote_book.get_quote(req.quote_id)
    if quote is None:
        return _err("QUOTE_NOT_FOUND", f"报价 {req.quote_id} 不存在", 404)

    # 归属校验：quote.vin 必须属于该 owner（越权/不一致 = 422）
    owners = json.loads((config.SYNTHETIC_DIR / "owner.json")
                        .read_text(encoding="utf-8"))["owners"]
    owner = next((o for o in owners if o["owner_id"] == req.owner_id), None)
    if owner is None or quote.get("vin") != owner["vin"]:
        return _err("OWNER_MISMATCH",
                    f"报价与车主 {req.owner_id} 不匹配", 422)

    # 过期校验（AC-12）
    if quote_book.is_expired(quote):
        return _err("QUOTE_EXPIRED",
                    f"报价已于 {quote['valid_until']} 过期，请重新询价", 409)

    # 版本校验（旧版本立即失效）
    if int(req.quote_version) != int(quote["quote_version"]):
        return _err("QUOTE_VERSION_STALE",
                    f"请求版本 v{req.quote_version}，最新版本 v{quote['quote_version']}",
                    409)

    order = quote_book.create_order(quote)
    return order


# ---------------------------------------------------------------- /health
@app.get("/health")
async def health():
    llm = get_client()
    return {
        "status": "ok",
        "llm_mode": "llm" if llm.available else "rule",
        "llm_strict": llm.strict,                      # v1.0.5：严格模式开关状态
        "llm_degraded_total": len(llm.degradations),   # v1.0.5：进程内降级次数
        "wiki_entries": len(wiki_search.get_searcher().entries),
        "graph": "langgraph",
        "nodes": 11,
    }


# ---------------------------------------------------------------- /metrics
@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus 文本暴露（OTel GenAI 语义约定命名，见 server/metrics.py）。

    与 /health 同级运维端点：鉴权豁免但仅输出聚合指标（无 PII、无高基数
    标签——Prometheus 命名实践明确禁止 user id / trace id 类标签）。
    生产建议再由网络层限制抓取来源。
    """
    from . import metrics as metrics_mod

    return Response(content=metrics_mod.render(),
                    media_type="text/plain; version=0.0.4; charset=utf-8")
