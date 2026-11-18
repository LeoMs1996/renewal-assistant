# step-f5-ruff.md —— F5a：claims 域 ruff 清零 + evidence 排除决策

> 任务：**t29**。执行人：flow-engineer（attempt 2 / `attempt_id=a497b33b-5290-49db-a1b9-f6acaae2432d`）
> 时间：2026-11-19（+0800）。ruff 版本 **0.17.5**（`.venv/bin/python -m ruff --version`）
> 写作用域：`claims/**` + `pyproject.toml`。**未改** `server/**`、`tests/**`、`data/llm-wiki-claims/**`、`docs/research/evidence/**` 内容。

---

## 0. 结论

| 项 | 修前 | 修后 |
|---|---|---|
| `ruff check claims/` | **17 errors**（15 fixable） | **All checks passed!** |
| `ruff check .`（全仓） | 22 errors（含他人域） | **All checks passed!**（见 §4 说明） |
| `pytest claims/tests`（`.venv`） | collection error（跨域，见 §3） | **86 passed** |
| `pytest`（续保，`.venv`） | 148 passed, 2 skipped | **148 passed, 2 skipped** |
| `.venv-claims` 两套 | 168 passed | **168 passed** |

---

## 1. 修了什么（按规则码分类）

修前 `ruff check claims/ --statistics`（原文）：
```
7	F401 	[*] unused-import
5	UP037 	[*] quoted-annotation
2	E402 	[ ] module-import-not-at-top-of-file
2	I001 	[*] unsorted-imports
1	UP017 	[*] datetime-timezone-utc
Found 17 errors.
[*] 15 fixable with `--fix`.
```

| 规则码 | 条数 | 处置 | 说明 |
|---|---|---|---|
| `F401` unused-import | 7 | `--fix` 自动 | 删除未使用 import（如 `probe_f0.py` 的 `langchain_core`/`langgraph`、测试里的 `pytest`/`rules_analyzer`/`re`） |
| `UP037` quoted-annotation | 5 | `--fix` 自动 | 去掉多余引号类型注解（`from __future__ import annotations` 下无需字符串化） |
| `I001` unsorted-imports | 2 | `--fix` 自动 | import 排序/格式 |
| `UP017` datetime-timezone-utc | 1 | `--fix` 自动 | `datetime.timezone.utc` → `datetime.UTC`（`claims/graph.py`，**语义等价**，见下方 diff） |
| `E402` module-import-not-at-top | 2 | **人工** | `claims/tests/conftest.py` 里 `import os as _os` / `import warnings as _warnings` 写在了文件中部 —— 移到顶部 import 区 |

`--fix` 实际改动 **9 个文件**（对比 `/tmp/claims.bak.1795020545`）：

```
claims/deep_agents/analyzer.py          ← F3 领地，仅格式
claims/deep_agents/probe_f0.py          ← F3 领地（取证脚本），仅格式
claims/deep_agents/schema.py            ← F3 领地，仅格式
claims/deep_agents/tests/conftest.py    ← F3 领地，仅格式
claims/deep_agents/tests/test_analyzer_offline.py ← F3 领地，仅格式
claims/graph.py                         ← 本域（UP017 时间别名，等价）
claims/tests/conftest.py                ← 本域（E402 人工 + 跨域修复，见 §3）
claims/tests/test_f2d_degradations.py   ← 本域（删未用 import）
claims/tests/test_flow.py               ← 本域（删未用 import）
```

> ⚠️ **跨域声明**：其中 5 个文件属于 F3（`claims/deep_agents/**`）。t29 的写作用域是 `claims/**`，故在范围内；
> 但我只让 `ruff --fix` 做**格式类**改动（删未用 import / 去引号 / 排序），**没有改任何逻辑**。
> 验证：F3 的 82 条测试在 `.venv-claims` 下仍全绿（§4.3），且 `analyzer.py` 的公开签名未变
> （`run_analysis(docs, *, analyzer_version)`）。

