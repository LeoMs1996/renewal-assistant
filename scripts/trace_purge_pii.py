#!/usr/bin/env python3
"""存量轨迹 PII 清理（一次性数据治理工具）。

背景（reviews/security.md §3.2）：t9 之前轨迹是"原样落盘"，存量 900+ 个
`traces/*.jsonl` 里保留了车主姓名 / 车牌 / VIN 原文（身份证与手机号早在工具层
就被 SPEC §2 剔除，实测为 0）。写端与读端现在都已脱敏，但磁盘上的历史原文
仍属"at-rest PII"——备份、同步盘、包拷贝都会把它扩散出去。

本工具用与运行时完全相同的 `server.security.redact_row()` 就地重写存量文件，
保证「脱敏语义单一来源」，不会出现两套正则漂移。

用法：
  .venv/bin/python scripts/trace_purge_pii.py                 # 只统计（dry-run）
  .venv/bin/python scripts/trace_purge_pii.py --apply         # 就地重写
  .venv/bin/python scripts/trace_purge_pii.py --apply --dir traces
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import security  # noqa: E402

# 与 security 模块同源的脱敏语义：这里只做"是否还有命中"的判定
PII_PROBES = {
    "姓名": "张伟",
    "车牌": "沪AD12345",
    "VIN": "LSVAA26E2NE100001",
    "另一个姓名": "李静",
}


def purge_file(path: Path, apply: bool) -> tuple[bool, int]:
    rows, changed = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        clean = security.redact_row(row)
        if clean != row:
            changed += 1
        rows.append(clean)
    if apply and changed:
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        path.write_text(text, encoding="utf-8")
        path.chmod(0o600)
    return changed > 0, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="traces")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    target = Path(args.dir)
    if not target.is_absolute():
        target = ROOT / target
    files = sorted(target.glob("*.jsonl"))
    if not files:
        print(f"{target} 下没有轨迹文件")
        return 0

    dirty_files, dirty_rows, probes_before = 0, 0, {k: 0 for k in PII_PROBES}
    for path in files:
        text = path.read_text(encoding="utf-8")
        for label, probe in PII_PROBES.items():
            if probe in text:
                probes_before[label] += 1
        changed, rows = purge_file(path, args.apply)
        if changed:
            dirty_files += 1
            dirty_rows += rows

    mode = "已就地重写" if args.apply else "dry-run（未写盘，加 --apply 生效）"
    print(f"扫描 {len(files)} 个轨迹文件 · {mode}")
    print(f"含 PII 的文件 {dirty_files} 个 / 记录 {dirty_rows} 行")
    print("清理前命中文件数：" + "，".join(f"{k}={v}" for k, v in probes_before.items()))
    if args.apply:
        after = {k: sum(1 for p in files if k_probe in p.read_text(encoding='utf-8'))
                 for k, k_probe in PII_PROBES.items()}
        print("清理后命中文件数：" + "，".join(f"{k}={v}" for k, v in after.items()))
        if any(after.values()):
            print("仍有残留，请检查脱敏规则", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
