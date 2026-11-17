"""MCP 工具桥接：直连 mcp_servers/quote_server.py 的函数（不起子进程）。

约定（与 SPEC §3 一致，供 mcp_servers Agent 对齐）：
  get_policy(owner_id: str | None = None, vin: str | None = None) -> dict
  query_quote(vin: str, coverage_selection: list[dict],
              use_nature: str | None = None,
              ncd_years_no_claim: int | None = None) -> dict

- mcp_servers.quote_server 尚未实现时：get_policy 降级读 synthetic/ 本地实现
  （语义与 SPEC §3.1 完全一致，含脱敏与 expiring_soon）；query_quote 不降级
  （保费只能来自报价服务，硬规矩 #3），抛 BridgeUnavailable。
- 工具错误统一格式 {"error": {code, message}} → 抛 ToolError(code, message)。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from datetime import date, datetime

from . import config

# ---------------------------------------------------------------------------
# 传输模式（评审发现 b 项修复：协议通道从未验证）
# - inprocess（默认）：进程内直连 quote_server 函数。取舍：零子进程开销、演示
#   低延迟；代价是绕过 MCP 协议（initialize/tools/list/tools/call 从未真实走过）。
# - stdio（MCP_TRANSPORT=stdio）：用 mcp SDK ClientSession 以 stdio 子进程真实
#   拉起 quote_server，走完整协议链路（2026-11-13 修复：本模式此前为死代码——
#   _stdio_call 从未被 get_policy/query_quote 调用，注释所称 tests/test_mcp_e2e.py
#   亦不存在；现已接入两条工具出口并由 tests/test_mcp.py::test_stdio_bridge
#   全链路断言）。取舍：常驻子进程 RPC 开销，但协议兼容性可验证。
# 依据：MCP 2026-07-28 规范 §Transports/stdio（客户端拉起子进程、换行分隔
# JSON-RPC，https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio，
# 检索于 2026-11-13）；mcp python-sdk 2.x ClientSession/stdio_client 用法
# （Context7 /modelcontextprotocol/python-sdk，检索于 2026-11-13）。
# ---------------------------------------------------------------------------
_TRANSPORT = os.environ.get("MCP_TRANSPORT", "inprocess").strip().lower()
STDIO_MODE = _TRANSPORT == "stdio"

class ToolError(Exception):
    """MCP 工具业务错误（{"error":{code,message}}）。"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class BridgeUnavailable(Exception):
    """mcp_servers.quote_server 尚未就绪。"""


_quote_server = None


def _load_quote_server():
    global _quote_server
    if _quote_server is None:
        from mcp_servers import quote_server  # 直连函数，不起子进程
        _quote_server = quote_server
    return _quote_server


def _unwrap(result: dict) -> dict:
    if isinstance(result, dict) and isinstance(result.get("error"), dict):
        err = result["error"]
        raise ToolError(err.get("code", "TOOL_ERROR"), err.get("message", ""))
    return result


def _unwrap_exc(exc: Exception) -> ToolError:
    """SDK ToolError（quote_server._emit 抛出，message 为 {code,message} JSON）
    还原为桥接层 ToolError，保持 SPEC §3.2 错误语义不变。"""
    try:
        err = json.loads(str(exc))
        if isinstance(err, dict) and "code" in err:
            return ToolError(err["code"], err.get("message", ""))
    except (ValueError, TypeError):
        pass
    return ToolError("TOOL_ERROR", str(exc))

