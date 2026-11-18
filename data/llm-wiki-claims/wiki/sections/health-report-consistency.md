---
id: claims-section-health-report-consistency
type: section
title: 报告一致性（health_risk_assessment）
domain: claims
insurance_line: health_underwriting
summary: original_report/adjusted_report/match 在 12 条 health 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, health, section]
source_refs: [INS-MMBench:qid=health_0, INS-MMBench:qid=health_1, INS-MMBench:qid=health_2, INS-MMBench:qid=health_3, INS-MMBench:qid=health_4, INS-MMBench:qid=health_5, INS-MMBench:qid=health_6, INS-MMBench:qid=health_7, INS-MMBench:qid=health_8, INS-MMBench:qid=health_9, INS-MMBench:qid=health_10, INS-MMBench:qid=health_11]
raw_refs: [raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-health, claims-entity-report-consistency, claims-section-health-imaging-part, claims-section-health-risk-level, claims-section-health-underwriting-decision]
status: verified
---
# 报告一致性（health_risk_assessment）

> 本页只陈述本子集中 `original_report`, `adjusted_report`, `match` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `health_0`）

> 2. Scan Result Match: Determine whether the scan result (findings on the image) matches the findings described in the report (Yes/No). 

⟦S:INS-MMBench:qid=health_0@L5-L5⟧

> Please strictly output in the following format:
> 1. Scan Region: <Scan Region>
> 2. Scan Result Match: Yes/No.
> 3. Health Risk Severity: Low/Moderate/High.
> 4. Underwriting Evaluation: Declined/Standard/Higher Premium. Reason: <Reason>

⟦S:INS-MMBench:qid=health_0@L9-L13⟧

## 2. 样本事实（逐行 span 级）

| qid | `original_report` | `adjusted_report` | `match` | 原文定位 |
|---|---|---|---|---|
| `health_0` | The lungs are clear. There is no pleural effusion. The heart and mediastinum ar… | The lungs are clear. There is no pleural effusion. The heart and mediastinum ar… | yes | ⟦S:INS-MMBench:qid=health_0@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_0@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_0@labels.match⟧ |
| `health_1` | The heart size is upper limits of normal. Mediastinal contour appears normal an… | The heart size is upper limits of normal. Mediastinal contour appears normal an… | yes | ⟦S:INS-MMBench:qid=health_1@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_1@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_1@labels.match⟧ |
| `health_2` | Stable, normal cardiac size, mediastinum, and central pulmonary vasculature. In… | Stable, normal cardiac size, mediastinum, and central pulmonary vasculature. In… | yes | ⟦S:INS-MMBench:qid=health_2@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_2@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_2@labels.match⟧ |
| `health_3` | The heart size is within normal limits. Prominent right paratracheal soft tissu… | The heart size is within normal limits. Prominent right paratracheal soft tissu… | yes | ⟦S:INS-MMBench:qid=health_3@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_3@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_3@labels.match⟧ |
| `health_4` | 4 images. There is a large hydropneumothorax within the left chest. There is es… | 4 images. There is a large hydropneumothorax within the left chest. There is es… | yes | ⟦S:INS-MMBench:qid=health_4@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_4@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_4@labels.match⟧ |
| `health_5` | Heart size within normal limits. Mediastinal contours unremarkable. Pulmonary v… | Heart size within normal limits. Mediastinal contours unremarkable. Pulmonary v… | yes | ⟦S:INS-MMBench:qid=health_5@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_5@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_5@labels.match⟧ |
| `health_6` | Heart size and mediastinal contour are normal. Pulmonary vascularity is normal.… | Heart size and mediastinal contour are normal. Pulmonary vascularity is normal.… | yes | ⟦S:INS-MMBench:qid=health_6@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_6@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_6@labels.match⟧ |
| `health_7` | The heart size and mediastinal contours appear within normal limits. Low lung v… | The heart size and mediastinal contours appear within normal limits. Low lung v… | yes | ⟦S:INS-MMBench:qid=health_7@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_7@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_7@labels.match⟧ |
| `health_8` | The lungs are clear. There is no pleural effusion or pneumothorax. There has be… | The lungs are clear. There is no pleural effusion or pneumothorax. There has be… | yes | ⟦S:INS-MMBench:qid=health_8@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_8@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_8@labels.match⟧ |
| `health_9` | The cardiomediastinal silhouette and pulmonary vasculature are within normal li… | The cardiomediastinal silhouette and pulmonary vasculature are within normal li… | yes | ⟦S:INS-MMBench:qid=health_9@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_9@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_9@labels.match⟧ |
| `health_10` | The trachea is midline. The cardiomediastinal silhouette is normal. The lungs a… | The trachea is midline. The cardiomediastinal silhouette is normal. The lungs a… | yes | ⟦S:INS-MMBench:qid=health_10@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_10@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_10@labels.match⟧ |
| `health_11` | Frontal and lateral views demonstrate the cardiomediastinal silhouette to be wi… | Frontal and lateral views demonstrate the cardiomediastinal silhouette to be wi… | yes | ⟦S:INS-MMBench:qid=health_11@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_11@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_11@labels.match⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：original_report=The lungs are clear. Th…×1/The heart size is upper…×1/Stable, normal cardiac …×1/The heart size is withi…×1/4 images. There is a la…×1/Heart size within norma…×1/Heart size and mediasti…×1/The heart size and medi…×1/The lungs are clear. Th…×1/The cardiomediastinal s…×1/The trachea is midline.…×1/Frontal and lateral vie…×1；adjusted_report=The lungs are clear. Th…×1/The heart size is upper…×1/Stable, normal cardiac …×1/The heart size is withi…×1/4 images. There is a la…×1/Heart size within norma…×1/Heart size and mediasti…×1/The heart size and medi…×1/The lungs are clear. Th…×1/The cardiomediastinal s…×1/The trachea is midline.…×1/Frontal and lateral vie…×1；match=yes×12（证据：§2 全 12 行）⟦S:INS-MMBench:qids=health_0..health_11@labels.original_report⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-health]] `claims-doc-ins-mmbench-health`
- [[claims-entity-report-consistency]] `claims-entity-report-consistency`
- [[claims-section-health-imaging-part]] `claims-section-health-imaging-part`
- [[claims-section-health-risk-level]] `claims-section-health-risk-level`
- [[claims-section-health-underwriting-decision]] `claims-section-health-underwriting-decision`
