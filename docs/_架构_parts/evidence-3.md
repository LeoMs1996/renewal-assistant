# evidence-3：§5 培训材料对照 + §6 超出作业要求/遗留（主上下文取证 2026-11-24 14:55–15:00）

> 取证方式：培训材料只取标题/要点行（剥标签 grep），未读正文；行号复用 evidence-1/2（grep 真实返回）；标注「待核」者为未查证。

## §5 培训材料对照

材料位置：`../培训的html/Harness 架构设计七项要素-下午场-04.html`、`../培训的html/运行时架构与九大模块-上午-03.html`
七项要素的课程定义（原文）：「一份方案能不能上，不看它有多少组件，而看这**七类契约**是否齐备、每个不变量是否有对应的检查点」；每项要素必须给出三件事：**契约落在哪、拿什么证据验收、什么情况直接否决**。

### 表 A：七项要素（七类契约）× 本项目

| 要素（原文） | 契约落点 | 验收证据 | 否决情形 |
|---|---|---|---|
| 任务范围与完成标准 | `SPEC.md` §7 验收清单 19 条；`eval/cases/AC-01..14 + SEC-01..05` | `eval/run.py` 一键跑 + `--diff` 回归 | hard 断言失败（越权/编造）→ 整轮 FAIL |
| 三层责任与组件调用图 | `server/graph.py:1373–1403`（StateGraph + 11 add_node + 边）；`server/app.py` 7 条路由（62/176/296/309/322/352/367）；`mcp_servers/quote_server.py` | AC-14 轨迹节点链可回放 | 保费数字非来自报价服务（SPEC 硬规矩）|
| 阶段状态与产物依赖 | `graph.py:1403 compile(checkpointer=)`；理赔 `claims/graph.py:161` SqliteSaver；闸门 `graph.py:1391 clarify→END` + 会话续接 | AC-13 报价版本校验；checkpointer 重启继续（1C 批次验证） | 版本陈旧 → 409 `QUOTE_VERSION_STALE`（1A [08] 实测） |
| 工具与授权契约 | `server/security.py authorize_tool_args`；`server/middleware.py:157–216` 鉴权；`quote_server.py` 唯一 MCP server | AC-13 a4 → 422 `OWNER_MISMATCH`（hard，1A [08] 实测） | 跨车主确认 = 硬失败防线 |
| 门控与失败分支 | `graph.py:1159 await_confirm_node`；理赔 `claims/graph.py:381 interrupt()` / `:637 Command(resume)`；LLM 降级 SPEC §4.6 | AC-09 JQX_REQUIRED 不询价（1A [07]）；`done.degraded` 字段 | 删交强险 → 纠正 + 不报价；LLM 不可用 → 降级事件 |
| 版本升级与恢复策略 | durability：续保 `graph.py:62` 读环境变量；理赔 `:637` 硬编码 `"sync"`；递归上限硬编码 40（`app.py:223`） | SPEC 非破坏性追加（v1.0.4→v1.0.6 可选字段） | **X-03** 状态双真源未合并（见 §6 表 B） |
| 评测与回滚证据 | `eval/run.py`（`--baseline eval/baseline.json`，McNemar 成对检验）；`traces/`；`reviews/INDEX.md` | 三轮评审 6→13→14 演进 | 相对基线显著退化 → `--fail-on-regression` 退出码 1 |

### 表 B：九大模块 × 本项目

