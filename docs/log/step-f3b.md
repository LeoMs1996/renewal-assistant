# Step F3b — 修 X1 对账出的 2 条 degradation（t22）

- 任务：t22 / F3b（owner: deepagents-engineer）
- 输入：`docs/log/integration-contract.md`（integrator X1 对账）——I5-c、I5-d 两条 degradation
- 范围：只改 `claims/deep_agents/**`；未触碰 `claims/graph.py`、`claims/config.py`、`claims/SPEC-claims.md`、`server/**`、`SPEC.md`
- 结果：**两条都修了**，F3 测试 75 → **82 passed**；F2 `claims/tests` **56 passed**；全仓 **148 passed, 2 skipped**；隔离性用 inode/mtime 级证据证明（不是路径字符串）。

---

## A. I5-c｜`CLAIMS_DATA_DIR` 不覆盖 F3 材料工作区（已修）

### 根因

`claims/deep_agents/materials.py` 的 `materials_root()` 把路径写死成模块相对路径：

```python
# 修复前
def materials_root() -> Path:
    """材料工作区根：`claims/data/materials`（**不是**仓库根）。"""
    return Path(__file__).resolve().parents[1] / "data" / "materials"
```

而 `claims/config.py` 里所有运行态路径都走 `data_dir()`（读 `CLAIMS_DATA_DIR`）：
`checkpoint_db()` / `idempotency_dir()` / `analysis_cache_dir()` 都在它下面——**只有 F3 的材料工作区不在**。
后果正如 X1 所说：`claims/tests` 的 `tmp_env` 把 `CLAIMS_DATA_DIR` 指到临时目录，
F2 自己的 checkpoint/cache/幂等登记都跟着走了，**F3 仍然往仓库 `claims/data/materials/` 写**。
而且我原来的 `safe_workspace_root()` 还会以硬编码根做白名单，于是"传 `/tmp` 进来"直接
`UnsafeWorkspaceRoot` 被拒——**错误地拒绝正确的配置，同时默默接受错误的默认值**。

### 改法（一行语义变更 + 注释）

```python
# 修复后
def materials_root() -> Path:
    """材料工作区根：**`<CLAIMS_DATA_DIR>/materials`**（默认 `claims/data/materials`）。"""
    try:  # 只 import 不改：配置权威在 F2 的 claims/config.py
        from claims import config as claims_config
        base = Path(claims_config.data_dir())
    except Exception:  # pragma: no cover - claims.config 不可导入时退回模块相对路径
        base = Path(__file__).resolve().parents[1] / "data"
    return base / "materials"
```

要点：
1. **配置权威留在 F2**：我不复制一份常量、也不新增 config 字段，直接复用 `claims.config.data_dir()`
   （该函数每次调用都读环境变量，所以 `monkeypatch.setenv` / subprocess 传入都即时生效，不是 import 时缓存）。
2. `safe_workspace_root()` 的白名单基准同步改成 `materials_root()`，因此"允许的根"会跟着 env 走；
   但**仓库根 / 仓库上级 / `/` 仍然拒绝**（安全断言没有被放松，见测试 5、6）。
3. 需要 F2d 做的：无。`claims/config.py` 不需要新字段——`data_dir()` 本来就存在，是我之前没接。

### 隔离证明（不是路径字符串，是文件系统事实）

`claims/deep_agents/tests/test_workspace_isolation.py`：对仓库 `claims/data/` 做
`(inode, mtime_ns, size)` 全树快照，分析前后必须逐字相同；同时断言工作区确实落在
`CLAIMS_DATA_DIR` 之下（`keep_workspace=True` 时能看到 `manifest.json` 与 `doc-0001.txt`）。

端到端演示（真实跑一次分析 + 跑完 F2 整套测试）：

```
仓库 claims/data 快照条目数 (before): 1
analyze: ANALYZE_OK mode= deepagents
跑完 analyze 后条目数: 1 | 与 before 相同: True
CLAIMS_DATA_DIR 下的工作区: ['analysis-4kslon_6']
pytest claims/tests: 56 passed in 0.56s
跑完 F2 全部测试后条目数: 1 | 与 before 相同: True
```

