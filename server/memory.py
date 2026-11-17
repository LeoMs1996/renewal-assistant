"""记忆机制域：跨会话长期记忆存储 + 记忆策略层（memory manager）。

本次检索建立的 2026 基线（检索时间 2026-11-17，基线日 2026-11-13，逐条来源见
reviews/memory.md §3）：
- LangChain《Memory overview》：短期记忆 = thread 作用域（checkpointer 持久化 state）；
  长期记忆 = 跨 thread，按自定义 namespace 存 JSON 文档；语义记忆两形态
  profile（单文档持续更新）/ collection（多文档持续追加）；写入分 hot path / background。
- LangGraph《Stores》：store.put/search(namespace, key, value)，Item 带
  created_at/updated_at，delete 用于遗忘；语义检索需 index.embed（本域未接稠密通道，
  按字段/关键词召回，接口留 query 参数）。
- Oracle《Which Agent Memory Approach Is Best for Long Conversations?》(2026-06-05)：
  分层混合记忆 + memory manager 组 context package；冲突与新鲜度规则——结构化决策
  优于摘要、同权威取新、范围窄者优先、旧/被取代条目降权；每条记忆带
  source/timestamp/scope/type；用 active/superseded/rejected/archived 标记代替早删。
- Hindsight《Agent Memory Consolidation: Keep, Merge, Decay, Evict》(2026-05-20)：
  四个杠杆 重要性/合并/衰减/逐出；「recency-wins + 显式失效」是最稳默认（写新事实、
  把旧的标 invalid 而不是删掉）；GDPR/用户要求删除是硬删；evict last。
- MediaNama《AI Memory Raises New Privacy…》(2026-08-28)：目的限制与数据最小化；
  「删除 ≠ 遗忘」（检索层/向量/日志/派生物都要清）；可携权（portability）。
- OpenAI《Memory and new controls for ChatGPT》：记忆可见/可删/可关；不主动记忆
  敏感信息；告知用户记忆被更新。
- LoCoMo-Plus（ACL 2026）：字符串匹配指标与记忆能力错配，应按「约束一致性」评测。

本模块落成三层，对应上述基线：
1) 存储层 MemoryStore —— 每车主一个 JSON，Item 元数据对齐 LangGraph Store
   （id/namespace/created_at/updated_at），加 status/confidence/source/expires_at；
2) 策略层 —— 写时白名单（只记原子事实，不记对话原文）+ 合并/显式失效 + 读取时衰减
   + TTL 逐出 + 硬删（遗忘权）；
3) memory manager —— build_context_package() 组装「最近轮次（token 预算）+ 滚动摘要
   （确定性压缩）+ 结构化长期记忆」，并返回预算/丢弃/召回明细便于调试与评测。

PII 最小化（硬约束）：只落需求/偏好/保单到期日/最近报价，**不落**姓名、身份证、
手机号、车牌、VIN；用户自愿写入的自由文本在落盘前做脱敏（mask_pii）。
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

from . import config

# needs 增量：与 graph.py 的 needs 同构，成员是**异构**的
# （budget_yuan: int / use_nature_change: str / sum_insured_changes: list[dict] …）。
# 故意用 Any 作为值类型：这是异构映射，不是「list 或 duration」二选一；若让 mypy
# 按首行字面量（None / []）推导，会被误判成 list[Any] | None（t16 类型门禁 14 处
# 报错里有 6 处源于此）。取用时逐字段 isinstance 收窄，不用 cast 掩盖。
NeedsDelta = dict[str, Any]

_MEMORY_LOCK = threading.RLock()
_SCHEMA = 1
_MAX_ITEMS = 200          # 逐出上限（Hindsight「evict last」：只在超量时裁最旧）
_MAX_AUDIT = 500          # 审计行上限（记忆变更账本，便于回溯）

# 记忆种类 → 半衰期（天）。仅用于**召回排序**，不改写已落盘的 confidence
# （避免「读数即写」的隐性副作用）。
KIND_HALF_LIFE_DAYS = {
    "preference": 365.0,   # 稳定偏好：预算、常用保额档、提醒口径
    "constraint": 180.0,   # 会话约束：保额要求、加减险种、用途变更
    "fact": 90.0,          # 保单事实：到期日
    "episodic": 30.0,      # 事件：最近一次报价/确认
}

FIELD_LABELS = {
    "budget_yuan": "预算",
    "use_nature_change": "使用性质",
    "add_coverages": "新增险种",
    "remove_coverages": "去掉险种",
    "user_note": "车主口述偏好",
    "policy_end_date": "保单到期日",
    "last_quote_total": "最近一次报价总保费",
    "last_quote_id": "最近一次报价编号",
    "last_outcome": "最近一次会话结果",
}

_COVERAGE_CN = {
    "JQX": r"交强|强制险",
    "CSX": r"车损",
    "DSX": r"三者|第三者",
    "YWYW": r"医保外|外用药",
    "SJRX": r"司机",
    "CKRX": r"乘客",
    "BLPS": r"划痕",
}
_COVERAGE_NAME = {
    "JQX": "交强险", "CSX": "车损险", "DSX": "三者险", "YWYW": "医保外用药",
    "SJRX": "司机座位", "CKRX": "乘客座位", "BLPS": "划痕险",
}

# ---------------------------------------------------------------- 基础工具


def enabled() -> bool:
    """长期记忆开关（RENEWAL_MEMORY=off 关闭；默认开）。关闭后编排层退回旧截断策略。"""
    return (config.env("RENEWAL_MEMORY", "on") or "on").strip().lower() not in (
        "0", "off", "false", "no")


def _root() -> Path:
    """记忆落盘目录：跟随 config.TRACE_DIR（测试/多实例天然隔离）。"""
    root = Path(config.TRACE_DIR) / "memory"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe(owner_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(owner_id or ""))[:120] or "owner-anon"


def _path(owner_id: str) -> Path:
    return _root() / f"{_safe(owner_id)}.json"


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


def _parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.astimezone()


_ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_PLATE_RE = re.compile(r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼]"
                       r"[A-Z][A-Z0-9]{5,6}")


def mask_pii(text: str) -> str:
    """脱敏：身份证/手机号/车牌。用于任何自由文本落盘前（数据最小化）。"""
    out = _ID_RE.sub("[ID_REDACTED]", str(text or ""))
    out = _PHONE_RE.sub("[PHONE_REDACTED]", out)
    return _PLATE_RE.sub("[PLATE_REDACTED]", out)


def _read(owner_id: str) -> dict:
    path = _path(owner_id)
    empty = {"schema": _SCHEMA, "owner_id": owner_id, "items": [], "audit": []}
    if not path.is_file():
        return empty
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty
    doc.setdefault("items", [])
    doc.setdefault("audit", [])
    return doc


def _write(owner_id: str, doc: dict) -> None:
    doc["schema"] = _SCHEMA
    doc["owner_id"] = owner_id
    doc["updated_at"] = _iso()
    path = _path(owner_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)          # 原子替换：崩溃不留半截记忆文件


def _audit(doc: dict, action: str, field: str, item_id: str, reason: str = "") -> None:
    doc["audit"].append({"ts": _iso(), "action": action, "field": field,
                         "item": item_id, "reason": reason})
    if len(doc["audit"]) > _MAX_AUDIT:
        del doc["audit"][: len(doc["audit"]) - _MAX_AUDIT]


# ---------------------------------------------------------------- 存储层


def _kind_for(field: str) -> str:
    if field.startswith("sum_insured:"):
        return "constraint"
    return {
        "budget_yuan": "preference", "use_nature_change": "preference",
        "add_coverages": "preference", "remove_coverages": "preference",
        "user_note": "preference", "policy_end_date": "fact",
        "last_quote_total": "episodic", "last_quote_id": "episodic",
        "last_outcome": "episodic",
    }.get(field, "fact")


def _new_item(field: str, value, kind: str, source: dict | None,
              confidence: float, ttl_days: float | None, now: datetime) -> dict:
    return {
        "id": f"{kind}:{field}:{now.strftime('%Y%m%d%H%M%S%f')}",
        "namespace": ["owner", _safe(str((source or {}).get("owner_id") or "anon")), kind],
        "field": field,
        "value": value,
        "kind": kind,
        "status": "active",
        "confidence": float(confidence),
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "source": dict(source or {}),
        "expires_at": (_iso(now + timedelta(days=float(ttl_days)))
                       if ttl_days is not None else None),
        "superseded_at": None,
        "superseded_by": None,
        "reason": None,
        "observed_count": 1,
    }


def _expire(doc: dict, now: datetime) -> int:
    n = 0
    for item in doc["items"]:
        if item.get("status") != "active":
            continue
        exp = _parse_iso(item.get("expires_at"))
        if exp and exp <= now:
            item["status"] = "expired"
            item["reason"] = "TTL 到期（事实时效性，逐出但不删除审计）"
            _audit(doc, "expired", item["field"], item["id"], item["reason"])
            n += 1
    return n


def _prune(doc: dict) -> int:
    """逐出：只裁「非 active」的最旧条目，active 永不因容量被删（evict last）。"""
    if len(doc["items"]) <= _MAX_ITEMS:
        return 0
    inactive = [i for i in doc["items"] if i.get("status") != "active"]
    inactive.sort(key=lambda i: i.get("updated_at") or "")
    drop = len(doc["items"]) - _MAX_ITEMS
    drop_ids = {i["id"] for i in inactive[:drop]}
    if not drop_ids:
        return 0
    doc["items"] = [i for i in doc["items"] if i["id"] not in drop_ids]
    _audit(doc, "pruned", "-", ",".join(sorted(drop_ids))[:200],
           "超量逐出（仅非 active 条目）")
    return len(drop_ids)


def _upsert(doc: dict, now: datetime, field: str, value, *, kind: str | None = None,
            source: dict | None = None, confidence: float = 1.0,
            ttl_days: float | None = None, reason: str | None = None) -> str:
    """写入一条记忆，返回 created / superseded / refreshed。"""
    if value in (None, "", [], {}):
        return "skipped"
    kind = kind or _kind_for(field)
    actives = [i for i in doc["items"]
               if i.get("field") == field and i.get("status") == "active"]
    cur = actives[-1] if actives else None
    if cur is not None and cur.get("value") == value:
        cur["updated_at"] = _iso(now)
        cur["observed_count"] = int(cur.get("observed_count") or 1) + 1
        _audit(doc, "refreshed", field, cur["id"], "同事实再次观察，刷新新鲜度")
        return "refreshed"
    new = _new_item(field, value, kind, source, confidence, ttl_days, now)
    action = "created"
    for old in actives:
        old["status"] = "superseded"
        old["superseded_at"] = _iso(now)
        old["superseded_by"] = new["id"]
        old["reason"] = reason or "改口（recency-wins + 显式失效）"
        _audit(doc, "superseded", field, old["id"], old["reason"])
        action = "superseded"
    doc["items"].append(new)
    _audit(doc, "created", field, new["id"], reason or "")
    return action


def put(owner_id: str, field: str, value, *, kind: str | None = None,
        source: dict | None = None, confidence: float = 1.0,
        ttl_days: float | None = None, reason: str | None = None) -> dict:
    """显式写入一条记忆（对外 API，供工具/测试/用户「记住…」使用）。"""
    with _MEMORY_LOCK:
        doc = _read(owner_id)
        now = _now()
        _expire(doc, now)
        src = dict(source or {})
        src.setdefault("owner_id", owner_id)
        action = _upsert(doc, now, field, value, kind=kind, source=src,
                         confidence=confidence, ttl_days=ttl_days, reason=reason)
        _prune(doc)
        _write(owner_id, doc)
        return {"owner_id": owner_id, "field": field, "action": action}


def _score(item: dict, now: datetime) -> float:
    # item 来自 JSON 反序列化（dict[str, Any]），kind 可能是任意值/缺失：
    # 先收敛成 str 再查表，避免「dict[str, float].get(Any | None)」的类型漏洞。
    kind = str(item.get("kind") or "")
    half = KIND_HALF_LIFE_DAYS.get(kind, 90.0)
    updated = _parse_iso(item.get("updated_at")) or now
    age_days = max(0.0, (now - updated).total_seconds() / 86400.0)
    return float(item.get("confidence") or 1.0) * math.pow(0.5, age_days / half)


def active_items(owner_id: str, *, kind: str | None = None,
                 now: datetime | None = None) -> list[dict]:
    """读 active 条目（不含过期/被取代），按「衰减后置信度」降序。"""
    if not owner_id:
        return []
    now = now or _now()
    doc = _read(owner_id)
    out: list[dict] = []
    for item in doc["items"]:
        if item.get("status") != "active":
            continue
        exp = _parse_iso(item.get("expires_at"))
        if exp and exp <= now:
            continue
        if kind and item.get("kind") != kind:
            continue
        out.append(item)
    out.sort(key=lambda i: (-_score(i, now), i.get("updated_at") or ""))
    return out


def get(owner_id: str, field: str):
    for item in active_items(owner_id):
        if item.get("field") == field:
            return item.get("value")
    return None


def superseded_items(owner_id: str, *, limit: int = 5) -> list[dict]:
    doc = _read(owner_id)
    rows = [i for i in doc["items"] if i.get("status") == "superseded"]
    rows.sort(key=lambda i: i.get("superseded_at") or "", reverse=True)
    return rows[:limit]


def search(owner_id: str | None = None, *, field: str | None = None,
           kind: str | None = None, query: str | None = None,
           include_inactive: bool = False, limit: int | None = None) -> list[dict]:
    """检索记忆。owner_id=None 时跨车主扫描（运维/导出用）。

    query 为大小写不敏感的子串匹配（本域未接稠密通道，接口保留 query 位置，
    接 embedding 后替换实现即可 —— LangGraph Stores 同形契约）。
    """
    owners = [owner_id] if owner_id else owners_list()
    rows: list[dict] = []
    for own in owners:
        items = (_read(own)["items"] if include_inactive else active_items(own))
        for item in items:
            if field and item.get("field") != field:
                continue
            if kind and item.get("kind") != kind:
                continue
            if query:
                blob = json.dumps(item.get("value"), ensure_ascii=False) + item.get("field", "")
                if str(query).lower() not in blob.lower():
                    continue
            rows.append(item)
    if limit:
        rows = rows[:limit]
    return rows


def owners_list() -> list[str]:
    out = []
    for path in sorted(_root().glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if doc.get("owner_id"):
            out.append(str(doc["owner_id"]))
    return out


# ---------------------------------------------------------------- 遗忘 / 可携


def forget(owner_id: str, field: str | None = None) -> dict:
    """硬删除（遗忘权）。整车主遗忘时连审计账本一起清，只留时间戳墓碑。

    依据：MediaNama 2026-08-28「删除 ≠ 遗忘」——检索层与派生记录必须一起清；
    Hindsight 2026-05-20「GDPR/用户请求删除属硬删，绕过其它策略」。
    """
    with _MEMORY_LOCK:
        doc = _read(owner_id)
        before = len(doc["items"])
        if field:
            doc["items"] = [i for i in doc["items"] if i.get("field") != field]
            doc["audit"] = [a for a in doc["audit"] if a.get("field") != field]
        else:
            doc["items"] = []
            doc["audit"] = []
        doc["erased_at"] = _iso()
        _write(owner_id, doc)
        return {"owner_id": owner_id, "field": field,
                "removed": before - len(doc["items"])}


def export_owner(owner_id: str) -> dict:
    """可携权（portability）：导出该车主全部记忆（含状态与被取代历史）。"""
    doc = _read(owner_id)
    return {"owner_id": owner_id, "exported_at": _iso(),
            "schema": doc.get("schema", _SCHEMA),
            "items": doc.get("items", []), "audit": doc.get("audit", [])}


def stats(owner_id: str) -> dict:
    doc = _read(owner_id)
    items = doc.get("items", [])
    by_status: dict[str, int] = {}
    for item in items:
        by_status[item.get("status", "?")] = by_status.get(item.get("status", "?"), 0) + 1
    return {"owner_id": owner_id, "total": len(items), "by_status": by_status,
            "active_fields": [i["field"] for i in active_items(owner_id)],
            "audit_lines": len(doc.get("audit", [])),
            "updated_at": doc.get("updated_at")}


# ---------------------------------------------------------------- 写入口（策略层）

_USER_MEMORY_RE = re.compile(
    r"(?:请?记住|记一下|以后(?:都|按|不要|别|用)|今后(?:都|按)|下次(?:都|按))"
    r"[：:，,\s]*(?P<note>[^。；\n]{2,120})")


def facts_from_state(state: dict) -> dict[str, tuple[str, object]]:
    """从一轮最终 State 抽「原子事实」→ {field: (kind, value)}。

    重要性过滤（Hindsight「fact extraction 即重要性过滤器」）：只保留白名单字段，
    对话原文不进长期记忆（LangChain「profile」形态而非整轮文本）。
    """
    facts: dict[str, tuple[str, object]] = {}
    needs = state.get("needs") or {}
    budget = needs.get("budget_yuan")
    if isinstance(budget, (int, float)) and budget > 0:
        facts["budget_yuan"] = ("preference", int(budget))
    use_nature = needs.get("use_nature_change")
    if use_nature:
        facts["use_nature_change"] = ("preference", str(use_nature))
    for key in ("add_coverages", "remove_coverages"):
        vals = [str(c) for c in (needs.get(key) or []) if str(c).strip()]
        if vals:
            facts[key] = ("preference", sorted(set(vals)))
    for change in needs.get("sum_insured_changes") or []:
        code = str(change.get("code") or "").strip()
        amount = change.get("sum_insured")
        if code and isinstance(amount, (int, float)) and amount > 0:
            facts[f"sum_insured:{code}"] = ("constraint", int(amount))
    policy = (state.get("policy") or {}).get("policy") or {}
    if policy.get("end_date"):
        facts["policy_end_date"] = ("fact", str(policy["end_date"]))
    quote = state.get("latest_quote") or {}
    if quote.get("quote_id"):
        facts["last_quote_id"] = ("episodic", str(quote["quote_id"]))
    if isinstance(quote.get("total_premium"), (int, float)):
        facts["last_quote_total"] = ("episodic", round(float(quote["total_premium"]), 2))
    if state.get("status") in ("awaiting_confirm", "confirmed"):
        facts["last_outcome"] = ("episodic", str(state["status"]))
    note = _USER_MEMORY_RE.search(str(state.get("message") or ""))
    if note:
        text = mask_pii(note.group("note").strip())[:120]
        if len(text) >= 2:
            facts["user_note"] = ("preference", text)
    return facts


_TTL_DAYS = {"last_quote_id": 1, "last_quote_total": 1, "last_outcome": 30}


def record_turn(state: dict) -> dict:
    """每轮结束写长期记忆（由 sessions.save 调用，hot path 写入）。

    依据 LangChain「in the hot path」：新记忆立即可用于后续会话；贵在确定性——
    只写白名单事实，不做 LLM 抽取（无凭证也可运行）。
    """
    if not enabled():
        return {"enabled": False, "written": [], "superseded": [], "refreshed": []}
    owner = (state or {}).get("owner_id")
    if not owner:
        return {"enabled": True, "used": False, "written": [],
                "superseded": [], "refreshed": []}
    src = {"owner_id": owner, "session_id": state.get("session_id"),
           "trace_id": state.get("trace_id")}
    result = {"enabled": True, "used": True, "owner_id": owner,
              "written": [], "superseded": [], "refreshed": [], "invalidated": []}
    facts = facts_from_state(state)
    with _MEMORY_LOCK:
        doc = _read(owner)
        now = _now()
        _expire(doc, now)
        for field, (kind, value) in facts.items():
            action = _upsert(doc, now, field, value, kind=kind, source=src,
                             ttl_days=_TTL_DAYS.get(field))
            if action == "created":
                result["written"].append(field)
            elif action == "superseded":
                result["superseded"].append(field)
            elif action == "refreshed":
                result["refreshed"].append(field)
        result["invalidated"] = _mirror_invalidations(doc, state, src, now)
        _prune(doc)
        _write(owner, doc)
    return result


def _mirror_invalidations(doc: dict, state: dict, src: dict, now: datetime) -> list[str]:
    """把编排层「记忆撤回」事件（state.invalidated）落到长期记忆，并附审计理由。"""
    out: list[str] = []
    for entry in state.get("invalidated") or []:
        field = str(entry.get("field") or "")
        reason = str(entry.get("reason") or "车主改口，旧偏好失效")
        new = entry.get("new")
        if field == "budget_yuan" and isinstance(new, (int, float)) and new > 0:
            _upsert(doc, now, field, int(new), kind="preference", source=src, reason=reason)
            out.append(field)
        elif field == "sum_insured_changes":
            delta = new if isinstance(new, list) else []
            for change in delta:
                code = str(change.get("code") or "")
                amount = change.get("sum_insured")
                if code and isinstance(amount, (int, float)) and amount > 0:
                    _upsert(doc, now, f"sum_insured:{code}", int(amount),
                            kind="constraint", source=src, reason=reason)
                    out.append(f"sum_insured:{code}")
        elif field == "use_nature_change" and new:
            _upsert(doc, now, field, str(new), kind="preference", source=src,
                    reason=reason)
            out.append(field)
    return out


# ---------------------------------------------------------------- 读入口（策略层）

_REFERENCE_RE = re.compile(
    r"上次|上回|上一轮|之前(?:的)?(?:方案|说|提|讲|要求|设定|报|选)|"
    r"还是(?:按|用|照)|老方案|老样子|照旧|按原方案|跟之前一样")
_NEG_BUDGET_RE = re.compile(r"(?:不看|不考虑|无所谓|不限)[^。]{0,4}预算|"
                            r"预算[^。]{0,6}(?:无所谓|不限|不用考虑)")
_NEG_PREFIX = r"(?:去掉|不要|删掉|取消|不投|不加|不买|退掉)[^。]{0,8}(?:"
_IDEMPOTENT_USE_RE = re.compile(r"非营运|家庭自用")


def has_reference_signal(message: str) -> bool:
    """是否显式指代既往会话（「上次」「还是按老方案」）。

    安全闸门：跨会话记忆只在车主显式指代时才影响**询价参数**。理由——记忆是证据
    不是事实（Oracle 2026-06-05 优先级：当前消息 > 结构化记忆），错用记忆改会改保费，
    属财务风险；也保证幂等/回归稳定（AC-05/06 手算保费不受历史会话污染）。
    """
    return bool(_REFERENCE_RE.search(str(message or "")))


def _negated(msg: str, code: str) -> bool:
    pattern = _COVERAGE_CN.get(code)
    if not pattern:
        return False
    return bool(re.search(_NEG_PREFIX + pattern + r")", msg))


def _as_int(value: object) -> int | None:
    """把落盘值收敛为正整数（int/float/纯数字字符串），不可用返回 None。

    与原实现 `int(value)` 的接受范围一致（int/float/"6000" 都行），差别只在于
    脏数据（None/非数字串）从「抛 TypeError 中断召回」改为「跳过该条」——
    记忆是增强能力，读到坏数据不应让整轮召回失败。t16 类型门禁整改点之一。
    """
    if isinstance(value, bool):        # bool 是 int 子类，但语义上不该当保额/预算
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        return int(text) if text.isdigit() and int(text) > 0 else None
    return None


def recall_needs(state: dict) -> tuple[NeedsDelta, list[str]]:
    """跨会话召回 → 需要增量（needs delta 形态）。返回 (delta, seeded_fields)。

    只召回「预算 / 保额档 / 使用性质」三类可复核字段；加减险种不自动套用
    （语义歧义大，错用会改变保障范围）。
    """
    if not enabled():
        return {}, []
    owner = state.get("owner_id")
    msg = str(state.get("message") or "")
    if not owner or not has_reference_signal(msg):
        return {}, []
    generic = bool(re.search(r"按上次|按原方案|老方案|老样子|照旧|跟之前一样|还是按", msg))
    delta: NeedsDelta = {"budget_yuan": None, "sum_insured_changes": [],
                         "add_coverages": [], "remove_coverages": [],
                         "use_nature_change": None}
    changes: list[dict[str, int | str]] = delta["sum_insured_changes"]
    seeded: list[str] = []
    for item in active_items(owner):
        field = str(item.get("field") or "")
        value = item.get("value")
        if field == "budget_yuan" and not _NEG_BUDGET_RE.search(msg):
            budget = _as_int(value)          # 落盘脏数据 → 跳过该条，不中断召回
            if budget is None:
                continue
            delta["budget_yuan"] = budget
            seeded.append(field)
        elif field.startswith("sum_insured:"):
            code = field.split(":", 1)[1]
            amount = _as_int(value)
            if amount is None:
                continue
            pattern = _COVERAGE_CN.get(code)
            mentioned = bool(pattern and re.search(pattern, msg))
            if (mentioned or generic) and not _negated(msg, code):
                changes.append({"code": code, "sum_insured": amount})
                seeded.append(field)
        elif field == "use_nature_change" and not _IDEMPOTENT_USE_RE.search(msg):
            use_nature = str(value or "").strip()   # 与原 str(value) 一致，仅多挡 None/""
            if not use_nature:
                continue
            delta["use_nature_change"] = use_nature
            seeded.append(field)
    return delta, seeded


def _label(field: str) -> str:
    if field.startswith("sum_insured:"):
        code = field.split(":", 1)[1]
        return f"{_COVERAGE_NAME.get(code, code)}保额"
    return FIELD_LABELS.get(field, field)


def _fmt_value(field: str, value) -> str:
    if field == "budget_yuan" and isinstance(value, (int, float)):
        return f"{int(value)} 元"
    if field.startswith("sum_insured:") and isinstance(value, (int, float)):
        wan = float(value) / 10000.0
        return f"{wan:g} 万"
    if field in ("add_coverages", "remove_coverages") and isinstance(value, list):
        return "、".join(_COVERAGE_NAME.get(str(c), str(c)) for c in value)
    if field in ("last_quote_total",) and isinstance(value, (int, float)):
        return f"{float(value):.2f} 元"
    return str(value)


def _age_human(item: dict, now: datetime | None = None) -> str:
    now = now or _now()
    updated = _parse_iso(item.get("updated_at"))
    if not updated:
        return "时间未知"
    days = (now - updated).total_seconds() / 86400.0
    if days < 1:
        return "今日"
    if days < 30:
        return f"{int(days)} 天前"
    if days < 365:
        return f"{int(days / 30)} 个月前"
    return f"{days / 365:.1f} 年前"


def render_brief(owner_id: str, *, limit: int = 8,
                 include_superseded: bool = True) -> str:
    """渲染给模型看的记忆简报（带来源与新鲜度，可审计）。空则返回 ""。"""
    items = active_items(owner_id)[:limit]
    if not items:
        return ""
    lines = ["[跨会话长期记忆]（来自以往会话；与当前消息冲突时一律以当前消息为准）"]
    for item in items:
        src = (item.get("source") or {}).get("session_id") or "未知会话"
        lines.append(f"- {_label(item.get('field', ''))}："
                     f"{_fmt_value(item.get('field', ''), item.get('value'))}"
                     f"（{_age_human(item)}记录，来源会话 {src}）")
    if include_superseded:
        for item in superseded_items(owner_id, limit=2):
            stamp = str(item.get("superseded_at") or "")[:10]
            lines.append(f"- 已失效（勿引用）：{_label(item.get('field', ''))}="
                         f"{_fmt_value(item.get('field', ''), item.get('value'))}"
                         f"，{stamp} 被更新说法取代")
    return "\n".join(lines)


# ---------------------------------------------------------------- 上下文预算


def estimate_tokens(text: str) -> int:
    """保守 token 估算：CJK 字符按 1 token/字，其余按 1 token/4 字符。

    不使用真实分词器（无凭证/离线可用、跨模型稳定）；偏保守，用于预算裁剪而非计费。
    """
    if not text:
        return 0
    cjk = len(re.findall(r"[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]", text))
    other = len(text) - cjk
    return cjk + (other + 3) // 4


def trim_turns(turns: list[dict], budget_tokens: int) -> tuple[list[dict], list[dict], int]:
    """按 token 预算从新到旧保留消息；返回 (保留, 被裁, 保留tokens)。

    旧实现按固定条数裁剪（history[-20:]/[-8:]/[-6:] 三处不一致），既不看长度
    （长回复瞬间吃满预算）也没有压缩（丢掉就没了）——LangChain 短期记忆文档把
    「trim / delete / summarize」列为三种手段，只做 trim 会丢信息。
    """
    kept: list[dict] = []
    used = 0
    for turn in reversed(list(turns or [])):
        cost = estimate_tokens(str(turn.get("content") or "")) + 4
        if kept and used + cost > budget_tokens:
            break
        kept.append(turn)
        used += cost
    kept.reverse()
    total = len(turns or [])
    dropped = list(turns or [])[: max(0, total - len(kept))]
    return kept, dropped, used


_SUMMARY_KEY_RE = re.compile(
    r"预算|元|万|三者|车损|交强|医保外|划痕|司机|乘客|续保|比价|确认|投保|"
    r"报价|到期|脱保|网约|营运|保额|方案")

# 摘要里「最不能丢」的句子特征（金额/约束/增删动作）
_SUMMARY_CONSTRAINT_RE = re.compile(
    r"预算|保额|不超过|以内|元|万|去掉|不要|加|减|升到|降到|调")


def summarize_turns(dropped: list[dict], *, max_points: int = 3,
                    max_chars: int = 56) -> str:
    """确定性滚动摘要：从被裁轮次里抽「带业务信息量」的句子。

    2026 基线的 SummarizationMiddleware 用 LLM 生成摘要；本项目需离线/可复现，
    故用确定性抽取（含数字/险种/预算关键词的句子优先），并显式标注「已压缩」。
    有凭证时可在 memory_eval 里替换为 LLM 摘要（接口保留 summarizer 参数位）。
    """
    if not dropped:
        return ""
    points: list[str] = []
    for turn in dropped:
        role = "车主" if turn.get("role") == "user" else "助手"
        for sent in re.split(r"[。；\n]", str(turn.get("content") or "")):
            s = sent.strip()
            if len(s) < 6 or not _SUMMARY_KEY_RE.search(s):
                continue
            points.append(f"{role}：{s[:max_chars]}")
    seen: set[str] = set()
    uniq: list[str] = []
    for point in points:                 # 去重保序（首次出现优先）
        if point in seen:
            continue
        seen.add(point)
        uniq.append(point)
    # 重要性优先于纯粹的新旧：含「预算/保额/金额/增删险种」的句子权重更高
    # （Hindsight 2026-05-20 的 importance 杠杆；保险域里带数字的约束最不能丢）。
    scored = [(2 if _SUMMARY_CONSTRAINT_RE.search(p) else 1, idx, p)
              for idx, p in enumerate(uniq)]
    scored.sort(key=lambda t: (-t[0], -t[1]))
    keep = sorted(scored[:max_points], key=lambda t: t[1])   # 选定后按时间顺序排列
    head = [p for _, _, p in keep]
    lines = [f"（早前 {len(dropped)} 轮对话已按上下文预算压缩，以下为要点）"]
    lines += [f"- {p}" for p in head]
    if len(dropped) > len(head):
        lines.append(f"…其余 {len(dropped) - len(head)} 轮省略")
    return "\n".join(lines)


def build_context_package(state: dict, *, budget_tokens: int | None = None) -> dict:
    """memory manager：为当前轮组装 context package（可调试、可评测）。

    形状对齐 Oracle 2026-06-05 的 context_package（recent / summary / structured /
    retrieved），并额外返回预算明细，回答错时可直接看「是摘要过期、还是记忆串味」。
    """
    turns = list(state.get("history") or [])
    budget = int(budget_tokens if budget_tokens is not None
                 else config.memory_prompt_budget())
    kept, dropped, recent_tokens = trim_turns(turns, budget)
    summary = summarize_turns(dropped)
    owner = state.get("owner_id") or ""
    long_term = active_items(owner) if owner else []
    brief = render_brief(owner) if owner else ""
    return {
        "recent": kept,
        "dropped_turns": len(dropped),
        "summary": summary,
        "long_term": long_term,
        "brief": brief,
        "budget_tokens": budget,
        "tokens": {
            "recent": recent_tokens,
            "summary": estimate_tokens(summary),
            "brief": estimate_tokens(brief),
            "total": recent_tokens + estimate_tokens(summary) + estimate_tokens(brief),
        },
    }


def prompt_context(state: dict, *, budget_tokens: int | None = None,
                   legacy_tail: int = 8) -> tuple[str, list[dict]]:
    """编排层唯一入口：返回 (附加 system 文本, 历史消息)。

    关闭记忆时退回旧行为（固定尾部 N 条），保证 RENEWAL_MEMORY=off 可控回滚。
    """
    if not enabled():
        return "", list((state.get("history") or [])[-legacy_tail:])
    pkg = build_context_package(state, budget_tokens=budget_tokens)
    parts = [p for p in (pkg["brief"], pkg["summary"]) if p]
    system_extra = ("\n\n" + "\n\n".join(parts)) if parts else ""
    return system_extra, list(pkg["recent"])


def context_report(state: dict, *, budget_tokens: int | None = None) -> dict:
    """给节点可观测性用的轻量摘要（写进 node_end.output，不新增轨迹 record_type）。"""
    pkg = build_context_package(state, budget_tokens=budget_tokens)
    return {"recent_turns": len(pkg["recent"]), "dropped_turns": pkg["dropped_turns"],
            "tokens": pkg["tokens"], "long_term_fields": [i["field"] for i in pkg["long_term"]]}


# ---------------------------------------------------------------- 运维诊断


class DoctorReport(TypedDict):
    """记忆体检结果（doctor() 返回）：计数字段为 int，明细字段为 list[str]。

    t16 类型门禁整改：原先用无标注 dict 字面量，mypy 把值类型并成
    `int | list[Any]`，于是 `report["owners"] += 1` 报「object + int」。
    """

    owners: int
    items: int
    expired: int
    superseded: int
    no_source: int
    pii_leaks: list[str]
    stale_active: list[str]


def doctor() -> DoctorReport:
    """记忆健康状况：过期/超量/无来源/被取代堆积 + PII 泄漏扫描。"""
    pii_leaks: list[str] = []
    stale_active: list[str] = []
    report: DoctorReport = {"owners": 0, "items": 0, "expired": 0, "superseded": 0,
                            "no_source": 0, "pii_leaks": pii_leaks,
                            "stale_active": stale_active}
    for path in sorted(_root().glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        report["owners"] += 1
        for item in doc.get("items") or []:
            report["items"] += 1
            status = item.get("status")
            if status == "expired":
                report["expired"] += 1
            elif status == "superseded":
                report["superseded"] += 1
            if status == "active" and not (item.get("source") or {}).get("session_id"):
                report["no_source"] += 1
        blob = path.read_text(encoding="utf-8")
        if _ID_RE.search(blob) or _PHONE_RE.search(blob) or _PLATE_RE.search(blob):
            report["pii_leaks"].append(path.name)
    return report
