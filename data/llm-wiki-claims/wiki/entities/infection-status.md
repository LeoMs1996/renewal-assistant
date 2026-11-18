---
id: claims-entity-infection-status
type: entity
title: 病害感染判定
domain: claims
insurance_line: agricultural_claim
summary: infection 实体登记：12 个单元，逐属性可回溯。
tags: [ins-mmbench, agri, entity]
source_refs: [INS-MMBench:qid=agri_0, INS-MMBench:qid=agri_1, INS-MMBench:qid=agri_2, INS-MMBench:qid=agri_3, INS-MMBench:qid=agri_4, INS-MMBench:qid=agri_5, INS-MMBench:qid=agri_6, INS-MMBench:qid=agri_7, INS-MMBench:qid=agri_8, INS-MMBench:qid=agri_9, INS-MMBench:qid=agri_10, INS-MMBench:qid=agri_11]
raw_refs: [raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-agricultural, claims-section-agri-infection-status]
status: verified
---
# 病害感染判定（实体页）

> 本页把「病害感染判定」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

## 1. 字段出处（逐字，取首单元 `agri_0`）

>     3. Detect Pest/Disease Presence: Determine whether there is any pest or disease infection in the crop (Yes/No).

⟦S:INS-MMBench:qid=agri_0@L11-L11⟧

>     Please strictly output in this format:
>     1. Crop species: <species>
>     2. Fruit cluster count: <a specific number>
>     3. Pest/Disease infection: Yes/No
>     4. Insurance decision: No Compensation/Partial Compensation/Full Compensation. Reason: <Reason>

⟦S:INS-MMBench:qid=agri_0@L13-L17⟧

## 2. 属性事实（逐单元、逐属性带标记）

| qid | `infection` | 原文定位 |
|---|---|---|
| `agri_0` | YES | ⟦S:INS-MMBench:qid=agri_0@labels.infection⟧ |
| `agri_1` | YES | ⟦S:INS-MMBench:qid=agri_1@labels.infection⟧ |
| `agri_2` | NO | ⟦S:INS-MMBench:qid=agri_2@labels.infection⟧ |
| `agri_3` | NO | ⟦S:INS-MMBench:qid=agri_3@labels.infection⟧ |
| `agri_4` | NO | ⟦S:INS-MMBench:qid=agri_4@labels.infection⟧ |
| `agri_5` | NO | ⟦S:INS-MMBench:qid=agri_5@labels.infection⟧ |
| `agri_6` | NO | ⟦S:INS-MMBench:qid=agri_6@labels.infection⟧ |
| `agri_7` | NO | ⟦S:INS-MMBench:qid=agri_7@labels.infection⟧ |
| `agri_8` | NO | ⟦S:INS-MMBench:qid=agri_8@labels.infection⟧ |
| `agri_9` | NO | ⟦S:INS-MMBench:qid=agri_9@labels.infection⟧ |
| `agri_10` | NO | ⟦S:INS-MMBench:qid=agri_10@labels.infection⟧ |
| `agri_11` | NO | ⟦S:INS-MMBench:qid=agri_11@labels.infection⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 12 个单元（agri 分片），每个属性均可在 §2 对应单元格回溯；取值分布：infection=YES×2/NO×10⟦S:INS-MMBench:qids=agri_0..agri_11@labels.infection⟧
- 属性个数：1（`infection`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=agri_0@labels.infection⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-agricultural]] `claims-doc-ins-mmbench-agricultural`
- [[claims-section-agri-infection-status]] `claims-section-agri-infection-status`