`claims/graph.py` 的 diff（完整，仅 2 行）：
```diff
-from datetime import datetime, timezone
+from datetime import UTC, datetime
-    return datetime.now(timezone.utc).isoformat(timespec="seconds")
+    return datetime.now(UTC).isoformat(timespec="seconds")
```
（`UTC` 是 `timezone.utc` 的别名，行为等价；不涉及流程/幂等/中断语义。）

---

## 2. `docs/research/evidence/**` 排除决策：**选 A**

`pyproject.toml`：
```toml
# `docs/research/evidence/` 是**第三方官方文档快照 + 证据探针**（20 份 .mdx、graph.py、
# PyPI JSON、probe 脚本），sha256 登记在 evidence/MANIFEST.md；对本仓 lint 它们没有意义，
# 且改一个字符就会让证据链对不上。故整目录排除（决策 A，见 docs/log/step-f5-ruff.md）。
extend-exclude = [
    ".venv", "traces", "wiki", "synthetic", "eval/report-*.md",
    "docs/research/evidence",
]
```

**理由（三条，按重要性排序）**：

1. **不能改内容 → 就不该 lint 它**。该目录每个文件的 `sha256(前16)` 都登记在
   `docs/research/evidence/MANIFEST.md`，是"当时读到的原文"的唯一凭证。
   `ruff --fix` 会自动改写文件 → **必然**破坏证据链；而"只报不改"会在 C5 门禁里长期留红，
   逼后来者要么绕过门禁、要么偷偷改证据（更糟）。排除是唯一不产生这两种坏结果的选择。
2. **第三方文档不是我们的代码**。20 份 `.mdx` 是 LangChain 官方文档源文件快照；
   对别人的文档套我们的 lint 规则（line-length、import 排序…）没有工程意义，
   只会产生"修了也不该修"的噪声。
3. **probe 脚本虽是我们写的，但它是取证工具，不是产品代码**。`probe_langgraph_api.py`
   的价值在于"当时怎么验证的"，它的形态应随证据冻结，而不是随本仓风格漂移。

**为什么不用 B（只排 mdx/html 文本，保留 probe 脚本）**：
B 会把 `probe_langgraph_api.py` 继续纳入 lint。它当前是干净的，但它是**证据快照**：
将来任何人为了过 lint 去改它，就与 MANIFEST 记录的 sha256 对不上——
和 §2 理由是同一类问题，只是范围小一点。B 的收益（"我们也 lint 自己的脚本"）
远小于风险。

**为什么不用 C（把 probe 移到 `claims/research_probes/` 再 lint）**：
C 会**改变证据文件路径**，而 MANIFEST 按路径登记；移动后要么改 MANIFEST（等于改证据链），
要么让 MANIFEST 指向不存在的路径。且 probe 脚本依赖 R3 的 `evidence/` 目录布局
（`probe-checkpoints.sqlite` 等），搬家还要连带改脚本内的相对路径 —— 纯负收益。

**排除的边界是精确的**：只排除 `docs/research/evidence`，`docs/research/*.md`
（r3 结论、llmwiki-spec、ins-mmbench-access 等**我们自己的**研究文档与代码块）**仍在** lint 范围之外
是 Markdown（ruff 不检查 md），其内嵌的 Python 不在 ruff 目标内 —— 这一点也记录在案，避免误解。

---

## 3. 顺手修掉一个跨域 blocker：`.venv` 下 `claims/tests` 无法收集

**现象**（回归时发现，非 ruff 引入）：
```
.venv/bin/python -m pytest claims/tests -o addopts="" -q
→ ERROR collecting claims/tests/test_f4_api.py
  claims/api.py:453: app = create_app()
  claims/api.py:128: raise RuntimeError("deepagents 不可导入（D-22）… CLAIMS_ALLOW_RULES_ONLY=1")
```

