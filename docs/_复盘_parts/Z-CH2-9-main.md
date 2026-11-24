<!-- CH2 -->
## 2. 续保主线时间线（2026-11-11 → 11-19）

> **本章证据**：`git log` 仅 2 个 commit（`40541d1` 2026-11-17 baseline 把 11-11→11-17 全部历史压成一次提交；`a81780d` 2026-11-19 理赔域），**逐日 commit 不可考**；下表日期来自 SPEC/评审/评测报告文件名与 docs/summaries，而非提交记录。

| 日期 | 里程碑 | 证据 |
|---|---|---|
| 11-11 | 脚手架 + SPEC v1.0.0；确立「字段/接口以 SPEC 为准，改动先改 SPEC 并升版」 | `docs/summaries/scaffold.md §交接`（23:51）；主文件 §0.4 |
| 11-12 | 三轮评审 6/14 → 13/14 → 14/14；修复 `llm.py` "null" 归一化、AC-08 停售路由、`quote_seq` 持久化；SPEC v1.0.1（AC-10 裁决 + BLPS 费率） | `docs/summaries/review.md` / `repair.md` / `regression-eval.md`；`eval/report-20261112-*.md` |
| 11-13 | 2026 技术基线**第一轮**分域评审（9 域）；SPEC v1.0.4 安全契约落地（鉴权 / 限流 / 安全头 / SEC-01~05）+ 官方 checkpointer | `docs/评估与优化报告-20261113.md A.3`；`reviews/*.md`；`SPEC.md:5` |
| 11-17 | **第二轮**复评审，9 域评分翻转（见 §3）；SPEC v1.0.5（LLM 降级可观测）→ **v1.0.6**（严格模式 + §4.5.1 安全增强）；续保 wiki「三层」重构；提交 `40541d1` | `reviews/INDEX.md §1.1`；`SPEC.md:5`；`git log` |
| 11-18 → 11-19 | 理赔域 + INS-MMBench 子集 LLM-Wiki（R1…C5，见 §5）；提交 `a81780d`（11-19 01:58） | `docs/log/INDEX.md §2`；`git log` |

**边界**：11-11 至 11-13 之间的逐日动作（如 t1–t16 各子任务）本章未逐条核对，只保留有文档锚点的里程碑；需要逐日细节请读 `docs/summaries/*.md`（12 份）。

<!-- CH3 -->
## 3. 2026 技术基线两轮评估（11-13 与 11-17）

> **本章证据**：`reviews/INDEX.md` 标题级信息（§1.1 评分总表、§2.1–2.9 分域摘要标题含前后分）；各域报告正文**未读取**，因此只写分数与已登记的遗留，不写"发现条数"。

**第一轮（2026-11-13）**：9 个域各一份报告（`reviews/{platform,memory,security,knowledge,mcp,api,frontend,eval,orchestration}.md`）+ 汇总 `INDEX.md`。评分（前）：平台 2.4 / 记忆 2.7 / 安全 4.5 / 知识 6.0 / MCP 7.0 / API 6.5 / 前端 7.0 / 评测 6.5 / 编排 7.0。最低两项是平台工程与记忆机制。安全域 F1–F12 全部落地（`INDEX.md:114`，报告 445 行）；跨域遗留 X-01…X-08 登记（`INDEX.md:219–226`），其中 X-01（memory.py 14 处 mypy）后由 t16 修复（`captain-verification.md:160`）。

**第二轮（2026-11-17）**：复评后评分（后）：平台 8.3 / 记忆 7.7 / 安全 7.7 / 知识 8.0 / MCP 8.5 / API 8.0 / 前端 8.0 / 评测 8.0 / 编排 8.3。落地规模与新增测试面的具体数字在 `INDEX.md §1.2 / §1.3`（第 52、71 行），**本次未读取**，不在此复述。

| 域 | 前 → 后 | 仍开放的遗留（`INDEX.md`） |
|---|---|---|
| 平台工程 | 2.4 → 8.3 | X-06 轨迹 schema 缺 model/provider |
| 记忆机制 | 2.7 → 7.7 | X-02 记忆域未登记 SPEC（`grep memory_ SPEC.md`=0）；X-03 状态双真源 |
| 安全合规 | 4.5 → 7.7 | F1–F12 全部落地；本次 SEC-01~05 复跑 5/5 PASS（§8） |
| 知识检索 | 6.0 → 8.0 | X-07 `evidence_coverage==0` 应路由 clarify；X-08 7 条 stale 条款待业务方 |
| MCP / API / 前端 / 评测 / 编排 | 6.5–7.0 → 8.0–8.5 | X-04 未采用官方 HITL；X-05 无节点级超时 |

