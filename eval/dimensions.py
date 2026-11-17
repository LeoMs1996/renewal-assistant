#!/usr/bin/env python3
"""eval/dimensions.py — 评测维度分类法（覆盖矩阵的唯一来源）。

为什么需要它：19 条用例「全绿」并不说明评测充分，只说明已写下的断言都过了。
要回答「维度是否覆盖」，必须先有一张显式的维度表，再由断言反查每个维度的样本量。

分类法依据（2026-11 检索，非训练记忆）：
- LangSmith《Evaluate a complex agent》：Agent 评测分三层 —— final response /
  trajectory / single step。→ 本表把 trajectory 单列一维（`trajectory`），
  final response 的**确定性可观测部分**归 `contract`（不判措辞质量，见 KNOWN_GAPS）。
- promptfoo《Assertions & metrics》：确定性断言（tool_calls / trajectory:tool-used /
  trace-span-*）与 model-graded 断言分开。→ 本表只映射确定性断言；
  model-graded（LLM judge）维度列入 KNOWN_GAPS 并注明为何暂不引入。
- 项目 SPEC v1.0.4 的硬规矩（保费只能来自报价服务、越权=硬失败、轨迹可回放）
  → `pricing` / `security` / `privacy` / `observability` 必须各有独立维度与 hard 断言。

维护约定：
- 新增断言器时必须同时登记 dims（lint_cases.py 会校验 ASSERT 注册表与 DIM_OF 一致）。
- 维度没有断言时，必须在 KNOWN_GAPS 写明原因与计划，否则 lint 报 ERROR（禁止静默缺维）。
"""
from __future__ import annotations

# 维度定义：key → (中文名, 说明)
DIMENSIONS: dict[str, tuple[str, str]] = {
    "contract": ("契约/功能正确性", "SPEC §3–§4 的功能断言：事件流、字段、纠错码、错误码"),
    "trajectory": ("轨迹与工具调用", "工具被调用的次数/顺序/入参范围（LangSmith trajectory 层）"),
    "pricing": ("数值正确性", "保费逐行与 rates.json 独立手算一致；不得编造"),
    "idempotency": ("幂等与一致性", "quote_id/order_id 幂等、quote_version、跨会话复用"),
    "rag": ("检索与引用", "BM25 命中 Top-N、citation 带来源与版本"),
    "security": ("安全（注入/越权）", "OWASP LLM01 注入、BOLA 越权、路径穿越"),
    "privacy": ("隐私与脱敏", "身份证/手机号零泄漏、出参剔除敏感字段"),
    "compliance": ("合规话术", "模拟报价/合成数据免责声明必须保留"),
    "observability": ("可观测性", "轨迹文件存在、seq 连续、GET /trace 可回放"),
    "performance": ("性能预算", "单轮对话端到端耗时上限（防挂死/退化）"),
}

# 断言器 type → 维度（与 run.ASSERT 注册表必须一一对应，lint 校验）
DIM_OF: dict[str, str] = {
    # 契约
    "tool_result_path": "contract",
    "sse_has": "contract",
    "sse_absent": "contract",
    "sse_done": "contract",
    "correction": "contract",
    "api_status": "contract",
    "api_path": "contract",
    "api_path_nonempty": "contract",
    "api_error_code": "contract",
    "line_items_codes": "contract",
    # 轨迹与工具调用
    "tool_calls": "trajectory",
    "tool_input_scope": "trajectory",
    # 数值正确性
    "premium_manual": "pricing",
    "quote_line_path": "pricing",
    "quote_event_path": "pricing",
    "quote_factor": "pricing",
    # 幂等与一致性
    "idem_quote": "idempotency",
    "order_idempotent": "idempotency",
    "quote_fresh": "idempotency",
    # 检索与引用
    "retrieval_hit": "rag",
    "citation": "rag",
    # 安全
    "message_not_contains": "security",
    # 隐私
    "no_pii": "privacy",
    "api_key_absent": "privacy",
    # 合规话术
    "message_contains": "compliance",
    # 可观测性
    "traces_replayable": "observability",
    # 性能
    "latency_budget": "performance",
}

