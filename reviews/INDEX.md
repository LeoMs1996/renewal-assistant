# renewal-assistant 2026 技术基线评审 · 汇总索引

> **本文件是 9 份分域报告的单一入口**，供 t10 集成回归与最终交付使用。
> 生成者：integrator-ds（AgentTeams `renewal-assistant-2026-review` · t14 · attempt 2）
> 生成时间：2026-11-17 21:35 CST
> 数据来源：**逐份打开 9 份报告正文核对**（不是复制任务书表格）+ 只读静态复核
> （`ruff check .` / `mypy` / 文件清点 / 一次 `pytest` 只读复跑，`TRACE_DIR` 指向 `mktemp -d` 隔离）。
> 本次**未修改任何代码、未启动任何常驻服务、未跑 e2e**。

> ## ⚠️ 状态声明（必读）
> **安全域 t9 已定稿**（域评分 **4.5 → 7.7**，报告 45 KB / 445 行，F1–F12 全部落地；核对期间它从 429 行追加到 445 行，故以定稿版为准）。
> **安全域的所有结论最终以 `reviews/security.md` 为准**，本索引只引用其 §0/§3/§4/§6/§7/§8/§9 的当前快照。
> 另：`reviews/security-live-evidence.json`、`reviews/security-wiki-injection-evidence.json` 是**证据附件**，不是报告，不计入 9 份。

---

## 0. 索引速览（30 秒版）

| # | 事实 | 数字 |
|---|---|---|
| 1 | 9 域平均分 | **5.51 → 8.06**（**+2.54**，相对提升 +46%） |
| 2 | 评分分布 | 评审前最低 2.4（平台）→ 评审后最低 **7.7**（安全）；**9 域全部 ≥7.7** |
| 3 | 改进幅度 Top3 | 平台 **+5.9** / 记忆 **+5.0** / 安全 **+3.2** |
| 4 | 落盘规模 | 约 **73 个文件**（新增 ≈39 / 修改 ≈34，含 `deploy/` 9 个全新文件） |
| 5 | 新增测试 | **8 个新测试文件 + 1 个重写**；全量 `pytest` = **140 passed / 2 skipped**（本次只读复跑，退出码 0） |
| 6 | 代码门禁 | `ruff check .` → **All checks passed**；`mypy` → **Success: no issues found in 6 source files**（原 14 处已由 t16 修复，见 **X-01**，CI 门禁可过） |
| 7 | LLM 证据已补齐（原为唯一外部阻塞，现闭环） | 队长侧 `RENEWAL_LLM_STRICT=1` → **19/19 PASS / hard 0 / 36.1s / 零降级**；基线归档 `eval/baseline-llm.json`（stamp `20261117-213250`、mode=llm）。详见 §集成验证结论与 [`captain-verification.md`](captain-verification.md) |

**一句话结论**：本轮不是"把代码写好看"，而是把 9 个域里**"能力为 0 / 制度为 0"** 的地方补上——最大增量（平台 +5.9、记忆 +5.0）恰好对应"原来根本没有"（零部署物 / 无长期记忆），而不是"原来写得差"。**本稿初版曾挂着「X-01 类型错误」与「LLM 基线缺失」两项硬伤，二者已分别由 t16 与队长闭环（A-13/X-01）；但仍有 23 项未闭环遗留（X-02…X-24），"9 域全部 ≥7.7"仍不能被读成"可以交付了"。**

---

## 一、一页总览

### 1.1 评分总表（逐份核对报告 §评分 章节）

| 域 | 报告 | 评审前 | 评审后 | Δ | 起点性质 |
|---|---|---:|---:|---:|---|
| 平台工程 | [`platform.md`](platform.md) | 2.4 | 8.3 | **+5.9** | 零部署物、指标空转 |
| 记忆机制 | [`memory.md`](memory.md) | 2.7 | 7.7 | **+5.0** | 长期记忆=0、用户控制=0 |
| 安全合规 | [`security.md`](security.md) | 4.5 | 7.7 | **+3.2** | 注入防护=0、假绿灯 |
| 知识检索 | [`knowledge.md`](knowledge.md) | 6.0 | 8.0 | +2.0 | 引用只能到条目粒度、无指标 |
| MCP 工具层 | [`mcp.md`](mcp.md) | 7.0 | 8.5 | +1.5 | 协议语义（isError/annotations）缺失 |
| API / SSE | [`api.md`](api.md) | 6.5 | 8.0 | +1.5 | 手写框架已原生提供的机制 |
| 评测体系 | [`eval.md`](eval.md) | 6.5 | 8.0 | +1.5 | 判定层空白（无基线/无统计/文本门禁） |
| Agent 编排 | [`orchestration.md`](orchestration.md) | 7.0 | 8.3 | +1.3 | 三层 `except` 使官方韧性原语失效 |
| 前端 | [`frontend.md`](frontend.md) | 7.0 | 8.0 | +1.0 | 规范细节（CR 行尾 / TT / 动效偏好） |
| **平均** | 9 份 | **5.51** | **8.06** | **+2.54** | — |

**评分核对结果**：9/9 与任务书给定值**完全一致，无差异**。每个"前/后"值均取自各报告 §评分 章节的**域总评行**（不是子项算术平均，各域权重口径不同，不可跨域换算）。

### 1.2 本轮落地规模

按"各报告 changedPaths ∪ 本次目录实测清点"统计（`deploy/`、`scripts/`、`eval/`、`wiki/` 为实测文件数）：

| 类别 | 新增 | 修改 | 关键内容 |
|---|---:|---:|---|
| `server/` | 3 | 10 | `memory.py`(798 行)、`security.py`(395 行)、`otel_export.py`(402 行) |
| `mcp_servers/` | 0 | 1 | `quote_server.py`（isError + annotations） |
| `web/` | 0 | 1 | `index.html`（CR 行尾 / TT 策略 / reduced-motion） |
| `wiki/` | 3 | 8 | `index.md`/`log.md`/`README.md` + 8 条目 front-matter 与互链 |
| `eval/` | 6 py + `README-eval.md` + `baseline.json` | `run.py` + `cases/*.json`×8 | 统计/维度/lint/记忆评测/检索消融/中性哨兵 |
| `tests/` | 8 | 1（`test_metrics.py` 重写） | 见 1.3 |
| `scripts/` | 8 | 0 | wiki_tool / memory_tool / platform_check / security_check / trace_purge_pii / csp_browser_check / injection_live_check / poison_wiki |
| `deploy/` | **9** | 0 | Dockerfile/.dockerignore/compose/prometheus+rules/collector/k8s×2/README |
| 根目录与 CI | 0 | 5 | `SPEC.md`(v1.0.6)、`.gitignore`、`.env.example`、`ci.yml`、`pyproject.toml` |
| **合计** | **≈39** | **≈34** | **≈73** |

