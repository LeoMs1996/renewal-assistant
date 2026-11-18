---
id: claims-section-claim-vehicle-condition
type: section
title: 车辆条件与车值（auto_claim_processing）
domain: claims
insurance_line: auto_claim
summary: Condition/Cost_of_vehicle 在 12 条 claim 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, claim, section]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-section-claim-coverage-limits, claims-section-claim-loss-amount, claims-section-claim-policy-validity]
status: verified
---
# 车辆条件与车值（auto_claim_processing）

> 本页只陈述本子集中 `Condition`, `Cost_of_vehicle` 的 12 条样本事实与题干规约，不引入外部条款知识。

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

| qid | `Condition` | `Cost_of_vehicle` | 原文定位 |
|---|---|---|---|
| `claim_0` | 1 | 44900.0 | ⟦S:INS-MMBench:qid=claim_0@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Cost_of_vehicle⟧ |
| `claim_1` | 1 | 28600.0 | ⟦S:INS-MMBench:qid=claim_1@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Cost_of_vehicle⟧ |
| `claim_2` | 1 | 32700.0 | ⟦S:INS-MMBench:qid=claim_2@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Cost_of_vehicle⟧ |
| `claim_3` | 1 | 45800.0 | ⟦S:INS-MMBench:qid=claim_3@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Cost_of_vehicle⟧ |
| `claim_4` | 1 | 32900.0 | ⟦S:INS-MMBench:qid=claim_4@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Cost_of_vehicle⟧ |
| `claim_5` | 1 | 38300.0 | ⟦S:INS-MMBench:qid=claim_5@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Cost_of_vehicle⟧ |
| `claim_6` | 1 | 29400.0 | ⟦S:INS-MMBench:qid=claim_6@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Cost_of_vehicle⟧ |
| `claim_7` | 1 | 47300.0 | ⟦S:INS-MMBench:qid=claim_7@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Cost_of_vehicle⟧ |
| `claim_8` | 1 | 31500.0 | ⟦S:INS-MMBench:qid=claim_8@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Cost_of_vehicle⟧ |
| `claim_9` | 1 | 43400.0 | ⟦S:INS-MMBench:qid=claim_9@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Cost_of_vehicle⟧ |
| `claim_10` | 1 | 41800.0 | ⟦S:INS-MMBench:qid=claim_10@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Cost_of_vehicle⟧ |
| `claim_11` | 1 | 37700.0 | ⟦S:INS-MMBench:qid=claim_11@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Cost_of_vehicle⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：Condition=1×12；Cost_of_vehicle=44900.0×1/28600.0×1/32700.0×1/45800.0×1/32900.0×1/38300.0×1/29400.0×1/47300.0×1/31500.0×1/43400.0×1/41800.0×1/37700.0×1（证据：§2 全 12 行）⟦S:INS-MMBench:qids=claim_0..claim_11@labels.Condition⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-section-claim-coverage-limits]] `claims-section-claim-coverage-limits`
- [[claims-section-claim-loss-amount]] `claims-section-claim-loss-amount`
- [[claims-section-claim-policy-validity]] `claims-section-claim-policy-validity`
