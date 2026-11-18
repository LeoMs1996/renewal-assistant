# step-d3c · 修 --pages 空串根因 + index 体积 + log↔页面检查进 lint

> 任务：`t25`（attempt 2，`125cc739-8848-474f-9f99-4a9bfccf76cd`）｜执行：wiki-lead｜日期：2026-11-18
> 结论：**A 已根治**（`build --pages ""` 等 4 类误用一律 exit 2 且零文件变更）；**B 已达标**（index 6018 B ≤ 6144，≈2006 tokens）；**C 已进 lint**（两套各加 log↔页面 1:1 + 字段完整性 + fix 可审计，4 次负向控制均 exit 1）。
> ⚠️ B 的达标路径与你给的口径有偏差（见 §2.2）：**30 字摘要仍超预算**，最终用「26 字 + type 移入分组标题」，请你确认。

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 职责 |
|---|---|---|
| `scripts/compile_wiki.py` | 修改 | ①CLI 防线（见 §2.1）；②`index_summary()` 摘要前缀化（≤26 字）；③index 行改「slug 链接 + 标题去括注 + 摘要 + tags(分片) + updated」，type 交给分组标题；④`schema` 文本同步 index 契约与体积台账；⑤`schema` 生成命令改为 `build --all` |
| `scripts/wiki_lint.py` | 修改 | ①`parse_index` 适配新 5 列格式（type 取自分组标题）；②L10 改为「摘要前缀 + updated 相等 + tags 子集 + 分组 type 一致」；③**新增 L12**：log↔页面 1:1 + ingest 必含 `page/units/result` + fix 可审计 |
| `scripts/wiki_claims_lint.py` | 修改 | ①E2 同步新 index 格式与前缀/updated/tags/type 校验；②E8 扩展为「集合相等 + 重复检测 + 字段完整性 + fix 可审计」；③`--sample/--seed` 参数解析加固（非数字/缺值/未知参数 → exit 2） |
| `wiki/index.md` | 重建 | 6018 B（原 10,332 B），36 行 |
| `wiki/schema.md` | 重建 | index 契约 + **体积台账（6018 B / ≈2006 tokens / 方法）** |
| `docs/log/step-d3c.md` | 新增 | 本日志 |

**没改**：`wiki/*/*.md` 页面（未手改、未改 `summary` 字段；`build --all` 会按生成器重写，见 §4-2）、`raw/**`、`plan.md`、`claims/**`、`server/**`、`renewal-assistant/wiki/`。
`git status --short -- wiki traces server tests SPEC.md mcp_servers` 与 `git diff 40541d1 -- …` 均为空。

---

## 2. 关键决策与依据

### 2.1 A：把「无选择器」和「空选择器」都判为错误

| 用法 | 处理 |
|---|---|
| `build --pages id1,id2` | 正常（只写这些页） |
| `build --all` | 正常（显式全量） |
| `build --pages ""` / `build --pages ,` | **exit 2**：`--pages 的值为空：必须给出至少一个 page id；若确实要全量重建请显式使用 --all` |
| `build --pages`（缺值） | **exit 2**：`--pages 后必须跟至少一个 page id（本次为空值）` |
| `build`（不给选择器） | **exit 2**：`必须显式指定构建范围…（不提供任何选择器就等于“全量重写”，已禁止）` |
| `build --pages X --all` | **exit 2**：互斥 |
| 未知参数 | **exit 2** |
| `--sample/--seed` 非整数/缺值/未知参数 | **exit 2**（原本抛 ValueError 栈） |

**根因**：原实现用 `pages_filter: list|None`，空列表是 falsy → 与「不过滤」共用一条分支。现在把「有没有给选择器」变成显式枚举（`--pages` / `--all`），**没有第三种默认**。
**为什么重要**：这是有副作用的构建命令，「参数写错」退化成「全量重写」会在无人察觉时覆盖 36 页（t20 已发生过一次）。

### 2.2 B：index 精简——实测表明「30 字摘要」不足以达标，最终采用「26 字 + type 移入分组标题」

实测（先模拟后落码，模拟脚本已跑过 5 组方案）：