> 差异标注：`platform.md` §四 自述"`deploy/`（新增 **8** 文件）"但其清单实列 9 项；**实测 `find deploy -type f` = 9**，本文以 9 为准。（记为自检差异 F-1，见 §6.3）

### 1.3 新增测试与验证面

| 域 | 测试文件 | 源报告口径 | 本次静态核对 |
|---|---|---|---|
| 编排 t1 | `tests/test_orchestration.py`（新） | 6 组 / 25 条断言 | 6 个 test 函数 |
| MCP t2 | `tests/test_mcp.py`（新） | §四 自述"10 例"，§五 实测 **7 passed / 1 skipped** | **8** 个 test 函数（§四 与实测口径不一致，取实测） |
| 知识 t3 | `tests/test_wiki_retrieval.py`（新） | 12 条 | 12 |
| 记忆 t4 | `tests/test_memory.py`（新） | 16 条 | 16 |
| 平台 t8 | `tests/test_metrics.py`（重写 8）+ `tests/test_otel_export.py`（新 9） | 17 passed | 8 + 9 |
| 安全 t9 | `tests/test_privacy_injection.py`（新） | 34 例 | 25 个 test 函数（含参数化） |
| 评测 t7 | `tests/test_eval_tooling.py`（新，t13 增补） | 17 + 7 条 | 24 |
| LLM 降级 t11 | `tests/test_llm_degradation.py`（新） | 7 组 / 27 条断言 | 7 |
| API t5 / 前端 t6 | 无新增 pytest；前端用 node 行为测试 4 组 + `html.parser` 结构校验 | 2 passed（`test_sse.py`） | — |

**全量运行结果（本次只读复跑）**：`140 passed, 2 skipped in 1.33s`，退出码 0。
另有 2 个**脚本式**自测不计入 pytest 计数：`tests/test_llm_normalization.py`（15 通过）、`mcp_servers/test_quote_server.py`（54 通过 / 0 失败）。

**验证证据分四类（互不替代，别混读）**：

| 证据类型 | 覆盖域 | 代表证据 | 诚实边界 |
|---|---|---|---|
| 确定性单测/回归 | 9/9 | 140 passed / 2 skipped | 规则模式为主，不证明模型行为 |
| 评测门禁（19 用例 / 90 断言 / 31 hard） | 7 域间接 | `19/19 PASS`，hard 失败 0 | 单次运行；19 条处于"小样本噪声边界" |
| **真实 LLM** | 评测（队长）+ 安全 t9 | 评测：`RENEWAL_LLM_STRICT=1` → **19/19 PASS**、`llm_response` 27/27 为 `mode=llm`、**降级 0**；安全：LIVE-01~05,07 **6/6** + LIVE-06（投毒 wiki）**1/1** = **7/7** | 均为非规则兜底的真实调用；评测 LLM 基线由队长归档（A-13） |
| **真实浏览器** | 安全 t9 | Chrome + CDP **11/11**（CSP/TT/SSE/控制台零违规） | 仅 Chromium；Firefox/Safari 未测（安全 L7） |
| 部署物 | 平台 t8 | `platform_check.py` 4/4（含"告警引用的指标真被暴露"） | 镜像未 `docker build`、`promtool` 未跑、collector 未实跑 |

---

## 二、分域摘要（每域：最高危问题 → 关键落地 → 证据类型 → 边界）

### 2.1 平台工程 `platform.md`（2.4 → 8.3）
- **最高危**：F1「**指标空转**」——存量 387 个轨迹文件 7063 行里，`llm_response` **249/249**、`retrieval` **376/376** 缺 `latency_ms`，导致 `gen_ai.client.inference.duration` / `gen_ai.retrieval.duration` **自上线零样本**（仪表盘全空却看不出错）；F3 轨迹无 spanId/parent/status，**进不了任何 OTLP 后端**。
- **落地**：`trace.py` 唯一写入点用单调时钟派生缺省耗时（只写 SPEC §5 既有字段）；`metrics.py` 按 semconv 重写（补 3 个必填属性 + 5 个新指标 + 转义）；新增 `otel_export.py`；`deploy/` 9 文件（非 root 镜像 / 7 条告警 / 三探针 / 导出 sidecar）；`platform_check.py` 把"告警指标必须真实暴露"变成断言。
- **证据**：确定性（17 单测 + 自检 4/4 + 798 条真实轨迹 → 7330 spans）。
- **边界**：镜像未构建、promtool 未跑；`/metrics` 无鉴权；多副本语义未验。

### 2.2 记忆机制 `memory.md`（2.7 → 7.7）
- **最高危**：F1「**跨会话记忆为 0**」（`sessions.py` 以 session_id 为键，换会话即失忆）；F2「三处固定条数截断（20/8/6）无 token 预算无压缩」，实测 30 轮上下文 **1640 tokens 且无上界**，早期"预算 5000"被裁掉。
- **落地**：新增 `memory.py`（798 行，零新依赖，与 `BaseStore` 同形契约）：owner 命名空间 + 写时白名单 + recency-wins 显式失效 + 衰减排序 + TTL + evict-last；`trim_turns`/`summarize_turns` 把上下文压到 **975 tokens 有界**；`memory_tool.py` 提供 list/show/audit/export/forget/doctor/divergence。
- **证据**：确定性（16 单测 + A/B 5 场景 **0/5 → 5/5** + **报价中性哨兵 7 轮保费逐轮相同** `VERDICT: PASS`）。
- **边界**：召回只认"显式指代"（保守设计）；摘要为确定性抽取而非 LLM；双真源未合并。

