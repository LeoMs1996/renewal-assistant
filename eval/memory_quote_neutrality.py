"""记忆开关的报价中性哨兵：记忆开/关两模式下的保费必须逐轮完全一致。

为什么需要它：跨会话记忆会向 needs 注入默认值，而 needs 直接影响询价参数
（险种/保额档）。若记忆误触发，AC-02/03/06 的手算保费断言会静默失真。
本脚本用真实合成车主 OWN-1001 串行跑 7 轮（AC-01/05/06×2/07/09/10），
对比 RENEWAL_MEMORY=on 与 off 两种模式的 latest_quote.total_premium。

用法：.venv/bin/python eval/memory_quote_neutrality.py   # 退出码 0 = 中性
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MSGS = [
    ("ac01", "我的车快到期了，帮我看看续保方案"),
    ("ac05", "帮我对比原方案和新方案的续保差异"),
    ("ac06", "三者险保额从100万升到200万，给我续保报价"),
    ("ac06", "预算5000元以内就行"),
    ("ac07", "去掉三者险，去掉司机险，去掉乘客险，加个医保外用药"),
    ("ac09", "续保时不要交强险"),
    ("ac10", "我的车要改成网约车营运，帮我算保费"),
]

def run(memory_on: bool) -> dict:
    td = tempfile.mkdtemp(prefix=f"qn-{'on' if memory_on else 'off'}-")
    os.environ["TRACE_DIR"] = td
    os.environ["RENEWAL_MEMORY"] = "on" if memory_on else "off"
    os.environ["RENEWAL_FORCE_RULE_MODE"] = "1"
    for m in [x for x in list(sys.modules) if x.startswith("server.")]:
        del sys.modules[m]
    from server import graph as g
    from server import sessions as s
    handle = g.get_graph()
    out = {}
    for i, (sess, msg) in enumerate(MSGS):
        sid = f"qn-{i}"
        snap = s.load(sid)
        initial = dict(snap)
        initial.update({"session_id": sid, "owner_id": "OWN-1001", "message": msg,
                        "trace_id": f"trc-qn-{i}", "steps": 0, "intent": "",
                        "confirmed": False, "confirm_error": None, "finish_reason": "",
                        "error": None, "exit_reason": None, "corrections": [],
                        "out_of_scope": None, "wanted_wiki_ids": [], "citations": [],
                        "excerpts": {}, "clarify_questions": [], "await_flag": False,
                        "needs_sufficient": True, "need_quote": False})
        st = handle.invoke(initial)
        s.save(sid, st)
        q = st.get("latest_quote") or {}
        out[f"{i}:{sess}"] = {"total": q.get("total_premium"), "qid": q.get("quote_id"),
                              "needs": (st.get("needs") or {}).get("budget_yuan"),
                              "seeded": st.get("memory_seeded")}
    return out

off, on = run(False), run(True)
diff = {k: (off[k], on[k]) for k in off if off[k]["total"] != on[k]["total"]}
print("turns:", len(off))
print("premium mismatch:", json.dumps(diff, ensure_ascii=False))
print("on seeded:", {k: v["seeded"] for k, v in on.items() if v["seeded"]})
verdict = "PASS" if not diff else "FAIL"
print("VERDICT:", verdict)
raise SystemExit(0 if verdict == "PASS" else 1)
