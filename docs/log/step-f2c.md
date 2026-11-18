# step-f2c.md —— F2c：给 `DEEPAGENTS_ENABLED` 默认值加守卫

> 任务：**t18**。执行人：flow-engineer（attempt 2 / `attempt_id=f5ee885c-287c-4ba6-9e76-d62dc509f0e9`）
> 时间：2026-11-18（+0800）
> 起因：t16（F2b）报告 R1 —— 「28 条用例的确定性完全依赖 `conftest.tmp_env` 里 `DEEPAGENTS_ENABLED=false`」，而**默认值本身没有任何测试覆盖**，是隐形单点依赖。
> 写作用域：只改 `claims/tests/**`。`claims/config.py` 的默认值**未改**（只在反证时临时改过一次，已还原并校验 sha256）。

---

## 0. 结论

| 项 | 结果 |
|---|---|
| 守卫测试 | 新增 `claims/tests/test_config_defaults.py`（**断源码字面量 + 断运行期取值**，不依赖 `tmp_env`） |
| 会话级护栏 | 选 **方案 A**：`DEEPAGENTS_MODEL` 被设置 → `pytest.exit(returncode=3)`；`DEEPAGENTS_ENABLED=true` → 告警 |
| R2 | 排查结论：**18 条构造图的用例 100% 走 `tmp_env`**（0 条裸构造）；另加"跑完不许往仓库 `claims/data/` 写文件"的 session 护栏，并验证了它的判别力 |
| 反证 | 把默认值临时改成 `"true"` → 守卫测试 **3 failed**；还原后 sha256 与改前完全一致 |
| 验收 | `claims/tests`：**46 passed**（32 → 46，含参数化）；续保：**148 passed, 2 skipped** |

---

## 1. 做了什么

### 1.1 新增 `claims/tests/test_config_defaults.py`（15 个用例，含参数化）

| 用例 | 断言的内容 | 为什么这样断言 |
|---|---|---|
| `test_default_deepagents_enabled_is_false` | **用 AST 从 `claims/config.py` 取出** `_env("DEEPAGENTS_ENABLED", "<默认值>")` 的第二个实参，断言其小写值 == `"false"` | 断**源头**（源码字面量），而不是只断 `deepagents_enabled()` 的返回值——后者被别处硬编码成 false 也能绿 |
| `test_default_deepagents_enabled_runtime_is_false` | `monkeypatch.delenv` 后 `config.deepagents_enabled() is False` | 断运行期真实行为，覆盖"源码默认对但读取逻辑写错" |
| `test_explicit_truthy_values_still_enable`（5 参数） | `1/true/TRUE/yes/on` → True | 守卫只锁**默认**，不锁能力（避免"为了安全把功能关死"） |
| `test_explicit_falsy_values_disable`（6 参数） | `0/false/no/off/""/"  "` → False | 空串/空白必须视为关闭（否则 CI 里 `DEEPAGENTS_ENABLED=` 会意外打开） |
| `test_tmp_env_fixture_pins_deepagents_off` | `conftest.py` 源码里必须出现 `setenv("DEEPAGENTS_ENABLED", "false")` | 第二道防线：即使默认值正确，fixture 漏设也会让用例打模型 |
| `test_env_is_clean_for_this_test` | 本文件运行期环境变量为空或 falsy | 自证守卫不靠 fixture 才成立（无循环依赖） |

失败信息里带**动态统计的后果数字**（`_dependent_test_count()` 现算使用 `tmp_env` 的用例数），
并写明"改成 true 会让 N 条用例调用真实模型：慢、需要凭证、失败现象与业务断言混在一起"。

### 1.2 `claims/tests/conftest.py` 加两个 `autouse=True` 的 session fixture

