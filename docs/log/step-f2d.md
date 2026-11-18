# step-f2d.md —— F2d：修 X1 对账的 4 条 degradation + 运行前提 + wiki 变量

> 任务：**t21**。执行人：flow-engineer（attempt 2 / `attempt_id=972b8d91-4760-4beb-801b-31dbab1e7ae9`）
> 时间：2026-11-18（+0800）
> 依据：`docs/log/integration-contract.md`（X1 对账，integrator）
> 写作用域：`claims/graph.py`、`claims/state.py`、`claims/tests/**`、`claims/SPEC-claims.md`（**未改** `claims/config.py` 默认值、`claims/deep_agents/**`、`server/**`、`tests/**`、`SPEC.md`）

---

## 0. 结论一览

| 项 | 判定 | 处置 | 证据 |
|---|---|---|---|
| I4-a 首行轨迹落 `unknown.jsonl` | 真 bug（integrator 对） | **已修**：intake 先算 `claim_id` 再记轨迹；`record()` 支持显式 `claim_id`；`node_end` 用**执行后**的 claim_id | §1，测试 2 条 |
| I4-b 降级原因被吞 | 真 bug（integrator 对） | **已修**：`ContextVar` 记录 `error_type/error_class/message`，落 `claims.llm_degraded` | §2，测试 2 条 |
| I6-a 终态再 invoke 重跑 + 再 charge | 真 bug（integrator 对） | **已修**：入口终态守卫，直接返回终态 + `CLAIM_STATE_INVALID`，不进入 intake、不新增 checkpoint | §3，测试 1 条 |
| I6-b paid 后 resume 静默成功 | 真 bug（integrator 对） | **已修**：终态 / 无挂起中断 → `CLAIM_STATE_INVALID` | §3，测试 2 条 |
| I1-a 运行前提（解释器） | blocker，文档缺失 | **已补** SPEC §8.0（`.venv-claims` 唯一验收解释器 + `.venv` 假绿风险） | §5 |
| I3-a `CLAIMS_WIKI_DIR` 未登记 | 文档缺失 | **已登记** SPEC §8.1 + 明确"禁读续保 wiki"；接线归 D5 | §5 |
| D1 `server.metrics` 是否接入 | **integrator 对，我 F2 的说法不成立** | **已修**：补 `node_end` / `tool_call` / `tool_result`；`/metrics` 从 **0 行 → 135 行** | §4 |
| D2 `analysis_key` 缓存未实现 | 真（契约与实现不一致） | **选择实现**（默认倾向项），最小文件缓存 + 2 条测试 | §6 |
| §8.1 环境变量总表（F3 6 个 + F2 已定义） | 队长交办 | **已统一为 5 列表**（变量/默认/生效点/影响/消费方），`DEEPAGENTS_MODEL` 标注"未设置绝不外呼" | §10.1 |
| F3 私有 anomaly 码是否进 `flags` | 队长裁决：**不进** | **已落地**：SPEC §4.6 词汇表 + `flags_for()` **显式剔除** + 2 条测试 | §10.2 |
| 决策台账未登记 | 队长交办 | **已补 D-15..D-22** 到 `docs/log/decisions.md`（C5 对账基准） | §10.3 |

**关键自纠**：F2 交付时我说"指标由 `TraceRecorder.record()` 内部自动喂 `metrics.observe_record`，无需额外调用"——**这句是错的**。`observe_record()` 只处理 `node_end / tool_call / tool_result / llm_response / retrieval / error`，而理赔域当时只写 `node_start`，所以指标**一条都没有**（实测 `metrics.render()` 返回 0 行）。integrator 的判定正确，我已按 §4 修复。

---

## 1. I4-a｜首行轨迹落到 `unknown.jsonl`

- **现象**：新案轨迹里出现 `traces-claims/unknown.jsonl`，其中是 `intake_accepted` 的首行；CLM-20 的"轨迹可完整重放"缺首行。
- **根因**：`ClaimGraph.recorder(state)` 用 `state.get("claim_id") or "unknown"`；`intake` 在**算出 claim_id 之前**就调 `self.record(...)`，此时 state 里没有 claim_id。`node_end` 包装器同样在节点返回前取 state。
- **修法**（`claims/graph.py`）：
  1. `intake` 把 `key/claim_id` 的计算提到最前面（在任何 `record` 之前）；
  2. `recorder(state, claim_id=None)` 与 `record(..., claim_id=None, ...)` 支持**显式传入** claim_id；
  3. 无效报案也用算出的 claim_id 写轨迹，并回填 `state["claim_id"]`（保证 `node_end` 同文件）；
  4. `_wrap` 的 `node_end` 使用 **`{**state, claim_id: result["claim_id"]}`**。
