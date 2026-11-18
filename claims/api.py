"""F4：理赔域 HTTP/SSE 入口（**不碰 `server/`**，只调用 F2 的 `ClaimGraph`）。

设计约束（逐条对应任务书与已定契约）
------------------------------------
1. **不新增 record_type / 不新增 SSE event 名**（D-08 / SPEC §6.2）：
   SSE 的 `event:` 直接取轨迹行的 `record_type`（11 种白名单内），理赔语义仍在
   `data.event.kind`（`claims.*` 前缀）。
2. **错误码只用 SPEC §5 的 14 项**（`claims/state.py::ErrorCode`），HTTP 状态按 SPEC
   表格映射；不自造 code。
3. **运行前提硬断言**（SPEC §8.0 / D-22）：默认要求 `deepagents` 可导入；`.venv` 下
   会直接拒起（否则是"假绿"）。允许用 `CLAIMS_ALLOW_RULES_ONLY=1` 显式降级跑
   （仅用于演示规则模式，启动横幅会标 `degraded=true`）。
4. **知识侧汇合**（D-21）：`wiki-check` 走 `claims.wiki_retrieve.retrieve()`（语料根是
   `claims.config.wiki_dir()`，**不读续保 `wiki/`**），并把命中回填成一条
   `record_type="retrieval"` 的轨迹行；检索拒答/空语料**显式记录**，不静默跳过。
5. **轨迹落点**（C0 基线 §4）：`claims.config.trace_dir()`（默认 `traces-claims/`），
   本模块不写 `traces/`。

外部依据（先检索后动手，详见 `docs/log/step-f4.md` §2）
- S1 FastAPI 官方 SSE 教程（Context7 取回）：`fastapi.sse.EventSourceResponse` +
  `ServerSentEvent`（`comment` 即 keep-alive ping）；本机实测 `fastapi 0.162.4` 可用。
- S2 LangGraph 官方 interrupts 文档（Context7 取回）：`Command(resume=...)` 必须用**同一
  thread_id**，且被中断节点会从函数开头重跑。
- S3 sse-starlette README：客户端断连检测、ping/keep-alive、`X-Accel-Buffering: no`。
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from collections.abc import AsyncIterable
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from claims import config
from claims import wiki_retrieve as wr
from claims.graph import ClaimGraph, ReviewDecision
from claims.state import ErrorCode, Status
from claims.tools import logic
from server import metrics
from server.trace import read_trace

#: SPEC §5 错误码 → HTTP 状态（唯一映射表，禁止在路由里散写 magic number）
ERROR_HTTP: dict[str, int] = {
    ErrorCode.CLAIM_FIELD_INVALID: 400,
    ErrorCode.CLAIM_DUPLICATE: 409,
    ErrorCode.POLICY_NOT_FOUND: 404,
    ErrorCode.CLAIM_STATE_INVALID: 409,
    ErrorCode.MATERIAL_MISSING: 422,
    ErrorCode.ANALYSIS_SCHEMA_INVALID: 502,
    ErrorCode.ANALYSIS_UNAVAILABLE: 200,  # 降级不报错（SPEC §9），靠事件体现
    ErrorCode.REVIEW_DECISION_INVALID: 422,
    ErrorCode.AMOUNT_EXCEED_LIMIT: 409,
    ErrorCode.PAYMENT_KEY_MISSING: 500,
    ErrorCode.PAYMENT_REJECTED: 402,
    ErrorCode.PAYMENT_UNKNOWN: 202,
    ErrorCode.PAYMENT_AMOUNT_MISMATCH: 500,
    ErrorCode.TOOL_FORBIDDEN: 403,
}

#: 事件顺序里"最先命中"的错误码决定 HTTP 状态（同一条错误可能来自多个节点）
_HTTP_PRIORITY = (
    ErrorCode.CLAIM_FIELD_INVALID,
    ErrorCode.CLAIM_DUPLICATE,
    ErrorCode.TOOL_FORBIDDEN,
    ErrorCode.POLICY_NOT_FOUND,
    ErrorCode.CLAIM_STATE_INVALID,
    ErrorCode.REVIEW_DECISION_INVALID,
    ErrorCode.MATERIAL_MISSING,
    ErrorCode.ANALYSIS_SCHEMA_INVALID,
    ErrorCode.PAYMENT_REJECTED,
    ErrorCode.PAYMENT_KEY_MISSING,
    ErrorCode.PAYMENT_UNKNOWN,
)


# --------------------------------------------------------------------------- #
# 前置断言（任务书 A1–A3）
# --------------------------------------------------------------------------- #
def _deepagents_available() -> bool:
    return importlib.util.find_spec("deepagents") is not None


def preflight(*, strict: bool | None = None) -> dict[str, Any]:
    """启动自检：解释器 / wiki 语料 / 轨迹隔离。返回结构化报告（不抛异常）。"""
    allow_rules = os.environ.get("CLAIMS_ALLOW_RULES_ONLY", "") == "1"
    if strict is None:
        strict = not allow_rules

    has_da = _deepagents_available()
    searcher = wr.get_searcher()          # 空语料会抛 WikiCorpusEmpty（显式失败，D-21）
    trace_dir = config.trace_dir()
    return {
        "python": os.sys.executable,
        "deepagents": has_da,
        "rules_only_degraded": (not has_da) or (not strict and not has_da),
        "strict": strict,
        "wiki_dir": str(config.wiki_dir()),
        "wiki_entries": len(searcher.entries),
        "wiki_available": bool(searcher.available),
        "trace_dir": str(trace_dir),
        "trace_dir_isolated": trace_dir.name == "traces-claims",
        "checkpoint_db": str(config.checkpoint_db()),
        "deepagents_enabled": config.deepagents_enabled(),
    }


def assert_preflight(*, strict: bool | None = None) -> dict[str, Any]:
    """硬断言：不满足就抛，绝不允许"假绿"起服务。"""
    report = preflight(strict=strict)
    problems: list[str] = []
    if report["strict"] and not report["deepagents"]:
        problems.append(
            "deepagents 不可导入（D-22）：请用 .venv-claims/bin/python 启动；"
            "若只要跑规则模式，请显式设 CLAIMS_ALLOW_RULES_ONLY=1"
        )
    if report["wiki_entries"] <= 0:
        problems.append(f"wiki 语料为空：{report['wiki_dir']}（D-21 拒绝静默空检索）")
    if not report["trace_dir_isolated"]:
        problems.append(f"轨迹目录不是 traces-claims：{report['trace_dir']}（C0 基线 §4）")
    if problems:
        raise RuntimeError("；".join(problems))
    return report


# --------------------------------------------------------------------------- #
# 序列化 / 状态整形
# --------------------------------------------------------------------------- #
def _jsonable(value: Any) -> Any:
    """把 LangGraph 返回值（可能含 Interrupt / Pydantic）压成可 JSON 化的结构。"""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items() if not str(k).startswith("__")}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _interrupt_of(out: dict[str, Any]) -> dict[str, Any] | None:
    raw = out.get("__interrupt__")
    if not raw:
        return None
    first = raw[0] if isinstance(raw, (list, tuple)) else raw
    payload = getattr(first, "value", first)
    return _jsonable(payload) if payload is not None else None


def _error_codes(out: dict[str, Any]) -> list[str]:
    return [str(e.get("code")) for e in (out.get("errors") or []) if isinstance(e, dict)]


def _http_status_for(out: dict[str, Any]) -> int:
    codes = set(_error_codes(out))
    for code in _HTTP_PRIORITY:
        if code in codes:
            return ERROR_HTTP[code]
    return 200


def _state_view(values: dict[str, Any]) -> dict[str, Any]:
    """对外状态视图：只暴露契约字段，不泄漏内部对象。"""
    view = {
        "claim_id": values.get("claim_id"),
        "status": values.get("status"),
        "synthetic": values.get("synthetic"),
        "payable_amount": (values.get("assessment") or {}).get("payable_amount"),
        "payment_key": values.get("payment_key"),
        "payment_id": values.get("payment_id"),
        "approval_version": values.get("approval_version"),
        "approval_mode": values.get("approval_mode"),
        "missing_docs": values.get("missing_docs") or [],
        "flags": values.get("flags") or [],
        "analysis_degraded": values.get("analysis_degraded"),
        "analysis_cached": values.get("analysis_cached"),
        "errors": _jsonable(values.get("errors") or []),
        "receipt": _jsonable(values.get("payment_receipt") or {}),
    }
    if values.get("terminal"):
        view["terminal"] = True
    return view


# --------------------------------------------------------------------------- #
# 服务层（不含 HTTP，便于 demo / 测试直接调用）
# --------------------------------------------------------------------------- #
class ClaimService:
    """把 `ClaimGraph` 包成"一次一个进程"的服务对象。"""

    def __init__(self, graph: ClaimGraph | None = None) -> None:
        self.graph = graph or ClaimGraph()

    # -- 生命周期 ---------------------------------------------------------
    def close(self) -> None:
        self.graph.close()

    # -- 报案 -------------------------------------------------------------
    @staticmethod
    def claim_id_for(payload: dict[str, Any]) -> str:
        """按 SPEC §3.1 复算 claim_id（确定性，可作 thread_id）。"""
        report = payload.get("report") or {}
        key = logic.idempotency_key(str(payload.get("owner_id", "")),
                                    str(payload.get("policy_no", "")), report)
        return logic.claim_id_for(key, occurred_at=str(report.get("occurred_at", "")))

    def intake(self, payload: dict[str, Any], *, thread_id: str | None = None) -> dict[str, Any]:
        """报案。**thread_id 必须等于 claim_id**（否则 resume 找不到同一个线程）。

        claim_id 是确定性的（SPEC §3.1：`sha256(owner|policy|occurred_at|location)` 前 8 位），
        所以在 invoke 之前就能算出来——不能先随便起个线程名再改名（LangGraph 不支持改 thread_id）。
        """
        thread = thread_id or self.claim_id_for(payload)
        out = self.graph.invoke(payload, thread_id=thread)
        return {
            "thread_id": thread,
            "claim_id": out.get("claim_id"),
            "status": out.get("status"),
            "interrupt": _interrupt_of(out),
            "state": _state_view(out),
            "http_status": _http_status_for(out),
        }

    # -- 审核恢复 ---------------------------------------------------------
    def resume(self, claim_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        try:
            review = ReviewDecision(**decision)
        except Exception as exc:  # pydantic 校验失败 → SPEC REVIEW_DECISION_INVALID
            return {
                "claim_id": claim_id,
                "status": None,
                "error": {"code": ErrorCode.REVIEW_DECISION_INVALID, "message": str(exc)[:300]},
                "http_status": ERROR_HTTP[ErrorCode.REVIEW_DECISION_INVALID],
            }
        if review.decision == "reject" and not review.comment.strip():
            return {
                "claim_id": claim_id,
                "status": None,
                "error": {
                    "code": ErrorCode.REVIEW_DECISION_INVALID,
                    "message": "reject 必须给出 comment（SPEC §4.4）",
                },
                "http_status": ERROR_HTTP[ErrorCode.REVIEW_DECISION_INVALID],
            }
        out = self.graph.resume(review, thread_id=claim_id)
        return {
            "claim_id": out.get("claim_id") or claim_id,
            "status": out.get("status"),
            "interrupt": _interrupt_of(out),
            "state": _state_view(out),
            "http_status": _http_status_for(out),
        }

    # -- 状态快照 ---------------------------------------------------------
    def snapshot(self, claim_id: str) -> dict[str, Any]:
        snap = self.graph.state(thread_id=claim_id)
        values = dict(snap.values or {})
        return {
            "claim_id": claim_id,
            "next": list(snap.next or ()),
            "state": _state_view(values),
        }

    # -- 轨迹（SSE 数据源）------------------------------------------------
    def events(self, claim_id: str) -> list[dict[str, Any]]:
        rows = read_trace(claim_id, trace_dir=config.trace_dir())
        return list(rows or [])

    # -- 知识侧汇合（D）---------------------------------------------------
    def wiki_check(
        self,
        claim_id: str,
        query: str,
        *,
        top_k: int = 3,
        section_hint: str | None = None,
    ) -> dict[str, Any]:
        """检索理赔 LLM-Wiki 并**把命中写进轨迹**（record_type=retrieval，白名单内）。"""
        started = time.monotonic()
        result = wr.retrieve(query, top_k=top_k)
        elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        hits = result.get("hits") or []
        row_payload = {
            "kind": "claims.wiki_retrieved",
            "query": query,
            "wiki_dir": str(config.wiki_dir()),
            "hits": [
                {
                    "wiki_id": h.get("wiki_id"),
                    "title": h.get("title"),
                    "anchor": h.get("anchor"),
                    "span": h.get("span"),
                    "verbatim": h.get("verbatim"),
                    "citations_ok": h.get("citations_ok"),
                    "citations_strict": h.get("citations_strict"),
                }
                for h in hits
            ],
            "hit_ids": [h.get("wiki_id") for h in hits],
            "citations": result.get("citations"),
            "grounding_rate": result.get("grounding_rate"),
            "best_term_support": result.get("best_term_support"),
            # 拒答/空语料必须显式落痕（不得静默跳过）
            "abstained": bool(result.get("abstained")),
            "degraded": bool(not hits),
        }
        rec = self.graph.recorder({"claim_id": claim_id}, claim_id)
        rec.record("retrieval", node="verify_wiki", event=row_payload, latency_ms=elapsed_ms)
        return {
            "claim_id": claim_id,
            "query": query,
            "section_hint": section_hint,
            "result": {
                "corpus": result.get("corpus"),
                "hits": hits,
                "citations": result.get("citations"),
                "grounding_rate": result.get("grounding_rate"),
                "abstained": result.get("abstained"),
            },
            "trace_row": {"record_type": "retrieval", "node": "verify_wiki", **row_payload},
        }

    # -- 指标 -------------------------------------------------------------
    @staticmethod
    def metrics_text() -> str:
        return metrics.render()


# --------------------------------------------------------------------------- #
# HTTP 模型
# --------------------------------------------------------------------------- #
class IntakeBody(BaseModel):
    owner_id: str = Field(min_length=1)
    policy_no: str = Field(min_length=1)
    report: dict[str, Any]
    documents: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str = "sess-claims"


class ResumeBody(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str = ""
    reviewer_id: str = "RV-0001"


class WikiCheckBody(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = 3
    section_hint: str | None = None


# --------------------------------------------------------------------------- #
# 应用装配
# --------------------------------------------------------------------------- #
def create_app(service: ClaimService | None = None, *, strict: bool | None = None) -> FastAPI:
    app = FastAPI(title="claims-api（模拟理赔 · 合成数据）", version="0.1.0")
    svc = service or ClaimService()
    report = assert_preflight(strict=strict)
    app.state.service = svc
    app.state.preflight = report

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "preflight": app.state.preflight}

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        return Response(svc.metrics_text(), media_type="text/plain; version=0.0.4")

    @app.post("/claims/intake")
    def intake(body: IntakeBody) -> Response:
        out = svc.intake(body.model_dump())
        return Response(
            json.dumps(out, ensure_ascii=False), status_code=int(out["http_status"]),
            media_type="application/json",
        )

    @app.get("/claims/{claim_id}")
    def get_claim(claim_id: str) -> dict[str, Any]:
        return svc.snapshot(claim_id)

    @app.post("/claims/{claim_id}/resume")
    def resume(claim_id: str, body: ResumeBody) -> Response:
        out = svc.resume(claim_id, body.model_dump())
        return Response(
            json.dumps(out, ensure_ascii=False), status_code=int(out["http_status"]),
            media_type="application/json",
        )

    @app.post("/claims/{claim_id}/wiki-check")
    def wiki_check(claim_id: str, body: WikiCheckBody) -> dict[str, Any]:
        return svc.wiki_check(claim_id, body.query, top_k=body.top_k, section_hint=body.section_hint)

    @app.get("/claims/{claim_id}/events", response_class=EventSourceResponse)
    async def events(
        claim_id: str,
        follow: int = Query(0, ge=0, le=30, description=">0 时在未终态的情况下轮询追加新行（秒）"),
    ) -> AsyncIterable[ServerSentEvent]:
        """SSE：先重放已落盘轨迹，`follow>0` 且未终态时继续轮询。

        说明（诚实边界）：这是"重放 + 短跟随"，不是常驻订阅；
        `event:` 取轨迹行的 `record_type`（11 种白名单），语义在 `data.event.kind`。
        """
        emitted = 0
        deadline = time.monotonic() + follow
        while True:
            rows = svc.events(claim_id)
            for row in rows[emitted:]:
                emitted += 1
                yield ServerSentEvent(
                    event=str(row.get("record_type") or "message"),
                    id=str(row.get("seq")),
                    data=row,
                )
            snapshot = svc.snapshot(claim_id)
            terminal = snapshot["state"].get("status") in Status.TERMINAL
            if terminal or time.monotonic() >= deadline:
                yield ServerSentEvent(
                    event="done",
                    data={
                        "claim_id": claim_id,
                        "status": snapshot["state"].get("status"),
                        "next": snapshot["next"],
                        "events": emitted,
                        "synthetic": True,
                    },
                )
                return
            # keep-alive（S3：comment 行用于防代理/LB 超时）
            yield ServerSentEvent(comment=f"keep-alive {int(time.time())}")
            await _sleep(0.2)

    @app.on_event("shutdown")
    def _shutdown() -> None:  # pragma: no cover - 仅在真实 uvicorn 生命周期触发
        svc.close()

    return app


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("CLAIMS_API_PORT", "8130")))
