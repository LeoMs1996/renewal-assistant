"""F2d（t21）：X1 对账 4 条 degradation 的回归测试 + analysis_key 缓存 + 指标接线。

每条测试都对应一个**曾经真实发生过**的缺陷，因此必须"能失败"：
- I4-a 首行轨迹落到 `unknown.jsonl`（轨迹无法按 claim 重放）
- I4-b 降级原因被 `except Exception: pass` 吞掉（无法回答"为什么降级"）
- I6-a 终态线程再 invoke 会重跑全流程并再次 charge（网关去重兜底 ≠ 流程正确）
- I6-b 已 paid 后二次 resume 静默成功
"""

from __future__ import annotations

import json
from pathlib import Path

from claims.graph import ClaimGraph
from claims.state import ErrorCode, Event, Status
from claims.tools import synthetic
from claims.tools.payment_gateway import MockPaymentGateway

REPO_ROOT = Path(__file__).resolve().parents[2]


def _graph(tmp_env, **gateway_kw) -> ClaimGraph:
    return ClaimGraph(
        gateway=MockPaymentGateway(**gateway_kw),
        checkpoint_db=tmp_env / "data" / "checkpoints.sqlite",
        trace_dir=tmp_env / "traces-claims",
    )


def _thread(claim_input: dict) -> str:
    return f"t21-{claim_input['report']['occurred_at']}-{claim_input['report']['location']}"


def _traces(tmp_env) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for path in (tmp_env / "traces-claims").glob("*.jsonl"):
        out[path.name] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out


def _history_len(graph: ClaimGraph, thread: str) -> int:
    return sum(1 for _ in graph.graph.get_state_history({"configurable": {"thread_id": thread}}))


# --------------------------------------------------------------------------- #
# I4-a：新案首行轨迹必须落在 traces-claims/<claim_id>.jsonl
# --------------------------------------------------------------------------- #
def test_i4a_first_trace_row_goes_to_claim_file(tmp_env, claim_input):
    graph = _graph(tmp_env)
    cfg = claim_input("complete")
    result = graph.invoke(cfg, thread_id=_thread(cfg))
    graph.close()

    traces = _traces(tmp_env)
    assert "unknown.jsonl" not in traces, f"首行落到了 unknown.jsonl：{list(traces)}"
    claim_file = f"{result['claim_id']}.jsonl"
    assert claim_file in traces, f"缺少 {claim_file}，实际：{list(traces)}"

    rows = traces[claim_file]
    assert rows, "轨迹不能为空"
    # 首行就必须属于本 claim（曾经是 unknown.jsonl 里的 intake_invalid/accepted）
    assert rows[0]["trace_id"] == result["claim_id"]
    assert (rows[0].get("event") or {})["kind"] == Event.INTAKE_ACCEPTED
    assert {r["trace_id"] for r in rows} == {result["claim_id"]}


def test_i4a_invalid_report_trace_also_uses_claim_file(tmp_env, claim_input):
    """无效报案也不许写 unknown.jsonl（轨迹要能按 claim 归档）。"""
    graph = _graph(tmp_env)
    cfg = claim_input("complete")
    cfg["report"] = {"location": "北京", "description": "x", "has_injury": False}  # 缺 occurred_at
    graph.invoke(cfg, thread_id="t21-invalid")
    graph.close()

    traces = _traces(tmp_env)
    assert "unknown.jsonl" not in traces, list(traces)
    assert len(traces) == 1
    (name, rows), = traces.items()
    assert (rows[0].get("event") or {})["kind"] == Event.INTAKE_INVALID
    assert name != "unknown.jsonl"


# --------------------------------------------------------------------------- #
# I4-b：降级必须带 error_type / error_class
# --------------------------------------------------------------------------- #
class _FakeTimeout(Exception):
    """模拟 F3 的 AnalysisTimeout（带契约里的 error_type 属性）。"""

    error_type = "AnalysisTimeout"


