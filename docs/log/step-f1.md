# step-f1.md —— F1 架构设计（理赔域）

> 任务：**t9 [f1] — F1 架构设计：LangGraph 确定性流程 × Deep Agents 材料分析（中断/幂等/审核/支付）**
> 执行人：flow-engineer（AgentTeams `insurance-intel-2026`，attempt 2 / `attempt_id=b0d8af93-f373-437f-9e5c-90f6a74eb236`）
> 时间：2026-11-18（+0800）
> 交付：`claims/SPEC-claims.md`（v1.0.0 定稿，330 行）、`claims/ARCHITECTURE.md`（289 行）、本文件
> 依赖：t3（R3 框架基线）、t1（LLM-Wiki 规范）——两者已完成，本文件只消费不重做

---

## 1. 改动清单（只新增文件，续保域零改动）

| 文件 | 类型 | 说明 |
|---|---|---|
| `claims/SPEC-claims.md` | **改写**（C0 占位 → v1.0.0 定稿） | 四段流程契约：11 态状态机 + 迁移表、每段入参/出参/中断点/幂等语义/错误码、`MaterialsAnalysis` 严格 schema、`ReviewDecision`、14 个错误码、事件与轨迹口径、**CLM-01~20 + SEC-CLM-01~04 可测验收**、复用/隔离表 |
| `claims/ARCHITECTURE.md` | **新增** | 拓扑 mermaid、节点职责与失败边界、持久化、Deep Agents 唯一调用点与降级、interrupt 设计、幂等/支付、**逐函数复用接线**、被否决方案 9 条、风险 6 条 |
| `docs/log/step-f1.md` | 新增 | 本文件 |
| `docs/log/step-f1-arch.md` | 新增（指针） | 任务卡文件名指向本文件，避免重复维护 |

**未改动**：`server/**`、`tests/**`、`mcp_servers/**`、`wiki/**`、`SPEC.md`、`claims/graph.py`（仍是 C0 占位，等 t10）。验证见 §4 [V1]。

---

## 2. 决策与依据

### 2.1 已定稿的关键决策（每条都有外部来源或实测支撑）

| # | 决策 | 依据 | 若被否决会怎样 |
|---|---|---|---|
| D1 | LangGraph 1.2.20 用 `interrupt(value, *, response_schema=)` + `Command(resume=)`，**全流程唯一中断点** `review_gate` | R3/S1（官方现行 HITL 原语，`response_schema` 需 ≥1.2.12，本机 1.2.20）；S8 实测签名 | 用 `interrupt_before` 会失去「payload 校验 + 决策型 resume」；多点 interrupt 因 resume **按索引**匹配，极易错位 |
| D2 | `interrupt()` 放节点函数**最前面**、不被 `try/except` 包裹；副作用一律后置 | S1（节点 resume 从函数头重跑；`GraphInterrupt` 是异常控制流） | 审核后重跑会把「发通知/写库」执行两遍 |
| D3 | 幂等键由 **`reserve_payment_key` 独立节点**生成并先 checkpoint；`execute_payment` 只读 | S3（官方反例 K1/K2 → 双扣）；S2（崩溃场景需 `durability="sync"`） | 在支付节点内生成 → 崩溃重试必重复扣款 |
| D4 | `execute_payment` **不挂 retry**，用 `error_handler` → `payment_unknown` → `reconcile_payment` 查单 | S3（「缺失 ACK 视为未知，而非未发生」） | `max_attempts=3` 会对不可逆操作重复调用 |
| D5 | Deep Agents 只作 `analyze_materials` 一个调用点，输出 `materials-analysis/1` 严格 schema（**无金额/结论字段**） | R3/S5（官方 workflow vs agent 口径）；S6（`create_deep_agent -> CompiledStateGraph`，可当子图/节点内调用） | 让 agent 当主控 → 步数与副作用不可预测，且金额不可审计 |
| D6 | checkpoint = `SqliteSaver("claims/data/checkpoints.sqlite")`，`thread_id = claim_id`，`durability="sync"`，`recursion_limit=40` 显式传 | S2/S4/S8（默认 10,007；跨进程恢复已实测） | 用 `MemorySaver` → 重启丢状态，CLM-10 无法通过 |
| D7 | 轨迹复用 `server.trace.TraceRecorder`，**只用既有 11 种 record_type**，理赔语义放 `event` | 本机实测 `RECORD_TYPES` 白名单 + `record()` 非法值 `raise ValueError` | 新增 record_type 等于改续保（违反方案 C） |
| D8 | 轨迹/知识/checkpoint 三处物理隔离：`traces-claims/`、`data/llm-wiki-claims/wiki`、`claims/data/` | C0（`server/config.py` 已支持 `TRACE_DIR`/`WIKI_DIR`，零改动） | 写 `traces/`、`wiki/` 会污染保护对象（C0 基线 §7） |
| D9 | SSE **不新增 event 名**，审核挂起复用 `await_confirm` | `SPEC.md` §4.1 的 12 类事件口径（避免前端分裂） | 新增事件需改前端与续保契约 |
| D10 | `DEEPAGENTS_ENABLED=false` 为默认，`rules_analyzer` 产出**同 schema**（`analyzer.mode="rules_fallback"`） | t15 尚在安装 `deepagents`；CLM-15 要求端到端可跑 | 环境缺包 → t12 集成直接卡死 |