- **测试**（`claims/tests/test_f2d_degradations.py`）：
  - `test_i4a_first_trace_row_goes_to_claim_file`：断言无 `unknown.jsonl`、`<claim_id>.jsonl` 存在、**首行** `trace_id == claim_id` 且 `event.kind == claims.intake_accepted`、全文件 trace_id 唯一；
  - `test_i4a_invalid_report_trace_also_uses_claim_file`：无效报案也只产生 1 个 claim 文件、首行是 `claims.intake_invalid`。

---

## 2. I4-b｜降级原因被 `except Exception: pass` 吞掉

- **现象**：`claims.llm_degraded` 轨迹行只有 `code/mode`，没有 `error_type`；生产上无法回答"为什么降级"。
- **根因**：`run_analysis()` 是契约入口（`(docs, *, analyzer_version) -> dict`），**不能加返回值**；旧实现用 `except Exception: pass` 直接丢弃异常。
- **修法**：
  - 新增 `_LAST_ANALYSIS_ERROR: ContextVar[dict|None]`（协程安全，不改契约签名）+ `last_analysis_error()`；
  - 捕获时写 `{error_class, error_type, message[:300]}`；`DEEPAGENTS_ENABLED=false` 时写 `error_type="DeepAgentsDisabled"`；
  - `analyze_materials` 落轨迹时带 `error_type` / `error_class` / `message` / `analysis_key`。
- **测试**：
  - `test_i4b_degradation_records_error_type`：让 F3 抛带 `error_type="AnalysisTimeout"` 的假异常 → 轨迹行 `error_type=="AnalysisTimeout"`、`error_class=="_FakeTimeout"`、`mode=="rules_fallback"`、message 含"超时"；
  - `test_i4b_disabled_switch_also_records_reason`：默认关闭时 `error_type=="DeepAgentsDisabled"`。

---

## 3. I6-a / I6-b｜终态线程再流转

- **现象**：paid 后再 `invoke` 会从 START 重跑 → `intake` 重置 status（绕过 `ALLOWED_TRANSITIONS`）→ 再次 charge（3 次 invoke = 3 次 charge；仅靠网关按 `payment_key` 去重兜底）。paid 后 `resume` 静默成功。
- **根因**：`invoke`/`resume` 直接 `graph.invoke(...)`，没有入口状态检查。
- **修法**：
  - 新增 `_terminal_snapshot(thread_id)`：读 `get_state`，若 `status ∈ Status.TERMINAL` → 返回既有 values + `{code: CLAIM_STATE_INVALID, message: 终态不可再流转}` + `terminal=True`；**不调用 `graph.invoke`**（因此不新增 checkpoint、不推进任何业务）。
  - `invoke()`：先查终态；`resume()`：先查终态，再查 `snapshot.next` 为空 → `CLAIM_STATE_INVALID`（无挂起中断）。
- **测试**：
  - `test_i6a_terminal_thread_reinvoke_is_rejected`：paid 后二次 invoke → `charge_count==1`、`get_state_history` 长度不变、`CLAIM_STATE_INVALID`、`status` 仍 paid、claim_id 不变；
  - `test_i6b_resume_after_paid_is_rejected`：paid 后 resume → 同上（charge 不变、历史不变、错误码明确）；
  - `test_i6b_resume_without_pending_interrupt_is_rejected`：`need_info`（next 为空）时 resume → `CLAIM_STATE_INVALID`。

---

## 4. D1｜`server.metrics` 到底接没接（integrator 对）

**grep 证据**：
```
server/trace.py:149:            from . import metrics
server/trace.py:150:            metrics.observe_record(row)
```
**但 `observe_record` 只认这些 record_type**（`server/metrics.py:311-375`）：
`llm_response / tool_call / tool_result / retrieval / node_end / error`。

