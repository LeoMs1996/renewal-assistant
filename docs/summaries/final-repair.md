# 终修：AC-05 选择键归一化（SPEC v1.0.1 → v1.0.2）

## 做了什么

修复 eval/report.md 最后一条 FAIL（AC-05：需求无变化时询价 2 次而期望 1 次），根因与修法：

### 根因 a）selection_key 归一化缺失
`graph.py::_build_selection` 从原保单带入各险种 sum_insured 时**包含 JQX**，而 `quote_node` 对照组基线 `base_sel` 构造时明确剔除 JQX 的 sum_insured → 同语义选择生成两个不同的 `coverage_selection_key` → 幂等/复用失效，`quote_node` 走了两路询价（新方案 + 原方案对照各一次）。

### 修法（两层）
1. **`_build_selection`**（server/graph.py:404 区域）：原保单带入 sum_insured 时跳过 `JQX`（交强险保额为法定固定值，非用户可选），与 `base_sel` 口径对齐。
2. **`_selection_key` 归一化**（server/graph.py:454 区域，防御层）：构造 key 时剔除「**等于费率表默认值**」的 sum_insured（新增 `_rate_default_sum()` 懒加载缓存 rates.json `base_premium[code].sum_insured`：JQX=200000 / YWYW=50000 / BLPS=5000）——携带默认值与缺省视为等价；**不等于默认值的 sum_insured 仍是不同入参**（保住 AC-06 改保额触发重新报价的语义）。

### 根因 b）quote 两路识别
`quote_node` 既有逻辑已正确：`base_key == key` 且无复用时 `baseline = latest`（只询价一次）；根因 a 修复后两键相等，该分支自然生效，无需改动。

## 决策依据

- SPEC §3.2 规则 2 幂等以「相同 coverage_selection」为条件，但未定义 sum_insured 缺省与携带默认值是否等价 → 属契约语义空白，按备忘 #1 先升契约：**SPEC v1.0.2** §3 报价规则新增第 7 条『选择键归一化』，并在版本行登记变更原因。
- 归一化做在 `_selection_key`（比较语义层）而非篡改报价入参：`_do_quote` 仍发送带 sum_insured 的原始 selection，报价服务端幂等键不受影响，改动面最小。
- 不在 graph 里硬编码默认值，改从 rates.json 读取（费率表升版时自动跟随）。

## 验证证据

1. **单元断言**（`.venv/bin/python` 内联脚本，5/5 过）：JQX/YWYW 默认值折叠同 key；DSX 100万 vs 200万 不同 key；CSX（费率表无默认）携带与缺省不同 key。
2. **图级专项**（真实 synthetic 数据 vin=LSVAA26E2NE100001，spy `_call_tool` 计数）：
   - AC-05（需求无变化）：`query_quote` tool_call = **1**（期望 1）✅
   - AC-06（DSX 升 200 万）：`query_quote` = **2**（新方案 + 原方案对照，期望 2）✅，且无 error
   - 同需求二次进入 quote_node：**0 次新增**（复用生效）✅
3. **eval 靶向实测**（eval/run.py，端口 8401，LLM 模式）：AC-05 **PASS 5/5**（含 tool_call=1、premium_manual hard 断言）、AC-06 **PASS 8/8**（tiers 计价、幂等 quote_version 不变、跨会话幂等）。
   - 报告：`eval/report-20261112-181630.md`
4. 既有单测 `tests/test_llm_normalization.py`：15 通过 / 0 失败（回归无损）。

## 遗留

- 规则模式 AC-06 的**既有独立缺陷**未在本任务范围：保额正则（graph.py parse_needs 附近）对「从100万升到200万」取首个数字 100 万（ROOT_CAUSES 已登记，eval/report-20261112-182425.md 可复现）。本次修复不掩盖也不加剧该问题（该缺陷下选择与基线相同 → 询价 1 次，行为与修复前语义一致）。
- 端口 8401/8402 评测子进程已随 eval 自管生命周期退出，未触碰常驻 8000。