# ------------------------------------------------------- stdio 协议模式
class _StdioClient:
    """常驻后台线程持有 ClientSession（避免每次调用重建子进程/握手）。

    取舍：daemon 线程随宿主进程退出（演示场景可接受，注释留痕）；正式部署
    应改为进程生命周期管理器。SDK 2.x：ClientSession 需在异步任务内 enter/exit，
    同步侧用 asyncio.run_coroutine_threadsafe 投递 call_tool。
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session = None
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._thread: threading.Thread | None = None

    def start(self, timeout: float = 30.0) -> None:
        if self._thread is not None:
            if not self._ready.wait(timeout):
                raise BridgeUnavailable(f"stdio 模式初始化超时：{self._error}")
            if self._error:
                raise BridgeUnavailable(f"stdio 模式初始化失败：{self._error}")
            return
        self._thread = threading.Thread(target=self._run, name="mcp-stdio-bridge", daemon=True)
        self._thread.start()
        self.start(timeout)

    def _run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(config.BASE_DIR / "mcp_servers" / "quote_server.py")],
            cwd=str(config.BASE_DIR),
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._loop = asyncio.get_running_loop()
                    self._session = session
                    self._ready.set()
                    await asyncio.Event().wait()  # 常驻直到进程退出
        except BaseException as exc:  # 初始化失败也要唤醒等待方
            self._error = exc
            self._ready.set()

    def call(self, name: str, arguments: dict, timeout: float = 60.0) -> dict:
        self.start()
        assert self._session is not None and self._loop is not None
        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, arguments=arguments), self._loop)
        result = future.result(timeout)
        if getattr(result, "is_error", False):
            # isError=true 的 Tool Execution Error：content[0] 为 {error:{code,message}}
            # JSON，还原成 dict 交给 _unwrap → 桥接层 ToolError（SPEC §3.2 语义不变）
            texts = [getattr(b, "text", "") for b in getattr(result, "content", [])]
            try:
                payload = json.loads(texts[0]) if texts else {}
            except ValueError:
                # SDK 可能包装为 "Error executing tool <name>: {json}"——提取首个 { 起的 JSON
                payload = {}
                if texts:
                    i = texts[0].find("{")
                    if i >= 0:
                        try:
                            payload = json.loads(texts[0][i:])
                        except ValueError:
                            payload = {}
            if isinstance(payload, dict) and set(payload) >= {"code", "message"}:
                # _emit 的 ToolError message 即 {code,message}：直接包装为统一错误格式
                payload = {"error": payload}
            if not (isinstance(payload, dict) and isinstance(payload.get("error"), dict)):
                payload = {"error": {"code": "TOOL_ERROR", "message": texts[0] if texts else f"stdio 模式 {name} 工具错误"}}
            return payload
        payload = getattr(result, "structured_content", None)
        if isinstance(payload, dict) and set(payload) == {"result"} and isinstance(payload["result"], dict):
            payload = payload["result"]  # SDK 输出包装兼容
        if not isinstance(payload, dict):
            texts = [getattr(b, "text", "") for b in getattr(result, "content", [])]
            payload = json.loads(texts[0]) if texts and texts[0].strip().startswith("{") else {"raw": texts}
        return payload


_stdio_client_singleton: _StdioClient | None = None
_stdio_lock = threading.Lock()


def _stdio_call(name: str, arguments: dict) -> dict:
    global _stdio_client_singleton
    with _stdio_lock:
        if _stdio_client_singleton is None:
            _stdio_client_singleton = _StdioClient()
    return _unwrap(_stdio_client_singleton.call(name, arguments))


# ---------------------------------------------------------------- get_policy
def get_policy(owner_id: str | None = None, vin: str | None = None) -> dict:
    if not owner_id and not vin:
        raise ToolError("INVALID_ARGS", "owner_id 与 vin 至少提供其一")
    if STDIO_MODE:
        # MCP_TRANSPORT=stdio：真实走 initialize + tools/call 协议链路
        return _stdio_call("get_policy", {"owner_id": owner_id, "vin": vin})
    try:
        return _unwrap(_load_quote_server().get_policy(owner_id=owner_id, vin=vin))
    except BridgeUnavailable:
        raise
    except ImportError:
        return _local_get_policy(owner_id, vin)

def query_quote(
    vin: str,
    coverage_selection: list[dict],
    use_nature: str | None = None,
    ncd_years_no_claim: int | None = None,
) -> dict:
    """保费只能由报价服务计算，不做本地降级。"""
    if STDIO_MODE:
        # MCP_TRANSPORT=stdio：真实走 initialize + tools/call 协议链路
        return _stdio_call("query_quote", {
            "vin": vin,
            "coverage_selection": coverage_selection,
            "use_nature": use_nature,
            "ncd_years_no_claim": ncd_years_no_claim,
        })
    try:
        return _unwrap(
            _load_quote_server().query_quote(
                vin=vin,
                coverage_selection=coverage_selection,
                use_nature=use_nature,
                ncd_years_no_claim=ncd_years_no_claim,
            )
        )
    except Exception as exc:  # noqa: BLE001 — SDK ToolError（_emit）还原为桥接层错误
        if type(exc).__name__ == "ToolError" and not isinstance(exc, ToolError):
            raise _unwrap_exc(exc) from exc
        raise


# ------------------------------------------------- 本地降级实现（get_policy）
def _load_json(name: str) -> dict:
    return json.loads((config.SYNTHETIC_DIR / name).read_text(encoding="utf-8"))


def _local_get_policy(owner_id: str | None, vin: str | None) -> dict:
    owners = _load_json("owner.json")["owners"]
    owner = next(
        (o for o in owners if (owner_id and o["owner_id"] == owner_id)
         or (vin and o["vin"] == vin)), None
    )
    if owner is None:
        return {"found": False, "message": "未找到保单"}
    policy = next(
        (p for p in _load_json("policy.json")["policies"]
         if p["owner_id"] == owner["owner_id"]), None
    )
    if policy is None:
        return {"found": False, "message": "未找到保单"}
    end = datetime.strptime(policy["end_date"], "%Y-%m-%d").date()
    days = (end - date.today()).days
    masked = {k: v for k, v in owner.items() if k not in ("id_number", "phone")}
    return {
        "found": True,
        "owner": masked,
        "policy": policy,
        "days_to_expiry": days,
        "expiring_soon": days <= 30,
    }
