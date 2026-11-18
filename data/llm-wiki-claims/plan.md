# 理赔域 LLM-Wiki 萃取计划（D2 产出 · D3 执行契约）

> 生成方式：`python3 data/llm-wiki-claims/scripts/normalize_raw.py build`（**勿手改**，改脚本重跑）。
> 规范依据：`docs/research/llmwiki-spec.md`（R1 定稿）；本文件只做「切分与顺序」，不定义新 schema。
> 数据来源：INS-MMBench 子集，revision pin `b77ea65c18c61108a32b811ca344308941ff8046`，许可 Apache-2.0。

## 1. 规模与输入

| 项 | 值 |
|---|---|
| raw 源单元（单元=1 条记录） | **54** |
| 引用图片 | **120**（磁盘已逐张 sha256 校验） |
| 分片 | claim=12, agri=12, health=12, liability=12, property=6 |
| 保险类型 | agricultural=12, auto=24, health=12, property=6 |
| 任务 | agri_claim_processing=12, auto_claim_processing=12, auto_liability_determination=12, health_risk_assessment=12, property_risk_management=6 |
| 计划页面 | **36**（doc/section/entity/faq 四类；query 由 D4 事后回写） |

## 2. 萃取单元决策：单元 = 一条记录（54 个单元）

**决策**：一个 raw 源单元 = D1 的一条抽样记录，`unit_id = raw_id = raw-<split>-<source_index:04d>`。

**理由（可机械执行，不需要 D3 再判断）**：

1. 一条记录本身就自洽：`question`（任务与规则文本）+ `labels`（事实字段）+ `images`（视觉证据）三者互相解释；只取 `labels` 会失去「这条事实在什么任务语境下成立」，只取 `question` 会失去全部事实。
2. 记一条 = 一个 ingest 事务，正好匹配「一次只编译一个来源」的串行纪律（R1 spec §8）：取一次锁、写一次日志、跑一次 lint，读写边界清晰。
3. 若再按字段组拆（question 单元 / labels 单元），单元数翻倍到 108，同一事实会跨两个单元落地，容易产生两边互不同步的实体页——反而放大 R1 spec 里点名的「共享状态冲突」问题。

**被否决方案**：按字段组拆单元。否决理由见上第 3 条；字段组的可引用性改由 **span 方案**解决（见 §5），不必靠拆单元实现。

## 3. 三层切分：保险类型 → 任务层级 → 主题

> **诚实说明**：本子集 54 条的 `task_layer` **全为 `scenario`**、`meta_task` 全为 null（D1 实测）。
> 因此「任务层级」这一层在本子集只有一个取值，第二层的实际区分度落在 `task_name`（5 个场景任务）上。
> 保留该层是为了与全量数据集的 `fundamental / meta_task` 层级对齐，避免日后扩样时改 schema。

| 保险类型 | 任务层级 | 任务（task_name） | 分片 | 单元数 | 主题（第三层） |
|---|---|---|---|---|---|
| auto | scenario | `auto_claim_processing` | claim | 12 | 保单有效期与失效、保额上下限、损失金额与严重程度、车辆条件与车值 |
| agricultural | scenario | `agri_claim_processing` | agri | 12 | 标的物种与数量、病害感染判定、赔付档位 |
| health | scenario | `health_risk_assessment` | health | 12 | 影像部位、报告一致性、风险等级、核保决定 |
| auto | scenario | `auto_liability_determination` | liability | 12 | 是否构成事故、事故成因与主责、道路场景与路段形态、天气与光照条件 |
| property | scenario | `property_risk_management` | property | 6 | 灾种识别、受灾与损失计数、理赔决定 |

## 4. 页面清单（D3 按此顺序产出）

