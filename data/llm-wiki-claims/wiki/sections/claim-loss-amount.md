---
id: claims-section-claim-loss-amount
type: section
title: 损失金额与严重程度（auto_claim_processing）
domain: claims
insurance_line: auto_claim
summary: Amount/Severity 在 12 条 claim 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, claim, section]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-entity-loss-severity, claims-section-claim-coverage-limits, claims-section-claim-policy-validity, claims-section-claim-vehicle-condition]
status: verified
---
# 损失金额与严重程度（auto_claim_processing）

> 本页只陈述本子集中 `Amount`, `Severity` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `claim_0`）

> 5. If eligible for a claim, calculate the final claimable amount, with a short and brief explanation.  

⟦S:INS-MMBench:qid=claim_0@L7-L7⟧

> 2. If damaged, assess the severity of the damage (Minor, Moderate, Severe). 

⟦S:INS-MMBench:qid=claim_0@L4-L4⟧

> please strictly output in this format:
> 1. Yes/No 
> 2. Minor/Moderate/Severe  
> 3. Cost Amount 
> 4. Yes/No. Reason: <Reason>  
> 5. Final Claim Amount. Reason: <Reason>

⟦S:INS-MMBench:qid=claim_0@L9-L14⟧

## 2. 样本事实（逐行 span 级）

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

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：Amount=4043.0×1/2452.0×1/459.0×1/826.0×1/2426.0×1/1000.0×1/626.0×1/4048.0×1/487.0×1/3090.0×1/305.0×1/3607.0×1；Severity=minor×12（证据：§2 全 12 行）⟦S:INS-MMBench:qids=claim_0..claim_11@labels.Amount⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-entity-loss-severity]] `claims-entity-loss-severity`
- [[claims-section-claim-coverage-limits]] `claims-section-claim-coverage-limits`
- [[claims-section-claim-policy-validity]] `claims-section-claim-policy-validity`
- [[claims-section-claim-vehicle-condition]] `claims-section-claim-vehicle-condition`
