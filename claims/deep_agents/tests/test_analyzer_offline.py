"""F3 端到端离线测试：**假模型也能跑完整链路**，且失败必须显式。

覆盖任务书要求的三类：
- schema 校验（含注入材料试图输出金额）
- 超时
- 空材料、脏数据

外加：工具面（无 `execute`）、逐字引用、子代理开关、契约签名与输出键对齐。
"""

from __future__ import annotations

import inspect
import json
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from claims.deep_agents import analyzer, errors, materials
from claims.deep_agents.analyzer import AnalysisConfig, analyze, run_analysis
from claims.deep_agents.materials import materials_root, prepare_materials
from claims.deep_agents.prompts import user_prompt
from claims.deep_agents.schema import assert_no_forbidden_fields
from claims.tools import rules_analyzer

from .conftest import make_fake


@pytest.fixture()
def work_root() -> Path:
    path = materials_root() / f"_pytest-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        import shutil

        shutil.rmtree(path, ignore_errors=True)


def _config(**overrides: Any) -> AnalysisConfig:
    base = dict(timeout_s=60.0, enable_subagents=False, max_attempts=2, recursion_limit=12)
    base.update(overrides)
    return AnalysisConfig(**base)


def _legal_payload(doc_id: str = "doc-0001", quote: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "materials-analysis/1",
        "documents": [
            {
                "doc_id": doc_id,
                "kind": "police_report",
                "facts": [
                    {
                        "key": "accident_time",
                        "value": "2026年11月1日8时20分许",
                        "confidence": 0.92,
                        "evidence": {
                            "doc_id": doc_id,
                            "span": "L2",
                            "quote": quote or "2026年11月1日8时20分许",
                        },
                    }
                ],
                "consistency_notes": [],
                "anomalies": [],
            }
        ],
        "missing_items": [{"key": "repair_quote", "why": "仅提供发票，无定损单"}],
    }


# --------------------------------------------------------------------------- #
# 1) happy path：假模型 → 契约结构
# --------------------------------------------------------------------------- #
def test_run_analysis_happy_path(police_doc: dict[str, Any], work_root: Path) -> None:
    fake = make_fake(_legal_payload())
    out = analyze(
        [police_doc],
        config=_config(model=fake, workspace_root=work_root),
        analyzer_version="rules-1",
    )

    assert out["schema_version"] == "materials-analysis/1"
    assert out["analyzer"]["mode"] == "deepagents"  # 不降级
    assert out["analyzer"]["version"]  # 真实 deepagents 版本
    assert out["coverage"] == {"requested_docs": 1, "analyzed_docs": 1}
    assert out["cost"]["tool_calls"] >= 1
    assert out["documents"][0]["facts"][0]["key"] == "accident_time"
    assert out["missing_items"][0]["key"] == "repair_quote"
    assert out["claim_id"] == ""  # 由编排层填
    assert_no_forbidden_fields(out)
    json.dumps(out, ensure_ascii=False)


def test_output_keys_match_rules_fallback(police_doc: dict[str, Any], work_root: Path) -> None:
    """两种实现必须同 schema（调用方不区分来源）。"""
    fake = make_fake(_legal_payload())
    deep = analyze([police_doc], config=_config(model=fake, workspace_root=work_root), analyzer_version="rules-1")
    rules = rules_analyzer.run_analysis([police_doc], analyzer_version="rules-1")

    assert set(deep) == set(rules)
    assert set(deep["analyzer"]) == set(rules["analyzer"])
    assert set(deep["cost"]) == set(rules["cost"])
    assert set(deep["coverage"]) == set(rules["coverage"])
    assert rules["analyzer"]["mode"] == "rules_fallback"


