---
id: claims-entity-loss-severity
type: entity
title: 损失严重程度
domain: claims
insurance_line: auto_claim
summary: Amount/Severity 实体登记：12 个单元，逐属性可回溯。
tags: [ins-mmbench, claim, entity]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-section-claim-loss-amount]
status: verified
---
# 损失严重程度（实体页）

> 本页把「损失严重程度」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

## 1. 字段出处（逐字，取首单元 `claim_0`）

> 2. If damaged, assess the severity of the damage (Minor, Moderate, Severe). 

⟦S:INS-MMBench:qid=claim_0@L4-L4⟧

> please strictly output in this format:
> 1. Yes/No 
> 2. Minor/Moderate/Severe  
> 3. Cost Amount 
> 4. Yes/No. Reason: <Reason>  
> 5. Final Claim Amount. Reason: <Reason>

⟦S:INS-MMBench:qid=claim_0@L9-L14⟧

## 2. 属性事实（逐单元、逐属性带标记）

| qid | `Amount` | `Severity` | 原文定位 |
|---|---|---|---|
| `claim_0` | 4043.0 | minor | ⟦S:INS-MMBench:qid=claim_0@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Severity⟧ |
| `claim_1` | 2452.0 | minor | ⟦S:INS-MMBench:qid=claim_1@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Severity⟧ |
| `claim_2` | 459.0 | minor | ⟦S:INS-MMBench:qid=claim_2@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Severity⟧ |
| `claim_3` | 826.0 | minor | ⟦S:INS-MMBench:qid=claim_3@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Severity⟧ |
| `claim_4` | 2426.0 | minor | ⟦S:INS-MMBench:qid=claim_4@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Severity⟧ |
| `claim_5` | 1000.0 | minor | ⟦S:INS-MMBench:qid=claim_5@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Severity⟧ |
| `claim_6` | 626.0 | minor | ⟦S:INS-MMBench:qid=claim_6@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Severity⟧ |
| `claim_7` | 4048.0 | minor | ⟦S:INS-MMBench:qid=claim_7@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Severity⟧ |
| `claim_8` | 487.0 | minor | ⟦S:INS-MMBench:qid=claim_8@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Severity⟧ |
| `claim_9` | 3090.0 | minor | ⟦S:INS-MMBench:qid=claim_9@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Severity⟧ |
| `claim_10` | 305.0 | minor | ⟦S:INS-MMBench:qid=claim_10@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Severity⟧ |
| `claim_11` | 3607.0 | minor | ⟦S:INS-MMBench:qid=claim_11@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Severity⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 12 个单元（claim 分片），每个属性均可在 §2 对应单元格回溯；取值分布：Amount=4043.0×1/2452.0×1/459.0×1/826.0×1/2426.0×1/1000.0×1/626.0×1/4048.0×1/487.0×1/3090.0×1/305.0×1/3607.0×1；Severity=minor×12⟦S:INS-MMBench:qids=claim_0..claim_11@labels.Amount⟧
- 属性个数：2（`Amount`, `Severity`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=claim_0@labels.Amount⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-section-claim-loss-amount]] `claims-section-claim-loss-amount`
