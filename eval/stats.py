#!/usr/bin/env python3
"""eval/stats.py — 评测统计工具（回归显著性 + 稳定性 + 基线快照）。

为什么单独成文件：run.py 只负责「跑用例、收断言」，统计判定与基线存取放在这里，
可以单独单测（tests/test_eval_tooling.py），也方便以后换基线格式而不动 runner。

2026-11 基线依据（本文件实现的判定逻辑逐条对应）：
1. Kübler et al., "When LLMs get significantly worse: A statistical approach to
   detect model degradations", arXiv:2602.10144v2 —— 结论：比较两次评测不能把两次
   准确率当独立样本（方差被高估），必须在**同一条样本上成对比较**，并对不一致的
   样本做精确单侧二项（McNemar）检验；参考实现在 lm-evaluation-harness 之上。
   → 本文件的 paired_regression()：b=基线 PASS & 本次 FAIL，c=反之，
     p = P(X>=b | n=b+c, p=0.5)，只对「翻转」的断言计数。
2. ossaihub, "Regression Eval On CI With Score Thresholds"（updated 2026-06-11）——
   CI 模式：仓库内保存 baseline.json，每次跑完与基线比，任一指标跌幅超阈值即失败；
   并明确警告「eval 集 <20 条时噪声主导」「LLM 非确定性要用 temperature=0 或多轮取中位」。
   → 本项目功能用例 19 条，正处在噪声边缘：故门禁不用「通过率跌 2pp」，
     而用成对断言级检验（见 1）+ hard 断言零容忍，避免小样本误报。
3. promptfoo, Assertions & metrics（https://www.promptfoo.dev/docs/configuration/expected-outputs/）——
   断言分「确定性/metric-graded」两类；确定性断言（tool_calls、trajectory:tool-used、
   trace-span-*）优先，因为它们可复现。
   → 本 runner 全部断言为确定性断言，本文件故只做确定性统计，不引入 LLM judge 噪声。
4. LangSmith, "Evaluate a complex agent"（docs.langchain.com/langsmith/evaluate-complex-agent）——
   Agent 评测三层：final response / trajectory / single step。
   → 基线快照按「case → 断言」两级存，等价于 trajectory+single-step 粒度。

CLI（供人工排查）：
    python eval/stats.py --baseline eval/baseline.json --current eval/results.json
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

BASELINE_SCHEMA = 1


# ---------------------------------------------------------------- 统计原语
def binom_one_sided_p(b: int, c: int) -> float:
    """精确单侧二项（McNemar 精确检验）：P(X >= b | n=b+c, p=0.5)。

    b: 基线通过、本次失败的「退化翻转」数
    c: 基线失败、本次通过的「修复翻转」数
    只有翻转样本参与计算（一致样本不提供信息），这正是 McNemar 的核心。
    b+c==0 时返回 1.0（无翻转 → 无证据）。
    """
    n = b + c
    if n == 0:
        return 1.0
    if b <= 0:
        return 1.0
    # P(X >= b) = sum_{k=b}^{n} C(n,k) / 2^n
    tail = sum(math.comb(n, k) for k in range(b, n + 1))
    return min(1.0, tail / (2 ** n))


def wilson_interval(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 置信区间：小样本通过率必然要带区间，否则 1/1 与 19/19 看起来一样。"""
    if total <= 0:
        return (0.0, 1.0)
    p = passed / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# ---------------------------------------------------------------- 结果快照
def snapshot_from_results(case_rows: list[dict], *, stamp: str, llm_mode: str,
                          repeat: int, extra: dict | None = None) -> dict:
    """把一次运行的断言明细压成基线快照（case → 断言 → bool）。

    case_rows: [{"case": "AC-01", "results": [{"desc":..., "ok":..., "hard":...}]}]
    断言用 desc 作为稳定键；同一 case 内 desc 必须唯一（lint_cases.py 会校验）。
    """
    cases: dict[str, dict] = {}
    for row in case_rows:
        cid = row["case"]
        # desc 作为稳定键；万一重名（历史用例）同义后缀保号，避免基线互相覆盖
        asserts: dict[str, bool] = {}
        hard: set[str] = set()
        for r in row["results"]:
            key = r["desc"]
            if key in asserts:
                n = 2
                while f"{key}#{n}" in asserts:
                    n += 1
                key = f"{key}#{n}"
            asserts[key] = bool(r["ok"])
            if r.get("hard"):
                hard.add(key)
        cases[cid] = {
            "pass": bool(row["results"]) and all(r["ok"] for r in row["results"]),
            "assertions": asserts,
            "hard_assertions": sorted(hard),
        }
    total_asserts = sum(len(c["assertions"]) for c in cases.values())
    passed_asserts = sum(sum(1 for v in c["assertions"].values() if v) for c in cases.values())
    snap = {
        "schema": BASELINE_SCHEMA,
        "stamp": stamp,
        "llm_mode": llm_mode,
        "repeat": repeat,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "totals": {
            "cases": len(cases),
            "cases_pass": sum(1 for c in cases.values() if c["pass"]),
            "assertions": total_asserts,
            "assertions_pass": passed_asserts,
            "hard_failures": sum(1 for c in cases.values() for d in c["hard_assertions"]
                                 if c["assertions"].get(d) is False),
        },
        "cases": cases,
    }
    if extra:
        snap.update(extra)
    return snap


