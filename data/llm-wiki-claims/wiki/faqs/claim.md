---
id: claims-faq-claim
type: faq
title: 车损理赔金额如何受保额与损失金额约束？
domain: claims
insurance_line: auto_claim
summary: claim 任务语料能支持到的回答范围（12 条样本，逐条引用）。
tags: [ins-mmbench, claim, faq]
source_refs: [INS-MMBench:qid=claim_0, INS-MMBench:qid=claim_1, INS-MMBench:qid=claim_2, INS-MMBench:qid=claim_3, INS-MMBench:qid=claim_4, INS-MMBench:qid=claim_5, INS-MMBench:qid=claim_6, INS-MMBench:qid=claim_7, INS-MMBench:qid=claim_8, INS-MMBench:qid=claim_9, INS-MMBench:qid=claim_10, INS-MMBench:qid=claim_11]
raw_refs: [raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto]
status: verified
---
# 车损理赔金额如何受保额与损失金额约束？

> 本页只回答「本子集语料能支持到什么程度」：答案由样本字段与题干规约拼成，不是业务建议。

目录中的问题：给定车辆价值、保单保额上下限与损失金额，理赔金额与严重程度如何对应？

## 1. 题干规约（逐字，取首单元 `claim_0`）

> please strictly output in this format:
> 1. Yes/No 
> 2. Minor/Moderate/Severe  
> 3. Cost Amount 
> 4. Yes/No. Reason: <Reason>  
> 5. Final Claim Amount. Reason: <Reason>

⟦S:INS-MMBench:qid=claim_0@L9-L14⟧

## 2. 本子集能给出的答案（逐条引用）

| qid | `Cost_of_vehicle` | `Min_coverage` | `Expiry_date` | `Max_coverage` | `Condition` | `Amount` | `Severity` | `expired` | `claim` | 原文定位 |
|---|---|---|---|---|---|---|---|---|---|---|
| `claim_0` | 44900.0 | 1122.5 | 2021-11-12 | 11303.0 | 1 | 4043.0 | minor | 1 | 0.0 | ⟦S:INS-MMBench:qid=claim_0@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_0@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_0@labels.claim⟧ |
| `claim_1` | 28600.0 | 715.0 | 2022-04-05 | 7228.0 | 1 | 2452.0 | minor | 1 | 0.0 | ⟦S:INS-MMBench:qid=claim_1@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_1@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_1@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_1@labels.claim⟧ |
| `claim_2` | 32700.0 | 817.5 | 2026-04-30 | 8253.0 | 1 | 459.0 | minor | 0 | 459.0 | ⟦S:INS-MMBench:qid=claim_2@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_2@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_2@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_2@labels.claim⟧ |
| `claim_3` | 45800.0 | 1145.0 | 2028-07-28 | 11528.0 | 1 | 826.0 | minor | 0 | 826.0 | ⟦S:INS-MMBench:qid=claim_3@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_3@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_3@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_3@labels.claim⟧ |
| `claim_4` | 32900.0 | 822.5 | 2025-06-02 | 8303.0 | 1 | 2426.0 | minor | 0 | 2426.0 | ⟦S:INS-MMBench:qid=claim_4@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_4@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_4@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_4@labels.claim⟧ |
| `claim_5` | 38300.0 | 957.5 | 2023-10-04 | 9653.0 | 1 | 1000.0 | minor | 1 | 0.0 | ⟦S:INS-MMBench:qid=claim_5@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_5@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_5@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_5@labels.claim⟧ |
| `claim_6` | 29400.0 | 735.0 | 2022-12-15 | 7428.0 | 1 | 626.0 | minor | 1 | 0.0 | ⟦S:INS-MMBench:qid=claim_6@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_6@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_6@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_6@labels.claim⟧ |
| `claim_7` | 47300.0 | 1182.5 | 2028-08-22 | 11903.0 | 1 | 4048.0 | minor | 0 | 4048.0 | ⟦S:INS-MMBench:qid=claim_7@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_7@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_7@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_7@labels.claim⟧ |
| `claim_8` | 31500.0 | 787.5 | 2023-03-09 | 7953.0 | 1 | 487.0 | minor | 1 | 0.0 | ⟦S:INS-MMBench:qid=claim_8@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_8@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_8@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_8@labels.claim⟧ |
| `claim_9` | 43400.0 | 1085.0 | 2025-04-17 | 10928.0 | 1 | 3090.0 | minor | 0 | 3090.0 | ⟦S:INS-MMBench:qid=claim_9@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_9@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_9@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_9@labels.claim⟧ |
| `claim_10` | 41800.0 | 1045.0 | 2025-05-14 | 10528.0 | 1 | 305.0 | minor | 0 | 305.0 | ⟦S:INS-MMBench:qid=claim_10@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_10@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_10@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_10@labels.claim⟧ |
| `claim_11` | 37700.0 | 942.5 | 2025-09-24 | 9503.0 | 1 | 3607.0 | minor | 0 | 3607.0 | ⟦S:INS-MMBench:qid=claim_11@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_11@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_11@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_11@labels.claim⟧ |

- 以本子集 12 条 claim 样本为准，判断类字段 `claim` 的取值分布为 0.0×5/459.0×1/826.0×1/2426.0×1/4048.0×1/3090.0×1/305.0×1/3607.0×1（证据：上表逐行）⟦S:INS-MMBench:qids=claim_0..claim_11@labels.claim⟧
- 可用于回答的字段清单（与本页 `source_refs` 同集合）：`Cost_of_vehicle`, `Min_coverage`, `Expiry_date`, `Max_coverage`, `Condition`, `Amount`, `Severity`, `expired`, `claim` ⟦S:INS-MMBench:qid=claim_0@labels.Cost_of_vehicle⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Min_coverage⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Expiry_date⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Max_coverage⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Condition⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Amount⟧ ⟦S:INS-MMBench:qid=claim_0@labels.Severity⟧ ⟦S:INS-MMBench:qid=claim_0@labels.expired⟧ ⟦S:INS-MMBench:qid=claim_0@labels.claim⟧

## 3. 本页不回答什么

- 不给出条款级依据：本子集无条款文本，且 `answer` 列不存在（`answer_status=absent_in_source`）⟦S:INS-MMBench:qid=claim_0@answer_status⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
