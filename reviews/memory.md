# 记忆机制域评审 + 落地优化报告（对话记忆 / 长期记忆 / 跨会话记忆）

- 项目：`renewal-assistant`（车险续保助手，SPEC v1.0.5）
- 域：记忆机制（对话记忆 / 长期记忆 / 跨会话记忆）— 团队任务 `t4`
- 基线日：**2026-11-13**；本次检索时间：**2026-11-17**（全部来源见 §8，逐条带 URL 与检索时间戳）
- 方法：先联网检索 2026 最新记忆基线 → 实读项目记忆相关源码 → 逐项对比 → **直接落地改造**（非仅建议）→ 用 A/B 评测 + 单测 + 报价中性哨兵验证
- 约束遵守：所有技术结论均来自本次检索（§3 逐条标注来源）；训练记忆不作为依据；无法检索证实的标注「待验证」

---

## 1. 结论摘要

### 1.1 评分（域内维度，改造前 → 改造后）

| 维度 | 权重 | 改造前 | 改造后 | 判据 |
|---|---|---|---|---|
| 对话记忆（短期上下文管理） | 25% | **5.0** | **8.0** | 旧：固定条数截断 20/8/6，无 token 预算、无压缩；新：token 预算 + 确定性滚动摘要 + 可回滚开关 |
| 长期记忆（跨会话） | 25% | **1.0** | **7.5** | 旧：**完全没有**（换 session 即失忆）；新：按 owner 命名空间的结构化记忆 store |
| 记忆策略（重要性/合并/衰减/逐出） | 20% | **2.0** | **7.5** | 旧：只有会话内 `invalidated` 追加，不读、不裁剪；新：写时白名单 + recency-wins 显式失效 + 衰减排序 + TTL + evict-last |
| 用户控制与合规（遗忘/可携/最小化） | 15% | **2.0** | **7.5** | 旧：无查看/删除/导出；新：`memory_tool` 的 list/show/audit/export/forget + PII 脱敏 + 泄漏扫描 |
| 可观测性与评测 | 15% | **3.0** | **8.0** | 旧：轨迹里看不到记忆贡献；无记忆用例；新：`node_end.output.memory`（不新增 record_type）+ 5 场景 A/B eval + 16 条回归 |
| **域总分** | 100% | **2.7 / 10** | **7.7 / 10** | 加权 |

> 改造前分数低不是「质量不足」而是「能力缺失」：长期记忆 = 0、用户控制 = 0。这也解释了为什么此前全维度评估（`docs/评估与优化报告-20261113.md`）没有单列记忆维度——它当时几乎不存在。

### 1.2 三个最高价值发现（全部已修复，含证据）

**F1（high，已修复）跨会话记忆为 0：车主换个会话就要重讲一遍需求。**
`server/sessions.py` 的 `load/save` 以 **session_id** 为键（`traces/sessions/{session_id}.json`），`server/graph.py` 只从 `state["needs"]`（本会话运行态）取上下文。同一 `owner_id` 开新会话 → 预算/保额/用途全部丢失。续保是典型**低频、多会话**业务（先问条款、隔天问价、再隔周确认），这个缺口直接换算成重复提问与流失。基线（LangGraph Stores / LangChain Memory overview）明确要求长期记忆按 `user_id` 命名空间跨 thread 共享。

**F2（high，已修复）三处固定条数截断，无 token 预算、无任何压缩。**
改造前 `graph.py` 有三处各自为政的切片：`parse_needs` 用 `history[-8:]`、`compare` 与 `fallback(terms)` 各用 `history[-6:]`，`sessions.py` 落盘再砍到 `[-20:]`。三个数字互不一致、不按 token 计量、被裁掉的内容**永久消失**。LangChain 短期记忆文档把 trim / delete / summarize 并列为三种手段，只做 trim 必然丢信息。实测（§6.2 S4）：30 轮长会话下旧策略上下文 **1640 tokens 且无上界**，早期「预算 5000」这类关键约束被裁掉；新策略 **975 tokens 有界**且约束经摘要保留。

**F3（high，已修复）没有记忆策略层：写什么、合并、衰减、逐出全都没有。**
改造前唯一的「记忆语义」是 `parse_needs` 里的 `invalidated` 追加（改口留痕）——但它**只写不读**（后续没有任何代码消费），且**永不裁剪**（每改口一次 append 一条，随会话快照无限增长）。基线（Hindsight 四杠杆、Oracle 冲突规则）要求的 importance / merge / decay / eviction 一个都没有。改造后：写时白名单（只落原子事实，不落对话原文）、recency-wins 显式失效（旧值标 `superseded` 而非删除）、读取时衰减排序（不改写存储值）、TTL 逐出（报价事实 24h）、`evict last`（active 永不因容量被删）。

### 1.3 结构化发现（供集成/安全/评测域采纳）

| ID | 严重度 | 问题 | 状态 |
|---|---|---|---|
| F1 | high | 无跨会话长期记忆（换 session 即失忆） | ✅ 已修复（`server/memory.py` + `sessions.save` 写入点） |
| F2 | high | 固定条数截断、无 token 预算、无压缩 | ✅ 已修复（`trim_turns` + `summarize_turns`） |
| F3 | high | 无记忆策略层（重要性/合并/衰减/逐出） | ✅ 已修复（白名单 + supersede + decay + TTL + evict-last） |
| F4 | high | 无用户控制（不可查看/删除/导出），自由文本可能带 PII | ✅ 已修复（`memory_tool` + `mask_pii` + `doctor` 泄漏扫描） |
| F5 | medium | 记忆贡献在轨迹里不可见，评测无用例 | ✅ 已修复（`node_end.output.memory` + `eval/memory_eval.py`） |
| F6 | medium | 双真源：checkpointer 与 `sessions.json` 各自持久化 | ⚠️ 已给对账工具（`memory_tool divergence`），**未合并**（属编排域决策） |
| F7 | low | `invalidated` 无上限增长 | ✅ 已修复（跨会话侧走 supersede+prune；会话内数组仍由编排域决定，见 §7） |
| F8 | medium | SPEC 未登记记忆域（§6.2 状态字段无 memory_*） | ⚠️ 已在报告登记为提案（SPEC v1.0.6 建议），未改 SPEC |