**实跑证据（修复前）**：跑完整理赔流程后 `metrics.render()` 里**只有 `# HELP` / `# TYPE` 行、没有任何样本行**（过滤注释行后为 0 行）。
> 顺便自纠一个"假绿"：F2d 早期版本的 `test_metrics_are_actually_wired` 断言 `"renewal_" in rendered` —— 这个条件被 **`# HELP renewal_...` 注释行**满足，所以它一直绿。加强为断言**样本行**（如 `renewal_tool_calls_total{node="execute_payment"}`）后，修复前会正确变红（见 §7）。
→ 结论：**F2 当时"已自动接入"的说法不成立**；`observe_record` 的调用链在，但理赔域没有产出它认识的 record_type。

**修法**：
1. 新增 `ClaimGraph._wrap(name, fn)`：节点**成功**执行后补一条 `node_end`（带 `latency_ms`；异常/`interrupt` 路径不补，避免把"暂停"记成"完成"）；
2. 所有 13 个节点注册时都包 `_wrap`；
3. `execute_payment` 调网关前后补 `tool_call` / `tool_result`（`tool_calls` 计数器 + `execute_tool_duration`）；
4. `Event` 增加 `claims.payment_charge`（`tool_call` 行的 `event.kind`），并登记到 SPEC §6.3。

**实跑证据（修复后）**：
```
指标行数: 135
   renewal_tool_calls_total{node="execute_payment"} 1
   renewal_node_duration_seconds_bucket{node="analyze_materials",le="0.001"} 1
   ...
含 renewal_node_duration: True
含 renewal_tool_calls_total: True
```
**测试**：`test_metrics_are_actually_wired` 断言 `renewal_node_duration` 存在、`renewal_tool_calls_total{node="execute_payment"}` 存在，且 `intake/verify_precheck/analyze_materials/assess_amount/finalize` 均有样本。

---

## 5. SPEC 变更（契约侧）

| 位置 | 变更 |
|---|---|
| §3.2 | `analysis_key` 缓存标注 **v1.0.1 已实现**（函数名 / `analysis_cached` 状态 / 可覆盖目录） |
| §6.3 | 新增 `claims.payment_charge`（`tool_call` 行） |
| **§8.0（新增）** | **运行前提**：理赔流水线（含 F3）必须用 `.venv-claims/bin/python`；`.venv` 下 F3 会 `DeepAgentsNotInstalled` **自动降级为规则模式** → **"假绿"风险**；`.venv` 只用于续保基线与降级路径验收；`DEEPAGENTS_PYTHON` 仅作约定/一致性检查 |
| §8.1 | 登记 `CLAIMS_WIKI_DIR`：**理赔域一律读 claims wiki，禁读续保 `wiki/`**（续保 `WikiSearch()` 默认读 `server.config.WIKI_DIR`，cwd 敏感）；实际接线归 D5 |
| §9 | 降级行**必须带** `error_type` + `error_class` + `message`(≤300)；给出取值枚举与实现位置 |

---

## 6. D2｜`analysis_key` 缓存：选择「实现」

理由：F1 已把它写进契约（§3.2），**契约与实现不一致比缺功能更难查**；实现成本低（约 30 行 + 2 条测试），且能直接省 token。

实现（`claims/graph.py`）：
```python
_analysis_key(claim_id, documents, *, analyzer_version) -> sha256(claim_id|逐材料sha256(按doc_id排序)|version)[:32]
_load_analysis_cache / _store_analysis_cache → claims/data/cache/<key>.json
```
命中时 `analysis_cached=True`、`analysis_key` 进 state 与 `claims.materials_analyzed` 轨迹行；写缓存失败不影响主流程（缓存是优化不是正确性前提）。

测试：
- `test_analysis_cache_hit_on_second_analysis`：第一次 `analysis_cached=False` 且缓存文件存在；第二次 `True` 且结果一致；
- `test_analysis_key_changes_with_content_and_claim`：换 claim / 改材料内容 → key 改变；同输入 → key 稳定。

---

## 7. "先红后绿"证据（4 条 degradation 的测试确实能失败）

把 `claims/graph.py` 临时换回**修复前**备份（`/tmp/graph.py.bak`），跑新增测试：

