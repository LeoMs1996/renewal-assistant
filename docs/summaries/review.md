> **轮次标注**：下文章节一～六为**第一轮评审**（2026-11-12 11:06，6 PASS / 8 FAIL）原始记录，原样保留。第二轮（修复验证，2026-11-12 13:49）结论 **13 PASS / 1 FAIL**（报告 eval/report-20261112-134930.md，唯一 FAIL = AC-05），三根因核销见 docs/summaries/repair.md；AC-05 终修见 docs/summaries/final-repair.md。三轮演进入见文末「第三轮终审」。

# 评审总结（review）— 独立验收

> 评审孙Agent · 2026-11-12 11:06 · 独立复核，未改动任何业务代码
> 方法：读 SPEC.md §7 / docs/summaries/* / eval/report.md / traces 样例 → 独立端口复跑 `scripts/e2e_smoke.sh 8564` 与 `.venv/bin/python eval/run.py --port 8565` → 对 3 条关键根因做代码/轨迹一手取证。
> 当前环境：`.env` 已配 GLM 凭证（10:22 起），服务运行于 **LLM 模式**（复核报告 report-20261112-105638 header `/health.llm_mode=llm`）。

## 一、AC-01~AC-14 逐条验收结论

依据 = 复核运行（8565 端口，20261112-105638）+ 一手证据；结论与 eval/report-20261112-104904 完全一致（6 PASS / 8 FAIL，稳定复现）。

| AC | 判定 | 证据（文件/命令/一手复核） |
|---|---|---|
| AC-01 临期提醒 | **FAIL** | 复跑 e2e_smoke 8564：节点链 `[..., quote, fallback]`，无 quote/await_confirm；轨迹 `trc-20261112103410-6c3rxv.jsonl` seq19 亲见 `INVALID_USE_NATURE「使用性质『null』不在费率表」`。expiring_soon=true 子项本身 PASS |
| AC-02 读保单+脱敏 | **PASS** | e2e_smoke A1（本次复跑）：found/policy_version=404→200 全过，owner 出参 keys 无 id_number/phone；eval PII 全链路扫描无泄漏（hard） |
| AC-03 非临期 OWN-1002 | **FAIL** 🔴 | 复跑报告 AC-03：expiring_soon=false ✅ 但无 quote 事件（同 'null' 缺陷）；修复后将暴露 BLPS 无费率 → RATE_NOT_FOUND（数据缺口） |
| AC-04 查无此人 | **PASS** | e2e_smoke A1 + 复跑：OWN-9999 → 404 found=false，query_quote 次数=0（不编造，hard） |
| AC-05 差异表 | **FAIL** 🔴 | 复跑 2/5 断言：无 quote 事件（'null' 缺陷）；规则模式另有 selection_key 归一化缺失 → 同语义询价 2 次 |
| AC-06 升保额 tiers | **FAIL** 🔴 | 复跑 0/8：无 quote 事件；规则模式第二层 = graph.py:297 保额正则取首数字（"从100万升到200万"→100万），代码亲验 |
| AC-07 YWYW 前置 | **PASS** | 复跑 4/4：corrections 含 RIDER_PREREQUISITE_MISSING、询价 0 次（hard）、引 wiki-ywyw |
| AC-08 停售险种 | **FAIL** 🔴 | 复跑 2/3：corrections=[] 无 COVERAGE_DISCONTINUED。一手取证 graph.py intake：`DISCONTINUED_KEYWORDS → intent="terms"` 走 retrieve_terms→fallback 绕过 parse_needs 纠正；wiki-csx 引用正常 |
| AC-09 删交强险 | **PASS** | 复跑 3/3：JQX_REQUIRED 纠正、询价 0 次（hard）、引 wiki-jqx |
| AC-10 网约车 1.6 系数 | **FAIL**（按 SPEC 断言） | 复跑 1/4：实现按任务书转人工不报价（询价 0 次、系数未生效），引 wiki-ride-hailing ✅。**任务书 vs SPEC §7 冲突，编排Agent已按任务书裁决**；本评审维持"按 SPEC 断言=FAIL"的如实记录，最终采信主Agent裁决（转人工+引 wiki 为准） |
| AC-11 未年检问答 | **PASS** | 复跑 4/4 + e2e_smoke A5（本次复跑）：命中 wiki-annual-inspection、citations 含 wiki_id/source/version、不进比价（询价 0 次，hard）、finish_reason=end |
| AC-12 24h 过期 | **FAIL**（过期逻辑本身 PASS） | 复跑 3/4：409 QUOTE_EXPIRED ✅、新报价 confirm 200 ✅；失败点=重报价 quote_id 撞号。一手取证 quote_server.py:343 `_QUOTE_SEQ` 进程内计数器，跨进程从 0001 重新起号 |
| AC-13 确认投保 | **FAIL** 🔴 | 复跑 4/11：SSE 无 confirmed、/confirm 422/404（t1 无报价 → 入参占位符，**连带失败**）。错误码矩阵本体在 e2e_smoke B2（历史 3 连过）验证过：OWNER_MISMATCH/VERSION_STALE/NOT_FOUND 全对；本次复跑因 LLM 模式主缺陷未到达该阶段 |
| AC-14 轨迹完整性 | **PASS** | 复跑 1/1（hard）：14 条轨迹文件存在、seq 连续、GET /trace 回放一致；e2e_smoke A6 同验 |

## 二、总判定

**❌ 未通过验收（6 PASS / 8 FAIL，其中 hard 失败 6 条）** — 前提为按 SPEC §7 原文断言且服务运行于 LLM 模式。

两点关键评审意见（超出 eval 报告的新发现）：

1. **备忘已知事实"e2e_smoke 三连跑通过"已失效**：`.env` 配入 GLM 后 smoke 亦被同一 'null' 缺陷击穿（本次复跑阶段 A 即败：节点链 `quote→fallback`，且脚本在无 quote 时 IndexError 崩溃而非优雅报错——smoke 脚本自身的健壮性小缺陷）。集成阶段的"三连过"是在规则模式取得的，模式切换后无人回归——这正是 evalAgent 指出的盲区，评审亲证属实。
2. **规则模式基线为 8/14**（report-20261112-100847），LLM 模式降至 6/14：AC-01/05/06/13 四条在规则模式可通过。缺陷是 LLM 引入后暴露的归一化缺失，不是状态机架构问题。

## 三、失败根因归类

| 类别 | 涉及 AC | 根因 |
|---|---|---|
| **未实现/代码缺陷（主）** | 01/03/05/06/13 | GLM tool-use 把 `use_nature_change` 序列化为字符串 `"null"`，llm.py/graph.py 未归一化 → INVALID_USE_NATURE → 整轮无报价（轨迹 seq19 一手取证） |
| **代码缺陷（次）** | 08 | intake 把停售关键词判为 terms 意图，绕过 parse_needs 的 COVERAGE_DISCONTINUED 纠正（graph.py intake 一手取证） |
| **代码缺陷（次）** | 06（规则模式） | 保额正则取首个数字，"从100万升到200万"解析为 100万 |
| **契约/工程缺陷** | 12 | quote_id 用进程内计数器，跨进程/重启撞号覆盖旧报价 |
| **数据缺口** | 03（第二层） | rates.json 无 BLPS 费率 → RATE_NOT_FOUND（补数据需先升 SPEC 版本） |
| **契约不一致（任务书 vs SPEC）** | 10 | SPEC §7 期望 1.6 系数入报价；任务书要求不报价转人工。实现从任务书，eval 用例从 SPEC → 结构性 FAIL，非质量缺陷 |
| **评测覆盖缺失** | —（无） | eval 用例本身覆盖良好（22 种断言、保费独立手算、PII 扫描）；唯一小缺口是 smoke 脚本无 quote 时崩溃 |

## 四、修复优先级

1. **P0（一处修复回绿 4 条）**：llm.py `chat_tool_json` 或 graph `parse_needs` 对 `'null'/'None'` 字符串归一化为 None → 重跑 `eval/run.py`，预期 AC-01/05/06/13 回绿（规则模式已证这四条链路本身可用）。
2. **P0（回归纪律）**：修复后必须以 **LLM 模式**重跑 `scripts/e2e_smoke.sh`（本次评审证实现行 smoke 在 LLM 模式失败）；建议 smoke 脚本补"无 quote 时不崩溃"的防御。
3. **P1**：AC-08 停售关键词路由改走 renewal→parse_needs（graph.py intake）。
4. **P1**：AC-12 quote_id 改为读登记簿初始化或撞号拒写。
5. **P2**：AC-06 规则模式保额正则取"最后/目标"数字；AC-05 selection_key 归一化。
6. **P2（需先升 SPEC）**：rates.json 补 BLPS 费率；AC-10 任务书/SPEC 冲突在 SPEC v1.0.1 中书面裁决（建议收录"转人工"语义，与编排实现一致）。

## 五、验证证据（本次评审命令与输出摘录）

- `./scripts/e2e_smoke.sh 8564` → 阶段 A 失败：`❌ 收到 quote 事件`、节点链 `['intake','get_policy','parse_needs','retrieve_terms','quote','fallback']`、A1（AC-01/02/04 子项）全 ✅
- `.venv/bin/python eval/run.py --port 8565` → 退出码 0，`=== 评测完成：6/14 PASS，hard 失败 8 条 ===`，报告 eval/report-20261112-105638.md 与既有 report.md 结论一致
- `grep INVALID_USE_NATURE traces/*.jsonl` → `trc-20261112103410-6c3rxv.jsonl` seq19：`error: {"code":"INVALID_USE_NATURE","message":"使用性质「null」不在费率表用途系数中"}`
- `sed -n '440,460p' server/graph.py` → intake 中 `any(kw in message for kw in DISCONTINUED_KEYWORDS) → intent="terms"`（AC-08 根因亲验）
- `grep -n _QUOTE_SEQ mcp_servers/quote_server.py` → L61/L343：进程内计数器（AC-12 根因亲验）
- `grep "'null'" server/llm.py server/graph.py` → 无归一化逻辑（AC-01 根因亲验：schema 只声明 `["string","null"]`，未处理字符串 "null"）

## 六、遗留问题与交接

- 本评审未改任何业务代码；`eval/report-20261112-105638.md` 为复核副产物（结论与 104904 一致，可作 --diff 基线）。
- 复核运行新增的 traces/ 条目与 quotes.json 评测条目已由 runner 按其快照恢复策略处理（既有条目恢复原值）。
- AC-10 的最终口径请主Agent在交付文档中统一为："任务书裁决=不报价+转人工+引 wiki-ride-hailing，SPEC §7 原文待 v1.0.1 修订"。

---

# 第三轮终审（最终验收）

> 终审孙Agent · 2026-11-12 18:27 · 独立复核，未改动任何业务代码。本章为**最终验收结论，交付以此为准**。
> 环境：`.env` 已配 GLM 凭证，服务 **LLM 模式**（复跑 header `/health.llm_mode=llm`）；契约 = SPEC.md **v1.0.2**。

## 一、AC-05 修复代码亲验（本轮唯一未过项）

- `server/graph.py:404` `_build_selection`：原保单带入 sum_insured 时跳过 JQX，与 quote_node 对照组 base_sel 口径对齐（消除同语义双键的第一层根因）；
- `server/graph.py:435-463` `_selection_key` + `_rate_default_sum`：比较键层面剔除「等于费率表默认值」的 sum_insured（JQX=200000/YWYW=50000/BLPS=5000，从 rates.json 懒加载缓存，不硬编码）；不等于默认值的 sum_insured 仍区分（保住 AC-06 升保额语义）；
- 契约先行：SPEC v1.0.2 §3 规则 7『选择键归一化』已书面登记（SPEC.md:5、:206），符合备忘 #1「改动先升 SPEC」。

结论：修复设计在比较语义层归一化、不篡改报价入参，两层防御自洽，无发现漏洞。

## 二、独立端口复跑证据（全部退出码 0）

1. **全量 eval**：`.venv/bin/python eval/run.py --port 8451`（端口亲验空闲后使用，未触碰常驻 8000）→ **14/14 PASS，hard 失败 0 条**，exit 0；报告 `eval/report-20261112-182704.md`。逐 AC 断言数：AC-01 6/6、AC-02 8/8、AC-03 4/4、AC-04 5/5、**AC-05 5/5（含询价次数=1 与 premium_manual hard 手算）**、AC-06 8/8、AC-07 4/4、AC-08 3/3、AC-09 3/3、AC-10 4/4（v1.0.1 裁决口径）、AC-11 4/4、AC-12 4/4、AC-13 11/11、AC-14 1/1。
2. **e2e_smoke**：`./scripts/e2e_smoke.sh 8452` → Phase A（AC 链路）+ Phase B（重启恢复 /confirm 错误码矩阵 OWNER_MISMATCH/QUOTE_VERSION_STALE/NOT_FOUND、订单幂等 ORD-20261112-2490、confirmed 事件）**全部通过**，exit 0 —— 第一轮发现的"LLM 模式下 smoke 阶段 A 即败"已消除。

## 三、逐 AC 最终判定（14/14）

| AC | 最终判定 | 终审证据（report-20261112-182704 + smoke 8452） |
|---|---|---|
| AC-01 临期提醒 | **PASS** | 6/6 断言，含 quote/await_confirm 事件链 |
| AC-02 读保单+脱敏 | **PASS** | 8/8，PII 全链路扫描无泄漏（hard） |
| AC-03 非临期 OWN-1002 | **PASS** | 4/4（BLPS 费率已补，原数据缺口消除） |
| AC-04 查无此人 | **PASS** | 5/5，询价 0 次不编造（hard） |
| AC-05 差异表 | **PASS** | 5/5：询价次数=1、六险种覆盖、保费手算一致（hard）——第一轮双根因（'null' + selection_key 归一化）均已修复 |
| AC-06 升保额 tiers | **PASS** | 8/8：DSX 200万档 1292.0、询价 2 次、幂等 quote_id/version 不变 |
| AC-07 YWYW 前置 | **PASS** | 4/4，询价 0 次（hard） |
| AC-08 停售险种 | **PASS** | 3/3，COVERAGE_DISCONTINUED 纠正 |
| AC-09 删交强险 | **PASS** | 3/3，JQX_REQUIRED（hard） |
| AC-10 网约车 | **PASS** | 4/4，按 SPEC v1.0.1 裁决口径（转人工+引 wiki-ride-hailing），契约冲突已书面解决 |
| AC-11 未年检问答 | **PASS** | 4/4 + smoke A5，citation 带 wiki_id/source/version（hard） |
| AC-12 24h 过期 | **PASS** | 4/4，过期 409 + 重报价无撞号（序号持久化生效） |
| AC-13 确认投保 | **PASS** | 11/11 + smoke B2/B3 错误码矩阵与订单幂等 |
| AC-14 轨迹完整性 | **PASS** | 1/1（hard）+ smoke A6/B1 跨重启回放 |

## 四、总判定与三轮演进

**✅ 通过最终验收：14/14 PASS，hard 失败 0 条**（LLM 模式，SPEC v1.0.2）。

| 轮次 | 时间 | 结论 | 报告 |
|---|---|---|---|
| 第一轮 独立评审 | 11:06 | ❌ 6/14（hard 失败 6） | report-20261112-105638 |
| 第二轮 修复验证 | 13:49 | ⚠️ 13/14（余 AC-05） | report-20261112-134930 + repair.md |
| **第三轮 终审** | 18:27 | **✅ 14/14（终值）** | **report-20261112-182704（最终交付基线）** |

演进链路：第一轮三根因（P0 'null' 归一化、P1 AC-08 路由、P1 AC-12 撞号）+ P2（BLPS 数据、AC-10 契约裁决）在第二轮全部核销；第二轮遗留的 AC-05（selection_key 归一化缺失）由 SPEC v1.0.2 终修核销，终审全量复跑确认。

## 五、遗留（不阻塞交付）

- 规则模式下 AC-06 保额正则取首数字的既有独立缺陷仍在（LLM 模式主链路不受影响，ROOT_CAUSES 已登记，见 final-repair.md）。
- 序号文件多进程并发写的窄窗口竞态（单机演示可接受）。
- 评测子进程（8451/8452）已随 runner/smoke 自管生命周期退出，常驻 8000 未触碰。