---

## 2. 现状实读（改造前，逐处引用）

### 2.1 `server/sessions.py`（105 行）——会话快照，不是记忆

- 键：`_safe(session_id)` → `traces/sessions/{session_id}.json`；**没有 owner 维度**。
- `save()`：剔除 `_EPHEMERAL_KEYS` 后整份落盘，`history` 裁到 `_HISTORY_TAIL = 20`。
- `append_history()`：每轮追加 user/assistant 两条，同样裁 20。
- 模块 docstring 自称「降为兼容层」，实际仍是 `/chat` 的**唯一恢复来源**（`app.py:128` 每轮 `sessions.load()` 组装 initial State）。

### 2.2 `server/graph.py`（1449 行）——三处截断 + 一处只写不读的「记忆撤回」

| 位置 | 改造前 | 问题 |
|---|---|---|
| `parse_needs` | `history[-8:]` + 本轮 message | 条数固定；长回复挤爆上下文；无摘要 |
| `compare` | `history[-6:]` | 与上面数字不一致，无理由 |
| `fallback(terms)` | `history[-6:]` | 同上 |
| `parse_needs` 记忆撤回 | `invalidated.append({field, old, new, needs_version, reason})` | **只写不读**、无上限、无跨会话 |

另注：安全域已在这些调用点用 `_untrusted_history()` 包裹历史（OWASP LLM01 缓解），本次改造**保留**该包裹。

### 2.3 持久化真源

`graph.py#_make_checkpointer` 用 `SqliteSaver`（`traces/checkpoints.sqlite`，thread_id = session）保存**整个 State**；`sessions.json` 又保存一份。两者口径独立、无对账 → F6。

### 2.4 依赖与可运行性

- `rank_bm25`（检索域已用）；**本域未引入任何新第三方依赖**（长期记忆用手写 JSON store，理由见 §5.1）。
- `.venv/bin/python -m pytest`：本 attempt 开工前实测 **83 passed / 2 skipped**；改造后 **140 passed / 2 skipped**
  （增量含其他域并行新增用例；本域新增 16 条）。

---

## 3. 2026 基线（本次检索，逐条标注来源与时间戳）

> 检索时间：**2026-11-17**（本轮会话实际执行）；基线日：**2026-11-13**。以下每条都是本次抓取的原文要点，非训练记忆。

**B1. LangChain《Memory overview》**（https://docs.langchain.com/oss/python/concepts/memory ，检索 2026-11-17）
- 短期记忆 = thread 作用域，由 checkpointer 持久化 state；长期记忆 = 跨 thread，按**自定义 namespace** 存 JSON 文档。
- 语义记忆两形态：**profile**（单文档持续更新，「每次都要把旧 profile 传进去让模型生成新 profile 或 JSON patch」）与 **collection**（多文档持续追加，召回率更高但更新/去重更难）。
- 写入两时机：**hot path**（运行时写，立即可用、可对用户透明，但增加延迟与复杂度）与 **background**（后台写，无延迟但时机难定）。

**B2. LangGraph《Stores》**（https://docs.langchain.com/oss/python/langgraph/stores ，检索 2026-11-17）
- `store.put(namespace, key, value)` / `store.search(namespace, query=, filter=, limit=)`；`Item` 含 `key / value / namespace / created_at / updated_at`；`delete` 用于遗忘。
- namespace 是**元组**（如 `(user_id, "memories")`），支持前缀匹配；`limit` 超限**静默截断**（无溢出信号）；默认排序随后端而异，**不能依赖顺序**。
- 语义检索需 `index={"embed":..., "dims":...}`；不接 embedding 时 `query` 会 `NotImplementedError`。

**B3. LangChain《Short-term memory》**（https://docs.langchain.com/oss/python/langchain/short-term-memory ，检索 2026-11-17）
- 长会话三种处理：**Trim messages**（按 token 裁，`trim_messages`）、**Delete messages**、**Summarize messages**（`SummarizationMiddleware(trigger=("tokens",4000), keep=("messages",20))`）。
- 原文明确：trim/delete 的问题是「你可能会丢信息」（"you may lose information from culling of the message queue"），因此推荐摘要升级路径。

**B4. Oracle《Which Agent Memory Approach Is Best for Long Conversations?》**（https://blogs.oracle.com/developers/which-agent-memory-approach-is-best-for-long-conversations ，2026-06-05，检索 2026-11-17）
- 生产可用形态是**分层混合记忆**：最近轮次 / 滚动摘要 / 向量召回 / 结构化记忆 / 情节记忆 + 一个 **memory manager** 决定「这一轮放什么进 prompt」。
- **冲突与新鲜度规则**：结构化决策优先于摘要；同权威取新；范围窄者优先；旧/被取代条目降权；每条记忆必须带 `source / timestamp / scope / type`；**用 active/superseded/rejected/archived 标记代替早删**。
- 推荐优先级顺序：当前消息 > 最近轮次 > active 结构化决策 > 相关情节 > 滚动摘要 > 向量召回 > 归档（仅在解释需要时）。
- context package 要**可调试**（答错时能看出是摘要过期、召回没命中、还是结构化决策缺失）。