| # | page_id | type | 标题 | 层级路径 | source_refs（全部单元 id） |
|---|---|---|---|---|---|
| 1 | `claims-doc-ins-mmbench-agricultural` | doc | INS-MMBench 子集：agricultural 保险样本总览 | agricultural | 12: `raw-agri-0000`, `raw-agri-0001`, `raw-agri-0002`, `raw-agri-0003`, `raw-agri-0004`, `raw-agri-0005`, `raw-agri-0006`, `raw-agri-0007`, `raw-agri-0008`, `raw-agri-0009`, `raw-agri-0010`, `raw-agri-0011` |
| 2 | `claims-doc-ins-mmbench-auto` | doc | INS-MMBench 子集：auto 保险样本总览 | auto | 24: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011`, `raw-liability-0000`, `raw-liability-0001`, `raw-liability-0003`, `raw-liability-0004`, `raw-liability-0006`, `raw-liability-0008`, `raw-liability-0010`, `raw-liability-0012`, `raw-liability-0016`, `raw-liability-0017`, `raw-liability-0019`, `raw-liability-0020` |
| 3 | `claims-doc-ins-mmbench-health` | doc | INS-MMBench 子集：health 保险样本总览 | health | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 4 | `claims-doc-ins-mmbench-property` | doc | INS-MMBench 子集：property 保险样本总览 | property | 6: `raw-property-0000`, `raw-property-0001`, `raw-property-0002`, `raw-property-0003`, `raw-property-0004`, `raw-property-0005` |
| 5 | `claims-section-claim-policy-validity` | section | 保单有效期与失效（auto_claim_processing） | auto > scenario > policy-validity | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 6 | `claims-section-claim-coverage-limits` | section | 保额上下限（auto_claim_processing） | auto > scenario > coverage-limits | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 7 | `claims-section-claim-loss-amount` | section | 损失金额与严重程度（auto_claim_processing） | auto > scenario > loss-amount | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 8 | `claims-section-claim-vehicle-condition` | section | 车辆条件与车值（auto_claim_processing） | auto > scenario > vehicle-condition | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 9 | `claims-section-agri-insured-subject` | section | 标的物种与数量（agri_claim_processing） | agricultural > scenario > insured-subject | 12: `raw-agri-0000`, `raw-agri-0001`, `raw-agri-0002`, `raw-agri-0003`, `raw-agri-0004`, `raw-agri-0005`, `raw-agri-0006`, `raw-agri-0007`, `raw-agri-0008`, `raw-agri-0009`, `raw-agri-0010`, `raw-agri-0011` |
| 10 | `claims-section-agri-infection-status` | section | 病害感染判定（agri_claim_processing） | agricultural > scenario > infection-status | 12: `raw-agri-0000`, `raw-agri-0001`, `raw-agri-0002`, `raw-agri-0003`, `raw-agri-0004`, `raw-agri-0005`, `raw-agri-0006`, `raw-agri-0007`, `raw-agri-0008`, `raw-agri-0009`, `raw-agri-0010`, `raw-agri-0011` |
| 11 | `claims-section-agri-compensation-tier` | section | 赔付档位（agri_claim_processing） | agricultural > scenario > compensation-tier | 12: `raw-agri-0000`, `raw-agri-0001`, `raw-agri-0002`, `raw-agri-0003`, `raw-agri-0004`, `raw-agri-0005`, `raw-agri-0006`, `raw-agri-0007`, `raw-agri-0008`, `raw-agri-0009`, `raw-agri-0010`, `raw-agri-0011` |
| 12 | `claims-section-health-imaging-part` | section | 影像部位（health_risk_assessment） | health > scenario > imaging-part | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 13 | `claims-section-health-report-consistency` | section | 报告一致性（health_risk_assessment） | health > scenario > report-consistency | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 14 | `claims-section-health-risk-level` | section | 风险等级（health_risk_assessment） | health > scenario > risk-level | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 15 | `claims-section-health-underwriting-decision` | section | 核保决定（health_risk_assessment） | health > scenario > underwriting-decision | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 16 | `claims-section-liability-accident-occurrence` | section | 是否构成事故（auto_liability_determination） | auto > scenario > accident-occurrence | 12: `raw-liability-0000`, `raw-liability-0001`, `raw-liability-0003`, `raw-liability-0004`, `raw-liability-0006`, `raw-liability-0008`, `raw-liability-0010`, `raw-liability-0012`, `raw-liability-0016`, `raw-liability-0017`, `raw-liability-0019`, `raw-liability-0020` |
| 17 | `claims-section-liability-causation` | section | 事故成因与主责（auto_liability_determination） | auto > scenario > causation | 12: `raw-liability-0000`, `raw-liability-0001`, `raw-liability-0003`, `raw-liability-0004`, `raw-liability-0006`, `raw-liability-0008`, `raw-liability-0010`, `raw-liability-0012`, `raw-liability-0016`, `raw-liability-0017`, `raw-liability-0019`, `raw-liability-0020` |
| 18 | `claims-section-liability-scene-context` | section | 道路场景与路段形态（auto_liability_determination） | auto > scenario > scene-context | 12: `raw-liability-0000`, `raw-liability-0001`, `raw-liability-0003`, `raw-liability-0004`, `raw-liability-0006`, `raw-liability-0008`, `raw-liability-0010`, `raw-liability-0012`, `raw-liability-0016`, `raw-liability-0017`, `raw-liability-0019`, `raw-liability-0020` |
| 19 | `claims-section-liability-environment` | section | 天气与光照条件（auto_liability_determination） | auto > scenario > environment | 12: `raw-liability-0000`, `raw-liability-0001`, `raw-liability-0003`, `raw-liability-0004`, `raw-liability-0006`, `raw-liability-0008`, `raw-liability-0010`, `raw-liability-0012`, `raw-liability-0016`, `raw-liability-0017`, `raw-liability-0019`, `raw-liability-0020` |
| 20 | `claims-section-property-disaster-type` | section | 灾种识别（property_risk_management） | property > scenario > disaster-type | 6: `raw-property-0000`, `raw-property-0001`, `raw-property-0002`, `raw-property-0003`, `raw-property-0004`, `raw-property-0005` |
| 21 | `claims-section-property-damage-count` | section | 受灾与损失计数（property_risk_management） | property > scenario > damage-count | 6: `raw-property-0000`, `raw-property-0001`, `raw-property-0002`, `raw-property-0003`, `raw-property-0004`, `raw-property-0005` |
| 22 | `claims-section-property-claim-decision` | section | 理赔决定（property_risk_management） | property > scenario > claim-decision | 6: `raw-property-0000`, `raw-property-0001`, `raw-property-0002`, `raw-property-0003`, `raw-property-0004`, `raw-property-0005` |
| 23 | `claims-entity-coverage-limit` | entity | 保额与赔付上限 | 跨任务实体 | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 24 | `claims-entity-policy-expiry` | entity | 保单有效期 | 跨任务实体 | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 25 | `claims-entity-loss-severity` | entity | 损失严重程度 | 跨任务实体 | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 26 | `claims-entity-primary-responsibility` | entity | 事故主责判定 | 跨任务实体 | 12: `raw-liability-0000`, `raw-liability-0001`, `raw-liability-0003`, `raw-liability-0004`, `raw-liability-0006`, `raw-liability-0008`, `raw-liability-0010`, `raw-liability-0012`, `raw-liability-0016`, `raw-liability-0017`, `raw-liability-0019`, `raw-liability-0020` |
| 27 | `claims-entity-infection-status` | entity | 病害感染判定 | 跨任务实体 | 12: `raw-agri-0000`, `raw-agri-0001`, `raw-agri-0002`, `raw-agri-0003`, `raw-agri-0004`, `raw-agri-0005`, `raw-agri-0006`, `raw-agri-0007`, `raw-agri-0008`, `raw-agri-0009`, `raw-agri-0010`, `raw-agri-0011` |
| 28 | `claims-entity-compensation-tier` | entity | 赔付档位 | 跨任务实体 | 24: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011`, `raw-agri-0000`, `raw-agri-0001`, `raw-agri-0002`, `raw-agri-0003`, `raw-agri-0004`, `raw-agri-0005`, `raw-agri-0006`, `raw-agri-0007`, `raw-agri-0008`, `raw-agri-0009`, `raw-agri-0010`, `raw-agri-0011` |
| 29 | `claims-entity-report-consistency` | entity | 报告一致性 | 跨任务实体 | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 30 | `claims-entity-underwriting-decision` | entity | 核保决定 | 跨任务实体 | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 31 | `claims-entity-claim-decision` | entity | 理赔决定 | 跨任务实体 | 6: `raw-property-0000`, `raw-property-0001`, `raw-property-0002`, `raw-property-0003`, `raw-property-0004`, `raw-property-0005` |
| 32 | `claims-faq-claim` | faq | 车损理赔金额如何受保额与损失金额约束？ | auto > scenario > faq | 12: `raw-claim-0000`, `raw-claim-0001`, `raw-claim-0002`, `raw-claim-0003`, `raw-claim-0004`, `raw-claim-0005`, `raw-claim-0006`, `raw-claim-0007`, `raw-claim-0008`, `raw-claim-0009`, `raw-claim-0010`, `raw-claim-0011` |
| 33 | `claims-faq-agri` | faq | 农业保险赔付档位如何确定？ | agricultural > scenario > faq | 12: `raw-agri-0000`, `raw-agri-0001`, `raw-agri-0002`, `raw-agri-0003`, `raw-agri-0004`, `raw-agri-0005`, `raw-agri-0006`, `raw-agri-0007`, `raw-agri-0008`, `raw-agri-0009`, `raw-agri-0010`, `raw-agri-0011` |
| 34 | `claims-faq-health` | faq | 影像报告与核保决定如何对应？ | health > scenario > faq | 12: `raw-health-0000`, `raw-health-0001`, `raw-health-0002`, `raw-health-0003`, `raw-health-0004`, `raw-health-0005`, `raw-health-0006`, `raw-health-0007`, `raw-health-0008`, `raw-health-0009`, `raw-health-0010`, `raw-health-0011` |
| 35 | `claims-faq-liability` | faq | 如何判定事故是否发生以及主责归属？ | auto > scenario > faq | 12: `raw-liability-0000`, `raw-liability-0001`, `raw-liability-0003`, `raw-liability-0004`, `raw-liability-0006`, `raw-liability-0008`, `raw-liability-0010`, `raw-liability-0012`, `raw-liability-0016`, `raw-liability-0017`, `raw-liability-0019`, `raw-liability-0020` |
| 36 | `claims-faq-property` | faq | 财产险理赔决定如何判定？ | property > scenario > faq | 6: `raw-property-0000`, `raw-property-0001`, `raw-property-0002`, `raw-property-0003`, `raw-property-0004`, `raw-property-0005` |

