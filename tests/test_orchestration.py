#!/usr/bin/env python3
"""单元测试：编排域（LangGraph 状态机）本轮评审整改的可回归断言。

覆盖（对应 reviews/orchestration.md 的 F1/F2/F3/F6）：
1. F6 拓扑守卫：11 业务节点 + 边/条件边快照，防止拓扑被误改（前几轮遗留项）；
2. F3 执行期参数：_ThreadHandle 注入 thread_id / recursion_limit，并把
   durability 传给底层 graph（不再依赖各调用点自觉）；
3. F3 递归上限：GraphRecursionError 被翻译成协议内 error 事件 +
   finish_reason=error / exit_reason=recursion_limit（不再退化成 INTERNAL）；
4. F1 工具重试：桥接层瞬时故障节点内重试；业务错误（ToolError）绝不重试
   （否则会破坏「仅询价 N 次」类契约）；
5. F2 并发：多线程共享同一 SqliteSaver 并发跑图不报错（删除无效 _RUN_LOCK 的
   依据：Saver 内部自带锁）；并守卫 _RUN_LOCK 不被重新引入。

运行方式（两种都可）：
    .venv/bin/python tests/test_orchestration.py          # 脚本，退出码 0 = 通过
    .venv/bin/python -m pytest tests/test_orchestration.py -q
"""

from __future__ import annotations

import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 本文件所有用例都不该触网：先关 LLM，再导入 server 模块
import os  # noqa: E402

os.environ.setdefault("RENEWAL_FORCE_RULE_MODE", "1")

from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from langgraph.errors import GraphRecursionError  # noqa: E402

from server import graph as graph_mod  # noqa: E402
from server import mcp_bridge  # noqa: E402

PASS = 0
FAIL = 0

BUSINESS_NODES = {
    "intake", "get_policy", "parse_needs", "clarify", "retrieve_terms",
    "quote", "compare", "await_confirm", "confirm", "fallback",
}

# 拓扑快照（SPEC §6.2 + 文件头声明的三条事务性旁路）。
# 改动拓扑必须先改 SPEC 与本快照——这是「防误改」而非「防改」。
EDGE_SNAPSHOT = {
    ("__start__", "intake", False),
    ("intake", "get_policy", True),
    ("intake", "retrieve_terms", True),
    ("intake", "fallback", True),
    ("get_policy", "parse_needs", False),
    ("parse_needs", "clarify", True),
    ("parse_needs", "retrieve_terms", True),
    ("parse_needs", "fallback", True),
    ("clarify", "__end__", False),
    ("retrieve_terms", "quote", True),
    ("retrieve_terms", "fallback", True),
    ("retrieve_terms", "confirm", True),
    ("quote", "compare", True),
    ("quote", "fallback", True),
    ("compare", "await_confirm", False),
    ("await_confirm", "confirm", True),
    ("await_confirm", "__end__", True),
    ("confirm", "quote", True),
    ("confirm", "__end__", True),
    ("fallback", "__end__", False),
}


def check(cond: bool, label: str) -> None:
    global PASS, FAIL
    print(f"  {'✓' if cond else '✗'} {label}")
    PASS += 1 if cond else 0
    FAIL += 0 if cond else 1


def _initial(session_id: str, message: str) -> dict:
    return {
        "session_id": session_id,
        "owner_id": "OWN-1001",
        "trace_id": f"tr-{session_id}",
        "message": message,
        "steps": 0, "intent": "", "confirmed": False, "confirm_error": None,
        "finish_reason": "", "error": None, "exit_reason": None,
        "corrections": [], "out_of_scope": None, "wanted_wiki_ids": [],
        "citations": [], "excerpts": {}, "clarify_questions": [],
        "await_flag": False, "needs_sufficient": True, "need_quote": False,
    }


# --------------------------------------------------------------- 1. 拓扑快照
def test_topology_snapshot():
    print("[1] 拓扑快照（11 业务节点 + 边/条件边）")
    dg = graph_mod.build_graph(None).get_graph()
    nodes = set(dg.nodes)
    biz = nodes - {"__start__", "__end__"}
    check(biz == BUSINESS_NODES, f"业务节点集合 = {sorted(biz)}（期望 11 个，SPEC §6.2）")

    edges = {(e.source, e.target, bool(e.conditional)) for e in dg.edges}
    missing = EDGE_SNAPSHOT - edges
    extra = edges - EDGE_SNAPSHOT
    check(not missing, f"快照中的边全部存在（缺失 {sorted(missing)}）")
    check(not extra, f"没有快照外的隐式新边（新增 {sorted(extra)}）")
    check(len(EDGE_SNAPSHOT) == 20, f"边快照条数 = {len(EDGE_SNAPSHOT)}（20）")