（快照条目数从早先的 8 变成 1，是因为我顺手清掉了 §E-5 说的两处**修复前**探针残留目录；
剩下这 1 条就是空的 `materials/` 目录本身。关键是 **before == after**，不是数字大小。）

即：**设了 `CLAIMS_DATA_DIR` 之后，无论 F3 直接调用还是 F2 整套测试，仓库 `claims/data` 零新增/零修改**。

新增 6 个测试：

| 测试 | 断言什么 |
|---|---|
| `test_claims_data_dir_moves_workspace_and_leaves_repo_untouched` | 仓库 `claims/data` 快照完全不变 + 工作区落在 env 根下（含 manifest/材料文件） |
| `test_claims_data_dir_moves_workspace_with_default_cleanup` | 默认清理路径下同样不写仓库，且 `analysis-*` 用完即删 |
| `test_materials_root_follows_env_each_call` | `materials_root()` 逐次读 env（a→b 切换即时生效），未设时回落到 `claims/data/materials` |
| `test_safe_workspace_root_base_follows_env` | 白名单基准随 env 漂移；新根内的子目录被接受 |
| `test_repo_root_still_rejected_even_when_env_points_elsewhere` | 改根**没有**放宽安全断言：仓库根/上级/`claims`/`/` 仍拒；新根外的路径也拒 |
| `test_workspace_under_env_root_cannot_read_repo_dotenv` | 换根后 `../.env`、`../../.env`、绝对路径 `.env` 仍读不到，且异常/payload 不含 `ANTHROPIC`/`sk-` |
| `test_timeout_leaves_no_workspace_behind` | **失败路径也清理**：超时抛 `AnalysisTimeout` 后，仓库零新增且 `analysis-*` 不残留（补的是清理逻辑的异常分支，不是 happy path） |

---

## B. I5-d｜F3 自带的 6 个未登记 env（清单交给 F2d 登记）

F3 读取的、**由 F3 自己解释语义**的 6 个变量（SPEC §8.1 与 `claims/config.py` 均未登记）。
全部只在需要时才读，未设置时都有安全默认值，**不会因为缺失而静默改变行为**。

| # | 变量 | 默认值 | 生效点（代码位置） | 影响 | 建议 SPEC 登记口径 |
|---|---|---|---|---|---|
| 1 | `DEEPAGENTS_MODEL` | **未设置**（→ `NoModelConfigured` 显式失败） | `analyzer.resolve_model()` | 决定用哪个 provider/model。取值 `provider:model`；特殊值 `project` = 复用项目 `ANTHROPIC_*` 凭证。**未设置时本层不会调用任何外部 API**（避免"打开开关就花钱"） | 「F3 模型选择；未设置则本层拒绝运行并让 F2 降级；`project` 复用项目凭证」 |
| 2 | `DEEPAGENTS_TIMEOUT_S` | `120` | `AnalysisConfig.from_env()` → `_run_graph_with_deadline()` | 单次材料分析的墙钟预算（主线程 `stream` 逐步检查）。超时抛 `AnalysisTimeout`（`code=ANALYSIS_UNAVAILABLE`）。非法/≤0 回落默认 | 「F3 单次分析超时秒数，默认 120」 |
| 3 | `DEEPAGENTS_MAX_ATTEMPTS` | `2`（最小值 1） | `analyze()` 重试循环 | **仅对 `ANALYSIS_SCHEMA_INVALID` 重试**（契约：内部重试 1 次）。调大会成倍增加 token 消耗 | 「F3 schema 失败重试次数，默认 2（=1 次重试）」 |
| 4 | `DEEPAGENTS_RECURSION_LIMIT` | `40`（最小值 4） | `_run_graph_with_deadline()` → `invoke(config={"recursion_limit": ...})` | 限制 Deep Agents 图的步数，防工具调用死循环。过小会导致 `StructuredOutputRetriesExhausted`。与 F1 的 `recursion_limit=40` 对齐 | 「F3 子图步数上限，默认 40」 |
| 5 | `DEEPAGENTS_SUBAGENTS` | `true` | `build_agent()` | 材料 **>3 份**时是否启用两个子代理（`photo-inspector`/`document-reader`）+ `TodoListMiddleware`。置 false 可省 token，但失去同轮并行与分步进度 | 「F3 多材料是否启用子代理，默认 true，仅 >3 份时生效」 |
| 6 | `CLAIMS_ANALYSIS_KEEP_WORKSPACE` | `false` | `AnalysisConfig.from_env()` → `analyze()` 的 `finally` | 是否保留材料工作区（`<data>/materials/analysis-*/`）供排障。**开启会把材料副本留在数据目录**（含 PII），需同时考虑磁盘与脱敏/留存策略 | 「F3 是否保留材料工作区，默认 false（用完即删）」 |

