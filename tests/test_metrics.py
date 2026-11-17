"""平台工程域：Prometheus 指标 / OTel GenAI 语义约定 落地测试（t8, 2026-11-17）。

验证点：
1. TraceRecorder.record() → metrics 同源映射（llm_response 的 token/耗时、
   node_end 节点耗时、tool_result 工具耗时、retrieval 检索耗时、error 计数）；
2. semconv 必填属性到位：gen_ai.operation.name / gen_ai.provider.name /
   gen_ai.request.model / gen_ai.token.modality；
3. 规则模式不产出 gen_ai.* 信号（没有真实推理，不污染 AI 口径）；
4. Prometheus 文本格式合规：HELP/TYPE 行、标签值转义、histogram 必有 le="+Inf"
   且等于 _count；
5. 高基数治理：指标名与标签键不含 trace_id / session_id，也不含原始 owner_id。
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from server import config, metrics
from server.app import app
from server.trace import TraceRecorder


def _recorder(tmp_path, trace_id: str = "trc-20261117000000-metrics"):
    return TraceRecorder(trace_id=trace_id, session_id="sess-metrics",
                         trace_dir=tmp_path)


@pytest.fixture(autouse=True)
def _deterministic_llm(monkeypatch):
    """固定 LLM 身份，避免测试随 .env / 环境变量漂移。"""
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://api.deepseek.com/anthropic")
    monkeypatch.setattr(config, "LLM_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(config, "LLM_MODEL", "deepseek-flash")
    monkeypatch.setattr(config, "force_rule_mode", lambda: False)
    metrics.reset()
    yield
    metrics.reset()


def test_record_feeds_genai_metrics(tmp_path):
    rec = _recorder(tmp_path)
    rec.record("llm_response", node="parse_needs", latency_ms=250.0,
               tokens_in=100, tokens_out=180)
    out = metrics.render()
    # semconv：必填属性全部到位（operation.name / provider.name / request.model）
    assert ('gen_ai_client_inference_usage_input_tokens_total{'
            'gen_ai_operation_name="chat",gen_ai_provider_name="deepseek",'
            'gen_ai_request_model="deepseek-flash",gen_ai_token_modality="text"} 100'
            ) in out
    assert "gen_ai_client_inference_duration_seconds_bucket" in out
    # token 计数器应带 _total（Prometheus 累积计数命名规则）
    assert "gen_ai_client_inference_usage_output_tokens_total" in out
    # 推理耗时直方图 sum 应为 0.25 秒（基本单位=秒）
    assert re.search(r"gen_ai_client_inference_duration_seconds_sum\{[^}]*\} 0\.25", out)


def test_node_tool_retrieval_metrics(tmp_path):
    rec = _recorder(tmp_path)
    rec.record("node_end", node="intake", latency_ms=0.4)
    rec.record("tool_result", node="quote", latency_ms=12.0)
    rec.record("retrieval", node="retrieve_terms", latency_ms=2.0)
    rec.record("error", error={"code": "INTERNAL", "message": "x"})
    out = metrics.render()
    # 标签按名排序输出；0.4ms 落在最小桶 le="0.001" 内
    assert 'renewal_node_duration_seconds_bucket{node="intake",le="0.001"} 1' in out
    assert 'gen_ai_execute_tool_duration_seconds_count{gen_ai_tool_name="quote"} 1' in out
    assert ('gen_ai_retrieval_duration_seconds_count{'
            'gen_ai_operation_name="retrieval",node="retrieve_terms"} 1') in out
    assert 'renewal_errors_total{code="INTERNAL"} 1' in out


def test_rule_mode_emits_no_genai_signals(monkeypatch, tmp_path):
    """规则模式下没有 GenAI 推理：不得往 gen_ai.* 命名空间写样本。"""
    monkeypatch.setattr(config, "force_rule_mode", lambda: True)
    rec = _recorder(tmp_path)
    rec.record("llm_response", node="compare", latency_ms=5.0,
               tokens_in=None, tokens_out=None)
    rec.record("error", error={"code": "INTERNAL"})
    out = metrics.render()
    assert "gen_ai_client_inference_duration_seconds_bucket" not in out
    assert "gen_ai_client_inference_usage_input_tokens_total{" not in out
    # 应用级指标照常
    assert "renewal_errors_total" in out


def test_label_escaping(tmp_path):
    """Prometheus 文本格式：标签值中的 \\ " 换行 必须转义，否则抓取端解析失败。"""
    rec = _recorder(tmp_path)
    rec.record("error", error={"code": 'BAD"CODE\nX', "message": "m"})
    out = metrics.render()
    line = next(ln for ln in out.splitlines() if ln.startswith("renewal_errors_total{"))
    assert '\\"' in line and "\\n" in line
    assert "\n" not in line
    # 反转义后应还原为原始值：只有包裹的两个引号未转义
    assert line.count('"') - line.count('\\"') == 2