**B5. Hindsight《Agent Memory Consolidation: Keep, Merge, Decay, Evict》**（https://raw.githubusercontent.com/vectorize-io/hindsight/e5e558bd041d452e23c1679ba6bc9c0553f20954/hindsight-docs/blog/2026-05-20-agent-memory-consolidation.md ，2026-05-20，检索 2026-11-17）
- 四杠杆：**importance**（什么才成为记忆）、**merge**（同一实体/事实合并，写入时做实体解析与去重）、**decay**（旧事实置信度衰减；指数衰减是合理默认；Zep 用 `valid_at/expired_at/invalid_at`）、**eviction**（硬删仅用于 GDPR/用户请求/安全事件；**evict last**，因为其它杠杆可逆而硬删不可逆）。
- 「**recency-wins + 显式失效** 是最可辩护的默认」：写新事实、把旧的标 invalid 而不是删掉（可审计、可回溯）。
- 评测三信号：多会话推理准确率（LongMemEval）、**矛盾检测**（注入状态变更后一周再问当前值）、**每轮 token 成本是否随会话数线性上涨**。生产要记录：每轮召回数、token 用量、实体合并率、**事实失效事件**、检索命中率。

**B6. MediaNama《AI Memory Raises New Privacy and Data Portability Questions》**（https://www.medianama.com/2026/08/223-ai-memory-privacy-data-portability/ ，2026-08-28，检索 2026-11-17）
- 长期记忆撞上**目的限制**与**数据最小化**；「**删除 ≠ 遗忘**」：删了数据库里的一条，不等于它不在记忆、检索层、向量、日志或派生物里。
- 用户需要的是 **exit / portability / control**：能带走、能删干净、能控制谁能用。

**B7. OpenAI《Memory and new controls for ChatGPT》**（https://openai.com/index/memory-and-new-controls-for-chatgpt/ ，首发 2024-02-13，2025-04-10/2025-06-03 更新，检索 2026-11-17）
- 产品级用户控制基线：可**查看**（Manage memories）、可**单条删除/全清**、可**整体关闭**（关闭后既不创建也不使用）、**临时对话**不读写记忆、记忆被更新时**告知用户**。
- 「**Deleting a chat doesn't erase its memories**」——会话删除与记忆删除是两件事，必须分别提供。
- 明确**不主动记忆敏感信息**（如健康），除用户明确要求。

**B8. LoCoMo-Plus（ACL 2026）**（https://aclanthology.org/2026.acl-long.1150/ ，2026-07，检索 2026-11-17）
- 摘要原文：现有 benchmark 与评测协议「primarily focus on surface-level factual recall」，而真实交互依赖**隐式约束**（用户状态/目标/价值）在后续并不被显式问及。
- 结论：**字符串匹配指标与记忆能力错配**，应改用「constraint consistency」评测框架。

**B9（旁证，非结论依据）** LongMemEval 榜单分数（Hindsight 94.6% / SuperMemory 81.6% / Zep 71.2% / Mem0 67.6%）来自 B5 转述，本次未直接核验原始榜单 → 标注「**待验证**」，仅用于说明「无合并/无衰减的系统会明显掉分」的趋势，不用于评分。

---

## 4. 差距分析（基线 → 现状 → 处置）

| # | 基线要求（来源） | 改造前现状 | 差距 | 处置 |
|---|---|---|---|---|
| G1 | 长期记忆跨 thread、按 user namespace（B1/B2） | 只有 session_id 快照 | **能力缺失** | 新增 `server/memory.py`：`("owner", <owner>, <kind>)` 命名空间，每车主一 JSON |
| G2 | 记忆按 profile/collection 组织，不存整轮原文（B1） | 无长期记忆；会话快照存原文 | 无写入策略 | 写时白名单：预算/保额档/加减险种/用途/保单到期日/最近报价/用户口述偏好 |
| G3 | 上下文按 token 预算，trim 之外要有 summarize（B3） | 20/8/6 三处固定条数，无摘要 | 无预算、丢信息 | `estimate_tokens` + `trim_turns` + `summarize_turns`（确定性，可离线复现） |
| G4 | 冲突处理：recency-wins + 显式失效，标记而非删除（B4/B5） | `invalidated` 只写不读、无上限 | 无合并/无失效语义 | `_upsert`：值变→旧条目标 `superseded`+`superseded_by`+`reason`；`invalidated` 镜像落库 |
| G5 | 衰减只用于排序，不改事实；evict last（B5） | 无 | 无 | `_score`（kind 半衰期）+ `_expire`（TTL）+ `_prune`（只裁非 active） |
| G6 | 每条记忆带 source/timestamp/scope/type（B4） | 无 | 无 | Item 带 `id/namespace/kind/status/source{owner,session,trace}/created_at/updated_at/expires_at` |
| G7 | 用户可查看/删除/导出/关闭（B6/B7） | 无任何入口 | 无 | `scripts/memory_tool.py`（list/show/audit/export/forget/doctor/divergence）+ `RENEWAL_MEMORY=off` |
| G8 | 删除要覆盖派生物（B6） | 无 | 无 | `forget()` 同时清 items + audit，只留 `erased_at` 墓碑；`doctor()` 全库 PII 扫描 |
| G9 | 评测看约束一致性而非字符串匹配（B8）；看矛盾检测与 token 成本（B5） | 无记忆用例 | 无 | `eval/memory_eval.py` 5 场景 A/B（含约束一致性、矛盾检测、token 有界） |
| G10 | context package 可调试（B4） | 无 | 无 | `build_context_package()` 返回 recent/summary/long_term/brief/tokens；`node_end.output.memory` 落轨迹 |

---

## 5. 落地改造（已实现，含前/后对照）