### 4.1 单元 → 页面（D3 每编译一个单元要碰的页面）

按 `ingest_order` 列出；D3 编译第 N 个单元时，只允许写这个表里列出的页面（新增页面需先改 `plan.md` 的生成器并重跑）。

| # | raw_id | 本章元要写入的页面 |
|---|---|---|
| 1 | `raw-claim-0000` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 2 | `raw-claim-0001` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 3 | `raw-claim-0002` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 4 | `raw-claim-0003` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 5 | `raw-claim-0004` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 6 | `raw-claim-0005` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 7 | `raw-claim-0006` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 8 | `raw-claim-0007` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 9 | `raw-claim-0008` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 10 | `raw-claim-0009` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 11 | `raw-claim-0010` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 12 | `raw-claim-0011` | `claims-doc-ins-mmbench-auto`, `claims-section-claim-policy-validity`, `claims-section-claim-coverage-limits`, `claims-section-claim-loss-amount`, `claims-section-claim-vehicle-condition`, `claims-entity-coverage-limit`, `claims-entity-policy-expiry`, `claims-entity-loss-severity`, `claims-entity-compensation-tier`, `claims-faq-claim` |
| 13 | `raw-agri-0000` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 14 | `raw-agri-0001` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 15 | `raw-agri-0002` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 16 | `raw-agri-0003` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 17 | `raw-agri-0004` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 18 | `raw-agri-0005` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 19 | `raw-agri-0006` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 20 | `raw-agri-0007` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 21 | `raw-agri-0008` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 22 | `raw-agri-0009` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 23 | `raw-agri-0010` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 24 | `raw-agri-0011` | `claims-doc-ins-mmbench-agricultural`, `claims-section-agri-insured-subject`, `claims-section-agri-infection-status`, `claims-section-agri-compensation-tier`, `claims-entity-infection-status`, `claims-entity-compensation-tier`, `claims-faq-agri` |
| 25 | `raw-health-0000` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 26 | `raw-health-0001` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 27 | `raw-health-0002` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 28 | `raw-health-0003` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 29 | `raw-health-0004` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 30 | `raw-health-0005` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 31 | `raw-health-0006` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 32 | `raw-health-0007` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 33 | `raw-health-0008` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 34 | `raw-health-0009` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 35 | `raw-health-0010` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 36 | `raw-health-0011` | `claims-doc-ins-mmbench-health`, `claims-section-health-imaging-part`, `claims-section-health-report-consistency`, `claims-section-health-risk-level`, `claims-section-health-underwriting-decision`, `claims-entity-report-consistency`, `claims-entity-underwriting-decision`, `claims-faq-health` |
| 37 | `raw-liability-0000` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 38 | `raw-liability-0001` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 39 | `raw-liability-0003` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 40 | `raw-liability-0004` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 41 | `raw-liability-0006` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 42 | `raw-liability-0008` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 43 | `raw-liability-0010` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 44 | `raw-liability-0012` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 45 | `raw-liability-0016` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 46 | `raw-liability-0017` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 47 | `raw-liability-0019` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 48 | `raw-liability-0020` | `claims-doc-ins-mmbench-auto`, `claims-section-liability-accident-occurrence`, `claims-section-liability-causation`, `claims-section-liability-scene-context`, `claims-section-liability-environment`, `claims-entity-primary-responsibility`, `claims-faq-liability` |
| 49 | `raw-property-0000` | `claims-doc-ins-mmbench-property`, `claims-section-property-disaster-type`, `claims-section-property-damage-count`, `claims-section-property-claim-decision`, `claims-entity-claim-decision`, `claims-faq-property` |
| 50 | `raw-property-0001` | `claims-doc-ins-mmbench-property`, `claims-section-property-disaster-type`, `claims-section-property-damage-count`, `claims-section-property-claim-decision`, `claims-entity-claim-decision`, `claims-faq-property` |
| 51 | `raw-property-0002` | `claims-doc-ins-mmbench-property`, `claims-section-property-disaster-type`, `claims-section-property-damage-count`, `claims-section-property-claim-decision`, `claims-entity-claim-decision`, `claims-faq-property` |
| 52 | `raw-property-0003` | `claims-doc-ins-mmbench-property`, `claims-section-property-disaster-type`, `claims-section-property-damage-count`, `claims-section-property-claim-decision`, `claims-entity-claim-decision`, `claims-faq-property` |
| 53 | `raw-property-0004` | `claims-doc-ins-mmbench-property`, `claims-section-property-disaster-type`, `claims-section-property-damage-count`, `claims-section-property-claim-decision`, `claims-entity-claim-decision`, `claims-faq-property` |
| 54 | `raw-property-0005` | `claims-doc-ins-mmbench-property`, `claims-section-property-disaster-type`, `claims-section-property-damage-count`, `claims-section-property-claim-decision`, `claims-entity-claim-decision`, `claims-faq-property` |

