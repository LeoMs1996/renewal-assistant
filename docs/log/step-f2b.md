# step-f2b.md —— F2b：修正「因错误原因通过」的降级测试

> 任务：**t16**。执行人：flow-engineer（attempt 2 / `attempt_id=b3168fdb-bc50-4897-b4f3-7ff8edc2659a`）
> 时间：2026-11-18（+0800）。**只改 `claims/tests/**`**：`claims/graph.py`、`claims/deep_agents/**`、`server/`、`tests/`、`SPEC.md` 一行未动。
> 起因：F3（deepagents-engineer）自报 —— 旧用例 `test_deepagents_enabled_but_missing_falls_back` 在 F3 落地后**仍然绿，但绿的原因变了**（从"模块缺失"变成"未配置模型"）。

---

## 0. 结论

| 项 | 结果 |
|---|---|
| 旧用例 | **删除**（1 条，语义已失效） |
| 新用例 | **2 条**，各测各的失败路径：`module_missing`（真实 `ImportError`）/ `no_model_configured`（F3 抛 `NoModelConfigured`） |
| 顺带强化 | 另 1 条相邻用例（`ENABLED=false`）补上"F3 根本未被调用"的断言 |
| 变异验证 | 去掉 F2 的降级兜底后，**两条新用例对应场景都会抛异常** → 证明它们承重、不是空壳 |
| 套件 | `claims/tests`：**31 passed**（原 30）；续保：**148 passed, 2 skipped**（不变） |

---

## 1. 改动清单

| 文件 | 改动 |
|---|---|
| `claims/tests/test_flow.py` | ① 删除 `test_deepagents_enabled_but_missing_falls_back`；② 新增 `test_deepagents_enabled_but_module_missing_falls_back`；③ 新增 `test_deepagents_enabled_but_no_model_configured_falls_back`；④ `test_rules_fallback_when_deepagents_disabled` 增补"F3 未被调用"断言 |
| `docs/log/step-f2b.md` | 本文件 |

未新增/未修改其它文件；未改实现来迁就测试。

---

## 2. 两条测试的失败路径构造方式（关键：**真的**触发该路径）

### 2.1 路径 A：模块导入失败 → `rules_fallback`

```python
monkeypatch.setenv("DEEPAGENTS_ENABLED", "true")
monkeypatch.setitem(sys.modules, "claims.deep_agents.analyzer", None)  # 记录原值，结束后自动还原
monkeypatch.delattr(deep_pkg, "analyzer", raising=False)

# 先自证：此刻导入确实失败（否则本用例测的就不是「模块缺失」）
with pytest.raises(ImportError):
    from claims.deep_agents import analyzer
```

- **机制**：CPython 的导入器遇到 `sys.modules[name] is None` 会抛
  `ImportError: import of claims.deep_agents.analyzer halted; None in sys.modules`。
  这与"文件被删/import 期报错"是**同一类可观测行为**（ImportError），不依赖任何私有 API。
- **为什么还要 `delattr` 包属性**：`from pkg import sub` 会先 `getattr(pkg, "sub")`；
  如果 `claims.deep_agents` 包此前已导入过 analyzer，属性还在，就**不会**走导入器 →
  模拟无效。删属性后才真正触发导入并失败。
- **为什么先 `pytest.raises(ImportError)` 自证**：这是本用例的"校准步"——
  如果哪天模拟失效（例如 monkeypatch 写法失效），用例会在这一行**失败**，
  而不是悄悄退化成"测到了别的降级原因"。
- **额外断言**：`rules_calls` 非空（证明兜底真的执行了 `rules_analyzer.run_analysis`，
  而不是流程被别处静默吞掉后返回一个空的 `rules_fallback` 假象）。

### 2.2 路径 B：模块存在、但未配置模型 → `rules_fallback`

```python
monkeypatch.setenv("DEEPAGENTS_ENABLED", "true")
monkeypatch.delenv("DEEPAGENTS_MODEL", raising=False)   # F3 的显式 opt-in 开关

# 包住 F3 的入口，记录"是否被调用 + 抛了什么"
monkeypatch.setattr(deep_analyzer, "run_analysis", spy)
...
assert caught, "F3 应被调用（DEEPAGENTS_ENABLED=true）"
assert isinstance(caught[0], AnalysisUnavailable)
assert getattr(caught[0], "error_type", None) == "NoModelConfigured"
```

- **机制**：F3 的 `_analyze_once` **第一步**就是 `resolve_model(config)`；
  `DEEPAGENTS_MODEL` 缺失时抛 `AnalysisUnavailable(error_type="NoModelConfigured")`
  （`claims/deep_agents/analyzer.py:159-166`）。F2 的 `except Exception` 兜底转 rules。
- **与路径 A 的判据差异（这是本次修正的核心）**：
  路径 B 断言**F3 真的被调用过**且**抛的是 `NoModelConfigured`**。
  这样"模块缺失"就不再能冒充本用例的通过原因。
- 说明：本机 `.venv` **未安装 `deepagents`** 也不影响本用例——`resolve_model` 在
  `build_agent` 之前就抛了，还没走到重依赖导入。

### 2.3 变异验证（证明不是空壳）

用一次性探针（`/tmp/mutation_probe2.py`，不入库）把 F2 的兜底去掉
（`claims.graph.run_analysis = strict_run_analysis`：不再 try/except），其它条件不变：