### 2.2 被否决的备选方案（详见 ARCHITECTURE §10）

| 方案 | 否决理由 |
|---|---|
| A. Deep Agents 当主控流程 | 官方 workflow/agent 口径 + agent 无步数上限 + 违背 I2/I3/I4 |
| B. 支付节点内生成幂等键 | 官方明示双扣反例（S3） |
| C. 支付挂 retry | 不可逆操作不可重试（S3） |
| D. 二次 `interrupt()` 确认支付 | resume 重跑 → 重复扣款；多 interrupt 索引易错 |
| E. `MemorySaver` | 重启即丢（S2） |
| F. fork `server/trace.py` 加 record_type | 违反零改动；白名单强校验会失败 |
| G. `materials_analysis.facts` 直连 `payable_amount` | 违背 I1（金额必须纯函数算） |
| H. 模型输出自然语言结论给审核员 | 无结构化出处 → 不可测不可审计 |
| I. 每次分析新 thread + 留全轨迹 | checkpoint 膨胀（S2 坑） |

### 2.3 未采信 / 存疑（如实登记）

- `docs.langchain.com/.../langgraph/durable-execution` 已**重定向**到 Persistence 页（R3 实测）；durability 三档的权威出处改引 `checkpointers` 页。本文件中未引用该旧 URL。
- 本轮 `web_call search.run` 全部 provider 失败（exa/ddg/github），检索改用 `read.fetch` + `curl` 直取官方原文并落盘（R3 §2 有完整记录与 sha256）。**本任务未新增抓取**，全部复用 R3 的 23 个证据文件（同一会话、同一日、`docs/research/evidence/`）。

---

## 3. 关键设计要点（给 t10/t11 的落地口径）

1. **拓扑**：`intake → verify_precheck → analyze_materials → verify_assemble →（缺件回 need_info）→ assess_amount → route_risk →{review_gate | auto_approve}→ reserve_payment_key → execute_payment →{finalize | reconcile_payment}→ END`。
2. **唯一 interrupt**：`review_gate`；`response_schema=ReviewDecision`；`allowed_decisions=["approve","reject"]`（不给 edit）。
3. **唯一 Deep Agents 调用点**：`analyze_materials` 节点内 `claims/deep_agents/analyst.py::run_analysis()`；返回 Pydantic `MaterialsAnalysis` → JSON；**无金额/结论字段**。
4. **幂等**：`payment_key = sha256(claim_id|policy_no|payable_amount|approval_version)`，只在 `reserve_payment_key` 生成（先落盘），`execute_payment` 只读。
5. **复用接线**（只 import，不改源码）：
   - `server/trace.py` → `TraceRecorder` / `read_trace`（`TRACE_DIR=traces-claims`，0600 权限，11 种 record_type）
   - `server/security.py` → `redact_row/redact_obj/redact_text/sanitize_input/scan_untrusted/wrap_untrusted/neutralize_delimiters/authorize_tool_args/SecurityViolation/guard_system_prompt/pii_mode`
   - `server/metrics.py` → `observe_record/finish_turn/turn_counts/render/reset`
   - `server/memory.py`（可选）→ `put/get/active_items/search/render_brief`，键空间加 `claims:` 前缀
   - `server/wiki_search.py` → `WikiSearch(wiki_dir=...)`（`WIKI_DIR=data/llm-wiki-claims/wiki`）
   - `server/config.py` → `TRACE_DIR`/`WIKI_DIR` 环境变量注入
6. **新增环境变量**（需 t10 在 `claims/config.py` 内实现，**不改 `server/config.py`**）：`DEEPAGENTS_ENABLED`、`DEEPAGENTS_PYTHON`、`CLAIMS_CHECKPOINT_DB`、`CLAIMS_AMOUNT_REVIEW_THRESHOLD`。

---

## 4. 命令与真实输出（验证）

```bash
cd /Users/leoms/Documents/deepseek-harness-workspace/homework5/renewal-assistant
```