每条 `section` 页的产出要求：正文断言逐条带 `⟦S:<raw_id>@<span>⟧`（span 写法见 §5），
frontmatter 九项必填（R1 spec §3.1），`source_refs` 不得超出上表列出的集合（超集即 lint L6 失败）。

## 5. 引用语法（本语料的两种 span）

| 证据类型 | 写法 | 说明 |
|---|---|---|
| 题干行 | `⟦S:raw-claim-0000@L3-L7⟧` | `content.question.text` 按 `\n` 切分的**行号**，1-based 含端点；每单元 13–17 行 |
| 标签字段 | `⟦S:raw-claim-0000@labels.Amount⟧` | `labels` 的 JSON 路径；值必须与源文件逐字一致 |
| 图片 | `⟦S:raw-claim-0000@claim/0/0.jpg⟧` | 用 `images[].path`；sha256 已在 manifest 固定 |

## 6. 覆盖自检（生成时自动计算）

| 检查 | 结果 |
|---|---|
| 每个 raw 单元至少被 1 个页面引用 | PASS |
| 被引用单元数 / 总单元数 | 54 / 54 |
| 引用总次数（含重复引用） | 420 |
| 覆盖保险类型数 | 4 / 4（agricultural, auto, health, property） |
| 覆盖任务数 | 5 |