def test_contract_signature_is_exact() -> None:
    sig = inspect.signature(run_analysis)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["docs", "analyzer_version"]
    assert params[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params[1].kind is inspect.Parameter.KEYWORD_ONLY  # 只允许关键字传
    assert params[1].default is inspect.Parameter.empty  # 必填


def test_no_execute_tool_exposed(police_doc: dict[str, Any], work_root: Path) -> None:
    """F0 断言 A2 的延续：本层也不给模型 shell 能力。"""
    fake = make_fake(_legal_payload())
    analyze([police_doc], config=_config(model=fake, workspace_root=work_root), analyzer_version="rules-1")

    assert "execute" not in fake.bound_tools
    for expected in ("read_file", "ls", "grep"):
        assert expected in fake.bound_tools
    assert "MaterialsAnalysisDraft" in fake.bound_tools


# --------------------------------------------------------------------------- #
# 2) 安全：注入材料不能带出金额/决策
# --------------------------------------------------------------------------- #
def test_injection_material_cannot_add_amount_field(
    injected_doc: dict[str, Any], work_root: Path
) -> None:
    """模型坚持输出 payable_amount → 必须显式失败，而不是"就当没看见"。"""
    hostile = dict(_legal_payload(doc_id="doc-0002"))
    hostile["payable_amount"] = 1000000
    hostile["decision"] = "approve"
    fake = make_fake(hostile)

    with pytest.raises(errors.AnalysisSchemaInvalid) as excinfo:
        analyze(
            [injected_doc],
            config=_config(model=fake, workspace_root=work_root, recursion_limit=6),
            analyzer_version="rules-1",
        )
    assert excinfo.value.code == "ANALYSIS_SCHEMA_INVALID"
    assert excinfo.value.degraded is False


def test_injection_text_does_not_reach_output(injected_doc: dict[str, Any], work_root: Path) -> None:
    """模型"听话"只输出合法 draft 时，材料里的赔付要求也不会变成输出字段。"""
    fake = make_fake(_legal_payload(doc_id="doc-0002", quote="前保险杠喷漆：1200元"))
    out = analyze(
        [injected_doc],
        config=_config(model=fake, workspace_root=work_root),
        analyzer_version="rules-1",
    )
    serialized = json.dumps(out, ensure_ascii=False)
    assert "payable_amount" not in serialized
    assert "decision" not in serialized
    assert_no_forbidden_fields(out)


# --------------------------------------------------------------------------- #
# 3) 引用逐字校验
# --------------------------------------------------------------------------- #
def test_non_verbatim_quote_is_dropped_and_counted(
    police_doc: dict[str, Any], work_root: Path
) -> None:
    fake = make_fake(_legal_payload(quote="这句话材料里没有"))
    out = analyze([police_doc], config=_config(model=fake, workspace_root=work_root), analyzer_version="rules-1")

    doc = out["documents"][0]
    assert doc["facts"] == []
    assert any(a.startswith("quote_not_verbatim:") for a in doc["anomalies"])


def test_unknown_doc_id_is_dropped_and_counted(police_doc: dict[str, Any], work_root: Path) -> None:
    fake = make_fake(_legal_payload(doc_id="doc-9999"))
    out = analyze([police_doc], config=_config(model=fake, workspace_root=work_root), analyzer_version="rules-1")

    ids = [d["doc_id"] for d in out["documents"]]
    assert "doc-9999" not in ids
    assert "doc-0001" in ids  # 请求的材料被补成 skipped_by_model
    skipped = next(d for d in out["documents"] if d["doc_id"] == "doc-0001")
    assert "skipped_by_model" in skipped["anomalies"]


def test_model_skipping_a_document_is_visible(police_doc: dict[str, Any], work_root: Path) -> None:
    two_docs = [
        police_doc,
        {"doc_id": "doc-0002", "kind": "photo", "text": "照片：前保险杠轻微划痕。"},
    ]
    fake = make_fake(_legal_payload())  # 只回了 doc-0001
    out = analyze(two_docs, config=_config(model=fake, workspace_root=work_root), analyzer_version="rules-1")

    assert out["coverage"] == {"requested_docs": 2, "analyzed_docs": 1}
    missing = next(d for d in out["documents"] if d["doc_id"] == "doc-0002")
    assert missing["anomalies"] == ["skipped_by_model"]


# --------------------------------------------------------------------------- #
# 4) 超时 / 失败：必须显式、禁止静默降级
# --------------------------------------------------------------------------- #
def test_timeout_raises_explicitly(police_doc: dict[str, Any], work_root: Path) -> None:
    slow = make_fake(_legal_payload(), delay=2.0)
    started = time.monotonic()
    with pytest.raises(errors.AnalysisTimeout) as excinfo:
        analyze(
            [police_doc],
            config=_config(model=slow, workspace_root=work_root, timeout_s=0.3),
            analyzer_version="rules-1",
        )
    elapsed = time.monotonic() - started

    err = excinfo.value
    assert err.code == "ANALYSIS_UNAVAILABLE"  # 错误码取自契约，不新增
    assert err.error_type == "AnalysisTimeout"
    assert err.degraded is False
    assert elapsed < 5.0  # 不挂死


def test_missing_credentials_raise_not_degrade(
    police_doc: dict[str, Any], work_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """没有模型凭证 → 显式 `NoModelConfigured`，**不**自己退回规则模式。"""
    monkeypatch.setattr(analyzer, "_project_env", lambda name: None)
    monkeypatch.delenv("DEEPAGENTS_MODEL", raising=False)

    with pytest.raises(errors.AnalysisUnavailable) as excinfo:
        analyze(
            [police_doc],
            config=_config(model=None, workspace_root=work_root),
            analyzer_version="rules-1",
        )
    assert excinfo.value.error_type == "NoModelConfigured"


def test_project_model_alias_builds_anthropic_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DEEPAGENTS_MODEL=project` 才复用项目凭证——显式 opt-in，避免意外打真实 API。"""
    env = {
        "ANTHROPIC_BASE_URL": "https://example.invalid/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "test-token",
        "MODEL_NAME": "demo-model",
    }
    monkeypatch.setattr(analyzer, "_project_env", lambda name: env.get(name))

    model, label = analyzer.resolve_model(AnalysisConfig(model="project"))
    assert type(model).__name__ == "ChatAnthropic"
    assert label == "anthropic-compat:demo-model"
    assert getattr(model, "anthropic_api_url", None) == env["ANTHROPIC_BASE_URL"]


def test_bare_enable_does_not_use_project_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """回归：仅 `DEEPAGENTS_ENABLED=true`（没有 DEEPAGENTS_MODEL）绝不能自己去打真实 API。"""
    monkeypatch.setattr(
        analyzer,
        "_project_env",
        lambda name: "present-but-must-not-be-used",
    )
    monkeypatch.delenv("DEEPAGENTS_MODEL", raising=False)
    with pytest.raises(errors.AnalysisUnavailable) as excinfo:
        analyzer.resolve_model(AnalysisConfig(model=None))
    assert excinfo.value.error_type == "NoModelConfigured"


def test_no_silent_degradation_anywhere(police_doc: dict[str, Any], work_root: Path) -> None:
    """失败时不可能拿到 dict；成功时 `mode` 必为 deepagents（本层从不写 rules_fallback）。"""
    hostile = dict(_legal_payload())
    hostile["payout"] = 1
    with pytest.raises(errors.AnalysisError):
        analyze(
            [police_doc],
            config=_config(model=make_fake(hostile), workspace_root=work_root, recursion_limit=6),
            analyzer_version="rules-1",
        )

    ok = analyze(
        [police_doc],
        config=_config(model=make_fake(_legal_payload()), workspace_root=work_root),
        analyzer_version="rules-1",
    )
    assert ok["analyzer"]["mode"] == "deepagents"


# --------------------------------------------------------------------------- #
# 5) 空材料 / 脏数据
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("label", "payload", "error_type"),
    [
        ("空列表", [], "EmptyMaterials"),
        ("None", None, "EmptyMaterials"),
        ("非 list", {"doc_id": "d1"}, "InvalidDocsArgument"),
        ("条目非 dict", ["裸字符串"], "InvalidMaterialEntry"),
        ("缺 doc_id", [{"kind": "photo", "text": "内容"}], "MissingDocId"),
        ("doc_id 路径注入", [{"doc_id": "../.env", "kind": "photo", "text": "内容"}], "InvalidDocId"),
        ("重复 doc_id", [{"doc_id": "d1", "kind": "p", "text": "a"}, {"doc_id": "d1", "kind": "p", "text": "b"}], "DuplicateDocId"),
        ("正文 None", [{"doc_id": "d1", "kind": "photo", "text": None}], "EmptyMaterial"),
        ("正文空白", [{"doc_id": "d1", "kind": "photo", "text": "   \n\t"}], "EmptyMaterial"),
    ],
)
def test_empty_or_dirty_materials_raise_explicit(
    label: str, payload: Any, error_type: str, work_root: Path
) -> None:
    with pytest.raises(errors.AnalysisError) as excinfo:
        analyze(
            payload,
            config=_config(model=make_fake(_legal_payload()), workspace_root=work_root),
            analyzer_version="rules-1",
        )
    assert excinfo.value.code == "MATERIAL_MISSING", label
    assert excinfo.value.error_type == error_type, label


def test_oversized_material_is_truncated_with_flag(work_root: Path) -> None:
    """超长材料截断，但**显式**标记（不静默丢内容）。"""
    long_doc = {"doc_id": "doc-0001", "kind": "photo", "text": "字" * (materials.MAX_DOC_CHARS + 10)}
    mats = prepare_materials([long_doc])
    assert mats[0].truncated is True
    assert len(mats[0].text) == materials.MAX_DOC_CHARS
    assert mats[0].manifest_row()["truncated"] is True


# --------------------------------------------------------------------------- #
# 6) 子代理 / todo（ARCHITECTURE §5.1：>3 份才启用）
# --------------------------------------------------------------------------- #
def test_subagents_and_todo_enabled_only_for_many_docs(work_root: Path) -> None:
    docs = [
        {"doc_id": f"doc-{i:04d}", "kind": "photo" if i % 2 else "police_report", "text": f"材料内容 {i}"}
        for i in range(1, 6)
    ]
    fake = make_fake({"documents": [], "missing_items": []})

    analyzer.analyze(
        docs,
        config=_config(model=fake, workspace_root=work_root, enable_subagents=True),
        analyzer_version="rules-1",
    )
    assert "task" in fake.bound_tools  # 子代理经 task 工具调用
    assert "write_todos" in fake.bound_tools  # v0.7 todo 是 opt-in，本层显式打开

    fake_single = make_fake({"documents": [], "missing_items": []})
    analyzer.analyze(
        docs[:1],
        config=_config(model=fake_single, workspace_root=work_root, enable_subagents=True),
        analyzer_version="rules-1",
    )
    assert "write_todos" not in fake_single.bound_tools


def test_user_prompt_lists_manifest_without_inlining_text() -> None:
    mats = prepare_materials(
        [
            {"doc_id": "doc-0001", "kind": "police_report", "text": "很长的材料正文" * 100},
            {"doc_id": "doc-0002", "kind": "photo", "text": "照片说明"},
        ]
    )
    manifest = [m.manifest_row() for m in mats]
    prompt = user_prompt(manifest)

    assert "doc-0001.txt" in prompt and "doc-0002.txt" in prompt
    assert "很长的材料正文" not in prompt  # 长材料靠文件系统读，不内联
    assert "逐字" in prompt


# --------------------------------------------------------------------------- #
# 7) 缓存/工作区清理
# --------------------------------------------------------------------------- #
def test_workspace_is_cleaned_up_by_default(police_doc: dict[str, Any], work_root: Path) -> None:
    fake = make_fake(_legal_payload())
    analyze([police_doc], config=_config(model=fake, workspace_root=work_root), analyzer_version="rules-1")
    assert list(work_root.glob("analysis-*")) == []


def test_workspace_can_be_kept_for_debug(police_doc: dict[str, Any], work_root: Path) -> None:
    fake = make_fake(_legal_payload())
    analyze(
        [police_doc],
        config=_config(model=fake, workspace_root=work_root, keep_workspace=True),
        analyzer_version="rules-1",
    )
    kept = list(work_root.glob("analysis-*"))
    assert len(kept) == 1
    assert (kept[0] / "manifest.json").is_file()