### 2.3 安全合规 `security.md`（4.5 → 7.7）✅ **t9 已定稿**（F1–F12 全部落地，报告 45 KB / 445 行）
- **最高危**：F1「存量 967 个轨迹文件中 **687 个**含姓名/车牌/VIN 原文，`/trace` API 原样回吐」；F2「**提示注入零输入/输出侧控制**——规则模式下 `/chat` 根本不把用户原句交给模型，原 SEC-01~04 的绿灯是'路径不存在'而非'防线有效'」；F3「`compare` 输出不含免责声明（硬规矩 #3 在 LLM 模式靠运气）」；F12「LLM 客户端无超时 → `/chat` 实测挂死 1.5~2.1 小时」。
- **落地**：新增 `security.py`(395) + `tests/test_privacy_injection.py`(34) + `scripts/security_check.py`(12 项 CI 门禁) + `trace_purge_pii.py`（已执行 687 文件/1667 行）+ `csp_browser_check.py` + `injection_live_check.py` + `poison_wiki.py`；写端读端双脱敏、文件 0600、CSP 强制 Trusted Types、422 `INVALID_INPUT`、`/chat` 独立限流桶。
- **F12 单列（可用性，原报告此条最容易被漏读）**：LLM 客户端原沿用 SDK 默认（**10 分钟超时 + 2 次重试**），真实凭证下 `/chat` 实测**挂起 1.5 小时 / 2.1 小时**才返回；现 `config.llm_timeout_s()`（默认 **30s**）+ `llm_max_retries()`（默认 **1**），最坏 ~60s。
- **证据**：**三类互不替代**——规则模式确定性（CI 门禁）+ **真实 LLM 7/7** + **真实 Chrome 11/11** + 真实模型下 429 语义实测（200/200/429 + `Retry-After=55`）。
- **边界**：限流仍进程内内存、未按 API-Key 计；`sessions/*.json` at-rest 仍存原文；仅 Chromium；注入检测是正则信号（`scan=low` ≠ 安全）。

### 2.4 知识检索 `knowledge.md`（6.0 → 8.0）
- **最高危**：KB-1「引用只到**条目**粒度、无章节锚点，答案里的条款归因不可核验」；KB-3「8 条条款 `effective_date` 全为 2024-01-01（2.9 年未复核），stale claim 无检测」。
- **落地**：`wiki/` 重构为 LLM-Wiki（index/log/schema + 36 章节锚点 + 20 条双向互链）；`wiki_search.py` 重写为三通道 + RRF(k=60)，引用下沉到 `wiki_id#章节` + 逐字 span + `evidence_coverage`；`wiki_tool.py` 三操作 + 进 CI；17 条标注集消融。
- **证据**：确定性（12 测试 + 消融 Hit@1 0.81→0.88、MRR@5 0.896→0.938、接地率 0.85→0.90、**负样本正确拒答**）。
- **边界**：**主动记录"混合检索在 8 条语料上无统计显著差异"**（Hit@3 恒为 1.00），未夸大为算法升级；层级检索 D 被证伪未启用；条款内容未复核。

### 2.5 MCP 工具层 `mcp.md`（7.0 → 8.5）
- **最高危**：F1「业务错误不以 `isError:true` 返回」——`query_quote` 的 8 类校验失败以 `{"error":{...}}` 正常 payload 返回，**LLM 客户端在协议层无法区分成败**，违反 MCP 2026-07-28；F2「`MCP_TRANSPORT=stdio` 是死代码」，且注释声称存在 `tests/test_mcp_e2e.py`（该文件不存在，文实不符）。
- **落地**：`_emit()` 出口抛 SDK `ToolError`（→ `isError=true`）；两工具补 `title` + `ToolAnnotations`；桥接层接入 `STDIO_MODE` 并还原 `{code,message}`；新增 `tests/test_mcp.py`（含 stdio 全链路 initialize → tools/call 成功/isError 双路）。
- **证据**：确定性（7 passed / 1 skipped，`MCP_TEST_STDIO=1` 则 8 passed；`test_quote_server.py` 54 通过）。
- **边界**：未声明 `outputSchema`（P2）；stdio 客户端无重连/健康检查（P3）。

### 2.6 API / SSE `api.md`（6.5 → 8.0）
- **最高危**：手写 SSE 管线**复刻了框架已原生提供的全部机制**（心跳、背压、结构化取消、wire 编码），而依赖已锁 fastapi 0.162.4（0.135+ 原生 SSE）；历史上正是这段手写收尾出过"哨兵不匹配 → 连接挂死"。
- **落地**：`/chat` 改 async 生成器 + `EventSourceResponse` 子类，帧改 `yield ServerSentEvent(...)`，**删除约 60 行**手写队列/心跳/取消。
- **证据**：确定性（`tests/test_sse.py` 2 passed，含"流自然收尾、末事件 done、id 递增"）。
- **边界**：`Last-Event-ID` 仅记录不续传（显式 `X-Resume-Supported: false`，诚实契约）；`retry:` 未加（无消费方）。

### 2.7 前端 `frontend.md`（7.0 → 8.0）
- **最高危**：G1「SSE 解析器只识别 `\n`/`\r\n`，**漏掉单独 `\r` 行尾**（WHATWG ABNF 明确 `cr` 单独即行尾）」；G2「20+ 处 `innerHTML` sink 无 Trusted Types 兼容层，而后端一旦下发 CSP 强制策略页面将整体 TypeError」。
- **落地**：行尾归一 + `feed.flush()`；注册 TT default 策略；`@media (prefers-reduced-motion: reduce)` 关闭 pulse。
- **证据**：确定性（node 行为测试 4 组全过：单独 CR/跨 chunk 拆 CR/EOF flush/id-only 不派发；`html.parser` 标签平衡 `HTML_OK`）。
- **边界**：TT default 策略是**透传**（不净化），真实浏览器验证在安全域完成；CSP 头由服务端下发。

### 2.8 评测体系 `eval.md`（6.5 → 8.0）
- **最高危**：F1「门禁依赖**报告文本**」——runner 恒 `return 0`，CI 用 `grep "^## ... — FAIL"`，格式一改静默失效；F2「无机器可读基线，`--diff` 逐行比 markdown 且**跨模式混比**」；F7「'配置模式'冒充'有效模式'」（`llm_mode=llm` 但 429 静默兜底）。
- **落地**：`stats.py`（断言级**成对精确 McNemar** + Wilson + `baseline.json`）、`dimensions.py`（10 维矩阵 + `KNOWN_GAPS`）、`lint_cases.py`（E1–E8/W1–W3 静态校验）、runner 三道门禁、hard 断言 **19 → 31**、t13 增 `--fail-on-degraded` + 参与度可追溯。
- **证据**：确定性 + **正反两向实验**（人为改 AC-13 期望 → 门禁阻断 exit 1；改 AC-02 → 判"无显著退化"，证明不误杀噪声）。
- **边界**：**真实 LLM 0 次调用**（`RateLimitError`，外部阻塞）；无语义 judge 维度；19 条处小样本边界。

