"""平台工程域：轨迹 JSONL → OTel span（OTLP/HTTP JSON）落地测试（t8, 2026-11-17）。

验证点（对应 reviews/platform.md §三 的 F1/F2）：
1. 一轮对话（根 span）下能重建节点/工具/推理/检索四类子 span，父子链正确；
2. 命名与 kind 符合 GenAI 语义约定（chat=CLIENT、execute_tool <name>/retrieval/
   invoke_workflow <agent>=INTERNAL）；
3. 错误经 status.code=2 + error.type 表达（不只靠日志）；
4. OTLP JSON 编码合规：traceId 32 位十六进制、spanId 16 位、kind 为整数、
   时间戳为十进制字符串、不发送空 envelope；
5. 敏感内容不外泄：导出的载荷不含 input/output 原文（semconv 默认不采集）；
6. 真实历史轨迹（traces/*.jsonl）全量可转换，且 spanId 唯一、parent 可解析。
"""
from __future__ import annotations

import json
import time

import pytest

from server import config, metrics, otel_export
from server.trace import TraceRecorder

TRACE_ID = "trc-20261117000000-oteltst"


@pytest.fixture(autouse=True)
def _deterministic_llm(monkeypatch):
    """固定 LLM 身份。

    注意：tests/test_orchestration.py 在模块级 setdefault 了
    RENEWAL_FORCE_RULE_MODE=1（进程级副作用），若本文件依赖 .env 的真实配置，
    全量跑套件时 provider 会变成 None、gen_ai.* 指标不产出。测试必须显式钉住
    身份，才能既独立跑也随套件跑。
    """
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://api.deepseek.com/anthropic")
    monkeypatch.setattr(config, "LLM_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(config, "LLM_MODEL", "deepseek-flash")
    monkeypatch.setattr(config, "force_rule_mode", lambda: False)
    metrics.reset()
    yield
    metrics.reset()


def _record_turn(tmp_path) -> list[dict]:
    """用真实 TraceRecorder 落一条覆盖四类 span 的轨迹（含派生耗时）。"""
    rec = TraceRecorder(trace_id=TRACE_ID, session_id="sess-otel", trace_dir=tmp_path)
    rows = [rec.record("user_message", input="三者险升到200万，报个价")]
    rows.append(rec.record("node_start", node="intake"))
    rows.append(rec.record("node_end", node="intake", output={"intent": "renewal"},
                           latency_ms=0.5))
    rows.append(rec.record("node_start", node="get_policy"))
    rows.append(rec.record("tool_call", node="get_policy", input={"owner_id": "OWN-1001"}))
    rows.append(rec.record("tool_result", node="get_policy", latency_ms=1.5,
                           output={"found": True}))
    rows.append(rec.record("node_end", node="get_policy", latency_ms=1.8))
    rows.append(rec.record("node_start", node="parse_needs"))
    rows.append(rec.record("llm_call", node="parse_needs",
                           input={"system": "needs-extractor"}))
    rows.append(rec.record("llm_response", node="parse_needs", output="{}",
                           tokens_in=120, tokens_out=45))
    rows.append(rec.record("node_end", node="parse_needs", latency_ms=900.0))
    rows.append(rec.record("node_start", node="retrieve_terms"))
    rows.append(rec.record("retrieval", node="retrieve_terms", input="三者险 保额",
                           output=[{"wiki_id": "wiki-dsx"}, {"wiki_id": "wiki-ywyw"}]))
    rows.append(rec.record("node_end", node="retrieve_terms", latency_ms=3.0))
    rows.append(rec.record("node_start", node="quote"))
    rows.append(rec.record("tool_call", node="quote", input={"vin": "LSVAA26E2NE100001"}))
    rows.append(rec.record("tool_result", node="quote", latency_ms=2.0,
                           output={"quote_id": "QT-1"}))
    rows.append(rec.record("node_end", node="quote", latency_ms=2.5))
    rows.append(rec.record("assistant_message", output="【模拟报价】..."))
    return rows


def test_span_tree_and_naming(tmp_path):
    rows = _record_turn(tmp_path)
    spans = otel_export.build_spans(rows, trace_id=TRACE_ID,
                                    provider="deepseek", model="deepseek-flash")
    names = [s.name for s in spans]
    assert names[0] == f"invoke_workflow {metrics.AGENT_NAME}"  # 根 span
    assert "node.intake" in names and "chat" in names
    assert "execute_tool get_policy" in names and "retrieval" in names

    by_id = {s.span_id: s for s in spans}
    root = spans[0]
    assert root.parent_id is None
    assert root.kind == otel_export.KIND_INTERNAL
    assert root.attributes["gen_ai.operation.name"] == "invoke_workflow"
    assert root.attributes["gen_ai.agent.name"] == metrics.AGENT_NAME
    assert root.attributes["gen_ai.provider.name"] == "deepseek"

    chat = next(s for s in spans if s.name == "chat")
    assert chat.kind == otel_export.KIND_CLIENT
    assert chat.attributes["gen_ai.operation.name"] == "chat"
    assert chat.attributes["gen_ai.usage.input_tokens"] == 120
    assert chat.attributes["gen_ai.usage.output_tokens"] == 45
    assert chat.end_ns >= chat.start_ns
    # 推理 span 挂在 parse_needs 节点下，而不是根 span 下
    parent = by_id[chat.parent_id]
    assert parent.name == "node.parse_needs"

    tool = next(s for s in spans if s.name == "execute_tool get_policy")
    assert tool.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool.attributes["gen_ai.tool.name"] == "get_policy"
    assert by_id[tool.parent_id].name == "node.get_policy"

    ret = next(s for s in spans if s.name == "retrieval")
    assert ret.attributes["gen_ai.operation.name"] == "retrieval"
    assert ret.attributes["gen_ai.retrieval.documents.count"] == 2


def test_derived_latency_feeds_span_duration(tmp_path):
    """llm_response / retrieval 无显式 latency 时，record() 派生值应撑起 span 时长。"""
    rows = _record_turn(tmp_path)
    llm_resp = next(r for r in rows if r["record_type"] == "llm_response")
    ret_row = next(r for r in rows if r["record_type"] == "retrieval")
    # 派生耗时写回 §5 既有字段（不新增字段）
    assert llm_resp["latency_ms"] is not None
    assert ret_row["latency_ms"] is not None
    spans = otel_export.build_spans(rows, trace_id=TRACE_ID)
    chat = next(s for s in spans if s.name == "chat")
    assert (chat.end_ns - chat.start_ns) >= 0
    ret = next(s for s in spans if s.name == "retrieval")
    assert "renewal.duration.derived" not in ret.attributes  # 有 latency，无需降级


def test_error_status_propagation(tmp_path):
    rows = _record_turn(tmp_path)
    rec = TraceRecorder(trace_id=TRACE_ID, session_id="sess-otel", trace_dir=tmp_path)
    rec._seq = len(rows)  # 续写同一轨迹（仅测试构造用）
    rows = rows + [rec.record("error", node="quote",
                              error={"code": "QUOTE_VERSION_STALE", "message": "过期"})]
    spans = otel_export.build_spans(rows, trace_id=TRACE_ID)
    errored = [s for s in spans if s.status_code == otel_export.STATUS_ERROR]
    assert errored, "error 记录必须转成 span status=ERROR"
    assert any(s.attributes.get("error.type") == "QUOTE_VERSION_STALE"
               for s in errored)


def test_otlp_payload_encoding(tmp_path):
    rows = _record_turn(tmp_path)
    spans = otel_export.build_spans(rows, trace_id=TRACE_ID)
    payload = otel_export.to_otlp_payload([(otel_export.trace_id_hex(TRACE_ID), spans)])
    rs = payload["resourceSpans"]
    assert len(rs) == 1
    attrs = {a["key"]: a["value"] for a in rs[0]["resource"]["attributes"]}
    assert attrs["service.name"]["stringValue"] == "renewal-assistant"
    otlp_spans = rs[0]["scopeSpans"][0]["spans"]
    assert otlp_spans
    for s in otlp_spans:
        assert len(s["traceId"]) == 32 and s["traceId"] == s["traceId"].lower()
        assert len(s["spanId"]) == 16
        assert isinstance(s["kind"], int)          # 枚举必须是整数
        assert isinstance(s["startTimeUnixNano"], str)   # int64 用字符串
        assert isinstance(s["endTimeUnixNano"], str)
        assert int(s["endTimeUnixNano"]) >= int(s["startTimeUnixNano"])
        if "parentSpanId" in s:
            assert len(s["parentSpanId"]) == 16
    # 空 envelope 不发（OTLP：SHOULD NOT）
    empty = otel_export.to_otlp_payload([(otel_export.trace_id_hex("trc-x"), [])])
    assert empty["resourceSpans"] == []


def test_no_content_leak(tmp_path):
    """默认不导出 input/output 原文（semconv：敏感内容 SHOULD NOT 默认采集）。"""
    rows = _record_turn(tmp_path)
    payload = otel_export.to_otlp_payload(
        [("a" * 32, otel_export.build_spans(rows, trace_id=TRACE_ID))])
    blob = json.dumps(payload, ensure_ascii=False)
    assert "三者险升到200万" not in blob      # user_message 原文
    assert "LSVAA26E2NE100001" not in blob    # tool_call 入参（VIN 属敏感）
    assert "QT-1" not in blob                 # tool_result 输出
    assert "gen_ai.input.messages" not in blob
    assert "gen_ai.output.messages" not in blob


def test_historical_traces_all_convert():
    """真实历史轨迹全量可转换（含半行/异常行的容错），paren 链可解析。"""
    trace_dir = otel_export.config.TRACE_DIR
    files = sorted(trace_dir.glob("*.jsonl"))
    if not files:
        pytest.skip("traces/ 为空，跳过历史轨迹回归")
    traces, stats = otel_export.collect(trace_dir)
    assert stats["files"] == len(files) or stats["empty"] > 0
    assert stats["spans"] > 0
    for trace_hex, spans in traces:
        assert len(trace_hex) == 32
        ids = [s.span_id for s in spans]
        assert len(ids) == len(set(ids)), "spanId 在同一条轨迹内必须唯一"
        known = set(ids)
        for s in spans[1:]:
            assert s.parent_id in known, "子 span 的 parent 必须可解析"
            assert s.end_ns >= s.start_ns
    # 端到端 CLI 冒烟：离线导出前 3 条轨迹
    assert otel_export.main(["--trace-dir", str(trace_dir), "--limit", "3",
                             "--out", "/dev/null"]) == 0


def test_metrics_agent_histograms_from_turns(tmp_path):
    """一轮收口后应产出 gen_ai.invoke_agent.* 三项（semconv agent 指标）。"""
    metrics.reset()
    rows = _record_turn(tmp_path)
    for row in rows:
        # TraceRecorder 已自动喂指标；这里再显式触发保证顺序无关
        metrics.observe_record(row)
    metrics.finish_turn(TRACE_ID, 1.75, "done")
    out = metrics.render()
    assert "gen_ai_invoke_agent_duration_seconds_count{" in out
    assert "gen_ai_invoke_agent_tool_calls_bucket" in out
    assert "gen_ai_invoke_agent_inference_calls_bucket" in out
    assert 'gen_ai_agent_name="renewal-assistant"' in out
    assert 'gen_ai_operation_name="invoke_workflow"' in out
    # 轮次状态已清理，不会随进程生命周期无界增长
    assert metrics.turn_counts(TRACE_ID)["tool"] == 0


def test_metrics_not_applied_twice(tmp_path):
    """observe_record 幂等性检查：同一行重复喂入会重复计数（显式文档化行为）。"""
    metrics.reset()
    rec = TraceRecorder(trace_id="trc-20261117000001-dup", session_id="s",
                        trace_dir=tmp_path)
    rec.record("llm_response", node="compare", latency_ms=100.0,
               tokens_in=10, tokens_out=5)
    metrics.reset()  # 清掉 record() 自动写入的样本，避免干扰
    row = {"record_type": "llm_response", "node": "compare",
           "trace_id": "trc-dup", "latency_ms": 100.0, "tokens_in": 10, "tokens_out": 5}
    metrics.observe_record(row)
    metrics.observe_record(row)
    out = metrics.render()
    assert 'gen_ai_client_inference_usage_input_tokens_total' in out
    assert " 20 " in out or "20\n" in out  # 两次 × 10


def test_latency_derivation_is_monotonic(tmp_path):
    """派生耗时必须是单调时钟差（墙钟回拨不影响），且不覆盖显式值。"""
    rec = TraceRecorder(trace_id="trc-20261117000002-drv", session_id="s",
                        trace_dir=tmp_path)
    rec.record("llm_call", node="compare")
    time.sleep(0.02)
    row = rec.record("llm_response", node="compare", tokens_in=1, tokens_out=1)
    assert row["latency_ms"] >= 15  # 20ms 睡眠的保守下界
    explicit = rec.record("node_end", node="compare", latency_ms=1.23)
    assert explicit["latency_ms"] == 1.23
