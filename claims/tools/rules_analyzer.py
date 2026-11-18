"""材料分析的**降级实现**（规则引擎，F2 自有）。

Deep Agents 版本由 F3 在 `claims/deep_agents/analyzer.py` 实现，必须提供**同名同签名**：

    def run_analysis(docs: list[dict], *, analyzer_version: str) -> dict

两者产出必须满足同一份 `materials-analysis/1` schema（契约 §4.3）：只有事实 + 出处 +
置信度 + 缺件，**没有任何金额/赔付结论字段**。本文件是 `DEEPAGENTS_ENABLED=false`
（默认）时的路径，保证 t12 集成不因缺少 `deepagents` 包而中断。
"""

from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = "materials-analysis/1"
RULES_VERSION = "rules-1"

_TIME_RE = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时\d{1,2}分")
_PLATE_RE = re.compile(r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z][A-Z0-9]{5}")
_ITEM_RE = re.compile(r"([^\n：:]{2,12})[：:]\s*(\d+(?:\.\d+)?)\s*元")


def _fact(key: str, value: Any, *, doc_id: str, quote: str, confidence: float = 0.9) -> dict:
    return {
        "key": key,
        "value": value,
        "confidence": confidence,
        # quote 必须来自原文的逐字片段（本实现直接用正则命中的原文）
        "evidence": {"doc_id": doc_id, "span": "L1", "quote": quote},
    }


def _facts_for(doc: dict[str, Any]) -> list[dict]:
    doc_id = str(doc.get("doc_id", ""))
    text = str(doc.get("text", ""))
    kind = str(doc.get("kind", ""))
    facts: list[dict] = []

    if kind == "police_report":
        match = _TIME_RE.search(text)
        if match:
            facts.append(_fact("accident_time", match.group(0), doc_id=doc_id, quote=match.group(0)))
        plate = _PLATE_RE.search(text)
        if plate:
            facts.append(_fact("plate_no", plate.group(0), doc_id=doc_id, quote=plate.group(0)))
        if "人伤" in text:
            facts.append(_fact("injury_flag", True, doc_id=doc_id, quote="人伤"))

    if kind == "repair_quote":
        for name, amount in _ITEM_RE.findall(text):
            quote = f"{name}：{amount}元"
            if quote not in text:  # 兼容半角冒号
                quote = f"{name}:{amount}元"
            if quote not in text:
                continue
            facts.append(
                _fact(
                    f"repair_item:{name.strip()}",
                    float(amount),
                    doc_id=doc_id,
                    quote=quote,
                )
            )

    return facts


def run_analysis(docs: list[dict[str, Any]], *, analyzer_version: str = RULES_VERSION) -> dict:
    """规则抽取（降级路径）。返回 `materials-analysis/1` 结构。"""
    documents: list[dict[str, Any]] = []
    for doc in docs or []:
        doc_id = str(doc.get("doc_id", ""))
        facts = _facts_for(doc)
        documents.append(
            {
                "doc_id": doc_id,
                "kind": str(doc.get("kind", "")),
                "facts": facts,
                "consistency_notes": [],
                "anomalies": [],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "claim_id": "",  # 由编排层填（分析层不认识 claim）
        "analyzer": {"mode": "rules_fallback", "model": "rules", "version": analyzer_version},
        "documents": documents,
        "missing_items": [],
        "coverage": {"requested_docs": len(docs or []), "analyzed_docs": len(documents)},
        "cost": {"tokens_in": 0, "tokens_out": 0, "tool_calls": 0},
    }
