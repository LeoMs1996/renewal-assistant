#!/usr/bin/env python3
"""quote-server — MCP 服务器（车险续保助手）

按 SPEC.md v1.0.0 §3 暴露两个工具：
  - get_policy(owner_id?, vin?)   读取合成保单（脱敏）
  - query_quote(vin, coverage_selection, use_nature?, ncd_years_no_claim?)  报价试算

实现说明（MCP Python SDK 2.x，Context7 查证要点）：
  - FastMCP 在 SDK 2.x 已更名为 MCPServer：`from mcp.server import MCPServer`
  - `mcp.run()` 不传参即 stdio 传输
  - `@mcp.tool()` 装饰器注册工具；返回 dict 即结构化输出（Pydantic TypeAdapter 校验）

数据来源：synthetic/*.json（全部为虚构合成数据，仅用于演示与教学）。
报价保费一律由本服务按 rates.json 费率表计算，模型不得编造。
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# 常量与数据装载
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
SYNTHETIC_DIR = BASE_DIR.parent / "synthetic"

TZ = ZoneInfo("Asia/Shanghai")
QUOTE_TTL = timedelta(hours=24)          # SPEC §3.2 规则 1：24h 有效期
EXPIRING_SOON_THRESHOLD = 30             # SPEC §3.1：days_to_expiry <= 30

mcp = MCPServer("quote-server")


def _load(name: str) -> dict[str, Any]:
    with open(SYNTHETIC_DIR / name, encoding="utf-8") as f:
        return json.load(f)


_OWNER_DATA = _load("owner.json")
_POLICY_DATA = _load("policy.json")
_RATES_DATA = _load("rates.json")

_OWNERS = {o["owner_id"]: o for o in _OWNER_DATA["owners"]}
_OWNERS_BY_VIN = {o["vin"]: o for o in _OWNER_DATA["owners"]}
_POLICIES = {p["policy_id"]: p for p in _POLICY_DATA["policies"]}


# ---------------------------------------------------------------------------
# 报价存储（进程内；quote_id 幂等与版本自增依据 SPEC §3.2）
# ---------------------------------------------------------------------------

_QUOTES: dict[str, dict[str, Any]] = {}          # quote_id -> quote
_QUOTE_SEQ: dict[str, int] = {}                  # "YYYYMMDD" -> 序号

# P1b 修复（评审 review.md AC-12）：quote_id 序号持久化，重启不撞号。
# 序号文件 traces/quote_seq.json 记录各日期已用最大序号；初始化时再从报价
# 登记簿 traces/quotes.json（含 orders 内登记的报价）的已有 quote_id 兜底取
# 最大值，保证“基于日期 + 已有数据文件最大值续号”。
_SEQ_LOCK = __import__("threading").Lock()
_TRACES_DIR = BASE_DIR.parent / "traces"
_SEQ_FILE = _TRACES_DIR / "quote_seq.json"
_QUOTE_BOOK_FILE = _TRACES_DIR / "quotes.json"


def _max_seq_from_quote_ids(qids: list[str]) -> dict[str, int]:
    """从 QT-YYYYMMDD-NNNN 形式的 quote_id 列表提取各日期最大序号。"""
    out: dict[str, int] = {}
    for qid in qids:
        m = re.match(r"^QT-(\d{8})-(\d+)$", str(qid))
        if m:
            day, seq = m.group(1), int(m.group(2))
            out[day] = max(out.get(day, 0), seq)
    return out


def _init_quote_seq() -> dict[str, int]:
    """模块加载时恢复持久化序号（序号文件 + 登记簿兜底）。"""
    seq: dict[str, int] = {}
    try:
        if _SEQ_FILE.is_file():
            seq.update(_max_seq_from_quote_ids(
                [f"QT-{d}-{n:04d}" for d, n in json.loads(
                    _SEQ_FILE.read_text(encoding="utf-8")).items()]))
    except Exception:
        pass
    try:
        if _QUOTE_BOOK_FILE.is_file():
            data = json.loads(_QUOTE_BOOK_FILE.read_text(encoding="utf-8"))
            ids = list((data.get("quotes") or {}).keys())
            for o in (data.get("orders") or {}).values():
                if isinstance(o, dict) and o.get("quote_id"):
                    ids.append(o["quote_id"])
            for d, n in _max_seq_from_quote_ids(ids).items():
                seq[d] = max(seq.get(d, 0), n)
    except Exception:
        pass
    return seq


_QUOTE_SEQ.update(_init_quote_seq())


def _persist_quote_seq() -> None:
    """把当前序号写回序号文件（最好力度的原子性：临时文件 + replace）。"""
    try:
        _TRACES_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _SEQ_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_QUOTE_SEQ), encoding="utf-8")
        tmp.replace(_SEQ_FILE)
    except Exception:
        pass  # 持久化失败不阻断报价（下次启动仍有登记簿兜底）


def _next_quote_id(now: datetime) -> str:
    """生成全局不重复 quote_id（跨进程/重启：序号持久化 + 登记簿续号）。"""
    with _SEQ_LOCK:
        day_key = now.strftime("%Y%m%d")
        _QUOTE_SEQ[day_key] = _QUOTE_SEQ.get(day_key, 0) + 1
        qid = f"QT-{day_key}-{_QUOTE_SEQ[day_key]:04d}"
        # 撞号防御：当前进程登记簿里若已有该 ID（不应发生），继续自增直到不撞
        while qid in _QUOTES:
            _QUOTE_SEQ[day_key] += 1
            qid = f"QT-{day_key}-{_QUOTE_SEQ[day_key]:04d}"
        _persist_quote_seq()
        return qid

def _now() -> datetime:
    return datetime.now(TZ)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _error(code: str, message: str) -> dict[str, Any]:
    """SPEC §3.2 工具错误统一格式。"""
    return {"error": {"code": code, "message": message}}

# ---------------------------------------------------------------------------
# 协议错误出口（2026-07-28 规范 §Server/Tools Error Handling：业务校验失败属于
# Tool Execution Error，应置 isError=true 并把可自纠信息放进 content，而不是
# 伪装成成功结果；检索于 2026-11-13，来源见 reviews/mcp.md）
# ---------------------------------------------------------------------------

def _emit(result: dict[str, Any]) -> dict[str, Any]:
    """工具出口：业务错误 dict 抛 SDK ToolError（→ isError=true + content JSON）。

    inprocess 直连调用方（server/mcp_bridge.py）仍可捕获 ToolError 并还原
    {code, message}，SPEC §3.2 工具错误格式不破坏。
    """
    if isinstance(result, dict) and isinstance(result.get("error"), dict):
        raise ToolError(json.dumps(result["error"], ensure_ascii=False))
    return result
# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _vehicle_age_years(first_registration_date: str, today: date) -> int:
    reg = date.fromisoformat(first_registration_date)
    return max(0, today.year - reg.year - ((today.month, today.day) < (reg.month, reg.day)))


def _vehicle_age_factor(first_registration_date: str, today: date) -> float:
    age = _vehicle_age_years(first_registration_date, today)
    tiers = _RATES_DATA["factors"]["vehicle_age_factor"]["tiers"]
    for tier in tiers:
        m = re.match(r"^(\d+)-(\d+)年$", tier["age_range"])
        if m and int(m.group(1)) <= age <= int(m.group(2)):
            return float(tier["coefficient"])
        if tier["age_range"].endswith("年以上"):
            low = int(tier["age_range"].replace("年以上", ""))
            if age > low:
                return float(tier["coefficient"])
    return 1.0


def _resolve_ncd(ncd_years_no_claim: int | None, owner: dict[str, Any]) -> float:
    """SPEC §3.2：ncd_years_no_claim 缺省时按 policy.ncd_factor 反推。"""
    tiers = _RATES_DATA["factors"]["ncd_coefficient"]["tiers"]
    if ncd_years_no_claim is not None:
        for tier in tiers:
            if tier.get("years_no_claim") == ncd_years_no_claim:
                return float(tier["coefficient"])
        # 超出表内年数：取最优档
        best = min((t for t in tiers if "years_no_claim" in t), key=lambda t: t["coefficient"])
        return float(best["coefficient"])
    # 反推：用当前保单的 ncd_factor 找对应档位
    policy = _POLICIES.get(owner.get("current_policy_id", ""))
    target = float(policy["ncd_factor"]) if policy else 1.0
    for tier in tiers:
        if abs(float(tier["coefficient"]) - target) < 1e-9:
            return float(tier["coefficient"])
    return 1.0


def _days_to_expiry(end_date: str, today: date) -> int:
    return (date.fromisoformat(end_date) - today).days


def _is_expired(quote: dict[str, Any], now: datetime) -> bool:
    """SPEC §3.2 规则 4：valid_until 过期判断。"""
    valid_until = datetime.fromisoformat(quote["valid_until"])
    return now > valid_until


# ---------------------------------------------------------------------------
# 险种基准保费计算（SPEC §2.3 / rates.json base_premium）
# ---------------------------------------------------------------------------

def _line_base_premium(code: str, sum_insured: int | None, owner: dict[str, Any],
                       policy: dict[str, Any] | None) -> tuple[float | None, str | None, int | None]:
    """返回 (基准保费, 错误消息, 实际采用的 sum_insured)。"""
    bp = _RATES_DATA["base_premium"]
    if code not in bp:
        return None, f"险种 {code} 无费率定义（模拟数据未提供该险种费率）", None

    entry = bp[code]
    if code == "JQX":
        return float(entry["base_premium_home_private"]), None, int(entry["sum_insured"])
    if code == "CSX":
        # sum_insured 缺省沿用当前保单车损保额
        if sum_insured is None:
            for cov in (policy or {}).get("coverages", []):
                if cov["code"] == "CSX":
                    sum_insured = int(cov["sum_insured"])
                    break
        if sum_insured is None:
            return None, "车损险需提供 sum_insured（当前保单无车损险可沿用）", None
        premium = sum_insured / 10000 * float(entry["base_rate_per_10k_sum"])
        return premium, None, sum_insured
    if code == "DSX":
        if sum_insured is None:
            sum_insured = 1000000  # 缺省取费率表默认档（100万）
        tiers = entry["tiers"]
        key = str(int(sum_insured))
        if key not in tiers:
            valid = "、".join(f"{int(k) // 10000}万" for k in tiers)
            return None, f"三者险保额 {sum_insured} 不在可选档位（{valid}）", None
        return float(tiers[key]), None, int(sum_insured)
    if code == "YWYW":
        si = int(entry["sum_insured"]) if sum_insured is None else int(sum_insured)
        return float(entry["base_premium"]), None, si
    if code == "BLPS":
        # v1.0.1：rates.json 补录划痕险费率（SPEC §2.3 已登记）
        si = int(entry["sum_insured"]) if sum_insured is None else int(sum_insured)
        return float(entry["base_premium"]), None, si
    if code in ("SJRX", "CKRX"):
        if sum_insured is None:
            return None, f"{entry['name']} 需提供 sum_insured（每座保额）", None
        premium = sum_insured / 10000 * float(entry["base_premium_per_10k_seat"])
        return premium, None, int(sum_insured)
    return None, f"险种 {code} 费率结构未实现", None


# ---------------------------------------------------------------------------
# get_policy 实现（SPEC §3.1）
# ---------------------------------------------------------------------------

def _get_policy_impl(owner_id: str | None = None, vin: str | None = None,
                     now: datetime | None = None) -> dict[str, Any]:
    if not owner_id and not vin:
        return _error("INVALID_PARAMS", "owner_id 与 vin 必须提供其一")
    owner = _OWNERS.get(owner_id or "") or _OWNERS_BY_VIN.get(vin or "")
    if owner is None:
        return {"found": False, "message": "未找到保单"}
    policy = _POLICIES.get(owner["current_policy_id"])
    if policy is None:
        return {"found": False, "message": "未找到保单"}

    now = now or _now()
    days = _days_to_expiry(policy["end_date"], now.date())

    # 脱敏：剔除 id_number 与 phone（SPEC §3.1）
    owner_sanitized = {k: v for k, v in owner.items() if k not in ("id_number", "phone")}

    return {
        "found": True,
        "owner": owner_sanitized,
        "policy": policy,
        "days_to_expiry": days,
        "expiring_soon": days <= EXPIRING_SOON_THRESHOLD,
    }


@mcp.tool(
    title="读取当前保单",
    # 2026-07-28 规范 §Server/Tools：annotations 为可选行为提示（客户端 MUST 视为不可信）。
    # get_policy 纯读取、无副作用 → read_only_hint=true, destructive_hint=false
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False),
)
def get_policy(owner_id: str | None = None, vin: str | None = None) -> dict[str, Any]:
    """读取车主当前保单（合成数据，脱敏输出：不含身份证号与手机号）。

    Args:
        owner_id: 车主ID（与 vin 二选一）
        vin: 车架号（与 owner_id 二选一）

    Returns:
        found=true 时含 owner（脱敏）/ policy / days_to_expiry / expiring_soon；
        found=false 时仅 {found, message}。
    """
    result = _get_policy_impl(owner_id=owner_id, vin=vin)
    return _emit(result)

# ---------------------------------------------------------------------------
# query_quote 实现（SPEC §3.2）
# ---------------------------------------------------------------------------

def _validate_selection(codes: list[str]) -> dict[str, Any] | None:
    """SPEC §3.2 规则 5/6：停售、交强险前置、附加险前置校验。"""
    code_set = set(codes)

    # 规则 5a：停售险种
    for d in _RATES_DATA["discontinued_coverages"]:
        if d["code"] in code_set:
            return _error(
                "COVERAGE_DISCONTINUED",
                f"{d['name']}（{d['code']}）已自 {d['discontinued_since']} 停售：{d['note']}；"
                f"建议改投 {d['replacement']}",
            )

    # 规则 5b：缺交强险
    if "JQX" not in code_set:
        return _error("JQX_REQUIRED", "交强险为法定强制保险，报价必须包含 JQX（交强险不可删除）")

    # 规则 6：附加险前置
    if "YWYW" in code_set and not ({"DSX", "SJRX", "CKRX"} & code_set):
        return _error("RIDER_PREREQUISITE_MISSING", "医保外用药责任险（YWYW）为附加险，需同单投保三者险（DSX）或车上人员责任险（SJRX/CKRX）")
    if "BLPS" in code_set and "CSX" not in code_set:
        return _error("RIDER_PREREQUISITE_MISSING", "车身划痕损失险（BLPS）为附加险，需先投保机动车损失险（CSX）")
    return None


def _quote_cache_key(vin: str, selection: list[dict[str, Any]], use_nature: str,
                     ncd: float) -> str:
    """幂等键：vin + 归一化险种选择（解析出实际 sum_insured 后按 code 排序）+ 用途 + NCD。"""
    norm = json.dumps(
        sorted((it["code"], it.get("sum_insured_resolved")) for it in selection),
        ensure_ascii=False, sort_keys=True,
    )
    return f"{vin}|{norm}|{use_nature}|{ncd}"


def _query_quote_impl(vin: str, coverage_selection: list[dict[str, Any]],
                      use_nature: str | None = None,
                      ncd_years_no_claim: int | None = None,
                      now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()

    owner = _OWNERS_BY_VIN.get(vin)
    if owner is None:
        return _error("OWNER_NOT_FOUND", f"车架号 {vin} 未找到对应车主（合成数据）")
    policy = _POLICIES.get(owner["current_policy_id"])

    if not coverage_selection or not isinstance(coverage_selection, list):
        return _error("INVALID_PARAMS", "coverage_selection 不能为空")

    codes = []
    for item in coverage_selection:
        code = item.get("code")
        if not code:
            return _error("INVALID_PARAMS", f"coverage_selection 元素缺少 code：{item}")
        codes.append(code)

    # ---- 规则 5/6 校验 ----
    err = _validate_selection(codes)
    if err is not None:
        return err

    # ---- 系数解析 ----
    eff_use_nature = use_nature or owner["use_nature"]
    un_factor_table = _RATES_DATA["factors"]["use_nature_factor"]
    if eff_use_nature not in un_factor_table:
        return _error("INVALID_USE_NATURE", f"使用性质「{eff_use_nature}」不在费率表用途系数中")
    use_nature_factor = float(un_factor_table[eff_use_nature])

    ncd_factor = _resolve_ncd(ncd_years_no_claim, owner)
    age_factor = _vehicle_age_factor(owner["first_registration_date"], now.date())

    # ---- 逐险种基准保费（同时解析实际 sum_insured）----
    line_items: list[dict[str, Any]] = []
    commercial_total = 0.0
    jqx_total = 0.0
    selection_resolved: list[dict[str, Any]] = []

    for item in coverage_selection:
        code = item["code"]
        sum_in = item.get("sum_insured")
        base, msg, resolved_si = _line_base_premium(code, sum_in, owner, policy)
        if base is None:
            return _error("RATE_NOT_FOUND", msg)
        name = _RATES_DATA["base_premium"][code]["name"]

        if code == "JQX":
            # 交强险为法定固定保费，不参与商业险系数浮动
            premium = base
            jqx_total += premium
        else:
            # SPEC §2.3：商业险 = Σ基准 × NCD × 用途系数；车龄系数仅作用于车损险部分
            premium = base * ncd_factor * use_nature_factor
            if code == "CSX":
                premium *= age_factor
            commercial_total += premium

        line_items.append({
            "code": code,
            "name": name,
            "sum_insured": resolved_si,
            "premium": round(premium, 2),
        })
        selection_resolved.append({"code": code, "sum_insured_resolved": resolved_si})

    premium_total = round(jqx_total + commercial_total, 2)
    cache_key = _quote_cache_key(vin, selection_resolved, eff_use_nature, ncd_factor)

    # ---- 规则 2：24h 内同入参幂等，返回同一 quote_id 且版本不变 ----
    # 前提补充（2026-11-13 修正）：仅当费率表版本未变时才幂等直返。
    # 否则命中下面的规则 3（版本自增）；原实现缺此条件，使规则 3 永远不可达
    # （评审 b 项「死代码」的真实成因不在缺少自增代码，而在幂等短路过早返回）。
    for quote in _QUOTES.values():
        if (quote["_cache_key"] == cache_key
                and quote["rates_version"] == _RATES_DATA["version"]
                and not _is_expired(quote, now)):
            out = {k: v for k, v in quote.items() if not k.startswith("_")}
            return out

    # ---- 规则 3（SPEC v1.0.3 落实，原为死代码）：同入参且费率表版本变化 ----
    # 同 quote_id 重算：quote_version 自增（1→2→…）、保费/valid_until 重出、旧版本立即失效。
    # 旧实现仅写注释、恒新发 v1，与 SPEC §3.2 规则 3 文实不符（评审发现 b 项）。
    prev = next(
        (q for q in _QUOTES.values()
         if q["_cache_key"] == cache_key
         and q["rates_version"] != _RATES_DATA["version"]),
        None,
    )
    if prev is not None:
        quote_id = prev["quote_id"]                       # 复用同 quote_id
        quote_version = int(prev["quote_version"]) + 1     # 版本自增
        superseded = list(prev.get("_superseded_versions", [])) + [int(prev["quote_version"])]
    else:
        quote_id = _next_quote_id(now)   # P1b：持久化序号，跨进程/重启不撞号（AC-12）
        quote_version = 1
        superseded = []
    created_at = now
    quote = {
        "quote_id": quote_id,
        "vin": vin,
        "quote_version": quote_version,
        "rates_version": _RATES_DATA["version"],
        "factors_applied": {
            "ncd_coefficient": ncd_factor,
            "use_nature_factor": use_nature_factor,
            "vehicle_age_factor": age_factor,
        },
        "line_items": line_items,
        "premium_total": premium_total,
        "currency": "CNY",
        "created_at": _iso(created_at),
        "valid_until": _iso(created_at + QUOTE_TTL),  # 规则 1：valid_until = created_at + 24h
        "disclaimer": "模拟报价：基于合成费率数据计算，仅供参考",
        "_cache_key": cache_key,
        "_created_dt": created_at.isoformat(),
        "_superseded_versions": superseded,  # 规则3：已被自增取代的历史版本号
    }
    _QUOTES[quote_id] = quote
    return {k: v for k, v in quote.items() if not k.startswith("_")}


@mcp.tool(
    title="车险报价试算",
    # query_quote 会产生新报价状态（quote_id），非纯读；但 SPEC §3.2 规则 2
    # 保证 24h 内同入参幂等（同 quote_id 同版本）→ idempotent_hint=true
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True,
    ),
)
def query_quote(vin: str, coverage_selection: list[dict[str, Any]],
                use_nature: str | None = None,
                ncd_years_no_claim: int | None = None) -> dict[str, Any]:
    """车险报价试算（保费由费率服务计算，模拟报价，合成数据）。

    Args:
        vin: 车架号（必填）
        coverage_selection: 投保险种选择 [{code, sum_insured?}]（必填，须含 JQX）
        use_nature: 使用性质，缺省沿用车主档案
        ncd_years_no_claim: 连续无出险年数，缺省按当前保单 ncd_factor 反推

    Returns:
        报价对象（quote_id/quote_version/line_items/premium_total/valid_until 等）。
        业务校验失败（COVERAGE_DISCONTINUED / JQX_REQUIRED /
        RIDER_PREREQUISITE_MISSING 等）按 MCP 2026-07-28 规范 §Server/Tools
        「Error Handling」以 isError=true 的 Tool Execution Error 返回
        （content 内携带 {"error":{code,message}} JSON），供模型自纠重试。
    """
    result = _query_quote_impl(vin=vin, coverage_selection=coverage_selection,
                               use_nature=use_nature, ncd_years_no_claim=ncd_years_no_claim)
    return _emit(result)

def get_quote(quote_id: str) -> dict[str, Any] | None:
    """供 /confirm（server 侧）查询已存在报价（含内部字段）。"""
    return _QUOTES.get(quote_id)


def quote_is_stale(quote_id: str, quote_version: int, now: datetime | None = None) -> str | None:
    """供 /confirm 校验：返回错误码或 None（通过）。"""
    quote = _QUOTES.get(quote_id)
    if quote is None:
        return "QUOTE_NOT_FOUND"
    now = now or _now()
    if _is_expired(quote, now):
        return "QUOTE_EXPIRED"
    if quote["quote_version"] != quote_version:
        return "QUOTE_VERSION_STALE"
    return None


if __name__ == "__main__":
    mcp.run()  # 默认 stdio 传输（MCP SDK 2.x）
