#!/usr/bin/env bash
# e2e_smoke.sh — 端到端冒烟（集成Agent产出，可重复执行）
#
# 覆盖 AC 场景串联：查保单(AC-01/02/04) → 比价(AC-05/06) → 改保额 → 加附加险(YWYW)
# → 条款问答(AC-11) → 确认(AC-13) + /confirm 错误码(AC-12相关) + 轨迹回放(AC-14)
# + 重启恢复（kill 服务再起：session 状态/报价仍在，POST /confirm 幂等只生成一个 order_id）。
#
# 用法：./scripts/e2e_smoke.sh [PORT]     # 默认 8123，不占用 SPEC 的 8000
# 退出码：0 = 全部通过；1 = 有断言失败。
set -uo pipefail
cd "$(dirname "$0")/.."

PORT="${1:-${E2E_PORT:-8123}}"
BASE="http://127.0.0.1:${PORT}"
PY=".venv/bin/python"
command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python3)"
STATE_FILE="$(mktemp -t e2e-state)"
SRV_PID=""
LOG="$(mktemp -t e2e-uvicorn)"
trap 'cleanup' EXIT

cleanup() {
  if [ -n "$SRV_PID" ] && kill -0 "$SRV_PID" 2>/dev/null; then
    kill "$SRV_PID" 2>/dev/null
    wait "$SRV_PID" 2>/dev/null
  fi
  rm -f "$STATE_FILE"
}

start_server() {
  PORT="$PORT" "$PY" -m uvicorn server.app:app \
    --host 127.0.0.1 --port "$PORT" --log-level warning >"$LOG" 2>&1 &
  SRV_PID=$!
  for _ in $(seq 1 100); do
    curl -sf "$BASE/health" >/dev/null 2>&1 && return 0
    sleep 0.2
  done
  echo "❌ 服务启动失败（$BASE/health 无响应），日志："; tail -20 "$LOG"
  exit 1
}

stop_server() {
  [ -n "$SRV_PID" ] || return 0
  kill "$SRV_PID" 2>/dev/null
  wait "$SRV_PID" 2>/dev/null
  SRV_PID=""
}

echo "=================================================================="
echo "E2E smoke  BASE=$BASE  (python: $PY)"
echo "=================================================================="

# ---------------- 阶段 A：起服务 → AC 链路串测 -------------------------
start_server
"$PY" - "$BASE" "$STATE_FILE" phaseA <<'PYEOF'
import json, sys, time
import httpx

BASE, STATE_FILE, PHASE = sys.argv[1], sys.argv[2], sys.argv[3]
FAILURES = []

def check(cond, label):
    print(f"  {'✅' if cond else '❌'} {label}")
    if not cond:
        FAILURES.append(label)

def chat(client, sid, owner, msg):
    events, trace_id, name, buf = [], "", "", []
    with client.stream("POST", "/chat",
                       json={"session_id": sid, "owner_id": owner, "message": msg},
                       timeout=120) as resp:
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        for line in resp.iter_lines():
            if line.startswith("event: "):
                name = line[7:].strip()
            elif line.startswith("data: "):
                buf.append(line[6:])
            elif line == "" and name:
                data = json.loads("".join(buf))
                events.append((name, data))
                if name == "done":
                    trace_id = data.get("trace_id", trace_id)
                name, buf = "", []
    return events, trace_id

def data_of(events, name):
    return [d for e, d in events if e == name]