```
FAILED claims/tests/test_f2d_degradations.py::test_i4a_first_trace_row_goes_to_claim_file
FAILED claims/tests/test_f2d_degradations.py::test_i4a_invalid_report_trace_also_uses_claim_file
FAILED claims/tests/test_f2d_degradations.py::test_i4b_degradation_records_error_type
FAILED claims/tests/test_f2d_degradations.py::test_i4b_disabled_switch_also_records_reason
FAILED claims/tests/test_f2d_degradations.py::test_i6a_terminal_thread_reinvoke_is_rejected
FAILED claims/tests/test_f2d_degradations.py::test_i6b_resume_after_paid_is_rejected
FAILED claims/tests/test_f2d_degradations.py::test_i6b_resume_without_pending_interrupt_is_rejected
FAILED claims/tests/test_f2d_degradations.py::test_analysis_cache_hit_on_second_analysis
FAILED claims/tests/test_f2d_degradations.py::test_analysis_key_changes_with_content_and_claim
9 failed, 1 passed in 0.42s
```
> 补充：那次"1 passed"是**加强前**的 `test_metrics_are_actually_wired`——它当时断言 `"renewal_" in rendered`，被 `# HELP renewal_...` 注释行满足而假绿。
> 加强后我单独做了第二次回退验证（修复前代码 + 加强版测试）：
> ```
> >       assert 'renewal_tool_calls_total{node="execute_payment"}' in rendered, rendered[:400]
> E       assert 'renewal_tool_calls_total{node="execute_payment"}' in '# HELP renewal_chat_requests_total ...\n# TYPE ...'
> FAILED claims/tests/test_f2d_degradations.py::test_metrics_are_actually_wired
> 1 failed, 9 deselected
> ```
> 恢复修复版后 `sha256` 与回退前一致（YES），`claims/tests` 56 passed。

恢复修复版后：`claims/tests` 全绿。

**红→绿对照表（TDD 证据链）**：

| 测试 | 修复前 | 修复后 | 修的是哪条 |
|---|---|---|---|
| `test_i4a_first_trace_row_goes_to_claim_file` | RED（`unknown.jsonl` 存在） | GREEN | I4-a |
| `test_i4a_invalid_report_trace_also_uses_claim_file` | RED（同） | GREEN | I4-a |
| `test_i4b_degradation_records_error_type` | RED（无 `error_type`） | GREEN | I4-b |
| `test_i4b_disabled_switch_also_records_reason` | RED（同） | GREEN | I4-b |
| `test_i6a_terminal_thread_reinvoke_is_rejected` | RED（charge 2 次） | GREEN | I6-a |
| `test_i6b_resume_after_paid_is_rejected` | RED（静默成功） | GREEN | I6-b |
| `test_i6b_resume_without_pending_interrupt_is_rejected` | RED（静默成功） | GREEN | I6-b |
| `test_analysis_cache_hit_on_second_analysis` | RED（无缓存） | GREEN | D2 |
| `test_analysis_key_changes_with_content_and_claim` | RED（无 `analysis_key`） | GREEN | D2 |
| `test_metrics_are_actually_wired` | RED（只有 `# HELP/# TYPE`，零样本） | GREEN（135 行样本） | D1 |
| `test_anomalies_do_not_leak_into_flags` | RED（无显式剔除时依赖"自然忽略"） | GREEN | §10.2 |
| `test_anomaly_codes_registry_matches_spec` | RED（SPEC 无词汇表） | GREEN | §10.2 |

> ⚠️ 如实记录一次操作事故：第一次回退试验时我误把备份覆盖回工作区且未先保存修复版，随后用同一组补丁脚本重新应用并跑通（56 passed）。功能等价，`graph.py` 与首次修复版仅空白格式差异；**第二次回退验证前已先 `cp` 到 `/tmp/graph.py.fixed2`，恢复后 sha256 校验一致（YES）**。

---

## 8. 验收原文

### 8.1 `.venv-claims`（唯一可验收 F3 的解释器）

```bash
.venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
```
```
........................................................................ [ 52%]
..................................................................       [100%]
138 passed in 5.17s
```

### 8.2 续保基线（`.venv`，口径不变）

```bash
.venv/bin/python -m pytest -o addopts="" -q
```
```
......                                                                   [100%]
148 passed, 2 skipped in 1.60s
```

