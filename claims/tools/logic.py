"""理赔业务纯函数（F2）。

**全部无副作用、不依赖 LangGraph / 网络 / LLM**，因此可以被单测直接调用，
也让「金额由服务端算」这条不变量（契约 I1 / CLM-06）变成可断言的事实。

分层：
- `claims/graph.py`：LangGraph 节点（编排、interrupt、checkpointer、轨迹）
- 本文件：业务判定（校验 / 幂等键 / 金额 / 状态迁移）
"""

from __future__ import annotations

import hashlib
from typing import Any

from claims.state import ErrorCode, Status
from claims.tools import synthetic
from claims.tools.verify_quote import is_verbatim


class ClaimError(Exception):
    """业务断言失败（code 直接进 API/轨迹错误码）。"""

    def __init__(self, code: str, message: str, *, node: str = "") -> None:
        self.code = code
        self.message = message
        self.node = node
        super().__init__(f"{code}: {message}")


REQUIRED_REPORT_FIELDS = ("occurred_at", "location", "description", "has_injury")
REQUIRED_DOC_KINDS = ("police_report", "repair_quote")

#: F3 产出的 **分析过程信号**（anomalies）。它们**不进 flags**（SPEC §4.6 裁决）：
#: flags 是业务信号（影响路由），anomalies 只进轨迹供排查。
ANALYSIS_ANOMALY_CODES = frozenset(
    {"skipped_by_model", "quote_not_verbatim", "kind_mismatch", "unknown_doc_id_dropped"}
)


def _anomaly_code(raw: object) -> str:
    """`kind_mismatch:a!=b` → `kind_mismatch`（码可能带参）。"""
    return str(raw).split(":", 1)[0]

#: 允许的状态迁移（契约 §2.2）
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    Status.INTAKE: frozenset({Status.VERIFYING}),
    Status.VERIFYING: frozenset({Status.NEED_INFO, Status.REVIEW_PENDING, Status.REJECTED}),
    Status.NEED_INFO: frozenset({Status.VERIFYING, Status.CLOSED_ABANDONED}),
    Status.REVIEW_PENDING: frozenset({Status.APPROVED, Status.REJECTED}),
    Status.APPROVED: frozenset({Status.PAYING}),
    Status.PAYING: frozenset({Status.PAID, Status.PAYMENT_UNKNOWN}),
    Status.PAYMENT_UNKNOWN: frozenset({Status.PAID, Status.PAYING, Status.PAYMENT_FAILED}),
}


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def idempotency_key(owner_id: str, policy_no: str, report: dict[str, Any]) -> str:
    """报案幂等键：可由请求体稳定复现（契约 §3.1）。"""
    raw = "|".join(
        [
            str(owner_id),
            str(policy_no),
            str(report.get("occurred_at", "")),
            str(report.get("location", "")),
        ]
    )
    return sha256_hex(raw)


def claim_id_for(key: str, *, occurred_at: str) -> str:
    day = "".join(ch for ch in occurred_at[:10] if ch.isdigit()) or "00000000"
    return f"CLM-{day}-{key[:8]}"


def validate_report(report: dict[str, Any]) -> list[str]:
    """返回缺失/非法的字段名列表（空列表 = 通过）。"""
    problems: list[str] = []
    for field in REQUIRED_REPORT_FIELDS:
        if field not in report or report[field] in (None, ""):
            problems.append(field)
    if "has_injury" in report and not isinstance(report["has_injury"], bool):
        problems.append("has_injury:type")
    occurred = str(report.get("occurred_at", ""))
    if occurred and len(occurred) < 10:
        problems.append("occurred_at:format")
    return problems


def get_policy(policy_no: str, owner_id: str) -> dict[str, Any]:
    """取保单并做归属断言（最小权限，对齐 `server.security.authorize_tool_args` 口径）。"""
    policy = synthetic.POLICIES.get(policy_no)
    if not policy:
        raise ClaimError(
            ErrorCode.POLICY_NOT_FOUND,
            f"保单不存在：{policy_no}",
        )
    if policy["owner_id"] != owner_id:
        # 不泄露真实归属；续保域同样只报"无权访问"
        raise ClaimError(
            ErrorCode.TOOL_FORBIDDEN,
            f"保单 {policy_no} 与报案人不匹配（最小权限）",
        )
    if not policy.get("active", False):
        raise ClaimError(
            ErrorCode.POLICY_NOT_FOUND,
            f"保单 {policy_no} 已失效（不在保险期间）",
        )
    return policy