**不属于 F3 自有、但 F3 依赖的两个既有变量**（已在 F2 的配置侧，无需新登记）：

| 变量 | 现状 | F3 用途 |
|---|---|---|
| `CLAIMS_DATA_DIR` | F2 `config.data_dir()` 已支持 | **本次修复后**决定 F3 材料工作区根（`$CLAIMS_DATA_DIR/materials`） |
| `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN`（或 `ANTHROPIC_API_KEY`）/ `MODEL_NAME`（或 `ANTHROPIC_MODEL`） | 续保域既有，经 `server.config.env()` 读取（进程 env > 项目 `.env`） | 仅在 `DEEPAGENTS_MODEL=project` 时用于构建 Anthropic 兼容客户端 |

**给 F2d 的一句话需求**：把上表 6 行加进 SPEC §8.1 配置表即可；`claims/config.py` **不需要**加字段
（F3 自己读 env，不做 subprocess、不改 F2 配置对象）。若 F2d 希望统一收口到 `claims/config.py`，
可以加 `deepagents_model()/deepagents_timeout_s()/deepagents_max_attempts()/deepagents_recursion_limit()/
deepagents_subagents_enabled()/claims_analysis_keep_workspace()` 六个函数，我这边改为调用它们，
但**这不是必须的**（当前无重复解析逻辑，只有 6 个 `_env_*` 辅助函数）。

---

## C. schema 零偏差确认（X1 的 I2 结论与我实现一致）

**结论：一致，无 shape 级暗差。** 我用脚本把三方对齐核了一遍（F2 规则输出 ↔ F3 pydantic 最终结构）：

```
=== 1) model_validate(rules_output) ===
   OK -> MaterialsAnalysis
   rules keys : ['analyzer', 'claim_id', 'cost', 'coverage', 'documents', 'missing_items', 'schema_version']
   model keys : ['analyzer', 'claim_id', 'cost', 'coverage', 'documents', 'missing_items', 'schema_version']

=== 2) 递归 shape 对比（键集合 + 类型） ===
   shape equal: True
   （documents[*] = {doc_id,kind,facts,consistency_notes,anomalies}；
     facts[*] = {key,value,confidence,evidence{doc_id,span,quote}}；
     analyzer = {mode,model,version}；coverage = {requested_docs,analyzed_docs}；
     cost = {tokens_in,tokens_out,tool_calls}）

=== 3) forbidden fields ===
   both OK（无 amount/payout/decision/approved/deductible/liability...）

=== 4) 可选字段默认值 & None vs 缺省 ===
   doc with only doc_id -> {"doc_id": "d1", "kind": "", "facts": [], "consistency_notes": [], "anomalies": []}
   missing_item with only key -> {"key": "k", "why": ""}
   cost defaults -> {'tokens_in': 0, 'tokens_out': 0, 'tool_calls': 0} | claim_id -> ''
   explicit None for optional str? -> REJECTED: ValidationError

=== 5) facts 缺 evidence.quote 必须拒 ===
   OK 拒绝: ValidationError
```