def test_histogram_has_inf_bucket_equal_count(tmp_path):
    rec = _recorder(tmp_path)
    for lat in (1.0, 100.0, 90000.0):  # 第三个超出所有桶边界（81.92s）
        rec.record("llm_response", node="compare", latency_ms=lat,
                   tokens_in=1, tokens_out=1)
    out = metrics.render()
    count = int(re.search(
        r"gen_ai_client_inference_duration_seconds_count\{[^}]*\} (\d+)", out).group(1))
    inf = int(re.search(
        r'gen_ai_client_inference_duration_seconds_bucket\{[^}]*le="\+Inf"\} (\d+)',
        out).group(1))
    assert count == inf == 3


def test_metrics_endpoint_prometheus_text():
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "version=0.0.4" in r.headers["content-type"]
    body = r.text
    assert "# TYPE renewal_chat_requests_total counter" in body
    assert "# TYPE gen_ai_client_inference_duration_seconds histogram" in body
    # 高基数治理：指标名与标签键不含 trace/session 维度
    assert "trace_id" not in body and "session_id" not in body
    assert "owner_id" not in body


def test_finish_turn_aggregates_agent_metrics(tmp_path):
    rec = _recorder(tmp_path, trace_id="trc-20261117000010-turn")
    rec.record("tool_call", node="get_policy")
    rec.record("tool_result", node="get_policy", latency_ms=1.0, output={})
    rec.record("tool_call", node="quote")
    rec.record("tool_result", node="quote", latency_ms=1.0, output={})
    rec.record("llm_call", node="compare")
    rec.record("llm_response", node="compare", latency_ms=9.0, tokens_in=1, tokens_out=1)
    metrics.finish_turn("trc-20261117000010-turn", 2.5, "done")
    out = metrics.render()
    # 一轮内 2 次工具调用 → invoke_agent.tool_calls 落在 le="2" 桶
    assert re.search(r'gen_ai_invoke_agent_tool_calls_bucket\{gen_ai_agent_name='
                     r'"renewal-assistant",gen_ai_operation_name="invoke_workflow",'
                     r'le="2"\} 1', out)
    assert ('gen_ai_invoke_agent_inference_calls_count{gen_ai_agent_name='
            '"renewal-assistant",gen_ai_operation_name="invoke_workflow"} 1') in out
    assert 'renewal_chat_requests_total{outcome="done"} 1' in out
    assert ('gen_ai_invoke_agent_duration_seconds_count{error_type="",'
            'gen_ai_agent_name=') in out
    # 轮次状态已释放
    assert metrics.turn_counts("trc-20261117000010-turn")["tool"] == 0


def test_no_reserved_namespace_abuse():
    """semconv 未定义的指标不得占用 gen_ai.* 命名空间（改名前缀 renewal_）。"""
    metrics.reset()
    body = metrics.render()
    listed = {ln.split()[2] for ln in body.splitlines() if ln.startswith("# TYPE")}
    assert "gen_ai_client_inference_requests_total" not in listed
    assert "renewal_inference_requests_total" in listed
    assert listed  # 非空
