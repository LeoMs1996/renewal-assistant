"""R3 evidence probe — verify LangGraph 1.2.20 API surface + SqliteSaver restart semantics.

Run with the project venv:
    renewal-assistant/.venv/bin/python insurance-agent/docs/research/evidence/probe_langgraph_api.py introspect
    renewal-assistant/.venv/bin/python insurance-agent/docs/research/evidence/probe_langgraph_api.py phase1   # dispatch, pause at interrupt
    renewal-assistant/.venv/bin/python insurance-agent/docs/research/evidence/probe_langgraph_api.py phase2   # NEW process: resume from sqlite

Nothing here is production code; it exists only to produce first-hand evidence for
docs/research/framework-baseline.md.
"""

from __future__ import annotations

import inspect
import json
import os
import sqlite3
import sys
from importlib.metadata import version
from typing import TypedDict

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe-checkpoints.sqlite")
THREAD = "claim-2026-0001"


class ClaimState(TypedDict, total=False):
    claim_id: str
    policy_no: str
    evidence_summary: str
    approved: bool
    payment_idempotency_key: str
    paid: bool
    trace: list[str]


def build_graph(checkpointer):
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    def intake(state: ClaimState):
        # side effect marker: proves whether a node re-runs after resume
        trace = list(state.get("trace", [])) + ["intake"]
        return {"trace": trace, "claim_id": state.get("claim_id", "C1")}

    def review(state: ClaimState):
        # node re-runs from the top on resume -> intake must stay untouched
        decision = interrupt(
            {
                "question": "Approve claim payout?",
                "claim_id": state.get("claim_id"),
                "evidence_summary": state.get("evidence_summary", ""),
            }
        )
        return {"approved": bool(decision), "trace": list(state["trace"]) + ["review"]}

    def route(state: ClaimState):
        return "pay" if state.get("approved") else "reject"

    def pay(state: ClaimState):
        key = list(state["trace"])  # placeholder to avoid unused warning
        del key
        return {
            "paid": True,
            "trace": list(state["trace"]) + ["pay"],
        }

    def reject(state: ClaimState):
        return {"paid": False, "trace": list(state["trace"]) + ["reject"]}

    return (
        StateGraph(ClaimState)
        .add_node("intake", intake)
        .add_node("review", review)
        .add_node("pay", pay)
        .add_node("reject", reject)
        .add_edge(START, "intake")
        .add_edge("intake", "review")
        .add_conditional_edges("review", route, {"pay": "pay", "reject": "reject"})
        .add_edge("pay", END)
        .add_edge("reject", END)
        .compile(checkpointer=checkpointer)
    )


def _sqlite_saver():
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(DB, check_same_thread=False)
    return SqliteSaver(conn)


def introspect() -> None:
    import langgraph
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import StateGraph
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.types import Command, Interrupt, RetryPolicy, TimeoutPolicy, interrupt

    def sig(obj, name):
        try:
            print(f"{name}{inspect.signature(obj)}")
        except Exception as exc:  # pragma: no cover
            print(f"{name} <no signature: {exc}>")

    print("== versions")
    for pkg in (
        "langgraph",
        "langgraph-checkpoint",
        "langgraph-checkpoint-sqlite",
        "langgraph-prebuilt",
        "langchain-core",
        "aiosqlite",
    ):
        try:
            print(f"  {pkg}=={version(pkg)}")
        except Exception:
            print(f"  {pkg}=<not installed>")
    print(f"  langgraph.__file__={langgraph.__file__}")

    print("== signatures")
    sig(StateGraph.__init__, "StateGraph.__init__")
    sig(StateGraph.add_node, "StateGraph.add_node")
    sig(StateGraph.add_conditional_edges, "StateGraph.add_conditional_edges")
    sig(StateGraph.add_edge, "StateGraph.add_edge")
    sig(StateGraph.compile, "StateGraph.compile")
    sig(interrupt, "interrupt")
    sig(Command, "Command")
    sig(SqliteSaver.__init__, "SqliteSaver.__init__")
    sig(RetryPolicy, "RetryPolicy")
    sig(TimeoutPolicy, "TimeoutPolicy")
    from langgraph.graph.state import CompiledStateGraph as CSG

    for method in ("invoke", "stream", "get_state", "update_state", "get_state_history"):
        if hasattr(CSG, method):
            sig(getattr(CSG, method), f"CompiledStateGraph.{method}")
    print(f"  Interrupt fields: {getattr(Interrupt, '__annotations__', {})}")

    print("== interrupt() docstring head")
    print("  " + (inspect.getdoc(interrupt) or "").split("\n\n")[0].replace("\n", " "))


