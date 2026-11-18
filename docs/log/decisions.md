# 决策台账（Decisions Ledger）

> **性质**：本文件是本次「理赔域（claims）+ INS-MMBench 萃取」全部关键决策的**唯一权威记录**。
> 只追加、不覆盖；若后续推翻某条，新增一条并标注 `supersedes: D-xx`，旧条保留以便审计演进过程。
>
> **为什么要有它**：任务书要求「全程自动生成文档，完整记录整套操作流程」。但分散在十几个 `step-*.md`
> 里的决策无法对账——C5 终验需要一份能逐条核对「决策 → 依据 → 影响」的台账。
>
> 记录时间：2026-11-18（Asia/Shanghai），项目根 `renewal-assistant/`。

| ID | 日期 | 决策 | 依据 | 影响范围 |
|---|---|---|---|---|
| D-01 | 2026-11-18 | **交付根 = `renewal-assistant/`（方案 C）**，废弃团队简介里的 `homework5/insurance-agent/` | 方案 C 同仓新增 claims 子域，复用已验证基础设施；新建项目需重做 trace/security/metrics/wiki 等 6 个模块。仓库 `insurance-agent/` 出现两次，均已合并进 renewal 后删除（比对 sha256 确认 renewal 为超集，零内容丢失） | 全队路径口径；C0 骨架 |
| D-02 | 2026-11-18 | **隔离靠环境变量，不靠改代码**：`TRACE_DIR=traces-claims`、`WIKI_DIR=data/llm-wiki-claims/wiki` | C0 实测 `server/config.py:42/44` 已支持两变量；注入后续保 `traces/` 文件数 1183→1183（零写入） | F1/F2/F3 接线；C5 隔离性验收 |
| D-03 | 2026-11-18 | **子集口径固定为 54 题**：`multi_step_property` 取 **6** 条，其余 4 个 `multi_step_*` 各 **12** 条；**禁止**按吞吐动态决定 k | R2 实测：HF 仓库只有 6 个 `.tsv`（2.70 GiB），图片 base64 内联，无 parquet；`huggingface.co` 不可达，镜像 30–200 KB/s。property 为 4 MB/行，12 条=48 MB 不确定性过大。固定 k 保证可复现 | D1 脚本；manifest |
| D-04 | 2026-11-18 | **排除 `fundamental.tsv`（1.44 GiB）**，登记为 Tier-2 局限；**D5 只报检索指标**（Hit@1 / MRR@5 / 引用接地率），**不报问答准确率**。**用户已确认按 A 走** | 5 个场景文件无 `answer` 列（队长用 `curl -r 0-65535` 独立验证 `multi_step_claim.tsv` 12 列无 answer；仅 `multi_step_property.tsv` 有 `claim_decision`）。`fundamental.tsv` 按任务排序，头部读只能取到第 1 个任务，分层不可行且体积不可承受 | D5 评测口径；论文/报告结论表述；**这是主动取舍，不是遗漏，必须在交付文档写明** |
| D-05 | 2026-11-18 | **deepagents 0.7.39 装入独立 `.venv-claims`（复制自 `.venv`），共享 `.venv` 一个字节不动** | R3 实测 `uv pip install --dry-run` 会把 `tenacity 9.2.1→9.1.4`（降级）、`langchain-core 1.8.0→1.8.1`（PyPI 元数据证实 deepagents 强制 `>=1.8.1`）。共享 venv 跑着 148 passed 的续保基线，不接受降级包进入 | F0 任务；F3 运行环境；交付需同时说明两套 venv 用途 |
| D-06 | 2026-11-18 | **`claims/tests` 不并入 `pytest` 默认收集**，`pyproject.toml` 的 `testpaths` 保持不变 | `148 passed, 2 skipped` 是续保基线的度量单位。口径一变，C0/C5 的「零回归」就无法对账。claims 测试用显式路径 `pytest claims/tests` 单独跑，C5 分别报告两套数字 | C5 终验口径；CI 配置 |
| D-07 | 2026-11-18 | `CLAIMS_AMOUNT_REVIEW_THRESHOLD=3000` **保留为演示配置值**，须在 SPEC 与代码 docstring 标注「生产需按保单条款配置」 | 它是配置项而非业务规则，不应伪装成 SPEC 常量；但也不能散落成魔数 | F1/F2 配置节 |
| D-08 | 2026-11-18 | 理赔轨迹**只复用既有 11 种 `record_type`**（不改 `trace.py`），理赔语义塞 `event` 且**必须加 `claims.` 前缀** | 改 `record_type` 白名单会 ValueError 并波及续保；不加前缀则两套语义在同一字段无法区分，C5 审计会失效 | F2 轨迹写入；C5 审计 |
| D-09 | 2026-11-18 | **研究证据入库策略**：`.mdx`/`.json`/`.py`/`.txt` 入库；`*.html` / `*.html.txt` **不入库**，仅以 `MANIFEST.md` 的 `sha256 + URL + 抓取时间` 作为可复现凭据 | 证据目录 8.0 MB 中 **7.1 MB 是 HTML 渲染副本**，文本源仅 2.0 MB。依据 [GitHub 大文件规则](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)（>50 MiB 告警、>100 MiB 拒收、建议仓库 <1 GB）。审计靠清单而非会腐烂的副本 | `.gitignore`；所有成员后续取证方式 |
| D-10 | 2026-11-18 | **DAG 去串行化**：F1 依赖由 `(R3, D4)` 改为 `(R3, R1)`；F3 依赖由 `(F1, D4)` 改为 `(F1, F0)` | F1 是设计文档，只需框架基线与 wiki 规范，不需 wiki 内容做完。原图让框架设计白等整条数据流水线 | 调度并行度；工期 |
| D-11 | 2026-11-18 | **Deep Agents 只做材料抽取，不做业务决策**：`MaterialsAnalysis` schema 顶层**无金额、无责任比例、无通过/拒绝建议**；金额一律服务端计算 | R3 §8 举证官方 5 条原文（workflow=predetermined 路径 vs agent=自定流程；不可逆操作只建议 checkpoint 审计 + 收紧 HITL）。与续保「保费只来自报价服务」同一条原则 | F1 schema、F3 实现；CLM 验收 |
| D-12 | 2026-11-18 | **「只抽样不拉全量」的技术路径唯一**：`HF_ENDPOINT=https://hf-mirror.com` + 头部 HTTP Range（≤3 MiB/次）+ 顺序追加 + CSV 校验 + 可续传 | R2 实测判死两条常见路线：`datasets` streaming（无 parquet/builder）、随机 byte-range 切块（单条记录内 base64 达 876 KB 无换行，6 个随机窗口 5 个取不到记录）| D1 脚本；manifest 需记实际 Range |

