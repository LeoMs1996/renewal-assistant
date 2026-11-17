#!/usr/bin/env python3
"""编排链路自测（httpx 直连 POST /chat，SSE 解析）：

链路① 续保比价到 await_confirm：OWN-1001 发起续保 + 三者险 100万→200万，
      预期：node 链 intake→get_policy→parse_needs→retrieve_terms→quote→compare
      →await_confirm，收到 quote 与 await_confirm 事件。
链路② 改保额 200万→300万 → 重新询价（新 quote 事件、tool_call query_quote>0）；
      随后仅改预算（其他不变）→ 复用报价（本轮 tool_call query_quote==0，
      quote 事件 quote_id 不变）。
链路③ 条款问答（新会话）：未年检条款问题 → message 带 citation（wiki 条目），
      不出现 quote / await_confirm 事件，finish_reason=end。

轨迹校验：traces/{trace_id}.jsonl 存在、seq 从 1 连续、字段符合 SPEC §5。

用法：先启动服务（./run.sh 或 uvicorn server.app:app --port 8000），再
      python3 scripts/demo_chat.py [BASE_URL]
退出码：0 = 全部通过；1 = 有断言失败。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
TRACES = ROOT / "traces"

FAILURES: list[str] = []


def check(cond: bool, label: str) -> None:
    mark = "✅" if cond else "❌"
    print(f"  {mark} {label}")
    if not cond:
        FAILURES.append(label)


def chat(client: httpx.Client, session_id: str, owner_id: str,
         message: str) -> tuple[list[tuple[str, dict]], str]:
    """POST /chat，解析 SSE，返回 ([(event, data)...], trace_id)。"""
    events: list[tuple[str, dict]] = []
    trace_id = ""
    with client.stream("POST", "/chat",
                       json={"session_id": session_id, "owner_id": owner_id,
                             "message": message},
                       timeout=120) as resp:
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        event_name = ""
        data_buf: list[str] = []
        for line in resp.iter_lines():
            if line.startswith("event: "):
                event_name = line[7:].strip()
            elif line.startswith("data: "):
                data_buf.append(line[6:])
            elif line == "" and event_name:
                data = json.loads("".join(data_buf))
                events.append((event_name, data))
                if event_name == "done":
                    trace_id = data.get("trace_id", trace_id)
                event_name, data_buf = "", []
    return events, trace_id


def names(events):
    return [e for e, _ in events]


def data_of(events, name):
    return [d for e, d in events if e == name]


def verify_trace(trace_id: str, label: str) -> None:
    path = TRACES / f"{trace_id}.jsonl"
    check(path.is_file(), f"{label}: traces/{trace_id}.jsonl 存在")
    if not path.is_file():
        return
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
    seqs = [r["seq"] for r in rows]
    check(seqs == list(range(1, len(rows) + 1)), f"{label}: seq 从 1 连续到 {len(rows)}")
    base_fields = {"ts", "trace_id", "session_id", "seq", "record_type"}
    check(all(base_fields <= set(r) for r in rows), f"{label}: SPEC §5 基础字段齐全")
    types = {r["record_type"] for r in rows}
    check(types <= {"node_start", "node_end", "tool_call", "tool_result", "llm_call",
                    "llm_response", "retrieval", "user_message", "assistant_message",
                    "error"}, f"{label}: record_type 枚举合法 ({sorted(types)})")
    retr = [r for r in rows if r["record_type"] == "retrieval"]
    if retr:
        ok = all(isinstance(r["output"], list) and r["output"] and
                 all({"wiki_id", "source", "version", "score"} <= set(h)
                     for h in r["output"]) for r in retr)
        check(ok, f"{label}: retrieval.output 含 [wiki_id/source/version/score]")


def main() -> int:
    with httpx.Client(base_url=BASE) as client:
        h = client.get("/health").json()
        print(f"服务健康：llm_mode={h['llm_mode']} graph={h['graph']} "
              f"wiki_entries={h['wiki_entries']}")

        stamp = int(time.time())

        # ================= 链路①：续保比价 → await_confirm =================
        print("\n=== 链路① 续保比价（OWN-1001，三者险 100万→200万）===")
        s1 = f"demo-{stamp}-1"
        events, tid1 = chat(client, s1, "OWN-1001",
                            "我的车快到期了，帮我看看续保方案，三者险保额提高到200万")
        evs = names(events)
        check("quote" in evs, "收到 quote 事件")
        check("await_confirm" in evs, "收到 await_confirm 事件（挂起待确认）")
        check("done" in evs and data_of(events, "done")[0]["finish_reason"] == "await_user",
              "done.finish_reason=await_user")
        node_starts = [d["node"] for d in data_of(events, "node_start")]
        expected_chain = ["intake", "get_policy", "parse_needs",
                          "retrieve_terms", "quote", "compare", "await_confirm"]
        check(node_starts == expected_chain,
              f"节点链完整 {node_starts}")
        tools = [d["tool"] for d in data_of(events, "tool_call")]
        check(tools.count("query_quote") >= 1, f"真实 query_quote 调用 x{tools.count('query_quote')}")
        quotes1 = data_of(events, "quote")
        dsx = [li for li in quotes1[-1]["line_items"] if li["code"] == "DSX"]
        check(dsx and dsx[0]["sum_insured"] == 2000000,
              "新方案 DSX 保额=200万（tiers 计价）")
        msgs = data_of(events, "message")
        comp = next((m for m in msgs if "保障差异" in m.get("content", "")), None)
        check(comp is not None, "compare 输出保障差异表（先保障后价格）")
        ac = data_of(events, "await_confirm")[0]
        check(bool(ac.get("confirmables")), "await_confirm 带待确认项")
        verify_trace(tid1, "链路①")

        # ================= 链路②：改保额 → 重新询价；仅改预算 → 复用 =================
        print("\n=== 链路② 改保额 200万→300万（应重新询价）===")
        events2, tid2 = chat(client, s1, "OWN-1001", "改一下，三者险调到300万吧")
        q2 = data_of(events2, "quote")
        check(bool(q2), "收到新 quote 事件")
        t2 = [d["tool"] for d in data_of(events2, "tool_call")]
        check(t2.count("query_quote") >= 1,
              f"改保额触发重新询价（query_quote x{t2.count('query_quote')}）")
        dsx2 = [li for li in q2[-1]["line_items"] if li["code"] == "DSX"]
        check(dsx2 and dsx2[0]["sum_insured"] == 3000000, "新方案 DSX=300万")
        check("await_confirm" in names(events2), "再次到 await_confirm")
        verify_trace(tid2, "链路②-a")

        print("\n=== 链路②-b 仅改预算（应复用报价，不重复询价）===")
        events3, tid3 = chat(client, s1, "OWN-1001",
                             "其他都不变，我预算控制在20000元以内，再给我看看")
        t3 = [d for d in data_of(events3, "tool_call") if d["tool"] == "query_quote"]
        check(len(t3) == 0, f"预算-only 未调 query_quote（调用次数={len(t3)}，轨迹可证）")
        q3 = data_of(events3, "quote")
        check(bool(q3) and q3[0]["quote_id"] == q2[-1]["quote_id"],
              "复用同一 quote_id（24h 内幂等）")
        msgs3 = data_of(events3, "message")
        check(any("预算" in m.get("content", "") for m in msgs3),
              "回复体现预算信息")
        verify_trace(tid3, "链路②-b")

        # ================= 链路③：条款问答（带 citation，不进比价） =================
        print("\n=== 链路③ 条款问答（未年检是否赔付）===")
        s3 = f"demo-{stamp}-3"
        events4, tid4 = chat(client, s3, "OWN-1001",
                             "车辆没年检出事故，保险赔不赔？")
        evs4 = names(events4)
        check("quote" not in evs4 and "await_confirm" not in evs4,
              "条款问答不进入比价/确认")
        msgs4 = data_of(events4, "message")
        cited = [m for m in msgs4 if m.get("citations")]
        check(bool(cited), "message 带 citations")
        if cited:
            c0 = cited[0]["citations"][0]
            check({"wiki_id", "source", "version"} <= set(c0),
                  f"citation 字段齐全：{c0}")
        retr_trace = any(r["record_type"] == "retrieval"
                         for r in (json.loads(x) for x in
                                   (TRACES / f"{tid4}.jsonl").read_text(
                                       encoding="utf-8").splitlines() if x))
        check(retr_trace, "轨迹含 retrieval 记录")
        done4 = data_of(events4, "done")[0]
        check(done4["finish_reason"] == "end", "done.finish_reason=end")
        verify_trace(tid4, "链路③")

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"❌ {len(FAILURES)} 项断言失败：")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("✅ 全部链路通过（三链路 + 轨迹完整性）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
