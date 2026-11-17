#!/usr/bin/env python3
"""SSE 链路回归测试：流必须正常收尾（2026-11-13 修复的挂死缺陷）。

背景：生产者投递结束哨兵 `(None, None)`，消费者判 `chunk is None`，哨兵永不匹配
→ 事件循环一直 await 下一条，连接永不关闭；客户端（curl / eval / 前端）只能等超时。
本测试的价值在于：只要有人再动这段收尾逻辑，立刻红。

断言：
1. `/chat` 的 SSE 流在超时时间内**自然结束**（不靠客户端断开）；
2. 最后一次事件是 `done`，且带 `trace_id` / `finish_reason`；
3. 事件带递增的 `id:` 序号（断线重连契约的前提）；
4. 空闲期有心跳 `: ping` 能力由服务端 15s 超时实现（本测试不等待 15s，只验证格式不破坏解析）。

运行：.venv/bin/python -m pytest tests/test_sse.py -q
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import config as config_mod  # noqa: E402
from server import llm as llm_mod  # noqa: E402
from server.app import app  # noqa: E402
from server.middleware import reset_rate_limiter  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def rule_mode(monkeypatch):
    """强制规则模式：确定性、不依赖 .env 里的 LLM 凭证。"""
    monkeypatch.setattr(config_mod, "force_rule_mode", lambda: True)
    monkeypatch.setattr(config_mod, "api_keys", lambda: {})
    monkeypatch.setattr(config_mod, "rate_limit_per_min", lambda: 10000)
    monkeypatch.setattr(llm_mod, "_client", None)  # 清掉已缓存的客户端
    reset_rate_limiter()
    yield
    reset_rate_limiter()


def _collect_stream(payload: dict, timeout_s: float = 40.0):
    events, ids, started = [], [], time.monotonic()
    with client.stream("POST", "/chat", json=payload) as resp:
        assert resp.status_code == 200, f"/chat HTTP {resp.status_code}"
        name = None
        for line in resp.iter_lines():
            if time.monotonic() - started > timeout_s:
                pytest.fail(f"SSE 流超过 {timeout_s}s 未结束（疑似结束哨兵未生效）")
            if line.startswith("id: "):
                ids.append(int(line[4:].strip()))
            elif line.startswith("event: "):
                name = line[7:].strip()
            elif line.startswith("data: ") and name:
                events.append((name, json.loads(line[6:])))
                name = None
    return events, ids, time.monotonic() - started


def test_sse_stream_closes_and_ends_with_done(rule_mode):
    events, ids, elapsed = _collect_stream(
        {"session_id": "sse-1", "owner_id": "OWN-1001",
         "message": "我的车险快到期了"})
    names = [e for e, _ in events]
    assert "done" in names, f"流已结束但缺 done 事件，事件={sorted(set(names))}"
    last_name, last_data = events[-1]
    assert last_name == "done", f"最后一帧应为 done，实际={last_name}"
    assert last_data.get("trace_id"), "done 必须带 trace_id"
    assert last_data.get("finish_reason"), "done 必须带 finish_reason"
    assert elapsed < 40, f"收尾耗时过长：{elapsed:.1f}s"


def test_sse_event_ids_are_increasing(rule_mode):
    _events, ids, _elapsed = _collect_stream(
        {"session_id": "sse-2", "owner_id": "OWN-1001",
         "message": "三者险保额从100万升到200万，给我续保报价"})
    assert len(ids) >= 5, f"事件 id 数过少：{ids}"
    assert ids == sorted(ids), f"id 必须单调递增：{ids}"
    assert ids == list(range(1, len(ids) + 1)), f"id 应从 1 连续：{ids}"
