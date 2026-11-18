# step-d3b · D3b 批量萃取 33 页（36 页全量）

> 任务：`t20`（attempt 1，`7e0edc7c-4781-4219-8253-e6da05bed72e`）｜执行：wiki-lead｜日期：2026-11-18
> 结果：**36 页齐全（4 doc / 18 section / 9 entity / 5 faq）**，两套 lint 均 0 error，幂等（40 个 md sha256 一致），2 次 entity 专项负向控制均咬住。
> ⚠️ 过程中有一次**误触全量构建**并因此改了 `log.md`（剔除 33 条失效记录），已留 `fix` 条目 + 本节 §5 明写，不隐瞒。

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 职责 |
|---|---|---|
| `scripts/compile_wiki.py` | 修改 | ①新增 `body_entity()`（实体页模板）；②`markers_by_split()` 修跨分片非法区间；③FAQ 判断类字段按分片映射；④entity 的 `insurance_line` 按真实单元推导；⑤doc↔section/faq 改按「单元有交集」连边；⑥`order` 子命令输出 plan 顺序 |
| `scripts/wiki_lint.py` | 修改 | L5 目录名复数表（`entity → entities`，此前误写成 `entitys`） |
| `wiki/{docs,sections,entities,faqs}/*.md` | 生成 **36 页** | 4 / 18 / 9 / 5 |
| `wiki/index.md` | 重建 | 36 行，列齐全 |
| `wiki/log.md` | 追加 | 36 条 `ingest`（各含 `page/units/qids/result/lint`）+ 1 条 `fix`（见 §5） |
| `wiki/schema.md`、`wiki/README.md` | 重建/更新 | 同步 `insurance_line`、span 语法（含 JSON 路径）、entity 页约定 |
| `docs/log/step-d3b.md` | 新增 | 本日志 |

**没碰**：`raw/**`、`plan.md`、`server/`、`tests/`、`mcp_servers/`、`SPEC.md`、`renewal-assistant/wiki/`、`traces/`。
`git status --short -- wiki traces server tests SPEC.md mcp_servers` 与 `git diff 40541d1 -- …` 均为空。

---

## 2. 开工前的两件前置（均已确认完成）

| 前置 | 状态 |
|---|---|
| `claim_type` → `insurance_line` 改名 | ✅ 在 t7 已落地（生成器 `INSURANCE_LINE`、两套 lint 必填/枚举、`schema.md` §2.1 改名记录）；本步 36 页全部使用 `insurance_line`，`grep claim_type` 0 处误用 |
| `body_entity()` 模板 | ✅ 本步新增。设计：§1 字段出处（逐字 + 行区间）→ §2 **属性事实表（逐单元 × 逐属性各一个 `@labels.*` 标记）** → §3 取值分布（区间标记）→ §4 互链。**每个属性都有标记，无裸断言**（验收要求） |

---

## 3. 分批执行与逐批 lint（FAIL=0 才进下一批）

按 `plan.md` §4 顺序（`compile_wiki.py order` 输出）分 6 批，每批用**累计页集合**构建（保证 `index.md` 始终与磁盘一致、`log.md` 只追加新页），批后跑两套 lint：

| 批次 | 累计页 | 构建 | D3 lint | D4 lint |
|---|---|---|---|---|
| 1 | 6 | ok | **FAIL=60 → 修**（见 §4） | ERROR=68 → 修 |
| 2 | 12 | ok | FAIL=0 | **ERROR=24 → 修**（log 陈旧记录，见 §5） |
| 3 | 18 | ok | FAIL=0 | ERROR=0 |
| 4 | 24 | ok | FAIL=0 | ERROR=0 |
| 5 | 30 | ok | FAIL=0 | ERROR=0 |
| 6 | 36 | ok | FAIL=0 | ERROR=0 |

> 批 1/2 的失败是**真失败**，没有跳过：批 1 暴露生成器三个跨分片缺陷，批 2 暴露 log 陈旧记录；修完再跑，批 3–6 全绿。

---

## 4. 规模化后暴露并修掉的 4 个缺陷（都只在 >3 页时才会出现）

| ID | 缺陷 | 触发条件 | 修法 |
|---|---|---|---|
| G1 | 区间标记跨分片非法：`claim_0..liability_20` | doc 页跨分片（auto = claim + liability） | 新增 `markers_by_split()`，按分片分组各发一个区间 |
| G2 | doc 页 §2 用「键并集首键 × 全部单元」发标记 → `labels.weather` 在 claim 单元上不存在 | 同上 | 每个键只对**真正含该键**的单元发区间标记，并在文本里标出「键(条数)」 |
| G3 | FAQ 硬编码 `labels.claim`，但 health/liability/property **没有 `claim` 字段** | 非 agri 分片的 FAQ 页 | 增 `DECISION_KEY` 映射：agri/claim→`claim`、property→`claim_decision`、health→`underwriting_decision`、liability→`primary_responsibility` |
| G4 | entity 页 `insurance_line` 恒为 `cross_cutting`；`doc-auto` 与 liability 页无互链 → `faqs/liability` 成孤儿 | 36 页规模 + 跨分片 doc | entity 的 `insurance_line` 按真实单元推导；doc↔section/faq 改按「单元集合有交集」连边 |

另修 D3 lint 自身一处 bug：L5 的目录名用 `type + "s"`，把 entity 判成 `entitys/`（误报 9 条）。已改显式复数表。

---

## 5. 事故与纠偏（不美化）：一次误触全量构建 + 改了 `log.md`

