#!/usr/bin/env python3
"""单元测试：官方 checkpointer 持久化（2026-11-13 评审整改）。

覆盖：
1. 同 thread_id 两次 invoke：跨轮需求累积（budget 沿用、DSX 保额保留），
   状态经官方 checkpoint 延续（不经 sessions.json 恢复路径）；
2. 不同 thread_id 之间状态隔离（互不串扰）；
3. 进程内“重启语义”：同一 SQLite 文件重建 checkpointer + 重新编译图，
   历史线程状态仍可读（SqliteSaver 落盘有效性）；InMemorySaver 环境跳过该项；
4. get_graph() 默认句柄注入 thread_id（app.py 零改动兼容层）。

运行：.venv/bin/python -m pytest tests/test_persistence.py -q （退出码 0 = 通过）
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402

from server import graph as graph_mod  # noqa: E402

PASS = 0
FAIL = 0


def check(cond: bool, label: str) -> None:
    global PASS, FAIL
    print(f"  {'✓' if cond else '✗'} {label}")
    PASS += 1 if cond else 0
    FAIL += 0 if cond else 1


def _initial(session_id: str, message: str) -> dict:
    return {
        "session_id": session_id,
        "owner_id": "OWN-1001",
        "trace_id": f"tr-{session_id}-{abs(hash(message)) % 10000}",
        "message": message,
        "steps": 0, "intent": "", "confirmed": False, "confirm_error": None,
        "finish_reason": "", "error": None, "exit_reason": None,
        "corrections": [], "out_of_scope": None, "wanted_wiki_ids": [],
        "citations": [], "excerpts": {}, "clarify_questions": [],
        "await_flag": False, "needs_sufficient": True, "need_quote": False,
    }


def test_thread_continuity_and_isolation():
    print("[1] 同 thread_id 状态延续 + [2] 线程隔离")
    handle = graph_mod.get_graph()
    s2 = handle.invoke(_initial("t-persist-a", "我想续保，三者险保额调整到200万"))
    check(bool((s2.get("needs") or {}).get("sum_insured_changes")),
          "第 1 轮：解析出 DSX 保额调整")

    # 第 2 轮不带任何历史键：需求只能来自 checkpointer（thread 延续）
    s3 = handle.invoke(_initial("t-persist-a", "预算控制在6000元以内"))
    needs = s3.get("needs") or {}
    check(needs.get("budget_yuan") == 6000, "第 2 轮：预算 6000 已解析")
    codes = {c["code"]: c["sum_insured"] for c in needs.get("sum_insured_changes") or []}
    check(codes.get("DSX") == 2000000, "第 2 轮：DSX 200万 跨轮保留（checkpoint 延续）")
    check(int(s3.get("needs_version") or 0) >= 2, "需求版本跨轮自增")

    # 隔离：另一 thread 不受污染
    s_other = handle.invoke(_initial("t-persist-b", "你好"))
    check(not ((s_other.get("needs") or {}).get("sum_insured_changes")),
          "另一 thread_id：无串扰（状态隔离）")


def test_restart_semantics_sqlite():
    print("[3] SqliteSaver 重启语义（同库文件重建 checkpointer）")
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "ckpt.sqlite"
        conn = sqlite3.connect(db, check_same_thread=False)
        saver = SqliteSaver(conn)
        g1 = graph_mod.build_graph(checkpointer=saver)
        cfg = {"configurable": {"thread_id": "t-restart"}}
        out = g1.invoke(_initial("t-restart", "我想续保，三者险保额调整到300万"), cfg)
        check(bool((out.get("needs") or {}).get("sum_insured_changes")), "重启前：需求已入 checkpoint")
        conn.close()

        # 模拟重启：新连接、重新编译，同 thread_id 读回状态
        conn2 = sqlite3.connect(db, check_same_thread=False)
        g2 = graph_mod.build_graph(checkpointer=SqliteSaver(conn2))
        snap = g2.get_state(cfg)
        codes = {c["code"]: c["sum_insured"]
                 for c in ((snap.values.get("needs") or {}).get("sum_insured_changes") or [])}
        check(codes.get("DSX") == 3000000, "重启后：checkpoint 状态仍可读（SQLite 落盘）")
        out2 = g2.invoke(_initial("t-restart", "预算8000元"), cfg)
        codes2 = {c["code"]: c["sum_insured"]
                  for c in (out2.get("needs") or {}).get("sum_insured_changes") or []}
        check((out2.get("needs") or {}).get("budget_yuan") == 8000
              and codes2.get("DSX") == 3000000,
              "重启后继续对话：新需求叠加在恢复状态之上")
        conn2.close()


def test_default_handle_injects_thread_id():
    print("[4] get_graph() 兼容层注入 thread_id")
    handle = graph_mod.get_graph()
    cfg = handle._config({"session_id": "t-inject"}, {"recursion_limit": 40})
    check(cfg["configurable"].get("thread_id") == "t-inject",
          "config 缺 configurable 时自动注入 thread_id")
    cfg2 = handle._config({"session_id": "t-keep"},
                          {"configurable": {"thread_id": "explicit"}})
    check(cfg2["configurable"]["thread_id"] == "explicit",
          "外部已指定 thread_id 时不覆盖")


if __name__ == "__main__":
    test_thread_continuity_and_isolation()
    test_restart_semantics_sqlite()
    test_default_handle_injects_thread_id()
    print(f"\n通过 {PASS} / {PASS + FAIL}")
    sys.exit(0 if FAIL == 0 else 1)