### [V1] 续保域零改动（隔离）

```bash
git diff --stat 40541d1 -- server tests mcp_servers wiki SPEC.md | tail -3
```
输出：**（空）** → 通过。`git status --porcelain` 仅显示 `?? claims/`、`?? docs/`、`?? data/`、`?? traces-claims/`、`M .gitignore`。

### [V2] 交付物规模

```bash
wc -l claims/SPEC-claims.md claims/ARCHITECTURE.md
```
输出：
```
     330 claims/SPEC-claims.md
     289 claims/ARCHITECTURE.md
     619 total
```

### [V3] mermaid 拓扑自检（保留字冲突）

```bash
python3 - <<'PY'   # 提取 mermaid 块内所有节点 id，与 Mermaid 保留字比对
...
PY
```
输出：
```
node ids(16): ['analyze', 'assemble', 'assess', 'auto_approve', 'finalize', 'intake', 'need_info', 'pay', 'pay_failed', 'precheck', 'reconcile', 'reject_post', 'reject_pre', 'reserve', 'review_gate', 'route_risk']
冲突: 无 ✅
```

### [V4] `MaterialsAnalysis` schema 自检（可解析 + 无危险字段 + 带出处）

```bash
python3 - <<'PY'   # 取 SPEC 中 materials-analysis/1 的 JSON 块 → json.loads → 检查顶层键
...
PY
```
输出：
```
JSON 解析 ✅；顶层键: ['analyzer', 'claim_id', 'cost', 'coverage', 'documents', 'missing_items', 'schema_version']
危险字段: 无 ✅
facts 均带 evidence.quote: True
命中 materials-analysis 代码块: 1
```

### [V5] 复用 API 签名核对（实读源码，非记忆）

```bash
TRACE_DIR=traces-claims WIKI_DIR=data/llm-wiki-claims/wiki .venv/bin/python - <<'PY'
# 反射打印 server.trace/security/metrics/memory/wiki_search/config 的公共签名
PY
```
关键输出（节选）：
```
TRACE_DIR = PosixPath('traces-claims')
WIKI_DIR  = PosixPath('data/llm-wiki-claims/wiki')
RECORD_TYPES = ['assistant_message','error','llm_call','llm_degraded','llm_response',
                'node_end','node_start','retrieval','tool_call','tool_result','user_message']
TraceRecorder(trace_id: str, session_id: str, trace_dir: Path | None = None)
TraceRecorder.record(record_type, *, node, event, input, output, latency_ms, tokens_in,
                     tokens_out, error, mode, degraded, error_type)
redact_row(row: dict) -> dict ; scan_untrusted(text: str) -> dict
authorize_tool_args(tool: str, arguments: dict, session_owner: str | None) -> None
observe_record(row: dict) -> None ; finish_turn(trace_id, duration_s, outcome) -> None
put(owner_id, field, value, *, kind, source, confidence, ttl_days, reason) -> dict
active_items(owner_id, *, kind=None, now=None) -> list[dict]
WikiSearch(wiki_dir: Path | None = None, channels: tuple[str, ...] = DEFAULT_CHANNELS)
```
→ 契约 §8 与 ARCHITECTURE §8 的每一行都对应上述真实签名（无杜撰函数名）。

---

## 5. 遗留与交接

| # | 事项 | 接手方 |
|---|---|---|
| 1 | `claims/graph.py` 仍是 C0 占位（`NotImplementedError`）；按本 SPEC/ARCH 实现节点与装配 | t10 |
| 2 | `claims/deep_agents/analyst.py` + `schema.py`（Pydantic `MaterialsAnalysis`）+ prompt | t11 |
| 3 | `claims/tools/payment_gateway.py`（以 `payment_key` 为幂等键的模拟网关）、`verify_quote.py`（逐字子串校验）、`rules_analyzer.py`（降级） | t11 |
| 4 | `deepagents` 安装（`.venv-claims`）与双跑验证 | t15（已派发） |
| 5 | 20 条 CLM + 4 条 SEC-CLM 落成 pytest（当前 `claims/tests/` 为空占位，`pyproject.toml` 的 `testpaths` **不含** claims，需 t12 决策是否并入默认收集） | t10/t11/t12 |
| 6 | `claims/config.py`（上述 4 个新环境变量） | t10 |
| 7 | 阈值 `CLAIMS_AMOUNT_REVIEW_THRESHOLD=3000` 是**演示值**，真实规则需业务确认 | 队长/业务 |

---

## 6. 补记（append-only）

- 2026-11-18：首版定稿。`SPEC-claims.md` 从 C0 占位升级到 v1.0.0；`ARCHITECTURE.md` 新增。