### 2.9 Agent 编排 `orchestration.md`（7.0 → 8.3）
- **最高危**：F1「节点级 `RetryPolicy` **结构性失效**」——`llm.py` 的 `except Exception` 降级 + `_call_tool` 把异常收进返回值 → 图节点**永不抛异常** → 官方重试永不触发，故障被降级成"看起来成功的输出"；F2「`_RUN_LOCK` **无效且无必要**（文实不符）」，探针实测两路并发真并行、Saver 自带 `threading.Lock`；F3「落盘时机未声明 + 递归超限退化成 `INTERNAL`」。
- **落地**：`_call_tool` 分层重试（业务错不重试 / 传输错指数退避）；删除无效锁；`durability` 默认 `sync` + `recursion_limit` 天花板语义 + `GraphRecursionError` → `GRAPH_RECURSION_LIMIT`；拓扑快照回归测试。
- **证据**：确定性（25 断言 + 敏感度自证"人为改快照 → 2 条翻红" + 独立端口端到端 + eval 19/19）。
- **边界**：未迁移官方 `interrupt()/Command(resume=)`；无节点级超时（sync 节点编译期不支持）；双真源未收敛。

---

## 三、检索基线汇总

### 3.1 各域来源与站点（按报告 §检索基线 章节清点）

| 域 | 来源条数 | 覆盖的官方/权威站点 | 时间戳口径（报告自述） |
|---|---:|---|---|
| 编排 | 12 | docs.langchain.com（3 篇官方文档 + 1 错误页）、4 个 GitHub 工程仓、**langgraph 安装包源码实测 ×2** | 2026-11-17 11:59–12:06 |
| MCP | 4 | modelcontextprotocol.io（tools / stdio 两篇）、py.sdk.modelcontextprotocol.io、**SDK 2.3.0 源码实测** | 2026-11-13 |
| 知识检索 | 10 | Karpathy gist（一手来源）、github 考据仓、3 篇 DOI/ACL 论文、arxiv、2 个工程仓/社区 | 2026-11-17 12:00–12:09 |
| 记忆 | 9 | docs.langchain.com ×3、Oracle Developers、Hindsight、MediaNama、openai.com、ACL Anthology | 2026-11-17 |
| API | 4 | fastapi.tiangolo.com ×2（教程 + reference）、MDN、WHATWG HTML 规范 | 2026-11-13 |
| 前端 | 4 | WHATWG HTML Living Standard、MDN ×3（SSE / Trusted Types / reduced-motion） | 2026-11-13 |
| 评测 | 5 | arxiv（Kübler 统计退化）、promptfoo docs ×2、docs.langchain.com/langsmith、ossaihub | 2026-11-17 12:00–12:05 |
| 平台 | 9 | opentelemetry.io（semconv 迁移页 + OTLP 1.11.1）、semantic-conventions-genai ×5、prometheus.io ×2、kubernetes.io | 2026-11-17 11:59–12:07 |
| 安全 | 7 | genai.owasp.org ×4（LLM01/02/10 + Top10）、modelcontextprotocol.io（security best practices 2026-07-28）、MDN ×2（CSP TT 两指令） | 2026-11-17 12:20–12:55 |
| **合计** | **64** | **约 13 个独立官方/权威站点** | — |

**去重后的官方/权威站点清单**：`docs.langchain.com`（LangChain/LangGraph/LangSmith）、`modelcontextprotocol.io`、`py.sdk.modelcontextprotocol.io`、`fastapi.tiangolo.com`、`developer.mozilla.org`、`html.spec.whatwg.org`、`opentelemetry.io` + `github.com/open-telemetry/semantic-conventions-genai`、`prometheus.io`、`kubernetes.io`、`genai.owasp.org`、`openai.com`、`aclanthology.org`/DOI 出版方。

### 3.2 「先检索后评审」是否落实——**结论：9/9 域都建了检索基线章节，实质落实，但有 3 处必须如实标注的偏差**

**落实的硬证据**：
1. **9/9** 报告都有独立的 §检索/§基线 章节，**每行都带 URL**；不确定处普遍显式标「待验证」（记忆域 B9、编排域"interrupt 在 SSE 下的行为"、平台域 L1、安全域 L8）。
2. **规范→改动的因果链可追踪**：如 platform F2 的"必填属性"直接引 semconv 条文；api 的"删 60 行手写管线"直接引 FastAPI 0.135+ SSE 教程；security 的 CSP 指令直接引 MDN 两页（S6/S7）。
3. **检索推翻了训练直觉**：knowledge 域检索后发现"混合检索在 8 条语料无显著差异"，**主动放弃了"算法升级"的叙事**并保留被证伪的 `navigate()`；orchestration 域引用安装包源码**证伪了自己代码注释里的锁语义**。这类"检索结果与预期相反仍照实写"是本批报告最可信的部分。

**三处偏差（不美化）**：
1. **时间戳漂移**：任务书要求标注基线日 **2026-11-13**，但实际联网检索大多发生在 **2026-11-17**（编排/知识/记忆/平台/安全/评测均明确写"真实检索时间，不倒填"）。→ 结论仍属"2026-11 现行"，但**没有 2026-11-13 当日快照**，属待验证项；`api` / `mcp` / `frontend` 三份标注为 2026-11-13。
2. **来源构成混杂**：64 条中约 **6 条是"本机安装包源码实测"**（langgraph ×2、MCP SDK ×2、fastapi/sse ×1 等）而非联网规范；另有 1 条是运行时错误信息引用。它们是**更强的一手证据**，但按"检索来源"严格计应扣减。
3. **真实模型覆盖已从 0 扩到 2 个域（但有保留）**：安全域真实凭证 7/7 + 真实 Chrome 11/11；评测域由队长跑出 **19/19、27/27 真实调用、零降级** 并归档 LLM 基线。但：① 时间戳偏移不变——真实跑分发生在 2026-11-17，不是 11-13 当日；② 编排域的"实 LLM 模式"端到端仍含规则兜底成分；③ LLM 基线未进 CI 常规门禁。→ "2026 基线"在**代码/配置层已对齐**，在**模型行为层**已有点验证但**不构成持续保证**。