**读法提醒**：分数是评审报告自评，不是外部基准；"翻转"反映的是修复落地，不代表 7.7–8.5 是行业可比的分数。

<!-- CH5 -->
## 5. 理赔域 + Deep Agents：从 R3 到 C5

> **本章证据**：`docs/log/INDEX.md §2 步骤索引表`（76–109 行，逐行读取）；`claims/ARCHITECTURE.md` 标题；`claims/api.py:10/86–120` grep。

| 阶段 | 内容 | 状态 | 产物 / 证据 |
|---|---|---|---|
| R3 | 框架基线：LangGraph + Deep Agents 选型研究 | ✅ | `docs/research/r3-langgraph-deepagents.md`（D-05、D-11、E-01） |
| C0 | 基线守护 / 隔离骨架：`claims/`、`data/`、`traces-claims/`、`.gitignore`、硬规则 | ✅ | `docs/log/hard-rules.md`（续保 SPEC 只读 = H4） |
| F0 | 隔离解释器 `.venv-claims/` + `deepagents 0.7.39` | ✅ | `docs/research/f0-deepagents-0739-install-evidence.md` |
| F1 | 理赔域契约与架构（`SPEC-claims.md` v1.0.x、`ARCHITECTURE.md`） | ✅ | D-07、D-08、D-11、E-03 |
| F2 / F2b / F2c / F2d | LangGraph 四段编排 + 降级用例纠偏 + `DEEPAGENTS_ENABLED` 默认值守卫 + 4 条 degradation | ✅ | `claims/graph.py`、`claims/state.py`、`claims/tools/*`、`claims/tests/*` |
| F3 / F3b | **Deep Agents 材料分析层**（`claims/deep_agents/*`）+ 工作区隔离修复 | ✅ | `step-f3-deepagents.md`；`test_workspace_isolation.py` |
| X1 | 静态接口对账（6 条契约） | ✅ | `docs/log/integration-contract.md` → 反哺 D-15…D-22 |
| D5 | 理赔检索层 + 检索评测 | ✅ | `claims/wiki_retrieve.py`、`claims/eval_retrieval.py` |
| F4 | 端到端：HTTP/SSE 七端点 + E1–E6 CLI 门禁 | ✅ PASS 8/8（连跑两次） | `claims/api.py`、`claims/demo_claim.py`、`test_f4_api.py` |
| C5 | 方案 C 终验（零回归 / 隔离性 / wiki 一致性 / 硬规则审计） | ✅ 2026-11-19 01:52 | `docs/log/step-c5.md`；遗留 M-01、L-01 |

**Deep Agents 在理赔域的位置**（`claims/ARCHITECTURE.md §5`）：它是**材料分析层的唯一调用点**，只产出结构化分析结果，**不决定赔付**——"谁能决定什么"在 §5.2 划定；`DEEPAGENTS_ENABLED=false` 时按 §5.3 降级。运行前提是硬断言（`claims/api.py:10`，D-22）：默认要求 `deepagents` 可导入，否则在严格模式下直接拒绝并提示用 `.venv-claims/bin/python` 启动（`:118–120`）。

**与续保域的关系**：两套解释器是硬约束而非习惯（`docs/log/INDEX.md §4.3`）；理赔域只读续保 SPEC，复用 `server/trace.py` 与 `server/security.py`（`ARCHITECTURE.md §8.1/8.2`）；续保用手写 StateGraph + `clarify→END` 闸门，理赔用原生 `interrupt()`（`review_gate`，§6）——同一项目里**两种 HITL 实现并存**，这是有意的隔离而非不一致，但读者要分清。

<!-- CH6 -->
## 6. 踩坑与修复总表

