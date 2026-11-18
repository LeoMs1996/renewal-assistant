"""理赔域状态与错误码（契约见 `claims/SPEC-claims.md` §2/§4/§5）。

本文件只定义**类型与常量**，不含业务逻辑。
"""

from __future__ import annotations

from typing import Any, TypedDict


class Status:
    INTAKE = "intake"
    VERIFYING = "verifying"
    NEED_INFO = "need_info"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    PAYING = "paying"
    PAYMENT_UNKNOWN = "payment_unknown"
    PAID = "paid"
    REJECTED = "rejected"
    PAYMENT_FAILED = "payment_failed"
    CLOSED_ABANDONED = "closed_abandoned"

    TERMINAL = frozenset({PAID, REJECTED, PAYMENT_FAILED, CLOSED_ABANDONED})


class ErrorCode:
    CLAIM_FIELD_INVALID = "CLAIM_FIELD_INVALID"
    CLAIM_DUPLICATE = "CLAIM_DUPLICATE"
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    CLAIM_STATE_INVALID = "CLAIM_STATE_INVALID"
    MATERIAL_MISSING = "MATERIAL_MISSING"
    ANALYSIS_SCHEMA_INVALID = "ANALYSIS_SCHEMA_INVALID"
    ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"
    REVIEW_DECISION_INVALID = "REVIEW_DECISION_INVALID"
    AMOUNT_EXCEED_LIMIT = "AMOUNT_EXCEED_LIMIT"
    PAYMENT_KEY_MISSING = "PAYMENT_KEY_MISSING"
    PAYMENT_REJECTED = "PAYMENT_REJECTED"
    PAYMENT_UNKNOWN = "PAYMENT_UNKNOWN"
    PAYMENT_AMOUNT_MISMATCH = "PAYMENT_AMOUNT_MISMATCH"
    TOOL_FORBIDDEN = "TOOL_FORBIDDEN"


#: 契约里出现的 14 个错误码（测试用：禁止实现里出现表外错误码）
ALL_ERROR_CODES = frozenset(
    value for name, value in vars(ErrorCode).items() if name.isupper()
)


class Event:
    """轨迹 `event` 字段的 `claims.*` 命名空间（契约 §6，前缀防止与续保语义混淆）。"""

    INTAKE_ACCEPTED = "claims.intake_accepted"
    INTAKE_DUPLICATE = "claims.intake_duplicate"
    INTAKE_INVALID = "claims.intake_invalid"
    POLICY_REJECTED = "claims.policy_rejected"
    MATERIALS_ANALYZED = "claims.materials_analyzed"
    MATERIALS_MISSING = "claims.materials_missing"
    ASSESSED = "claims.assessed"
    REVIEW_REQUESTED = "claims.review_requested"
    REVIEW_APPROVED = "claims.review_approved"
    REVIEW_REJECTED = "claims.review_rejected"
    AUTO_APPROVED = "claims.auto_approved"
    PAYMENT_KEY_RESERVED = "claims.payment_key_reserved"
    PAYMENT_CHARGE = "claims.payment_charge"
    PAYMENT_CHARGED = "claims.payment_charged"
    PAYMENT_UNKNOWN = "claims.payment_unknown"
    PAYMENT_RECONCILED = "claims.payment_reconciled"
    PAYMENT_FAILED = "claims.payment_failed"
    CLOSED = "claims.closed"
    LLM_DEGRADED = "claims.llm_degraded"
    STATE_INVALID = "claims.state_invalid"


#: 契约 §6 登记的完整 event 清单（测试断言：实现只用这里面的值）
ALL_EVENTS = frozenset(
    value for name, value in vars(Event).items() if name.isupper()
)


class ClaimState(TypedDict, total=False):
    """理赔单状态（字段与契约 §4.1 一一对应）。"""

    claim_id: str
    session_id: str
    owner_id: str
    policy_no: str
    report: dict[str, Any]
    documents: list[dict[str, Any]]
    status: str
    doc_ids: list[str]
    materials_analysis: dict[str, Any] | None
    analysis_degraded: bool
    analysis_cached: bool
    analysis_key: str
    missing_docs: list[str]
    flags: list[str]
    assessment: dict[str, Any]
    approval_version: int
    approval_mode: str
    review_decision: str | None
    review_comment: str
    reviewer_id: str
    reviewed_at: str
    payment_key: str | None
    payment_id: str | None
    paid_at: str | None
    payment_receipt: dict[str, Any]
    synthetic: bool
    errors: list[dict[str, Any]]
