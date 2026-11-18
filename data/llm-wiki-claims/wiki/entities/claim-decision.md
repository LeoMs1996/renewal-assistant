---
id: claims-entity-claim-decision
type: entity
title: 理赔决定
domain: claims
insurance_line: property_claim
summary: claim_decision 实体登记：6 个单元，逐属性可回溯。
tags: [ins-mmbench, property, entity]
source_refs: [INS-MMBench:qid=property_0, INS-MMBench:qid=property_1, INS-MMBench:qid=property_2, INS-MMBench:qid=property_3, INS-MMBench:qid=property_4, INS-MMBench:qid=property_5]
raw_refs: [raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-property, claims-section-property-claim-decision]
status: verified
---
# 理赔决定（实体页）

> 本页把「理赔决定」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

## 1. 字段出处（逐字，取首单元 `property_0`）

> You are an expert in property insurance assessment. Here are two satellite images of the same area. Based on the visual information provided by the images, please perform a step-by-step evaluation of the property damage and make an insurance claim decision.

⟦S:INS-MMBench:qid=property_0@L1-L1⟧

> Please strictly output in this format:
> 1. Disaster Occurred: Yes/No
> 2. Disaster Type: <type>
> 3. House Count: <number>
> 4. Damaged House Count: <number>
> 5. Insurance Decision: <No Compensation/Partial Compensation/Full Compensation>. Reason: <Reason>

⟦S:INS-MMBench:qid=property_0@L9-L14⟧

## 2. 属性事实（逐单元、逐属性带标记）

| qid | `claim_decision` | 原文定位 |
|---|---|---|
| `property_0` | Full compensation | ⟦S:INS-MMBench:qid=property_0@labels.claim_decision⟧ |
| `property_1` | No compensation | ⟦S:INS-MMBench:qid=property_1@labels.claim_decision⟧ |
| `property_2` | No compensation | ⟦S:INS-MMBench:qid=property_2@labels.claim_decision⟧ |
| `property_3` | Partial compensation | ⟦S:INS-MMBench:qid=property_3@labels.claim_decision⟧ |
| `property_4` | No compensation | ⟦S:INS-MMBench:qid=property_4@labels.claim_decision⟧ |
| `property_5` | No compensation | ⟦S:INS-MMBench:qid=property_5@labels.claim_decision⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 6 个单元（property 分片），每个属性均可在 §2 对应单元格回溯；取值分布：claim_decision=Full compensation×1/No compensation×4/Partial compensation×1⟦S:INS-MMBench:qids=property_0..property_5@labels.claim_decision⟧
- 属性个数：1（`claim_decision`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=property_0@labels.claim_decision⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-property]] `claims-doc-ins-mmbench-property`
- [[claims-section-property-claim-decision]] `claims-section-property-claim-decision`
