---
id: claims-section-property-claim-decision
type: section
title: 理赔决定（property_risk_management）
domain: claims
insurance_line: property_claim
summary: claim_decision 在 6 条 property 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, property, section]
source_refs: [INS-MMBench:qid=property_0, INS-MMBench:qid=property_1, INS-MMBench:qid=property_2, INS-MMBench:qid=property_3, INS-MMBench:qid=property_4, INS-MMBench:qid=property_5]
raw_refs: [raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-property, claims-entity-claim-decision, claims-section-property-damage-count, claims-section-property-disaster-type]
status: verified
---
# 理赔决定（property_risk_management）

> 本页只陈述本子集中 `claim_decision` 的 6 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `property_0`）

> You are an expert in property insurance assessment. Here are two satellite images of the same area. Based on the visual information provided by the images, please perform a step-by-step evaluation of the property damage and make an insurance claim decision.

⟦S:INS-MMBench:qid=property_0@L1-L1⟧

> Please strictly output in this format:
> 1. Disaster Occurred: Yes/No
> 2. Disaster Type: <type>
> 3. House Count: <number>
> 4. Damaged House Count: <number>
> 5. Insurance Decision: <No Compensation/Partial Compensation/Full Compensation>. Reason: <Reason>

⟦S:INS-MMBench:qid=property_0@L9-L14⟧

## 2. 样本事实（逐行 span 级）

| qid | `claim_decision` | 原文定位 |
|---|---|---|
| `property_0` | Full compensation | ⟦S:INS-MMBench:qid=property_0@labels.claim_decision⟧ |
| `property_1` | No compensation | ⟦S:INS-MMBench:qid=property_1@labels.claim_decision⟧ |
| `property_2` | No compensation | ⟦S:INS-MMBench:qid=property_2@labels.claim_decision⟧ |
| `property_3` | Partial compensation | ⟦S:INS-MMBench:qid=property_3@labels.claim_decision⟧ |
| `property_4` | No compensation | ⟦S:INS-MMBench:qid=property_4@labels.claim_decision⟧ |
| `property_5` | No compensation | ⟦S:INS-MMBench:qid=property_5@labels.claim_decision⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 6/6 条样本均具备上述字段；取值分布：claim_decision=Full compensation×1/No compensation×4/Partial compensation×1（证据：§2 全 6 行）⟦S:INS-MMBench:qids=property_0..property_5@labels.claim_decision⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-property]] `claims-doc-ins-mmbench-property`
- [[claims-entity-claim-decision]] `claims-entity-claim-decision`
- [[claims-section-property-damage-count]] `claims-section-property-damage-count`
- [[claims-section-property-disaster-type]] `claims-section-property-disaster-type`
