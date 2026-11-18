---
id: claims-entity-coverage-limit
type: entity
title: 保额与赔付上限
domain: claims
insurance_line: auto_claim
summary: Min_coverage/Max_coverage 实体登记：12 个单元，逐属性可回溯。
tags: [ins-mmbench, claim, entity]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-section-claim-coverage-limits]
status: verified
---
# 保额与赔付上限（实体页）

> 本页把「保额与赔付上限」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

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

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 12 个单元（claim 分片），每个属性均可在 §2 对应单元格回溯；取值分布：Min_coverage=1122.5×1/715.0×1/817.5×1/1145.0×1/822.5×1/957.5×1/735.0×1/1182.5×1/787.5×1/1085.0×1/1045.0×1/942.5×1；Max_coverage=11303.0×1/7228.0×1/8253.0×1/11528.0×1/8303.0×1/9653.0×1/7428.0×1/11903.0×1/7953.0×1/10928.0×1/10528.0×1/9503.0×1⟦S:INS-MMBench:qids=claim_0..claim_11@labels.Min_coverage⟧
- 属性个数：2（`Min_coverage`, `Max_coverage`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=claim_0@labels.Min_coverage⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-section-claim-coverage-limits]] `claims-section-claim-coverage-limits`