```
[module-missing] ✅ 按预期失败 → ModuleNotFoundError: import of claims.deep_agents.analyzer halted; None in sys.modules
[no-model]       ✅ 按预期失败 → AnalysisUnavailable: [ANALYSIS_UNAVAILABLE/NoModelConfigured] 未配置模型：请设置 DEEPAGENTS_MODEL（pr…
```

→ 两条新用例对应的场景，在"降级被删掉"时都会失败，说明**测试确实在测降级**。
（第一次跑变异探针时 `no-model` 显示"未抛异常"，排查发现是同一 data 目录的
`idempotency` 登记让第二次调用在 `intake` 就判 `CLAIM_DUPLICATE` 直接 END，
根本没进 `analyze_materials`；改成每个场景独立临时目录后才复现出真实失败。
这条也记进 §3 的同类风险。）

---

## 3. 同类风险排查：还有没有"因错误原因通过"的测试？

逐条过了 `claims/tests/` 里所有与 `DEEPAGENTS_*` 有关的用例，结论如下。

| 用例 | 现在的绿来自 | 判定 |
|---|---|---|
| `test_rules_fallback_when_deepagents_disabled`（`ENABLED=false`） | 显式关闭 → 直接走 rules | ✅ 原因正确；**已补强**：断言 `deep_analyzer.run_analysis` **未被调用**（此前只要结果 mode 是 rules 就算过，理论上"调了 F3 失败再降级"也能冒充） |
| `test_deepagents_enabled_but_module_missing_falls_back`（新） | 真实 ImportError | ✅ 原因正确（§2.1） |
| `test_deepagents_enabled_but_no_model_configured_falls_back`（新） | F3 被调用并抛 NoModelConfigured | ✅ 原因正确（§2.2） |
| 其余 28 条（happy path / 中断 / 支付 / 轨迹 / 注入 / 阈值 …） | **依赖 `conftest.tmp_env` 默认 `DEEPAGENTS_ENABLED=false`** | ⚠️ 见风险 R1 |

### 发现的风险（只报告，未动手改）

| # | 风险 | 说明 | 建议 |
|---|---|---|---|
| **R1** | **隐式耦合 conftest 默认值**：28 条用例的确定性完全依赖 `tmp_env` 里 `DEEPAGENTS_ENABLED=false`。若有人改 conftest 默认、或新测试忘了用 `tmp_env` 而直接构造 `ClaimGraph()`，这些用例会尝试真实模型调用（慢/需凭证/不稳定），且**失败现象与业务断言混在一起**，排查成本高 | 不是"绿错原因"，但是"绿靠环境"的同族问题 | 在 `ClaimGraph.__init__` 或 conftest 加一道守卫测试：断言"未显式开启时 `config.deepagents_enabled()` 为 False"，把默认值也变成被测对象 |
| **R2** | 幂等登记跨用例串扰：`CLAIMS_DATA_DIR`/`CLAIMS_CHECKPOINT_DB` 若被多个场景共用，第二次调用会在 `intake` 判 `CLAIM_DUPLICATE` 并提前 END，**看起来像"某条路径没被触发"** | 我自己在变异探针里就踩到（§2.3 末段） | 已通过 fixture 规避（每用例 `tmp_path`）；建议 F3/t12 的测试同样每场景独立 data 目录 |
| **R3** | `claims/data/` 目录残留且**未被 `.gitignore` 忽略**：现存在 `claims/data/materials/analysis-*`（mtime 2026-11-18 01:02，F3 阶段产生，非本次测试） | 我的测试全部写 `tmp_path`，不会产生它；但仓库里留着未跟踪运行态目录，C5 审计时容易被误认为测试污染 | 由 t12/F3 决定：要么加 `.gitignore`（`claims/data/`），要么在测试结束清理 |
| **R4** | `test_only_one_interrupt_call_site` 是源码级断言（AST），不依赖运行；它绿的原因是"源码确实只有一处 `interrupt()`"，原因正确 | — | 无需改 |

---

## 4. 验证原文（两条命令，逐字粘贴）

### 4.1 `claims` 套件

```bash
cd /Users/leoms/Documents/deepseek-harness-workspace/homework5/renewal-assistant
.venv/bin/python -m pytest claims/tests -o addopts="" -q
```
输出：
```
...............................                                          [100%]
31 passed in 0.35s
```

### 4.2 续保套件（默认 `testpaths`，口径不变）

```bash
.venv/bin/python -m pytest -o addopts="" -q
```
输出：
```
......                                                                   [100%]
148 passed, 2 skipped in 1.92s
```

### 4.3 两条新用例 + 强化后的禁用用例（verbose）

```bash
.venv/bin/python -m pytest claims/tests/test_flow.py -o addopts="" -q \
  -k "deepagents_enabled or deepagents_disabled" -v
```
输出：
```
======================= 3 passed, 16 deselected in 0.20s =======================
```

### 4.4 作用域自检

```bash
git status --porcelain | grep -E "^ M (server|tests|mcp_servers|wiki|SPEC.md)"   # 空
ls -d claims/data        # 存在，但 mtime 01:02（F3 阶段），非本次测试产生
```

---

## 5. 遗留

| # | 事项 | 接手方 |
|---|---|---|
| 1 | R1：给 `deepagents_enabled()` 默认值加守卫测试（防止 conftest 默认值被改动后整套变成"靠环境绿"） | 可并入 t12 验收 |
| 2 | R3：`claims/data/` 是否加入 `.gitignore` | t12 / F3 |
| 3 | F3 侧的 `claims/deep_agents/tests/` 未被默认 `testpaths` 收集；是否纳入统一报告（不改变 148 口径的前提下） | t12 / 队长 |