**根因**：F4 的 `claims/api.py` 在**模块导入时**执行 `create_app()` → `assert_preflight(strict=?)`；
strict 由 `CLAIMS_ALLOW_RULES_ONLY` 决定。`claims/tests/test_f4_api.py` 只在 **fixture 里**
设这个变量（`monkeypatch.setenv(...)`），但 **import 发生在收集期、早于 fixture** → 必然炸。
`.venv-claims` 有 deepagents 所以不炸（这也解释了为什么 F4 自己看不到这个问题）。

**修法**（最小、且不篡改 F4 语义）：在 `claims/tests/conftest.py`（pytest 在**收集测试模块之前**导入它）
提前 `setdefault`：
```python
# D-22：`claims/api.py` 在模块导入时就 create_app() 并跑 preflight …
_os.environ.setdefault("CLAIMS_ALLOW_RULES_ONLY", "1")
```
- 用 `setdefault` 而非 `setenv`：**不覆盖**外部显式设置（CI 想跑严格模式仍可 `CLAIMS_ALLOW_RULES_ONLY=0`）。
- 显式 `strict=True` 的用例仍走严格路径：`test_preflight_strict_rejects_missing_deepagents`
  在 `.venv` 下依然断言 `assert_preflight(strict=True)` 抛错（实测通过）。
- 为什么不在 `claims/api.py` 里放宽（比如 import 时不 preflight）：那是 F4 的设计与领地，
  且"导入即校验"正是它防"假绿起服务"的手段；本次只修测试侧的时序 bug。

---

## 4. 修后原文输出

### 4.1 `ruff check claims/`

```bash
cd /Users/leoms/Documents/deepseek-harness-workspace/homework5/renewal-assistant
.venv/bin/python -m ruff check claims/
```
```
All checks passed!
```

### 4.2 `ruff check .`（全仓，C5 门禁口径）

```bash
.venv/bin/python -m ruff check .
```
```
All checks passed!
```
> 说明：本任务开始时全仓诊断是 **22 errors**（含 `data/llm-wiki-claims/scripts/wiki_lint.py:206 B007`
> 等他人域条目）。收尾时最后一次全仓运行已是 `All checks passed!` —— 该条由 wiki-lead 在本任务
> 并行期间自行修掉（我未改 `data/llm-wiki-claims/**`）。**我的贡献范围是 `claims/**` 的 17 条 + evidence 排除。**

### 4.3 回归四组

```bash
.venv/bin/python -m pytest claims/tests -o addopts="" -q
# 86 passed in 1.84s

.venv/bin/python -m pytest -o addopts="" -q
# 148 passed, 2 skipped in 2.85s

.venv-claims/bin/python -m pytest claims/tests claims/deep_agents/tests -o addopts="" -q
# 168 passed in 7.66s
```
（`claims/tests` 从 58 → 86：F4 的 `test_f4_api.py` 与 D5 的 `test_d5_wiki_retrieval.py`
在本任务期间由队友落地，本次修复让它们在 `.venv` 下也能跑起来。）

---

## 5. 遗留

| # | 事项 | 接手方 |
|---|---|---|
| 1 | `claims/tests` 在 `.venv` 下靠 conftest 注入 `CLAIMS_ALLOW_RULES_ONLY=1` 才可收集；若将来想验证"严格模式下的 HTTP 层"，需在 `.venv-claims` 下跑（不要在 `.venv` 下断言 strict 行为） | t12 / F4 |
| 2 | ruff 门禁建议锁定版本（当前 0.17.5）。ruff 规则集随版本扩张，`ruff check .` 今天绿不代表半年后绿；C5 可考虑 `pin ruff==0.17.5` + 独立升级 PR | 队长 / C5 |
| 3 | `docs/research/evidence` 排除规则写在 `pyproject.toml`；若将来该目录迁址，需同步更新（`MANIFEST.md` 里也会记路径） | 后续 |
