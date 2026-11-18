---
id: claims-section-property-disaster-type
type: section
title: 灾种识别（property_risk_management）
domain: claims
insurance_line: property_claim
summary: disaster/type 在 6 条 property 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, property, section]
source_refs: [INS-MMBench:qid=property_0, INS-MMBench:qid=property_1, INS-MMBench:qid=property_2, INS-MMBench:qid=property_3, INS-MMBench:qid=property_4, INS-MMBench:qid=property_5]
raw_refs: [raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-property, claims-section-property-claim-decision, claims-section-property-damage-count]
status: verified
---
# 灾种识别（property_risk_management）

> 本页只陈述本子集中 `disaster`, `type` 的 6 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `property_0`）

> 1. Determine whether a disaster occurred: Analyze the before and after images to decide if a disaster has taken place (Yes/No).

⟦S:INS-MMBench:qid=property_0@L3-L3⟧

> 2. Identify the disaster type: If a disaster is detected, specify the type (e.g., flood, earthquake, hurricane, fire, tsunami, volcano etc.).

⟦S:INS-MMBench:qid=property_0@L4-L4⟧

> Please strictly output in this format:
> 1. Disaster Occurred: Yes/No
> 2. Disaster Type: <type>
> 3. House Count: <number>
> 4. Damaged House Count: <number>
> 5. Insurance Decision: <No Compensation/Partial Compensation/Full Compensation>. Reason: <Reason>

⟦S:INS-MMBench:qid=property_0@L9-L14⟧

## 2. 样本事实（逐行 span 级）

| qid | `disaster` | `type` | 原文定位 |
|---|---|---|---|
| `property_0` | yes | hurricane | ⟦S:INS-MMBench:qid=property_0@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_0@labels.type⟧ |
| `property_1` | yes | flooding | ⟦S:INS-MMBench:qid=property_1@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_1@labels.type⟧ |
| `property_2` | yes | hurricane | ⟦S:INS-MMBench:qid=property_2@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_2@labels.type⟧ |
| `property_3` | yes | wildfire | ⟦S:INS-MMBench:qid=property_3@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_3@labels.type⟧ |
| `property_4` | yes | wildfire | ⟦S:INS-MMBench:qid=property_4@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_4@labels.type⟧ |
| `property_5` | yes | hurricane | ⟦S:INS-MMBench:qid=property_5@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_5@labels.type⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 6/6 条样本均具备上述字段；取值分布：disaster=yes×6；type=hurricane×3/flooding×1/wildfire×2（证据：§2 全 6 行）⟦S:INS-MMBench:qids=property_0..property_5@labels.disaster⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-property]] `claims-doc-ins-mmbench-property`
- [[claims-section-property-claim-decision]] `claims-section-property-claim-decision`
- [[claims-section-property-damage-count]] `claims-section-property-damage-count`
