# 架构与 Harness 设计 — 证据表（一）

> 方法：`grep -n` 定位 → `read` ≤80 行窗口；所有行号均为 grep 真实返回，未找到即标「未找到」。
> 项目根：`renewal-assistant/`；作业原文：`../课后作业-车险续保助手.html`
> 生成：2026-11-24

## §1 作业架构图 → 代码落点

**图源**：`../课后作业-车险续保助手.html` 第 140 行 `<h2>02 整体架构</h2>`；SVG 容器 143 行起；desc（145 行，原文）：「自上而下为入口层、Harness 控制层、能力层与数据层；Harness 内部由计划、执行、观察构成执行循环，可回到计划重新执行；右侧可观测与评测层贯穿每一次运行。」循环回边说明（185 行，原文）：「循环：未达成或出现新信息 → 回到「计划」重新执行；受步数上限与无进展退出约束」。

**代码拓扑锚点**：`server/graph.py:1373` `StateGraph(RenewalState)` → 1374–1383 共 11 个 `add_node` → 1385–1402 固定边/条件边 → 1403 `builder.compile(checkpointer=checkpointer)`。

| 作业图中的框（HTML 行） | 文件:行 | 一句话 |
|---|---|---|
| **入口层 · 车主交互（任选其一）** | | |
| Web / H5 对话（158） | `server/app.py:62` `@app.get("/", include_in_schema=False)` | 根路由且不入 API 文档，惯例为返回页面；返回体未读 |
| 命令行对话（159） | `scripts/demo_chat.py`（仅 ls 命中，内容未读） | 脚本文件存在；驱动方式未在本次 grep 范围 |
| API 服务 + 脚本（160） | `server/app.py:176` `/chat`、`:296` `/policy/{owner_id}`、`:309` `/trace/{trace_id}`、`:322` `/confirm`、`:352` `/health`、`:367` `/metrics` | FastAPI 六条业务/运维路由，覆盖对话→保单→轨迹→确认→健康→指标 |
| **Harness 控制层 · 计划、执行循环与闸门** | | |
| 计划与任务分解（169） | `server/graph.py:1374` intake、`:1376` parse_needs、`:1377` clarify；条件边 `:1386` `:1389` | 入口分流→解析需求→缺信息追问；是**确定性节点路由**，非模型自主规划 |
| 上下文装配（170） | `server/graph.py:1375` get_policy、`:1378` retrieve_terms、`:1379` quote | 原保单、条款片段、报价三个节点把材料装进 State；预算/压缩逻辑不在本次 grep 范围 |
| 执行与工具调用（MCP·超时重试）（171） | `server/graph.py:1375` get_policy_node、`:1379` quote_node；`server/mcp_bridge.py`、`mcp_servers/quote_server.py`（均仅 ls 命中） | 工具在节点内显式调用；「超时重试」落点见 §2「LLM 降级」行 |
| 观察与结果判定（172） | `server/graph.py:1380` compare；条件边 `:1394` route_after_quote | 比较两方案、判定预算是否达成，决定继续/等待/转人工 |
| 状态与检查点（173） | `server/graph.py:1403` `compile(checkpointer=checkpointer)`；`server/sessions.py`（ls 命中） | LangGraph checkpointer + 会话存储双轨；thread_id 落点见 §2 |
| 失败与人工升级（174） | `server/graph.py:1383` fallback、`:1402` `add_edge("fallback", END)`、`:149` RIDE_HAILING_WORDS | 超范围（网约车）/缺依据 → fallback → END 转人工 |
| 停止与确认闸门（175） | `server/graph.py:1381` await_confirm、`:1382` confirm、`:1397` `add_edge("compare","await_confirm")`、条件边 `:1398` `:1400`、`:143` CONFIRM_WORDS | 确认只能经 confirm 节点，校验有效方案后才放行 |
| 循环与分支控制（176） | `server/graph.py:1386` `:1389` `:1392` `:1394` `:1398` `:1400` 六条 `add_conditional_edges`；`:1391` `add_edge("clarify", END)  # await_user 挂起` | 分支由 6 个 `route_after_*` 函数决定；「挂起」= 走到 END 后靠会话存储续接，**不是** LangGraph `interrupt()`（§1 第 3 条 grep 零命中） |
| 循环回边：未达成/新信息 → 回「计划」（185） | `server/graph.py:1391` clarify→END；固定边中无回到 intake 的边 | 跨轮回到起点由 `/chat` 每轮重新 invoke 承担；6 个 `route_*` 目标未读，**不能断言**图内是否有回边 |
| **能力层 · 模型与工具（可替换）** | | |
| RAG 条款检索（194） | `wiki/` 11 文件（annual-inspection/csx/deductible/dsx/index/jqx/log/rate-surcharge/README/ride-hailing/ywyw）；`server/wiki_search.py`；`server/graph.py:1378` | 条款语料目录 + 检索模块 + retrieve_terms 节点；检索算法未读 |
| Skill 续保比较（195） | `skills/renew_compare.md`（ls 命中）；`server/graph.py:1380` compare | 单一技能文件，由 compare 节点消费；加载方式未读 |
| MCP 保单与报价（196） | `mcp_servers/quote_server.py`（目录内**唯一** server 文件）；`server/mcp_bridge.py` | 只有报价 MCP server；保单读取走 `app.py:296` HTTP 路由，**mcp_servers/ 下无 policy server** |
| **数据与外部服务 · 使用合成数据** | | |
| 车主与原保单（205） | `server/app.py:296` `@app.get("/policy/{owner_id}")`；`server/graph.py:1375` | 保单按 owner_id 经 HTTP 路由读取；合成数据文件未查 |
| 模拟报价服务（206） | `mcp_servers/quote_server.py`；`server/graph.py:1379` quote_node | 保费由报价服务计算，模型不编数 |
| 条款知识库（207） | `wiki/`（含 `index.md`、`log.md`） | 片段与版本由 wiki 目录管理（log.md 疑为版本日志，未读） |
| **可观测 · 可评测（贯穿每一次运行）** | | |
| 执行轨迹 Trace（213） | `server/trace.py`（ls 命中）；`server/app.py:309` `/trace/{trace_id}` | 轨迹模块 + 按 trace_id 查询接口 |
| 日志与指标（214） | `server/metrics.py`（ls 命中）；`server/app.py:367` `/metrics`、`:352` `/health` | 指标端点 + 健康检查 |
| 评测数据集（215） | `eval/cases/`、`eval/baseline.json`、`eval/baseline-llm.json`（ls 命中） | 固定样本目录 + 两份基线 |
| 判定器（216） | `eval/dimensions.py`、`eval/lint_cases.py`（ls 命中，未读） | 评测维度与用例校验脚本 |
| 回归与对比（217） | `eval/report-*.md`（多份按时间戳命名，ls 命中） | 每次评测落一份报告，可对比通过率 |
| 失败样本回流（218） | 未找到 | 仅凭 eval/ 目录清单无法确认；`eval/cases/` 内容未查 |