---

## 待决事项（Open Questions）

| ID | 问题 | 当前处置 |
|---|---|---|
| O-01 | `tenacity 9.2.1→9.1.4` 的**具体来源包**未定位（已排除 langchain / langsmith / langgraph / langgraph-prebuilt / langchain-core 1.8.0/1.8.1） | 交 F0 用 `uv pip install --dry-run -v` 记录完整求解链；不影响 D-05 结论 |
| O-02 | `multi_step_property` 的 `claim_decision` 是否可作 ground truth | 待 D1 取到 6 条实录后由 D2/D5 判定；若可用则 property 可分片报准确率，其余不能用 |
| O-03 | 数据集 `revision` 需 pin 成 commit sha（当前用 `main`） | D1 首次运行后固定，写入 manifest 与 README |

## 关联文档

- 基线：`docs/log/step-c0-baseline.md`、`docs/log/hard-rules.md`、`docs/log/step-c0-gate.md`
- 研究：`docs/research/llmwiki-spec.md`（R1）、`docs/research/ins-mmbench-access.md`（R2）、`docs/research/r3-langgraph-deepagents.md`（R3）
- 各步日志：`docs/log/step-{r1,r2,r3,c0,f1,d1,f2,f3,d2,d3,d4,d5,f4,c5}.md`

## 勘误（append-only，不改历史条目）