### 5.1 新增 `server/memory.py`（798 行，43 个函数；零新依赖）

为什么手写 store 而不用 `langgraph.store`：项目运行在**离线/无凭证**也能跑的模式（`RENEWAL_FORCE_RULE_MODE`），且已有 SQLite checkpoint；`InMemoryStore` 重启即失、`PostgresStore` 需外部依赖。故实现与 `BaseStore` **同形契约**（`put/get/search/delete` + namespace 元组 + Item 元数据），后续接 `PostgresStore` 只需替换 `_read/_write`。

存储层：
```python
_root()      -> config.TRACE_DIR / "memory"        # 跟随 TRACE_DIR：测试/多实例天然隔离
_path(owner) -> memory/<safe(owner)>.json          # 每车主一文件
_write()     -> tmp 文件 + os.replace()            # 原子替换，崩溃不留半截记忆
```
Item 形态（对齐 B2/B4）：
```json
{"id":"constraint:sum_insured:DSX:20261117160949564316",
 "namespace":["owner","OWN-1001","constraint"],
 "field":"sum_insured:DSX","value":2000000,"kind":"constraint","status":"active",
 "confidence":1.0,"created_at":"…","updated_at":"…",
 "source":{"owner_id":"OWN-1001","session_id":"ac06","trace_id":"trc-…"},
 "expires_at":null,"superseded_at":null,"superseded_by":null,"observed_count":1}
```
策略层（四杠杆逐条落地）：

| 杠杆 | 实现 | 依据 |
|---|---|---|
| importance | `facts_from_state()` 白名单：`budget_yuan / sum_insured:<code> / add_coverages / remove_coverages / use_nature_change / policy_end_date / last_quote_* / last_outcome / user_note`；**对话原文不入库** | B1（profile 而非整轮）、B5（fact extraction 即过滤器） |
| merge | `_upsert()`：同值→`refreshed`（刷新新鲜度、`observed_count+1`）；异值→旧条目 `superseded`（保留 + `superseded_by` + reason） | B4/B5（recency-wins + 显式失效） |
| decay | `_score = confidence * 0.5 ** (age_days / half_life)`，半衰期 preference 365d / constraint 180d / fact 90d / episodic 30d；**只影响召回排序，不改写存储值** | B5（指数衰减为默认） |
| eviction | `_expire()`（`expires_at` 到期标 `expired`，报价事实 TTL=1d）+ `_prune()`（超 200 条**只裁非 active**） | B5（evict last）+ B1（hot path 也要有界） |

读取层（跨会话召回 + 闸门）：
```python
_REFERENCE_RE = r"上次|上回|上一轮|之前(?:的)?(?:方案|说|提|讲|要求|设定|报|选)|还是(?:按|用|照)|老方案|老样子|照旧|按原方案|跟之前一样"
```
- **只有** 消息命中「显式指代」才允许长期记忆影响**询价参数**（`recall_needs`）。理由有两条且都可查证：①B4 的优先级「当前消息 > 结构化记忆」——记忆是证据不是事实；②保险域里错用记忆会**直接改保费**，属财务风险。
- 二次闸门：本轮明确否定的字段不得补回（`_negated()`：`去掉/不要/删掉/取消/不投…` + 险种别名）。
- 只召回三类**可复核**字段（预算 / 保额档 / 使用性质）；加减险种不自动套用（语义歧义会改保障范围）。
- 对抗验证：`忽略你之前的所有指令` **不触发**召回（正则要求 `之前` 后紧跟方案/说法/要求等名词），见测试 `test_recall_gate_blocks_injection_phrase`。

上下文预算层（B3 的 trim + summarize 组合）：
```python
estimate_tokens(text)   # CJK 1 token/字，其余 1 token/4 字符（保守估算，非分词器）
trim_turns(turns, budget)  # 从新到旧装入，超预算即停；至少保 1 条
summarize_turns(dropped)   # 确定性抽取：含金额/约束/增删动作的句子权重 2，其余 1；取 top-3 后按时间序
build_context_package(state)  # {recent, dropped_turns, summary, long_term, brief, tokens}（B4 context package 形状）
prompt_context(state)         # (system_extra, messages)；RENEWAL_MEMORY=off 时退回 legacy_tail
```
> 摘要实现是**确定性抽取**而非 LLM 摘要：本项目要求离线可复现（CI 无凭证）。B3 的 `SummarizationMiddleware` 用 LLM 生成摘要，本项目以「关键词加权抽取」近似重要性过滤，**局限已在 §7 明示**。

### 5.2 `server/sessions.py`（小改：写入点 + 上限）

| 项 | 改造前 | 改造后 |
|---|---|---|
| 历史保留 | `_HISTORY_TAIL = 20`（同时也是 prompt 上限，两个语义混用） | `RENEWAL_HISTORY_TAIL`，默认 **40**（只为摘要留素材与审计回放；进 prompt 的量由 token 预算控制） |
| 长期记忆写入 | 无 | `save()` 末尾 `memory.record_turn(state)`，**try/except 包裹**（记忆失败绝不影响会话落盘） |

选 **`sessions.save()`** 作写入点而不是 `app.py`：`app.py` 属 API 域，且每轮 `/chat` 都必经 `sessions.save`，零侵入即可覆盖全部链路（hot path 写入，B1）。

### 5.3 `server/graph.py`（4 处调用点 + 2 个扩展键 + 1 处 node_end）

