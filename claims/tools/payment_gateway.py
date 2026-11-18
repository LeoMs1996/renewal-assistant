"""模拟支付网关（F2）。

语义按契约 §3.4：
- `charge(payment_key, ...)` **以 payment_key 为幂等键**：同键重复请求返回首次结果，
  不产生第二笔；`attempts` 记录每次调用（用于断言"支付不重发"）。
- 可注入失败：`timeout_once=True` 时首次 charge 抛 `TimeoutError`（模拟丢 ACK），
  之后 `query()` 返回真实状态。
- 全部为**合成/模拟**数据，不接任何真实支付系统。
"""

from __future__ import annotations

import uuid
from typing import Any


class PaymentError(Exception):
    code = "PAYMENT_FAILED"


class PaymentRejected(PaymentError):
    code = "PAYMENT_REJECTED"


class MockPaymentGateway:
    """进程内幂等网关。多进程场景下真实网关需自行持久化，本模拟仅用于验收。"""

    def __init__(self, *, timeout_once: bool = False, reject: bool = False) -> None:
        self._charges: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self.attempts: list[dict[str, Any]] = []
        self.timeout_once = timeout_once
        self.reject = reject
        self._timed_out = False

    # -- 写：扣款 ---------------------------------------------------------
    def charge(self, *, payment_key: str, amount: float, payee: str) -> dict[str, Any]:
        self.attempts.append({"op": "charge", "payment_key": payment_key, "amount": amount})

        # 幂等：同键已有成功/待定记录 → 返回首次结果，不再产生新交易
        if payment_key in self._charges:
            existing = dict(self._charges[payment_key])
            existing["deduplicated"] = True
            return existing

        if self.reject:
            raise PaymentRejected("网关拒绝（模拟）")

        if self.timeout_once and not self._timed_out:
            self._timed_out = True
            # 记录为"已提交、结果未知"：真实网关此时可能已扣款成功
            self._pending[payment_key] = {
                "payment_id": f"PAY-{uuid.uuid4().hex[:10]}",
                "payment_key": payment_key,
                "amount": amount,
                "payee": payee,
                "status": "success",
            }
            raise TimeoutError("网关响应超时（模拟丢 ACK）")

        record = {
            "payment_id": f"PAY-{uuid.uuid4().hex[:10]}",
            "payment_key": payment_key,
            "amount": amount,
            "payee": payee,
            "status": "success",
        }
        self._charges[payment_key] = record
        return dict(record)

    # -- 查：对账 ---------------------------------------------------------
    def query(self, payment_key: str) -> dict[str, Any]:
        self.attempts.append({"op": "query", "payment_key": payment_key})
        if payment_key in self._charges:
            out = dict(self._charges[payment_key])
            out["status"] = "success"
            return out
        if payment_key in self._pending:
            out = dict(self._pending.pop(payment_key))
            self._charges[payment_key] = out  # 查单确认后落账
            return out
        return {"payment_key": payment_key, "status": "unknown"}

    # -- 观测 -------------------------------------------------------------
    @property
    def charge_count(self) -> int:
        """真正提交过的扣款次数（不含幂等去重与查单）。"""
        return sum(1 for a in self.attempts if a["op"] == "charge")

    def reset(self) -> None:
        self._charges.clear()
        self._pending.clear()
        self.attempts.clear()
        self._timed_out = False