with httpx.Client(base_url=BASE) as c:
    stamp = int(time.time())
    sid = f"e2e-{stamp}"

    print("=== A1 查保单（AC-01/02/04）===")
    r = c.get("/policy/OWN-1001")
    p = r.json()
    check(r.status_code == 200 and p.get("found") is True, "OWN-1001 found")
    check(p.get("expiring_soon") is True and p.get("days_to_expiry", 0) > 0,
          f"临期提醒 expiring_soon=true（{p.get('days_to_expiry')} 天）")
    check("id_number" not in p.get("owner", {}) and "phone" not in p.get("owner", {}),
          "身份证号/手机号脱敏（不出参）")
    check(bool(p.get("policy", {}).get("policy_version")), "返回 policy_version")
    r404 = c.get("/policy/OWN-9999")
    check(r404.status_code == 404 and r404.json().get("found") is False,
          "OWN-9999 → 404 found=false（不编造）")

    print("=== A2 比价：续保 + 三者险升 200万（AC-05/06）===")
    ev1, tid1 = chat(c, sid, "OWN-1001",
                     "我的车快到期了，帮我看看续保方案，三者险保额提高到200万")
    q1 = data_of(ev1, "quote")
    check(bool(q1), "收到 quote 事件")
    if not q1:
        # P1c：无报价时优雅报错退出（非 IndexError 崩溃），退出码非 0
        print(f"\n[phaseA] ❌ {len(FAILURES)} 项失败：本轮无 quote 事件（见上方 ❌ 项），跳过依赖报价的后续断言")
        sys.exit(1)
    check("await_confirm" in [e for e, _ in ev1], "收到 await_confirm 事件")
    check(data_of(ev1, "done")[0]["finish_reason"] == "await_user", "finish_reason=await_user")
    chain = [d["node"] for d in data_of(ev1, "node_start")]
    check(chain == ["intake", "get_policy", "parse_needs", "retrieve_terms",
                    "quote", "compare", "await_confirm"], f"节点链完整 {chain}")
    tools = [d["tool"] for d in data_of(ev1, "tool_call")]
    check("get_policy" in tools and "query_quote" in tools,
          f"MCP 工具真实调用 {tools}")
    dsx = [li for li in q1[-1]["line_items"] if li["code"] == "DSX"]
    check(dsx and dsx[0]["sum_insured"] == 2000000, "DSX 保额=200万（tiers 计价）")
    check(any("保障差异" in m.get("content", "") for m in data_of(ev1, "message")),
          "compare 输出保障差异表")

    print("=== A3 改保额 200万→300万（重新询价）===")
    ev2, tid2 = chat(c, sid, "OWN-1001", "改一下，三者险调到300万吧")
    q2 = data_of(ev2, "quote")
    check(bool(q2), "收到新 quote 事件")
    if not q2:
        print(f"\n[phaseA] ❌ {len(FAILURES)} 项失败：改保额轮无 quote 事件，跳过后续断言")
        sys.exit(1)
    check(sum(1 for d in data_of(ev2, "tool_call") if d["tool"] == "query_quote") >= 1,
          "改保额触发重新询价")
    dsx2 = [li for li in q2[-1]["line_items"] if li["code"] == "DSX"]
    check(dsx2 and dsx2[0]["sum_insured"] == 3000000, "新方案 DSX=300万")

    print("=== A4 加附加险：医保外用药（YWYW）===")
    ev3, tid3 = chat(c, sid, "OWN-1001", "再加个医保外用药附加险")
    q3 = data_of(ev3, "quote")
    check(bool(q3), "收到新 quote 事件")
    if not q3:
        print(f"\n[phaseA] ❌ {len(FAILURES)} 项失败：加附加险轮无 quote 事件，跳过后续断言")
        sys.exit(1)
    ywyw = [li for li in q3[-1]["line_items"] if li["code"] == "YWYW"]
    check(bool(ywyw), f"新方案含 YWYW 行项 {ywyw}")
    check(any("医保外用药" in m.get("content", "") or "YWYW" in m.get("content", "")
              for m in data_of(ev3, "message")), "回复体现附加险")

    print("=== A5 条款问答：未年检（AC-11，不进比价）===")
    ev4, tid4 = chat(c, f"{sid}-terms", "OWN-1001", "车辆没年检出事故，保险赔不赔？")
    evn = [e for e, _ in ev4]
    check("quote" not in evn and "await_confirm" not in evn, "条款问答不进入比价/确认")
    cited = [m for m in data_of(ev4, "message") if m.get("citations")]
    check(bool(cited) and {"wiki_id", "source", "version"} <= set(cited[0]["citations"][0]),
          f"message 带 citation（{cited[0]['citations'][0]['wiki_id'] if cited else '-'}）")
    check(data_of(ev4, "done")[0]["finish_reason"] == "end", "finish_reason=end")

    print("=== A6 轨迹回放（AC-14）===")
    rt = c.get(f"/trace/{tid1}")
    rows = rt.json()
    check(rt.status_code == 200 and isinstance(rows, list) and rows,
          f"GET /trace/{tid1} 可回放（{len(rows)} 行）")
    check([r["seq"] for r in rows] == list(range(1, len(rows) + 1)), "seq 连续")

    # 传递给阶段 B（重启后）
    latest = q3[-1]
    json.dump({"session_id": sid, "trace_id": tid1, "quote_id": latest["quote_id"],
               "quote_version": latest["quote_version"]},
              open(STATE_FILE, "w"))