| 模块（原文） | 落点 | 证据 / 备注 |
|---|---|---|
| ① 状态存储与 Checkpoint | `graph.py:1403`；`claims/graph.py:161` | AC-14 PASS（seq 连续 + `/trace` 回放）；X-03 双真源 |
| ② 上下文与记忆管理 | `server/memory.py:663–821`（`build_context_package` 768 / `trim_turns` 699 / `summarize_turns` 729）；预算 `config.py:161/168` | `server/context_assembly.py` **不存在**；长期记忆写入唯一调用点 `sessions.py:102` |
| ③ 执行循环与终止控制 | 11 节点条件边 `graph.py:1385–1402`；`recursion_limit=40` 硬编码 `app.py:223` | `RENEWAL_RECURSION_LIMIT` 入口未生效（待核） |
| ④ 任务规划与动态调整 | 6 个 `route_after_*` 函数（**未读，不能断言**）；选择键归一化 `SPEC.md:206`（v1.0.2） | 相同 coverage_selection 复用报价不重算 |
| ⑤ 异常恢复与人工接管 | `server/llm.py LLMUnavailableError` → 规则降级；SPEC §4.6 `llm_degraded`；理赔人工决策 `claims/graph.py:637` | **X-05** 无节点级超时 |
| ⑥ 工具与 Skill 管理 | `skills/renew_compare.md`（加载方式**未读**）；`mcp_servers/quote_server.py` | 「组织比较流程，不等于拥有定价权」——保费只来自报价服务 |
| ⑦ 执行隔离与权限控制 | `security.py authorize_tool_args`；`middleware.py` 鉴权；`scan_untrusted`（`security.py:213`）**只标记不拒绝** | 未配置 `RENEWAL_API_KEYS` = 演示模式匿名放行（`middleware.py:157–216`） |
| ⑧ 生命周期钩子与门控 | `graph.py:1159` + `:1391`（续保无 `interrupt()`）；理赔 `claims/graph.py:381` 原生中断 | **X-04** 未采用官方 HITL（续保域） |
| ⑨ 可观测与评测接口 | `trace.py:91 TraceRecorder.record`（0600）/ `:160 read_trace` 再脱敏；`/metrics` 14 指标（1A [04]） | `eval/run.py --diff`；OTel 导出（`otel_export.py`，待核行号） |

## §6 超出作业要求的能力 + 遗留项

### 表 A：作业原文未要求、项目已落地的能力（依据 `SPEC.md:5` 版本摘要 + evidence-1 §1 的 24 框清单）

| 能力 | 引入版本 | 落点 | 作业是否要求 |
|---|---|---|---|
| API-Key 鉴权 / owner 由凭证派生 / trace_id 白名单 | v1.0.4（2026-11-13）SPEC §4.5 安全契约 | `middleware.py:157–216`（鉴权放行分支） | **否**（24 框中无鉴权框）→ 超出 |
| 限流 + 安全响应头（CSP / x-frame-options / …） | v1.0.4 | `middleware.py:271`（x-frame-options，小写）；其余行号见 evidence-2 §4 | **否** → 超出 |
| SEC-01~05 对抗用例（验收清单扩为 19 条） | v1.0.4 | `eval/cases/SEC-01..05.json` | 作业只要求 14 验收场景 → 超出 |
| 官方 checkpointer 持久化 | v1.0.4 | `graph.py:1403` | 作业要求「重启后继续」→ **是**（非超出） |
| LLM 降级可观测（`llm_degraded` 事件 / `done.degraded` / 轨迹 `mode,degraded`） | v1.0.5 | SPEC §4.6；`server/llm.py` | **否** → 超出 |
| 严格模式（LLM 不可用即 503 而非静默降级） | v1.0.6（2026-11-17） | SPEC §4.1 / §5；`/health llm_strict` | **否** → 超出 |
| §4.5.1 安全增强 | v1.0.6 | SPEC §4.5.1（内容**未读**） | 待核 |
| 评测回归检验（McNemar 成对 / `--fail-on-regression`） | 待核 | `eval/run.py` CLI | 作业要求「回归对比」→ **是**（检验方法超出） |

### 表 B：遗留项（原文 `reviews/INDEX.md:221–225`，均「未闭环」）

| 编号 | 一句话 | 来源域 | 证据 |
|---|---|---|---|
| X-03 | 状态双真源（checkpointer vs `sessions.json`）未合并；只有 `memory_tool divergence` 对账工具 | 编排 P1 / 记忆 F6 | `reviews/INDEX.md:221` |
| X-04 | 未采用官方 HITL `interrupt()` / `Command(resume=)`（续保域） | 编排 P1（需 SPEC 升版 + 前端 + eval） | `reviews/INDEX.md:222` |
| X-05 | 无节点级超时（`TimeoutPolicy` 仅支持 async 节点，本项目 11 节点全 sync）；现以工具重试 + provider 超时兜底 | 编排 P1 | `reviews/INDEX.md:223` |
| X-07 | `retrieve_terms` 在 `evidence_coverage==0` 时应路由到 `clarify`；需改 20 条边快照 + SPEC §6.2 + eval 断言 | 知识 §7.4 + 编排 §7.5 | `reviews/INDEX.md:225` |

补充：X-02（记忆域未登记 SPEC，`grep memory_ SPEC.md`=0）、X-06（轨迹 schema 缺 model/provider）、X-08（7 条 stale 条款待业务方）同表相邻行，未在本任务范围。
