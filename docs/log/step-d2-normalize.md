# step-d2 · D2 抽样数据规范化与萃取切分（交付日志）

> 任务：`t5`（attempt 2，`6bdda6eb-e74a-4663-986b-5db4c805c731`）｜执行：wiki-lead｜日期：2026-11-18
> 交付物：`data/llm-wiki-claims/{raw/sources/*.json ×54, raw/manifest.json, raw/README.md, raw/assets/README.md, plan.md, scripts/normalize_raw.py}`

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 一句话职责 |
|---|---|---|
| `data/llm-wiki-claims/scripts/normalize_raw.py` | **新增**（30,016 B） | 规范化生成器：读 D1 `records.jsonl` → 写 54 个源单元 + manifest + plan；`check` 子命令做只读校验 |
| `data/llm-wiki-claims/raw/sources/raw-<split>-<idx4>.json` | **新增 ×54** | 每条抽样记录一个不可变源文件（raw_id 稳定、无时间戳、无随机数） |
| `data/llm-wiki-claims/raw/manifest.json` | **新增**（76,639 B） | 源清单：id / split / source_index / records_line / 各层 sha256 / 图片 / `ingest_order` |
| `data/llm-wiki-claims/plan.md` | **新增**（35,598 B，185 行） | 三层切分（保险类型 → 任务层级 → 主题）+ 36 页清单 + **单元→页面**映射 + D3 执行契约 |
| `data/llm-wiki-claims/raw/README.md` | **改写**（C0 占位 → 实际 schema） | 说明 `d2-raw-1.0` 字段、两种 span 写法、幂等校验命令、图片不入库的理由 |
| `data/llm-wiki-claims/raw/assets/README.md` | **新增** | 说明本层**故意为空**：图片引用 + sha256，不复制；含代价与将来改法 |
| `docs/log/step-d2-normalize.md` | **新增** | 本日志 |

**没有改动**（逐项自检）：`data/llm-wiki-claims/wiki/**`（D3 才写，仍为 C0 占位）、`renewal-assistant/wiki/`、`data/ins-mmbench/**`（只读）、`server/`、`tests/`、`mcp_servers/`、`SPEC.md`、`traces/`、`claims/`、`.env`。

---

## 2. 关键决策与依据（决策 → 来源 → 影响）

### 2.1 本步检索记录（2026-11-18，工具 `web_call read.fetch` / `search.run`）

| # | 来源 | URL | 检索时间 | 类型 | 支撑的决策 |
|---|---|---|---|---|---|
| D2-S1 | Karpathy《LLM Wiki》gist 原文 raw（本步重新抓取） | https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw | 2026-11-18 | 一手 · 方法论 | ①raw 层「LLM 只读、不可变、是 source of truth」→ 源文件不写时间戳/不手改、只由脚本生成；②官方 tips 明确「把图片下载/落到固定目录（如 `raw/assets/`）」且「LLM 无法一次读带内联图的 markdown，要先读文本再单独看图」→ base64 不内联进文本层，文本与图片分成两类证据；③「一次只编译一个来源」→ 单元粒度取 1 条记录 |
| D2-S2 | `chenhz01/memory-wiki` README（本步重新抓取） | https://github.com/chenhz01/memory-wiki | 2026-11-18 | 社区 · 独立实现 | ingest「never overwrites without `--force`」→ 生成器宁可 FAIL 退出也不覆盖不一致产物；`lint` exit 1、log 只追加 → `check` 用退出码表达「不一致」 |
| D2-S3（复用 R1 S6） | `nashsu/llm_wiki` README（R1 已抓，2026-11-17） | https://github.com/nashsu/llm_wiki | 2026-11-17 | 社区 · 生产实现 | 每页 `sources[]` 溯源 + 「一个来源」为编译单位 → 源文件必须一眼能列出「归我管的证据」；本步把它固化为 `source` 段 + `spans` |
| D2-S4（复用 R1 S3） | `chenhz01/memory-wiki` 的 lint 语义（同上条目，R1 已引） | 同上 | 2026-11-17 | 社区 | 孤儿/断链/重复/超长是「腐烂」的可命名状态 → 生成器内置「无孤立源文件」检查，plan 内置「单元必须被 ≥1 页引用」检查 |

> **复用说明**：船长允许复用 R1 的 7 条来源，但要求写清支撑哪个决策——上表 D2-S3/S4 已给出「R1 的哪一条 → 本步哪一项决定」。本步**新抓**的两条（D2-S1/S2）用于「raw 只读 + 图片分层」「拒绝静默覆盖」这两个 R1 未细化的点。

### 2.2 决策 1：萃取单元 = 一条记录（54 个单元），不按字段组拆

