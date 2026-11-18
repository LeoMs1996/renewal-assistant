---
id: claims-section-agri-insured-subject
type: section
title: 标的物种与数量（agri_claim_processing）
domain: claims
insurance_line: agricultural_claim
summary: species/count 在 12 条 agri 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, agri, section]
source_refs: [INS-MMBench:qid=agri_0, INS-MMBench:qid=agri_1, INS-MMBench:qid=agri_2, INS-MMBench:qid=agri_3, INS-MMBench:qid=agri_4, INS-MMBench:qid=agri_5, INS-MMBench:qid=agri_6, INS-MMBench:qid=agri_7, INS-MMBench:qid=agri_8, INS-MMBench:qid=agri_9, INS-MMBench:qid=agri_10, INS-MMBench:qid=agri_11]
raw_refs: [raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-agricultural, claims-section-agri-compensation-tier, claims-section-agri-infection-status]
status: verified
---
# 标的物种与数量（agri_claim_processing）

> 本页只陈述本子集中 `species`, `count` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `agri_0`）

>     1. Identify the Crop Species: Analyze the image and determine the specific crop species.

⟦S:INS-MMBench:qid=agri_0@L9-L9⟧

>     2. Fruit cluster count: <a specific number>

⟦S:INS-MMBench:qid=agri_0@L15-L15⟧

>     Please strictly output in this format:
>     1. Crop species: <species>
>     2. Fruit cluster count: <a specific number>
>     3. Pest/Disease infection: Yes/No
>     4. Insurance decision: No Compensation/Partial Compensation/Full Compensation. Reason: <Reason>

⟦S:INS-MMBench:qid=agri_0@L13-L17⟧

## 2. 样本事实（逐行 span 级）

| qid | `species` | `count` | 原文定位 |
|---|---|---|---|
| `agri_0` | grape | 1 | ⟦S:INS-MMBench:qid=agri_0@labels.species⟧ ⟦S:INS-MMBench:qid=agri_0@labels.count⟧ |
| `agri_1` | grape | 2 | ⟦S:INS-MMBench:qid=agri_1@labels.species⟧ ⟦S:INS-MMBench:qid=agri_1@labels.count⟧ |
| `agri_2` | grape | 0 | ⟦S:INS-MMBench:qid=agri_2@labels.species⟧ ⟦S:INS-MMBench:qid=agri_2@labels.count⟧ |
| `agri_3` | grape | 11 | ⟦S:INS-MMBench:qid=agri_3@labels.species⟧ ⟦S:INS-MMBench:qid=agri_3@labels.count⟧ |
| `agri_4` | grape | 9 | ⟦S:INS-MMBench:qid=agri_4@labels.species⟧ ⟦S:INS-MMBench:qid=agri_4@labels.count⟧ |
| `agri_5` | grape | 8 | ⟦S:INS-MMBench:qid=agri_5@labels.species⟧ ⟦S:INS-MMBench:qid=agri_5@labels.count⟧ |
| `agri_6` | grape | 0 | ⟦S:INS-MMBench:qid=agri_6@labels.species⟧ ⟦S:INS-MMBench:qid=agri_6@labels.count⟧ |
| `agri_7` | grape | 0 | ⟦S:INS-MMBench:qid=agri_7@labels.species⟧ ⟦S:INS-MMBench:qid=agri_7@labels.count⟧ |
| `agri_8` | grape | 0 | ⟦S:INS-MMBench:qid=agri_8@labels.species⟧ ⟦S:INS-MMBench:qid=agri_8@labels.count⟧ |
| `agri_9` | grape | 0 | ⟦S:INS-MMBench:qid=agri_9@labels.species⟧ ⟦S:INS-MMBench:qid=agri_9@labels.count⟧ |
| `agri_10` | grape | 0 | ⟦S:INS-MMBench:qid=agri_10@labels.species⟧ ⟦S:INS-MMBench:qid=agri_10@labels.count⟧ |
| `agri_11` | grape | 0 | ⟦S:INS-MMBench:qid=agri_11@labels.species⟧ ⟦S:INS-MMBench:qid=agri_11@labels.count⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：species=grape×12；count=1×1/2×1/0×7/11×1/9×1/8×1（证据：§2 全 12 行）⟦S:INS-MMBench:qids=agri_0..agri_11@labels.species⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-agricultural]] `claims-doc-ins-mmbench-agricultural`
- [[claims-section-agri-compensation-tier]] `claims-section-agri-compensation-tier`
- [[claims-section-agri-infection-status]] `claims-section-agri-infection-status`