```python
@pytest.fixture(scope="session", autouse=True)
def _guard_no_real_model():
    ...  # DEEPAGENTS_MODEL 被设置 → pytest.exit(..., returncode=3)
         # DEEPAGENTS_ENABLED=true → warnings.warn（逐个用例的 tmp_env 会重新钉成 false）

@pytest.fixture(scope="session", autouse=True)
def _guard_repo_data_untouched():
    before = _repo_data_files()
    yield
    assert not (set(_repo_data_files()) - set(before)), \
        "测试往仓库 claims/data/ 写了文件：... 说明有用例没走 tmp_env"
```

---

## 2. 为什么选方案 A（拒绝让测试"自动变绿"）

| 判据 | 方案 A（拒绝运行 + 明确报错） | 方案 B（自动注入 `false`） |
|---|---|---|
| 环境里真的配了 `DEEPAGENTS_MODEL` 时 | **整套拒绝运行**，退出码 3，消息说明"本套件按未配置模型设计" | 静默把开关设成 false → 本来想跑的真实模型路径被悄悄关掉，测试结果的**语义不再是它声称的那样** |
| 与队长判据"宁可跑不起来并明确报错" | 完全一致 | 相反：把风险变成"看起来一切正常" |
| 对 `test_deepagents_enabled_but_no_model_configured_falls_back` 的影响 | 该用例的失败原因不会被环境混淆 | 环境里配了模型时，该用例会因为"模型可用了"而**改变语义**却仍然可能绿 |
| 实现复杂度 | 低（一个 fixture） | 低 |

→ **选 A**。具体实现上做了分级：
- `DEEPAGENTS_MODEL`（真正决定"会不会打模型"）→ **硬退出**；
- `DEEPAGENTS_ENABLED=true`（只是开关漂移，且每个用例的 `tmp_env` 会重新钉死）→ **告警**，不退出。
  理由：硬退出会让"CI 里想跑真实集成测试"的合法场景被误伤，而告警已能满足"不静默"的要求。

---

## 3. 反证（必须失败才证明守卫有效）

### 3.1 临时把默认值改成 `true` → 守卫必须 FAIL

```bash
cp claims/config.py /tmp/config.py.bak            # 备份
python3 -c '...把 _env("DEEPAGENTS_ENABLED", "false") 改成 "true"...'
.venv/bin/python -m pytest claims/tests/test_config_defaults.py -o addopts="" -q
```

输出（原文）：
```
>       assert str(literal).strip().lower() == "false", (
E       assert 'true' == 'false'
>       assert config.deepagents_enabled() is False, (
E       assert True is False
FAILED claims/tests/test_config_defaults.py::test_default_deepagents_enabled_is_false
FAILED claims/tests/test_config_defaults.py::test_default_deepagents_enabled_runtime_is_false
FAILED claims/tests/test_config_defaults.py::test_explicit_falsy_values_disable[]
3 failed, 12 passed in 0.03s
```

> 注：第三条 `test_explicit_falsy_values_disable[]`（空串参数）也倒了——这暴露了一个**真实语义**：
> `_env` 把空串当作"未设置"，于是回落到默认值。这正是 `test_default...` 要守的点，
> 说明参数化用例和守卫用例共用同一个默认值来源，一致性成立。

### 3.2 还原并校验（不改实现）

```
原 sha:   2b570d957045bff1eef551cb965a890fd533327c7f5f0b65f984e36bc2230b97
恢复后 sha: 2b570d957045bff1eef551cb965a890fd533327c7f5f0b65f984e36bc2230b97
sha 一致 ✅（源码未被改动）
```

---

## 4. 会话护栏与 R2 护栏的判别力验证

### 4.1 护栏 A：`DEEPAGENTS_MODEL` 被设置 → 整套拒绝运行

```bash
DEEPAGENTS_MODEL="anthropic:claude-opus-4-8" .venv/bin/python -m pytest claims/tests -o addopts="" -q
```
输出（原文）：
```
no tests ran in 0.22s
! _pytest.outcomes.Exit: claims/tests 拒绝在可能调用真实模型的会话里运行：
  - DEEPAGENTS_MODEL=<已设置>（应留空：本套件按'未配置模型'设计）
请 unset 这些变量后重跑（或显式 `DEEPAGENTS_MODEL= ` 置空）。 !
```
实测 **pytest 退出码 = 3**（非 0），CI 会显式失败。