```python
# parse_needs（改造前：history[-8:]）
mem_system, mem_history = memory.prompt_context(state, budget_tokens=config.memory_prompt_budget())
msgs = _untrusted_history(mem_history) + [{"role": "user", "content": security.wrap_untrusted(message)}]
client.chat_tool_json(system=security.guard_system_prompt(NEEDS_SYSTEM + mem_system), messages=msgs, ...)

# 跨会话召回：优先级 本轮解析 > 会话内累积 > 长期记忆
memory_delta, memory_seeded = memory.recall_needs(state)
if intent == "confirm" and (prev_needs or memory_seeded): needs = dict(prev_needs or memory_delta)
elif prev_needs and memory_seeded: needs = _accumulate_needs(_accumulate_needs(prev_needs, memory_delta), needs)
elif prev_needs:                   needs = _accumulate_needs(prev_needs, needs)
elif memory_seeded:                needs = _accumulate_needs(memory_delta, needs)

# compare / fallback(terms)（改造前：history[-6:]）
mem_system, mem_history = memory.prompt_context(state, budget_tokens=config.memory_chat_budget(), legacy_tail=6)
```
- 新增 State 扩展键：`memory_seeded: list[str]`、`memory_ctx: dict`（与既有「编排扩展键」并列，**不动 SPEC §6.2 既有字段**）。
- 可观测性：`parse_needs` 的 `node_end.output` 增加
  `"memory": {"recent_turns":…, "dropped_turns":…, "tokens":{…}, "long_term_fields":[…], "seeded":[…]}`。
  **关键取舍**：`trace.py` 的 `RECORD_TYPES` 是 SPEC §5 封闭枚举，新增 `memory` 事件类型会破坏契约，故走既有 `node_end.output`（测试 `test_node_end_carries_memory_contract` 断言 `record_type ⊆ RECORD_TYPES`）。

### 5.4 `server/config.py`（新增 2 个预算旋钮）

```python
memory_prompt_budget()  # RENEWAL_MEMORY_PROMPT_BUDGET，默认 1000（需求解析类）
memory_chat_budget()    # RENEWAL_MEMORY_CHAT_BUDGET，默认 600（顾问/条款类：正文已占位）
```

### 5.5 新增 `scripts/memory_tool.py`（147 行，用户控制/合规入口）

| 子命令 | 能力 | 基线 |
|---|---|---|
| `list <owner>` | active 记忆（= 召回会看到的内容） | B7 查看 |
| `show <owner>` | 全量含 superseded/expired + 被谁取代、TTL | B4 可调试 |
| `audit <owner>` | 变更账本（created/superseded/expired/pruned + 理由） | B5 事实失效事件 |
| `export <owner>` | JSON 导出（含历史） | B6 可携权 |
| `forget <owner> [--field]` | 硬删（items + audit 一起清，留 `erased_at` 墓碑） | B6 删除≠遗忘 |
| `doctor` | 全库体检：过期/被取代/无来源/PII 泄漏 | B6 数据最小化 |
| `divergence` | 会话快照 vs 长期记忆 双口径对账（F6 诊断，不自动修复） | B4 冲突可见 |

### 5.6 新增 `tests/test_memory.py`（16 条）+ `eval/memory_eval.py`（5 场景 A/B）

见 §6。

---

## 6. 验证证据（本次实测）

### 6.1 全量回归

```
$ .venv/bin/python -m pytest
140 passed, 2 skipped in 1.46s        # 开工前 83 passed / 2 skipped；增量含其它域并行用例，本域 0 回归

$ .venv/bin/python -m pytest tests/test_memory.py
16 passed                              # 新增记忆域用例

$ .venv/bin/python -m ruff check server/memory.py server/sessions.py server/config.py \
      server/graph.py tests/test_memory.py eval/memory_eval.py scripts/memory_tool.py
All checks passed!
```

### 6.2 A/B 评测（`eval/memory_eval.py`，2026-11-17T16:10:03+08:00）

A/B 方式：只切 `RENEWAL_MEMORY` 开关，同一批脚本跑两遍；每轮真实经过 `sessions.load → graph.invoke → sessions.save/append_history`（= app.py 链路）。

| 场景 | before | after | after 关键指标 |
|---|---|---|---|
| S1 跨会话偏好延续 | **FAIL**（budget=null, DSX={}, seeded=[]） | **PASS** | budget=6000、DSX=200万、seeded=[budget_yuan, sum_insured:DSX] |
| S2 矛盾处理（200万→100万→「按上次」） | **FAIL**（无记忆可查） | **PASS** | 召回=100万；旧的 200万 标 superseded；记忆中带「已失效」标记 |
| S3 约束一致性（预算 6000 是否进入后续上下文） | **FAIL**（context_tokens=0） | **PASS** | 约束进入 system 附加段（47 tokens） |
| S4 上下文预算与信息保留 | **FAIL**（1640 tokens，**无上界**，早期「预算 5000」被裁掉） | **PASS** | **975 tokens 有界**，摘要保留「预算 5000」，27 轮被压缩 |
| S5 遗忘/可携 | **FAIL**（旧实现无此能力） | **PASS** | 导出 1 条→遗忘 1 条→全库残留 "6000" 计数 **0** |
| **合计** | **0 / 5** | **5 / 5** | 明细：`eval/memory-eval-20261117-161003.json` |

### 6.3 报价中性哨兵（最重要的一条安全证据）

记忆绝不能改变保费。脚本：`eval/memory_quote_neutrality.py`。用真实合成车主 `OWN-1001`，把 AC-01/05/06×2/07/09/10 的 7 轮消息在「记忆开」与「记忆关」两种模式下各跑一遍（每轮独立 session、同一 owner，等同于评测用例的串行形态）：

```
turns: 7
premium mismatch: {}
on seeded: {}
VERDICT: PASS
```
→ 7 轮 `latest_quote.total_premium` **逐轮完全相同**，且无任何一轮被记忆补字段（消息里没有「上次/还是按…」指代）。这直接回答了「新能力会不会把 AC 手算保费打翻」的风险。