| 编号 | 对哪条 | 勘误内容 | 依据 |
|---|---|---|---|
| E-01 | R3 §4 | 「FilesystemBackend 不执行 shell」→ 应读作「**不向模型暴露** shell 执行能力」。F0 源码核查：`filesystem.py` 内部会以固定 argv fork 本机 `rg` 做 grep 加速（`-F` 固定字符串、pattern 前有 `--` 终止符、失败回退纯 Python），但**无 `execute` 工具、无 `shell=True`、无 `os.system`**。结论未被推翻，是文档精度问题 | `docs/research/f0-deepagents-0739-install-evidence.md`；`claims/deep_agents/probe_f0.py` |
| E-02 | D-05 | tenacity 降级的**真因**已定位：不是 langchain-core，也不是 9.2.1 被 yank，而是 `google-genai 3.4.0` 要求 `tenacity<9.2.0,>=8.2.3`。只要 `langchain-google-genai` 在依赖图里，tenacity 就回不到 9.2.1 —— 这解释了为什么「换一个 venv」是唯一安全解 | 同上 + PyPI JSON |
| E-03 | D-11 | 「schema 层无金额字段」已有**官方 API 入口**：`create_deep_agent` 与 `SubAgent` 都接受 `response_format`，可把约束下沉到 schema 而非仅提示词。F3 必须使用，不得只靠 prompt | `inspect.signature` 实读（0.7.39）|

## 新增决策（D-14 起，append-only）

| 编号 | 决策 | 依据 | 影响范围 |
|---|---|---|---|
| D-14 | 发现 liability 分片 `source_index=[0,1,3,4,6,8,10,12,16,17,19,20]`，**非严格 head-k**（跳过 9 条）；**裁决不重取**，改为修正 manifest 描述 + 量化偏差 | 事实核实（我逐条读 `records.jsonl`）：其余 4 分片 42 条严格 head-k；为一个「装饰性连续」在 30–340 KB/s 镜像上再取 30 MB 不划算。但 `strategy=head_k_complete_records` 的描述与事实不符，属「文档说谎」，必须改为 `head_window_complete_records` 并列出跳过清单 | `manifest.json` 增字段；`step-d1.md` §1.1/§2/§4；`README.md` 警示；D5 评测结论需标注样本偏差边界 |

