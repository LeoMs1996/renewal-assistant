---
id: claims-faq-property
type: faq
title: 财产险理赔决定如何判定？
domain: claims
insurance_line: property_claim
summary: property 任务语料能支持到的回答范围（6 条样本，逐条引用）。
tags: [ins-mmbench, property, faq]
source_refs: [INS-MMBench:qid=property_0, INS-MMBench:qid=property_1, INS-MMBench:qid=property_2, INS-MMBench:qid=property_3, INS-MMBench:qid=property_4, INS-MMBench:qid=property_5]
raw_refs: [raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-property]
status: verified
---
# 财产险理赔决定如何判定？

> 本页只回答「本子集语料能支持到什么程度」：答案由样本字段与题干规约拼成，不是业务建议。

目录中的问题：给定灾前灾后卫星图像，灾种、受灾与损失计数、理赔决定如何判定？

## 1. 题干规约（逐字，取首单元 `property_0`）

> Please strictly output in this format:
> 1. Disaster Occurred: Yes/No
> 2. Disaster Type: <type>
> 3. House Count: <number>
> 4. Damaged House Count: <number>
> 5. Insurance Decision: <No Compensation/Partial Compensation/Full Compensation>. Reason: <Reason>

⟦S:INS-MMBench:qid=property_0@L9-L14⟧

## 2. 本子集能给出的答案（逐条引用）

| qid | `disaster` | `type` | `number` | `damage_number` | `claim_decision` | 原文定位 |
|---|---|---|---|---|---|---|
| `property_0` | yes | hurricane | 30 | 30 | Full compensation | ⟦S:INS-MMBench:qid=property_0@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_0@labels.type⟧ ⟦S:INS-MMBench:qid=property_0@labels.number⟧ ⟦S:INS-MMBench:qid=property_0@labels.damage_number⟧ ⟦S:INS-MMBench:qid=property_0@labels.claim_decision⟧ |
| `property_1` | yes | flooding | 3 | 0 | No compensation | ⟦S:INS-MMBench:qid=property_1@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_1@labels.type⟧ ⟦S:INS-MMBench:qid=property_1@labels.number⟧ ⟦S:INS-MMBench:qid=property_1@labels.damage_number⟧ ⟦S:INS-MMBench:qid=property_1@labels.claim_decision⟧ |
| `property_2` | yes | hurricane | 17 | 0 | No compensation | ⟦S:INS-MMBench:qid=property_2@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_2@labels.type⟧ ⟦S:INS-MMBench:qid=property_2@labels.number⟧ ⟦S:INS-MMBench:qid=property_2@labels.damage_number⟧ ⟦S:INS-MMBench:qid=property_2@labels.claim_decision⟧ |
| `property_3` | yes | wildfire | 37 | 1 | Partial compensation | ⟦S:INS-MMBench:qid=property_3@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_3@labels.type⟧ ⟦S:INS-MMBench:qid=property_3@labels.number⟧ ⟦S:INS-MMBench:qid=property_3@labels.damage_number⟧ ⟦S:INS-MMBench:qid=property_3@labels.claim_decision⟧ |
| `property_4` | yes | wildfire | 86 | 0 | No compensation | ⟦S:INS-MMBench:qid=property_4@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_4@labels.type⟧ ⟦S:INS-MMBench:qid=property_4@labels.number⟧ ⟦S:INS-MMBench:qid=property_4@labels.damage_number⟧ ⟦S:INS-MMBench:qid=property_4@labels.claim_decision⟧ |
| `property_5` | yes | hurricane | 243 | 0 | No compensation | ⟦S:INS-MMBench:qid=property_5@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_5@labels.type⟧ ⟦S:INS-MMBench:qid=property_5@labels.number⟧ ⟦S:INS-MMBench:qid=property_5@labels.damage_number⟧ ⟦S:INS-MMBench:qid=property_5@labels.claim_decision⟧ |

- 以本子集 6 条 property 样本为准，判断类字段 `claim_decision` 的取值分布为 Full compensation×1/No compensation×4/Partial compensation×1（证据：上表逐行）⟦S:INS-MMBench:qids=property_0..property_5@labels.claim_decision⟧
- 可用于回答的字段清单（与本页 `source_refs` 同集合）：`disaster`, `type`, `number`, `damage_number`, `claim_decision` ⟦S:INS-MMBench:qid=property_0@labels.disaster⟧ ⟦S:INS-MMBench:qid=property_0@labels.type⟧ ⟦S:INS-MMBench:qid=property_0@labels.number⟧ ⟦S:INS-MMBench:qid=property_0@labels.damage_number⟧ ⟦S:INS-MMBench:qid=property_0@labels.claim_decision⟧

## 3. 本页不回答什么

- 不给出条款级依据：本子集无条款文本，且 `answer` 列不存在（`answer_status=absent_in_source`）⟦S:INS-MMBench:qid=property_0@answer_status⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-property]] `claims-doc-ins-mmbench-property`
