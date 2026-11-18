---
id: claims-section-agri-infection-status
type: section
title: 病害感染判定（agri_claim_processing）
domain: claims
insurance_line: agricultural_claim
summary: infection 在 12 条 agri 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, agri, section]
source_refs: [INS-MMBench:qid=agri_0, INS-MMBench:qid=agri_1, INS-MMBench:qid=agri_2, INS-MMBench:qid=agri_3, INS-MMBench:qid=agri_4, INS-MMBench:qid=agri_5, INS-MMBench:qid=agri_6, INS-MMBench:qid=agri_7, INS-MMBench:qid=agri_8, INS-MMBench:qid=agri_9, INS-MMBench:qid=agri_10, INS-MMBench:qid=agri_11]
raw_refs: [raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-agricultural, claims-entity-infection-status, claims-section-agri-compensation-tier, claims-section-agri-insured-subject]
status: verified
---
# 病害感染判定（agri_claim_processing）

> 本页只陈述本子集中 `infection` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `agri_0`）

>     3. Detect Pest/Disease Presence: Determine whether there is any pest or disease infection in the crop (Yes/No).

⟦S:INS-MMBench:qid=agri_0@L11-L11⟧

>     Please strictly output in this format:
>     1. Crop species: <species>
>     2. Fruit cluster count: <a specific number>
>     3. Pest/Disease infection: Yes/No
>     4. Insurance decision: No Compensation/Partial Compensation/Full Compensation. Reason: <Reason>

⟦S:INS-MMBench:qid=agri_0@L13-L17⟧

## 2. 样本事实（逐行 span 级）

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

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：infection=YES×2/NO×10（证据：§2 全 12 行）⟦S:INS-MMBench:qids=agri_0..agri_11@labels.infection⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-agricultural]] `claims-doc-ins-mmbench-agricultural`
- [[claims-entity-infection-status]] `claims-entity-infection-status`
- [[claims-section-agri-compensation-tier]] `claims-section-agri-compensation-tier`
- [[claims-section-agri-insured-subject]] `claims-section-agri-insured-subject`