def test_i4b_degradation_records_error_type(tmp_env, claim_input, monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "true")
    import claims.deep_agents.analyzer as deep_analyzer

    def boom(docs, *, analyzer_version):
        raise _FakeTimeout("模型调用超时（模拟）")

    monkeypatch.setattr(deep_analyzer, "run_analysis", boom)

    graph = _graph(tmp_env)
    cfg = claim_input("complete")
    thread = _thread(cfg)
    graph.invoke(cfg, thread_id=thread)
    graph.close()

    traces = _traces(tmp_env)
    (name, rows), = [(n, r) for n, r in traces.items() if n != "unknown.jsonl"]
    degraded = [r for r in rows if (r.get("event") or {}).get("kind") == Event.LLM_DEGRADED]
    assert degraded, f"缺少 claims.llm_degraded 轨迹行；事件有 {[(r.get("event") or {}).get("kind") for r in rows]}"

    event = degraded[0]["event"]
    assert event["error_type"] == "AnalysisTimeout", event
    assert event["error_class"] == "_FakeTimeout", event
    assert event["mode"] == "rules_fallback"
    assert "超时" in event["message"]


def test_i4b_disabled_switch_also_records_reason(tmp_env, claim_input, monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "false")
    graph = _graph(tmp_env)
    cfg = claim_input("complete")
    graph.invoke(cfg, thread_id=_thread(cfg))
    graph.close()

    rows = next(r for n, r in _traces(tmp_env).items() if n != "unknown.jsonl")
    degraded = [r for r in rows if (r.get("event") or {}).get("kind") == Event.LLM_DEGRADED]
    assert degraded
    assert degraded[0]["event"]["error_type"] == "DeepAgentsDisabled"


# --------------------------------------------------------------------------- #
# I6-a：终态线程再 invoke 不得重跑流程 / 不得再次 charge
# --------------------------------------------------------------------------- #
def test_i6a_terminal_thread_reinvoke_is_rejected(tmp_env, claim_input):
    graph = _graph(tmp_env)
    cfg = claim_input("complete")
    thread = _thread(cfg)

    first = graph.invoke(cfg, thread_id=thread)
    assert first["status"] == Status.PAID
    assert graph.gateway.charge_count == 1
    history_before = _history_len(graph, thread)

    second = graph.invoke(cfg, thread_id=thread)

    assert graph.gateway.charge_count == 1, "终态后不得再次调用支付网关"
    assert _history_len(graph, thread) == history_before, "终态后不得新增 checkpoint 推进"
    assert second["status"] == Status.PAID
    assert second["claim_id"] == first["claim_id"]
    codes = [e["code"] for e in second["errors"]]
    assert ErrorCode.CLAIM_STATE_INVALID in codes, second["errors"]
    graph.close()


# --------------------------------------------------------------------------- #
# I6-b：已 paid 后二次 resume 必须明确报错，不许静默成功
# --------------------------------------------------------------------------- #
def test_i6b_resume_after_paid_is_rejected(tmp_env, claim_input):
    graph = _graph(tmp_env)
    cfg = claim_input("complete")
    thread = _thread(cfg)
    graph.invoke(cfg, thread_id=thread)
    assert graph.state(thread_id=thread).values["status"] == Status.PAID

    history_before = _history_len(graph, thread)
    out = graph.resume({"decision": "approve", "reviewer_id": "RV-0009"}, thread_id=thread)

    assert _history_len(graph, thread) == history_before, "终态后 resume 不得推进 checkpoint"
    assert graph.gateway.charge_count == 1
    codes = [e["code"] for e in out["errors"]]
    assert ErrorCode.CLAIM_STATE_INVALID in codes
    assert out["status"] == Status.PAID


def test_i6b_resume_without_pending_interrupt_is_rejected(tmp_env, claim_input):
    graph = _graph(tmp_env)
    cfg = claim_input("missing_quote")  # 停在 need_info（无挂起中断）
    thread = _thread(cfg)
    paused = graph.invoke(cfg, thread_id=thread)
    assert paused["status"] == Status.NEED_INFO

    out = graph.resume({"decision": "approve"}, thread_id=thread)
    assert ErrorCode.CLAIM_STATE_INVALID in [e["code"] for e in out["errors"]]
    graph.close()


