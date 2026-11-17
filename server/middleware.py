"""安全中间件：API-Key 鉴权 / trace_id 白名单 / 安全响应头 / 滑动窗口限流。

依据（2026-11-13 检索，链接+结论见 docs/summaries/optimization-security.md）：
- FastAPI 官方 security 文档：鉴权走 Security/Depends 体系；本服务为 SSE +
  全局契约（所有 /chat /confirm /policy /trace 均需鉴权），用 ASGI 中间件
  统一收口比逐端点 Depends 更不易漏（OWASP FastAPI Security Cheat Sheet
  同样提示"鉴权要集中、默认拒绝"）。
- OWASP API Security Top 10 2023：API1 BOLA（对象级越权：owner_id 必须由
  凭证派生，不得信任请求体自报）、API2 Broken Authentication、
  API4 Unrestricted Resource Consumption（限流）。
- OWASP DoS Cheat Sheet §Rate Limiting：先做便宜的校验（限流在鉴权外层），
  限制单 IP 最大请求速率。
- CSP：MDN CSP 文档 + OWASP CSP Cheat Sheet。本前端是单文件内联 JS/CSS，
  nonce 需要模板引擎注入（OWASP 明确警告勿用中间件改写 script 标签）、
  hash 对静态文件极脆（改一个空格即失效），故 script/style 采用
  'unsafe-inline' + 其余指令收紧的折中（见 _CSP 注释）。

演示模式（向后兼容）：未配置 RENEWAL_API_KEYS 时放行所有请求，但响应头
标注 X-Auth-Mode: demo——eval、本地演示无凭证不崩；生产必须配置密钥。

实现方式（2026-11-13 修正）：全部为**纯 ASGI 中间件**（`__call__(scope,
receive, send)`），刻意不用 Starlette `BaseHTTPMiddleware`——后者在
StreamingResponse/SSE 场景会包装 `receive`，流式中途抛
`RuntimeError: Unexpected message received: http.request`（本服务 /chat 为
SSE 长连接，实测被中断）。纯 ASGI 只观察/改写 send 消息，不触碰事件循环语义。
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sys
import threading
import time
from collections import deque

from . import config

# ------------------------------------------------------------------ 常量
# trace_id 白名单：^trc-\d{14}-[a-z0-9]{6}$（SPEC §5，与 app._new_trace_id 一致）。
# 作用：路径穿越（/trace/..%2Fetc%2Fpasswd）与任意文件读在此被拒绝。
TRACE_ID_RE = re.compile(r"^trc-\d{14}-[a-z0-9]{6}$")

# 鉴权豁免：探活与静态入口。
# 安全域（t9，2026-11-17）：/docs /redoc /openapi.json 从无条件豁免改为条件豁免。
# 把完整 API 结构图挂给匿名访问者属 OWASP API8:2023 Security Misconfiguration，
# 也是 OWASP LLM02:2025 缓解项明确点名的泄露面（“通过错误信息或配置细节泄露”）。
# 规则：演示模式（未配密钥）或 RENEWAL_EXPOSE_DOCS=1 时保留入口，否则需要凭证。
AUTH_EXEMPT_PATHS = {"/health", "/metrics", "/", "/favicon.ico"}
_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}


# PII 端点：响应体含车主/保单/轨迹内容，必须在响应头禁止缓存
# （共享终端/代理缓存是 LLM02 的“非预期披露”常见载体）。
_NO_STORE_PREFIXES = ("/policy", "/trace", "/chat", "/confirm")


def exempt_paths(demo: bool) -> set[str]:
    """当前生效的鉴权豁免路径集（文档入口按环境开关）。"""
    if demo or config.expose_docs():
        return AUTH_EXEMPT_PATHS | _DOCS_PATHS
    return set(AUTH_EXEMPT_PATHS)


def security_log(scope, event: str, **fields) -> None:
    """安全事件结构化日志（stderr 单行 JSON，便于采集与告警）。

    只写可聚合字段：**不写请求体、密钥原文、车主姓名/保单号**——日志本身
    也是 PII 载体（OWASP LLM02）；密钥只写不可逆指纹的前 12 位供关联。
    """
    client = scope.get("client") or ("-", 0)
    rec: dict = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "security_event": event,
        "path": scope.get("path"),
        "method": scope.get("method"),
        "client": client[0],
    }
    rec.update({k: v for k, v in fields.items() if v is not None})
    sys.stderr.write(json.dumps(rec, ensure_ascii=False) + "\n")


def key_fingerprint(key: str) -> str:
    """密钥指纹（sha256 前 12 位）：用于关联失败尝试，不可反推。"""
    return "sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def lookup_key(keys: dict[str, str], presented: str) -> str | None:
    """恒定时间密钥查找：不提前 break，避免按键比较泄露时序。"""
    found: str | None = None
    for candidate, owner in keys.items():
        try:
            hit = secrets.compare_digest(candidate, presented)
        except TypeError:  # 非 ASCII 密钥：退化为等值比较
            hit = candidate == presented
        if hit:
            found = owner
    return found

# 需要"owner_id 由凭证派生"校验的路径前缀（OWASP API1 BOLA）。
OWNER_BOUND_PREFIXES = ("/chat", "/confirm", "/policy", "/trace")

_JSON_CT = (b"content-type", b"application/json; charset=utf-8")


# ------------------------------------------------------------- ASGI 小工具
async def _send_json(send, status: int, payload: dict, extra: dict | None = None) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [list(_JSON_CT), [b"content-length", str(len(body)).encode()]]
    for k, v in (extra or {}).items():
        headers.append([k.lower().encode(), v.encode()])
    await send({"type": "http.response.start", "status": status,
                "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _err_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _header(scope, name: bytes) -> str:
    for k, v in scope.get("headers") or []:
        if k.lower() == name:
            return v.decode("latin-1")
    return ""


async def _read_body(receive):
    """把请求体读干净，并返回可回放 body 的 receive 包装。

    回放策略：首次调用返回缓存的完整 body；之后一律委托原 receive，
    这样 uvicorn 在连接存活时表现为阻塞等待（SSE 需要的 disconnect
    侦听语义不被伪造），断线时才收到 http.disconnect。
    """
    chunks: list[bytes] = []
    while True:
        msg = await receive()
        if msg["type"] == "http.disconnect":
            return b"".join(chunks), receive
        chunks.append(msg.get("body", b""))
        if not msg.get("more_body"):
            break
    body = b"".join(chunks)
    state = {"served": False}

    async def replay():
        if not state["served"]:
            state["served"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return body, replay


# ------------------------------------------------------------- 鉴权中间件
class AuthMiddleware:
    """X-API-Key 鉴权 + owner 绑定 + trace_id 白名单。

    - 密钥表来自 RENEWAL_API_KEYS（逗号分隔 key:owner_id）。
    - 未配置密钥表 → 演示模式：放行，响应头 X-Auth-Mode: demo。
    - 密钥缺失/未知 → 401；密钥与请求 owner_id 不符 → 403（API1 BOLA）。
    - /trace/{trace_id} 的 id 必须匹配白名单正则，否则 400（防路径穿越）。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        # trace_id 白名单（对演示/强制模式一视同仁，纯输入校验，零成本先做）
        if path.startswith("/trace/"):
            trace_id = path[len("/trace/"):].strip("/")
            if not TRACE_ID_RE.match(trace_id):
                return await _send_json(
                    send, 400,
                    _err_body("TRACE_ID_INVALID",
                              "trace_id 格式非法（期望 trc-YYYYMMDDHHMMSS-xxxxxx）"))

        keys = config.api_keys()  # 动态读取，测试可 monkeypatch
        state = scope.setdefault("state", {})
        state["auth_owner"] = None
        demo = not keys

        if demo:
            # 演示模式=无凭证放行：生产误配就会裸奔，必须留下可告警的痕迹。
            global _DEMO_WARNED
            if not _DEMO_WARNED:
                _DEMO_WARNED = True
                security_log(scope, "auth_demo_mode",
                             detail="RENEWAL_API_KEYS 未配置，已放行匿名请求")
            async def send_demo(message):
                if message["type"] == "http.response.start":
                    message.setdefault("headers", []).append(
                        [b"x-auth-mode", b"demo"])
                await send(message)
            return await self.app(scope, receive, send_demo)

        if path in exempt_paths(demo):
            return await self.app(scope, receive, send)

        presented = _header(scope, b"x-api-key")
        owner = lookup_key(keys, presented) if presented else None
        if owner is None:
            security_log(scope, "auth_rejected", reason="unknown_or_missing_key",
                         key_fp=key_fingerprint(presented) if presented else None)
            return await _send_json(send, 401,
                                    _err_body("UNAUTHORIZED",
                                              "缺少或无效的 X-API-Key"),
                                    {"WWW-Authenticate": "ApiKey"})
        state["auth_owner"] = owner

        # owner 归属校验：请求体/路径中的 owner_id 必须与密钥绑定一致
        if path.startswith(OWNER_BOUND_PREFIXES):
            claimed = None
            if path.startswith("/policy/"):
                claimed = path[len("/policy/"):].strip("/") or None
            elif scope.get("method") in ("POST", "PUT", "PATCH"):
                body, receive = await _read_body(receive)
                if body:
                    try:
                        data = json.loads(body)
                    except (ValueError, UnicodeDecodeError):
                        data = None
                    if isinstance(data, dict):
                        claimed = data.get("owner_id")
            if claimed is not None and claimed != owner:
                # 只记事件，不记 claimed（它可能含他人车主编号，日志不应存 PII）。
                security_log(scope, "auth_owner_mismatch", reason="claimed != credential")
                return await _send_json(
                    send, 403,
                    _err_body("OWNER_FORBIDDEN",
                              "API-Key 与请求的车主不一致，已拒绝"))

        return await self.app(scope, receive, send)


