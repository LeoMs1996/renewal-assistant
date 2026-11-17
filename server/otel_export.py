"""轨迹 JSONL → OpenTelemetry span（OTLP/HTTP JSON 导出，纯标准库）。

为什么需要这一层
----------------
本服务的可观测性长期只有两种形态：JSONL 轨迹（给人看、给 /trace 回放）与
Prometheus 指标（聚合数字）。二者都不是 OTel 数据模型，无法进 Tempo/Jaeger/
任意 OTLP 后端，也无法做跨服务的因果分析（谁等谁、慢在哪一跳）。
本模块把 **已有** 的 387 条历史轨迹就地转换成 OTLP span，不改轨迹格式、
不改 SPEC §5 字段，属于"观测面改造"而非"业务改造"。

检索依据（2026-11-17，逐条 URL + 时间戳见 reviews/platform.md §一）
----------------------------------------------------------------
- OTLP Specification 1.11.1（traces/metrics/logs 均 Stable）：
  * trace 数据默认路径 `/v1/traces`，HTTP POST；JSON 编码必须
    `Content-Type: application/json`；OTLP/HTTP 默认端口 4318。
  * `traceId`/`spanId` 在 JSON 中用十六进制字符串（不是 base64）；
    枚举字段必须用整数（`kind` 用 2 表示 SPAN_KIND_SERVER 这类）；
    int64（含 startTimeUnixNano/endTimeUnixNano）用十进制字符串。
  * 发送侧 SHOULD NOT 构造空 envelope（0 个 span 的载荷不要发）。
- GenAI 语义约定（semantic-conventions-genai 仓库）：
  * client-inference.md：推理 span 名 SHOULD 为 `{gen_ai.operation.name}`（即 `chat`），
    span kind `CLIENT`。
  * gen-ai-agent-spans.md：进程内 agent/工作流 span 名为
    `{gen_ai.operation.name} {gen_ai.agent.name}`、kind `INTERNAL`；LangGraph
    `StateGraph` 属"应用定义控制流"→ operation.name 用 `invoke_workflow`，
    且 `gen_ai.agent.name` MUST 低基数（不得用 "StateGraph" 之类类型名）。
  * execute-tool.md：span 名 `execute_tool {gen_ai.tool.name}`、kind `INTERNAL`。
  * retrieval.md：span 名 `{gen_ai.operation.name}`（即 `retrieval`）、kind `INTERNAL`。
  * gen-ai-spans.md：输入/输出属敏感内容，instrumentation SHOULD NOT 默认采集；
    本模块因此 **不导出** input/output 原文，只导出结构化元数据（节点名、
    文档数、token 数、错误码），PII 留在本地 JSONL（由 /trace 的鉴权与
    归属校验守护）。

口径约定（与 metrics.py 一致）
------------------------------
- 一轮 = 一个 trace = 根 span（`invoke_workflow renewal-assistant`）。
- node_start/node_end → 子 span（`node.<name>`，kind INTERNAL）。
- llm_call/llm_response → `chat` span（kind CLIENT）+ token 属性。
- tool_call/tool_result → `execute_tool <tool>` span（tool 名取图节点名）。
- retrieval → `retrieval` span。
- error 记录 → 落在当前打开的 span 上（status.code=2 + error.type 属性）。

历史轨迹的已知缺口（导出时按降级策略处理，已在报告登记）
--------------------------------------------------
轨迹行里 **没有记录模型名与 provider**，因此导出时的 `gen_ai.request.model` /
`gen_ai.provider.name` 只能取"当前进程配置"（`--provider/--model` 可覆盖），
对历史 GLM 轨迹会打上今天的标签 —— 这是 schema 缺口，修复点在编排层（§5 新增字段），
不在本模块。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import config, metrics

# OTLP SpanKind 枚举（JSON 中必须是整数，见 OTLP 1.11.1 §JSON Protobuf Encoding）。
KIND_INTERNAL = 1
KIND_CLIENT = 3
# OTLP Status.StatusCode：0 UNSET / 1 OK / 2 ERROR。
STATUS_ERROR = 2

AGENT_NAME = metrics.AGENT_NAME
OPERATION_WORKFLOW = "invoke_workflow"
OPERATION_CHAT = "chat"
OPERATION_TOOL = "execute_tool"
OPERATION_RETRIEVAL = "retrieval"

SCOPE_NAME = "renewal-assistant.trace-exporter"
SCOPE_VERSION = "1.0.0"


# ------------------------------------------------------------------ 基础工具
def _epoch_nanos(ts: str) -> int:
    """ISO-8601（可能带时区）→ Unix 纳秒；解析失败退化为 0（不抛，遥测不阻断业务）。"""
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return 0
    if dt.tzinfo is None:  # 无时区按本地时区解释（trace.now_iso 始终带 tz）
        dt = dt.astimezone()
    return int(dt.timestamp()) * 1_000_000_000 + dt.microsecond * 1000


def _hex_id(*parts: object, length: int) -> str:
    """确定性 id：同一 trace/seq 多次导出得到同一 spanId（可重复、可比对）。"""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def trace_id_hex(trace_id: str) -> str:
    return _hex_id("trace", trace_id, length=32)


def _span_id(trace_id: str, key: object) -> str:
    return _hex_id("span", trace_id, key, length=16)


def _attr(key: str, value) -> dict:
    """OTLP JSON AnyValue（int64 用字符串，遵循 proto3 JSON 映射）。"""
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


@dataclass
class Span:
    name: str
    kind: int
    start_ns: int
    end_ns: int
    span_id: str
    parent_id: str | None = None
    attributes: dict = field(default_factory=dict)
    status_code: int = 0
    status_message: str = ""

    def to_otlp(self, trace_id: str) -> dict:
        payload: dict[str, object] = {
            "traceId": trace_id,
            "spanId": self.span_id,
            "name": self.name,
            "kind": self.kind,
            "startTimeUnixNano": str(max(0, self.start_ns)),
            "endTimeUnixNano": str(max(self.start_ns, self.end_ns)),
            "attributes": [_attr(k, v) for k, v in sorted(self.attributes.items())],
        }
        if self.parent_id:
            payload["parentSpanId"] = self.parent_id
        if self.status_code:
            status: dict[str, object] = {"code": self.status_code}
            if self.status_message:
                status["message"] = self.status_message
            payload["status"] = status
        return payload


# ----------------------------------------------------------- 轨迹 → span 树
def build_spans(rows: list[dict], trace_id: str | None = None,
                provider: str | None = None,
                model: str | None = None) -> list[Span]:
    """把一条轨迹的行序列还原成 span 列表（根 span 在首位）。"""
    if not rows:
        return []
    trace_id = trace_id or str(rows[0].get("trace_id") or "unknown")
    provider = provider if provider is not None else metrics.llm_identity()[0]
    model = model if model is not None else metrics.llm_identity()[1]

    root_id = _span_id(trace_id, "root")
    start = _epoch_nanos(rows[0].get("ts", ""))
    end = _epoch_nanos(rows[-1].get("ts", ""))
    spans: list[Span] = []
    root_attrs: dict[str, object] = {
        "gen_ai.operation.name": OPERATION_WORKFLOW,
        "gen_ai.agent.name": AGENT_NAME,
    }
    if provider:
        root_attrs["gen_ai.provider.name"] = provider
    if model:
        root_attrs["gen_ai.request.model"] = model
    root = Span(name=f"{OPERATION_WORKFLOW} {AGENT_NAME}", kind=KIND_INTERNAL,
                start_ns=start, end_ns=end, span_id=root_id,
                attributes=root_attrs)

    # 打开中的节点栈：(node 名, span, start_ns, span_key)
    open_nodes: list[dict] = []
    # 按 node 名跟踪未收口的 llm / tool 调用起点
    open_llm: dict[str, dict] = {}
    open_tool: dict[str, dict] = {}

    def current_parent() -> str:
        return open_nodes[-1]["span"].span_id if open_nodes else root_id

    def row_end_ns(row: dict) -> int:
        """结束记录的时间 = 自身 ts（延迟已在记录时结清，不得再加一次）。"""
        return max(_epoch_nanos(row.get("ts", "")), start)

    def retrieval_start_ns(row: dict) -> tuple[int, bool]:
        """retrieval 起始时刻；返回 (起点 ns, 是否为退化的上界)。

        历史轨迹（2026-11-17 之前）的 retrieval 行没有 latency_ms，此时只能以
        所在节点 node_start 为上界，并在 span 属性里标注 duration.derived。
        """
        end_ns = _epoch_nanos(row.get("ts", ""))
        lat = row.get("latency_ms")
        if isinstance(lat, (int, float)) and lat >= 0:
            return max(0, end_ns - int(lat * 1_000_000)), False
        frame = next((f for f in reversed(open_nodes)
                      if f["node"] == row.get("node")), None)
        return (frame["start"] if frame else end_ns), True
    for idx, row in enumerate(rows, start=1):
        rt = row.get("record_type")
        node = row.get("node") or "unknown"
        ts_ns = _epoch_nanos(row.get("ts", ""))

        if rt == "node_start":
            span = Span(name=f"node.{node}", kind=KIND_INTERNAL, start_ns=ts_ns,
                        end_ns=ts_ns, span_id=_span_id(trace_id, f"node:{idx}"),
                        parent_id=current_parent(),
                        attributes={"renewal.node": node})
            spans.append(span)
            open_nodes.append({"node": node, "span": span, "start": ts_ns})
        elif rt == "node_end":
            frame = next((f for f in reversed(open_nodes) if f["node"] == node), None)
            if frame is not None:
                open_nodes.remove(frame)
                frame["span"].end_ns = row_end_ns(row)
        elif rt == "llm_call":
            open_llm[node] = {"idx": idx, "start": ts_ns,
                             "parent": current_parent()}
        elif rt in ("llm_response", "error") and node in open_llm:
            call = open_llm.pop(node)
            attrs: dict[str, object] = {"gen_ai.operation.name": OPERATION_CHAT}
            if provider:
                attrs["gen_ai.provider.name"] = provider
            if model:
                attrs["gen_ai.request.model"] = model
            ti, to = row.get("tokens_in"), row.get("tokens_out")
            if isinstance(ti, (int, float)):
                attrs["gen_ai.usage.input_tokens"] = int(ti)
            if isinstance(to, (int, float)):
                attrs["gen_ai.usage.output_tokens"] = int(to)
            span = Span(name=OPERATION_CHAT, kind=KIND_CLIENT,
                        start_ns=call["start"], end_ns=row_end_ns(row),
                        span_id=_span_id(trace_id, f"llm:{call['idx']}"),
                        parent_id=call["parent"], attributes=attrs)
            if rt == "error":
                code = str((row.get("error") or {}).get("code") or "unknown")
                span.attributes["error.type"] = code
                span.status_code, span.status_message = STATUS_ERROR, code
            spans.append(span)
        elif rt == "tool_call":
            open_tool[node] = {"idx": idx, "start": ts_ns,
                               "parent": current_parent()}
        elif rt == "tool_result" and node in open_tool:
            call = open_tool.pop(node)
            span = Span(name=f"{OPERATION_TOOL} {node}", kind=KIND_INTERNAL,
                        start_ns=call["start"], end_ns=row_end_ns(row),
                        span_id=_span_id(trace_id, f"tool:{call['idx']}"),
                        parent_id=call["parent"],
                        attributes={"gen_ai.operation.name": OPERATION_TOOL,
                                    "gen_ai.tool.name": node})
            out = row.get("output")
            if isinstance(out, dict) and out.get("error"):
                code = str(out["error"].get("code") or "unknown")
                span.attributes["error.type"] = code
                span.status_code, span.status_message = STATUS_ERROR, code
            spans.append(span)
        elif rt == "retrieval":
            retr_attrs: dict[str, object] = {
                "gen_ai.operation.name": OPERATION_RETRIEVAL}
            out = row.get("output")
            if isinstance(out, list):
                retr_attrs["gen_ai.retrieval.documents.count"] = len(out)
            r_start, derived = retrieval_start_ns(row)
            if derived:
                # 降级标注：该 span 时长是节点上界（历史轨迹无 retrieval.latency_ms）
                retr_attrs["renewal.duration.derived"] = "node_start"
            spans.append(Span(name=OPERATION_RETRIEVAL, kind=KIND_INTERNAL,
                              start_ns=r_start, end_ns=row_end_ns(row),
                              span_id=_span_id(trace_id, f"retrieval:{idx}"),
                              parent_id=current_parent(), attributes=retr_attrs))
        elif rt == "error" and node not in open_llm:
            code = str((row.get("error") or {}).get("code") or "unknown")
            target = open_nodes[-1]["span"] if open_nodes else root
            target.status_code, target.status_message = STATUS_ERROR, code
            target.attributes.setdefault("error.type", code)

    # 未收口的节点（进程被 kill / SSE 断流）按轨迹末行时间封口，避免悬挂 span
    for frame in open_nodes:
        frame["span"].end_ns = max(frame["span"].end_ns, end)

    root.end_ns = max([end] + [s.end_ns for s in spans if s is not root])
    return [root] + spans


# ------------------------------------------------------------- OTLP 载荷
def resource_attributes() -> dict:
    attrs = {"service.name": "renewal-assistant",
             "service.version": "0.2.0-orchestration",
             "deployment.environment.name": config.env("RENEWAL_ENV", "dev") or "dev"}
    return attrs


def to_otlp_payload(traces: list[tuple[str, list[Span]]]) -> dict:
    """traces: [(trace_id_hex, spans)] → ExportTraceServiceRequest（JSON 形态）。"""
    resource_spans = []
    for trace_hex, spans in traces:
        if not spans:  # OTLP：SHOULD NOT 发送空 envelope
            continue
        resource_spans.append({
            "resource": {"attributes": [_attr(k, v) for k, v
                                        in sorted(resource_attributes().items())]},
            "scopeSpans": [{
                "scope": {"name": SCOPE_NAME, "version": SCOPE_VERSION},
                "spans": [s.to_otlp(trace_hex) for s in spans],
            }],
        })
    return {"resourceSpans": resource_spans}


def read_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # 半行（进程被杀）跳过，不因坏行丢整条轨迹
    return rows


def collect(trace_dir: Path, limit: int | None = None,
            provider: str | None = None, model: str | None = None
            ) -> tuple[list[tuple[str, list[Span]]], dict]:
    """把目录下所有轨迹转成 (trace_id_hex, spans)；返回 (数据, 统计)。"""
    paths = sorted(trace_dir.glob("*.jsonl"))
    if limit:
        paths = paths[:limit]
    traces: list[tuple[str, list[Span]]] = []
    stats = {"files": 0, "spans": 0, "empty": 0, "errors": 0}
    for path in paths:
        rows = read_rows(path)
        if not rows:
            stats["empty"] += 1
            continue
        trace_id = str(rows[0].get("trace_id") or path.stem)
        spans = build_spans(rows, trace_id=trace_id, provider=provider, model=model)
        stats["files"] += 1
        stats["spans"] += len(spans)
        stats["errors"] += sum(1 for s in spans if s.status_code == STATUS_ERROR)
        traces.append((trace_id_hex(trace_id), spans))
    return traces, stats


def post_otlp(endpoint: str, payload: dict, timeout: float = 10.0) -> tuple[int, str]:
    """POST 到 {endpoint}/v1/traces（OTLP/HTTP JSON，默认端口 4318）。"""
    url = endpoint.rstrip("/")
    if not url.endswith("/v1/traces"):
        url += "/v1/traces"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read(2048).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(2048).decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)


# --------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="把 traces/*.jsonl 转成 OTel span（OTLP/HTTP JSON）")
    ap.add_argument("--trace-dir", default=str(config.TRACE_DIR))
    ap.add_argument("--out", help="离线模式下输出 JSON 文件路径（- 表示 stdout）")
    ap.add_argument("--endpoint", help="OTLP/HTTP 端点，如 http://127.0.0.1:4318")
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 条轨迹")
    ap.add_argument("--batch", type=int, default=50, help="POST 每批轨迹数")
    ap.add_argument("--provider", default=None, help="覆盖 gen_ai.provider.name")
    ap.add_argument("--model", default=None, help="覆盖 gen_ai.request.model")
    args = ap.parse_args(argv)

    traces, stats = collect(Path(args.trace_dir), limit=args.limit,
                            provider=args.provider, model=args.model)
    if not traces:
        print(f"没有可导出的轨迹（dir={args.trace_dir}）：{stats}", file=sys.stderr)
        return 1

    if args.endpoint:
        sent, failed = 0, 0
        for i in range(0, len(traces), max(1, args.batch)):
            chunk = traces[i:i + max(1, args.batch)]
            code, body = post_otlp(args.endpoint, to_otlp_payload(chunk))
            ok = 200 <= code < 300
            sent += len(chunk) if ok else 0
            failed += 0 if ok else len(chunk)
            print(f"batch {i // max(1, args.batch) + 1}: HTTP {code} {body[:120]}",
                  file=sys.stderr)
        print(f"导出完成：{sent} 条轨迹成功 / {failed} 条失败，"
              f"{stats['spans']} spans", file=sys.stderr)
        return 0 if failed == 0 else 2

    payload = to_otlp_payload(traces)
    text = json.dumps(payload, ensure_ascii=False)
    if args.out in (None, "-"):
        print(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
    print(f"离线导出：{stats['files']} 条轨迹 / {stats['spans']} spans"
          f"（error span {stats['errors']}）→ {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