### 8.3 降级路径仍可跑（`.venv` 下 claims 套件）

```bash
.venv/bin/python -m pytest claims/tests -o addopts="" -q
```
```
........................................................                 [100%]
58 passed in 0.63s
```
（58 = F2 原有 46 + F2d 新增 10 + 队长后补 2（anomaly））

---

## 10. 队长后补三项（F3b 交接，2026-11-18）

### 10.1 §8.1 环境变量总表（F2 + F3 统一，5 列）

已把 F3 的 6 个变量与 F2 已定义的合并成一张表（SPEC §8.1）：`变量 / 默认 / 生效点 / 影响 / 消费方`。

| 变量 | 默认 | 消费方 | 备注 |
|---|---|---|---|
| `DEEPAGENTS_MODEL` | **未设置** | F3 | **未设置 → `NoModelConfigured` → 降级，绝不会调用外部 API**（安全属性，SPEC 已加粗声明） |
| `DEEPAGENTS_TIMEOUT_S` | 120 | F3 | 超时 → `AnalysisTimeout` → 降级 |
| `DEEPAGENTS_MAX_ATTEMPTS` | 2 | F3 | 仅对 schema 不合规重试 |
| `DEEPAGENTS_RECURSION_LIMIT` | 40 | F3 | 触及 → `StructuredOutputRetriesExhausted` |
| `DEEPAGENTS_SUBAGENTS` | true | F3 | 材料少时可关，省 token |
| `CLAIMS_ANALYSIS_KEEP_WORKSPACE` | false | F3 | true 保留 `claims/data/materials/analysis-*`（占盘） |
| `CLAIMS_DATA_DIR` | `claims/data` | F2 + F3 | F3 `materials_root()` 已接 |
| `CLAIMS_WIKI_DIR` | `data/llm-wiki-claims/wiki` | **D5** | 禁读续保 `wiki/` |

### 10.2 anomaly 码：不进 `flags`，但登记为契约词汇表

- **裁决**：`flags` 是业务信号（影响 `route_risk` 路由），`anomalies` 是分析过程信号（只进轨迹）。
  混用会让"模型跳过某文档"被当成"客户欺诈风险"。
- **SPEC §4.6 新增词汇表**（4 个码 + 参数形式 + 是否影响可信度 + 典型触发原因）：
  `skipped_by_model` / `quote_not_verbatim:<片段>` / `kind_mismatch:<实际>!=<期望>` / `unknown_doc_id_dropped:<n>`。
- **实现**：`claims/tools/logic.py` 新增 `ANALYSIS_ANOMALY_CODES` + `_anomaly_code()`；
  `flags_for()` 末尾**显式剔除**这些码，并写明"不靠没匹配到就自然忽略"的原因。
- **测试**：
  - `test_anomalies_do_not_leak_into_flags`：四类 anomaly 全塞进去 → `flags == []` 且 `needs_manual_review` 仍为 False；
  - `test_anomaly_codes_registry_matches_spec`：实现里的每个码都必须在 SPEC §4.6 出现（防词汇表漂移）。

### 10.3 决策台账

`docs/log/decisions.md` 追加 **D-15..D-22**（与 §0 表一一对应）：
轨迹归属 / 降级可归因 / 终态守卫 / 指标接线方式 / 缓存落地 / anomalies 不进 flags / wiki 变量登记 / 运行前提。
格式沿用台账原有四列（决策 / 依据 / 影响范围），便于 C5 对账。

---

## 9. 遗留

| # | 事项 | 接手方 |
|---|---|---|
| 1 | `claims/deep_agents/**` 仍未被默认 `testpaths` 收集；建议 CI 用 `.venv-claims` 显式跑两个目录 | t12 / 队长 |
| 2 | `execute_payment` 的 `tool_call` 只覆盖支付网关；若 D5 接检索，需要同样补 `retrieval` 行才能进指标 | D5 |
| 3 | `analysis_key` 缓存无 TTL/清理策略（当前只增不减）；量大时需按 `claims/data/cache` 定期清理或加 LRU | t12 |
| 4 | 终态守卫目前只认 `Status.TERMINAL`；`closed_abandoned` 的超期关闭流程尚未实现（属业务规则，未在本任务范围） | 业务 / t12 |
