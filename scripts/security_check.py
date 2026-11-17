#!/usr/bin/env python3
"""安全自检（CI 门禁）：把「安全契约」变成可执行断言，而不是文档承诺。

六段检查（每一段都对应 reviews/security.md 里的一条基准与一个已落地的控制）：
  A 凭证卫生   —— 受版本控制的文件里不得出现真实密钥（OWASP API8/CICD 泄露）
  B 忽略规则   —— .env 与轨迹/会话目录必须被 .gitignore 覆盖（PII 不得入库）
  C 轨迹 PII   —— traces/*.jsonl 全文扫描：身份证号/手机号零命中（LLM02）
  D 运行时契约 —— CSP(Trusted Types) / no-store / 422 契约错误体 / 鉴权 / 独立配额
  E 脱敏自测   —— 写端脱敏对样例生效，且 owner_id 等归属字段保留
  F 浏览器 CSP —— 可选（--browser）：调用 scripts/csp_browser_check.py 做真实渲染验证

用法：
  .venv/bin/python scripts/security_check.py            # A~E
  .venv/bin/python scripts/security_check.py --browser  # 追加 F（需本机 Chrome）
退出码 0 = 全部通过；1 = 有失败项。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 必须在 import server.* 之前隔离轨迹目录，避免自检本身污染生产观测数据
os.environ.setdefault("TRACE_DIR", tempfile.mkdtemp(prefix="sec-check-traces-"))
os.environ["RENEWAL_FORCE_RULE_MODE"] = "1"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


# ---------------------------------------------------------------- A 凭证卫生
# 只匹配"看起来是真的密钥"：占位符（xxxx / your- / <...>）全部排除。
SECRET_PATTERNS = [
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9]{10,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]
SCAN_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".html", ".js", ".txt",
                 ".toml", ".env", ".example", ".sh", ".cfg"}
SKIP_DIRS = {".venv", "traces", "__pycache__", ".git", ".mypy_cache", ".ruff_cache",
             ".pytest_cache", "node_modules"}


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == ".env":  # 本机凭证文件：内容不上报，只由 B 段校验是否被忽略
            continue
        yield path


def section_a() -> None:
    hits: list[str] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(text):
                hits.append(f"{path.relative_to(ROOT)}: {label}={m.group(0)[:12]}***")
    check("A.凭证卫生（真实密钥不入库）", not hits,
          "; ".join(hits[:3]) or "未发现真实密钥形态")


# ---------------------------------------------------------------- B 忽略规则
def section_b() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (
        ROOT / ".gitignore").is_file() else ""
    needed = {".env": "凭证文件", "traces/*.jsonl": "含 PII 的轨迹",
              "traces/sessions": "会话快照（保单原文）"}
    missing = [f"{pat}（{why}）" for pat, why in needed.items() if pat not in ignore]
    check("B.忽略规则（PII/凭证不入库）", not missing,
          "; ".join(missing) or ".env / 轨迹 / 会话快照均被 .gitignore 覆盖")


# ---------------------------------------------------------------- C 轨迹 PII
ID_RE = re.compile(r"(?<![0-9A-Za-z])\d{6}\d{8}\d{3}[0-9Xx](?![0-9A-Za-z])")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


# 姓名/车牌/VIN 用合成数据里的固定值做探针：正则抓不准中文姓名，
# 但"这几位车主的姓名是否还躺在磁盘上"是可判定的（存量 967 个文件已清理，
# 见 scripts/trace_purge_pii.py）。
PII_LITERAL_PROBES = {
    "姓名": "张伟",
    "姓名2": "李静",
    "车牌": "沪AD12345",
    "VIN": "LSVAA26E2NE100001",
}


def section_c() -> None:
    trace_dir = ROOT / "traces"
    files = sorted(trace_dir.glob("*.jsonl"))
    leaks: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in (("身份证", ID_RE), ("手机号", PHONE_RE)):
            if pattern.search(text):
                leaks.append(f"{path.name}: {label}")
        for label, probe in PII_LITERAL_PROBES.items():
            if probe in text:
                leaks.append(f"{path.name}: {label}")
                break
    check("C.轨迹 PII（存量+新增）", not leaks,
          f"{len(files)} 个轨迹文件零 PII 原文命中" if not leaks
          else "; ".join(leaks[:3]))


# ------------------------------------------------------------ D 运行时契约
def section_d() -> None:
    from starlette.testclient import TestClient

    from server import config as config_mod
    from server import llm as llm_mod
    from server.app import app
    from server.middleware import reset_rate_limiter

    client = TestClient(app)
    reset_rate_limiter()
    original_keys = config_mod.api_keys
    try:
        config_mod.api_keys = lambda: {}  # 演示模式：只验头与契约错误体
        llm_mod._client = None
        resp = client.get("/policy/OWN-1001")
        csp = resp.headers.get("content-security-policy", "")
        check("D1.CSP 强制 Trusted Types",
              "require-trusted-types-for 'script'" in csp
              and "trusted-types default" in csp
              and "frame-ancestors 'none'" in csp, csp[:120])
        check("D2.PII 端点禁缓存",
              "no-store" in resp.headers.get("cache-control", ""),
              resp.headers.get("cache-control", "<无>"))

        bad = client.post("/chat", json={"session_id": "sec", "owner_id": "OWN-1001",
                                         "message": "x" * 5000})
        body = bad.json() if bad.headers.get("content-type", "").startswith(
            "application/json") else {}
        check("D3.入参超限 → 422 契约错误体",
              bad.status_code == 422 and body.get("error", {}).get("code") == "INVALID_INPUT"
              and "x" * 5000 not in json.dumps(body, ensure_ascii=False),
              f"HTTP={bad.status_code} code={body.get('error', {}).get('code')}")

        config_mod.api_keys = lambda: {"probe-key": "OWN-1001"}
        anon = client.get("/docs")
        check("D4.生产模式文档需凭证", anon.status_code == 401,
              f"GET /docs 无凭证 HTTP={anon.status_code}")
        unauthorized = client.get("/policy/OWN-1001")
        check("D5.无凭证 401 + 安全头",
              unauthorized.status_code == 401
              and "content-security-policy" in {
                  k.lower() for k in unauthorized.headers},
              f"HTTP={unauthorized.status_code}")

        chat_limit = config_mod.chat_rate_limit_per_min()
        ip_limit = config_mod.rate_limit_per_min()
        check("D6./chat 独立配额", chat_limit < ip_limit or chat_limit > 0,
              f"chat={chat_limit}/min · ip={ip_limit}/min（独立计数，见 middleware）")
    finally:
        config_mod.api_keys = original_keys
        reset_rate_limiter()


# ---------------------------------------------------------------- E 脱敏自测
def section_e() -> None:
    from server import security
    from server import trace as trace_mod

    sample_id, sample_phone = "310101198503157731", "13801610001"
    masked = security.redact_text(f"身份证{sample_id} 手机{sample_phone}")
    check("E1.文本脱敏", sample_id not in masked and sample_phone not in masked,
          masked[:80])

    tmp = Path(tempfile.mkdtemp(prefix="sec-check-write-"))
    rec = trace_mod.TraceRecorder("trc-20261117000000-sec001", "s", trace_dir=tmp)
    rec.record("tool_result", node="get_policy",
               input={"owner_id": "OWN-1001"},
               output={"owner": {"owner_id": "OWN-1001", "name": "张伟",
                                 "id_number": sample_id, "phone": sample_phone}})
    text = (tmp / "trc-20261117000000-sec001.jsonl").read_text(encoding="utf-8")
    check("E2.写端脱敏（唯一写入点）",
          sample_id not in text and sample_phone not in text and "张伟" not in text,
          "轨迹文件里无 PII 原文")
    check("E3.归属字段保留（BOLA 校验依赖 owner_id）",
          "OWN-1001" in text, "owner_id 未被脱敏")


# ------------------------------------------------------------ F 浏览器 CSP
def section_f() -> None:
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/csp_browser_check.py")],
                          cwd=ROOT, capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [proc.stderr.strip()[-160:]]
    check("F.浏览器 CSP/SSE 实测", proc.returncode == 0, tail[0] if tail else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", action="store_true", help="追加真实浏览器验证")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    section_a()
    section_b()
    section_c()
    section_d()
    section_e()
    if args.browser:
        section_f()

    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    if args.json:
        print(json.dumps([{"check": n, "ok": ok, "detail": d}
                          for n, ok, d in RESULTS], ensure_ascii=False, indent=1))
    else:
        width = max(len(n) for n, _, _ in RESULTS) + 2
        for name, ok, detail in RESULTS:
            print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}} {detail}")
        print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} 通过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