### 6.4 CLI 实跑（`scripts/memory_tool.py`）

```
$ TRACE_DIR=$(mktemp -d) … # 写入 2 轮：预算6000+三者200万 → 预算改 5000
$ memory_tool.py list OWN-CLI
OWN-CLI: 2 条 active 记忆
  budget_yuan      5000       preference 2026-11-17T16:09:49+08:00  ← cli-2
  sum_insured:DSX  2000000    constraint 2026-11-17T16:09:49+08:00  ← cli-1
$ memory_tool.py show OWN-CLI
  [superseded] budget_yuan     6000  → 被 … 取代（改口（recency-wins + 显式失效））
  [active    ] sum_insured:DSX 2000000
  [active    ] budget_yuan     5000
$ memory_tool.py forget OWN-CLI --field budget_yuan   → {"removed": 2}
$ memory_tool.py list OWN-CLI                          → 1 条 active（三者 200 万）
$ memory_tool.py doctor → {"owners":1,"items":4,"expired":0,"superseded":1,
                           "no_source":0,"pii_leaks":[]} ✓ 体检通过
```

### 6.5 PII 与非契约污染

- `test_pii_never_persisted`：把手机号/身份证/车牌/VIN 塞进 message 与 policy → 记忆文件里 **一个都不出现**（自由文本落盘前 `mask_pii`，其余字段根本不采）。
- `test_node_end_carries_memory_contract`：真实 `/chat` 跑一轮后，轨迹 `record_type ⊆ trace.RECORD_TYPES`，且 `node_end(parse_needs).output.memory` 存在 → 可观测性落地但**未越出 SPEC §5**。
- `test_whitelist_facts_only`：`corrections`（纠正码）、`out_of_scope`、对话原文等非白名单内容**不进**记忆。

---

## 7. 未采纳 / 遗留 / 后续建议（诚实清单）

| # | 项 | 为什么没做 | 建议 |
|---|---|---|---|
| 1 | 稠密/语义召回（embedding） | B2 的语义检索需 embedding provider；本项目须离线可跑，且无凭证 | `search(query=…)` 参数位已留；接上 embedding 后替换实现即可（同 schema） |
| 2 | LLM 摘要（对齐 B3 的 `SummarizationMiddleware`） | 需凭证 + 破坏 CI 可复现性 | `summarize_turns` 已把「摘要」与「裁剪」解耦，可在有凭证环境加 `summarizer=llm` 分支并纳入 eval |
| 3 | 后台（background）记忆巩固 | B1 的 background 写入需调度器；当前 hot path 足够（低频业务，轮次不长） | 若要跨会话情节记忆，加 cron/任务队列做 nightly consolidation |
| 4 | 双真源合并（checkpointer vs sessions.json，F6） | 属编排域决策（`graph.py` 状态职责） | 只用 `memory_tool divergence` 做对账；合并建议提给编排域 |
| 5 | 会话内 `invalidated` 数组上限（F7 残余） | 属编排域 State 语义，改它要动 SPEC §6.2 | 建议编排域加 `invalidated[-N:]` 裁剪或迁到长期记忆审计 |
| 6 | SPEC 登记记忆域（F8） | SPEC 是跨域契约，应由队长统一升版 | 建议 SPEC v1.0.6 增加：`memory_seeded/memory_ctx` 扩展键、`GET/DELETE /memory/{owner}`（若由 API 域实现）、记忆保留期 |
| 7 | 前端「记忆管理」界面 | 前端域（`web/index.html`）职责 | 可把 `memory_tool list` 的输出做成抽屉面板；注意 `esc()` 转义（前端域既有约定） |
| 8 | 记忆内容加密/权限 | 安全域职责；当前靠 `TRACE_DIR` 目录 + 文件权限 | 建议安全域把 `traces/memory/` 纳入与 `sessions/` 同级的 0600 策略 |
| 9 | 多租户隔离强度 | 现按 `owner_id` 分文件（路径经 `_safe()` 洗白），但 `/chat` 的 owner 由 API-Key 派生才可信 | 已在测试覆盖「无 owner 不写」；信任链依赖 API/安全域 |

**已知局限（必须写清，避免过度声称）**
- 记忆召回的「语义相关性」只有**显式指代**一种触发，属于**保守设计**：车主换种说法（「跟刚才那台车一样」以外的新表述）不会触发。这是为保护保费正确性付的代价。
- 摘要是有损压缩且**不做实体消歧**（B5 的 merge 里的 entity resolution 未实现）——本项目记忆按字段而非实体建模，故字段级去重已足够；若将来存自由文本记忆需补实体解析。
- 衰减参数（半衰期）是**经验默认值**，未做 A/B 调参；若后续有真实会话分布应据 B5 的「fact-invalidation 率/token 成本」调。

---

## 8. 参考来源清单（完整 URL + 检索时间戳）