| 编号 | 决策 | 依据 | 影响范围 |
|---|---|---|---|
| D-15 | **轨迹首行必须归属 `claim_id`**：`intake` 先算 `claim_id` 再记轨迹；`record()`/`recorder()` 支持显式 `claim_id`；`node_end` 用节点执行后的 `claim_id`；无效报案也回填 `claim_id` | X1 对账 I4-a：首行落 `unknown.jsonl` → 轨迹无法按 claim 重放（违背 CLM-20）；实测修复前 `traces-claims/` 同时出现 `<claim_id>.jsonl` 与 `unknown.jsonl` | `claims/graph.py`（intake/record/recorder/_wrap）；`claims/tests/test_f2d_degradations.py::test_i4a_*`（2 条） |
| D-16 | **降级必须可归因**：捕获异常后写 `error_type` + `error_class` + `message(≤300)` 到 `claims.llm_degraded`；用 `ContextVar` 传递，**不改** `run_analysis(docs, *, analyzer_version) -> dict` 契约签名 | X1 I4-b + SPEC §9：没有 `error_type` 的降级日志等于没有日志；契约签名是 F3/F2 的接口，不能为传原因而改 | `claims/graph.py`（`_LAST_ANALYSIS_ERROR`/`last_analysis_error`/`analyze_materials`）；SPEC §9；测试 `test_i4b_*`（2 条） |
| D-17 | **终态即终点**：`invoke()`/`resume()` 入口先查 `Status.TERMINAL`；已终态或无挂起中断 → 直接返回既有状态 + `CLAIM_STATE_INVALID`，**不调用 `graph.invoke`**（不新增 checkpoint、不再 charge、不绕过 `ALLOWED_TRANSITIONS`） | X1 I6-a/I6-b：3 次 invoke = 3 次 charge，仅靠网关按 `payment_key` 去重兜底属"网关对、流程错"；paid 后 resume 静默成功 | `claims/graph.py`（`_terminal_snapshot`/`invoke`/`resume`）；测试 `test_i6a_*`、`test_i6b_*`（3 条） |
| D-18 | **指标接线方式**：在 `ClaimGraph._wrap()` 里为每个节点补 `node_end`（带 `latency_ms`），支付网关调用前后补 `tool_call`/`tool_result`；**不在节点里手调 `metrics.observe_record`** | X1 D1 + 实测：`observe_record()` 只认 `node_end/tool_call/tool_result/llm_response/retrieval/error`，F2 早期只写 `node_start` → `metrics.render()` 只有 `# HELP/# TYPE`、**零样本**（我 F2 交付时的"已自动接入"说法不成立）。走 `TraceRecorder.record()` 保持"JSONL 与 /metrics 同源" | `claims/graph.py`；`claims/state.py::Event.PAYMENT_CHARGE`；SPEC §6.3；测试 `test_metrics_are_actually_wired` |
| D-19 | **`analysis_key` 缓存落地实现**（不降级为"v1.0.0 未实现"）：`claims/data/cache/<key>.json`，命中置 `analysis_cached=true` | 队长默认倾向；F1 已把缓存写进契约 §3.2，"契约与实现不一致比缺功能更难查"；成本约 30 行 | `claims/graph.py`（`_analysis_key`/`_load/_store`）；`claims/state.py`（`analysis_cached`/`analysis_key`）；SPEC §3.2；测试 2 条 |
| D-20 | **`anomalies` 不进 `flags`**：F3 私有码（`skipped_by_model`/`quote_not_verbatim`/`kind_mismatch`/`unknown_doc_id_dropped`）只作**分析过程信号**进轨迹；SPEC 新增 §4.6 词汇表；F2 `flags_for()` **显式剔除**这些码（不靠"没匹配到自然忽略"） | 队长裁决 2026-11-18：flags 是业务信号（影响 `route_risk`），anomalies 是技术信号；混用会让"模型跳文档"被当成"欺诈风险" | `claims/tools/logic.py`（`ANALYSIS_ANOMALY_CODES`/`_anomaly_code`/`flags_for`）；SPEC §4.6；测试 2 条 |
| D-21 | **`CLAIMS_WIKI_DIR` 登记为理赔域唯一知识目录**：理赔域一律读 claims wiki，**禁读续保 `wiki/`**（续保 `WikiSearch()` 默认读 `server.config.WIKI_DIR`，cwd 敏感）；实际接线归 D5 | X1 I3-a：变量已定义但无人消费、SPEC 未登记；`WikiSearch()` 默认路径会读到续保知识（8 条 entries） | SPEC §8.1；`claims/config.py::wiki_dir()`（实现已存在，本次仅登记）；D5 接 `WikiSearch(wiki_dir=claims.config.wiki_dir())` |
| D-22 | **运行前提**：理赔流水线（含 F3）必须用 `.venv-claims/bin/python`；`.venv` 下 F3 抛 `DeepAgentsNotInstalled` → 自动降级为规则模式，属**"假绿"风险**，不得作为 F3 验收依据 | X1 I1-a（blocker）+ 实测：`.venv` 下 `claims/deep_agents/tests` 20 failed（全 `ModuleNotFoundError: deepagents`）；`.venv-claims` 下 138 passed | SPEC §8.0；CI/验收命令必须写全解释器路径 |
| D-23 | **接受 D3b 的 log 收敛（对"只追加"的一次已声明偏离）**：误触 `build --all` 产生 33 条失效 ingest → 删生成页 → log 收敛到 36 条并要求后续不再清历史；已留下 `fix` 条目（reason/action/影响范围） | 不收敛会让 log 声称 ingests 不存在的页（比偏离更糟）；我独立校验：ingest 36 ↔ 页面 36，缺 0、幽灵 0、重复 0，`fix` 条目完整。**条件**：①保留 `fix` 条目不得删 ②此后一律只追加 ③必须把"log↔页面 1:1"加进 lint，不让下次靠人查 | `wiki/log.md`；`scripts/wiki_lint.py` 新增检查；`step-d3b.md §5` |
| D-24 | **`labels.claim` 同名不同义：不重映射，接受缓解 + 登记为限制 O-03**。agri 的 `claim`=决策枚举（No/Partial/Full Compensation），claim 分片的 `claim`=金额；已按分片分别登记并自动输出「同名不同义，不得合并统计」 | 重映射需改 `plan.md` 实体模型 → 要重生成受影响页 → 又一次并发写窗口（t20/t23 已经因并发产生过 `FAIL=108` 漂移）。且 property 的 `claim_decision` 是**不同标注来源**，合并反而会造出新的假等价。缓解已能阻止"合并分布"这个实际错误，根治的收益不抵风险 | `entities/compensation-tier`（分片分列）；`step-d4.md`；D5 评测不得跨分片合并该字段 |
| D-25 | **wiki 单写者规则**：从 t25 起，`data/llm-wiki-claims/{scripts,wiki}/**` 仅 wiki-lead 可写；其他成员一律只读。C5 必须在 t25 完成后复跑两套 lint + 引用审计（检测并发漂移） | t23 实测：17:49 `FAIL=64`、18:24 被全量刷新、18:28:00 突变 `FAIL=108`（全 L10，页面重写而 index 未同步）。两个 agent 同时 `build --all` 会让"谁改坏了"无法归因 | `t14` 增加 t25 依赖与复跑步骤；`step-d4.md §7` |
| D-26 | **index 允许 `type` 移到分组标题**（接受 t25 的格式改动），**但不接受摘要截断**——改为由页面元数据确定性生成的短标签（≤30 字、无语省略号、含区分维度）；若因此超 6144 B，则**分卷**而非继续压缩 | 截断后的摘要如「INS-MMBench 子集 agri 保险 12…」是标题同义重复，索引失去定位价值；我要求的是"短且能区分"，不是"短就好" | `index.md` 生成逻辑；`schema.md` 记录新格式；t26 |
| D-13 | **（空号补记，非新决策）** 编号 D-13 未被使用：起草时从 D-12 直接跳到 D-14（当时误将三条勘误 E-01~E-03 当作 D 系列续号）。**保留空号不补内容**，以免既有引用错位 | t24 总账核查发现编号不连续；补一行说明比重新编号安全（已有文档引用 D-14 及后续编号） | 本节；`INDEX.md §3` 决策台账索引 |
| D-27 | **lint 门禁口径**：①`docs/research/evidence/` **整目录** `extend-exclude`（不逐文件豁免、不移动探针）②门禁一律用仓库 venv 的 ruff（`requirements-dev.txt` 钉 `>=0.17,<0.18`，当前 0.17.5），不依赖全局安装 | ①该目录 sha256 登记在 MANIFEST，`--fix` 必然断证据链；"只报不改"又会让门禁长期留红→逼人绕过门禁或偷改证据（两种都比排除差）②ruff 规则集随版本扩张，"今天全仓绿"不等于半年后绿 | `pyproject.toml [tool.ruff]`；`step-f5-ruff.md`；C5 记录实际版本 |
| D-28 | **C5b 已提前并发执行，但结论仍可用**：我建 t32 时**漏写了 `dependencies`**（本意是等 t14+t31 落定），调度器因此立即派发。处置：不重跑，保留其结论，但**在交付说明里显式标注 C5b 与 C5 并发**，并以 C5b 的 P2–P5 清单作为后置修正清单 | 并发并未造成错误结论（C5b 自述快照前 15 分钟零改动、且逐项实测），但它确实可能在 t31 文档修正前完成 → 所以 P2–P5 必须后置跟修，不能当已闭环 | `step-c5-final.md`；后置修正任务 t33；交付说明 |
| D-29 | **C5 判定通过（verdict=pass）**，且两份终验（C5 自验 + C5b 独立复验）结论一致：可交付。**三条遗留主动接受，不在收尾时修**：①`.venv` 下裸 `import claims.api` 仍抛错——这是"导入即 preflight"的有意设计（防假绿）；改到 lifespan 会使 import 不再失败，属语义变更，最后一刻改风险大于收益 ②M-01（16 条决策未被编号回引）——已有 `INDEX §3.2` 产物反查作为替代证据链 ③L-01（4 个指针文件 <20 行）——已标注 | 两条判据均成立："续保基线未碰坏"+"理赔每条结论可回溯"；剩下的都是追溯性/人机工程事，不影响功能正确性；**在绿的基线上为美化而改代码是本类项目最高风险动作** | `step-c5.md`；`step-c5-final.md`；交付说明的局限清单 |