| 方案 | 估算/实测 | 是否 ≤6144 |
|---|---|---|
| 原样 | 10,332 B | ❌ |
| 摘要 ≤30 + tags 去常量 + slug 链接 + 标题去括注（**保留 type 列**） | 6,780 B（实测） | ❌ |
| 同上 + 摘要 ≤20（保留 type 列） | ≈6,209 B | ❌ |
| 同上 + 摘要 ≤18（保留 type 列） | ≈6,099 B | ✅ 但摘要几乎无语义 |
| **最终采用**：摘要 ≤26 + tags 只留分片 + **type 移入分组标题** + slug 链接 + 标题去括注 | **6,018 B（实测）** | ✅ |

**偏离说明**：你给的口径是「摘要 ≤30 字，目标 ≤6 KB」。实测 30 字只能到 6,780 B；若保住 30 字摘要，就必须砍掉 `type` 列（信息由分组标题承载，不丢）或压到 18 字（摘要失去导航价值）。我选了**前者 + 摘要再收到 26 字**，理由：`type` 在分组标题 `## 文档页（4）/章节页/实体页/问答页` 里逐行都能判定，信息未丢失；18 字摘要把 `INS-MMBench 子集 agri 保险 12 条样本的登记页` 压成 `INS-MMBench 子集 ag…`，等于毁掉 L0 的导航作用。

**若你要求每行保留 type 列**：唯一达标路径是摘要 ≤18 字（≈6,099 B），我可以立刻改；或批准分卷（主 index ~1 KB + 4 个分卷文件）——**我没有自行分卷**。

**schema 已记台账**：

```
index.md = 6018 B
估算 token ≈ 2006
方法：UTF-8 中文 3 B/字，按「1 字 ≈ 1 token」保守换算（B/3）；英文与标点略偏保守
上限 6144 B（≈3k tokens，R1 spec §4 L0 预算）
超限优先序：先压摘要 → 再考虑按 type 分卷（需先报告）
```

### 2.3 C：把「log↔页面 1:1」变成机器检查（两套 lint 各一条）

| 检查 | D3 `L12` | D4 `E8` |
|---|---|---|
| ingest 标题集合 == 页面 `id` 集合（缺一） | ✅ `页面缺 ingest 记录` | ✅ `缺少 ingest 记录` |
| 多一（幽灵） | ✅ `幽灵 ingest（页面不存在）` | ✅ 同 |
| 重复 | ✅ `ingest 记录重复` | ✅ 同 |
| 每条 ingest 必含 `page:` / `units:` / `result:` | ✅ | ✅ |
| `fix` 不计入 ingest 集合，但必须可解析 `reason:` / `action:` / `影响范围:` | ✅ | ✅ |

**设计说明**：`fix` 条目**不做**「页面无关」的处理——它照样要能被审计（否则下次没人知道为什么改过 log）。这也是把 t20 那次 log 收敛事故做成"可被自动发现"的机制。

---

## 3. 验证证据（命令 + 真实输出）

### 3.1 四条验收（原文）

```text
$ python3 data/llm-wiki-claims/scripts/compile_wiki.py build --pages ""
exit=2
FATAL: --pages 的值为空：必须给出至少一个 page id；若确实要全量重建请显式使用 --all
用法：compile_wiki.py build --pages <id1,id2,...>  或  build --all

# 零文件变更：构建前后对 wiki/ 全部 md 的「目录整体 sha256」比对
before=00021bf3a071388ef3717e2d54573ce38f5f00810dc6b249e350726db49c78c0
after =00021bf3a071388ef3717e2d54573ce38f5f00810dc6b249e350726db49c78c0
✅ 零文件变更

$ wc -c data/llm-wiki-claims/wiki/index.md
    6018 data/llm-wiki-claims/wiki/index.md
6018 B → 估算 2006 tokens（B/3，中文 3B/字保守计）

$ python3 data/llm-wiki-claims/scripts/wiki_lint.py
pages=36 index_rows=36 FAIL=0 WARN=0            # exit=0

$ python3 data/llm-wiki-claims/scripts/wiki_claims_lint.py
pages=36 index_rows=36 ERROR=0 WARN=0          # exit=0
```

