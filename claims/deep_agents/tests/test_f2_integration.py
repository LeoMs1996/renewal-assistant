"""跨边界测试：F2 `claims.graph.run_analysis` 与本层的交互。

只读 F2 的模块（不改一行），验证两件事：

1. `DEEPAGENTS_ENABLED=true` 时用的是本层；
2. 本层**抛异常**时 F2 能兜底降级到 `rules_fallback`（降级是 F2 的决定，不是本层偷偷做的）。
"""

from __future__ import annotations

from typing import Any

import pytest

from claims import config as claims_config
from claims import graph as claims_graph
from claims.deep_agents import analyzer as deep_analyzer
from claims.deep_agents import errors


def _doc() -> list[dict[str, Any]]:
    return [{"doc_id": "doc-0001", "kind": "police_report", "text": "2026年11月1日8时20分许 两车刮擦"}]


def test_f2_uses_f3_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(claims_config, "deepagents_enabled", lambda: True)
    sentinel = {
        "schema_version": "materials-analysis/1",
        "claim_id": "",
        "analyzer": {"mode": "deepagents", "model": "fake", "version": "0.7.39"},
        "documents": [],
        "missing_items": [],
        "coverage": {"requested_docs": 1, "analyzed_docs": 0},
        "cost": {"tokens_in": 0, "tokens_out": 0, "tool_calls": 0},
    }
    monkeypatch.setattr(deep_analyzer, "run_analysis", lambda docs, *, analyzer_version: dict(sentinel))

    out = claims_graph.run_analysis(_doc(), analyzer_version="rules-1")
    assert out["analyzer"]["mode"] == "deepagents"


def test_f2_degrades_when_f3_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """本层显式报错 → F2 兜底 rules_fallback，主流程不中断。"""
    monkeypatch.setattr(claims_config, "deepagents_enabled", lambda: True)

    def _boom(docs: list[dict[str, Any]], *, analyzer_version: str) -> dict[str, Any]:
        raise errors.AnalysisTimeout("模拟超时")

    monkeypatch.setattr(deep_analyzer, "run_analysis", _boom)

    out = claims_graph.run_analysis(_doc(), analyzer_version="rules-1")
    assert out["analyzer"]["mode"] == "rules_fallback"
    assert out["schema_version"] == "materials-analysis/1"


def test_f2_degrades_when_f3_returns_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """返回缺 schema_version 的脏 dict → F2 也降级（契约要求 schema_version 存在）。"""
    monkeypatch.setattr(claims_config, "deepagents_enabled", lambda: True)
    monkeypatch.setattr(deep_analyzer, "run_analysis", lambda docs, *, analyzer_version: {"oops": 1})

    out = claims_graph.run_analysis(_doc(), analyzer_version="rules-1")
    assert out["analyzer"]["mode"] == "rules_fallback"


def test_f2_uses_rules_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(claims_config, "deepagents_enabled", lambda: False)
    out = claims_graph.run_analysis(_doc(), analyzer_version="rules-1")
    assert out["analyzer"]["mode"] == "rules_fallback"
