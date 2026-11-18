---
id: claims-section-health-underwriting-decision
type: section
title: 核保决定（health_risk_assessment）
domain: claims
insurance_line: health_underwriting
summary: underwriting_decision 在 12 条 health 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, health, section]
source_refs: [INS-MMBench:qid=health_0, INS-MMBench:qid=health_1, INS-MMBench:qid=health_2, INS-MMBench:qid=health_3, INS-MMBench:qid=health_4, INS-MMBench:qid=health_5, INS-MMBench:qid=health_6, INS-MMBench:qid=health_7, INS-MMBench:qid=health_8, INS-MMBench:qid=health_9, INS-MMBench:qid=health_10, INS-MMBench:qid=health_11]
raw_refs: [raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-health, claims-entity-underwriting-decision, claims-section-health-imaging-part, claims-section-health-report-consistency, claims-section-health-risk-level]
status: verified
---
# 核保决定（health_risk_assessment）

> 本页只陈述本子集中 `underwriting_decision` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `health_0`）

> Please strictly output in the following format:
> 1. Scan Region: <Scan Region>
> 2. Scan Result Match: Yes/No.
> 3. Health Risk Severity: Low/Moderate/High.
> 4. Underwriting Evaluation: Declined/Standard/Higher Premium. Reason: <Reason>

⟦S:INS-MMBench:qid=health_0@L9-L13⟧

## 2. 样本事实（逐行 span 级）

| qid | `underwriting_decision` | 原文定位 |
|---|---|---|
| `health_0` | Higher Premium | ⟦S:INS-MMBench:qid=health_0@labels.underwriting_decision⟧ |
| `health_1` | Higher Premium | ⟦S:INS-MMBench:qid=health_1@labels.underwriting_decision⟧ |
| `health_2` | Higher Premium | ⟦S:INS-MMBench:qid=health_2@labels.underwriting_decision⟧ |
| `health_3` | Higher Premium | ⟦S:INS-MMBench:qid=health_3@labels.underwriting_decision⟧ |
| `health_4` | Declined | ⟦S:INS-MMBench:qid=health_4@labels.underwriting_decision⟧ |
| `health_5` | Higher Premium | ⟦S:INS-MMBench:qid=health_5@labels.underwriting_decision⟧ |
| `health_6` | Standard | ⟦S:INS-MMBench:qid=health_6@labels.underwriting_decision⟧ |
| `health_7` | Higher Premium | ⟦S:INS-MMBench:qid=health_7@labels.underwriting_decision⟧ |
| `health_8` | Higher Premium | ⟦S:INS-MMBench:qid=health_8@labels.underwriting_decision⟧ |
| `health_9` | Higher Premium | ⟦S:INS-MMBench:qid=health_9@labels.underwriting_decision⟧ |
| `health_10` | Higher Premium | ⟦S:INS-MMBench:qid=health_10@labels.underwriting_decision⟧ |
| `health_11` | Standard | ⟦S:INS-MMBench:qid=health_11@labels.underwriting_decision⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：underwriting_decision=Higher Premium×9/Declined×1/Standard×2（证据：§2 全 12 行）⟦S:INS-MMBench:qids=health_0..health_11@labels.underwriting_decision⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-health]] `claims-doc-ins-mmbench-health`
- [[claims-entity-underwriting-decision]] `claims-entity-underwriting-decision`
- [[claims-section-health-imaging-part]] `claims-section-health-imaging-part`
- [[claims-section-health-report-consistency]] `claims-section-health-report-consistency`
- [[claims-section-health-risk-level]] `claims-section-health-risk-level`