---

## 四、跨域遗留清单（最重要）

> 采集位置：`orchestration.md` §7.5+§六、`knowledge.md` §7、`memory.md` §7、`platform.md` §六、`eval.md` §七、`mcp.md` §六+P2/P3、`security.md` §7+§8、`frontend.md` §2.3、`api.md` §三。
> **闭环判定只认报告正文的 ✅ + 实测命令**，不认任务书声明。

### 4.A 本轮已闭环（跨域移交后被目标域关闭）——**14 项**

| # | 来源域 → 目标域 | 事项 | 闭环证据 |
|---|---|---|---|
| A-01 | 平台 → 安全 | 轨迹默认全量采集 PII（t8-L3） | 写端/读端双脱敏 + 存量 **687 文件 / 1667 行**清理 + 0600 + `no-store` |
| A-02 | 前端 → 安全 | CSP 头未下发（t6-§2.3） | `require-trusted-types-for 'script'; trusted-types default`，真实 Chrome **11/11** |
| A-03 | 平台 → 平台 | `metrics.py`/`otel_export.py` 在 mypy 门禁外（F12） | 门禁扩到 **6 files** 并全绿；后来记忆域新引入的 14 处已由 t16 修复（X-01 已闭环） |
| A-04 | 平台 → MCP/API | 3 处 `ruff I001` | t12 收口，本次复核 `ruff check .` → **All checks passed** |
| A-05 | MCP → 编排 | `server/llm.py:253 F821 Undefined name 'node'` | t12 定向上报，t11 补形参；`--select F821` 全通过 |
| A-06 | 安全 → 知识 | `wiki_search.py` 语法错误阻塞 pytest 收集 | 知识域复核**不复现**（`ast.parse` OK、`def tokens` 仅 1 处、收集成功） |
| A-07 | 知识 → 编排 | `graph.py:761` 对 `WikiEntry` 用下标 | 已是属性访问 `x.wiki_id`，跨域回归不存在 |
| A-08 | 知识 → 知识 | `evidence_coverage` 分母含语料外词（KB-5） | 改 in-corpus 分母，同一查询 **0.333 → 1.0** |
| A-09 | 评测 → 编排 | "静默兜底"根因（eval-F7 / P2） | t11 `llm_degraded` 事件 + `done.degraded` + `LLM_UNAVAILABLE`；t13 升级为 **hard 断言 + `--fail-on-degraded`** |
| A-10 | 评测 → 安全 | `/chat` 限流默认 20/min 误伤批量回归（6/19） | 改 60/min + `/chat` 独立桶 + `RENEWAL_RATE_LIMIT_DISABLED` |
| A-11 | 平台 → 平台 | 指标空转（llm_response/retrieval 无 `latency_ms`） | `trace.py` 唯一写入点派生；新写 **34 条 llm_response / 146 条 retrieval 全带** |
| A-12 | 评测 → 评测 | `results.json` 并行覆盖（t7 事故） | t13 加 `--results` 产物隔离（**归档目录仍未做 → 见 N-03**） |
| A-13 | 评测 → 队长 | **LLM 真实链路与基线缺失**（eval-F15 / P0 阻塞） | `RENEWAL_LLM_STRICT=1` → **19/19 PASS / hard 0 / 零降级**；基线归档 `eval/baseline-llm.json`（stamp `20261117-213250`、mode=llm、19 cases）。证据：[`captain-verification.md`](captain-verification.md) §1/§2 |
| A-14 | 安全 → 评测 | SEC-02/03 的 `message_not_contains` 有"否认式假阳性"风险（真实模型会写"不代表已完成投保"） | 评测侧已落地否认/澄清语境感知判定（`eval/run.py:686` 注释标 t15）：否认语境豁免、非否认命中仍判 FAIL（强度不降）；真实模型下 SEC-01~05 全 PASS。证据：[`captain-verification.md`](captain-verification.md) §5 |
### 4.B 未闭环（需 t10 或后续域）——原 16 项，**X-01 已于 2026-11-17 由 t16 闭环**，现余 **15 项**

| # | 来源域 | 事项 | 目标域 / 归属 | 状态 |
|---|---|---|---|---|
| ✅ **X-01（已闭环）** | 安全 §7（记忆域并行） | `server/memory.py` 曾有 **14 处 mypy 错误**（`Unsupported operand types for +` 等） | 记忆域（t16 knowledge-reviewer-ds） | **已修复**：队长侧 `.venv/bin/python -m mypy` → `Success: no issues found in 6 source files`（本次只读复跑一致）→ **CI mypy 门禁已可过**。保留此行仅为可追溯 |
| **X-02** | 记忆 F8 | SPEC 未登记记忆域（`memory_seeded`/`memory_ctx`、`/memory` API、保留期） | 队长 / SPEC | 未闭环。SPEC 已升 v1.0.6 但只登记了安全（§4.5.1）与 LLM 降级（§4.6），**`grep memory_ SPEC.md` = 0** |
| **X-03** | 编排 P1 / 记忆 F6 | 状态双真源（checkpointer vs `sessions.json`）未合并 | 编排域 | 未闭环；记忆域只给 `memory_tool divergence` 对账工具 |
| **X-04** | 编排 P1 | 未采用官方 HITL `interrupt()` / `Command(resume=)` | 编排域（需 SPEC 升版 + 前端 + eval） | 未闭环 |
| **X-05** | 编排 P1 | 无节点级超时（`TimeoutPolicy` 仅支持 async 节点，本项目 11 节点全 sync） | 编排域 | 未闭环；现以工具重试 + provider 超时兜底 |
| **X-06** | 平台 L2 + 安全 §7（**两次移交**） | 轨迹 schema 缺 `model`/`provider` → 历史 span 只能套用导出时配置 | 编排域（SPEC §5） | 未闭环；导出层给了 `--provider/--model` 应急 |
| **X-07** | 知识 §7.4 + 编排 §7.5（**两次提出**） | `retrieve_terms` 在 `evidence_coverage==0` 时应路由到 `clarify` | 编排 + 知识联合 | 未闭环；需改 20 条边快照 + SPEC §6.2 + eval 断言 |
| **X-08** | 知识 §7.1 | 条款 `effective_date=2024-01-01`（7 条 stale）内容复核 | **待业务方** | 未闭环（lint 只能报警，不能判定条款是否被新规替代） |
| **X-09** | 知识 KB-7 / 记忆 §7.1 | 稠密向量 / embedding 语义召回通道 | 知识 + 记忆 | 未闭环；`channels` 已参数化、`search(query=)` 已留位 |
| **X-10** | 记忆 §7.2 | LLM 摘要（对齐 `SummarizationMiddleware`） | 记忆域 | 未闭环；需凭证 + 破坏 CI 可复现性，`summarize_turns` 已解耦出 `summarizer` 位 |
| **X-11** | 知识 §7.5 | 中文分词 / BM25F 字段加权 | 知识域 | 未做；**四次替代实验均无增益**，故不下手（避免为指标堆通道） |
| **X-12** | 知识 §7.3 + 评测 P1 | 词法接地升级为"字段级核查 + LLM-as-judge"双轨 | 知识 + 评测 | 未闭环；需 ≥30 条人工校准集证明 judge 与人工一致率 |
| **X-13** | MCP P2/P3 | 未声明 `outputSchema`（TypedDict）；`_StdioClient` 无重连/健康检查 | MCP 域 | 未闭环 |
| **X-14** | API §三 | `Last-Event-ID` 真续传（需服务端事件缓冲）；`retry:` 字段 | API 域 | 未闭环（现状"不支持 + 显式声明 + 前端全量重发"） |
| **X-15** | API §三 / 前端 §2.3 | HTTP/1.1 每域 6 条 SSE 连接上限、多页签共享连接治理 | 平台 + 前端 | 未闭环（教学场景 1 条连接，未触发） |
| **X-16** | 安全 §7 → 前端 | TT default 策略是**透传**（`createHTML: s => s`），等价"有策略不净化" | 前端域 | 未闭环；当前风险由 `esc()`/`tx()` 手写转义承担 |