# 已知缺口：维度没有（或只有很弱）自动化断言时，必须在这里写明原因与计划。
# lint_cases.py 对「无断言且无缺口说明」的维度报 ERROR。
KNOWN_GAPS: dict[str, str] = {
    "compliance": "仅 AC/SEC 的免责声明关键词断言（message_contains），非语义级判定；"
                  "语义级需 LLM judge（见下条），暂以关键词兜底",
    "performance": "latency_budget 为软预算（默认 60s，非 hard），只拦「挂死/严重退化」；"
                   "P95/成本预算需多轮采样与 token 统计，LLM 模式凭证恢复后再补",
}

# 明确不引入的维度及原因（避免评审时被重复追问）
EXCLUDED_DIMENSIONS: dict[str, str] = {
    "llm_judge_quality": "话术质量/语义相关性 → 需 model-graded 断言（promptfoo llm-rubric / "
                         "LangSmith LLM-as-judge）。本项目断言纪律是「只读确定性证据，不读对话文字」，"
                         "引入 judge 会同时引入判定噪声与外部模型依赖；列为 P2 改进，"
                         "前置条件：LLM 凭证稳定 + judge 校准集（人工标注 ≥30 条）",
    "cost": "token 成本：llm_response 轨迹已记录 usage，但演示项目无预算契约，"
            "且规则模式无 token 消耗；正式化需先定预算口径",
}


def case_dimensions(assertions: list[dict]) -> set[str]:
    """由断言类型反查本用例覆盖的维度（未知类型忽略，由 lint 负责报错）。"""
    return {DIM_OF[a["type"]] for a in assertions if a.get("type") in DIM_OF}


def dimension_matrix(case_rows: list[dict]) -> list[dict]:
    """汇总维度覆盖矩阵。

    case_rows: [{"case": "AC-01", "results": [{"desc":..., "ok":..., "hard":...}]}]
    返回 [{dim, name, cases:[...], assertions:int, passed:int, failed:int, hard_failed:int}]
    """
    rows: dict[str, dict] = {
        d: {"dim": d, "name": DIMENSIONS[d][0], "cases": [], "assertions": 0,
            "passed": 0, "failed": 0, "hard_failed": 0}
        for d in DIMENSIONS
    }
    for row in case_rows:
        for r in row["results"]:
            dim = DIM_OF.get(r.get("assert_type") or "") or DIM_OF.get(r.get("type") or "")
            if dim is None:
                continue
            slot = rows[dim]
            slot["assertions"] += 1
            slot["passed" if r["ok"] else "failed"] += 1
            if not r["ok"] and r.get("hard"):
                slot["hard_failed"] += 1
            if row["case"] not in slot["cases"]:
                slot["cases"].append(row["case"])
    return [rows[d] for d in DIMENSIONS]


def format_matrix(matrix: list[dict]) -> str:
    """覆盖矩阵 → Markdown 表格正文（行列表）。"""
    lines = ["| 维度 | 断言数 | 通过 | 失败 | hard 失败 | 覆盖用例 |",
             "|---|---|---|---|---|---|"]
    for m in matrix:
        if m["assertions"] == 0:
            gap = KNOWN_GAPS.get(m["dim"])
            covered = f"—（缺口：{gap}）" if gap else "—（⚠️ 无断言且无缺口说明）"
            lines.append(f"| {m['name']} `{m['dim']}` | 0 | 0 | 0 | 0 | {covered} |")
        else:
            lines.append(f"| {m['name']} `{m['dim']}` | {m['assertions']} | {m['passed']} "
                         f"| {m['failed']} | {m['hard_failed']} | {', '.join(m['cases'])} |")
    return "\n".join(lines)
