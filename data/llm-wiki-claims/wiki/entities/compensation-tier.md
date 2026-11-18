---
id: claims-entity-compensation-tier
type: entity
title: 赔付档位
domain: claims
insurance_line: cross_cutting
summary: claim 实体登记：24 个单元（跨 agri+claim 分片），逐属性可回溯。
tags: [ins-mmbench, claim, entity]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11, INS-MMBench:qid=agri_0, INS-MMBench:qid=agri_1, INS-MMBench:qid=agri_2, INS-MMBench:qid=agri_3, INS-MMBench:qid=agri_4, INS-MMBench:qid=agri_5, INS-MMBench:qid=agri_6, INS-MMBench:qid=agri_7, INS-MMBench:qid=agri_8, INS-MMBench:qid=agri_9, INS-MMBench:qid=agri_10, INS-MMBench:qid=agri_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011, raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto]
status: verified
---
# 赔付档位（实体页）

> 本页把「赔付档位」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

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

| qid | `claim` | 原文定位 |
|---|---|---|
| `claim_0` | 0.0 | ⟦S:INS-MMBench:qid=claim_0@labels.claim⟧ |
| `claim_1` | 0.0 | ⟦S:INS-MMBench:qid=claim_1@labels.claim⟧ |
| `claim_2` | 459.0 | ⟦S:INS-MMBench:qid=claim_2@labels.claim⟧ |
| `claim_3` | 826.0 | ⟦S:INS-MMBench:qid=claim_3@labels.claim⟧ |
| `claim_4` | 2426.0 | ⟦S:INS-MMBench:qid=claim_4@labels.claim⟧ |
| `claim_5` | 0.0 | ⟦S:INS-MMBench:qid=claim_5@labels.claim⟧ |
| `claim_6` | 0.0 | ⟦S:INS-MMBench:qid=claim_6@labels.claim⟧ |
| `claim_7` | 4048.0 | ⟦S:INS-MMBench:qid=claim_7@labels.claim⟧ |
| `claim_8` | 0.0 | ⟦S:INS-MMBench:qid=claim_8@labels.claim⟧ |
| `claim_9` | 3090.0 | ⟦S:INS-MMBench:qid=claim_9@labels.claim⟧ |
| `claim_10` | 305.0 | ⟦S:INS-MMBench:qid=claim_10@labels.claim⟧ |
| `claim_11` | 3607.0 | ⟦S:INS-MMBench:qid=claim_11@labels.claim⟧ |
| `agri_0` | Partial Compensation | ⟦S:INS-MMBench:qid=agri_0@labels.claim⟧ |
| `agri_1` | Partial Compensation | ⟦S:INS-MMBench:qid=agri_1@labels.claim⟧ |
| `agri_2` | No Compensation | ⟦S:INS-MMBench:qid=agri_2@labels.claim⟧ |
| `agri_3` | No Compensation | ⟦S:INS-MMBench:qid=agri_3@labels.claim⟧ |
| `agri_4` | No Compensation | ⟦S:INS-MMBench:qid=agri_4@labels.claim⟧ |
| `agri_5` | No Compensation | ⟦S:INS-MMBench:qid=agri_5@labels.claim⟧ |
| `agri_6` | No Compensation | ⟦S:INS-MMBench:qid=agri_6@labels.claim⟧ |
| `agri_7` | No Compensation | ⟦S:INS-MMBench:qid=agri_7@labels.claim⟧ |
| `agri_8` | No Compensation | ⟦S:INS-MMBench:qid=agri_8@labels.claim⟧ |
| `agri_9` | No Compensation | ⟦S:INS-MMBench:qid=agri_9@labels.claim⟧ |
| `agri_10` | No Compensation | ⟦S:INS-MMBench:qid=agri_10@labels.claim⟧ |
| `agri_11` | No Compensation | ⟦S:INS-MMBench:qid=agri_11@labels.claim⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- `agri` 分片（12 个单元）：claim=Partial Compensation×2/No Compensation×10⟦S:INS-MMBench:qids=agri_0..agri_11@labels.claim⟧
- `claim` 分片（12 个单元）：claim=0.0×5/459.0×1/826.0×1/2426.0×1/4048.0×1/3090.0×1/305.0×1/3607.0×1⟦S:INS-MMBench:qids=claim_0..claim_11@labels.claim⟧
- 【方法约束】同名不同义（机器标记可回溯、语义却不同）：`claim` 在 claim 分片为数值（如 0.0），在 agri 分片为枚举（如 Partial Compensation）；本页按分片分别登记，**不得合并统计**⟦S:INS-MMBench:qids=agri_0..agri_11@labels.claim⟧ ⟦S:INS-MMBench:qids=claim_0..claim_11@labels.claim⟧
- 属性个数：1（`claim`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=claim_0@labels.claim⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