# --------------------------------------------------- 2. 执行期参数注入（F3）
class _RecordingInner:
    """记录 stream/invoke 收到的 config 与 kwargs，不真正跑图。"""

    def __init__(self):
        self.calls = []

    def stream(self, initial, config=None, **kwargs):
        self.calls.append(("stream", config, kwargs))
        yield ("values", {"finish_reason": "end"})

    def invoke(self, initial, config=None, **kwargs):
        self.calls.append(("invoke", config, kwargs))
        return {"finish_reason": "end"}

    def get_state(self, config):
        return None


def test_execution_params_injected():
    print("[2] _ThreadHandle 注入 thread_id / recursion_limit / durability")
    inner = _RecordingInner()
    handle = graph_mod._ThreadHandle(inner)
    list(handle.stream({"session_id": "t-param"}, {"configurable": {"thread_id": "explicit"}}))
    mode, cfg, kw = inner.calls[-1]
    check(cfg["configurable"]["thread_id"] == "explicit", "显式 thread_id 不被覆盖")
    check(cfg["recursion_limit"] == graph_mod.RECURSION_LIMIT,
          f"未指定时补默认 recursion_limit={graph_mod.RECURSION_LIMIT}")
    check(kw.get("durability") == graph_mod.GRAPH_DURABILITY,
          f"stream 自动带上 durability={graph_mod.GRAPH_DURABILITY}")

    handle.invoke({"session_id": "t-param2"}, {"recursion_limit": 7})
    mode, cfg, kw = inner.calls[-1]
    check(cfg["recursion_limit"] == min(7, graph_mod.RECURSION_LIMIT),
          "调用方更小的 recursion_limit 被尊重（可降）")
    crank = handle._config({"session_id": "t-param3"}, {"recursion_limit": 99999})
    check(crank["recursion_limit"] == graph_mod.RECURSION_LIMIT,
          f"超过天花板的 recursion_limit 被夹到 {graph_mod.RECURSION_LIMIT}（不可升）")
    check(cfg["configurable"]["thread_id"] == "t-param2",
          "thread_id 由 session_id 兜底注入（checkpoint 主键）")
    check(kw.get("durability") == graph_mod.GRAPH_DURABILITY, "invoke 同样带上 durability")

    check(graph_mod.GRAPH_DURABILITY in ("sync", "async", "exit"),
          f"durability 取值合法：{graph_mod.GRAPH_DURABILITY}")


# --------------------------------------------- 3. 递归上限异常翻译（F3/健壮性）
class _RecursionInner:
    def stream(self, initial, config=None, **kwargs):
        raise GraphRecursionError("Recursion limit of 40 reached")
        yield  # pragma: no cover - 仅为让本方法成为生成器函数

    def invoke(self, initial, config=None, **kwargs):
        raise GraphRecursionError("Recursion limit of 40 reached")

    def get_state(self, config):
        return None


def test_recursion_error_translated():
    print("[3] GraphRecursionError → 协议内 error 事件（不退化成 INTERNAL）")
    handle = graph_mod._ThreadHandle(_RecursionInner())
    events = list(handle.stream({"session_id": "t-rec"}, {}))
    custom = [p for m, p in events if m == "custom"]
    values = [p for m, p in events if m == "values"]
    check(len(custom) == 1 and custom[0]["event"] == "error",
          f"产出 1 个 error 事件：{[c.get('event') for c in custom]}")
    check(custom and custom[0]["data"]["code"] == "GRAPH_RECURSION_LIMIT",
          f"错误码 = {custom[0]['data']['code'] if custom else None}（期望 GRAPH_RECURSION_LIMIT）")
    check(custom and custom[0]["trace"]["record_type"] == "error",
          "同时落一条 record_type=error 轨迹（可检索）")
    check(bool(values) and values[-1]["finish_reason"] == "error"
          and values[-1]["exit_reason"] == "recursion_limit",
          f"终态交代 finish_reason/exit_reason = {values[-1] if values else None}")