print(f"\n[phaseA] {'❌ ' + str(len(FAILURES)) + ' 项失败' if FAILURES else '✅ 全部通过'}")
sys.exit(1 if FAILURES else 0)
PYEOF
RC_A=$?
stop_server

if [ $RC_A -ne 0 ]; then
  echo "❌ 阶段 A 失败，终止"; exit 1
fi

# ---------------- 阶段 B：重启恢复 + 确认幂等 -------------------------
echo ""
echo "=== 重启服务（kill 再起），验证 session 状态/报价仍在 ==="
start_server
"$PY" - "$BASE" "$STATE_FILE" phaseB <<'PYEOF'
import json, sys
import httpx

BASE, STATE_FILE, PHASE = sys.argv[1], sys.argv[2], sys.argv[3]
FAILURES = []
st = json.load(open(STATE_FILE))

def check(cond, label):
    print(f"  {'✅' if cond else '❌'} {label}")
    if not cond:
        FAILURES.append(label)

def chat(client, sid, owner, msg):
    events, name, buf = [], "", []
    with client.stream("POST", "/chat",
                       json={"session_id": sid, "owner_id": owner, "message": msg},
                       timeout=120) as resp:
        for line in resp.iter_lines():
            if line.startswith("event: "):
                name = line[7:].strip()
            elif line.startswith("data: "):
                buf.append(line[6:])
            elif line == "" and name:
                events.append((name, json.loads("".join(buf)))); name, buf = "", []
    return events

def data_of(events, name):
    return [d for e, d in events if e == name]

with httpx.Client(base_url=BASE) as c:
    print("=== B1 轨迹跨重启回放 ===")
    rt = c.get(f"/trace/{st['trace_id']}")
    check(rt.status_code == 200 and isinstance(rt.json(), list) and rt.json(),
          f"重启前 trace {st['trace_id']} 仍可回放（{len(rt.json())} 行）")

    print("=== B2 /confirm 错误码矩阵 ===")
    body = {"session_id": st["session_id"], "quote_id": st["quote_id"],
            "quote_version": st["quote_version"], "owner_id": "OWN-1001"}
    r_mismatch = c.post("/confirm", json={**body, "owner_id": "OWN-1002"})
    check(r_mismatch.status_code == 422 and
          r_mismatch.json()["error"]["code"] == "OWNER_MISMATCH", "越权 → 422 OWNER_MISMATCH")
    r_stale = c.post("/confirm", json={**body, "quote_version": body["quote_version"] + 5})
    check(r_stale.status_code == 409 and
          r_stale.json()["error"]["code"] == "QUOTE_VERSION_STALE",
          "旧版本 → 409 QUOTE_VERSION_STALE")
    r_notfound = c.post("/confirm", json={**body, "quote_id": "QT-NOT-EXIST"})
    check(r_notfound.status_code == 404 and
          r_notfound.json()["error"]["code"] == "QUOTE_NOT_FOUND", "不存在 → 404")

    print("=== B3 确认成功 + 幂等（重启后报价仍在）===")
    r1 = c.post("/confirm", json=body)
    check(r1.status_code == 200 and r1.json().get("order_id", "").startswith("ORD-"),
          f"POST /confirm 200 → {r1.json().get('order_id')}")
    r2 = c.post("/confirm", json=body)
    check(r2.status_code == 200 and r2.json().get("order_id") == r1.json().get("order_id"),
          f"重复确认幂等：同一 order_id {r2.json().get('order_id')}")

    print("=== B4 会话状态跨重启（awaiting_confirm → 对话内“确认”）===")
    ev = chat(c, st["session_id"], "OWN-1001", "确认，就按这个方案投保")
    conf = data_of(ev, "confirmed")
    check(bool(conf), "SSE 推送 confirmed 事件")
    if conf:
        check(conf[0]["order_id"] == r1.json()["order_id"],
              f"对话确认与 /confirm 幂等一致（{conf[0]['order_id']}）")
    check(data_of(ev, "done")[0]["finish_reason"] == "end", "finish_reason=end")

print(f"\n[phaseB] {'❌ ' + str(len(FAILURES)) + ' 项失败' if FAILURES else '✅ 全部通过'}")
sys.exit(1 if FAILURES else 0)
PYEOF
RC_B=$?
stop_server

echo ""
echo "=================================================================="
if [ $RC_B -eq 0 ]; then
  echo "✅ E2E smoke 全部通过（AC 链路 + 重启恢复 + 确认幂等）"
  exit 0
else
  echo "❌ E2E smoke 阶段 B 失败"; exit 1
fi