### 3.2 A 的另外 3 类误用（均 exit 2，且零变更）

```text
[build]                          exit=2  FATAL: 必须显式指定构建范围：--pages <id,...> 或 --all（不提供任何选择器就等于“全量重写”，已禁止）
[build --pages]                  exit=2  FATAL: --pages 后必须跟至少一个 page id（本次为空值）
[build --pages claims-faq-agri --all] exit=2  FATAL: --all 与 --pages 不能同时使用
[--sample abc]                   exit=2  FATAL: --sample 必须是整数，收到 'abc'
[--bogus]                        exit=2  FATAL: 未知参数 --bogus
```

### 3.3 C 的负向控制（4 次，两套 lint 都咬住）

| # | 注入 | D3 | D4 |
|---|---|---|---|
| 1 | 删掉一条 `ingest \| claims-faq-claim` | exit=1 `[L12] 页面缺 ingest 记录: claims-faq-claim` | exit=1 `[E8] 缺少 ingest 记录：claims-faq-claim` |
| 2 | 注入幽灵 `ingest \| claims-ghost-page` | exit=1 `[L12] 幽灵 ingest（页面不存在）` | exit=1 `[E8] 幽灵 ingest（页面不存在）` |
| 3 | 删掉 fix 条目的 `影响范围:` 行 | exit=1 `[L12] fix 条目无法审计（缺 影响范围:）` | exit=1 `[E8] fix 条目无法审计（缺 影响范围:）` |
| 4 | 删掉某条 ingest 的 `- units:` 行 | exit=1 `[L12] ingest 缺字段 units:` | exit=1 `[E8] ingest 缺字段 units:` |

每次注入后均从备份复原；复原后两套 lint 回到 `FAIL=0 / ERROR=0`。

### 3.4 幂等与一致性

```text
$ 两次 build --all 后比对 wiki/**/*.md
IDEMPOTENT: 40 个 md 一致

$ 比对 --pages(全量 id) 与 --all 的产物
✅ --pages(全量) 与 --all 产物完全一致      # 新 CLI 没有签名分歧
```

---

## 4. 遗留与交接

| # | 事项 | 说明 |
|---|---|---|
| 1 | **B 的口径偏差待你确认** | 30 字摘要 → 6,780 B（超）；现为「26 字 + type 移入分组标题」= 6,018 B。若必须每行保留 type，只能压到 18 字摘要（6,099 B）或分卷——**我没自行分卷**，等你裁决 |
| 2 | **11 页 sha 与 t20 基线快照不一致 —— 已归因（t26 补记）** | 差异来自 **t23 改了编译器后 `build --all` 按新规则重写**，不是未知漂移。船长给出的两条证据：① `entities/compensation-tier.md` 含 t23 新增的「同名不同义」约束（1 处）；② `sections/claim-loss-amount.md` 已补引金额指令（t23 第 3 类修复）。结论：**属预期变更**；t25 当时未掌握 t23 的改动清单，所以写了“未完全归因”——此处更正 |
| 3 | index 只剩 126 B 余量 | 6018 / 6144。再增页就会超；下次增长前需要：先压摘要 → 再按 type 分卷（需先报告） |
| 4 | `--sample` 上限未约束 | 现在要求 >0；语义上 ≤ 页数即可（脚本已自动截断） |
| 5 | 其它调用点已排查 | 仓库内没有 `.py/.sh/.yml` 调 `compile_wiki.py`；`schema.md` 的原「裸 build」命令已改为 `build --all`，`README.md` 本就是 `--all` |
giV
---

## 5. t26 追加：index 摘要改为「生成的短标签」+ 归因补记

> 背景：t25 用「summary 截断到 26 字」压体积，船长否决——截断后开头是标题同义重复（`INS-MMBench 子集 agri 保险 12…`），索引失去定位价值。

### 5.1 改法：短标签由元数据确定性生成（不截断）