**我知情的 5 处「非 shape」差异**（都不是 schema 漂移，但契约读者应知道）：

1. **`None` 一律不接受**：所有可选字段的默认值是 `""` / `[]` / `0`，**没有一个是 `None`**；
   显式传 `claim_id=None` 会被 `ValidationError` 拒。这与 F2 规则实现一致（它也从不产出 `None`），
   所以不存在"同一字段一边 `None` 一边缺省"的暗差。
2. **`analyzer.version` 的取值不同**（不是 shape）：F2 报 `"rules-1"`，F3 报真实 deepagents 版本 `"0.7.39"`；
   调用方传入的 `analyzer_version`（F2 传的是 rules 版本号）**不会被回填**——否则真·deepagents
   运行会被标成 `rules-1`，契约 §4.3 硬约束 4 的"降级可观测"失真。
3. **`documents[*].anomalies` 里会出现 F3 私有的码**：`skipped_by_model`、
   `quote_not_verbatim:<n>`、`kind_mismatch:<a>!=<b>`、`unknown_doc_id_dropped:<n>`。
   schema 上合法（`list[str]`），但**F2 的 `logic.flags_for` 不认识这些 token**（它们只进轨迹，
   不参与 `flags` 判定）。若 F2 希望它们也进 `flags`，需要约定枚举——目前按"仅供参考"处理。
4. **空材料行为差异（非 schema）**：`docs=[]` 时 F3 抛 `MaterialMissing`（`MATERIAL_MISSING`），
   而 `rules_analyzer` 返回 `documents=[]` 的正常结构。F2 的 `except Exception` 兜底会走到规则实现，
   所以端到端不受影响。
5. **`MaterialsAnalysisDraft` 是 F3 内部类型**，不是契约类型：它只含
   `schema_version/documents/missing_items`，作为 `response_format` 给模型；
   `analyzer/coverage/cost/claim_id` 由**代码**填。契约 §4.3 的 `MaterialsAnalysis` 才是对外结构。

---

## D. 验收原文

```
$ .venv-claims/bin/python -m pytest claims/deep_agents/tests -o addopts="" -q
........................................................................ [ 88%]
.........                                                                [100%]
82 passed in 4.60s
```

```
$ .venv-claims/bin/python -m pytest claims/tests -o addopts="" -q
..............................................                           [100%]
56 passed in 0.70s
```

```
$ .venv-claims/bin/python -m pytest -o addopts="" -q            # 全仓（.venv-claims）
148 passed, 2 skipped in 1.39s
```

隔离证明见 §A（仓库 `claims/data` 快照 before == after，逐字相同；工作区落在 `CLAIMS_DATA_DIR` 下）。

---

## E. 遗留

| # | 事项 | 说明 |
|---|---|---|
| 1 | 6 个 env 未进 SPEC 配置表 | 清单已在上文 §B，等 F2d 登记；`claims/config.py` 无必改项 |
| 2 | `anomalies` 私有码未与 F2 `flags` 对齐 | 见 §C-3；若要纳入 `flags`，需双方约定枚举（属契约变更） |
| 3 | 若 `CLAIMS_DATA_DIR` 指向仓库内（如 `claims/data`），F3 仍会写仓库 | 这是**配置本身的语义**（用户显式要求写那里），不是隔离失效；测试覆盖的是"指到仓库外必须真的出去" |
| 4 | 真实 LLM 的"同轮多 tool_calls"仍未验证 | F0/F3 已两次标记，本次未涉及 |
| 5 | 已清理两处**修复前**的探针残留（`claims/data/materials/analysis-o_jfruvk` 05:22、`analysis-y62k4os6` 08:23） | 是我早前用 `/tmp/real_run.py`、`/tmp/probe_loop.py` 跑真实模型时留下的合成演示材料，非本次代码泄漏；已删除，并补 `test_timeout_leaves_no_workspace_behind` 覆盖失败路径清理 |
