# 理赔域 LLM-Wiki 索引（index.md）

> 脚本生成，勿手改。条目 36；类型见分组标题；末列「短标签」由页面元数据确定性生成（≤30 字，含区分维度与数量）。
> 分层只落在 `task_name`（54 条 `task_layer` 全为 `scenario`）。查询：本索引定位 id → 读条目 → 逐字核对回 raw。

## 文档页（4）

| id | 标题 | 短标签 | tags | updated |
|---|---|---|---|---|
| [`ins-mmbench-agricultural`](docs/ins-mmbench-agricultural.md) | INS-MMBench 子集：agricultural 保险样本总览 | agri · 12 条样本 · 4 字段 | agri | 2026-11-18 |
| [`ins-mmbench-auto`](docs/ins-mmbench-auto.md) | INS-MMBench 子集：auto 保险样本总览 | claim+liability · 24 条 · 16 字段 | claim | 2026-11-18 |
| [`ins-mmbench-health`](docs/ins-mmbench-health.md) | INS-MMBench 子集：health 保险样本总览 | health · 12 条样本 · 6 字段 | health | 2026-11-18 |
| [`ins-mmbench-property`](docs/ins-mmbench-property.md) | INS-MMBench 子集：property 保险样本总览 | property · 6 条样本 · 5 字段 | property | 2026-11-18 |

## 章节页（18）

| id | 标题 | 短标签 | tags | updated |
|---|---|---|---|---|
| [`claim-policy-validity`](sections/claim-policy-validity.md) | 保单有效期与失效 | claim · Expiry_date · 12 单元 | claim | 2026-11-18 |
| [`claim-coverage-limits`](sections/claim-coverage-limits.md) | 保额上下限 | claim · Min_coverage · 12 单元 | claim | 2026-11-18 |
| [`claim-loss-amount`](sections/claim-loss-amount.md) | 损失金额与严重程度 | claim · Amount · 12 单元 | claim | 2026-11-18 |
| [`claim-vehicle-condition`](sections/claim-vehicle-condition.md) | 车辆条件与车值 | claim · Condition · 12 单元 | claim | 2026-11-18 |
| [`agri-insured-subject`](sections/agri-insured-subject.md) | 标的物种与数量 | agri · species/count · 12 单元 | agri | 2026-11-18 |
| [`agri-infection-status`](sections/agri-infection-status.md) | 病害感染判定 | agri · infection · 12 单元 | agri | 2026-11-18 |
| [`agri-compensation-tier`](sections/agri-compensation-tier.md) | 赔付档位 | agri · claim · 12 单元 | agri | 2026-11-18 |
| [`health-imaging-part`](sections/health-imaging-part.md) | 影像部位 | health · part · 12 单元 | health | 2026-11-18 |
| [`health-report-consistency`](sections/health-report-consistency.md) | 报告一致性 | health · 12 单元 | health | 2026-11-18 |
| [`health-risk-level`](sections/health-risk-level.md) | 风险等级 | health · risk_level · 12 单元 | health | 2026-11-18 |
| [`health-underwriting-decision`](sections/health-underwriting-decision.md) | 核保决定 | health · 12 单元 | health | 2026-11-18 |
| [`liability-accident-occurrence`](sections/liability-accident-occurrence.md) | 是否构成事故 | liability · 12 单元 | liability | 2026-11-18 |
| [`liability-causation`](sections/liability-causation.md) | 事故成因与主责 | liability · causes · 12 单元 | liability | 2026-11-18 |
| [`liability-scene-context`](sections/liability-scene-context.md) | 道路场景与路段形态 | liability · scenes · 12 单元 | liability | 2026-11-18 |
| [`liability-environment`](sections/liability-environment.md) | 天气与光照条件 | liability · weather · 12 单元 | liability | 2026-11-18 |
| [`property-disaster-type`](sections/property-disaster-type.md) | 灾种识别 | property · disaster · 6 单元 | property | 2026-11-18 |
| [`property-damage-count`](sections/property-damage-count.md) | 受灾与损失计数 | property · number · 6 单元 | property | 2026-11-18 |
| [`property-claim-decision`](sections/property-claim-decision.md) | 理赔决定 | property · 6 单元 | property | 2026-11-18 |

## 实体页（9）

| id | 标题 | 短标签 | tags | updated |
|---|---|---|---|---|
| [`coverage-limit`](entities/coverage-limit.md) | 保额与赔付上限 | 保额与赔付上限 · 12 种：1122.5/715.0 | claim | 2026-11-18 |
| [`policy-expiry`](entities/policy-expiry.md) | 保单有效期 | 保单有效期 · Expiry_date · 12 种取值 | claim | 2026-11-18 |
| [`loss-severity`](entities/loss-severity.md) | 损失严重程度 | 损失严重程度 · Amount · 12 种取值 | claim | 2026-11-18 |
| [`primary-responsibility`](entities/primary-responsibility.md) | 事故主责判定 | 事故主责判定 · 3 种：Both/Ego-car | liability | 2026-11-18 |
| [`infection-status`](entities/infection-status.md) | 病害感染判定 | 病害感染判定 · infection · 2 种取值 | agri | 2026-11-18 |
| [`compensation-tier`](entities/compensation-tier.md) | 赔付档位 | 赔付档位 · claim · 10 种取值 | claim | 2026-11-18 |
| [`report-consistency`](entities/report-consistency.md) | 报告一致性 | 报告一致性 · match · 1 种取值 | health | 2026-11-18 |
| [`underwriting-decision`](entities/underwriting-decision.md) | 核保决定 | 核保决定 · 3 种：Declined/Standard | health | 2026-11-18 |
| [`claim-decision`](entities/claim-decision.md) | 理赔决定 | 理赔决定 · claim_decision · 3 种取值 | property | 2026-11-18 |

## 问答页（5）

| id | 标题 | 短标签 | tags | updated |
|---|---|---|---|---|
| [`claim`](faqs/claim.md) | 车损理赔金额如何受保额与损失金额约束？ | claim · 判断档位 · 8 种取值 | claim | 2026-11-18 |
| [`agri`](faqs/agri.md) | 农业保险赔付档位如何确定？ | agri · claim · 2 种取值 | agri | 2026-11-18 |
| [`health`](faqs/health.md) | 影像报告与核保决定如何对应？ | health · 3 种取值 | health | 2026-11-18 |
| [`liability`](faqs/liability.md) | 如何判定事故是否发生以及主责归属？ | liability · 3 种取值 | liability | 2026-11-18 |
| [`property`](faqs/property.md) | 财产险理赔决定如何判定？ | property · 3 种取值 | property | 2026-11-18 |