| 页型 | 模板（`·` 分隔） | 实例 |
|---|---|---|
| doc | `分片[+分片] · N 条样本 · K 字段` | `claim+liability · 24 条 · 16 字段` |
| section | `分片 · 主字段[/次字段] · N 单元` | `claim · Min_coverage · 12 单元` |
| entity | `标题 · 主字段 · D 种取值`（或 `标题 · D 种：值1/值2`） | `核保决定 · 3 种：Declined/Standard` |
| faq | `分片 · 判断字段 · D 种取值` | `agri · claim · 2 种取值` |

- 生成器按固定**降级顺序**取第一个「≤30 字且不含省略号」的候选，因此永不输出半句话；**无人工手写**（36 页同一种风格）。
- 两套 lint 各自校验：≤30 字 / 无 `…` / 必含数字（数量维度）/ 必以分片开头（entity 以标题开头，区分维度）。
- 途中修正一处 lint 自身 bug：区分前缀取的是 `tags[0]`（`ins-mmbench` 常量），应为 `tags[1]`（分片），否则 36 行全误报。

### 5.2 验收（原文）

```text
$ wc -c data/llm-wiki-claims/wiki/index.md
    5867 data/llm-wiki-claims/wiki/index.md          # ≤6144
$ grep -c '…' data/llm-wiki-claims/wiki/index.md
0                                                  # 无省略号
$ python3 scripts/wiki_lint.py
pages=36 index_rows=36 FAIL=0 WARN=0              # exit=0
$ python3 scripts/wiki_claims_lint.py
pages=36 index_rows=36 ERROR=0 WARN=0             # exit=0
$ 两次 build --all 比对
IDEMPOTENT: 40 个 md 一致
```

标签长度：min/median/max = **14 / 24 / 30** 字；长度分布无一个超过 30。

### 5.3 抽 3 行看「如何区分同类页」

```text
| [`claim-policy-validity`](sections/claim-policy-validity.md) | 保单有效期与失效 | claim · Expiry_date · 12 单元 |
| [`claim-coverage-limits`](sections/claim-coverage-limits.md) | 保额上下限       | claim · Min_coverage · 12 单元 |
| [`underwriting-decision`](entities/underwriting-decision.md) | 核保决定       | 核保决定 · 3 种：Declined/Standard |
```

- 前两行同属 `claim` 分片、同为 `12 单元`，但**主字段不同**（`Expiry_date` vs `Min_coverage`）→ 一眼可分开；
- 第三行是 entity 页：给出**取值枚举**（`Declined/Standard`）+ 种类数 → 与 section 页的“字段事实”区分开；
- doc 页则用「覆盖分片 + 条数 + 字段数」区分（`claim+liability · 24 条 · 16 字段` 一眼看出它跨两个分片）。

### 5.4 负向控制（证明新规则真能咬）

| 注入 | 结果 |
|---|---|
| 把某行标签改成截断式 `claim · Min_cove…` | D3 exit=1 `[L10] 短标签含省略号（禁止截断）` + `缺少数量维度`；D4 exit=1 同 |
| 把某行标签改成 `agri · 样本 · 字段`（去数量） | D3 exit=1 `[L10] 短标签缺少数量维度` |

### 5.5 归因补记（对应船长要求）

§4-2 已从「未完全归因」改为 **已归因**：11 页差异来自 t23 修改编译器后的 `build --all` 重写（证据：`entities/compensation-tier.md` 的同名不同义约束、`sections/claim-loss-amount.md` 的金额指令补引），属预期变更。

### 5.6 体积台账更新

`index.md` = **5867 B**（t25 为 6018），估算 **≈1955 tokens**（B/3 保守法），上限 6144 B。`schema.md` 已同步短标签契约与台账；增长超限时**不再压字数/删列**，改为报告 + 分卷（须批准）。

---

**一句话交接（t26 更新）**：`build` 必须显式给 `--pages` 或 `--all`，写错参数一律 exit 2 且零副作用；index **5867 B（≈1955 tokens）** 在 L0 预算内，末列已是**生成的短标签**（≤30 字、无省略号、含字段/数量维度）；log↔页面 1:1 与短标签规则均已进两套 lint。
