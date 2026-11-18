---
id: claims-section-claim-coverage-limits
type: section
title: 保额上下限（auto_claim_processing）
domain: claims
insurance_line: auto_claim
summary: Min_coverage/Max_coverage 在 12 条 claim 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, claim, section]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-entity-coverage-limit, claims-section-claim-loss-amount, claims-section-claim-policy-validity, claims-section-claim-vehicle-condition]
status: verified
---
# 保额上下限（auto_claim_processing）

> 本页只陈述本子集中 `Min_coverage`, `Max_coverage` 的 12 条样本事实与题干规约，不引入外部条款知识。

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

| qid | `Min_coverage` | `Max_coverage` | 原文定位 |
|---|---|---|---|
| `claim_0` | 1122.5 | 11303.0 | ⟦S:INS-MMBench:qid=claim_0@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Max_coverage⟧ |
| `claim_1` | 715.0 | 7228.0 | ⟦S:INS-MMBench:qid=claim_1@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Max_coverage⟧ |
| `claim_2` | 817.5 | 8253.0 | ⟦S:INS-MMBench:qid=claim_2@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Max_coverage⟧ |
| `claim_3` | 1145.0 | 11528.0 | ⟦S:INS-MMBench:qid=claim_3@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Max_coverage⟧ |
| `claim_4` | 822.5 | 8303.0 | ⟦S:INS-MMBench:qid=claim_4@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Max_coverage⟧ |
| `claim_5` | 957.5 | 9653.0 | ⟦S:INS-MMBench:qid=claim_5@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Max_coverage⟧ |
| `claim_6` | 735.0 | 7428.0 | ⟦S:INS-MMBench:qid=claim_6@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Max_coverage⟧ |
| `claim_7` | 1182.5 | 11903.0 | ⟦S:INS-MMBench:qid=claim_7@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Max_coverage⟧ |
| `claim_8` | 787.5 | 7953.0 | ⟦S:INS-MMBench:qid=claim_8@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Max_coverage⟧ |
| `claim_9` | 1085.0 | 10928.0 | ⟦S:INS-MMBench:qid=claim_9@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Max_coverage⟧ |
| `claim_10` | 1045.0 | 10528.0 | ⟦S:INS-MMBench:qid=claim_10@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Max_coverage⟧ |
| `claim_11` | 942.5 | 9503.0 | ⟦S:INS-MMBench:qid=claim_11@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Max_coverage⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：Min_coverage=1122.5×1/715.0×1/817.5×1/1145.0×1/822.5×1/957.5×1/735.0×1/1182.5×1/787.5×1/1085.0×1/1045.0×1/942.5×1；Max_coverage=11303.0×1/7228.0×1/8253.0×1/11528.0×1/8303.0×1/9653.0×1/7428.0×1/11903.0×1/7953.0×1/10928.0×1/10528.0×1/9503.0×1（证据：§2 全 12 行）⟦S:INS-MMBench:qids=claim_0..claim_11@labels.Min_coverage⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-entity-coverage-limit]] `claims-entity-coverage-limit`
- [[claims-section-claim-loss-amount]] `claims-section-claim-loss-amount`
- [[claims-section-claim-policy-validity]] `claims-section-claim-policy-validity`
- [[claims-section-claim-vehicle-condition]] `claims-section-claim-vehicle-condition`
