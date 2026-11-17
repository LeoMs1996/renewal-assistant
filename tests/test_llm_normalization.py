#!/usr/bin/env python3
"""单元测试：修复Agent P0/P1b 回归（评审 review.md 根因）。

- P0：llm.normalize_tool_json 把 "null"/"None"/"" 字符串哨兵归一化为 None
      （LLM 模式 AC-01/03/05/06/13 全灭的根因）。
- P1b：quote_id 序号持久化，跨进程（模拟重启）不撞号（AC-12）。

运行：.venv/bin/python tests/test_llm_normalization.py   （退出码 0 = 全部通过）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.llm import normalize_tool_json  # noqa: E402

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    print(f"  {'✓' if cond else '✗'} {label}")
    PASS, FAIL = PASS + (1 if cond else 0), FAIL + (0 if cond else 1)


print("== P0：normalize_tool_json 可空字段字符串哨兵归一化 ==")

# 评审一手取证的场景：GLM 把 use_nature_change 序列化为字符串 "null"
raw = {
    "budget_yuan": "null",
    "sum_insured_changes": [],
    "add_coverages": [],
    "remove_coverages": [],
    "use_nature_change": "null",
    "terms_question": False,
}
got = normalize_tool_json(raw)
check(got["use_nature_change"] is None, 'use_nature_change "null" → None（轨迹 seq19 根因）')
check(got["budget_yuan"] is None, 'budget_yuan "null" → None')

# 其它大小写 / 变体
g2 = normalize_tool_json({"use_nature_change": "None", "budget_yuan": "NONE",
                          "note": " ", "k": "nil"})
check(g2["use_nature_change"] is None and g2["budget_yuan"] is None, '"None"/"NONE" → None')
check(g2["note"] is None and g2["k"] is None, '空白串 / "nil" → None')

# 非哨兵字符串必须原样保留（不得误伤正常值）
g3 = normalize_tool_json({
    "use_nature_change": "网约车（营运）",
    "budget_yuan": 5000,
    "note": "nullification is not a sentinel here",
    "flag": True,
    "none": None,
})
check(g3["use_nature_change"] == "网约车（营运）", "正常字符串保留")
check(g3["budget_yuan"] == 5000 and g3["flag"] is True and g3["none"] is None,
      "数值/布尔/真 None 不变")
check(g3["note"] == "nullification is not a sentinel here", "仅完全等于哨兵的字符串才转 None")

# 嵌套结构（list / dict 递归）
g4 = normalize_tool_json({"changes": [{"code": "DSX", "sum_insured": "null"}],
                          "extra": [{"deep": ["None"]}]})
check(g4["changes"][0]["sum_insured"] is None and g4["extra"][0]["deep"][0] is None,
      "嵌套 list/dict 递归归一化")

# 深度防御与 None 容器
check(normalize_tool_json(None) is None, "None 原样返回")

# chat_tool_json 在规则模式（无凭证客户端）仍返回 (None, None) 不崩
from server.llm import LLMClient  # noqa: E402

c = LLMClient.__new__(LLMClient)  # 绕过 __init__（不读 .env，避免真实凭证）
c.base_url, c.token, c.model, c.available, c._client = "", "", "", False, None
check(c.chat_tool_json("s", [], "t", "d", {}) == (None, None), "规则模式客户端降级返回 (None,None)")

print("== P1b：quote_id 序号持久化（跨进程不撞号，AC-12） ==")

_SNIPPET = r'''
import sys, json
sys.path.insert(0, %r)
from mcp_servers import quote_server as qs
sel_a = [{"code": "JQX"}, {"code": "DSX", "sum_insured": 2000000}]
sel_b = [{"code": "JQX"}, {"code": "DSX", "sum_insured": 3000000}]
ra = qs._query_quote_impl(vin="LSVAA26E2NE100001", coverage_selection=sel_a)
rb = qs._query_quote_impl(vin="LSVAA26E2NE100001", coverage_selection=sel_b)
print(json.dumps([ra["quote_id"], rb["quote_id"]]))
''' % str(ROOT)

# 进程 1（模拟首次运行）
out1 = subprocess.run([sys.executable, "-c", _SNIPPET], capture_output=True, text=True, cwd=str(ROOT))
check(out1.returncode == 0, f"子进程1运行成功（stderr 尾: {out1.stderr[-120:] if out1.returncode else ''}）")
ids1 = eval(out1.stdout.strip().splitlines()[-1]) if out1.returncode == 0 else []
# 进程 2（模拟重启：内存计数器归零，必须从持久化序号续号）
out2 = subprocess.run([sys.executable, "-c", _SNIPPET], capture_output=True, text=True, cwd=str(ROOT))
check(out2.returncode == 0, "子进程2（重启模拟）运行成功")
ids2 = eval(out2.stdout.strip().splitlines()[-1]) if out2.returncode == 0 else []

all_ids = [i for i in (ids1 + ids2) if i]
check(len(all_ids) == 4 and len(set(all_ids)) == 4,
      f"4 个 quote_id 全局唯一（跨进程不撞号）：{all_ids}")
check(all(i.startswith("QT-") for i in all_ids), "quote_id 格式 QT-YYYYMMDD-NNNN")
seq_file = ROOT / "traces" / "quote_seq.json"
check(seq_file.is_file(), f"序号文件已持久化：{seq_file.name}")

print(f"\n结果：{PASS} 通过 / {FAIL} 失败")
sys.exit(1 if FAIL else 0)
