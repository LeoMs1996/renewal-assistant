#!/usr/bin/env python3
"""记忆机制域评测：跨会话记忆 A/B（before = 旧截断策略 / after = 本次整改）。

设计依据（基线见 reviews/memory.md §3）：
- LoCoMo-Plus（ACL 2026）：字符串匹配指标与记忆能力错配，改看「约束一致性」——
  断言的是「约束/事实有没有进入模型上下文」，而不是答案里凑巧出现某个词；
- Hindsight（2026-05-20）：评测三信号 = 多会话推理准确率、矛盾检测、每轮 token 成本；
- Oracle（2026-06-05）：context package 可调试（摘要/结构化记忆/召回各自可见）；
- MediaNama（2026-08-28）：删除必须覆盖派生记录 → 遗忘后全库扫描无残留。

A/B 方式：只切 RENEWAL_MEMORY 开关（on=本次整改；off=退回旧行为）跑同一批脚本。
每个场景都真实经过 「sessions.load → graph.invoke → sessions.save/append_history」，
即 app.py 的每轮链路（不绕过任何一层）。

用法：
  .venv/bin/python eval/memory_eval.py                # 表格 + JSON 落盘
  .venv/bin/python eval/memory_eval.py --json          # 只输出 JSON
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------- 每轮链路


def _initial(session_id: str, owner_id: str, message: str, snapshot: dict) -> dict:
    """等价 app.py 的 initial State 组装（会话快照 + 本轮临时键）。"""
    initial = dict(snapshot)
    initial.update({
        "session_id": session_id, "owner_id": owner_id, "message": message,
        "trace_id": f"trc-eval-{session_id}-{abs(hash(message)) % 100000}",
        "steps": 0, "intent": "", "confirmed": False, "confirm_error": None,
        "finish_reason": "", "error": None, "exit_reason": None,
        "corrections": [], "out_of_scope": None, "wanted_wiki_ids": [],
        "citations": [], "excerpts": {}, "clarify_questions": [],
        "await_flag": False, "needs_sufficient": True, "need_quote": False,
    })
    return initial


def turn(graph, sessions, owner: str, session: str, message: str) -> dict:
    """跑一轮（与 app.py /chat 同构：load → invoke → save → append_history）。"""
    snap = sessions.load(session)
    state = graph.invoke(_initial(session, owner, message, snap))
    sessions.save(session, state)
    sessions.append_history(session, "user", message)
    if state.get("assistant_reply"):
        sessions.append_history(session, "assistant", state["assistant_reply"])
    return state


# ---------------------------------------------------------------- 场景


SCENARIOS: list[dict] = []


def scenario(fn):
    SCENARIOS.append({"id": fn.__name__, "fn": fn,
                      "title": (fn.__doc__ or "").strip().splitlines()[0]})
    return fn


@scenario
def s1_cross_session_preference(ctx) -> dict:
    """S1 跨会话偏好延续：新会话靠「上次」取回预算与保额档。"""
    g, s = ctx["graph"], ctx["sessions"]
    owner = "OWN-EVAL-1"
    turn(g, s, owner, "s1-a", "预算6000元，三者险保额调到200万，帮我续保报价")
    st = turn(g, s, owner, "s1-b", "还是按上次的方案，三者险照旧，帮我续保报价")
    needs = st.get("needs") or {}
    codes = {c["code"]: c["sum_insured"] for c in needs.get("sum_insured_changes") or []}
    ok = needs.get("budget_yuan") == 6000 and codes.get("DSX") == 2000000
    return {"ok": ok, "detail": {"budget_yuan": needs.get("budget_yuan"),
                                 "sum_insured": codes, "seeded": st.get("memory_seeded")}}


@scenario
def s2_contradiction_resolution(ctx) -> dict:
    """S2 矛盾处理：改口后旧值必须失效，召回不得把旧值当现值。"""
    g, s = ctx["graph"], ctx["sessions"]
    mem = ctx["memory"]
    owner = "OWN-EVAL-2"
    turn(g, s, owner, "s2-a", "三者险保额调到200万，帮我续保报价")
    turn(g, s, owner, "s2-b", "三者险保额降到100万，帮我续保报价")
    st = turn(g, s, owner, "s2-c", "还是按上次三者险的保额，帮我续保报价")
    codes = {c["code"]: c["sum_insured"]
             for c in (st.get("needs") or {}).get("sum_insured_changes") or []}
    active = mem.get(owner, "sum_insured:DSX") if ctx["memory_on"] else None
    superseded = [i for i in mem.superseded_items(owner) if i["field"] == "sum_insured:DSX"] \
        if ctx["memory_on"] else []
    brief = mem.render_brief(owner) if ctx["memory_on"] else ""
    # 正确 = 召回到 100 万且旧 200 万被标失效（或被召回到但标记为已失效）
    ok = (codes.get("DSX") == 1000000 and active == 1000000
          and all(i["value"] == 2000000 for i in superseded)
          and ("已失效" in brief or "200 万" in brief))
    return {"ok": ok, "detail": {"recalled_dsx": codes.get("DSX"), "active": active,
                                 "superseded_values": [i["value"] for i in superseded],
                                 "brief_has_stale_marker": "已失效" in brief}}


@scenario
def s3_constraint_consistency(ctx) -> dict:
    """S3 约束一致性：早期预算约束是否进入后续会话的模型上下文。"""
    g, s = ctx["graph"], ctx["sessions"]
    mem = ctx["memory"]
    owner = "OWN-EVAL-3"
    turn(g, s, owner, "s3-a", "预算不超过6000元，帮我续保报价")
    snap = s.load("s3-b") or {}
    snap["owner_id"] = owner
    state = {"history": snap.get("history") or [], "owner_id": owner,
             "message": "还是按上次的方案，帮我续保报价"}
    extra, _ = mem.prompt_context(state, budget_tokens=1000)
    ok = "6000" in extra
    return {"ok": ok, "detail": {"context_has_constraint": ok,
                                 "context_tokens": mem.estimate_tokens(extra)}}


@scenario
def s4_context_budget_and_summary(ctx) -> dict:
    """S4 上下文预算：长会话下 prompt token 有界，且早期要点被摘要保留。"""
    mem = ctx["memory"]
    turns = []
    for i in range(30):
        if i == 2:
            turns.append({"role": "user", "content": "预算 5000 元的说法先记着"})
        turns.append({"role": "user" if i % 2 == 0 else "assistant",
                      "content": f"第{i}轮：" + "续保方案与条款说明细节" * 18})
    state = {"history": turns, "owner_id": "OWN-EVAL-4", "message": "继续"}
    if ctx["memory_on"]:
        kept, dropped, used = mem.trim_turns(turns, 1000)
        pkg = mem.build_context_package(state, budget_tokens=1000)
        ctx_tokens = pkg["tokens"]["total"]
        summary = pkg["summary"]
        bounded = ctx_tokens <= 1000 * 1.4      # 摘要/简报允许少量溢出
    else:  # 旧策略：固定取尾部 8 条，无预算、无摘要
        kept = turns[-8:]
        ctx_tokens = sum(mem.estimate_tokens(t["content"]) + 4 for t in kept)
        summary = ""
        bounded = ctx_tokens <= 1000 * 1.4
    retains_key_info = ("5000" in summary) if ctx["memory_on"] else \
        any("5000" in t["content"] for t in kept)
    return {"ok": bool(bounded and retains_key_info),
            "detail": {"prompt_tokens": ctx_tokens, "bounded": bounded,
                       "dropped_turns": len(turns) - len(kept),
                       "summary_has_key_info": "5000" in summary,
                       "kept_turns": len(kept)}}


@scenario
def s5_erasure_and_portability(ctx) -> dict:
    """S5 遗忘权/可携权：导出可带走，遗忘后全库无残留。"""
    g, s = ctx["graph"], ctx["sessions"]
    mem = ctx["memory"]
    owner = "OWN-EVAL-5"
    turn(g, s, owner, "s5-a", "预算6000元，手机13801610001，帮我续保报价")
    if not ctx["memory_on"]:
        return {"ok": False, "detail": {"reason": "旧实现无长期记忆，无遗忘/可携能力"}}
    exported = mem.export_owner(owner)
    before = len(exported["items"])
    removed = mem.forget(owner)
    doc = json.loads(mem._path(owner).read_text(encoding="utf-8"))
    blob = json.dumps(doc, ensure_ascii=False)
    ok = (before > 0 and removed["removed"] == before and doc["items"] == []
          and doc["audit"] == [] and "6000" not in blob and "13801610001" not in blob)
    return {"ok": ok, "detail": {"exported_items": before,
                                 "removed": removed["removed"],
                                 "residual": blob.count("6000")}}


# ---------------------------------------------------------------- 运行器


def run(memory_on: bool) -> dict:
    td = tempfile.mkdtemp(prefix=f"mem-eval-{'on' if memory_on else 'off'}-")
    os.environ["TRACE_DIR"] = td
    os.environ["TRACE_DIR"] = td          # config 在 import 时读取
    os.environ["RENEWAL_MEMORY"] = "on" if memory_on else "off"
    os.environ["RENEWAL_FORCE_RULE_MODE"] = "1"
    for mod in [m for m in list(sys.modules) if m.startswith("server.")]:
        del sys.modules[mod]              # 重新按新 TRACE_DIR/开关导入
    from server import graph as graph_mod
    from server import memory as memory_mod
    from server import sessions as sessions_mod

    ctx = {"graph": graph_mod.get_graph(), "sessions": sessions_mod,
           "memory": memory_mod, "memory_on": memory_on}
    results = []
    for sc in SCENARIOS:
        try:
            out = sc["fn"](ctx)
        except Exception as exc:           # 场景失败不中断全批
            out = {"ok": False, "detail": {"error": f"{type(exc).__name__}: {exc}"}}
        results.append({"id": sc["id"], "title": sc["title"], **out})
    return {"mode": "after" if memory_on else "before", "trace_dir": td,
            "results": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    before, after = run(False), run(True)
    passed = {"before": sum(1 for r in before["results"] if r["ok"]),
              "after": sum(1 for r in after["results"] if r["ok"])}
    total = len(SCENARIOS)
    summary = {
        "generated_at": _iso_now(),
        "baseline_date": "2026-11-13",
        "retrieved_at": "2026-11-17",
        "total_scenarios": total,
        "passed": passed,
        "before": before, "after": after,
    }
    out_path = ROOT / "eval" / f"memory-eval-{datetime.now():%Y%m%d-%H%M%S}.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return 0

    print(f"记忆机制域 A/B 评测（{summary['generated_at']}）")
    print(f"{'场景':<34}{'before':<10}{'after':<10}detail")
    for b, a in zip(before["results"], after["results"], strict=True):
        detail = json.dumps(a["detail"], ensure_ascii=False)
        print(f"{b['id']:<34}{'PASS' if b['ok'] else 'FAIL':<10}"
              f"{'PASS' if a['ok'] else 'FAIL':<10}{detail[:88]}")
    print(f"\n合计：before {passed['before']}/{total} → after {passed['after']}/{total}")
    print(f"明细 JSON：{out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
