#!/usr/bin/env python
"""平台工程域自检（t8，2026-11-17）：离线校验部署配置与观测面一致性。

为什么需要它
------------
`deploy/` 里的 Prometheus 规则、告警、探针一旦写错（指标名拼错、YAML 缩进错、
引用了不存在的指标）不会在单测里暴露，只会在生产上表现为"告警永远不响"。
本脚本把这类"配置漂移"变成可执行的断言，可在 CI 里秒级跑完（无外部依赖）。

用法：
    .venv/bin/python scripts/platform_check.py [--trace-dir traces]

检查项：
1. deploy/ 下所有 YAML 可解析，且关键结构存在（scrape_configs / groups / probes）；
2. 告警与记录规则里引用的指标名都能在 server/metrics.render() 的输出里找到
   （记录规则自身命名 job:* 除外）；
3. /metrics 端点返回 Prometheus 文本格式，且含 semconv 要求的关键指标族；
4. traces/ 目录可被 otel_export 全量转换（spanId 唯一、parent 可解析）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402  (PyYAML 在 requirements-dev.txt)

from server import metrics, otel_export  # noqa: E402

DEPLOY = ROOT / "deploy"
REQUIRED_FAMILIES = [
    "renewal_chat_requests_total",
    "renewal_errors_total",
    "renewal_chat_duration_seconds",
    "renewal_node_duration_seconds",
    "gen_ai_client_inference_duration_seconds",
    "gen_ai_client_inference_usage_input_tokens_total",
    "gen_ai_client_inference_usage_output_tokens_total",
    "gen_ai_invoke_agent_duration_seconds",
    "gen_ai_invoke_agent_tool_calls",
    "gen_ai_invoke_agent_inference_calls",
    "gen_ai_retrieval_duration_seconds",
    "gen_ai_execute_tool_duration_seconds",
]
def _fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"  ✗ {msg}")


def check_yaml(errors: list[str]) -> None:
    print("[1/4] 部署 YAML 结构")
    files = sorted(DEPLOY.rglob("*.yml")) + sorted(DEPLOY.rglob("*.yaml"))
    if not files:
        _fail("deploy/ 下没有 YAML 文件", errors)
        return
    for path in files:
        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
        if not docs:
            _fail(f"{path.relative_to(ROOT)} 解析为空", errors)
        print(f"  ✓ {path.relative_to(ROOT)}（{len(docs)} 个文档）")

    prom = yaml.safe_load((DEPLOY / "prometheus/prometheus.yml").read_text("utf-8"))
    jobs = {j["job_name"] for j in prom.get("scrape_configs", [])}
    if "renewal-assistant" not in jobs:
        _fail("prometheus.yml 缺 renewal-assistant job", errors)
    if "rule_files" not in prom:
        _fail("prometheus.yml 未引用规则文件", errors)

    dep = next(d for d in yaml.safe_load_all(
        (DEPLOY / "k8s/deployment.yaml").read_text("utf-8")) if d)
    containers = {c["name"]: c for c in dep["spec"]["template"]["spec"]["containers"]}
    if "app" not in containers:
        _fail("k8s Deployment 缺 app 容器", errors)
    app = containers.get("app", {})
    for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
        if probe not in app:
            _fail(f"k8s Deployment 缺 {probe}", errors)
        elif app[probe].get("httpGet", {}).get("path") != "/health":
            _fail(f"{probe} 未指向 /health", errors)
    if "trace-export" not in containers:
        _fail("k8s Deployment 缺 trace-export sidecar（轨迹无法出集群）", errors)
    for c in containers.values():
        if c.get("securityContext", {}).get("runAsNonRoot") is None and \
                c.get("securityContext", {}).get("allowPrivilegeEscalation") is not False:
            _fail(f"容器 {c['name']} 未限制提权", errors)


def check_rules_against_metrics(errors: list[str]) -> None:
    print("[2/4] 规则引用的指标确实被暴露")
    exposed = {ln.split()[2] for ln in metrics.render().splitlines()
               if ln.startswith("# TYPE")}
    # 直方图在 PromQL 里以 _bucket/_count/_sum 出现
    exposed |= {f"{n}_bucket" for n in exposed} | {f"{n}_count" for n in exposed}
    exposed |= {f"{n}_sum" for n in exposed}
    rules_doc = yaml.safe_load(
        (DEPLOY / "prometheus/rules/renewal.yml").read_text("utf-8"))
    recorded = set()
    for group in rules_doc["groups"]:
        for rule in group["rules"]:
            if "record" in rule:
                recorded.add(rule["record"])
    checked = 0
    for group in rules_doc["groups"]:
        for rule in group["rules"]:
            expr = rule.get("expr", "")
            if not expr.strip():
                _fail(f"规则 {rule.get('alert') or rule.get('record')} 表达式为空", errors)
                continue
            tokens = set(re.findall(r"[a-zA-Z_:][a-zA-Z0-9_:]*", expr))
            unknown = {
                t for t in tokens
                if t.startswith(("renewal_", "gen_ai_"))
                and t not in exposed and t not in recorded
            }
            checked += 1
            if unknown:
                _fail(f"{rule.get('alert') or rule.get('record')} 引用未暴露指标 {sorted(unknown)}",
                      errors)
    print(f"  ✓ {checked} 条规则表达式全部指向已暴露指标")


def check_metrics_endpoint(errors: list[str]) -> None:
    print("[3/4] /metrics 暴露面")
    from fastapi.testclient import TestClient

    from server.app import app
    body = TestClient(app).get("/metrics")
    if body.status_code != 200:
        _fail("/metrics 非 200", errors)
        return
    if not body.headers["content-type"].startswith("text/plain"):
        _fail("/metrics Content-Type 非法（Prometheus 3.0 起抓取会失败）", errors)
    text = body.text
    for fam in REQUIRED_FAMILIES:
        if f"# TYPE {fam} " not in text:
            _fail(f"/metrics 缺指标族 {fam}", errors)
    if re.search(r'\{(?:[^}]*\b(?:trace_id|session_id|owner_id)=)', text):
        _fail("/metrics 出现高基数标签（trace/session/owner）", errors)
    print(f"  ✓ {len(REQUIRED_FAMILIES)} 个必备指标族齐全，无高基数标签")


def check_trace_export(errors: list[str], trace_dir: Path) -> None:
    print("[4/4] 轨迹 → OTLP 转换")
    files = sorted(trace_dir.glob("*.jsonl"))
    if not files:
        print("  - traces/ 为空，跳过（新环境正常）")
        return
    traces, stats = otel_export.collect(trace_dir)
    for trace_hex, spans in traces:
        ids = {s.span_id for s in spans}
        if len(ids) != len(spans):
            _fail(f"{trace_hex} 内 spanId 重复", errors)
        for s in spans[1:]:
            if s.parent_id not in ids:
                _fail(f"{trace_hex} 子 span parent 不可解析", errors)
                break
    payload = otel_export.to_otlp_payload(traces[:2])
    if not payload["resourceSpans"]:
        _fail("OTLP 载荷为空 envelope", errors)
    print(f"  ✓ {stats['files']} 条轨迹 → {stats['spans']} spans"
          f"（error span {stats['errors']}）")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="平台工程域部署/观测自检")
    ap.add_argument("--trace-dir", default=str(ROOT / "traces"))
    args = ap.parse_args(argv)
    errors: list[str] = []
    check_yaml(errors)
    check_rules_against_metrics(errors)
    check_metrics_endpoint(errors)
    check_trace_export(errors, Path(args.trace_dir))
    if errors:
        print(f"\n失败：{len(errors)} 项")
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