# --------------------------------------------------------------------------- #
# D2：SPEC §3.2 的 analysis_key 缓存必须真的存在
# --------------------------------------------------------------------------- #
def test_analysis_cache_hit_on_second_analysis(tmp_env, claim_input, monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "false")
    graph = _graph(tmp_env)
    state = {
        "claim_id": "CLM-20261101-cache001",
        "session_id": "sess-cache",
        "documents": synthetic.documents("complete"),
        "errors": [],
    }

    first = graph.analyze_materials(dict(state))
    assert first["analysis_cached"] is False
    key = first["analysis_key"]
    cache_file = tmp_env / "data" / "cache" / f"{key}.json"
    assert cache_file.exists(), f"未落盘缓存：{cache_file}"

    second = graph.analyze_materials(dict(state))
    assert second["analysis_cached"] is True
    assert second["analysis_key"] == key
    assert second["materials_analysis"] == first["materials_analysis"]
    graph.close()


def test_analysis_key_changes_with_content_and_claim(tmp_env, claim_input):
    graph = _graph(tmp_env)
    docs = synthetic.documents("complete")
    base = graph.analyze_materials({"claim_id": "C1", "session_id": "s", "documents": docs, "errors": []})
    same = graph.analyze_materials({"claim_id": "C1", "session_id": "s", "documents": docs, "errors": []})
    other_claim = graph.analyze_materials({"claim_id": "C2", "session_id": "s", "documents": docs, "errors": []})
    changed_docs = [dict(docs[0]), dict(docs[1], text=docs[1]["text"] + "\n右前翼子板：300元\n")]
    other_docs = graph.analyze_materials({"claim_id": "C1", "session_id": "s", "documents": changed_docs, "errors": []})

    assert base["analysis_key"] == same["analysis_key"]
    assert base["analysis_key"] != other_claim["analysis_key"]
    assert base["analysis_key"] != other_docs["analysis_key"]
    graph.close()


# --------------------------------------------------------------------------- #
# D1：指标是否真的接进理赔域（不是"我以为接了"）
# --------------------------------------------------------------------------- #
def test_metrics_are_actually_wired(tmp_env, claim_input):
    from server import metrics

    metrics.reset()
    graph = _graph(tmp_env)
    cfg = claim_input("complete")
    graph.invoke(cfg, thread_id=_thread(cfg))
    graph.close()

    rendered = metrics.render()
    # observe_record() 只认 node_end / tool_call / tool_result / llm_response / error；
    # 理赔域必须真的产出这些行，指标才有内容（只看"代码里有没有调用"会误判）。
    assert "renewal_node_duration" in rendered, rendered[:400]
    assert 'renewal_tool_calls_total{node="execute_payment"}' in rendered, rendered[:400]
    # 每个节点都必须有 node_end（否则 /metrics 永远为空——X1 D1 的真问题）
    for node in (
        "intake", "verify_precheck", "analyze_materials", "assess_amount", "finalize",
    ):
        assert f'node="{node}"' in rendered, f"缺少 {node} 的指标样本"


# --------------------------------------------------------------------------- #
# 裁决落地：F3 的 anomalies 不得进入 flags，也不得影响路由
# --------------------------------------------------------------------------- #
def test_anomalies_do_not_leak_into_flags(tmp_env, claim_input):
    from claims.tools import logic

    analysis = {
        "documents": [
            {"doc_id": "d1", "kind": "police_report", "facts": [],
             "anomalies": ["skipped_by_model", "quote_not_verbatim:改写过的引文",
                           "kind_mismatch:photo!=police_report", "unknown_doc_id_dropped:2"]},
        ]
    }
    flags = logic.flags_for(analysis, synthetic.documents("complete"), [])
    assert flags == [], f"anomalies 泄漏进 flags：{flags}"

    # 路由也不受影响：无业务 flags 且金额未超阈值 → 自动核准
    assessment = {"payable_amount": 100.0}
    assert logic.needs_manual_review(assessment, flags, threshold=3000) is False


def test_anomaly_codes_registry_matches_spec():
    """词汇表与实现保持同步（SPEC §4.6）。"""
    from pathlib import Path as _P

    from claims.tools import logic

    spec = (_P(__file__).resolve().parents[1] / "SPEC-claims.md").read_text(encoding="utf-8")
    for code in logic.ANALYSIS_ANOMALY_CODES:
        assert f"`{code}" in spec, f"SPEC §4.6 缺少 anomaly 码 {code}"