### 4.C 未闭环（运维/合规/流程类，归属明确但本轮不做）——8 项

| # | 来源域 | 事项 | 归属 | 状态 |
|---|---|---|---|---|
| X-17 | 平台 L4 | `/metrics` 无鉴权、无网络层保护（应 NetworkPolicy/反代限源） | 部署 + 安全 | 未闭环（已文档化豁免理由） |
| X-18 | 平台 L1 | 镜像未 `docker build`、`promtool check rules` 未跑、collector 未实跑 | 平台 / CI | 未闭环（仅结构 + "指标存在性"断言） |
| X-19 | 平台 L5 + 安全 L1/L2 | 多副本下：限流放大 N 倍、指标各算各的、SQLite checkpoint 非多副本方案 | 平台 + 安全 | 未闭环（Dockerfile 写死单 worker 属缓解，非解决） |
| X-20 | 安全 L4 | `traces/sessions/*.json` 仍含保单与对话原文，仅 `0600` + `.gitignore` | 安全 + 业务方 | 未闭环（需加密卷 / 保留期轮转 / 受控 KV） |
| X-21 | 安全 L6 | 供应链完整性：锁版本但无 SBOM / 哈希校验 / `pip-audit` | t10 / 平台 | 未闭环 |
| X-22 | 安全 L7 | 浏览器验证仅 Chromium；Firefox/Safari 未测 | 安全（上线前手测） | 未闭环 |
| X-23 | 安全 L9 | 无真实渗透/模糊测试（Schemathesis / ZAP baseline） | 安全 | 未闭环 |
| X-24 | 安全 L10 | 注入检测是正则信号（7 类），多语言混写 / 长距离拆分覆盖有限；`scan=low` ≠ 安全 | 安全 | 未闭环（定位为"标记 + 加固"辅助信号，不作放行依据） |

### 4.D 本轮新发现（本次核对 INDEX 时发现，非任何报告提出）——3 项，**N-01 已闭环**

| # | 事项 | 证据 | 建议 |
|---|---|---|---|
| ✅ **N-01（已闭环）** | `SPEC.md` 曾有重复的 `### 4.5.1 安全增强（v1.0.6）` 标题（第 287 行有正文、第 305 行仅一行指引的空壳），属并行编辑合并残留 | `grep -c "^### 4.5.1" SPEC.md` → 1；全文标题 `uniq -d` 为空（本次复测） | **队长 2026-11-17 21:41 删除空壳标题**：现 `SPEC.md` 435 行，`### 4.5.1` 仅剩 287 行一处（正文完整）、`### 4.6` 紧随其后 |
| **N-02** | `traces/` 现存 **991 个** `.jsonl`（平台域报 798、安全域报 967，均在不同时点）；测试污染已由 `conftest.py` 隔离修复，但存量未清理 | `ls traces/*.jsonl \| wc -l` | t10 决定是否归档/清理（影响 `/trace` 回放与导出统计口径） |
| **N-03** | `eval/report-*.md` 已累积 **40+ 份**、`report.md`/`results.json` 仍为共享产物 | `ls eval/report-*.md \| wc -l` | 对应 X-25 归档建议，t10 一并处理 |

### 4.E 待业务方 / 外部依赖（无法由工程侧闭环）

| # | 事项 | 归属 |
|---|---|---|
| O-01 | ✅ **已闭环（队长执行，2026-11-17）**：真实 LLM 严格模式 `RENEWAL_LLM_STRICT=1` → **19/19 PASS / hard 0 / 36.1s / 零降级**；基线已归档 `eval/baseline-llm.json`（stamp `20261117-213250`、mode=llm、19 cases）；`--diff` 跨模式报"不可比"而非错误结论 → 闭环 t7 指出的"LLM 基线缺失致 diff 失效"。详见 [`captain-verification.md`](captain-verification.md) | 队长（已完成） |
| O-02 | 保险条款内容是否被新规替代（7 条 2024 基线） | 业务方 |
| O-03 | 数据保留期 / 加密卷 / 迁移受控 KV | 业务方 + 安全 |
| O-04 | 模型层对齐（越狱/有害内容） | 模型供应商（外部风险） |
| O-05 | OWASP API Security 2023 原文本轮抓取全失败（`ACTION_FAILED`），安全域相关表述为**转述** | 待换网络/工具复核 |
| O-06 | Safari/Firefox 的 Trusted Types 行为 | 上线前手测 |

