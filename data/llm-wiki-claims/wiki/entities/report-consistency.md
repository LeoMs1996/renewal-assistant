---
id: claims-entity-report-consistency
type: entity
title: 报告一致性
domain: claims
insurance_line: health_underwriting
summary: match/original_report/adjusted_report 实体登记：12 个单元，逐属性可回溯。
tags: [ins-mmbench, health, entity]
source_refs: [INS-MMBench:qid=health_0, INS-MMBench:qid=health_1, INS-MMBench:qid=health_2, INS-MMBench:qid=health_3, INS-MMBench:qid=health_4, INS-MMBench:qid=health_5, INS-MMBench:qid=health_6, INS-MMBench:qid=health_7, INS-MMBench:qid=health_8, INS-MMBench:qid=health_9, INS-MMBench:qid=health_10, INS-MMBench:qid=health_11]
raw_refs: [raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-health, claims-section-health-report-consistency]
status: verified
---
# 报告一致性（实体页）

> 本页把「报告一致性」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

## 1. 字段出处（逐字，取首单元 `health_0`）

> 2. Scan Result Match: Determine whether the scan result (findings on the image) matches the findings described in the report (Yes/No). 

⟦S:INS-MMBench:qid=health_0@L5-L5⟧

> Please strictly output in the following format:
> 1. Scan Region: <Scan Region>
> 2. Scan Result Match: Yes/No.
> 3. Health Risk Severity: Low/Moderate/High.
> 4. Underwriting Evaluation: Declined/Standard/Higher Premium. Reason: <Reason>

⟦S:INS-MMBench:qid=health_0@L9-L13⟧

## 2. 属性事实（逐单元、逐属性带标记）

| qid | `match` | `original_report` | `adjusted_report` | 原文定位 |
|---|---|---|---|---|
| `health_0` | yes | The lungs are clear. There is no pleura… | The lungs are clear. There is no pleura… | ⟦S:INS-MMBench:qid=health_0@labels.match⟧ ⟦S:INS-MMBench:qid=health_0@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_0@labels.adjusted_report⟧ |
| `health_1` | yes | The heart size is upper limits of norma… | The heart size is upper limits of norma… | ⟦S:INS-MMBench:qid=health_1@labels.match⟧ ⟦S:INS-MMBench:qid=health_1@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_1@labels.adjusted_report⟧ |
| `health_2` | yes | Stable, normal cardiac size, mediastinu… | Stable, normal cardiac size, mediastinu… | ⟦S:INS-MMBench:qid=health_2@labels.match⟧ ⟦S:INS-MMBench:qid=health_2@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_2@labels.adjusted_report⟧ |
| `health_3` | yes | The heart size is within normal limits.… | The heart size is within normal limits.… | ⟦S:INS-MMBench:qid=health_3@labels.match⟧ ⟦S:INS-MMBench:qid=health_3@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_3@labels.adjusted_report⟧ |
| `health_4` | yes | 4 images. There is a large hydropneumot… | 4 images. There is a large hydropneumot… | ⟦S:INS-MMBench:qid=health_4@labels.match⟧ ⟦S:INS-MMBench:qid=health_4@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_4@labels.adjusted_report⟧ |
| `health_5` | yes | Heart size within normal limits. Medias… | Heart size within normal limits. Medias… | ⟦S:INS-MMBench:qid=health_5@labels.match⟧ ⟦S:INS-MMBench:qid=health_5@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_5@labels.adjusted_report⟧ |
| `health_6` | yes | Heart size and mediastinal contour are … | Heart size and mediastinal contour are … | ⟦S:INS-MMBench:qid=health_6@labels.match⟧ ⟦S:INS-MMBench:qid=health_6@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_6@labels.adjusted_report⟧ |
| `health_7` | yes | The heart size and mediastinal contours… | The heart size and mediastinal contours… | ⟦S:INS-MMBench:qid=health_7@labels.match⟧ ⟦S:INS-MMBench:qid=health_7@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_7@labels.adjusted_report⟧ |
| `health_8` | yes | The lungs are clear. There is no pleura… | The lungs are clear. There is no pleura… | ⟦S:INS-MMBench:qid=health_8@labels.match⟧ ⟦S:INS-MMBench:qid=health_8@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_8@labels.adjusted_report⟧ |
| `health_9` | yes | The cardiomediastinal silhouette and pu… | The cardiomediastinal silhouette and pu… | ⟦S:INS-MMBench:qid=health_9@labels.match⟧ ⟦S:INS-MMBench:qid=health_9@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_9@labels.adjusted_report⟧ |
| `health_10` | yes | The trachea is midline. The cardiomedia… | The trachea is midline. The cardiomedia… | ⟦S:INS-MMBench:qid=health_10@labels.match⟧ ⟦S:INS-MMBench:qid=health_10@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_10@labels.adjusted_report⟧ |
| `health_11` | yes | Frontal and lateral views demonstrate t… | Frontal and lateral views demonstrate t… | ⟦S:INS-MMBench:qid=health_11@labels.match⟧ ⟦S:INS-MMBench:qid=health_11@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_11@labels.adjusted_report⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 12 个单元（health 分片），每个属性均可在 §2 对应单元格回溯；取值分布：match=yes×12；original_report=The lungs are clear. Th…×1/The heart size is upper…×1/Stable, normal cardiac …×1/The heart size is withi…×1/4 images. There is a la…×1/Heart size within norma…×1/Heart size and mediasti…×1/The heart size and medi…×1/The lungs are clear. Th…×1/The cardiomediastinal s…×1/The trachea is midline.…×1/Frontal and lateral vie…×1；adjusted_report=The lungs are clear. Th…×1/The heart size is upper…×1/Stable, normal cardiac …×1/The heart size is withi…×1/4 images. There is a la…×1/Heart size within norma…×1/Heart size and mediasti…×1/The heart size and medi…×1/The lungs are clear. Th…×1/The cardiomediastinal s…×1/The trachea is midline.…×1/Frontal and lateral vie…×1⟦S:INS-MMBench:qids=health_0..health_11@labels.match⟧
- 属性个数：3（`match`, `original_report`, `adjusted_report`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=health_0@labels.match⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-health]] `claims-doc-ins-mmbench-health`
- [[claims-section-health-report-consistency]] `claims-section-health-report-consistency`