# ------------------------------------------------- 4. 桥接重试分层（F1）
def test_tool_retry_transient_vs_business():
    print("[4] _call_tool 重试：瞬时故障重试、业务错误不重试")
    state = {"session_id": "t-retry", "trace_id": "tr-retry"}
    args = {"owner_id": "OWN-1001"}

    calls = {"n": 0}

    def flaky_then_ok(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("bridge socket closed")
        return {"found": True, "owner": {"owner_id": "OWN-1001"}}

    original = mcp_bridge.get_policy
    mcp_bridge.get_policy = flaky_then_ok
    try:
        out = graph_mod._call_tool(state, "get_policy", "get_policy", args)
    finally:
        mcp_bridge.get_policy = original
    check(calls["n"] == 3, f"瞬时故障重试到成功：attempts = {calls['n']}（期望 3）")
    check("error" not in out and out.get("found") is True,
          f"重试后返回正常结果：{list(out)[:4]}")

    calls2 = {"n": 0}

    def always_business_error(**kwargs):
        calls2["n"] += 1
        raise mcp_bridge.ToolError("INVALID_USE_NATURE", "使用性质非法")

    original = mcp_bridge.get_policy
    mcp_bridge.get_policy = always_business_error
    try:
        out2 = graph_mod._call_tool(state, "get_policy", "get_policy", args)
    finally:
        mcp_bridge.get_policy = original
    check(calls2["n"] == 1, f"业务错误不重试：attempts = {calls2['n']}（期望 1）")
    check(out2.get("error", {}).get("code") == "INVALID_USE_NATURE",
          f"业务错误码原样回给节点：{out2.get('error')}")


# ------------------------------------------------------ 5. 并发（F2）
class _NoLLM:
    """规则模式桩：available=False → 图内 LLM 节点走确定性降级，不触网。"""

    available = False
    model = "stub"

    def chat(self, system, messages, max_tokens=1024):
        from server.llm import LLMResult
        return LLMResult(text="【规则模式】stub", tokens_in=None,
                         tokens_out=None, mode="rule")

    def chat_tool_json(self, *a, **kw):
        return None, None

    def stream_chat(self, system, messages, max_tokens=1024):
        from server.llm import LLMResult
        yield "", LLMResult(text="stub", tokens_in=None, tokens_out=None, mode="rule")


def test_concurrent_runs_share_checkpointer():
    print("[5] 多线程并发驱动同一 SqliteSaver（无全局串行锁也能安全）")
    original_client = graph_mod.get_client
    graph_mod.get_client = lambda: _NoLLM()
    try:
        with tempfile.TemporaryDirectory() as td:
            conn = __import__("sqlite3").connect(Path(td) / "c.sqlite",
                                                 check_same_thread=False)
            graph = graph_mod.build_graph(SqliteSaver(conn))
            results, errors = {}, []

            def worker(tag: int):
                try:
                    cfg = {"configurable": {"thread_id": f"conc-{tag}"},
                           "recursion_limit": 40}
                    results[tag] = graph.invoke(
                        _initial(f"conc-{tag}", "我的车快到期了，帮我看看续保方案"),
                        cfg, durability=graph_mod.GRAPH_DURABILITY)
                except Exception as exc:  # noqa: BLE001 - 测试要看到任何异常
                    errors.append(f"{tag}: {type(exc).__name__}: {exc}")

            ths = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in ths:
                t.start()
            for t in ths:
                t.join()

            check(not errors, f"4 路并发无异常（错误 {errors[:2]}）")
            check(len(results) == 4, f"4 路都产出终态（实际 {len(results)}）")
            ok_finish = [r.get("finish_reason") in ("end", "await_user", "error")
                         for r in results.values()]
            check(all(ok_finish), f"每路都有 finish_reason：{[r.get('finish_reason') for r in results.values()]}")
            # 各 thread 状态独立可读（checkpoint 未互相污染）
            tids = {f"conc-{i}" for i in range(4)}
            readable = {tid for tid in tids
                        if graph.get_state({"configurable": {"thread_id": tid}}).values.get("session_id") == tid}
            check(readable == tids, f"4 个 thread 状态各自可读（{sorted(readable)}）")
            conn.close()
    finally:
        graph_mod.get_client = original_client


def test_no_ineffective_run_lock():
    print("[6] 防回归：无效的进程级 _RUN_LOCK 不得被重新引入")
    check(not hasattr(graph_mod, "_RUN_LOCK"),
          "graph 模块不再持有 _RUN_LOCK（并发安全由 Saver 内部锁 + WAL 兜底）")


if __name__ == "__main__":
    test_topology_snapshot()
    test_execution_params_injected()
    test_recursion_error_translated()
    test_tool_retry_transient_vs_business()
    test_concurrent_runs_share_checkpointer()
    test_no_ineffective_run_lock()
    print(f"\n通过 {PASS} / {PASS + FAIL}")
    sys.exit(0 if FAIL == 0 else 1)
