"""理赔域 LangGraph 编排（F2）：报案 → 核验 → 审核 → 支付。

契约：`claims/SPEC-claims.md` v1.0.0；结构说明：`claims/ARCHITECTURE.md`。
实现要点（C5 会逐条验）：
1. 唯一 `interrupt()` 在 `review_gate`，且是节点函数**第一行**、不被 try/except 包裹。
2. 入口 `durability="sync"`、`recursion_limit=40` 走**顶层 config 键**（`invoke`/`resume`）。
3. `reserve_payment_key` 独立节点生成幂等键并先落 checkpoint；`execute_payment` 只读、**不挂 retry_policy**。
4. `execute_payment` 挂 `error_handler`：异常 → `payment_unknown` → `reconcile_payment` 查单（不重发）。
5. 材料分析唯一入口 `run_analysis(docs, *, analyzer_version)`：`DEEPAGENTS_ENABLED=true` 时用 F3 的
   `claims.deep_agents.analyzer.run_analysis`，否则用本域 `rules_analyzer`（同 schema），并记
   `claims.llm_degraded`。
6. 轨迹唯一写入点 = `server.trace.TraceRecorder`（内部已做 PII 脱敏 + 0600）；目录 `traces-claims/`。
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from claims import config
from claims.state import ClaimState, ErrorCode, Event, Status
from claims.tools import logic, rules_analyzer
from claims.tools.payment_gateway import MockPaymentGateway, PaymentRejected
from claims.tools.verify_quote import filter_facts
from server import security
from server.trace import TraceRecorder

ANALYZER_VERSION = rules_analyzer.RULES_VERSION
REQUIRED_DOC_KINDS = logic.REQUIRED_DOC_KINDS


# --------------------------------------------------------------------------- #
# 分析入口（唯一）：F3 实现同名函数，F2 只提供降级实现
# --------------------------------------------------------------------------- #
#: 最近一次降级的**原因**（不改变 run_analysis 契约签名，用 ContextVar 传递，协程安全）。
_LAST_ANALYSIS_ERROR: ContextVar[dict[str, str] | None] = ContextVar(
    "claims_last_analysis_error", default=None
)


def last_analysis_error() -> dict[str, str] | None:
    """取本次调用的降级原因：`{error_class, error_type, message}`；未降级为 None。"""
    return _LAST_ANALYSIS_ERROR.get()


def run_analysis(docs: list[dict[str, Any]], *, analyzer_version: str = ANALYZER_VERSION) -> dict:
    """材料分析唯一入口。

    签名契约（与 F3 约定，见 `claims/deep_agents/analyzer.py`）::

        def run_analysis(docs: list[dict], *, analyzer_version: str) -> dict

    返回 `materials-analysis/1` 结构（契约 §4.3）。
    """
    _LAST_ANALYSIS_ERROR.set(None)
    if config.deepagents_enabled():
        try:  # F3 的实现可能尚未落地/不可用 → 降级而不是让流程失败
            from claims.deep_agents import analyzer as deep_analyzer  # type: ignore

            result = deep_analyzer.run_analysis(docs, analyzer_version=analyzer_version)
            if isinstance(result, dict) and result.get("schema_version"):
                return result
            raise ValueError("F3 返回结构缺少 schema_version（按 schema 不合规降级）")
        except Exception as exc:  # noqa: BLE001 - 降级是显式决定，但必须留痕
            error_class = type(exc).__name__
            error_type = str(getattr(exc, "error_type", "") or error_class)
            _LAST_ANALYSIS_ERROR.set(
                {"error_class": error_class, "error_type": error_type,
                 "message": str(exc)[:300]}
            )
    else:
        _LAST_ANALYSIS_ERROR.set(
            {"error_class": "", "error_type": "DeepAgentsDisabled",
             "message": "DEEPAGENTS_ENABLED 未开启（默认），按规则模式分析"}
        )
    return rules_analyzer.run_analysis(docs, analyzer_version=analyzer_version)


# --------------------------------------------------------------------------- #
# analysis_key 缓存（契约 §3.2）：同 claim + 同材料 + 同分析器版本 → 复用结果
# --------------------------------------------------------------------------- #
def _analysis_key(claim_id: str, documents: list[dict[str, Any]], *, analyzer_version: str) -> str:
    """`sha256(claim_id | 逐材料 sha256（按 doc_id 排序） | analyzer_version)`。"""
    parts = [claim_id, str(analyzer_version)]
    for doc in sorted(documents, key=lambda d: str(d.get("doc_id", ""))):
        parts.append(f"{doc.get('doc_id', '')}:{logic.sha256_hex(str(doc.get('text', '')))}")
    return logic.sha256_hex("|".join(parts))[:32]


def _cache_path(analysis_key: str) -> Path:
    return config.analysis_cache_dir() / f"{analysis_key}.json"


def _load_analysis_cache(analysis_key: str) -> dict | None:
    path = _cache_path(analysis_key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) and data.get("schema_version") else None


def _store_analysis_cache(analysis_key: str, analysis: dict) -> None:
    try:
        path = _cache_path(analysis_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # 缓存是优化，不是正确性前提


class ReviewDecision(BaseModel):
    """人工审核决策（`interrupt(response_schema=...)`，契约 §4.4）。"""

    decision: Literal["approve", "reject"]
    comment: str = ""
    reviewer_id: str = "RV-0001"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _error(code: str, message: str, node: str) -> dict[str, Any]:
    return {"code": code, "message": message, "node": node, "at": _now()}


# --------------------------------------------------------------------------- #
# 编排装配
# --------------------------------------------------------------------------- #
class ClaimGraph:
    """持有 sqlite checkpointer + 模拟网关 + 轨迹会话缓存。"""

    def __init__(
        self,
        *,
        gateway: MockPaymentGateway | None = None,
        checkpoint_db: Path | str | None = None,
        trace_dir: Path | str | None = None,
    ) -> None:
        config.ensure_dirs()
        self.gateway = gateway or MockPaymentGateway()
        self.db_path = Path(checkpoint_db or config.checkpoint_db())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_dir = Path(trace_dir or config.trace_dir())
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.checkpointer = SqliteSaver(self._conn)
        self._recorders: dict[str, TraceRecorder] = {}
        self.graph = self._build()

    # -- 轨迹（唯一写入点：TraceRecorder 内部脱敏） -------------------------
    def recorder(self, state: ClaimState, claim_id: str | None = None) -> TraceRecorder:
        # I4-a：intake 阶段 state 里还没有 claim_id，必须由调用方显式传入，
        # 否则新案首行会落到 unknown.jsonl（轨迹无法完整重放）。
        claim_id = claim_id or state.get("claim_id") or "unknown"
        rec = self._recorders.get(claim_id)
        if rec is None:
            rec = TraceRecorder(
                trace_id=claim_id,
                session_id=state.get("session_id") or "sess-claims",
                trace_dir=self.trace_dir,
            )
            try:  # 跨进程 resume 时接着已有行数续号，避免 seq 重置
                existing = sum(1 for _ in rec.path.open(encoding="utf-8"))
                rec._seq = existing  # noqa: SLF001 - TraceRecorder 未暴露 setter
            except OSError:
                pass
            self._recorders[claim_id] = rec
        return rec

    def record(
        self, state: ClaimState, event: str, *, node: str, claim_id: str | None = None, **kw: Any
    ) -> None:
        """所有轨迹事件统一入口：event 必须落在 `claims.*` 命名空间（契约 §6）。"""
        if not event.startswith("claims."):
            raise ValueError(f"非法 event：{event}（必须以 claims. 开头）")
        self.recorder(state, claim_id).record(
            "node_start", node=node, event={"kind": event, **kw}
        )

    # -- 节点包装：成功执行后补一条 node_end（含耗时） --------------------- #
    def _wrap(self, name: str, fn):
        """包一层：成功执行后记 `node_end`（latency_ms）。

        为什么必须记 `node_end`：`server.metrics.observe_record()` 只对
        `node_end` / `tool_call` / `tool_result` / `llm_response` / `error` 这几类
        入指标；F2 早期只写 `node_start`，导致理赔域在 `/metrics` 里**一条都没有**
        （X1 D1 判定的"未接入"就是这个）。异常/中断路径不补 node_end（那不是完成）。
        """

        def wrapped(state: ClaimState):
            started = time.monotonic()
            result = fn(state)
            # node_end 要用**节点执行后**的 claim_id（intake 会在这里第一次产出 claim_id）
            merged = dict(state)
            if isinstance(result, dict) and result.get("claim_id"):
                merged["claim_id"] = result["claim_id"]
            self.recorder(merged).record(
                "node_end", node=name, latency_ms=(time.monotonic() - started) * 1000.0
            )
            return result

        wrapped.__name__ = f"wrapped_{name}"
        return wrapped

    # -- 节点 --------------------------------------------------------------- #
    def intake(self, state: ClaimState) -> ClaimState:
        node = "intake"
        errors = list(state.get("errors", []))
        report = dict(state.get("report") or {})
        owner_id = str(state.get("owner_id", ""))
        policy_no = str(state.get("policy_no", ""))

        # I4-a：**先算 claim_id，再记轨迹**——否则首行事件会落到 unknown.jsonl，
        # 轨迹就无法按 claim 完整重放（CLM-20）。
        key = logic.idempotency_key(owner_id, policy_no, report)
        claim_id = logic.claim_id_for(key, occurred_at=str(report.get("occurred_at", "")))
        doc_ids = [str(d.get("doc_id")) for d in state.get("documents", [])]

        problems = logic.validate_report(report)
        if problems:
            errors.append(_error(ErrorCode.CLAIM_FIELD_INVALID, f"报案字段非法：{problems}", node))
            # 无效报案不写入 state.claim_id（保持 state 不变），但轨迹仍落在自己的文件里
            self.record(state, Event.INTAKE_INVALID, node=node,
                        claim_id=claim_id, problems=problems)
            # 也回填 claim_id：轨迹要按 claim 归档（node_end 包装器同样要用它）
            return {
                "claim_id": claim_id,
                "errors": errors,
                "status": Status.INTAKE,
                "synthetic": True,
            }

        # 幂等登记（模拟"幂等键唯一索引"）：同键重复提交 → 同 claim_id + CLAIM_DUPLICATE
        marker = config.idempotency_dir() / f"{key}.json"
        if marker.exists() and not state.get("claim_id"):
            # 只有**全新线程**重复提交才算重复；同 thread 补件续跑不算
            errors.append(_error(ErrorCode.CLAIM_DUPLICATE, f"重复报案（幂等键 {key[:12]}）", node))
            self.record(state, Event.INTAKE_DUPLICATE, node=node, claim_id=claim_id)
            return {"claim_id": claim_id, "status": Status.INTAKE, "errors": errors,
                    "synthetic": True, "doc_ids": doc_ids}
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f'{{"claim_id": "{claim_id}"}}', encoding="utf-8")

        self.record(state, Event.INTAKE_ACCEPTED, node=node, claim_id=claim_id)
        return {
            "claim_id": claim_id,
            "session_id": state.get("session_id") or "sess-claims",
            "status": Status.INTAKE,
            "synthetic": True,
            "errors": errors,
            "doc_ids": doc_ids,
        }

    def verify_precheck(self, state: ClaimState) -> ClaimState:
        node = "verify_precheck"
        errors = list(state.get("errors", []))
        try:
            logic.guard_transition(str(state.get("status")), Status.VERIFYING)
            logic.get_policy(str(state.get("policy_no")), str(state.get("owner_id")))
        except logic.ClaimError as exc:
            errors.append(_error(exc.code, exc.message, node))
            self.record(state, Event.POLICY_REJECTED, node=node, code=exc.code)
            return {"errors": errors, "status": Status.REJECTED}
        return {"status": Status.VERIFYING, "errors": errors}

    def analyze_materials(self, state: ClaimState) -> ClaimState:
        node = "analyze_materials"
        documents = [dict(d) for d in state.get("documents", [])]
        errors = list(state.get("errors", []))

        # 注入检测：材料是**不可信输入**（复用 server.security，不自己写正则）
        signals: list[str] = []
        for doc in documents:
            scan = security.scan_untrusted(str(doc.get("text", "")))
            if scan["level"] != "none":
                signals.extend(scan["signals"])
            doc["text"] = security.wrap_untrusted(str(doc.get("text", "")))

        # 契约 §3.2：analysis_key 缓存（claim + 材料内容 + 分析器版本），避免重复消耗 token
        analysis_key = _analysis_key(
            str(state.get("claim_id", "")), documents, analyzer_version=ANALYZER_VERSION
        )
        cached = _load_analysis_cache(analysis_key)
        if cached is not None:
            analysis = cached
            analysis_cached = True
        else:
            analysis = run_analysis(
                [{"doc_id": d.get("doc_id"), "kind": d.get("kind"), "text": d.get("text", "")}
                 for d in documents],
                analyzer_version=ANALYZER_VERSION,
            )
            analysis_cached = False
            _store_analysis_cache(analysis_key, analysis)
        analysis["claim_id"] = str(state.get("claim_id", ""))

        # 逐字校验：引用不是原材料子串的事实直接丢弃（契约 §4.3 硬约束 2）
        filtered, dropped = filter_facts(analysis, logic.doc_sources(documents))
        flags = logic.flags_for(filtered, documents, dropped)
        degraded = filtered.get("analyzer", {}).get("mode") == "rules_fallback"

        self.record(state, Event.MATERIALS_ANALYZED, node=node, docs=len(documents),
                    dropped=dropped, signals=sorted(set(signals)),
                    analysis_key=analysis_key, cached=analysis_cached)
        if degraded:
            # I4-b：降级必须能回答"为什么"——error_type/error_class 缺一不可（SPEC §9）
            reason = last_analysis_error() or {"error_type": "Unknown", "error_class": "", "message": ""}
            self.record(
                state, Event.LLM_DEGRADED, node=node,
                code=ErrorCode.ANALYSIS_UNAVAILABLE, mode="rules_fallback",
                error_type=reason.get("error_type") or "Unknown",
                error_class=reason.get("error_class") or "",
                message=reason.get("message", ""),
                analysis_key=analysis_key,
            )

        return {
            "materials_analysis": filtered,
            "analysis_degraded": degraded,
            "analysis_cached": analysis_cached,
            "analysis_key": analysis_key,
            "flags": flags,
            "errors": errors,
        }

    def verify_assemble(self, state: ClaimState) -> ClaimState:
        node = "verify_assemble"
        missing = logic.missing_doc_kinds(list(state.get("documents", [])))
        if missing:
            self.record(state, Event.MATERIALS_MISSING, node=node, missing=missing)
            return {"missing_docs": missing, "status": Status.NEED_INFO}
        return {"missing_docs": [], "status": Status.VERIFYING}

    def assess_amount(self, state: ClaimState) -> ClaimState:
        node = "assess_amount"
        assessment = logic.assess_amount(
            state.get("materials_analysis"),
            deductible=config.deductible(),
            max_payable=config.max_payable(),
        )
        self.record(state, Event.ASSESSED, node=node,
                    payable=assessment["payable_amount"], capped=assessment["capped"])
        return {"assessment": assessment}

    def queue_review(self, state: ClaimState) -> ClaimState:
        """进入人工审核队列：把状态置为 review_pending（interrupt 之前必须已落盘）。"""
        self.record(state, Event.REVIEW_REQUESTED, node="queue_review",
                    payable=(state.get("assessment") or {}).get("payable_amount"),
                    flags=list(state.get("flags", [])))
        return {"status": Status.REVIEW_PENDING}

    def auto_approve(self, state: ClaimState) -> ClaimState:
        self.record(state, Event.AUTO_APPROVED, node="auto_approve",
                    payable=(state.get("assessment") or {}).get("payable_amount"))
        return {
            "status": Status.APPROVED,
            "approval_version": 1,
            "approval_mode": "auto",
            "review_decision": "approve",
            "reviewed_at": _now(),
            "reviewer_id": "SYSTEM",
        }

    def review_gate(self, state: ClaimState) -> Command[Literal["reserve_payment_key", "rejected"]]:
        # ① 第一行且唯一一处 interrupt()；**不得**包进 try/except（会吞 GraphInterrupt）
        decision = interrupt(
            {
                "kind": "claim_review",
                "claim_id": state.get("claim_id"),
                "payable_amount": (state.get("assessment") or {}).get("payable_amount"),
                "line_items": (state.get("assessment") or {}).get("line_items", []),
                "flags": state.get("flags", []),
                "missing_docs": state.get("missing_docs", []),
                "allowed_decisions": ["approve", "reject"],
                "synthetic": True,
            },
            response_schema=ReviewDecision,
        )
        if isinstance(decision, dict):  # response_schema 校验后可能是模型实例
            decision = ReviewDecision(**decision)

        approved = decision.decision == "approve"
        self.record(
            state,
            Event.REVIEW_APPROVED if approved else Event.REVIEW_REJECTED,
            node="review_gate",
            reviewer=decision.reviewer_id,
        )
        return Command(
            update={
                "review_decision": decision.decision,
                "review_comment": decision.comment,
                "reviewer_id": decision.reviewer_id,
                "reviewed_at": _now(),
                "approval_version": int(state.get("approval_version") or 0) + 1,
                "approval_mode": "manual",
                "status": Status.APPROVED if approved else Status.REJECTED,
            },
            goto="reserve_payment_key" if approved else "rejected",
        )

    def rejected(self, state: ClaimState) -> ClaimState:
        self.record(state, Event.REVIEW_REJECTED, node="rejected",
                    decision=state.get("review_decision"))
        return {"status": Status.REJECTED}

    def need_info(self, state: ClaimState) -> ClaimState:
        # 材料补充：**不用 interrupt**（多 interrupt 按索引匹配极易错位）；
        # 以 END 挂起，补件后同一 thread 再 invoke 即续跑（契约 §3.2）。
        return {"status": Status.NEED_INFO}

    def reserve_payment_key(self, state: ClaimState) -> ClaimState:
        node = "reserve_payment_key"
        existing = state.get("payment_key")
        if existing:  # 幂等：同 claim 重跑不换键
            return {"payment_key": existing, "status": Status.PAYING}
        assessment = state.get("assessment") or {}
        key = logic.payment_key_for(
            str(state.get("claim_id", "")),
            str(state.get("policy_no", "")),
            float(assessment.get("payable_amount", 0.0)),
            int(state.get("approval_version") or 0),
        )
        self.record(state, Event.PAYMENT_KEY_RESERVED, node=node, payment_key=key)
        return {"payment_key": key, "status": Status.PAYING}

    def execute_payment(self, state: ClaimState) -> ClaimState:
        node = "execute_payment"
        key = state.get("payment_key")
        if not key:  # 未先 reserve 就支付 = 编码错误（CLM-11）
            return {
                "errors": list(state.get("errors", []))
                + [_error(ErrorCode.PAYMENT_KEY_MISSING, "缺少支付幂等键", node)],
                "status": Status.PAYMENT_UNKNOWN,
            }
        assessment = state.get("assessment") or {}
        amount = float(assessment.get("payable_amount", 0.0))

        # 最小权限断言（复用 server.security）：入参 owner 必须等于会话车主
        security.authorize_tool_args(
            "payment_charge",
            {"owner_id": state.get("owner_id")},
            str(state.get("owner_id") or ""),
        )
        tool_started = time.monotonic()
        self.recorder(state).record(
            "tool_call", node=node, event={"kind": "claims.payment_charge", "payment_key": str(key)}
        )
        result = self.gateway.charge(payment_key=str(key), amount=amount, payee="PAYEE-SYNTHETIC")
        self.recorder(state).record(
            "tool_result", node=node, latency_ms=(time.monotonic() - tool_started) * 1000.0,
            output={"payment_id": result.get("payment_id")},
        )
        self.record(state, Event.PAYMENT_CHARGED, node=node,
                    payment_id=result.get("payment_id"),
                    deduplicated=result.get("deduplicated", False))
        return {"payment_id": result.get("payment_id"), "paid_at": _now(), "status": Status.PAID}

    def payment_error_handler(self, state: ClaimState, error: NodeError) -> Command:
        """异常出口：**不重发**，转查单（契约 §3.4 / CLM-12）。"""
        rejected = isinstance(error.error, PaymentRejected)
        code = ErrorCode.PAYMENT_REJECTED if rejected else ErrorCode.PAYMENT_UNKNOWN
        self.record(state, Event.PAYMENT_UNKNOWN, node="execute_payment",
                    code=code, error_type=type(error.error).__name__)
        return Command(
            update={
                "status": Status.PAYMENT_UNKNOWN,
                "errors": list(state.get("errors", []))
                + [_error(code, str(error.error), "execute_payment")],
            },
            goto="reconcile_payment",
        )

    def reconcile_payment(self, state: ClaimState) -> ClaimState:
        node = "reconcile_payment"
        result = self.gateway.query(str(state.get("payment_key") or ""))
        status = result.get("status")
        self.record(state, Event.PAYMENT_RECONCILED, node=node, status=status)
        if status == "success":
            return {"payment_id": result.get("payment_id"), "paid_at": _now(), "status": Status.PAID}
        if status == "failed":
            return {"status": Status.PAYMENT_FAILED}
        return {"status": Status.PAYMENT_UNKNOWN}

    def finalize(self, state: ClaimState) -> ClaimState:
        self.record(state, Event.CLOSED, node="finalize", payment_id=state.get("payment_id"))
        return {
            "status": Status.PAID,
            "payment_receipt": {
                "payment_id": state.get("payment_id"),
                "payment_key": state.get("payment_key"),
                "amount": (state.get("assessment") or {}).get("payable_amount"),
                "synthetic": True,
            },
        }

    # -- 条件边 ------------------------------------------------------------- #
    @staticmethod
    def route_after_intake(state: ClaimState) -> str:
        codes = {e.get("code") for e in state.get("errors", [])}
        if codes & {ErrorCode.CLAIM_FIELD_INVALID, ErrorCode.CLAIM_DUPLICATE}:
            return END
        return "verify_precheck"

    @staticmethod
    def route_after_precheck(state: ClaimState) -> str:
        return "rejected" if state.get("status") == Status.REJECTED else "analyze_materials"

    @staticmethod
    def route_after_assemble(state: ClaimState) -> str:
        return "need_info" if state.get("missing_docs") else "assess_amount"

    @staticmethod
    def route_risk(state: ClaimState) -> str:
        if logic.needs_manual_review(
            state.get("assessment") or {},
            list(state.get("flags", [])),
            threshold=config.amount_review_threshold(),
        ):
            return "queue_review"
        return "auto_approve"

    @staticmethod
    def route_after_payment(state: ClaimState) -> str:
        codes = {e.get("code") for e in state.get("errors", [])}
        if codes & {ErrorCode.PAYMENT_KEY_MISSING}:
            return END
        return "finalize"

    @staticmethod
    def route_after_reconcile(state: ClaimState) -> str:
        return "finalize" if state.get("status") == Status.PAID else END

    # -- 装配 --------------------------------------------------------------- #
    def _build(self):
        builder = StateGraph(ClaimState)
        builder.add_node("intake", self._wrap("intake", self.intake))
        builder.add_node("verify_precheck", self._wrap("verify_precheck", self.verify_precheck))
        builder.add_node("analyze_materials", self._wrap("analyze_materials", self.analyze_materials))
        builder.add_node("verify_assemble", self._wrap("verify_assemble", self.verify_assemble))
        builder.add_node("need_info", self._wrap("need_info", self.need_info))
        builder.add_node("assess_amount", self._wrap("assess_amount", self.assess_amount))
        builder.add_node("queue_review", self._wrap("queue_review", self.queue_review))
        builder.add_node("review_gate", self.review_gate)
        builder.add_node("auto_approve", self._wrap("auto_approve", self.auto_approve))
        builder.add_node("rejected", self._wrap("rejected", self.rejected))
        builder.add_node("reserve_payment_key", self._wrap("reserve_payment_key", self.reserve_payment_key))
        # 支付节点：**不挂 retry_policy**，只挂 error_handler（异常 → 查单，不重发）
        builder.add_node(
            "execute_payment",
            self._wrap("execute_payment", self.execute_payment),
            error_handler=self.payment_error_handler,
        )
        builder.add_node("reconcile_payment", self._wrap("reconcile_payment", self.reconcile_payment))
        builder.add_node("finalize", self._wrap("finalize", self.finalize))

        builder.add_edge(START, "intake")
        builder.add_conditional_edges("intake", self.route_after_intake, ["verify_precheck", END])
        builder.add_conditional_edges(
            "verify_precheck", self.route_after_precheck, ["analyze_materials", "rejected"]
        )
        builder.add_edge("analyze_materials", "verify_assemble")
        builder.add_conditional_edges(
            "verify_assemble", self.route_after_assemble, ["assess_amount", "need_info"]
        )
        builder.add_conditional_edges(
            "assess_amount", self.route_risk, ["queue_review", "auto_approve"]
        )
        builder.add_edge("queue_review", "review_gate")
        builder.add_edge("auto_approve", "reserve_payment_key")
        builder.add_edge("rejected", END)
        builder.add_edge("need_info", END)
        builder.add_edge("reserve_payment_key", "execute_payment")
        builder.add_conditional_edges(
            "execute_payment", self.route_after_payment, ["finalize", END]
        )
        builder.add_edge("reconcile_payment", "finalize")
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self.checkpointer)

    # -- 运行辅助 ----------------------------------------------------------- #
    def _terminal_snapshot(self, thread_id: str) -> dict[str, Any] | None:
        """线程已终态时返回带错误码的快照（**不再进入 intake / 不再推进**）。"""
        snapshot = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        values = dict(snapshot.values or {})
        if values.get("status") in Status.TERMINAL:
            values["errors"] = list(values.get("errors", [])) + [
                _error(ErrorCode.CLAIM_STATE_INVALID,
                       f"线程 {thread_id} 已处于终态 {values.get('status')}，不可再流转", "invoke")
            ]
            values["terminal"] = True
            return values
        return None

    def invoke(self, claim_input: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        """首轮：报案。`durability` 与 `recursion_limit` 都是**顶层 config 键**。

        I6-a：终态线程再 invoke 直接返回既有终态 + `CLAIM_STATE_INVALID`，
        不重新进入 `intake`（否则会重置 status 绕过 ALLOWED_TRANSITIONS 并再次触发支付）。
        """
        terminal = self._terminal_snapshot(thread_id)
        if terminal is not None:
            return terminal
        cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
        return self.graph.invoke(claim_input, cfg, durability="sync")

    def resume(self, decision: ReviewDecision | dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        """人工审核恢复：**必须同一 thread_id**。I6-b：终态/无挂起中断 → `CLAIM_STATE_INVALID`。"""
        terminal = self._terminal_snapshot(thread_id)
        if terminal is not None:
            return terminal
        snapshot = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        if not snapshot.next:
            values = dict(snapshot.values or {})
            values["errors"] = list(values.get("errors", [])) + [
                _error(ErrorCode.CLAIM_STATE_INVALID,
                       f"线程 {thread_id} 没有等待恢复的中断（next 为空）", "resume")
            ]
            return values
        cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
        return self.graph.invoke(Command(resume=decision), cfg, durability="sync")

    def state(self, *, thread_id: str):
        return self.graph.get_state({"configurable": {"thread_id": thread_id}})

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


def build_claim_graph(**kwargs: Any) -> ClaimGraph:
    """构建理赔流程（包装对象持有编译图，便于注入网关/临时目录）。"""
    return ClaimGraph(**kwargs)


def run_claim_turn(
    claim_input: dict[str, Any], *, graph: ClaimGraph | None = None, thread_id: str | None = None
) -> dict[str, Any]:
    """执行一轮理赔流程（供 API 层调用）。"""
    owned = graph or build_claim_graph()
    try:
        return owned.invoke(claim_input, thread_id=thread_id or str(claim_input.get("claim_id") or "claim-tmp"))
    finally:
        if graph is None:
            owned.close()


__all__ = [
    "ANALYZER_VERSION",
    "ClaimGraph",
    "ReviewDecision",
    "build_claim_graph",
    "run_analysis",
    "run_claim_turn",
]