> **统计（本稿头版）**：A 组 **14 项**已闭环（含 A-13 LLM 基线、A-14 SEC 断言语境），另 X-01（t16）与 N-01（队长）也已闭环，累计 **16 项**；B+C 组 **23 项仍未闭环**（X-02…X-24，其中 X-02/X-06/X-07 需 SPEC 升版、X-08 需业务方决策）；D 组 3 项剩 2 项待处置；E 组 **5 项**交业务方/外部。**"跨域遗留 ≥10 条"已超额满足，且未把未闭环项粉饰为闭环。**

---

## 五、改进幅度榜

| 排名 | 域 | Δ | 类型判定 | 为什么是这个幅度 |
|---:|---|---:|---|---|
| 1 | 平台工程 | **+5.9** | **制度性缺陷**（零部署物、零门禁、测试污染生产观测数据、有仪表无数据）+ 实现缺失（semconv 必填/span 化） | 起点 2.4 = "可观测性只存在于源码"：有指标名零样本、轨迹进不了任何后端、仓库里没有一个部署文件。补齐这些是**从 0 到 1**，不是调优 |
| 2 | 记忆机制 | **+5.0** | **能力缺失**（长期记忆=0、用户控制=0）+ 制度性（SPEC 未登记记忆域、无双真源对账） | 起点 2.7 = "换会话即失忆、无查看/删除/导出"。新建 798 行 store + 策略层 + CLI，属**能力新建** |
| 3 | 安全合规 | **+3.2** | **制度性缺陷**（无安全门禁 + **假绿灯**：规则模式下注入路径不存在）+ 实现缺失（CSP TT、限流维度、LLM 超时） | 起点 4.5 的"通过"有一半是假的；真实凭证一上，两条既有违约立刻暴露（无免责声明 6/6、检测器漏判） |
| 4 | 知识检索 | +2.0 | 制度性（无 lint / 无指标 / 引用粒度）+ 实现缺失（三通道，增益不显著） | 起点 6.0 的条目内容质量尚可，缺的是**引用可审计性**与**可量化性**；且域自身承认"混合检索不是收益点" |
| 5 | MCP 工具层 | +1.5 | 实现缺失（协议语义：`isError`/`annotations`/死代码） | 起点 7.0 已扎实，缺的是 2026-07-28 规范的**错误通道语义**与 stdio 通道可验证性 |
| 6 | API / SSE | +1.5 | 实现形态（手写复刻框架已原生提供的能力） | 起点 6.5 = 全对但**自造复杂度**；删 60 行即达标，属"少写代码换分" |
| 7 | 评测体系 | +1.5 | **制度性缺陷**（门禁靠文本 grep、无基线、无显著性、坏用例伪装成缺陷） | 起点 6.5 的强项在执行层（确定性断言/独立手算保费），弱项**全在判定层**；补的是"能不能判" |
| 8 | Agent 编排 | +1.3 | **制度性缺陷**（三层 `except` 吞错使官方韧性原语**结构性失效**；无效锁文实不符） | 起点 7.0 的图设计本来就对，问题在**执行期语义**；修的是"故障能不能被看见/被重试" |
| 9 | 前端 | +1.0 | 规范细节缺失（单独 CR 行尾、TT 兼容层、动效偏好） | 起点 7.0 主体已达基线（SSE 消费、续传头、指数退避、XSS 转义都对），只差 3 个规范细节 |

**三点解读（避免误读）**：
1. **幅度 ≠ 质量**：`frontend` 只 +1.0 但终评 8.0，与 `knowledge` 的 8.0 同级；`platform` +5.9 是因为起点 2.4。跨域比"幅度"没有意义，比"终值"才有。
2. **+5 以上的两项都是"从无到有"**：平台（零部署物）与记忆（零长期记忆）——这解释了为什么它们的制度性/能力缺失占比最高。**这类缺陷在纯代码评审里最容易漏**，因为"没有的文件"不会出现在 diff 里。
3. **9 域全部 ≥7.7 不等于可交付**：X-01（mypy）与 N-01（SPEC 重复标题）已分别由 t16 与队长闭环，LLM 基线也已归档（A-13）；但仍有 **23 项未闭环遗留**（X-02…X-24），且其中 3 项需 SPEC 升版、1 项需业务方决策。

---

## 集成验证结论（引用队长侧独立验证，非本索引自跑）

> 队长已把独立验证整理为正式文件 **[`reviews/captain-verification.md`](captain-verification.md)**（95 行）。本节只做**摘要 + 引用**，不复述其全文；两者冲突时以该文件为准。t10（mcp-reviewer-ds）的 `reviews/INTEGRATION.md` 仍在生成，完成后可再补一版（**INTEGRATION 不覆盖 INDEX**）。

| # | 已实测项 | 结果 | 出处 |
|---|---|---|---|
| V-1 | **真实 LLM 严格模式全量评测** | `RENEWAL_LLM_STRICT=1` → **19/19 PASS，hard 失败 0，36.1s，零降级** | `captain-verification.md` §1 |
| V-2 | **LLM 基线归档** | `eval/baseline-llm.json`（stamp `20261117-213250`、`llm_mode=llm`、19 cases、109/109 断言、hard 50 零失败） | 同上 §2；本索引已只读核对文件元数据 |
| V-3 | **全链路 e2e（真实模型）** | `./scripts/e2e_smoke.sh 8731` → **phaseA + phaseB 全通过**（节点链 7 节点、MCP 真实调用 `get_policy`+`query_quote`×2、改保额重询价、条款问答带 citation、轨迹 28 行 seq 连续、跨重启回放、`/confirm` 422/409/404 矩阵、幂等同一 `ORD-20261117-1339`） | 同上 §3 |
| V-4 | **全量单测与 lint** | `pytest` **140 passed / 2 skipped**；`ruff check .` **All checks passed** | 同上 §4 |
| V-5 | **跨模式 diff 行为正确** | 报「基线模式=rule vs 本次=llm 不可比」，不再给出错误退化结论（t7-F2 闭环） | 同上 §2 |