- **决策**：`unit_id = raw_id = raw-<split>-<source_index:04d>`，一单元一文件；子单元 `question / labels / images` 只用于 span，不独立成单元。
- **依据**：[D2-S1]「一次处理一个来源」+ R1 spec §8（写放大 10–15 页/来源，并行必冲突）；[D2-S3] 的 per-source `sources[]` 溯源单元。
- **为什么不拆**：拆成 `question` 单元 + `labels` 单元会让单元数变 108，同一事实跨两单元落地 → 两份不同步的实体页，正好放大 R1 §8 点名的共享状态冲突；字段级可引用性用 **span 方案**解决（`@labels.Amount`），不必付拆单元的代价。
- **给 D3 的机械保证**：`manifest.ingest_order` 是唯一顺序来源；`plan.md` §4.1 给出「第 N 个单元 → 该写哪些页」的完整映射，D3 不需要再做判断。

### 2.3 决策 2：图片不复制、只引用 + sha256 钉住（`raw/assets/` 故意为空）

- **依据**：[D2-S1]（图片应落到固定目录被引用，而不是内联在文本里）+ C0 `raw/README.md`（不做二进制入库，只记路径与哈希）+ `.gitignore` 第 44–46 行（`data/ins-mmbench/**` 不入库）。
- **效果**：`asset_ref`（仓库相对路径）+ `bytes` + `sha256` + `asset_sha256_verified: true`，120 张全部现场校验通过；避免 33 MiB 重复入库。
- **代价（已登记）**：新 clone 无图片（`plan.md` §8 限制 1、`raw/assets/README.md` 已写明重取与复核步骤）。

### 2.4 决策 3：产物零时间戳、零随机 → 幂等由构造保证

- **依据**：[D2-S2]「ingest 不得静默覆盖」的反面要求——如果产物含时间戳，`check` 就永远无法证明「没人手改」。
- **做法**：生成器只由输入 + 静态常量（`SPLIT_ORDER` / `THEMES` / `ENTITIES` / `FAQS`）决定输出；`build` 与 `check` 走**同一构造路径**（`build_all()`），`check` 只比较字节。
- **效果**：连跑两次 56 个产物 sha256 完全一致（§3-B）。

### 2.5 决策 4：三层切分「保险类型 → 任务层级 → 主题」，但如实标注任务层级在本子集退化

- `task_layer` 54 条全为 `scenario`、`meta_task` 全为 null（D1 实测）。**不粉饰**：`plan.md` §3 明确写出该层只有一个取值，实际区分度落在 `task_name`（5 个任务）；保留该层只为与全量数据集对齐。
- 主题（第三层）全部来自 `labels` 的实测字段名，不自造概念：18 个主题 → 18 个 `section` 页；另 9 个跨任务 `entity` 页、4 个 `doc` 页、5 个 `faq` 页，共 **36 页**。

### 2.6 被否决的方案

| 被否决 | 原因 |
|---|---|
| 按字段组拆单元（question/labels 各成单元） | 单元数翻倍、事实跨单元落地易产生不同步实体页；字段级引用用 span 解决即可 |
| 把图片 base64 原样塞进 raw JSON | 单条最大 5 图，文本层会被撑爆且无法被 LLM 一次读取（[D2-S1] 明确要先文本后图片）；体积与 parse 成本都无收益 |
| 把图片复制进 `raw/assets/` | 33 MiB 重复入库，且两份文件迟早 sha 漂移；C0 已定「不做二进制入库」 |
| 在源文件里写 `generated_at` 等时间戳 | 破坏幂等，`check` 失去「是否被手改」的判据 |
| 用 manifest 作为数据源 | 船长指出 manifest 正被并行修改（补 `source_indices_taken` 等）；`records.jsonl` 才是 D1 的产物事实，本步只从 manifest 取 revision（且实测与 records 内的 `source_revision` 一致） |

### 2.7 未采信（诚实记录）

本步一次 `search.run`（查询「多模态入库文本/图片分离、one-file-per-source 粒度、溯源元数据字段」，`profile=docs_code`）返回 **0 条达标证据**（`no_page_content`，仅低相关排行榜/百科噪声）。
→ 未据此写任何规则；上述决策全部由 [D2-S1][D2-S2] + R1 spec（[S1]–[S7]）支撑。

---

## 3. 验证证据（命令 + 真实输出）

### A. 覆盖率：54 源 ↔ 54 记录，120 图片全可解析

```text
[A] 源单元 54 / records 54 / 一一对应: True
[B] raw_id 唯一: True  格式样例: raw-claim-0000, raw-property-0005
[C] 逐字保真校验（question/labels/answer/options/index/line/revision）: 全部一致
[D] 图片引用 120 条，磁盘存在 120，sha256 不一致 0
[E] 保险类型: {'auto': 24, 'agricultural': 12, 'health': 12, 'property': 6}
[F] 计划覆盖: 单元被计划引用 54/54，覆盖类型 ['agricultural', 'auto', 'health', 'property']
[G] 计划页面数 36，任务数 5
[I] plan.md 提到所有保险类型: True
[J] plan.md 含全部 54 个 raw_id: 54/54（修正前为 10/54，已把表改为全量 id 并新增 §4.1 单元→页面映射）
[K] plan.md 行数 185，含 8 节
```