干净环境（`env -u DEEPAGENTS_MODEL`）：
```
46 passed in 0.35s
```

### 4.2 R2 护栏：往仓库 `claims/data/` 写文件 → teardown 报错

临时探针（已删除，未入库）：
```python
def test_probe_writes_repo_data():
    p = Path(__file__).resolve().parents[1] / "data" / "r2-probe.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("probe", encoding="utf-8")
```
输出（原文）：
```
E       AssertionError: 测试往仓库 claims/data/ 写了文件：['r2-probe.txt']
1 passed, 1 error in 0.02s
```
清理后 `claims/data/` 仅剩原有 `materials/`（F3 阶段产物）。

---

## 5. R2 排查结论（跨用例串扰）

**做法**：用 AST 扫 `claims/tests/test_*.py`，找出所有"会落盘"的用例（构造 `ClaimGraph` /
调 `ensure_dirs` / `idempotency_dir` / `checkpoint_db`），逐一检查是否用了 `tmp_env`。

**结果（真实统计）**：

| 指标 | 数值 |
|---|---|
| `test_*` 函数总数 | **37** |
| 显式使用 `tmp_env` 的用例 | **18** |
| 构造图的用例（函数体出现 `_graph(`） | **18** |
| 其中带 `tmp_env` | **18** |
| **不带 `tmp_env` 的构造图用例** | **0** ✅ |

**结论**：现有用例**不存在**跨用例串扰——所有会产生落盘副作用的用例都经由 `_graph(tmp_env)`，
`tmp_env` 把 `CLAIMS_DATA_DIR` / `CLAIMS_CHECKPOINT_DB` / `CLAIMS_TRACE_DIR` 全部指到
`pytest` 的 `tmp_path`（每个用例一个独立目录），因此 t16 里我踩到的
「同目录 → `intake` 判 `CLAIM_DUPLICATE` → 提前 END → 看起来像某路径没触发」不会再发生。

**防回归**：新增 `_guard_repo_data_untouched` session 护栏（§4.2 已证判别力），
以后任何人写出"忘记挂 `tmp_env`"的新用例，会在收尾时**显式失败**并报出被写入的文件名。

---

## 6. 验收原文

### 6.1 `claims/tests`

```bash
cd /Users/leoms/Documents/deepseek-harness-workspace/homework5/renewal-assistant
.venv/bin/python -m pytest claims/tests -o addopts="" -q
```
```
..............................................                           [100%]
46 passed in 0.36s
```
（t16 收尾时是 31；本次新增 15 个用例 → 46）

### 6.2 续保套件（口径不变）

```bash
.venv/bin/python -m pytest -o addopts="" -q
```
```
......                                                                   [100%]
148 passed, 2 skipped in 1.48s
```

### 6.3 写作用域

```bash
git status --porcelain | grep -E "^ M .*(server|tests|mcp_servers|wiki|SPEC\.md|claims/config\.py)"
```
输出：**空** → 受保护文件与 `claims/config.py` 均未被修改。

---

## 7. 遗留

| # | 事项 | 接手方 |
|---|---|---|
| 1 | `claims/deep_agents/**` 的测试仍未被默认 `testpaths` 收集；若将来纳入同一报告，需给它们也套本文件的 `_guard_no_real_model` 护栏（否则可能真打模型） | t12 / F3 |
| 2 | 若 CI 需要"真跑 Deep Agents 集成"，应新增**独立的** `claims/tests/integration/` 目录并用显式 marker 跳过，而不是放开本护栏 | 后续 |
| 3 | `test_explicit_falsy_values_disable[]` 覆盖了空串语义（视为关闭）；若将来 `_env` 改成"空串即显式空值"，需同步调整该参数化 | 后续 |
