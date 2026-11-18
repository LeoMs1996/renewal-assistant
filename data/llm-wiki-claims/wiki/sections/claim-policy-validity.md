---
id: claims-section-claim-policy-validity
type: section
title: 保单有效期与失效（auto_claim_processing）
domain: claims
insurance_line: auto_claim
summary: Expiry_date/expired 在 12 条 claim 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, claim, section]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-entity-policy-expiry, claims-section-claim-coverage-limits, claims-section-claim-loss-amount, claims-section-claim-vehicle-condition]
status: verified
---
# 保单有效期与失效（auto_claim_processing）

> 本页只陈述本子集中 `Expiry_date`, `expired` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `claim_0`）

> You are an expert in auto insurance claim processing, here is an image of a vehicle and basic information: cost of vehicle is $44900.0, the expired date of insurance is 2021-11-12, the min and max coverage of the vehicle is $1122.5 and $11303.0. Based on the textual and visual information, please provide a step-by-step evaluation of the vehicle's condition and make an insurance claim decision. Follow these steps:  

⟦S:INS-MMBench:qid=claim_0@L1-L1⟧

> please strictly output in this format:
> 1. Yes/No 
> 2. Minor/Moderate/Severe  
> 3. Cost Amount 
> 4. Yes/No. Reason: <Reason>  
> 5. Final Claim Amount. Reason: <Reason>

⟦S:INS-MMBench:qid=claim_0@L9-L14⟧

## 2. 样本事实（逐行 span 级）

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

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：Expiry_date=2021-11-12×1/2022-04-05×1/2026-04-30×1/2028-07-28×1/2025-06-02×1/2023-10-04×1/2022-12-15×1/2028-08-22×1/2023-03-09×1/2025-04-17×1/2025-05-14×1/2025-09-24×1；expired=1×5/0×7（证据：§2 全 12 行）⟦S:INS-MMBench:qids=claim_0..claim_11@labels.Expiry_date⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-entity-policy-expiry]] `claims-entity-policy-expiry`
- [[claims-section-claim-coverage-limits]] `claims-section-claim-coverage-limits`
- [[claims-section-claim-loss-amount]] `claims-section-claim-loss-amount`
- [[claims-section-claim-vehicle-condition]] `claims-section-claim-vehicle-condition`