> [C] 是「不改写」的硬证据：逐条对比 `raw/sources/*.json` 的 `question` / `labels` / `answer` / `options` / `source_index` / `records_line` / `record_line_sha256` / `revision` 与 `data/ins-mmbench/raw/<split>/records.jsonl` 对应行，**全部逐字一致**。

### B. 幂等：连跑两次，56 个产物 sha256 完全一致

```text
$ python3 data/llm-wiki-claims/scripts/normalize_raw.py build   # 第一次
$ (find …/raw/sources -name '*.json' | sort | xargs shasum -a 256; shasum -a 256 …/manifest.json …/plan.md) > /tmp/f1.txt
$ python3 data/llm-wiki-claims/scripts/normalize_raw.py build   # 第二次
$ (同一命令) > /tmp/f2.txt
$ diff /tmp/f1.txt /tmp/f2.txt
（无输出）
IDEMPOTENT: 56 个产物 sha256 完全一致
```

### C. 自校验子命令

```text
$ python3 data/llm-wiki-claims/scripts/normalize_raw.py check
CHECK OK: 54 个源文件与清单一致、内容逐字节可复现、无孤立文件
check exit=0
```

### D. 零污染

```text
$ git status --short -- wiki traces server tests SPEC.md mcp_servers
（空输出）
$ git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md
（空输出）
$ git status --short --untracked-files=all | grep -cE 'llm-wiki-claims'
62        # 54 sources + manifest + plan + 2 README + .gitkeep ×2 + scripts 目录内文件
```

`data/llm-wiki-claims/wiki/` 仍是 C0 的两个占位文件（`.gitkeep`、`README.md`），**D2 一个字都没写**。

### E. 可追溯：抽 3 个源反查 `records.jsonl`

```text
raw-claim-0000   : data/ins-mmbench/raw/claim/records.jsonl       L1  source_index=0  record_id=claim_0    question=990字/14行  images=1
raw-health-0002  : data/ins-mmbench/raw/health/records.jsonl      L3  source_index=2  record_id=health_2   question=1395字/13行 images=2
raw-property-0005: data/ins-mmbench/raw/property/records.jsonl    L6  source_index=5  record_id=property_5 question=1266字/14行 images=2
```

源文件内 `source.records_line` + `source.record_line_sha256` 双重钉住：改一行原文立刻可发现。

---

## 4. 遗留问题与交接

| # | 事项 | 承接方 | 说明 |
|---|---|---|---|
| 1 | 按 `plan.md` §4 顺序、§4.1 映射逐单元编译 | **D3** | 36 页 = 4 doc + 18 section + 9 entity + 5 faq；一次一单元、持 `.ingest.lock`、每单元追加 `## [YYYY-MM-DD] ingest \| <raw_id>` |
| 2 | `wiki/{index.md, log.md, schema.md}` 尚未创建 | D3 | D2 按船长要求**没碰** `wiki/`；D3 首个单元 ingest 时创建 |
| 3 | 图片在新 clone 缺失 | D5/D4 | 只影响多模态环节；文本检索与引用接地不受影响（`plan.md` §8 限制 1） |
| 4 | **台账 O-02 判定（`property.claim_decision` 能否作 GT）** | D2 → D5 | **本步判定：可作 property 域辅助 GT，但不作主指标。** 理由：6/6 条都有该字段且实测覆盖 No/Partial/Full 三类（有区分度）；但它是数据集标注者的结论、样本仅 6 条、且与 `type/number/damage_number` 同源标注，不能证明独立可靠性。建议 D5 用它做「方向一致性」抽检，主指标仍用 Hit@1 / MRR@5 / 引用接地率（D-04）。**这是判断不是测量**，如需实测须另开任务 |
| 5 | `data/ins-mmbench/manifest.json` 正被并行修改 | dataset-lead | 本步只从它取 revision（`b77ea65c…`），且与 `records.jsonl` 内 `source_revision` 交叉一致；manifest 字段变动不影响本步产物（`check` 重跑仍应 OK） |
| 6 | 主题（第三层）是「按字段聚类」，不是语义主题发现 | D3 → D5 | 18 个主题 = 18 组 label 字段；若 D3 编译时发现某主题证据过薄（如 `vehicle-condition` 只有 Condition/Cost_of_vehicle 两个字段），允许在其页面内标注「证据薄」，**不得**自行改 `plan.md`——改就改生成器的 `THEMES` 并重跑（保持可复现） |

**交接一句话**：D3 只需读三样东西——`plan.md`（做什么、什么顺序）、`raw/manifest.json`（`ingest_order` 与 sha256）、`raw/sources/<raw_id>.json`（证据）；写入范围严格限于 `data/llm-wiki-claims/wiki/`。