## 7. D3 执行契约（照做即可，无需再判断）

1. **顺序**：严格按 `raw/manifest.json` 的 `ingest_order` 逐单元编译（与 §4 表序一致），**一次一个单元**。
2. **加锁**：`data/llm-wiki-claims/wiki/.ingest.lock`（写 `pid` + 开始时间），取不到锁则排队，禁止并发写。
3. **单事务**：读源 → 写/改页面 → 双向 `related` → 重建 `index.md` → 追加 `log.md` → lint → 释放锁。
4. **幂等**：`log.md` 已有 `ingest | <raw_id>` 的单元不得重编（R1 spec §8 第 4 步）。
5. **禁止**：写 `data/llm-wiki-claims/wiki/` 以外的知识路径；写 `renewal-assistant/wiki/`、`server/`、`traces/`；改写 `raw/`。
6. **无答案**：54 单元 `answer` 均为 null（场景分片本身无 answer 列），页面只写「样本给出的字段事实 + 题干规则」，
   **禁止**编造标准答案；D5 只评检索指标（台账 D-04）。

## 8. 已知限制

| # | 限制 | 影响 / 处置 |
|---|---|---|
| 1 | 图片未复制进 `raw/assets/`，只记 `asset_ref` + sha256 | 避免 33 MiB 重复；但 `data/ins-mmbench/**` 被 gitignore，**新 clone 无图片** |
| 2 | 本子集 `task_layer` 单一（全 scenario）、部分标签单一值（如 `Severity` 全 minor） | 不得据此算分类准确率；只评检索与引用接地 |
| 3 | liability 12 条非严格 head-k（index 0–20 间 12 条） | 偏差敏感分析须按 `source.source_index` 追溯（manifest 已留） |
| 4 | `property` 的 `claim_decision` 覆盖面 No/Partial/Full | 是否可作 GT 待 D2/D5 判定（台账 O-02）；本步不改写、不判定 |