| # | 来源 | URL | 发布/更新 | 检索时间 |
|---|---|---|---|---|
| B1 | LangChain Docs — Memory overview | https://docs.langchain.com/oss/python/concepts/memory | 2026 现行文档 | 2026-11-17 |
| B2 | LangGraph Docs — Stores | https://docs.langchain.com/oss/python/langgraph/stores | 2026 现行文档 | 2026-11-17 |
| B3 | LangChain Docs — Short-term memory | https://docs.langchain.com/oss/python/langchain/short-term-memory | 2026 现行文档 | 2026-11-17 |
| B4 | Oracle Developers — Which Agent Memory Approach Is Best for Long Conversations? | https://blogs.oracle.com/developers/which-agent-memory-approach-is-best-for-long-conversations | 2026-06-05 | 2026-11-17 |
| B5 | Hindsight (Vectorize) — Agent Memory Consolidation: Keep, Merge, Decay, Evict | https://raw.githubusercontent.com/vectorize-io/hindsight/e5e558bd041d452e23c1679ba6bc9c0553f20954/hindsight-docs/blog/2026-05-20-agent-memory-consolidation.md | 2026-05-20 | 2026-11-17 |
| B6 | MediaNama — AI Memory Raises New Privacy and Data Portability Questions | https://www.medianama.com/2026/08/223-ai-memory-privacy-data-portability/ | 2026-08-28 | 2026-11-17 |
| B7 | OpenAI — Memory and new controls for ChatGPT | https://openai.com/index/memory-and-new-controls-for-chatgpt/ | 2024-02-13（2025-06 更新） | 2026-11-17 |
| B8 | LoCoMo-Plus（ACL 2026, pp.25085–25100） | https://aclanthology.org/2026.acl-long.1150/ | 2026-07 | 2026-11-17 |
| B9 | LongMemEval 榜单分数（经 B5 转述） | 同上 B5 | 2026-05-20 | 2026-11-17（**待验证**，未一手核验） |

---

## 9. 复现命令

```bash
cd renewal-assistant

# 1) 记忆域单测（16 条：白名单/PII/supersede/TTL/decay/预算/摘要/闸门/遗忘/开关/集成/端到端/契约）
.venv/bin/python -m pytest tests/test_memory.py -q

# 2) 全量回归（写入时为 140 passed / 2 skipped；其它域并行新增用例时数字会更大）
.venv/bin/python -m pytest

# 3) A/B 评测（before=旧截断 / after=本次整改，落盘 eval/memory-eval-*.json）
.venv/bin/python eval/memory_eval.py

# 4) 运维/合规工具
.venv/bin/python scripts/memory_tool.py doctor
.venv/bin/python scripts/memory_tool.py list OWN-1001
.venv/bin/python scripts/memory_tool.py show OWN-1001
.venv/bin/python scripts/memory_tool.py divergence
.venv/bin/python scripts/memory_tool.py forget OWN-1001        # 遗忘权（不可逆）

# 5) 回滚闸门（整体退回旧截断策略）
RENEWAL_MEMORY=off .venv/bin/python -m pytest tests/test_persistence.py -q

# 6) 报价中性哨兵（记忆开关不得改变任何一轮保费；退出码 0 = 中性）
.venv/bin/python eval/memory_quote_neutrality.py
```

---

## 10. 变更文件清单（本域，attempt 4）

| 文件 | 类型 | 说明 |
|---|---|---|
| `server/memory.py` | 新增（798 行） | 记忆 store + 策略层 + memory manager + 运维诊断 |
| `server/sessions.py` | 小改 | 历史上限改配置项（默认 40）+ `save()` 内挂长期记忆写入（异常隔离） |
| `server/config.py` | 小改 | `memory_prompt_budget()` / `memory_chat_budget()` 两个预算旋钮 |
| `server/graph.py` | 小改（4 处调用点） | 旧固定切片 → `memory.prompt_context`；跨会话召回接入 `parse_needs`；`node_end.output.memory` |
| `tests/test_memory.py` | 新增（16 条） | 记忆域回归（含 /chat 端到端跨会话） |
| `eval/memory_eval.py` | 新增 | 5 场景 A/B 评测（约束一致性 / 矛盾检测 / token 成本 / 遗忘） |
| `scripts/memory_tool.py` | 新增 | 查看 / 审计 / 导出 / 遗忘 / 体检 / 对账 CLI |
| `eval/memory_quote_neutrality.py` | 新增 | 报价中性哨兵（记忆开/关保费逐轮一致，退出码即结论） |
| `reviews/memory.md` | 新增 | 本报告 |

---

## 11. 类型门禁收口（t16，2026-11-17）

### 11.1 背景与复现

`reviews/INDEX.md` 索引自检（X-01）发现：t4 新增的 798 行 `server/memory.py` 让 CI 的
mypy 门禁全红（**14 errors in 1 file**）。复现：

```bash
cd renewal-assistant
.venv/bin/python -m mypy        # 修复前：Found 14 errors in 1 file (checked 6 source files)
```

> 说明：`memory.py` 不在 `pyproject.toml` 的 `[tool.mypy] files` 列表里，但它是
> `server/sessions.py` 的导入依赖（`from . import memory`），**mypy 会跟随导入检查**，
> 所以这 14 处错误照样进 CI。这一点值得记住：门禁清单不等于被检查面。

### 11.2 逐条修法（零批量 `# type: ignore`，零 `cast`）

