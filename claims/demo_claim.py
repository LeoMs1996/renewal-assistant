#!/usr/bin/env python3
"""F4 端到端 demo：E1–E6 六个场景，一条命令跑完并给出 PASS/FAIL。

为什么要有它：`claims/api.py` 是 HTTP 面，但"跨进程恢复 / 重复提交 / 支付超时 / 降级"
这些**流程语义**用 CLI 验证更直接、可复现、无端口依赖；HTTP 面复用同一 `ClaimService`。

用法（**必须用 .venv-claims**，见 SPEC §8.0 / D-22）::

    export PYTHONPATH=.
    .venv-claims/bin/python claims/demo_claim.py            # 跑 E1–E6
    .venv-claims/bin/python claims/demo_claim.py --only E5  # 单跑一条

退出码：0 = 六条全过；1 = 有失败（失败项会逐条打印判据与实际值）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claims import api as capi
from claims import config
from claims.graph import ClaimGraph, ReviewDecision
from claims.state import ErrorCode, Status
from claims.tools import synthetic
from claims.tools.payment_gateway import MockPaymentGateway
from server.trace import RECORD_TYPES

RESULTS: list[dict[str, Any]] = []


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _payload(*, docs: str = "complete", occurred: str = "2026-11-01T08:20:00+08:00",
             location: str = "北京市朝阳区建国路", description: str = "追尾事故，前保险杠与大灯受损",
             owner: str = "OWN-1001", policy: str = "POL-2026-0001") -> dict[str, Any]:
    return {
        "owner_id": owner,
        "policy_no": policy,
        "session_id": "sess-f4",
        "report": {"occurred_at": occurred, "location": location,
                   "description": description, "has_injury": False},
        "documents": synthetic.documents(docs),
    }


def _trace_path(claim_id: str) -> Path:
    return config.trace_dir() / f"{claim_id}.jsonl"


def _rows(claim_id: str) -> list[dict[str, Any]]:
    path = _trace_path(claim_id)
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _kinds(rows: list[dict[str, Any]]) -> list[str]:
    return [str((r.get("event") or {}).get("kind")) for r in rows]


def _check(name: str, ok: bool, detail: dict[str, Any]) -> None:
    RESULTS.append({"id": name, "ok": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {json.dumps(detail, ensure_ascii=False)}")


def _tmpdb(tag: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix=f"f4-{tag}-"))
    return d / "checkpoints.sqlite"


# --------------------------------------------------------------------------- #
# E1 报案 → 核验 → 审核（interrupt）→ approve → 支付 → 完成
# --------------------------------------------------------------------------- #
def e1() -> None:
    os.environ["DEEPAGENTS_ENABLED"] = "false"          # 规则模式，确定性强
    os.environ["CLAIMS_AMOUNT_REVIEW_THRESHOLD"] = "0"  # 强制进人工审核
    graph = ClaimGraph(checkpoint_db=_tmpdb("e1"))
    thread = f"E1-{int(time.time())}"
    try:
        out = graph.invoke(_payload(), thread_id=thread)
        claim_id = str(out.get("claim_id"))
        interrupted = out.get("__interrupt__") is not None
        payable = (out.get("assessment") or {}).get("payable_amount")
        resumed = graph.resume(
            ReviewDecision(decision="approve", comment="材料齐备，同意赔付", reviewer_id="RV-0001"),
            thread_id=thread,
        )
        rows = _rows(claim_id)
        kinds = _kinds(rows)
        types = sorted({r.get("record_type") for r in rows})
        ok = (
            interrupted
            and out.get("status") == Status.REVIEW_PENDING
            and resumed.get("status") == Status.PAID
            and graph.gateway.charge_count == 1
            and _trace_path(claim_id).is_file()
            and "claims.review_requested" in kinds
            and "claims.review_approved" in kinds
            and "claims.payment_charged" in kinds
            and "claims.closed" in kinds
            # D-08：record_type 只能落在 server/trace.py 的 11 种白名单内（这里直接对白名单取子集）
            and set(types) <= set(RECORD_TYPES)
        )
        _check("E1 报案→核验→审核→支付→paid", ok, {
            "claim_id": claim_id,
            "interrupt": interrupted,
            "status_intake": out.get("status"),
            "status_final": resumed.get("status"),
            "payable_amount": payable,
            "charge_count": graph.gateway.charge_count,
            "trace_file": str(_trace_path(claim_id)),
            "trace_rows": len(rows),
            "record_types": types,
            "kinds": kinds,
        })
    finally:
        graph.close()


# --------------------------------------------------------------------------- #
# E2 跨进程恢复：A 停在 interrupt → B（新实例、同一 DB）resume → paid
# --------------------------------------------------------------------------- #
def e2() -> None:
    os.environ["DEEPAGENTS_ENABLED"] = "false"
    os.environ["CLAIMS_AMOUNT_REVIEW_THRESHOLD"] = "0"
    db = _tmpdb("e2")
    thread = f"E2-{int(time.time())}"
    a = ClaimGraph(checkpoint_db=db)
    claim_id = ""
    try:
        out = a.invoke(_payload(occurred="2026-11-02T09:10:00+08:00",
                                location="北京市海淀区中关村",
                                description="变道剐蹭，右前翼子板受损"), thread_id=thread)
        claim_id = str(out.get("claim_id"))
        a_count = a.gateway.charge_count
        a.close()                                    # 模拟进程 A 退出
        b = ClaimGraph(checkpoint_db=db)             # 新实例 = 跨进程（同 DB、同 thread）
        try:
            snap = b.state(thread_id=thread)
            resumed = b.resume(
                ReviewDecision(decision="approve", comment="跨进程恢复后通过", reviewer_id="RV-0002"),
                thread_id=thread,
            )
            b_count = b.gateway.charge_count
            ok = (
                out.get("__interrupt__") is not None
                and snap.values.get("status") == Status.REVIEW_PENDING
                and resumed.get("status") == Status.PAID
                and (a_count + b_count) == 1
            )
            _check("E2 跨进程恢复（新实例同 DB resume）", ok, {
                "claim_id": claim_id,
                "process_A_charge": a_count,
                "process_B_charge": b_count,
                "total_charge": a_count + b_count,
                "status_before_resume": snap.values.get("status"),
                "status_after_resume": resumed.get("status"),
            })
        finally:
            b.close()
    finally:
        a.close()


# --------------------------------------------------------------------------- #
# E3 重复提交幂等：同 thread 再 invoke → 终态 + CLAIM_STATE_INVALID，不新增 charge
# --------------------------------------------------------------------------- #
def e3() -> None:
    os.environ["DEEPAGENTS_ENABLED"] = "false"
    os.environ["CLAIMS_AMOUNT_REVIEW_THRESHOLD"] = "3000"   # 小额快赔，无人工
    graph = ClaimGraph(checkpoint_db=_tmpdb("e3"))
    thread = f"E3-{int(time.time())}"
    try:
        first = graph.invoke(_payload(occurred="2026-11-03T10:00:00+08:00",
                                      location="上海市浦东新区", description="倒车撞柱"), thread_id=thread)
        claim_id = str(first.get("claim_id"))
        count1 = graph.gateway.charge_count
        second = graph.invoke(_payload(occurred="2026-11-03T10:00:00+08:00",
                                       location="上海市浦东新区", description="倒车撞柱"), thread_id=thread)
        codes = [str(e.get("code")) for e in (second.get("errors") or []) if isinstance(e, dict)]
        count2 = graph.gateway.charge_count
        ok = (
            first.get("status") == Status.PAID
            and second.get("status") == Status.PAID
            and ErrorCode.CLAIM_STATE_INVALID in codes
            and second.get("terminal") is True
            and count2 == count1 == 1
        )
        _check("E3 重复提交幂等（不再 charge）", ok, {
            "claim_id": claim_id,
            "status_first": first.get("status"),
            "status_second": second.get("status"),
            "second_terminal": second.get("terminal"),
            "second_error_codes": codes,
            "charge_first": count1,
            "charge_after_repeat": count2,
        })
    finally:
        graph.close()


# --------------------------------------------------------------------------- #
# E4 reject 路径 → rejected，无支付
# --------------------------------------------------------------------------- #
def e4() -> None:
    os.environ["DEEPAGENTS_ENABLED"] = "false"
    os.environ["CLAIMS_AMOUNT_REVIEW_THRESHOLD"] = "0"
    graph = ClaimGraph(checkpoint_db=_tmpdb("e4"))
    thread = f"E4-{int(time.time())}"
    try:
        out = graph.invoke(_payload(occurred="2026-11-04T15:40:00+08:00",
                                    location="广州市天河区体育西路",
                                    description="停车剐蹭，左后门凹陷"), thread_id=thread)
        claim_id = str(out.get("claim_id"))
        resumed = graph.resume(
            ReviewDecision(decision="reject", comment="材料与报案陈述不一致，拒赔", reviewer_id="RV-0003"),
            thread_id=thread,
        )
        rows = _rows(claim_id)
        kinds = _kinds(rows)
        ok = (
            resumed.get("status") == Status.REJECTED
            and graph.gateway.charge_count == 0
            and "claims.review_rejected" in kinds
            and "claims.payment_charged" not in kinds
        )
        _check("E4 reject → rejected，无支付", ok, {
            "claim_id": claim_id,
            "status_final": resumed.get("status"),
            "charge_count": graph.gateway.charge_count,
            "has_review_rejected": "claims.review_rejected" in kinds,
            "has_payment_charged": "claims.payment_charged" in kinds,
        })
    finally:
        graph.close()


# --------------------------------------------------------------------------- #
# E5 支付超时 → payment_unknown → reconcile 查单（不重发）
# --------------------------------------------------------------------------- #
def e5() -> None:
    os.environ["DEEPAGENTS_ENABLED"] = "false"
    os.environ["CLAIMS_AMOUNT_REVIEW_THRESHOLD"] = "3000"    # 自动路径，直接进支付
    gateway = MockPaymentGateway(timeout_once=True)          # 第一次 charge 抛 TimeoutError
    graph = ClaimGraph(gateway=gateway, checkpoint_db=_tmpdb("e5"))
    thread = f"E5-{int(time.time())}"
    try:
        out = graph.invoke(_payload(occurred="2026-11-05T14:30:00+08:00",
                                    location="深圳市南山区科苑路", description="被追尾"), thread_id=thread)
        claim_id = str(out.get("claim_id"))
        kinds = _kinds(_rows(claim_id))
        ops = [a["op"] for a in gateway.attempts]
        ok = (
            out.get("status") == Status.PAID
            and gateway.charge_count == 1          # 只提交过一次，没有重发
            and ops.count("query") == 1            # 查单一次
            and "claims.payment_unknown" in kinds
            and "claims.payment_reconciled" in kinds
        )
        _check("E5 支付超时→查单（不重发）", ok, {
            "claim_id": claim_id,
            "status_final": out.get("status"),
            "charge_count": gateway.charge_count,
            "gateway_ops": ops,
            "has_payment_unknown": "claims.payment_unknown" in kinds,
            "has_payment_reconciled": "claims.payment_reconciled" in kinds,
        })
    finally:
        graph.close()


# --------------------------------------------------------------------------- #
# E6 降级路径：DEEPAGENTS_ENABLED=false → rules_fallback + llm_degraded(error_type)
# --------------------------------------------------------------------------- #
def e6() -> None:
    os.environ["DEEPAGENTS_ENABLED"] = "false"
    os.environ["CLAIMS_AMOUNT_REVIEW_THRESHOLD"] = "3000"
    graph = ClaimGraph(checkpoint_db=_tmpdb("e6"))
    thread = f"E6-{int(time.time())}"
    try:
        out = graph.invoke(_payload(occurred="2026-11-06T11:00:00+08:00",
                                    location="杭州市西湖区文三路",
                                    description="掉头剐蹭，右后门受损"), thread_id=thread)
        claim_id = str(out.get("claim_id"))
        rows = _rows(claim_id)
        degraded_rows = [r for r in rows if (r.get("event") or {}).get("kind") == "claims.llm_degraded"]
        mode = ((out.get("materials_analysis") or {}).get("analyzer") or {}).get("mode")
        ev = (degraded_rows[0].get("event") if degraded_rows else {}) or {}
        ok = (
            mode == "rules_fallback"
            and out.get("analysis_degraded") is True
            and bool(degraded_rows)
            and str(ev.get("error_type") or "") != ""
        )
        _check("E6 降级路径（rules_fallback + error_type）", ok, {
            "claim_id": claim_id,
            "analyzer_mode": mode,
            "analysis_degraded": out.get("analysis_degraded"),
            "degraded_rows": len(degraded_rows),
            "error_type": ev.get("error_type"),
            "error_class": ev.get("error_class"),
            "mode_field": ev.get("mode"),
            "code": ev.get("code"),
        })
    finally:
        graph.close()


# --------------------------------------------------------------------------- #
# D 两条流水线汇合：问题 → 命中 wiki 页 → 引用 raw 行（并落轨迹）
# --------------------------------------------------------------------------- #
def wiki_link() -> None:
    os.environ["DEEPAGENTS_ENABLED"] = "false"
    os.environ["CLAIMS_AMOUNT_REVIEW_THRESHOLD"] = "3000"
    graph = ClaimGraph(checkpoint_db=_tmpdb("wiki"))
    thread = f"D-{int(time.time())}"
    try:
        out = graph.invoke(_payload(occurred="2026-11-07T09:00:00+08:00",
                                    location="成都市武侯区人民南路",
                                    description="农险作物受灾报案"), thread_id=thread)
        claim_id = str(out.get("claim_id"))
        svc = capi.ClaimService(graph)
        query = "农业保险赔付档位怎么确定"
        res = svc.wiki_check(claim_id, query, top_k=3)
        hits = res["result"]["hits"]
        top = hits[0] if hits else {}
        rows = [r for r in _rows(claim_id) if r.get("record_type") == "retrieval"]
        ok = (
            bool(hits)
            and bool(top.get("wiki_id"))
            and bool(top.get("anchor") or top.get("span"))
            and bool(rows)
            and (rows[-1].get("event") or {}).get("kind") == "claims.wiki_retrieved"
        )
        _check("D wiki 汇合（问题→页→raw 引用，且落轨迹）", ok, {
            "claim_id": claim_id,
            "query": query,
            "top_hit": {k: top.get(k) for k in ("wiki_id", "title", "anchor", "span", "verbatim")},
            "hits": len(hits),
            "grounding_rate": res["result"].get("grounding_rate"),
            "abstained": res["result"].get("abstained"),
            "trace_retrieval_rows": len(rows),
        })
    finally:
        graph.close()


SCENARIOS: dict[str, Callable[[], None]] = {
    "E1": e1, "E2": e2, "E3": e3, "E4": e4, "E5": e5, "E6": e6, "D": wiki_link,
}


# --------------------------------------------------------------------------- #
# 前置断言（A1–A3）
# --------------------------------------------------------------------------- #
def preflight() -> bool:
    traces_before = len(list(Path("traces").glob("*.jsonl"))) if Path("traces").is_dir() else 0
    report = capi.assert_preflight(strict=True)
    traces_after = len(list(Path("traces").glob("*.jsonl"))) if Path("traces").is_dir() else 0
    ok = (
        report["deepagents"] is True
        and report["wiki_entries"] > 0
        and report["trace_dir_isolated"] is True
        and traces_before == traces_after
    )
    _check("A 前置断言（解释器 / wiki / 轨迹隔离）", ok, {
        **{k: report[k] for k in ("python", "deepagents", "wiki_entries", "trace_dir",
                                  "trace_dir_isolated")},
        "traces_before": traces_before,
        "traces_after": traces_after,
    })
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F4 端到端 demo（E1–E6 + wiki 汇合）")
    parser.add_argument("--only", action="append", choices=sorted(SCENARIOS), default=None,
                        help="只跑指定场景（可重复）")
    parser.add_argument("--json", action="store_true", help="最后打印 JSON 汇总")
    args = parser.parse_args(argv)

    print("=" * 78)
    print("F4 端到端 demo  ——  模拟理赔 · 合成数据")
    print("=" * 78)
    # 幂等登记/缓存默认落在 claims/data（仓库内）。demo 每跑一次都是一批"新案件"，
    # 否则同 payload 会命中上一次的幂等键 → CLAIM_DUPLICATE（这是 CLM-02 的正常行为，
    # 但会让 E1 无法重复验证）。故默认注入一次性数据目录；轨迹仍写 traces-claims（证据留仓）。
    if not os.environ.get("CLAIMS_DATA_DIR"):
        os.environ["CLAIMS_DATA_DIR"] = tempfile.mkdtemp(prefix="f4-data-")
    started = time.time()
    if not preflight():
        print("\n前置断言未通过：按 SPEC §8.0 / D-22，拒绝继续（避免假绿）。")
        return 1

    chosen = args.only or list(SCENARIOS)
    for name in chosen:
        print(f"\n--- {name} ---")
        try:
            SCENARIOS[name]()
        except Exception as exc:  # 场景内异常也算失败，但不中断其它场景
            _check(f"{name} 未捕获异常", False, {"error": f"{type(exc).__name__}: {exc}"})

    failed = [r for r in RESULTS if not r["ok"]]
    print("\n" + "=" * 78)
    print(f"总计 {len(RESULTS)} 项，PASS {len(RESULTS) - len(failed)}，FAIL {len(failed)}，"
          f"耗时 {time.time() - started:.2f}s")
    if failed:
        print("失败项：" + ", ".join(r["id"] for r in failed))
    if args.json:
        print(json.dumps(RESULTS, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
