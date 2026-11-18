# 理赔域 LLM-Wiki schema（schema.md）

> 规范来源：`docs/research/llmwiki-spec.md`（R1 定稿）；本文件是它在本语料根的落地摘要。
> 生成方式：`python3 data/llm-wiki-claims/scripts/compile_wiki.py build --all`（勿手改；`build` 不带选择器会报错，防误触全量）。

## 1. 三层

| 层 | 位置 | 谁写 |
|---|---|---|
| raw（事实，不可变） | `../raw/sources/*.json` | D2 生成器；LLM 只读 |
| wiki（知识，本目录） | `index.md` / `log.md` / `<type>/*.md` | 编译脚本（D3） |
| schema | 本文件 | 人 + 脚本共演进 |

## 2. frontmatter（9 必填 + 1 补充）

| 字段 | 必填 | 取值 |
|---|---|---|
| `id` | 是 | `claims-<type>-<slug>`，全局唯一 |
| `type` | 是 | `doc｜section｜entity｜faq`（`query` 由 D4 回写时新增） |
| `title` | 是 | 中文短标题 |
| `domain` | 是 | 恒 `claims` |
| `insurance_line` | 是 | `auto_claim｜auto_liability｜agricultural_claim｜health_underwriting｜property_claim｜cross_cutting` |
| `summary` | 是 | 一句话 ≤80 字，与 index 摘要列完全一致 |
| `tags` | 是 | 3 个：`ins-mmbench` / 分片 / 页类型 |
| `source_refs` | 是 | `INS-MMBench:qid=<split>_<idx>` 列表（D4 核对用） |
| `raw_refs` | 补充 | `raw-<split>-<idx:04d>` 列表（R1 spec 的 raw_id 形式） |
| `updated` | 是 | ISO 日期（本批固定 `2026-11-18`） |
| `related` | 是 | 其它 `id`，必须双向；可为空（尚无已编译邻居时） |
| `status` | 是 | `draft｜verified｜conflicted｜stale` |

`qid <-> raw_id` 是机械双射：`qid = <split>_<idx>`，`raw_id = raw-<split>-<idx:04d>`，均可从 `../raw/manifest.json` 反查。

### 2.1 字段改名记录（2026-11-18）

**`claim_type` → `insurance_line`**（船长评审裁决定名）。原因：`claim` 在本项目同时表示「理赔域（claims）」与「断言（claim）」，36 页规模下极易被误读成 fact/rule 那类断言分类。
方法名与值域**未变**（仍是 6 个业务类型枚举），只改字段名；旧名 `claim_type` **不要再使用**，两套 lint 均已把它移出必填列表。
若看到历史文本写 `claim_type`，按本条映射理解为 `insurance_line`。

## 3. 引用语法（断言级，span 必须落到字段/行/图）

| 形态 | 例子 | 适用 |
|---|---|---|
| 单单元 | `⟦S:INS-MMBench:qid=agri_0@labels.species⟧` | 单条样本事实 |
| 单元区间 | `⟦S:INS-MMBench:qids=agri_0..agri_11@labels.count⟧` | 聚合陈述（集合必须 ⊆ 本页 source_refs） |
| 行区间 | `⟦S:INS-MMBench:qid=agri_0@L9-L10⟧` | 题干规约逐字引用（1-based，含端点） |
| 图片 | `⟦S:INS-MMBench:qid=agri_0@agri/0/0.jpg⟧` | 视觉证据（图片未入库，见 §6） |
| 字段路径 | `⟦S:INS-MMBench:qid=agri_0@answer_status⟧` / `@sample.task_layer` | raw JSON 的任意标量路径（点分；`labels.a.b` 同理） |

禁止只写「来源：raw-xxx」这类粗引用。逐字引用块（`> ` 行）之后必须紧跟行区间标记，且内容必须与 raw 该行区间一致（比较时忽略行尾空白）。

## 4. 页面正文约定

1. 只写两类内容：逐字引用（`>` 块 + 行区间标记）与样本表行（每行带字段级标记）。
2. 聚合陈述必须紧跟区间标记，且区间集合 ⊆ 本页 `source_refs`。
3. 不得引入 raw 之外的知识；业务解释一律标注「本页不回答」。
   评测口径等**方法约束**必须以 `- 【方法约束】` 开头，且**不得挂引用标记**（它是规则，不是样本事实）。
4. 图片未入库：正文必须写明「需按 FETCH.md 重取后校验 sha256」的前提。

## 5. index.md / log.md

- `index.md`：每页一行，列为 `id | 标题 | 短标签 | tags | updated`，**type 由分组标题承载**（`## 文档页 / 章节页 / 实体页 / 问答页`）；脚本重建。
  **末列是「生成的短标签」，不是 summary 截断**（截断会切出「标题同义重复 + …」，无定位价值）。短标签由页面元数据确定性生成，规则：
  | 页型 | 生成模板（`·` 分隔） | 例 |
  |---|---|---|
  | doc | `分片[+分片] · N 条样本 · K 字段` | `claim+liability · 24 条 · 16 字段` |
  | section | `分片 · 主字段[/次字段] · N 单元` | `claim · Min_coverage · 12 单元` |
  | entity | `标题 · 主字段 · D 种取值`（或 `标题 · D 种：值1/值2`） | `保额与赔付上限 · 12 种：1122.5/715.0` |
  | faq | `分片 · 判断字段 · D 种取值` | `agri · claim · 2 种取值` |
  生成时按固定降级顺序选出 **≤30 字且不含省略号** 的第一种候选；**禁止**人工手写（36 页会出 36 种风格）。
  两套 lint 各自校验：≤30 字 / 无 `…` / 必须含数字（数量维度）/ 必须以分片（entity 为标题）开头（区分维度）+ updated 相等 + tags ⊆ frontmatter tags。
  链接标签用 slug（`claims-<type>-` 前缀在分组标题里已表达，省字节）。
  **体积台账（2026-11-18 实测，t26 短标签版）**：`index.md` = **5867 B**；估算 token ≈ **1955**（方法：UTF-8 中文 3 B/字，按「1 字 ≈ 1 token」保守换算，即 B/3；英文与标点略偏保守）。
  上限 **6144 B（≈3k tokens）**，来自 R1 spec §4 的 L0 预算。增长到超限时：**不再压缩字数或删列**，改为报告并提出按 type 分卷（`index-{doc,section,entity,faq}.md`），分卷须经批准。
- `log.md`：只追加，格式 `## [YYYY-MM-DD] <op> | <title>`；`op ∈ ingest｜query｜lint｜fix｜schema｜retract`；每条 `ingest` 必须含 `page`、`units`、`result`、`lint` 四项。

## 6. 已知边界

- 本子集 54 条 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`：分层只落在 `task_name`。
- 54 条 `answer` 全为 `null`（场景分片无 answer 列）：页面不得编造标准答案，D5 只评检索/接地指标。
- 图片未入 `raw/assets/`：需按 `../ins-mmbench/FETCH.md` 重取后校验 sha256。
- 部分标签在本子集为单值分布（按标签排序所致）：不得据此算分类准确率。