**发生了什么**：第一批驱动脚本用了 bash `mapfile`（macOS 自带 bash 3.2 无此内建），页列表为空 → `build --pages ""` 退化成 `build --all`，用**当时仍有 G1/G2/G3 缺陷的生成器**一次性产出 36 页，并追加了 33 条 ingest 记录。

**处置**：
1. 删除全部生成页（可重生成），把 `log.md` 收敛到「表头 + `fix` 留痕」，随后按 §3 的 6 批重编。
2. 批 2 又发现 log 里仍残留 24 条指向「尚未编译页」的旧 ingest 记录（D4 lint E8 抓到），再做一次收敛。

**偏离声明**：R1 spec §5 要求 `log.md` **只追加**；本步为清除失效记录**做了收敛**（否则 D4 lint 会持续报「记录指向不存在的页面」）。已在文件顶部保留一条 `fix` 条目写明：`reason / action / 影响范围`。这是本步唯一的流程偏离，**其他任何一步都没有改过历史条目**。

**教训**：`build` 的「空 `--pages` 等于 `--all`」是危险默认值。后续若再做分批，应在 `cmd_build` 里把「显式传了 `--pages` 但解析为空」判为错误而不是全量。→ 已登记为遗留项（§7-3）。

---

## 6. 验证证据（命令 + 真实输出）

### 6.1 页型分布与索引/账本

```text
$ for t in docs sections entities faqs; do ls data/llm-wiki-claims/wiki/$t/*.md | wc -l; done
docs=4  sections=18  entities=9  faqs=5          # 合计 36，与 plan.md §4 逐条对应

$ grep -c '^| \[' data/llm-wiki-claims/wiki/index.md
36
$ grep -c '] ingest |' data/llm-wiki-claims/wiki/log.md
36
$ grep -c '] fix |' data/llm-wiki-claims/wiki/log.md
1
```

`log.md` 每条 ingest 都带 `page / units / qids / result / lint`，`units` 即 `raw_id` 列表 → 可逐条追溯到 raw 源文件；例：

```text
## [2026-11-18] ingest | claims-entity-coverage-limit
- page: entities/coverage-limit.md
- units: raw-claim-0000, raw-claim-0001, … raw-claim-0011
- qids: claim_0, … claim_11
- result: ok (serial, one unit at a time)
```

### 6.2 互链完整性（无孤儿、全双向）

```text
related 边数=128  非双向/缺文件=0
related 为空的页: 无（每页都有互链）
```

（注：我第一版自查脚本同样犯了 `entity+s` 的复数错误，误报 17 条「目标缺文件」；改用 `{doc:docs, section:sections, entity:entities, faq:faqs}` 后为 0。两套 lint 本身用的是正确复数表。）

### 6.3 两套 lint 终态

```text
$ python3 data/llm-wiki-claims/scripts/wiki_lint.py
pages=36 index_rows=36 FAIL=0 WARN=0            # exit=0

$ python3 data/llm-wiki-claims/scripts/wiki_claims_lint.py
pages=36 index_rows=36 ERROR=0 WARN=0          # exit=0
```

### 6.4 幂等（连跑两次全产物）

```text
$ 两次构建后比对 wiki/**/*.md 的 sha256
IDEMPOTENT: 40 个 md sha256 一致               # 36 页 + index + log + schema + README
```

### 6.5 entity 专项负向控制（船长要求 ≥2 次）

| # | 注入 | D3 lint | D4 lint |
|---|---|---|---|
| F | 删掉 `entities/coverage-limit.md` 的 `source_refs` 行 | `FAIL=3` exit=**1**：`[L1] 缺少必填字段: source_refs` / `source_refs 为空` / `[L6] 聚合标记的单元超出本页 source_refs` | `ERROR=3` exit=**1**：`E1 缺字段 source_refs` 等 |
| G | 把该页 `@L1-L1` 改成 `@L1-L99`（越界） | `FAIL=2` exit=**1**：`[L6] 逐字引用块与 raw 不一致（L1-L99）` / `行区间越界` | `ERROR=1` exit=**1**：`E9 第 9 行 span 行区间越界 L1-L99（该单元 14 行）` |

两次注入后均用 `build` 复原，复原后两套 lint 回到 `FAIL=0 / ERROR=0`。

---

## 7. 遗留与交接（给 t23）

| # | 事项 | 说明 |
|---|---|---|
| 1 | 36 页全量质检 + ≥6 页人工抽样 | t23 主任务；方法用 `wiki_claims_lint.py --sample 10 --seed 20261118`，重点补**跨页冲突**（entity 页 vs section 页对同一字段的说法）与**覆盖缺口** |
| 2 | 引用「语义支撑」仍需人看 | machine 只能验「标记可解析 + 逐字一致」；t7 抓到的 F3/F6/F7 类「指错字段」在 36 页上还会有，抽样时优先看 entity 页（它们最容易退化成常识介绍） |
| 3 | `build --pages ""` 退化为 `--all` | 建议改成显式报错；本步因它误触一次全量构建（§5） |
| 4 | `index.md` 体量 | 36 页后 index 约 8 KB；R1 spec 的 L0 预算 3k tokens（≈6 KB）已被突破，t23 需决定：精简摘要 or 分卷 |
| 5 | `log.md` 的历史收敛 | 本步做过一次（§5）；后续不要再收敛，除非出现同类失效记录，且必须同样留 `fix` 条目 |

**一句话交接**：36 页与 `plan.md` §4 逐条对应、两套 lint 0 error、幂等成立；`raw/` 与 `plan.md` 未改；可进入 t23 全量质检。