> §1 第 3 条 grep（`interrupt\(|Command\(resume` 于 `server/`，排除 test）**返回 0 行**。含义：续保域没有 LangGraph 原生中断/恢复调用；「闸门」靠 `clarify→END`（1391）+ `await_confirm` 节点 + 会话存储实现。

## §2 Harness 执行循环证据

**取证说明（诚实纪律）**：
- 规定 grep（`server/graph.py server/app.py server/llm.py`，`head -40`）**打满 40 行且全是 graph.py**（止于 1413），app.py/llm.py 被截断 → 已对两文件**分别补跑**同一模式（各 `head -25`，未截断）。
- §1 第 3 条在 `server/` 零命中，但理赔代码实际位于 `claims/`（含 `graph.py`/`api.py`/`deep_agents/`），故**扩展**：对 `claims/ --include='*.py'` 跑同一模式 + `interrupt\(|Command\(resume`，排除 test，`head -40`（命中 30 行，未截断）。
- 「无进展退出」不在本次 grep 模式内，两域均**未查**。

| 机制 | 续保域落点（文件:行） | 理赔域落点（文件:行） |
|---|---|---|
| 计划/路由 | `server/graph.py:1373` StateGraph → `:1374–1383` 11 节点；条件边 `:1386 :1389 :1392 :1394 :1398 :1400`；`:1357` route_after_await_confirm；`:1345` `return "confirm"  # 跨轮确认` | `claims/graph.py:595` `compile(checkpointer=self.checkpointer)`（图入口；节点/边定义行不在本次模式内，**未查**） |
| 执行/工具调用 | `server/graph.py:1375` get_policy_node、`:1379` quote_node（§1 拓扑 grep） | **未查**（本次模式不含 add_node/工具调用） |
| 观察/判定 | `server/graph.py:1394` route_after_quote（compare 1380 后分流）；`:1159–1175` await_confirm_node 输出待确认项并 `_emit("await_confirm")` | `claims/graph.py:126` 人工审核决策节点 docstring；`:315` `degraded = mode=="rules_fallback"`；`:320–334` 写入 `analysis_degraded` |
| 循环上限 / durability | `server/graph.py:65` `RECURSION_LIMIT=int(config.env("RENEWAL_RECURSION_LIMIT","40"))`；`:60` 注释 recursion_limit/superstep/GraphRecursionError；**:223 app.py `config={"recursion_limit": 40}` 硬编码**，app.py 中 `RENEWAL_RECURSION_LIMIT` 零命中 → 环境变量在 /chat 入口疑未生效；`:62` `GRAPH_DURABILITY=config.env("RENEWAL_GRAPH_DURABILITY","sync")` | `claims/graph.py:620 :636` `"recursion_limit": 40`（同样硬编码）；`:637` `durability="sync"` 硬编码于 resume；`:612` docstring「durability 与 recursion_limit 都是顶层 config 键」 |
| interrupt 闸门 | **未找到**（`interrupt(`/`Command(resume` 于 server/ 零命中）。实际闸门 = `:1391` clarify→END + `:1159` await_confirm_node：图走完后靠会话续接；`:10 :12` 注释自称「挂起」「跨轮实现」 | `claims/graph.py:381` `decision = interrupt(`（`:380` 注释：第一行且唯一一处，不得 try/except）；`:637` `Command(resume=decision)`；`claims/api.py:22–23` Context7 要点：同一 thread_id + 被中断节点从头重跑 |
| checkpointer / thread_id | `server/graph.py:1403` `compile(checkpointer=checkpointer)`；`:77` `_make_checkpointer()`；`:1372` docstring「None 时不持久化」；`:36–42` 注释（官方 checkpointer，Context7 查证）；`:42` thread_id 为 checkpoint 主键；`:114` 从 tup.config 取 thread_id；`:1413` docstring「注入 checkpointer 主键——app.py 的 config 不带 configurable.thread_id」（app.py 中 thread_id 零命中） | `claims/graph.py:161` `SqliteSaver(self._conn)`；`:145` 持有 sqlite checkpointer；`:600 :628 :640` `get_state({"configurable":{"thread_id":…}})`；`claims/api.py:215`「thread_id 必须等于 claim_id」；`:208` claim_id 确定性复算可作 thread_id；`:660` 默认取 claim_id |
| 失败升级 / 转人工 | `server/graph.py:1383` fallback 节点 + `:1402` `add_edge("fallback", END)`；`:149` RIDE_HAILING_WORDS（§1 拓扑 grep）；`handoff` 三文件**零命中** | `claims/graph.py:126` 人工审核决策（interrupt 等 reviewer）；`:605 :633` 终态/无挂起中断 → `CLAIM_STATE_INVALID`；`handoff` 零命中 |
| LLM 降级 | `server/llm.py:27` `class LLMUnavailableError`；`:51` `degraded: bool`；`:90–98` 严格模式抛异常；`:103` `_degraded_text`；`:165–167 :219 :259–263` 返回 `degraded=True`；`server/graph.py:33` 导入、`:167` State.llm_degraded、`:242–243 :265 :275–278` `_emit("llm_degraded")`、`:844 :1155 :1310` 并入 State；`server/app.py:34` 导入、`:276` done 帧 `degraded`、`:277` `except LLMUnavailableError`、`:359` `/health` `llm_degraded_total` | `claims/graph.py:11` 注释 `claims.llm_degraded`；`:315–334` `analysis_degraded`（rules_fallback）；`claims/api.py:102` `rules_only_degraded`、`:182` 输出 `analysis_degraded`；`LLMUnavailableError` 在 claims/ **零命中**（理赔用字段标记，续保用异常类+字段双轨） |

**两域设计差异（由上表行号直接推出，非推测）**：
1. 闸门实现相反：理赔用 LangGraph 原生 `interrupt()`/`Command(resume)`（381/637）；续保用 `clarify→END`（1391）+ 会话存储，无原生中断。
2. 递归上限两域都**硬编码 40**（app.py:223；claims/graph.py:620/636）；续保虽定义 `RENEWAL_RECURSION_LIMIT` 环境变量（graph.py:65），但 /chat 入口未引用。
3. 降级留痕：续保 = `LLMUnavailableError` 异常（严格模式）+ `llm_degraded` 列表双轨；理赔 = `analysis_degraded`/`rules_only_degraded` 布尔字段，无异常类。
