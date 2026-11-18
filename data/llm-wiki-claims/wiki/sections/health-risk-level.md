---
id: claims-section-health-risk-level
type: section
title: 风险等级（health_risk_assessment）
domain: claims
insurance_line: health_underwriting
summary: risk_level 在 12 条 health 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, health, section]
source_refs: [INS-MMBench:qid=health_0, INS-MMBench:qid=health_1, INS-MMBench:qid=health_2, INS-MMBench:qid=health_3, INS-MMBench:qid=health_4, INS-MMBench:qid=health_5, INS-MMBench:qid=health_6, INS-MMBench:qid=health_7, INS-MMBench:qid=health_8, INS-MMBench:qid=health_9, INS-MMBench:qid=health_10, INS-MMBench:qid=health_11]
raw_refs: [raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-health, claims-entity-underwriting-decision, claims-section-health-imaging-part, claims-section-health-report-consistency, claims-section-health-underwriting-decision]
status: verified
---
# 风险等级（health_risk_assessment）

> 本页只陈述本子集中 `risk_level` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `health_0`）

> Please strictly output in the following format:
> 1. Scan Region: <Scan Region>
> 2. Scan Result Match: Yes/No.
> 3. Health Risk Severity: Low/Moderate/High.
> 4. Underwriting Evaluation: Declined/Standard/Higher Premium. Reason: <Reason>

⟦S:INS-MMBench:qid=health_0@L9-L13⟧

## 2. 样本事实（逐行 span 级）

| qid | `risk_level` | 原文定位 |
|---|---|---|
| `health_0` | mild risk | ⟦S:INS-MMBench:qid=health_0@labels.risk_level⟧ |
| `health_1` | mild risk | ⟦S:INS-MMBench:qid=health_1@labels.risk_level⟧ |
| `health_2` | mild risk | ⟦S:INS-MMBench:qid=health_2@labels.risk_level⟧ |
| `health_3` | mild risk | ⟦S:INS-MMBench:qid=health_3@labels.risk_level⟧ |
| `health_4` | severe risk | ⟦S:INS-MMBench:qid=health_4@labels.risk_level⟧ |
| `health_5` | mild risk | ⟦S:INS-MMBench:qid=health_5@labels.risk_level⟧ |
| `health_6` | no risk | ⟦S:INS-MMBench:qid=health_6@labels.risk_level⟧ |
| `health_7` | mild risk | ⟦S:INS-MMBench:qid=health_7@labels.risk_level⟧ |
| `health_8` | mild risk | ⟦S:INS-MMBench:qid=health_8@labels.risk_level⟧ |
| `health_9` | mild risk | ⟦S:INS-MMBench:qid=health_9@labels.risk_level⟧ |
| `health_10` | mild risk | ⟦S:INS-MMBench:qid=health_10@labels.risk_level⟧ |
| `health_11` | no risk | ⟦S:INS-MMBench:qid=health_11@labels.risk_level⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：risk_level=mild risk×9/severe risk×1/no risk×2（证据：§2 全 12 行）⟦S:INS-MMBench:qids=health_0..health_11@labels.risk_level⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-health]] `claims-doc-ins-mmbench-health`
- [[claims-entity-underwriting-decision]] `claims-entity-underwriting-decision`
- [[claims-section-health-imaging-part]] `claims-section-health-imaging-part`
- [[claims-section-health-report-consistency]] `claims-section-health-report-consistency`
- [[claims-section-health-underwriting-decision]] `claims-section-health-underwriting-decision`