def phase1() -> None:
    from langgraph.types import Command  # noqa: F401  (documented import surface)

    cp = _sqlite_saver()
    graph = build_graph(cp)
    cfg = {"configurable": {"thread_id": THREAD}}
    result = graph.invoke(
        {"claim_id": "C1", "policy_no": "P-1", "evidence_summary": "crash report + photos"},
        cfg,
        durability="sync",
    )
    pending = result.get("__interrupt__")
    print("phase1 interrupts:", [(type(i).__name__, i.id, i.value) for i in pending or []])
    snap = graph.get_state(cfg)
    print("phase1 next:", snap.next)
    print("phase1 state:", json.dumps(dict(snap.values), ensure_ascii=False))
    print("phase1 checkpoint_id:", snap.config["configurable"].get("checkpoint_id"))
    print("DB size:", os.path.getsize(DB))


def phase2() -> None:
    from langgraph.types import Command

    cp = _sqlite_saver()
    graph = build_graph(cp)
    cfg = {"configurable": {"thread_id": THREAD}}
    before = graph.get_state(cfg)
    print("phase2 (fresh process) recovered next:", before.next)
    print("phase2 recovered state:", json.dumps(dict(before.values), ensure_ascii=False))
    resumed = graph.invoke(Command(resume=True), cfg, durability="sync")
    print("phase2 final state:", json.dumps(dict(resumed), ensure_ascii=False))
    print("phase2 intake ran again?", dict(resumed).get("trace"))


class LoopState(TypedDict, total=False):
    n: int


def bump(state: LoopState):
    return {"n": state.get("n", 0) + 1}


def loop_forever(state: LoopState):
    return "loop"


def recursion_probe() -> None:
    from langgraph.errors import GraphRecursionError
    from langgraph.graph import START, StateGraph

    g = (
        StateGraph(LoopState)
        .add_node("bump", bump)
        .add_edge(START, "bump")
        .add_conditional_edges("bump", loop_forever, {"loop": "bump"})
        .compile()
    )
    try:
        g.invoke({"n": 0}, {"recursion_limit": 7})
    except GraphRecursionError as exc:
        print("GraphRecursionError OK at recursion_limit=7:", str(exc)[:120])


def durability_probe() -> None:
    """Which durability values does this build accept *with* a checkpointer?"""
    cp = _sqlite_saver()
    graph = build_graph(cp)
    for value in ("sync", "async", "exit", "bogus"):
        try:
            out = graph.invoke(
                {"claim_id": "C-probe", "evidence_summary": ""},
                {"configurable": {"thread_id": f"probe-{value}"}},
                durability=value,  # type: ignore[arg-type]
            )
            print(
                f"durability={value!r}: accepted, interrupts={bool(out.get('__interrupt__'))}"
            )
        except Exception as exc:
            print(f"durability={value!r}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "introspect"
    if cmd == "cleanup" and os.path.exists(DB):
        os.remove(DB)
        print("removed", DB)
    else:
        {
            "introspect": introspect,
            "phase1": phase1,
            "phase2": phase2,
            "recursion": recursion_probe,
            "durability": durability_probe,
        }[cmd]()
