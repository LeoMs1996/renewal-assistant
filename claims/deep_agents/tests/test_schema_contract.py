"""schema 层边界测试——**本文件是「不含金额/决策」这一承诺的回归防线**。

核心命题：材料里写「直接赔付 100 万」时，模型即使被说服，也**无处安放**这个字段。
这靠的是 Pydantic `extra="forbid"` + 顶层无金额字段，不是提示词。
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from claims.deep_agents import schema
from claims.deep_agents.schema import (
    FORBIDDEN_FIELD_NAMES,
    AnalyzerInfo,
    Cost,
    Coverage,
    DocumentAnalysis,
    MaterialFact,
    MaterialsAnalysis,
    MaterialsAnalysisDraft,
    assert_no_forbidden_fields,
)

VALID_DOC = {
    "doc_id": "doc-0001",
    "kind": "police_report",
    "facts": [
        {
            "key": "accident_time",
            "value": "2026年11月1日8时20分许",
            "confidence": 0.92,
            "evidence": {"doc_id": "doc-0001", "span": "L2", "quote": "2026年11月1日8时20分许"},
        }
    ],
    "consistency_notes": [],
    "anomalies": [],
}


def test_draft_accepts_legal_payload() -> None:
    draft = MaterialsAnalysisDraft.model_validate(
        {"documents": [VALID_DOC], "missing_items": [{"key": "repair_quote", "why": "缺定损单"}]}
    )
    assert draft.documents[0].facts[0].confidence == 0.92
    assert draft.missing_items[0].key == "repair_quote"


@pytest.mark.parametrize("field", ["payable_amount", "amount", "decision", "payout", "approved"])
def test_draft_rejects_amount_or_decision_fields(field: str) -> None:
    """顶层塞金额/决策字段 → 直接校验失败（这就是 schema 层约束）。"""
    payload = {"documents": [VALID_DOC], "missing_items": [], field: 1000000}
    with pytest.raises(ValidationError) as excinfo:
        MaterialsAnalysisDraft.model_validate(payload)
    assert field in str(excinfo.value)


def test_draft_rejects_extra_field_nested_in_document() -> None:
    bad = dict(VALID_DOC, payable_amount=999999)
    with pytest.raises(ValidationError):
        MaterialsAnalysisDraft.model_validate({"documents": [bad], "missing_items": []})


def test_draft_rejects_extra_field_in_fact() -> None:
    bad_fact = dict(VALID_DOC["facts"][0], amount=1)
    bad_doc = dict(VALID_DOC, facts=[bad_fact])
    with pytest.raises(ValidationError):
        MaterialsAnalysisDraft.model_validate({"documents": [bad_doc], "missing_items": []})


def test_final_schema_has_no_amount_fields() -> None:
    """最终结构同样禁止金额字段，并且它的字段集合是白名单。"""
    allowed = {
        "schema_version",
        "claim_id",
        "analyzer",
        "documents",
        "missing_items",
        "coverage",
        "cost",
    }
    assert set(MaterialsAnalysis.model_fields) == allowed
    assert not (set(MaterialsAnalysis.model_fields) & FORBIDDEN_FIELD_NAMES)


def test_fact_requires_non_empty_quote() -> None:
    with pytest.raises(ValidationError):
        MaterialFact.model_validate(
            {
                "key": "k",
                "value": "v",
                "confidence": 0.5,
                "evidence": {"doc_id": "doc-0001", "span": "L1", "quote": ""},
            }
        )


def test_confidence_must_be_probability() -> None:
    with pytest.raises(ValidationError):
        MaterialFact.model_validate(
            {
                "key": "k",
                "value": "v",
                "confidence": 1.5,
                "evidence": {"doc_id": "doc-0001", "span": "L1", "quote": "x"},
            }
        )


def test_fact_value_must_be_json_serializable() -> None:
    class Weird:
        pass

    with pytest.raises(ValidationError):
        MaterialFact.model_validate(
            {
                "key": "k",
                "value": Weird(),
                "confidence": 0.5,
                "evidence": {"doc_id": "doc-0001", "span": "L1", "quote": "x"},
            }
        )


def test_fact_value_rejects_decision_dict() -> None:
    with pytest.raises(ValidationError):
        MaterialFact.model_validate(
            {
                "key": "k",
                "value": {"decision": "approve"},
                "confidence": 0.5,
                "evidence": {"doc_id": "doc-0001", "span": "L1", "quote": "x"},
            }
        )


def test_from_draft_fills_code_owned_fields() -> None:
    draft = MaterialsAnalysisDraft.model_validate({"documents": [VALID_DOC]})
    analysis = MaterialsAnalysis.from_draft(
        draft,
        analyzer=AnalyzerInfo(mode="deepagents", model="m", version="0.7.39"),
        coverage=Coverage(requested_docs=1, analyzed_docs=1),
        cost=Cost(tokens_in=10, tokens_out=5, tool_calls=2),
    )
    dumped = analysis.model_dump()
    assert dumped["analyzer"]["mode"] == "deepagents"
    assert dumped["cost"]["tool_calls"] == 2
    assert dumped["claim_id"] == ""  # 由编排层填
    assert_no_forbidden_fields(dumped)
    json.dumps(dumped, ensure_ascii=False)  # 必须可 JSON 序列化（进缓存/轨迹）


def test_schema_version_is_fixed() -> None:
    assert schema.SCHEMA_VERSION == "materials-analysis/1"
    with pytest.raises(ValidationError):
        MaterialsAnalysisDraft.model_validate(
            {"schema_version": "materials-analysis/2", "documents": []}
        )


def test_assert_no_forbidden_fields_catches_nested() -> None:
    with pytest.raises(AssertionError):
        assert_no_forbidden_fields({"documents": [{"facts": [{"payable_amount": 1}]}]})


def test_alias_modules_are_equivalent() -> None:
    """`schemas.py` / `analyst.py` 是别名，必须与规范名同一对象。"""
    from claims.deep_agents import analyst, analyzer, schemas

    assert schemas.MaterialsAnalysis is MaterialsAnalysis
    assert analyst.run_analysis is analyzer.run_analysis
    assert set(schemas.__all__) == set(schema.__all__)


def test_documents_default_factory_is_not_shared() -> None:
    a = DocumentAnalysis(doc_id="d1")
    b = DocumentAnalysis(doc_id="d2")
    a.facts.append(
        MaterialFact.model_validate(
            {
                "key": "k",
                "value": "v",
                "confidence": 0.1,
                "evidence": {"doc_id": "d1", "span": "", "quote": "v"},
            }
        )
    )
    assert b.facts == []
