#!/usr/bin/env python3
"""quote-server 自测脚本（不走 LLM，直接断言工具函数）。

覆盖：正常报价、幂等同ID、入参变化新ID、三档三者险价格、越权字段脱敏、
停售/JQX/附加险三种错误、24h 过期判断。
运行：python3 mcp_servers/test_quote_server.py（退出码 0 = 全部通过）
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quote_server as qs  # noqa: E402

TZ = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 11, 11, 23, 0, 0, tzinfo=TZ)  # 固定时钟，日期对齐 SPEC 示例

VIN_1001 = "LSVAA26E2NE100001"  # 张伟 OWN-1001
VIN_1002 = "LBV5S3102NME00002"  # 李静 OWN-1002

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")


print("== 1. get_policy 基础与脱敏 ==")
r = qs._get_policy_impl(owner_id="OWN-1001", now=NOW)
check("found=true", r.get("found") is True)
check("owner 不含 id_number（脱敏）", "id_number" not in r["owner"])
check("owner 不含 phone（脱敏）", "phone" not in r["owner"])
check("policy_version 返回 v2024.3", r["policy"]["policy_version"] == "v2024.3")
check("days_to_expiry=24（2026-12-05 到期）", r["days_to_expiry"] == 24, f"got {r['days_to_expiry']}")
check("expiring_soon=true（≤30天）", r["expiring_soon"] is True)

r2 = qs._get_policy_impl(owner_id="OWN-1002", now=NOW)
check("OWN-1002 非临期 expiring_soon=false", r2["expiring_soon"] is False)

r3 = qs._get_policy_impl(vin="UNKNOWNVIN0000001", now=NOW)
check("查无此人：仅 {found:false, message}", r3 == {"found": False, "message": "未找到保单"}, f"got {r3}")

r4 = qs._get_policy_impl(vin=VIN_1001, now=NOW)
check("按 vin 查询同样命中", r4["found"] is True and r4["owner"]["owner_id"] == "OWN-1001")

print("== 2. query_quote 正常报价（含系数计算）==")
sel = [{"code": "JQX"}, {"code": "DSX", "sum_insured": 2000000}]
q = qs._query_quote_impl(vin=VIN_1001, coverage_selection=sel, now=NOW)
check("无 error", "error" not in q, f"got {q}")
check("quote_id 形如 QT-YYYYMMDD-NNNN", q["quote_id"].startswith("QT-20261111-"))
check("quote_version=1", q["quote_version"] == 1)
check("rates_version=v2025.1", q["rates_version"] == "v2025.1")
# 系数：NCD 0.85（保单反推 2 年无赔）× 用途 1.0 × 车龄 1.05（2023-03 上牌 ≈3.6年 → 2-5年档）
check("ncd=0.85（按 ncd_factor 反推）", q["factors_applied"]["ncd_coefficient"] == 0.85)
check("use_nature=1.0", q["factors_applied"]["use_nature_factor"] == 1.0)
check("vehicle_age=1.05", q["factors_applied"]["vehicle_age_factor"] == 1.05)
# 保费：JQX 950 固定；DSX 200万档 1520×0.85×1.0=1292 → 总 2242
dsx = next(li for li in q["line_items"] if li["code"] == "DSX")
jqx = next(li for li in q["line_items"] if li["code"] == "JQX")
check("JQX 保费 950（法定固定，不参与系数）", jqx["premium"] == 950.0)
check("DSX 200万 = 1520×0.85 = 1292", abs(dsx["premium"] - 1292.0) < 0.01, f"got {dsx['premium']}")
check("premium_total = 2242", abs(q["premium_total"] - 2242.0) < 0.01, f"got {q['premium_total']}")
check("currency=CNY", q["currency"] == "CNY")
check("created_at=2026-11-11T23:00:00+08:00", q["created_at"] == "2026-11-11T23:00:00+08:00")
check("valid_until=created_at+24h", q["valid_until"] == "2026-11-12T23:00:00+08:00")
check("含模拟报价标注", "模拟报价" in q.get("disclaimer", ""))

print("== 3. 幂等：同入参 24h 内同 quote_id 同版本 ==")
q_again = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": 2000000}], now=NOW + timedelta(hours=1))
check("同 quote_id", q_again["quote_id"] == q["quote_id"])
check("同 quote_version", q_again["quote_version"] == q["quote_version"])
check("同 premium_total", q_again["premium_total"] == q["premium_total"])

print("== 4. 入参变化 → 新 quote_id，版本从 1 计数 ==")
q_new = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": 1000000}], now=NOW + timedelta(hours=1))
check("新 quote_id", q_new["quote_id"] != q["quote_id"])
check("新 quote_version=1", q_new["quote_version"] == 1)

print("== 5. 三档三者险按 tiers 计价 ==")
for si, tier_base in [(500000, 780.0), (1000000, 1180.0), (3000000, 1780.0)]:
    qt = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": si}], now=NOW + timedelta(hours=2))
    line = next(li for li in qt["line_items"] if li["code"] == "DSX")
    expect = round(tier_base * 0.85, 2)
    check(f"DSX {si // 10000}万 → {tier_base}×0.85={expect}", abs(line["premium"] - expect) < 0.01, f"got {line['premium']}")
# 非法档位
qe = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": 123456}], now=NOW)
check("非法保额档位报错", "error" in qe)

print("== 6. 三种业务错误 ==")
# 6a 停售
qe = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "FDJJS"}], now=NOW)
check("停售 → COVERAGE_DISCONTINUED", qe.get("error", {}).get("code") == "COVERAGE_DISCONTINUED", f"got {qe}")
check("停售错误附 replacement=CSX 建议", "CSX" in qe["error"]["message"])
# 6b 缺 JQX
qe = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "DSX", "sum_insured": 1000000}], now=NOW)
check("缺 JQX → JQX_REQUIRED", qe.get("error", {}).get("code") == "JQX_REQUIRED", f"got {qe}")
# 6c 附加险前置：YWYW 无 DSX/SJRX/CKRX
qe = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "CSX", "sum_insured": 128000}, {"code": "YWYW"}], now=NOW)
check("YWYW 无主险 → RIDER_PREREQUISITE_MISSING", qe.get("error", {}).get("code") == "RIDER_PREREQUISITE_MISSING", f"got {qe}")
# YWYW 有 DSX 在场 → 通过
qe_ok = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": 1000000}, {"code": "YWYW"}], now=NOW)
check("YWYW 随 DSX 同单 → 通过", "error" not in qe_ok)
# BLPS 需 CSX
qe = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "BLPS"}], now=NOW)
check("BLPS 无 CSX → RIDER_PREREQUISITE_MISSING", qe.get("error", {}).get("code") == "RIDER_PREREQUISITE_MISSING")
# 错误格式统一为 {error:{code,message}}
check("错误统一格式 {error:{code,message}}", set(qe.keys()) == {"error"} and set(qe["error"].keys()) == {"code", "message"})

print("== 7. 24h 过期判断 ==")
check("now=valid_until → 未过期（含边界）", qs._is_expired(q, NOW + timedelta(hours=24)) is False)
check("now>valid_until → 过期", qs._is_expired(q, NOW + timedelta(hours=24, seconds=1)) is True)
# 过期后同参数询价 → 新 quote_id 版本 1
q_re = qs._query_quote_impl(vin=VIN_1001, coverage_selection=sel, now=NOW + timedelta(hours=25))
check("过期后重报：新 quote_id", q_re["quote_id"] != q["quote_id"])
check("过期后重报：quote_version=1", q_re["quote_version"] == 1)
check("过期后重报：valid_until 顺延 24h", q_re["valid_until"] == "2026-11-14T00:00:00+08:00", f"got {q_re['valid_until']}")
# quote_is_stale（供 /confirm）
check("quote_is_stale: 未过期且版本一致 → None", qs.quote_is_stale(q["quote_id"], 1, now=NOW + timedelta(hours=23)) is None)
check("quote_is_stale: 过期 → QUOTE_EXPIRED", qs.quote_is_stale(q["quote_id"], 1, now=NOW + timedelta(hours=25)) == "QUOTE_EXPIRED")
check("quote_is_stale: 版本不符 → QUOTE_VERSION_STALE", qs.quote_is_stale(q["quote_id"], 2, now=NOW) == "QUOTE_VERSION_STALE")
check("quote_is_stale: 不存在 → QUOTE_NOT_FOUND", qs.quote_is_stale("QT-XXXX", 1, now=NOW) == "QUOTE_NOT_FOUND")

print("== 8. 网约车用途系数 1.6 ==")
q_ride = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": 1000000}], use_nature="网约车（营运）", now=NOW + timedelta(hours=3))
check("use_nature_factor=1.6", q_ride["factors_applied"]["use_nature_factor"] == 1.6)
line = next(li for li in q_ride["line_items"] if li["code"] == "DSX")
check("DSX 100万 = 1180×0.85×1.6 = 1604.8", abs(line["premium"] - 1604.8) < 0.01, f"got {line['premium']}")

print("== 9. NCD 显式入参 ==")
q_ncd0 = qs._query_quote_impl(vin=VIN_1001, coverage_selection=[{"code": "JQX"}, {"code": "DSX", "sum_insured": 1000000}], ncd_years_no_claim=0, now=NOW + timedelta(hours=4))
check("ncd_years_no_claim=0 → 系数 1.0", q_ncd0["factors_applied"]["ncd_coefficient"] == 1.0)
line = next(li for li in q_ncd0["line_items"] if li["code"] == "DSX")
check("DSX 100万 无赔0年 = 1180", abs(line["premium"] - 1180.0) < 0.01)

print("== 10. MCP 服务器注册与 stdio 冒烟 ==")
tools = {t.name for t in qs.mcp._tool_manager.list_tools()} if hasattr(qs.mcp, "_tool_manager") else set()
if not tools:
    # SDK 2.x API 兜底
    try:
        tools = {t.name for t in qs.mcp.list_tools()} if callable(getattr(qs.mcp, "list_tools", None)) else set()
    except Exception:
        tools = set()
check("注册了 get_policy / query_quote 两个工具", tools == {"get_policy", "query_quote"}, f"got {tools}")

# stdio 真实链路冒烟（SDK 2.x client）
async def stdio_smoke() -> bool:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).resolve().parent / "quote_server.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("get_policy", {"owner_id": "OWN-1001"})
            import json as _json
            payload = _json.loads(res.content[0].text)
            return payload.get("found") is True and "id_number" not in payload.get("owner", {})

import asyncio

try:
    ok = asyncio.run(stdio_smoke())
    check("stdio 链路：initialize + tools/call get_policy 脱敏返回", ok)
except Exception as e:  # pragma: no cover
    check("stdio 链路冒烟", False, f"exception: {e}")

print(f"\n结果：{PASS} 通过 / {FAIL} 失败")
sys.exit(0 if FAIL == 0 else 1)
