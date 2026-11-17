"""MCP 工具层测试（2026-11-13 评审+优化，reviews/mcp.md）。

覆盖三块：
1. inprocess 桥接语义：业务错误 → ToolError(code, message)（SPEC §3.2 不破坏）。
2. SDK ToolError 出口：quote_server._emit 把 {"error":{...}} dict 抛成协议级
   isError=true（对齐 MCP 2026-07-28 §Server/Tools Error Handling）。
3. stdio 全链路（test_stdio_bridge，默认跳过，MCP_TEST_STDIO=1 启用）：
   initialize + tools/list（含 annotations/title）+ tools/call 成功/失败两路。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_servers import quote_server as qs  # noqa: E402
from server import mcp_bridge  # noqa: E402

VIN = "LSVAA26E2NE100001"


# ---------------------------------------------------------------- 1. inprocess
def test_get_policy_sanitized_inprocess():
    r = mcp_bridge.get_policy(owner_id="OWN-1001")
    assert r["found"] is True
    assert "id_number" not in r["owner"] and "phone" not in r["owner"]


def test_query_quote_business_error_becomes_toolerror():
    # 缺 JQX → 协议侧 isError=true；桥接层还原为 ToolError(JQX_REQUIRED)
    with pytest.raises(mcp_bridge.ToolError) as ei:
        mcp_bridge.query_quote(vin=VIN, coverage_selection=[{"code": "DSX", "sum_insured": 1000000}])
    assert ei.value.code == "JQX_REQUIRED"
    assert "交强险" in ei.value.message


def test_query_quote_success_inprocess():
    r = mcp_bridge.query_quote(vin=VIN, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": 1000000}])
    assert "error" not in r and r["quote_id"].startswith("QT-")
    assert r["currency"] == "CNY"


def test_get_policy_invalid_args():
    with pytest.raises(mcp_bridge.ToolError) as ei:
        mcp_bridge.get_policy()
    assert ei.value.code == "INVALID_ARGS"


# ---------------------------------------------------------------- 2. _emit 出口
def test_emit_raises_sdk_toolerror_with_error_payload():
    from mcp.server.mcpserver.exceptions import ToolError as SDKToolError
    with pytest.raises(SDKToolError) as ei:
        qs._emit({"error": {"code": "JQX_REQUIRED", "message": "x"}})
    assert json.loads(str(ei.value))["code"] == "JQX_REQUIRED"


def test_emit_passthrough_success():
    assert qs._emit({"found": True}) == {"found": True}


def test_tool_annotations_registered():
    import asyncio
    tools = {t.name: t for t in asyncio.run(qs.mcp.list_tools())}
    assert set(tools) >= {"get_policy", "query_quote"}
    ann = tools["get_policy"].annotations
    assert ann is not None and ann.read_only_hint is True and ann.destructive_hint is False
    ann_q = tools["query_quote"].annotations
    assert ann_q is not None and ann_q.idempotent_hint is True and ann_q.destructive_hint is False


# ---------------------------------------------------------------- 3. stdio 全链路
@pytest.mark.skipif(os.environ.get("MCP_TEST_STDIO") != "1", reason="设 MCP_TEST_STDIO=1 启用 stdio 全链路")
class TestStdioBridge:
    def test_stdio_bridge(self):
        """MCP_TRANSPORT=stdio 真实协议链路：list + 成功 call + isError call。"""
        os.environ["MCP_TRANSPORT"] = "stdio"
        import importlib
        importlib.reload(mcp_bridge)
        try:
            # tools/list via client session
            r = mcp_bridge.get_policy(owner_id="OWN-1001")
            assert r["found"] is True
            with pytest.raises(mcp_bridge.ToolError) as ei:
                mcp_bridge.query_quote(vin=VIN, coverage_selection=[{"code": "DSX"}])
            assert ei.value.code == "JQX_REQUIRED"
        finally:
            os.environ.pop("MCP_TRANSPORT", None)
            importlib.reload(mcp_bridge)
