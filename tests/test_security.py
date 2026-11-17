#!/usr/bin/env python3
"""安全中间件单元测试（2026-11-13 评审整改验收）。

覆盖范围（对应 OWASP API Security Top 10 2023）：
- API2 Broken Authentication：无密钥 401 / 错误密钥 401 / 正确密钥放行
- API1 BOLA：密钥与请求 owner_id 不符 403（owner 由凭证派生，不采信请求自报）
- API8 注入/路径穿越：trace_id 白名单 400
- API4 Unrestricted Resource Consumption：滑动窗口限流 429 + Retry-After
- 响应头基线：CSP / nosniff / X-Frame-Options / Referrer-Policy（含 401 响应）
- 演示模式：未配置密钥时放行并标 X-Auth-Mode: demo

运行：.venv/bin/python -m pytest tests/test_security.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import config as config_mod  # noqa: E402
from server.app import app  # noqa: E402
from server.middleware import reset_rate_limiter, trace_owner_allowed  # noqa: E402

client = TestClient(app)

SEC_HEADERS = ("content-security-policy", "x-content-type-options",
               "x-frame-options", "referrer-policy")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """每个用例从干净的限流桶与无密钥状态开始。"""
    reset_rate_limiter()
    monkeypatch.delenv("RENEWAL_API_KEYS", raising=False)
    monkeypatch.delenv("RENEWAL_RATE_LIMIT_PER_MIN", raising=False)
    # .env 里可能配了密钥，这里强制以 env(空) 覆盖不了 dotenv，故直接打补丁
    yield
    reset_rate_limiter()


# ------------------------------------------------------------------ 演示模式
def test_demo_mode_passes_and_marks_header(monkeypatch):
    monkeypatch.setattr(config_mod, "api_keys", lambda: {})
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-auth-mode") == "demo"


# ------------------------------------------------------------------ 鉴权
def test_missing_key_401_with_security_headers(monkeypatch):
    monkeypatch.setattr(config_mod, "api_keys", lambda: {"k1": "OWN-1001"})
    r = client.get("/policy/OWN-1001")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.headers.get("www-authenticate") == "ApiKey"
    # 最外层 SecurityHeaders 必须给错误响应也补上安全头
    for h in SEC_HEADERS:
        assert h in {k.lower() for k in r.headers}, f"401 响应缺少 {h}"


def test_wrong_key_401(monkeypatch):
    monkeypatch.setattr(config_mod, "api_keys", lambda: {"k1": "OWN-1001"})
    r = client.get("/policy/OWN-1001", headers={"X-API-Key": "bogus"})
    assert r.status_code == 401


def test_owner_mismatch_403(monkeypatch):
    """API1 BOLA：k1 绑定 OWN-1001，却请求 OWN-1002 → 403。"""
    monkeypatch.setattr(config_mod, "api_keys", lambda: {"k1": "OWN-1001"})
    r = client.get("/policy/OWN-1002", headers={"X-API-Key": "k1"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "OWNER_FORBIDDEN"


def test_owner_match_passes(monkeypatch):
    monkeypatch.setattr(config_mod, "api_keys", lambda: {"k1": "OWN-1001"})
    r = client.get("/policy/OWN-1001", headers={"X-API-Key": "k1"})
    assert r.status_code in (200, 404)  # 200=有保单；404=合成数据里无该保单，均非鉴权失败


def test_body_owner_mismatch_403(monkeypatch):
    """POST 请求体里的 owner_id 同样必须与凭证一致（防止改 body 越权）。"""
    monkeypatch.setattr(config_mod, "api_keys", lambda: {"k1": "OWN-1001"})
    r = client.post("/confirm", headers={"X-API-Key": "k1"},
                    json={"session_id": "s", "quote_id": "QT-x",
                          "quote_version": 1, "owner_id": "OWN-1002"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "OWNER_FORBIDDEN"


# ------------------------------------------------------- trace_id 路径穿越
@pytest.mark.parametrize("path", [
    "/trace/..%2F..%2F.env",
    "/trace/..%2f..%2f.env",
    "/trace/%2e%2e%2f.env",
    "/trace/etc%2Fpasswd",
])
def test_trace_id_whitelist_blocks_traversal(monkeypatch, path):
    monkeypatch.setattr(config_mod, "api_keys", lambda: {})
    r = client.get(path)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "TRACE_ID_INVALID"


def test_trace_id_valid_format_passes_whitelist(monkeypatch):
    """格式合法但不存在的 trace → 404（证明是"格式校验通过、文件不存在"）。"""
    monkeypatch.setattr(config_mod, "api_keys", lambda: {})
    r = client.get("/trace/trc-20261113000000-abcdef")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TRACE_NOT_FOUND"


# ------------------------------------------------------------------ 限流
def test_rate_limit_429_with_retry_after(monkeypatch):
    monkeypatch.setattr(config_mod, "api_keys", lambda: {})
    monkeypatch.setattr(config_mod, "rate_limit_per_min", lambda: 2)
    reset_rate_limiter()
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    r = client.get("/health")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert int(r.headers["retry-after"]) >= 1


# --------------------------------------------------- 轨迹内容归属（单元层）
def test_trace_owner_allowed_rules():
    rows = [{"record_type": "tool_call",
             "input": {"owner_id": "OWN-1002"}}]
    assert trace_owner_allowed(rows, "OWN-1001") is False, "他人轨迹必须拒绝"
    assert trace_owner_allowed(rows, "OWN-1002") is True, "本人轨迹放行"
    assert trace_owner_allowed(rows, None) is True, "演示模式无凭证不校验内容"
    assert trace_owner_allowed([{"record_type": "message"}], "OWN-1001") is True, \
        "无归属证据的轨迹放行（不含保单数据）"