def missing_doc_kinds(documents: list[dict[str, Any]]) -> list[str]:
    kinds = {d.get("kind") for d in documents}
    return [k for k in REQUIRED_DOC_KINDS if k not in kinds]


def doc_sources(documents: list[dict[str, Any]]) -> dict[str, str]:
    return {str(d.get("doc_id")): str(d.get("text", "")) for d in documents}


def flags_for(
    analysis: dict[str, Any],
    documents: list[dict[str, Any]],
    dropped_facts: list[str],
) -> list[str]:
    """可疑项代码（枚举，见契约 §4.5）——由**规则**产生，模型无权自定义。"""
    flags: list[str] = []
    text = "\n".join(str(d.get("text", "")) for d in documents)
    if "人伤" in text or any(
        fact.get("key") == "injury_flag"
        for doc in analysis.get("documents", [])
        for fact in doc.get("facts", [])
    ):
        flags.append("PERSONAL_INJURY")
    if dropped_facts:
        flags.append("LOW_CONFIDENCE")
    if "忽略" in text and "指令" in text:
        flags.append("QUOTE_OUTLIER")

    # 显式忽略 anomalies（SPEC §4.6）：**不要**依赖"没匹配到就自然忽略"。
    # 若将来有人把 anomaly 码写进上面的 flags 规则，这里也会把它剔除，
    # 避免 route_risk 把"模型跳过了某文档"当成"客户有欺诈风险"。
    anomalies = [
        _anomaly_code(a)
        for doc in (analysis or {}).get("documents", [])
        for a in (doc.get("anomalies") or [])
    ]
    ignored = set(anomalies) & ANALYSIS_ANOMALY_CODES
    return [f for f in flags if f not in ignored]


def line_items_from(analysis: dict[str, Any] | None) -> list[dict[str, Any]]:
    """从材料事实里抽 `repair_item:*`，只作为**金额链路的输入项**，不是结论。"""
    items: list[dict[str, Any]] = []
    for doc in (analysis or {}).get("documents", []):
        for fact in doc.get("facts", []):
            key = str(fact.get("key", ""))
            if not key.startswith("repair_item:"):
                continue
            try:
                amount = float(fact.get("value"))
            except (TypeError, ValueError):
                continue
            items.append(
                {
                    "name": key.split(":", 1)[1],
                    "amount": round(amount, 2),
                    "evidence": fact.get("evidence", {}),
                }
            )
    return items


def assess_amount(
    analysis: dict[str, Any] | None,
    *,
    deductible: float,
    max_payable: float,
) -> dict[str, Any]:
    """金额计算（纯函数）。**模型输出里任何 amount 字段都不参与计算。**

    契约 I1 / CLM-06：即使 `analysis` 里被塞入 `payable_amount`，本函数也只按
    `repair_item:*` 事实重算。
    """
    items = line_items_from(analysis)
    raw_total = round(sum(item["amount"] for item in items), 2)
    after_deductible = round(raw_total - max(deductible, 0.0), 2)
    payable = max(after_deductible, 0.0)
    capped = payable > max_payable
    if capped:
        payable = round(max_payable, 2)
    return {
        "line_items": items,
        "raw_total": raw_total,
        "deductible": round(max(deductible, 0.0), 2),
        "payable_amount": round(payable, 2),
        "capped": capped,
        "currency": "CNY",
    }


def needs_manual_review(assessment: dict[str, Any], flags: list[str], *, threshold: float) -> bool:
    """条件边判定（契约 §2.2 / CLM-07）。"""
    if float(assessment.get("payable_amount", 0.0)) > threshold:
        return True
    blocking = {"PERSONAL_INJURY", "PHOTO_MISMATCH", "QUOTE_OUTLIER", "DUPLICATE_PATTERN"}
    return bool(blocking & set(flags))


def payment_key_for(
    claim_id: str,
    policy_no: str,
    payable_amount: float,
    approval_version: int,
) -> str:
    """支付幂等键（契约 §3.4）：只由**已持久化**的四元组派生，重试/恢复必然同键。"""
    raw = f"{claim_id}|{policy_no}|{payable_amount:.2f}|{approval_version}"
    return f"pay-{sha256_hex(raw)[:32]}"


def guard_transition(current: str, target: str) -> None:
    """状态迁移守卫：非法迁移必须显式失败（CLM-14），不许静默忽略。"""
    if current == target:
        return
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ClaimError(
            ErrorCode.CLAIM_STATE_INVALID,
            f"非法状态迁移：{current} → {target}",
        )


def quote_ok(fact: dict[str, Any], source: str) -> bool:
    evidence = fact.get("evidence") or {}
    return is_verbatim(str(evidence.get("quote", "")), source)