| # | 现象 | 根因 | 修复 / 处置 | 证据 |
|---|---|---|---|---|
| 1 | LLM 模式下 AC-05 失败：`use_nature_change="null"` 字符串直传 → `INVALID_USE_NATURE` | 工具 JSON 可空字段未归一化 | `server/llm.py` `normalize_tool_json`（哨兵集 + 递归） | `repair.md §一`；本次 AC-05 PASS（1A [06]） |
| 2 | 规则模式 AC-05 第②层：`_build_selection` 含 JQX sum_insured 致 selection_key 不等，同语义询价 2 次 | 选择键未归一化 | SPEC v1.0.2 选择键归一化（`SPEC.md:206`） | `regression-eval.md` 遗留① |
| 3 | D3b 误触 `build --all` 删了 33 条 log 记录 | 脚本默认动作过宽 | 事后从产物重建索引 | 主文件 §0.2 点名 |
| 4 | `.venv` 下 Deep Agents 测试「假绿」 | 解释器混用 | 两解释器硬约束 + `api.py` 运行前提断言 | `docs/log/INDEX.md §4.3`；D-22 |
| 5 | 评测集与 raw 同源（循环论证） | 评测数据来自被评测的语料 | **未解决**，主文件点名 | 主文件 §0.2 |
| 6 | `-q` 叠加吞掉 pytest 汇总行 | pytest 配置已含 `-q` | 本次用 `-v` 抵消取得计数（148/86） | 主文件 §8.1；本文 §8 |
| 7 | 6 个优化子 Agent 全部中断留下半成品 | 并发过高 / 上下文耗尽 | 人工核对已落盘改动 | 主文件 §0.2 |
| 8 | `memory.py` 14 处 mypy 红 CI | 类型注解缺失 | t16 修复，`Success: no issues` | `captain-verification.md:160` |
| 9 | F2c 文档把 conftest 写成 `claims/conftest.py`（不存在） | 文档路径笔误 | P2 修正为 `claims/tests/conftest.py` | `docs/log/INDEX.md §2` F2c 行 |
| 10 | 指针文件（0 字节）被当成独立步骤 | 命名重复（`step-d2.md` → `step-d2-normalize.md`） | INDEX 加说明 | `docs/log/INDEX.md:107` |
| 11 | `e2e_smoke.sh` 无 quote 时 `IndexError` | 脚本健壮性 | **未修**（非业务缺陷） | `repair.md` 遗留 |
| 12 | `quote_seq.json` 多进程并发窄窗口竞态 | 无文件锁 | 演示可接受；全局唯一需文件锁 | `repair.md` 遗留 |
| 13 | 本次验收：AC-11 回答误称用户"使用性质为网约车" | terms 路径未取 `use_nature`，检索摘览串扰 | **未修**，建议加一致性断言 | `验收验证/_batch/1B-2.md [14]` |

<!-- CH7 -->
## 7. 遗留与未验证

**跨域遗留（`reviews/INDEX.md:219–226`，均未闭环）**

| 编号 | 内容 | 为何未做 | 影响 |
|---|---|---|---|
| X-02 | 记忆域（`memory_seeded`/`memory_ctx`、`/memory`、保留期）未登记 SPEC | SPEC 升版只登记了安全与降级 | 契约与实现漂移 |
| X-03 | 状态双真源（checkpointer vs `sessions.json`）未合并 | 需架构级合并 | 只有 `memory_tool divergence` 对账 |
| X-04 | 续保域未采用官方 HITL `interrupt()`/`Command(resume)` | 需 SPEC 升版 + 前端 + eval | 与理赔域两套闸门并存 |
| X-05 | 无节点级超时（`TimeoutPolicy` 仅支持 async 节点，11 节点全 sync） | 需改节点签名 | 以工具重试 + provider 超时兜底 |
| X-06 | 轨迹 schema 缺 `model`/`provider` | 需 SPEC §5 | 历史 span 只能套导出配置 |
| X-07 | `retrieve_terms` 在 `evidence_coverage==0` 时应路由 `clarify` | 需改 20 条边快照 + eval 断言 | 低证据时仍可能生成回答 |
| X-08 | 7 条条款 `effective_date=2024-01-01` 内容复核 | **待业务方** | lint 只能报警不能判定 |

**本次复盘未验证项**（如实列出）：① 真实凭证下的长会话（>10 轮）压缩与记忆撤回；② `RENEWAL_RECURSION_LIMIT` 入口是否生效（`app.py:223` 硬编码 40）；③ 6 个 `route_after_*` 函数体；④ `skills/renew_compare.md` 的加载方式；⑤ `trace_owner_allowed`（`middleware.py:395`）函数体；⑥ SPEC §4.5.1 安全增强内容；⑦ MCP 自测（历史 54 项）入口与复跑；⑧ `reviews/INDEX.md §1.2/§1.3` 的落地规模数字。

