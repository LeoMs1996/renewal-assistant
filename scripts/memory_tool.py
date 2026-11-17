#!/usr/bin/env python3
"""记忆运维工具：查看 / 导出 / 遗忘 / 体检（对照 2026-11 基线的用户控制要求）。

子命令（依据见 reviews/memory.md §3）：
  list <owner>      active 记忆（跨会话召回会看到的内容）
  show <owner>      全部记录，含 superseded（改口留痕）/ expired（TTL 到期）
  audit <owner>     记忆变更账本（created/superseded/expired/pruned）
  export <owner>    导出 JSON（可携权，含历史与被取代条目）
  forget <owner>    硬删除全部记忆（遗忘权：条目 + 审计 + 派生物一起清）
  forget <owner> --field budget_yuan   只删单个字段
  doctor            全库体检：过期/被取代/无来源/PII 泄漏
  divergence        会话快照 vs 长期记忆 分歧清单（双侧口径对账）

依据：MediaNama 2026-08-28「删除 ≠ 遗忘」+ OpenAI Memory controls（可见/可删/可关）。
用法：.venv/bin/python scripts/memory_tool.py doctor
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import memory as memory_mod  # noqa: E402
from server import sessions as sessions_mod  # noqa: E402


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def cmd_list(owner: str) -> int:
    items = memory_mod.active_items(owner)
    if not items:
        print(f"{owner}: 无 active 记忆")
        return 0
    print(f"{owner}: {len(items)} 条 active 记忆")
    for item in items:
        print(f"  {item['field']:<22}{json.dumps(item['value'], ensure_ascii=False):<28}"
              f"{item['kind']:<11}{item['updated_at']}  ← {item['source'].get('session_id')}")
    return 0


def cmd_show(owner: str) -> int:
    _dump(memory_mod.stats(owner))
    doc = json.loads(memory_mod._path(owner).read_text(encoding="utf-8")) \
        if memory_mod._path(owner).is_file() else {"items": []}
    for item in doc.get("items", []):
        line = (f"  [{item.get('status'):<10}] {item.get('field'):<22}"
                f"{json.dumps(item.get('value'), ensure_ascii=False)}")
        if item.get("superseded_by"):
            line += f"  → 被 {item['superseded_by']} 取代（{item.get('reason')}）"
        if item.get("expires_at"):
            line += f"  TTL={item['expires_at']}"
        print(line)
    return 0


def cmd_audit(owner: str) -> int:
    doc = json.loads(memory_mod._path(owner).read_text(encoding="utf-8")) \
        if memory_mod._path(owner).is_file() else {"audit": []}
    for row in doc.get("audit", []):
        print(f"  {row['ts']}  {row['action']:<11}{row['field']:<22}{row['reason']}")
    return 0


def cmd_export(owner: str) -> int:
    _dump(memory_mod.export_owner(owner))
    return 0


def cmd_forget(owner: str, field: str | None) -> int:
    _dump(memory_mod.forget(owner, field))
    return 0


def cmd_doctor() -> int:
    report = memory_mod.doctor()
    _dump(report)
    if report["pii_leaks"]:
        print("✗ 发现 PII 泄漏文件：", report["pii_leaks"])
        return 1
    print(f"✓ 体检通过（{report['owners']} 车主 / {report['items']} 条目，"
          f"无 PII 泄漏）")
    return 0


def cmd_divergence() -> int:
    """会话快照 vs 长期记忆：对同一字段给出两个口径，差异即「记忆串味」候选。

    注意：两者**设计上**可以不同——sessions 是当前会话运行态，长期记忆是跨会话
    默认值底座（且只在显式指代时生效）。这里只做对账展示，不做自动修复。
    """
    owners = sorted(set(memory_mod.owners_list())
                    | {p.stem for p in (Path(sessions_mod._dir()).glob("*.json"))})
    rows = []
    for owner in owners:
        mem = {i["field"]: i["value"] for i in memory_mod.active_items(owner)}
        sess = []
        for path in Path(sessions_mod._dir()).glob("*.json"):
            try:
                snap = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if snap.get("owner_id") != owner:
                continue
            needs = snap.get("needs") or {}
            sess.append({k: needs.get(k) for k in
                         ("budget_yuan", "use_nature_change", "sum_insured_changes")})
        if not mem and not sess:
            continue
        rows.append({"owner": owner, "long_term": mem, "session_snapshots": sess})
    _dump(rows)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="记忆运维工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "show", "audit", "export", "forget"):
        p = sub.add_parser(name)
        p.add_argument("owner")
        if name == "forget":
            p.add_argument("--field", default=None)
    sub.add_parser("doctor")
    sub.add_parser("divergence")
    args = ap.parse_args(argv)
    if args.cmd == "doctor":
        return cmd_doctor()
    if args.cmd == "divergence":
        return cmd_divergence()
    if args.cmd == "list":
        return cmd_list(args.owner)
    if args.cmd == "show":
        return cmd_show(args.owner)
    if args.cmd == "audit":
        return cmd_audit(args.owner)
    if args.cmd == "export":
        return cmd_export(args.owner)
    return cmd_forget(args.owner, getattr(args, "field", None))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
