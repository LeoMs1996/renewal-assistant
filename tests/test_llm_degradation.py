#!/usr/bin/env python3
"""单元测试：LLM 降级可观测 + 严格模式（SPEC v1.0.5，编排域 F6 整改）。

覆盖：
1. 宽松模式（默认）：LLM 运行时失败 → 结果带 degraded/error_type，且登记到
   client.degradations（不再静默）；
2. 严格模式（RENEWAL_LLM_STRICT=1）：同样失败 → 抛 LLMUnavailableError
   （code=LLM_UNAVAILABLE），不返回规则兜底文本；
3. 显式规则模式（available=False / FORCE_RULE_MODE）：不算降级、不打标记、
   严格模式下也不报错（区分「配置选择的规则模式」与「故障降级」）；
4. 编排层：_llm_event 落 llm_response(mode=rule) + llm_degraded 双标记；
   _stream_guarded 把 LLMUnavailableError 翻译成 error{LLM_UNAVAILABLE}；
5. 探活：严格模式下 provider 不可达 → preflight ok=False（app.py 据此 503）。

本文件不发真实网络请求（所有 provider 调用由 FakeMessages 注入异常）。
运行：.venv/bin/python tests/test_llm_degradation.py   /   pytest 亦可
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import config as config_mod  # noqa: E402
from server import graph as graph_mod  # noqa: E402
from server.llm import (  # noqa: E402
    LLM_UNAVAILABLE,
    LLMClient,
    LLMResult,
    LLMUnavailableError,
)

PASS = 0
FAIL = 0


def check(cond: bool, label: str) -> None:
    global PASS, FAIL
    print(f"  {'✓' if cond else '✗'} {label}")
    PASS += 1 if cond else 0
    FAIL += 0 if cond else 1


class RateLimitError(Exception):
    """模拟 provider 429（SDK 的 RateLimitError 语义一致：可重试的运行时失败）。"""


class FakeMessages:
    def __init__(self, exc: Exception):
        self.exc = exc

    def create(self, **kwargs):
        raise self.exc

    def stream(self, **kwargs):  # noqa: D401 - 用于 stream_chat 分支
        raise self.exc


class FakeAnthropic:
    def __init__(self, exc: Exception):
        self.messages = FakeMessages(exc)

    def with_options(self, **_kwargs):
        return self


class _Env:
    """临时改 config 的 provider 配置（真实 .env 不读取、不修改）。"""

    def __init__(self, *, strict: bool, available: bool = True,
                 exc: Exception | None = None):
        self.strict = strict
        self.available = available
        self.exc = exc or RateLimitError("429 Too Many Requests")

    def __enter__(self):
        self._saved = (config_mod.LLM_BASE_URL, config_mod.LLM_AUTH_TOKEN,
                       config_mod.LLM_MODEL, config_mod.force_rule_mode,
                       config_mod.llm_strict)
        config_mod.LLM_BASE_URL = "http://127.0.0.1:9" if self.available else None
        config_mod.LLM_AUTH_TOKEN = "test-token-not-real" if self.available else None
        config_mod.LLM_MODEL = "stub-model"
        config_mod.force_rule_mode = lambda: not self.available
        config_mod.llm_strict = lambda: self.strict
        return self

    def __exit__(self, *exc_info):
        (config_mod.LLM_BASE_URL, config_mod.LLM_AUTH_TOKEN, config_mod.LLM_MODEL,
         config_mod.force_rule_mode, config_mod.llm_strict) = self._saved
        return False


def _client(env: _Env) -> LLMClient:
    """构造客户端并把 provider 换成注入异常的假实现（无网络）。"""
    client = LLMClient()
    client._client = FakeAnthropic(env.exc)
    return client


# ------------------------------------------------ 1. 宽松模式：留痕降级
def test_loose_mode_marks_degraded():
    print("[1] 宽松模式：失败 → degraded=True（含原因与错误类型）")
    with _Env(strict=False) as env:
        client = _client(env)
        res = client.chat(system="s", messages=[{"role": "user", "content": "hi"}],
                          node="compare")
    check(res.mode == "rule", f"mode = {res.mode!r}（期望 rule）")
    check(res.degraded is True, f"degraded = {res.degraded}（期望 True）")
    check(res.error_type == "RateLimitError", f"error_type = {res.error_type!r}")
    check("规则模式兜底" in res.text, "正文保留「规则模式兜底」提示（旧行为不丢）")
    check(len(client.degradations) == 1
          and client.degradations[0]["node"] == "compare"
          and client.degradations[0]["code"] == LLM_UNAVAILABLE,
          f"client.degradations = {client.degradations}")


def test_tool_json_degraded():
    print("[2] 宽松模式：chat_tool_json 失败 → (None, 带 degraded 的 LLMResult)")
    with _Env(strict=False) as env:
        client = _client(env)
        data, res = client.chat_tool_json(
            system="s", messages=[{"role": "user", "content": "hi"}],
            tool_name="extract_needs", tool_description="d", input_schema={})
    check(data is None, "解析结果 None（调用方仍走关键词规则，行为不变）")
    check(res is not None and res.degraded is True,
          f"LLMResult.degraded = {getattr(res, 'degraded', None)}（期望 True）")
    check(res is not None and res.error_type == "RateLimitError",
          f"error_type = {getattr(res, 'error_type', None)}")


# -------------------------------------------------- 3. 严格模式：显式失败
def test_strict_mode_raises():
    print("[3] 严格模式：失败 → 抛 LLMUnavailableError（不返回兜底文本）")
    raised = None
    with _Env(strict=True) as env:
        client = _client(env)
        try:
            client.chat(system="s", messages=[{"role": "user", "content": "hi"}],
                        node="compare")
        except LLMUnavailableError as exc:
            raised = exc
    check(raised is not None, "抛出了 LLMUnavailableError")
    check(raised is not None and raised.code == LLM_UNAVAILABLE,
          f"code = {getattr(raised, 'code', None)}（期望 {LLM_UNAVAILABLE}）")
    check(raised is not None and raised.error_type == "RateLimitError",
          f"error_type 透传 = {getattr(raised, 'error_type', None)}")
    check(raised is not None and raised.node == "compare",
          f"node 透传 = {getattr(raised, 'node', None)}")


def test_rule_mode_by_config_is_not_degraded():
    print("[4] 显式规则模式（无凭证）：不是降级，严格模式也不报错")
    with _Env(strict=True, available=False) as env:
        client = _client(env)
        res = client.chat(system="s", messages=[{"role": "user", "content": "hi"}])
        probe = client.preflight()
    check(res.mode == "rule" and res.degraded is False,
          f"mode={res.mode}, degraded={res.degraded}（配置性规则模式不打降级标记）")
    check(len(client.degradations) == 0, "未登记降级事件")
    check(probe.get("ok") is True and probe.get("skipped") == "rule_mode_by_config",
          f"preflight = {probe}（显式规则模式放行）")


# ------------------------------------------- 5. 编排层：双标记 + 严格翻译
def test_llm_event_emits_double_marker():
    print("[5] 编排层：_llm_event → llm_response(mode=rule) + llm_degraded")
    captured = []
    original = graph_mod._emit
    graph_mod._emit = lambda event, data, trace=None: captured.append(
        {"event": event, "data": data, "trace": trace})
    try:
        degraded = LLMResult(text="兜底文本", tokens_in=None, tokens_out=None,
                             mode="rule", degraded=True,
                             error_type="RateLimitError", error_message="429")
        marker = graph_mod._llm_event({"trace_id": "tr-1"}, "parse_needs", degraded,
                                      {"tool": "extract_needs"})
        graph_mod._llm_event({"trace_id": "tr-1"}, "compare",
                             LLMResult(text="ok", tokens_in=1, tokens_out=2, mode="llm"))
    finally:
        graph_mod._emit = original

    events = [c["event"] for c in captured]
    check(events == ["llm_response", "llm_degraded", "llm_response"],
          f"事件序列 = {events}")
    resp = captured[0]
    check(resp["data"]["mode"] == "rule" and resp["trace"]["mode"] == "rule"
          and resp["trace"]["degraded"] is True
          and resp["trace"]["error_type"] == "RateLimitError",
          f"llm_response 轨迹含 mode/degraded/error_type：{resp['trace'].get('mode')}/"
          f"{resp['trace'].get('degraded')}/{resp['trace'].get('error_type')}")
    deg = captured[1]
    check(deg["data"]["code"] == LLM_UNAVAILABLE
          and deg["data"]["error_type"] == "RateLimitError"
          and deg["data"]["node"] == "parse_needs",
          f"llm_degraded 载荷 = {deg['data']}")
    check(deg["trace"]["record_type"] == "llm_degraded", "轨迹 record_type=llm_degraded")
    check(marker is not None and marker["code"] == LLM_UNAVAILABLE,
          "返回标记供 State.llm_degraded 汇总（done.degraded 依据）")
    check(captured[2]["trace"].get("degraded") is None,
          "正常（未降级）调用不打 degraded 字段")


class _RaisingInner:
    """模拟图内节点抛出严格模式异常。"""

    def stream(self, initial, config=None, **kwargs):
        raise LLMUnavailableError(node="parse_needs", error_type="RateLimitError",
                                  message="429 Too Many Requests")
        yield  # pragma: no cover

    def invoke(self, initial, config=None, **kwargs):
        raise LLMUnavailableError(node="parse_needs", error_type="RateLimitError",
                                  message="429 Too Many Requests")

    def get_state(self, config):
        return None


def test_stream_guarded_translates_strict_failure():
    print("[6] 编排层：LLMUnavailableError → SSE error{LLM_UNAVAILABLE} + 终态 error")
    handle = graph_mod._ThreadHandle(_RaisingInner())
    events = list(handle.stream({"session_id": "s-strict"}, {}))
    custom = [p for m, p in events if m == "custom"]
    values = [p for m, p in events if m == "values"]
    check(len(custom) == 1 and custom[0]["data"]["code"] == LLM_UNAVAILABLE,
          f"error 事件码 = {custom[0]['data'].get('code') if custom else None}")
    check(custom and custom[0]["data"].get("error_type") == "RateLimitError"
          and custom[0]["data"].get("node") == "parse_needs",
          f"错误载荷透传 = {custom[0]['data'] if custom else None}")
    check(bool(values) and values[-1]["finish_reason"] == "error"
          and values[-1]["exit_reason"] == "llm_unavailable",
          f"终态 = {values[-1] if values else None}")


# ------------------------------------------------------------ 7. 探活（503 依据）
def test_preflight():
    print("[7] 严格模式探活：provider 不可达 → ok=False（app.py 据此 503）")
    with _Env(strict=True) as env:
        client = _client(env)
        probe = client.preflight()
    check(probe.get("ok") is False, f"probe = {probe}")
    check(probe.get("code") == LLM_UNAVAILABLE
          and probe.get("error_type") == "RateLimitError",
          f"错误码/类型 = {probe.get('code')}/{probe.get('error_type')}")

    with _Env(strict=False) as env:  # 非严格模式不探活（零额外上游调用）
        client = _client(env)
        probe2 = client.preflight()
    check(probe2.get("ok") is True and probe2.get("skipped") == "non_strict",
          f"非严格模式 = {probe2}")


if __name__ == "__main__":
    test_loose_mode_marks_degraded()
    test_tool_json_degraded()
    test_strict_mode_raises()
    test_rule_mode_by_config_is_not_degraded()
    test_llm_event_emits_double_marker()
    test_stream_guarded_translates_strict_failure()
    test_preflight()
    print(f"\n通过 {PASS} / {PASS + FAIL}")
    sys.exit(0 if FAIL == 0 else 1)