<!-- CH8 -->
## 8. 复跑命令（本次实跑，带时间戳）

| 命令 | 时间（+0800） | 结果（尾部原样） |
|---|---|---|
| `.venv/bin/python -m pytest tests/ -v` | 2026-11-24 18:08 | `148 passed, 2 skipped in 1.44s` |
| `.venv/bin/python -m pytest claims/tests/ -v` | 2026-11-24 18:08 | `86 passed in 0.97s` |
| `.venv/bin/python -m pytest tests/ -q` | 2026-11-24 18:07 | 仅点阵、无汇总行（`-q` 叠加，见 §6 #6） |
| `.venv/bin/python -m eval.run --results /tmp/eval-results-final.json` | 2026-11-24 18:07 | `评测完成：19/19 PASS，hard 失败 0 条，总耗时 35.4s`；报告 `eval/report-20261124-180712.md` |
| 同上 · 回归基线对比 | — | `退化翻转 b=0 / 修复翻转 c=0 … 判定：❌ 阻断 — 基线模式=rule vs 本次=llm：不可比` |
| `.venv/bin/python data/llm-wiki-claims/scripts/wiki_lint.py` | 2026-11-24 18:07 | `pages=36 index_rows=36 FAIL=0 WARN=0` |
| `.venv/bin/python data/llm-wiki-claims/scripts/wiki_claims_lint.py` | 2026-11-24 18:07 | `pages=36 index_rows=36 ERROR=0 WARN=0` |
| MCP 报价服务自测 | — | **未复跑**：`scripts/` 下无自测脚本（仅 `demo_chat.py`、`e2e_smoke.sh`），`quote_server.py --selftest` 无输出 |
| `scripts/e2e_smoke.sh` | — | **未跑**：含重启步骤，本次服务为常驻进程（归验收批次 1C） |

**说明**：eval 以常驻 8000（`llm_mode=llm`）为目标；回归对比因基线为 rule 模式而被工具判"不可比"，这不代表退化（b=c=0），但也**不能宣称"相对基线无退化"**——需在 llm 模式下重建基线（`--save-baseline`）后再比。

<!-- CH9 -->
## 9. 决策索引（在哪能查到每条决策）

| 决策 | 落点 | 证据 / 本次核验 |
|---|---|---|
| 保费只能来自报价服务，模型不得生成 | SPEC 硬规矩 | 1A [07] `premium_manual` hard；1B-1 [10] DSX 1292.0 来自 `tool_result` |
| 越权 / 编造 = 硬失败 | SPEC §4.5（v1.0.4） | 1A [08] a4 → 422 `OWNER_MISMATCH`；SEC-02/04 PASS |
| 续保闸门用 `clarify→END` + 会话续接而非 `interrupt()` | `server/graph.py:1391` | X-04 登记为未闭环（`reviews/INDEX.md:222`） |
| 理赔闸门用原生 `interrupt()` / `Command(resume)` | `claims/graph.py:381/637`；`ARCHITECTURE.md §6` | F4 PASS 8/8 |
| LLM-Wiki 不接稠密向量通道 | `reviews/knowledge.md:219/222` | 语料小、二元组零依赖、四次替代实验无增益（无 SPEC 显式否决句，§4.1 已注） |
| 网约车一律转人工 + 引 `wiki-ride-hailing` | SPEC v1.0.1（`repair.md §一-4`） | 1B-2 [13] `out_of_scope="ride_hailing"` |
| 选择键归一化（默认保额视为相同需求） | `SPEC.md:206`（v1.0.2） | 1B-1 [10] t2 复用 0 次询价 |
| SPEC 先行：改动先改 SPEC 并升版 | `scaffold.md §交接` | 版本线 v1.0.0→v1.0.6（`SPEC.md:5`） |
| 两套解释器（`.venv` / `.venv-claims`）是硬约束 | `docs/log/INDEX.md §4.3`；D-22 | `claims/api.py:118–120` 严格模式拒绝 |
| 评测集与 raw 同源 | 主文件 §0.2 | **未解决**，点名保留 |
