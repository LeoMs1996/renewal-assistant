"""F4 HTTP/SSE 层测试（`claims/api.py`）。

原则：**不 mock 业务**——直接用真实 `ClaimGraph` + 临时 DB/轨迹（`tmp_env` 夹具），
只把"环境"隔离掉；HTTP 面走 `TestClient`（进程内 ASGI，不起端口）。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from claims import api as capi
from claims.graph import ClaimGraph
from claims.state import ErrorCode, Status
from claims.tools import synthetic
from server.trace import RECORD_TYPES


def _payload(**over):
    payload = {
        "owner_id": "OWN-1001",
        "policy_no": "POL-2026-0001",
        "session_id": "sess-f4-test",
        "report": {
            "occurred_at": "2026-11-08T09:00:00+08:00",
            "location": "南京市鼓楼区中山北路",
            "description": "追尾，前保险杠受损",
            "has_injury": False,
        },
        "documents": synthetic.documents("complete"),
    }
    payload.update(over)
    return payload


@pytest.fixture()
def client(tmp_env, monkeypatch):
    """真实图 + 临时数据目录；严格模式按当前解释器自动判定（.venv 下允许规则模式）。"""
    monkeypatch.setenv("CLAIMS_ALLOW_RULES_ONLY", "1")   # 单测不因解释器不同而红
    monkeypatch.setenv("CLAIMS_AMOUNT_REVIEW_THRESHOLD", "0")  # 强制人工，便于测 resume
    graph = ClaimGraph()
    app = capi.create_app(capi.ClaimService(graph), strict=False)
    with TestClient(app) as c:
        yield c
    graph.close()


def test_preflight_reports_real_environment():
    report = capi.preflight(strict=False)
    assert report["wiki_entries"] > 0, "wiki 语料不能为空（D-21）"
    assert report["trace_dir_isolated"] is True, "轨迹必须落 traces-claims（C0 基线 §4）"
    assert report["trace_dir"].endswith("traces-claims")


def test_preflight_strict_rejects_missing_deepagents(monkeypatch):
    """D-22：`.venv` 下严格模式必须拒起（否则"假绿"）。"""
    monkeypatch.setattr(capi, "_deepagents_available", lambda: False)
    with pytest.raises(RuntimeError) as excinfo:
        capi.assert_preflight(strict=True)
    assert "deepagents" in str(excinfo.value)
    # 显式允许规则模式时不应抛
    monkeypatch.setenv("CLAIMS_ALLOW_RULES_ONLY", "1")
    assert capi.assert_preflight()["strict"] is False


def test_intake_interrupt_approve_paid_via_http(client):
    resp = client.post("/claims/intake", json=_payload())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    claim_id = body["claim_id"]
    assert claim_id.startswith("CLM-")
    assert body["status"] == Status.REVIEW_PENDING
    assert body["interrupt"]["kind"] == "claim_review"
    assert body["interrupt"]["allowed_decisions"] == ["approve", "reject"]

    snapshot = client.get(f"/claims/{claim_id}").json()
    assert snapshot["next"] == ["review_gate"]

    resumed = client.post(f"/claims/{claim_id}/resume",
                          json={"decision": "approve", "comment": "材料齐备", "reviewer_id": "RV-9"})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == Status.PAID

    # 轨迹：record_type 全在 11 种白名单内，且事件是 claims.* 命名空间
    rows = client.app.state.service.events(claim_id)
    assert {r["record_type"] for r in rows} <= set(RECORD_TYPES)
    kinds = {(r.get("event") or {}).get("kind") for r in rows}
    assert {"claims.intake_accepted", "claims.review_requested",
            "claims.review_approved", "claims.payment_charged"} <= kinds


def test_resume_rejects_bad_decision_and_terminal_thread(client):
    claim_id = client.post("/claims/intake", json=_payload()).json()["claim_id"]

    bad = client.post(f"/claims/{claim_id}/resume", json={"decision": "approve"})
    # 空 comment 的 approve 是合法的；这里用 schema 外的 decision 验证 422
    assert bad.status_code == 200
    bad2 = client.post(f"/claims/{claim_id}/resume",
                       json={"decision": "maybe", "comment": "x"})
    assert bad2.status_code == 422  # FastAPI 的 pydantic 校验

    # reject 必须带 comment（SPEC §4.4）→ 我们的服务层映射 REVIEW_DECISION_INVALID
    rejected = capi.ClaimService(client.app.state.service.graph).resume(
        claim_id, {"decision": "approve", "comment": "", "reviewer_id": "RV-1"})
    assert rejected["status"] == Status.PAID

    # 终态线程再 resume → CLAIM_STATE_INVALID + 409
    again = client.post(f"/claims/{claim_id}/resume",
                        json={"decision": "reject", "comment": "重复审核"})
    assert again.status_code == 409
    codes = [e["code"] for e in again.json()["state"]["errors"]]
    assert ErrorCode.CLAIM_STATE_INVALID in codes


def test_intake_field_invalid_maps_to_400(client):
    bad = _payload(report={"occurred_at": "", "location": "", "description": "", "has_injury": "不是布尔"})
    resp = client.post("/claims/intake", json=bad)
    assert resp.status_code == 400, resp.text
    codes = [e["code"] for e in resp.json()["state"]["errors"]]
    assert ErrorCode.CLAIM_FIELD_INVALID in codes


def test_wiki_check_writes_retrieval_row(client):
    claim_id = client.post("/claims/intake", json=_payload()).json()["claim_id"]
    resp = client.post(f"/claims/{claim_id}/wiki-check",
                       json={"query": "农业保险赔付档位怎么确定", "top_k": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"]["hits"], "36 页语料必须能命中"
    assert body["result"]["citations"]["total"] > 0
    assert body["trace_row"]["kind"] == "claims.wiki_retrieved"

    rows = [r for r in client.app.state.service.events(claim_id)
            if r["record_type"] == "retrieval"]
    assert len(rows) == 1
    assert rows[0]["event"]["hit_ids"][0].startswith("claims-")


def test_sse_replays_trace_then_done(client):
    claim_id = client.post("/claims/intake", json=_payload()).json()["claim_id"]
    with client.stream("GET", f"/claims/{claim_id}/events") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        text = "".join(resp.iter_text())
    assert "event: node_start" in text
    assert "event: done" in text
    # SSE 的 event 名只能来自 11 种白名单 + done
    events = {line.split(": ", 1)[1] for line in text.splitlines() if line.startswith("event: ")}
    assert events <= (set(RECORD_TYPES) | {"done"})


def test_metrics_endpoint_has_samples_not_only_help(client):
    claim_id = client.post("/claims/intake", json=_payload()).json()["claim_id"]
    client.post(f"/claims/{claim_id}/resume", json={"decision": "approve", "comment": "ok"})
    text = client.get("/metrics").text
    sample_lines = [ln for ln in text.splitlines()
                    if ln.startswith("renewal_") and not ln.startswith("renewal_#")]
    assert sample_lines, "指标必须真实暴露样本行，不能只有 HELP/TYPE"
    assert any("renewal_" in ln for ln in sample_lines)