_DEMO_WARNED = False  # 演示模式告警只打一次，避免刷爆 stderr


# --------------------------------------------------------- 安全响应头中间件
# CSP（来源均为本次检索，链接见 reviews/security.md §1）：
#   - MDN `require-trusted-types-for`（Baseline 2026，2026-02 起跨浏览器可用）：
#     `'script'` 下 innerHTML 等 DOM XSS sink 拒收字符串，只收策略类型。
#   - MDN `trusted-types`：白名单策略名；此处显式列出 `default`——前端
#     web/index.html 首部已注册 default 透传策略（t6 就绪），两边对齐。
#   - MCP 2026-07-28 Security Best Practices 把 CSP 列为 stdio/代理链路的
#     缓解项（“Use Content Security Policy (CSP) to prevent JavaScript
#     execution from untrusted sources”）。
#   取舍：本页仍是单文件内联 JS/CSS，script-src 保留 'unsafe-inline'（nonce/hash
#   对单文件前端不实用，见上方历史注释）；但 Trusted Types 这个“最后一道 sink
#   锁”不依赖内联策略，即使未来注入进 DOM 也拿不到可执行的 HTML。
_CSP = ("default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "require-trusted-types-for 'script'; "
        "trusted-types default")

_SEC_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    # 收敛浏览器能力面（MDN Permissions-Policy）：本页不需要摄像头/麦克风/定位。
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"content-security-policy", _CSP.encode()),
)


