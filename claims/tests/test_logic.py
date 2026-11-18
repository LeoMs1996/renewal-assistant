"""纯函数层测试（不依赖 LangGraph / LLM / 网络）。

覆盖契约：CLM-01（字段校验）、CLM-02（幂等键）、CLM-03（保单归属）、
CLM-05（逐字引用）、CLM-06（金额只从服务端算）、CLM-07（路由条件）、
CLM-13（幂等键稳定）、CLM-14（非法迁移）。
"""

from __future__ import annotations

import pytest

from claims.state import ALL_ERROR_CODES, ErrorCode, Status
from claims.tools import logic, rules_analyzer, synthetic
from claims.tools.verify_quote import filter_facts, is_verbatim


# --------------------------------------------------------------- CLM-01
def test_validate_report_requires_all_fields():
    ok = {"occurred_at": "2026-11-01T08:20:00+08:00", "location": "北京", "description": "追尾", "has_injury": False}
    assert logic.validate_report(ok) == []

    bad = dict(ok)
    bad.pop("occurred_at")
    problems = logic.validate_report(bad)
    assert "occurred_at" in problems


def test_validate_report_rejects_bad_types():
    problems = logic.validate_report(
        {"occurred_at": "2026-11-01", "location": "北京", "description": "x", "has_injury": "yes"}
    )
    assert "has_injury:type" in problems


# --------------------------------------------------------------- CLM-02
def test_idempotency_key_is_stable_and_claim_id_reproducible():
    report = {"occurred_at": "2026-11-01T08:20:00+08:00", "location": "北京市朝阳区建国路"}
    k1 = logic.idempotency_key("OWN-1001", "POL-2026-0001", report)
    k2 = logic.idempotency_key("OWN-1001", "POL-2026-0001", dict(report))
    assert k1 == k2
    assert logic.claim_id_for(k1, occurred_at=report["occurred_at"]) == logic.claim_id_for(
        k2, occurred_at=report["occurred_at"]
    )

    other = logic.idempotency_key("OWN-1001", "POL-2026-0001", {**report, "location": "别处"})
    assert other != k1


# --------------------------------------------------------------- CLM-03
def test_policy_ownership_and_status():
    policy = logic.get_policy("POL-2026-0001", "OWN-1001")
    assert policy["owner_id"] == "OWN-1001"

    with pytest.raises(logic.ClaimError) as exc:
        logic.get_policy("POL-2026-0001", "OWN-9999")
    assert exc.value.code == ErrorCode.TOOL_FORBIDDEN

    with pytest.raises(logic.ClaimError) as exc:
        logic.get_policy("POL-NOT-EXIST", "OWN-1001")
    assert exc.value.code == ErrorCode.POLICY_NOT_FOUND

    with pytest.raises(logic.ClaimError) as exc:  # 已失效保单
        logic.get_policy("POL-2026-0002", "OWN-1002")
    assert exc.value.code == ErrorCode.POLICY_NOT_FOUND


# --------------------------------------------------------------- CLM-05
def test_quote_must_be_verbatim_substring():
    assert is_verbatim("2026年11月1日8时20分许", "……2026年11月1日8时20分许，在朝阳区……")
    assert not is_verbatim("事故发生在11月1日", "……2026年11月1日8时20分许……")


def test_filter_facts_drops_unverifiable_quotes():
    analysis = {
        "documents": [
            {
                "doc_id": "doc-0001",
                "kind": "police_report",
                "facts": [
                    {"key": "accident_time", "value": "x",
                     "evidence": {"doc_id": "doc-0001", "quote": "2026年11月1日8时20分许"}},
                    {"key": "made_up", "value": "y",
                     "evidence": {"doc_id": "doc-0001", "quote": "这句话原材料里没有"}},
                ],
            }
        ]
    }
    filtered, dropped = filter_facts(analysis, {"doc-0001": "2026年11月1日8时20分许发生事故"})
    keys = [f["key"] for f in filtered["documents"][0]["facts"]]
    assert keys == ["accident_time"]
    assert dropped == ["made_up"]


# --------------------------------------------------------------- CLM-06
def test_assess_amount_ignores_model_supplied_amount():
    analysis = rules_analyzer.run_analysis(synthetic.documents("complete"))
    # 模型"越权"塞入金额（schema 本不该有，这里模拟恶意输出）
    analysis["payable_amount"] = 999999.0
    analysis["documents"][0]["payable_amount"] = 888888.0

    assessment = logic.assess_amount(analysis, deductible=500.0, max_payable=20000.0)
    assert assessment["raw_total"] == 2600.0  # 1200 + 800 + 600
    assert assessment["payable_amount"] == 2100.0
    assert assessment["capped"] is False


def test_assess_amount_caps_at_policy_limit():
    analysis = {
        "documents": [
            {"doc_id": "d", "facts": [
                {"key": "repair_item:发动机", "value": 90000.0, "evidence": {"quote": "发动机：90000元"}}
            ]}
        ]
    }
    assessment = logic.assess_amount(analysis, deductible=0.0, max_payable=20000.0)
    assert assessment["payable_amount"] == 20000.0
    assert assessment["capped"] is True


# --------------------------------------------------------------- CLM-07
def test_needs_manual_review_by_amount_or_flag():
    assert logic.needs_manual_review({"payable_amount": 2100.0}, [], threshold=3000) is False
    assert logic.needs_manual_review({"payable_amount": 3100.0}, [], threshold=3000) is True
    assert logic.needs_manual_review({"payable_amount": 10.0}, ["PERSONAL_INJURY"], threshold=3000) is True


# --------------------------------------------------------------- CLM-13
def test_payment_key_is_stable_and_version_sensitive():
    a = logic.payment_key_for("CLM-1", "POL-1", 4820.0, 1)
    b = logic.payment_key_for("CLM-1", "POL-1", 4820.0, 1)
    c = logic.payment_key_for("CLM-1", "POL-1", 4820.0, 2)
    assert a == b != c


# --------------------------------------------------------------- CLM-14
def test_illegal_transition_is_rejected():
    logic.guard_transition(Status.INTAKE, Status.VERIFYING)
    with pytest.raises(logic.ClaimError) as exc:
        logic.guard_transition(Status.PAID, Status.VERIFYING)
    assert exc.value.code == ErrorCode.CLAIM_STATE_INVALID


# ------------------------------------------------------- 错误码白名单（契约 §5）
def test_error_codes_are_within_contract():
    assert len(ALL_ERROR_CODES) == 14
    assert ErrorCode.PAYMENT_UNKNOWN in ALL_ERROR_CODES
    # 实现里出现的错误码必须都在契约表内（这里枚举实现用到的常量）
    used = {
        getattr(ErrorCode, name)
        for name in dir(ErrorCode)
        if name.isupper() and not name.startswith("_")
    }
    assert used <= ALL_ERROR_CODES
