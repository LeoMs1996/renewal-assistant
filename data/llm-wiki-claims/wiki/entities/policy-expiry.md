---
id: claims-entity-policy-expiry
type: entity
title: 保单有效期
domain: claims
insurance_line: auto_claim
summary: Expiry_date/expired 实体登记：12 个单元，逐属性可回溯。
tags: [ins-mmbench, claim, entity]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-section-claim-policy-validity]
status: verified
---
# 保单有效期（实体页）

> 本页把「保单有效期」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

## 1. 字段出处（逐字，取首单元 `claim_0`）

> You are an expert in auto insurance claim processing, here is an image of a vehicle and basic information: cost of vehicle is $44900.0, the expired date of insurance is 2021-11-12, the min and max coverage of the vehicle is $1122.5 and $11303.0. Based on the textual and visual information, please provide a step-by-step evaluation of the vehicle's condition and make an insurance claim decision. Follow these steps:  

⟦S:INS-MMBench:qid=claim_0@L1-L1⟧

> please strictly output in this format:
> 1. Yes/No 
> 2. Minor/Moderate/Severe  
> 3. Cost Amount 
> 4. Yes/No. Reason: <Reason>  
> 5. Final Claim Amount. Reason: <Reason>

⟦S:INS-MMBench:qid=claim_0@L9-L14⟧

## 2. 属性事实（逐单元、逐属性带标记）

| qid | `Expiry_date` | `expired` | 原文定位 |
|---|---|---|---|
| `claim_0` | 2021-11-12 | 1 | ⟦S:INS-MMBench:qid=claim_0@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_0@labels.expired⟧ |
| `claim_1` | 2022-04-05 | 1 | ⟦S:INS-MMBench:qid=claim_1@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_1@labels.expired⟧ |
| `claim_2` | 2026-04-30 | 0 | ⟦S:INS-MMBench:qid=claim_2@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_2@labels.expired⟧ |
| `claim_3` | 2028-07-28 | 0 | ⟦S:INS-MMBench:qid=claim_3@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_3@labels.expired⟧ |
| `claim_4` | 2025-06-02 | 0 | ⟦S:INS-MMBench:qid=claim_4@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_4@labels.expired⟧ |
| `claim_5` | 2023-10-04 | 1 | ⟦S:INS-MMBench:qid=claim_5@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_5@labels.expired⟧ |
| `claim_6` | 2022-12-15 | 1 | ⟦S:INS-MMBench:qid=claim_6@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_6@labels.expired⟧ |
| `claim_7` | 2028-08-22 | 0 | ⟦S:INS-MMBench:qid=claim_7@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_7@labels.expired⟧ |
| `claim_8` | 2023-03-09 | 1 | ⟦S:INS-MMBench:qid=claim_8@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_8@labels.expired⟧ |
| `claim_9` | 2025-04-17 | 0 | ⟦S:INS-MMBench:qid=claim_9@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_9@labels.expired⟧ |
| `claim_10` | 2025-05-14 | 0 | ⟦S:INS-MMBench:qid=claim_10@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_10@labels.expired⟧ |
| `claim_11` | 2025-09-24 | 0 | ⟦S:INS-MMBench:qid=claim_11@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_11@labels.expired⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 12 个单元（claim 分片），每个属性均可在 §2 对应单元格回溯；取值分布：Expiry_date=2021-11-12×1/2022-04-05×1/2026-04-30×1/2028-07-28×1/2025-06-02×1/2023-10-04×1/2022-12-15×1/2028-08-22×1/2023-03-09×1/2025-04-17×1/2025-05-14×1/2025-09-24×1；expired=1×5/0×7⟦S:INS-MMBench:qids=claim_0..claim_11@labels.Expiry_date⟧
- 属性个数：2（`Expiry_date`, `expired`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=claim_0@labels.Expiry_date⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-section-claim-policy-validity]] `claims-section-claim-policy-validity`
