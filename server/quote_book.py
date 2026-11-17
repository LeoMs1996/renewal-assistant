"""报价登记簿：服务侧已见报价 + 订单（POST /confirm 校验依据）。

- 报价来源：mcp_bridge.query_quote 的成功结果（每次成功询价自动 register）。
- 持久化 traces/quotes.json（已加入 .gitignore），重启不丢。
- 订单幂等：同一 quote_id 重复确认返回同一 order_id（SPEC：重复确认只存一份）。
"""
from __future__ import annotations

import json
import random
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config

_LOCK = threading.Lock()


def _path() -> Path:
    return config.TRACE_DIR / "quotes.json"


def _load() -> dict:
    p = _path()
    if not p.is_file():
        return {"quotes": {}, "orders": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register(quote: dict) -> None:
    """记录一次成功报价（quote_id / quote_version / valid_until / vin 等）。

    SPEC v1.0.3 §3.2 规则3 同步：quote_server 对同 quote_id 重算后 quote_version +1，
    登记簿以覆盖方式接收新版本；防御性保留已登记的最大版本，防止旧版本回写覆盖。
    """
    with _LOCK:
        data = _load()
        qid = quote["quote_id"]
        old = data["quotes"].get(qid)
        if old is not None and int(old.get("quote_version", 0)) > int(quote.get("quote_version", 1)):
            return  # 旧版本报价不回写（规则3：旧版本立即失效）
        data["quotes"][qid] = quote
        _save(data)


def get_quote(quote_id: str) -> dict | None:
    return _load()["quotes"].get(quote_id)


def is_expired(quote: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now().astimezone()
    valid_until = datetime.fromisoformat(quote["valid_until"])
    return now > valid_until


def create_order(quote: dict) -> dict:
    """生成订单（幂等）。effective_date=当天，end_date=生效日+1年-1天。"""
    with _LOCK:
        data = _load()
        for order in data["orders"].values():
            if order["quote_id"] == quote["quote_id"]:
                return order  # 幂等：重复确认只存一份
        today = date.today()
        end = today.replace(year=today.year + 1) - timedelta(days=1)
        order = {
            "order_id": f"ORD-{today.strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            "quote_id": quote["quote_id"],
            "premium_total": quote["premium_total"],
            "effective_date": today.isoformat(),
            "end_date": end.isoformat(),
        }
        data["orders"][order["order_id"]] = order
        _save(data)
        return order