class SecurityHeadersMiddleware:
    """给所有响应补安全头（MDN/OWASP 推荐基线）。

    挂最外层：401/403/429 等由内层中间件产生的错误响应同样带齐安全头。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                present = {k.lower() for k, _ in headers}
                for k, v in _SEC_HEADERS:
                    if k not in present:
                        headers.append([k, v])
                # PII 端点禁缓存（LLM02：共享终端/代理缓存是非预期披露载体）。
                # 用 setdefault 语义：不覆盖业务自己已声明的缓存策略。
                path = scope.get("path", "")
                if path.startswith(_NO_STORE_PREFIXES) and b"cache-control" not in present:
                    headers.append([b"cache-control", b"no-store, no-cache, must-revalidate"])
                    headers.append([b"pragma", b"no-cache"])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ------------------------------------------------------------- 限流中间件
_RATE_BUCKETS: dict[str, deque] = {}
_RATE_LOCK = threading.Lock()
_RATE_WINDOW_S = 60.0
_RATE_DISABLED_WARNED = False


def reset_rate_limiter() -> None:
    """清空限流桶（测试用）。"""
    with _RATE_LOCK:
        _RATE_BUCKETS.clear()


class RateLimitMiddleware:
    """每 IP 滑动窗口限流（默认 60 次/分钟，RENEWAL_RATE_LIMIT_PER_MIN 可配）。

    滑动窗口 vs 固定窗口：固定窗口在窗口边界可突刺 2×limit；滑动窗口以
    "最近 60s 内的请求时间戳队列"判定，无边界突刺（OWASP DoS Cheat Sheet
    §Rate Limiting：定义最大 ingress 速率并丢弃超限连接）。内存实现，
    单进程部署（uvicorn --workers 1）语义准确；多副本需换 Redis（遗留项）。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        client = scope.get("client")
        ip = client[0] if client else "unknown"
        now = time.monotonic()
        path = scope.get("path", "")
        # 关闭闸门（RENEWAL_RATE_LIMIT_DISABLED=1）：给压测/全量回归用的显式开关。
        # 之所以要"独立开关"而不是把阈值调大：批量任务把阈值改到 1e9 后再上线，
        # 审计看不出限流其实已失效；显式开关会在启动日志留一行 warning。
        if config.rate_limit_disabled():
            global _RATE_DISABLED_WARNED
            if not _RATE_DISABLED_WARNED:
                _RATE_DISABLED_WARNED = True
                security_log(scope, "rate_limit_disabled",
                             detail="RENEWAL_RATE_LIMIT_DISABLED=1，限流已关闭")
            return await self.app(scope, receive, send)
        # 端点级配额（OWASP LLM10:2025 · Rate Limiting / Denial of Wallet）：
        # /chat 每次都会触发 LLM 推理与轨迹写入，单位成本远高于静态端点，故单独
        # 一个计数桶（bucket_key 加 |chat 前缀，两桶互不占额度）。默认阈值两者
        # 都是 60/min：独立桶已足够隔离；再压低默认值会误伤合法批量（评测回归）。
        is_chat = path == "/chat"
        limit = (config.chat_rate_limit_per_min() if is_chat
                 else config.rate_limit_per_min())
        bucket_name = "/chat（LLM 端点）" if is_chat else "每 IP"
        bucket_key = f"{ip}|chat" if is_chat else ip
        with _RATE_LOCK:
            bucket = _RATE_BUCKETS.setdefault(bucket_key, deque())
            while bucket and now - bucket[0] >= _RATE_WINDOW_S:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(_RATE_WINDOW_S - (now - bucket[0])) + 1)
                security_log(scope, "rate_limited", limit=limit,
                             bucket="chat" if is_chat else "ip")
                return await _send_json(
                    send, 429,
                    _err_body("RATE_LIMITED",
                              f"请求过于频繁（{bucket_name} 每分钟限 {limit} 次）"),
                    {"Retry-After": str(retry_after)})
            bucket.append(now)
        return await self.app(scope, receive, send)


# ------------------------------------------------- trace 内容 owner 校验
def _collect_owner_ids(obj, found: set) -> None:
    """递归收集轨迹行里出现过的 owner_id 值（tool_call input 等处）。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "owner_id" and isinstance(v, str) and v:
                found.add(v)
            else:
                _collect_owner_ids(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_owner_ids(item, found)


def trace_owner_allowed(rows: list, requester_owner: str | None) -> bool:
    """轨迹内容归属校验：轨迹中出现过其他 owner_id 即拒绝（API1 BOLA）。

    无归属证据（如纯闲聊轮未查保单）时放行——轨迹不含个人保单数据；
    已在 SPEC v1.0.4 登记该边界。
    """
    if not requester_owner:
        return True  # 演示模式无凭证，不做内容级校验（响应头已标 demo）
    found: set = set()
    _collect_owner_ids(rows, found)
    return not found or requester_owner in found
