---
id: claims-section-property-damage-count
type: section
title: 受灾与损失计数（property_risk_management）
domain: claims
insurance_line: property_claim
summary: number/damage_number 在 6 条 property 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, property, section]
source_refs: [INS-MMBench:qid=property_0, INS-MMBench:qid=property_1, INS-MMBench:qid=property_2, INS-MMBench:qid=property_3, INS-MMBench:qid=property_4, INS-MMBench:qid=property_5]
raw_refs: [raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-property, claims-section-property-claim-decision, claims-section-property-disaster-type]
status: verified
---
# 受灾与损失计数（property_risk_management）

> 本页只陈述本子集中 `number`, `damage_number` 的 6 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `property_0`）

> 3. Count the number of houses: Based on the satellite images, provide an concrete count of the houses.

⟦S:INS-MMBench:qid=property_0@L5-L5⟧

> Please strictly output in this format:
> 1. Disaster Occurred: Yes/No
> 2. Disaster Type: <type>
> 3. House Count: <number>
> 4. Damaged House Count: <number>
> 5. Insurance Decision: <No Compensation/Partial Compensation/Full Compensation>. Reason: <Reason>

⟦S:INS-MMBench:qid=property_0@L9-L14⟧

## 2. 样本事实（逐行 span 级）

| qid | `number` | `damage_number` | 原文定位 |
|---|---|---|---|
| `property_0` | 30 | 30 | ⟦S:INS-MMBench:qid=property_0@labels.number⟧ ⟦S:INS-MMBench:qid=property_0@labels.damage_number⟧ |
| `property_1` | 3 | 0 | ⟦S:INS-MMBench:qid=property_1@labels.number⟧ ⟦S:INS-MMBench:qid=property_1@labels.damage_number⟧ |
| `property_2` | 17 | 0 | ⟦S:INS-MMBench:qid=property_2@labels.number⟧ ⟦S:INS-MMBench:qid=property_2@labels.damage_number⟧ |
| `property_3` | 37 | 1 | ⟦S:INS-MMBench:qid=property_3@labels.number⟧ ⟦S:INS-MMBench:qid=property_3@labels.damage_number⟧ |
| `property_4` | 86 | 0 | ⟦S:INS-MMBench:qid=property_4@labels.number⟧ ⟦S:INS-MMBench:qid=property_4@labels.damage_number⟧ |
| `property_5` | 243 | 0 | ⟦S:INS-MMBench:qid=property_5@labels.number⟧ ⟦S:INS-MMBench:qid=property_5@labels.damage_number⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 6/6 条样本均具备上述字段；取值分布：number=30×1/3×1/17×1/37×1/86×1/243×1；damage_number=30×1/0×4/1×1（证据：§2 全 6 行）⟦S:INS-MMBench:qids=property_0..property_5@labels.number⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-property]] `claims-doc-ins-mmbench-property`
- [[claims-section-property-claim-decision]] `claims-section-property-claim-decision`
- [[claims-section-property-disaster-type]] `claims-section-property-disaster-type`
