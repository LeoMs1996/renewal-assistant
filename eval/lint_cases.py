#!/usr/bin/env python3
"""eval/lint_cases.py — 用例静态校验（case 设计质量门禁）。

为什么需要它（2026-11 检索依据）：
- promptfoo《Assertions & metrics》把断言分为确定性/metric-graded 两类，断言必须**声明式**
  且参数完整；本项目断言器是手工注册表（run.ASSERT），一个拼错的 type 会在运行时抛
  KeyError 被计为 FAIL，看起来像"产品缺陷"，实际是"用例缺陷"——这类噪声必须前置拦截。
- ossaihub《Regression Eval On CI With Score Thresholds》警告 eval 集小时噪声主导；
  噪声的主要来源之一就是坏用例，而不是被测系统。
- 本项目基线快照用「case + 断言 desc」作为稳定键（eval/stats.py），desc 重名会导致
  基线覆盖丢失 → 本 lint 强制同 case 内 desc 唯一。

检查项（ERROR 阻断 CI，WARN 仅提示）：
  E1 文件名与 id 不一致 / id 格式非法 / id 重复
  E2 缺字段（id/title/spec/steps/assertions）
  E3 step 结构非法（未知 kind、缺必填字段、label 重复）
  E4 断言 type 未在 run.ASSERT 注册表登记
  E5 断言参数缺失（按 ASSERTS_SCHEMA）或引用了不存在的 turn/api label
  E6 同一 case 内断言 desc 重复（基线键冲突）
  E7 断言 type 未在 dimensions.DIM_OF 登记（维度覆盖会静默丢样本）
  E8 SPEC 验收清单（§7 表格 AC-xx/SEC-xx）与 cases/ 文件互相漂移
  W1 对抗用例没有任何 hard 断言（防线单薄）
  W2 维度无任何断言且未在 KNOWN_GAPS 说明
  W3 用例无 spec/notes 说明（可追溯性弱）

用法：
    python eval/lint_cases.py                 # 人读输出
    python eval/lint_cases.py --json          # 机器读（CI 归档）
退出码：有 ERROR → 1，否则 0。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVAL_DIR))

# 直接按路径加载同目录模块（eval/ 不是 package）
def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"eval_{name}", EVAL_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


run = _load("run")
dims = _load("dimensions")

CASE_ID_RE = re.compile(r"^(AC|SEC)-\d{2}$")
STEP_KINDS = {"chat", "api", "expired_quote", "requote"}

# 每种断言器的必填参数（与 run.py 里各 a_* 函数读取的键一一对应）
ASSERTS_SCHEMA: dict[str, dict] = {
    "tool_calls": {"required": ["turn", "tool", "count"], "turn": True},
    "tool_result_path": {"required": ["turn", "tool", "path", "value"], "turn": True},
    "sse_has": {"required": ["turn", "event"], "turn": True},
    "sse_absent": {"required": ["turn", "event"], "turn": True},
    "sse_done": {"required": ["turn"], "turn": True, "one_of": [("reason", "reason_any")]},
    "line_items_codes": {"required": ["turn", "index", "codes"], "turn": True},
    "quote_line_path": {"required": ["turn", "index", "code", "path", "value"], "turn": True},
    "quote_event_path": {"required": ["turn", "index", "path", "value"], "turn": True},
    "quote_factor": {"required": ["turn", "path", "value"], "turn": True},
    "idem_quote": {"required": ["turn_a", "turn_b"], "turn": True},
    "premium_manual": {"required": ["turn"], "turn": True},
    "retrieval_hit": {"required": ["turn", "wiki_id"], "turn": True},
    "citation": {"required": ["turn", "wiki_id"], "turn": True},
    "message_contains": {"required": ["turn"], "turn": True, "one_of": [("contains", "any_of")]},
    "message_not_contains": {"required": ["turn"], "turn": True,
                             "one_of": [("contains", "any_of")]},
    "tool_input_scope": {"required": ["turn", "tool", "key", "allow"], "turn": True},
    "correction": {"required": ["turn", "code"], "turn": True},
    "api_status": {"required": ["label", "code"], "api": True},
    "api_path": {"required": ["label", "path", "value"], "api": True},
    "api_path_nonempty": {"required": ["label", "path"], "api": True},
    "api_key_absent": {"required": ["label", "path"], "api": True},
    "api_error_code": {"required": ["label", "code"], "api": True},
    "no_pii": {"required": []},
    "order_idempotent": {"required": ["label_a", "label_b"], "api": True},
    "quote_fresh": {"required": ["label_a", "label_b"]},
    "traces_replayable": {"required": []},
    "latency_budget": {"required": ["turn", "budget_ms"], "turn": True},
}


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def err(self, code: str, where: str, msg: str) -> None:
        self.items.append({"level": "ERROR", "code": code, "where": where, "msg": msg})

    def warn(self, code: str, where: str, msg: str) -> None:
        self.items.append({"level": "WARN", "code": code, "where": where, "msg": msg})

    @property
    def errors(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "ERROR"]

    @property
    def warnings(self) -> list[dict]:
        return [i for i in self.items if i["level"] == "WARN"]


def lint_case(path: Path, rep: Report) -> dict | None:
    where = path.name
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.err("E2", where, f"JSON 解析失败: {type(exc).__name__}: {exc}")
        return None
    if not isinstance(case, dict):
        rep.err("E2", where, "顶层不是对象")
        return None

    # E2 必填字段
    for key in ("id", "title", "spec", "steps", "assertions"):
        if key not in case:
            rep.err("E2", where, f"缺字段 {key}")
    cid = case.get("id", "")
    if not CASE_ID_RE.match(cid or ""):
        rep.err("E1", where, f"id 格式非法：{cid!r}（期望 AC-xx / SEC-xx）")
    if cid and path.name != f"{cid}.json":
        rep.err("E1", where, f"文件名与 id 不一致（id={cid}）")
    if not case.get("steps") and cid != "AC-14":
        rep.warn("W3", where, "steps 为空（仅轨迹类用例可接受）")
    if not case.get("spec"):
        rep.warn("W3", where, "缺 spec 依据说明")

    # E3 step 结构
    labels: set[str] = set()
    turns: set[str] = set()
    apis: set[str] = set()
    for i, st in enumerate(case.get("steps") or []):
        kind = st.get("kind")
        if kind not in STEP_KINDS:
            rep.err("E3", where, f"steps[{i}] 未知 kind={kind!r}")
            continue
        label = st.get("label")
        if not label:
            rep.err("E3", where, f"steps[{i}] 缺 label")
            continue
        if label in labels:
            rep.err("E3", where, f"steps[{i}] label 重复：{label}")
        labels.add(label)
        if kind == "chat":
            turns.add(label)
            for key in ("session", "owner", "message"):
                if not st.get(key):
                    rep.err("E3", where, f"steps[{i}]({label}) chat 缺 {key}")
        elif kind == "api":
            apis.add(label)
            for key in ("method", "path"):
                if not st.get(key):
                    rep.err("E3", where, f"steps[{i}]({label}) api 缺 {key}")
        else:  # expired_quote / requote
            if not st.get("owner"):
                rep.err("E3", where, f"steps[{i}]({label}) {kind} 缺 owner")

    # E4/E5/E6/E7 断言
    seen_desc: dict[str, int] = {}
    for i, a in enumerate(case.get("assertions") or []):
        atype = a.get("type")
        if atype not in run.ASSERT:
            rep.err("E4", where, f"assertions[{i}] type={atype!r} 未在 run.ASSERT 注册")
            continue
        if atype not in dims.DIM_OF:
            rep.err("E7", where, f"assertions[{i}] type={atype!r} 未登记维度（dimensions.DIM_OF）")
        schema = ASSERTS_SCHEMA.get(atype)
        if schema is None:
            rep.err("E5", where, f"assertions[{i}] type={atype!r} 缺 lint schema 定义")
            schema = {"required": []}
        for key in schema.get("required", []):
            if key not in a:
                rep.err("E5", where, f"assertions[{i}]({atype}) 缺参数 {key}")
        for group in schema.get("one_of", []):
            if not any(k in a for k in group):
                rep.err("E5", where, f"assertions[{i}]({atype}) 需至少其一：{group}")
        if schema.get("turn"):
            refs = [a[k] for k in ("turn", "turn_a", "turn_b") if a.get(k)]
            for ref in refs:
                if ref not in turns:
                    rep.err("E5", where, f"assertions[{i}]({atype}) 引用不存在的 turn={ref!r}")
        if schema.get("api"):
            refs = [a[k] for k in ("label", "label_a", "label_b") if a.get(k)]
            for ref in refs:
                if ref not in apis:
                    rep.err("E5", where, f"assertions[{i}]({atype}) 引用不存在的 api label={ref!r}")
        # E6 desc 唯一（基线键）
        desc = a.get("desc") or atype
        seen_desc[desc] = seen_desc.get(desc, 0) + 1
        if seen_desc[desc] == 2:
            rep.err("E6", where, f"断言 desc 重复：{desc!r}（基线快照会互相覆盖，请显式写 desc）")

    # W1 对抗用例防线
    asserts = case.get("assertions") or []
    if case.get("adversarial"):
        if not any(a.get("hard") for a in asserts):
            rep.warn("W1", where, "对抗用例无 hard 断言（退化不会阻断）")
    elif not any(a.get("acceptance") or a.get("hard") for a in asserts) and not asserts:
        rep.warn("W1", where, "用例没有任何断言")
    return case


def lint_spec_coverage(cases: list[dict], rep: Report) -> None:
    """E8：SPEC §7 验收清单 ↔ eval/cases/ 双向对齐。"""
    spec_path = ROOT / "SPEC.md"
    if not spec_path.is_file():
        rep.warn("W3", "SPEC.md", "SPEC 不存在，跳过验收清单对齐检查")
        return
    text = spec_path.read_text(encoding="utf-8")
    declared = set(re.findall(r"^\|\s*((?:AC|SEC)-\d{2})\s*\|", text, flags=re.M))
    implemented = {c.get("id") for c in cases if c.get("id")}
    for cid in sorted(declared - implemented):
        rep.err("E8", "SPEC.md", f"SPEC 声明 {cid} 但 eval/cases/ 无对应用例")
    for cid in sorted(implemented - declared):
        rep.err("E8", f"cases/{cid}.json", f"用例 {cid} 未在 SPEC §7 验收清单登记（契约漂移）")


def lint_dimension_coverage(cases: list[dict], rep: Report) -> list[str]:
    """W2：维度必须有断言，或必须在 KNOWN_GAPS 说明。返回缺口维度列表。"""
    covered: set[str] = set()
    for c in cases:
        covered |= dims.case_dimensions(c.get("assertions") or [])
    gaps = []
    for dim in dims.DIMENSIONS:
        if dim in covered:
            continue
        gaps.append(dim)
        if dim in dims.KNOWN_GAPS:
            rep.warn("W2", "dimensions", f"维度 {dim} 无用例，已登记缺口说明")
        else:
            rep.err("W2", "dimensions", f"维度 {dim} 无任何断言且未在 KNOWN_GAPS 说明")
    # 反向：断言器/维度表漂移
    for atype in run.ASSERT:
        if atype not in dims.DIM_OF:
            rep.err("E7", "dimensions", f"断言器 {atype} 未登记维度")
    for atype in dims.DIM_OF:
        if atype not in run.ASSERT:
            rep.err("E7", "dimensions", f"维度表登记了不存在的断言器 {atype}")
        if dims.DIM_OF[atype] not in dims.DIMENSIONS:
            rep.err("E7", "dimensions", f"断言器 {atype} 映射到未定义维度")
    return gaps


def main() -> int:
    ap = argparse.ArgumentParser(description="eval 用例静态校验")
    ap.add_argument("--cases", default=str(ROOT / "eval" / "cases"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = Report()
    cases: list[dict] = []
    files = sorted(Path(args.cases).glob("*.json"))
    ids: dict[str, str] = {}
    for path in files:
        case = lint_case(path, rep)
        if not case:
            continue
        cases.append(case)
        cid = case.get("id")
        if cid in ids:
            rep.err("E1", path.name, f"id 重复：{cid}（另见 {ids[cid]}）")
        else:
            ids[cid or path.name] = path.name

    lint_spec_coverage(cases, rep)
    gaps = lint_dimension_coverage(cases, rep)

    summary = {
        "cases": len(cases),
        "assertions": sum(len(c.get("assertions") or []) for c in cases),
        "errors": len(rep.errors),
        "warnings": len(rep.warnings),
        "dimension_gaps": gaps,
        "items": rep.items,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        for item in rep.items:
            icon = "❌" if item["level"] == "ERROR" else "⚠️"
            print(f"{icon} [{item['code']}] {item['where']}: {item['msg']}")
        print(f"\n用例 {summary['cases']} 条 / 断言 {summary['assertions']} 条 / "
              f"ERROR {summary['errors']} / WARN {summary['warnings']}")
        if gaps:
            print(f"维度缺口（已在 KNOWN_GAPS 或待补）：{', '.join(gaps)}")
        print("lint 通过" if not rep.errors else "lint 失败：存在 ERROR")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