def load_snapshot(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("schema") != BASELINE_SCHEMA:
        return None
    return data


def save_snapshot(path: Path, snap: dict) -> None:
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------- 回归对比
def paired_regression(baseline: dict, current: dict, alpha: float = 0.05) -> dict:
    """成对比较两次运行。

    返回结构：
      {
        "ok": bool,                 # 无显著退化、无 hard 退化
        "b": int, "c": int,         # 退化翻转 / 修复翻转（断言级，仅共同断言）
        "p_value": float,
        "alpha": float,
        "newly_failing": [...],     # 基线通过 → 本次失败的断言（按 case 聚合）
        "newly_passing": [...],
        "hard_regressions": [...],  # 基线通过的 hard 断言本次失败（零容忍）
        "new_cases": [...], "missing_cases": [...],
        "mode_mismatch": str|None,  # 规则模式 vs LLM 模式不同基线，不可比
        "note": str,
      }

    判定规则（保守，避免小样本误报）：
      - hard 断言退化 → 直接阻断（契约级：保费/越权/编造/轨迹完整性）
      - 任一断言显著退化（p < alpha 且 b > c）→ 阻断
      - 仅「通过率下降但翻转样本太少」→ 只报告，不阻断（噪声主导）
    """
    mismatch = None
    if baseline.get("llm_mode") and current.get("llm_mode") \
            and baseline["llm_mode"] != current["llm_mode"]:
        mismatch = f"基线模式={baseline['llm_mode']} vs 本次={current['llm_mode']}：不可比"

    b = c = 0
    newly_failing: list[dict] = []
    newly_passing: list[dict] = []
    hard_regressions: list[dict] = []
    base_cases = baseline.get("cases") or {}
    cur_cases = current.get("cases") or {}

    for cid in sorted(set(base_cases) & set(cur_cases)):
        ba = base_cases[cid].get("assertions") or {}
        ca = cur_cases[cid].get("assertions") or {}
        hard = set(base_cases[cid].get("hard_assertions") or [])
        for desc in sorted(set(ba) & set(ca)):
            was, now = bool(ba[desc]), bool(ca[desc])
            if was == now:
                continue
            if was and not now:
                b += 1
                item = {"case": cid, "assertion": desc}
                newly_failing.append(item)
                if desc in hard:
                    hard_regressions.append(item)
            else:
                c += 1
                newly_passing.append({"case": cid, "assertion": desc})

    p = binom_one_sided_p(b, c)
    significant = p < alpha and b > c
    ok = not hard_regressions and not significant and mismatch is None
    if mismatch:
        note = mismatch
    elif hard_regressions:
        note = f"hard 断言退化 {len(hard_regressions)} 条 → 阻断"
    elif significant:
        note = f"断言级显著退化（b={b}, c={c}, p={p:.4g} < {alpha}）→ 阻断"
    elif b > c:
        note = f"退化翻转 b={b} > 修复 c={c}，但 p={p:.4g} ≥ {alpha}：样本不足，仅提示"
    else:
        note = f"退化翻转 b={b} ≤ 修复 c={c}：无退化证据"
    return {
        "ok": ok,
        "b": b, "c": c, "p_value": p, "alpha": alpha,
        "newly_failing": newly_failing,
        "newly_passing": newly_passing,
        "hard_regressions": hard_regressions,
        "new_cases": sorted(set(cur_cases) - set(base_cases)),
        "missing_cases": sorted(set(base_cases) - set(cur_cases)),
        "mode_mismatch": mismatch,
        "note": note,
    }


def format_regression(r: dict, baseline_stamp: str = "?") -> str:
    """回归对比 → 报告小节正文（Markdown 行列表）。"""
    lines = [
        f"- 对比基线：{baseline_stamp}（成对断言级精确二项检验，McNemar）",
        f"- 退化翻转 b={r['b']} / 修复翻转 c={r['c']}，单侧 p={r['p_value']:.4g}"
        f"（α={r['alpha']}）",
        f"- 判定：{'✅ 无显著退化' if r['ok'] else '❌ 阻断 — ' + r['note']}",
    ]
    if r["mode_mismatch"]:
        lines.append(f"- ⚠️ {r['mode_mismatch']}")
    if r["hard_regressions"]:
        lines.append("- hard 断言退化：")
        lines += [f"  - `{i['case']}` · {i['assertion']}" for i in r["hard_regressions"][:10]]
    soft = [i for i in r["newly_failing"] if i not in r["hard_regressions"]]
    if soft:
        lines.append("- 其他新增失败断言：")
        lines += [f"  - `{i['case']}` · {i['assertion']}" for i in soft[:10]]
    if r["newly_passing"]:
        lines.append("- 已修复断言：")
        lines += [f"  - `{i['case']}` · {i['assertion']}" for i in r["newly_passing"][:10]]
    if r["new_cases"]:
        lines.append(f"- 新增用例（未计入对比）：{', '.join(r['new_cases'])}")
    if r["missing_cases"]:
        lines.append(f"- 基线有、本次缺失的用例：{', '.join(r['missing_cases'])}")
    return "\n".join(lines)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="成对比较两份评测快照（McNemar 精确检验）")
    ap.add_argument("--baseline", default="eval/baseline.json")
    ap.add_argument("--current", default="eval/results.json")
    ap.add_argument("--alpha", type=float, default=0.05)
    args = ap.parse_args()

    base = load_snapshot(Path(args.baseline))
    cur = load_snapshot(Path(args.current))
    if base is None or cur is None:
        print(f"快照不可用：baseline={args.baseline} current={args.current}")
        return 2
    r = paired_regression(base, cur, alpha=args.alpha)
    print(format_regression(r, base.get("stamp", "?")))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