| 报错位置（修复前） | 根因 | 修法 | 行为影响 |
|---|---|---|---|
| `:287 arg-type` | `KIND_HALF_LIFE_DAYS.get(item.get("kind"), 90.0)`：`dict[str,float]` 收到 `Any \| None` | 先 `kind = str(item.get("kind") or "")` 再查表 | 无（合法 kind 映射不变，缺失仍走 90.0） |
| `:565 var-annotated` + `:571/578/579/582`（5 处） | `delta` 由字面量 `{"budget_yuan": None, "sum_insured_changes": [], …}` 推导成 `dict[str, list[Any] \| None]`，随后写 int/str 全部冲突；`delta["sum_insured_changes"].append(...)` 又撞 union-attr | 显式类型别名 `NeedsDelta = dict[str, Any]`（注释说明它**本就是异构映射**：`budget_yuan: int` / `use_nature_change: str` / `sum_insured_changes: list[dict]`，不是「list 或 duration」二选一）；取值处新增 `_as_int()` 收窄，`changes` 局部变量给出 `list[dict[str, int \| str]]` | 合法值完全一致；**脏数据由「抛 TypeError」改为「跳过该条」**（见 11.4） |
| `:707 func-returns-value` | `uniq = [p for p in points if not (p in seen or seen.add(p))]` 把 `set.add()` 的返回值当布尔用 | 改写成显式循环：`if point in seen: continue; seen.add(point); uniq.append(point)` | **真实逻辑瑕疵修正**：旧写法恰好因 `add()` 返回 None 才「碰巧正确」；新写法把意图写明。去重结果逐值一致（11.4 有等价性证明） |
| `:785-794 operator` ×5 | `report = {"owners": 0, …, "pii_leaks": [], "stale_active": []}` 被推导成 `dict[str, int \| list[Any]]`，`report["owners"] += 1` 变成 `object + int` | 新增 `class DoctorReport(TypedDict)`（`owners/items/expired/superseded/no_source: int`，`pii_leaks/stale_active: list[str]`），`doctor() -> DoctorReport`，明细列表用局部变量持有再放入 | 返回值的键集合与类型完全不变（11.4 校验） |

关键设计判断两条：

1. **为什么 `NeedsDelta` 用 `Any` 而不是 `TypedDict`**：该 dict 的消费方是
   `server/graph.py#_accumulate_needs(prev: dict, delta: dict)`——TypedDict **不是**
   `dict` 的子类型（mypy 因可变性判不兼容），要改用 TypedDict 就得同时改 `graph.py`
   的签名，而本任务硬约束是「只改 `server/memory.py`」。故用带完整注释的
   `dict[str, Any]` 别名 + 逐字段 `isinstance`/`_as_int` 收窄——语义清楚且不引入 `cast`。
2. **为什么保留 `stale_active` 字段**：它是体检报告的前向位（预留给「stale claim」类
   检查），当前不填充；放进 TypedDict 是为了让后续加检查时不必再改返回类型。

### 11.3 验证输出（全部 `.venv/bin/python`）

```
$ .venv/bin/python -m mypy
Success: no issues found in 6 source files            # 修复前：Found 14 errors in 1 file

$ .venv/bin/python -m pytest
148 passed, 2 skipped in 1.53s                        # 验收基线 140/2 不减（+8 为并行域新增用例）
$ .venv/bin/python -m pytest tests/test_memory.py -q
16 passed                                             # t4 的 16 条记忆域回归全绿

$ .venv/bin/python -m ruff check .
All checks passed!

$ .venv/bin/python eval/memory_eval.py
s1_cross_session_preference   FAIL → PASS   {budget_yuan:6000, DSX:2000000, seeded:[…]}
s2_contradiction_resolution   FAIL → PASS   {recalled_dsx:1000000, superseded:[2000000]}
s3_constraint_consistency     FAIL → PASS   {context_has_constraint:true, 47 tokens}
s4_context_budget_and_summary FAIL → PASS   {975 tokens 有界, summary 保留关键约束}
s5_erasure_and_portability    FAIL → PASS   {removed:1, residual:0}
合计：before 0/5 → after 5/5

$ TRACE_DIR=$(mktemp -d) .venv/bin/python eval/memory_quote_neutrality.py
turns: 7
premium mismatch: {}
on seeded: {}
VERDICT: PASS            # 7 轮保费逐轮完全一致（AC-01/05/06×2/07/09/10），exit=0
```

### 11.4 行为等价性证明（重构不改语义）

除测试外，另用一次性脚本对四处改动做**逐值等价**校验（2026-11-17 实跑）：

| 校验项 | 结果 |
|---|---|
| 摘要去重：旧表达式 `[p for p in points if not (p in seen or seen.add(p))]` vs 新循环，4 组输入（含空、单元素、多重重复、60 元素） | **逐值相同**（均等价于保序去重）；同句重复在摘要里只出现一次 |
| `_as_int()` vs 原 `int()` 的接受范围 | 合法值 `6000 / 6000.0 / "6000" / 6000.4` → **全是 6000**（与原 `int()` 一致） |
| `_as_int()` 对脏值 `None / "abc" / "" / {} / [] / nan` | 全部返回 `None` 且**不抛异常**（原 `int()` 对 `None`/`""`/`{}` 抛 TypeError/ValueError，会让整轮召回中断） |
| `_score()` 半衰期映射 | `preference/constraint/fact/episodic` 与缺失/未知 kind 的半衰期不变；`fact` 半年后 ≈ **0.241**（理论 0.5^2.04） |
| `doctor()` 返回值 | 键集合 `[expired, items, no_source, owners, pii_leaks, stale_active, superseded]` 与类型（5×int + 2×list）**与修复前一致** |
| 脏数据端到端召回 | `put(budget_yuan="abc")` 后 `recall_needs("上次…")`：预算条目被**跳过**，三者 200 万正常召回，**无异常** |

唯一的行为变化是**健壮性增强**（坏数据跳过而非崩溃），不影响任何正常路径；16 条记忆回归、
5 场景 A/B、7 轮报价中性哨兵均已覆盖正常路径，全部通过。

### 11.5 复现命令（本小节专用）

```bash
cd renewal-assistant
.venv/bin/python -m mypy                       # 期望：Success: no issues found in 6 source files
.venv/bin/python -m pytest tests/test_memory.py -q
.venv/bin/python -m pytest                     # 期望：≥ 140 passed / 2 skipped
.venv/bin/python -m ruff check .
.venv/bin/python eval/memory_eval.py           # 期望：before 0/5 → after 5/5
TRACE_DIR=$(mktemp -d) .venv/bin/python eval/memory_quote_neutrality.py   # 期望：VERDICT: PASS
```