**两点必须保留的不美化口径**：
1. `pytest`/`ruff` 绿 **不等于** 可交付：§四 仍有 **23 项未闭环遗留**（X-02/X-06/X-07 需 SPEC 升版，X-08 需业务方）；`mypy` 的 14 处曾红 CI，**已由 t16 修复**——本次只读复跑 `Success: no issues found in 6 source files`，CI 门禁可过。
2. 队长侧 §6 另列 5 项未覆盖：多副本/Redis 限流、Safari/Firefox、OWASP 原文逐条核对、渗透测试、**nightly 回归未做**、`traces/` 仍有约 **411** 个评审期测试轨迹未清理（对应本索引 N-02）。这些与本索引 §4.B/§4.C **交叉引用、不重复计数**。

---

## 六、索引自检

### 6.1 存在性与规模（本次核对 2026-11-17 21:33 CST）

| 报告 | 字节 | 行数 | 非空 |
|---|---:|---:|:--:|
| `reviews/orchestration.md` | 34,932 | 282 | ✅ |
| `reviews/mcp.md` | 12,623 | 123 | ✅ |
| `reviews/knowledge.md` | 29,522 | 256 | ✅ |
| `reviews/memory.md` | 33,668 | 399 | ✅ |
| `reviews/api.md` | 6,189 | 47 | ✅ |
| `reviews/frontend.md` | 7,308 | 71 | ✅ |
| `reviews/eval.md` | 35,043 | 362 | ✅ |
| `reviews/platform.md` | 24,306 | 210 | ✅ |
| `reviews/security.md` | **45,014** | **445** | ✅（t9 已定稿） |

**9/9 存在、非空、路径正确**（`ls reviews/*.md` 核对）。**不计入 9 份的附件/衍生文件**：`security-live-evidence.json`、`security-wiki-injection-evidence.json`（证据）、[`captain-verification.md`](captain-verification.md)（队长侧独立验证，95 行）、`INTEGRATION.md`（t10 待生成）。

### 6.2 关键章节矩阵（检索基线 / 评分 / Findings / 验证证据 / 遗留移交）

| 报告 | 检索基线 | 评分 | Findings | 验证证据 | 遗留/移交 |
|---|:--:|:--:|:--:|:--:|:--:|
| orchestration | ✅ §一 | ✅ §二 | ✅ F1–F8 | ✅ §五 | ✅ §六 + §7.5 |
| mcp | ✅ §一 | ✅ §二 | ✅ F1–F7 | ✅ §五 | ⚠️ **无独立"遗留"节**，P2/P3 散在 §三/§六 |
| knowledge | ✅ §3 | ✅ §1.1 | ✅ KB-1–KB-7 | ✅ §6 | ✅ §7 |
| memory | ✅ §3 (B1–B9) | ✅ §1.1 | ✅ F1–F8 | ✅ §6 | ✅ §7 |
| api | ✅ §一 | ✅ §四 | ⚠️ **无 Findings 表**，用"核心差距(High)" + 未落地清单 | ✅ §三 | ⚠️ "未落地"嵌在 §三 |
| frontend | ✅ §一 (S1–S4) | ✅ §五 | ⚠️ **无 Findings 表**，用 G1–G3 差距表（含规范依据） | ✅ §四 (V1–V3) | ✅ §2.3（跨域遗留项） |
| eval | ✅ §一 | ✅ §二 | ✅ F1–F15 | ✅ §6.2/§9 | ✅ §七 |
| platform | ✅ §一 | ✅ §二 | ✅ F1–F12 | ✅ §五 | ✅ §六 |
| security | ✅ §1 (S1–S7) | ✅ §9 | ✅ F1–F12 | ✅ §6（三类） | ✅ §7 + §8 |

**判定**：8/9 章节齐全；3 处**形式差异**不影响内容（`api.md`/`frontend.md` 用"差距表"代替 Findings 表；`mcp.md` 的遗留以 P2/P3 形式散落）。已在上表如实标注，未强行为它们"补章节"。

### 6.3 数字一致性抽查——**发现 4 处口径差异（均以实测为准，已在正文标注）**

| # | 位置 | 差异 | 处置 |
|---|---|---|---|
| F-1 | `platform.md` §四 | 自述"`deploy/`（新增 **8** 文件）"，但清单实列 **9** 项 | 实测 `find deploy -type f` = **9**（含 `README.md`），本文取 9 |
| F-2 | `mcp.md` §四 vs §五 | §四 自述"`tests/test_mcp.py` … **10 例**"；§五 实测 **7 passed / 1 skipped** | 静态核对 = **8 个 test 函数**；本文取实测 |
| F-3 | `security.md` §0 vs §9 | §0 写"真实 LLM **7/7**"，§9 写"真实 LLM **6/6**" | 二者不矛盾：**主链路 6/6 + 投毒 wiki 通道 1/1 = 7/7**（§6.2 逐条可查） |
| F-4 | 全批 | 全量 `pytest` 数字随时点漂移：76（t8/t3 时点）→ 83（t11/t12）→ 140（记忆域 t4） | 本次只读复跑 = **140 passed / 2 skipped**，为当前 HEAD 真值 |

### 6.4 本索引**未**复核的项（明确交接给 t10）

1. **全链路 e2e**：`scripts/e2e_smoke.sh`、`scripts/demo_chat.py`、MCP stdio 全链路 —— 本次按约束未跑。
2. ~~真实 LLM 严格模式全量评测 + `--save-baseline` 归档 `eval/baseline-llm.json`~~ → **已由队长执行并归档（A-13 / §集成验证结论 V-1·V-2）**；但 **LLM 基线尚未进 CI 常规门禁**（`ci.yml` 仍跑规则模式），属 t10 待决。
3. ~~`X-01` 的修复（`server/memory.py` 14 处 mypy）~~ → **已由 t16（knowledge-reviewer-ds）修复**，本次只读复核 `mypy` 全绿；本任务未代改代码。
4. **`deploy/` 真实构建与抓取**（`docker build` / `promtool check rules` / collector 实跑）。
5. **真实浏览器/跨浏览器**复验（仅在安全域报告内有效，INDEX 未重跑）。
6. **评分本身的复核**：INDEX 只核对"报告自述值 vs 任务书值"，**未独立重打分**（重打分属 t10/评审复核范围）。

> 自检声明：本文件只写了 `reviews/INDEX.md` 一个文件，未改任何代码、未改其他报告。
> 所有引用数字均来自 9 份报告正文或本次只读命令输出；不确定处标注"源报告未给出"或"待验证"。
