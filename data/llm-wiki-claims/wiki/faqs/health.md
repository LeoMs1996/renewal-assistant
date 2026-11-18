---
id: claims-faq-health
type: faq
title: 影像报告与核保决定如何对应？
domain: claims
insurance_line: health_underwriting
summary: health 任务语料能支持到的回答范围（12 条样本，逐条引用）。
tags: [ins-mmbench, health, faq]
source_refs: [INS-MMBench:qid=health_0, INS-MMBench:qid=health_1, INS-MMBench:qid=health_2, INS-MMBench:qid=health_3, INS-MMBench:qid=health_4, INS-MMBench:qid=health_5, INS-MMBench:qid=health_6, INS-MMBench:qid=health_7, INS-MMBench:qid=health_8, INS-MMBench:qid=health_9, INS-MMBench:qid=health_10, INS-MMBench:qid=health_11]
raw_refs: [raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-health]
status: verified
---
# 影像报告与核保决定如何对应？

> 本页只回答「本子集语料能支持到什么程度」：答案由样本字段与题干规约拼成，不是业务建议。

目录中的问题：给定影像部位与放射科报告，报告一致性、风险等级与核保决定如何推定？

## 1. 题干规约（逐字，取首单元 `health_0`）

> Please strictly output in the following format:
> 1. Scan Region: <Scan Region>
> 2. Scan Result Match: Yes/No.
> 3. Health Risk Severity: Low/Moderate/High.
> 4. Underwriting Evaluation: Declined/Standard/Higher Premium. Reason: <Reason>

⟦S:INS-MMBench:qid=health_0@L9-L13⟧

## 2. 本子集能给出的答案（逐条引用）

| qid | `part` | `original_report` | `adjusted_report` | `match` | `risk_level` | `underwriting_decision` | 原文定位 |
|---|---|---|---|---|---|---|---|
| `health_0` | chest | The lungs are clear. Th… | The lungs are clear. Th… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_0@labels.part⟧ ⟦S:INS-MMBench:qid=health_0@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_0@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_0@labels.match⟧ ⟦S:INS-MMBench:qid=health_0@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_0@labels.underwriting_decision⟧ |
| `health_1` | chest | The heart size is upper… | The heart size is upper… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_1@labels.part⟧ ⟦S:INS-MMBench:qid=health_1@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_1@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_1@labels.match⟧ ⟦S:INS-MMBench:qid=health_1@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_1@labels.underwriting_decision⟧ |
| `health_2` | chest | Stable, normal cardiac … | Stable, normal cardiac … | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_2@labels.part⟧ ⟦S:INS-MMBench:qid=health_2@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_2@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_2@labels.match⟧ ⟦S:INS-MMBench:qid=health_2@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_2@labels.underwriting_decision⟧ |
| `health_3` | chest | The heart size is withi… | The heart size is withi… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_3@labels.part⟧ ⟦S:INS-MMBench:qid=health_3@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_3@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_3@labels.match⟧ ⟦S:INS-MMBench:qid=health_3@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_3@labels.underwriting_decision⟧ |
| `health_4` | chest | 4 images. There is a la… | 4 images. There is a la… | yes | severe risk | Declined | ⟦S:INS-MMBench:qid=health_4@labels.part⟧ ⟦S:INS-MMBench:qid=health_4@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_4@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_4@labels.match⟧ ⟦S:INS-MMBench:qid=health_4@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_4@labels.underwriting_decision⟧ |
| `health_5` | chest | Heart size within norma… | Heart size within norma… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_5@labels.part⟧ ⟦S:INS-MMBench:qid=health_5@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_5@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_5@labels.match⟧ ⟦S:INS-MMBench:qid=health_5@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_5@labels.underwriting_decision⟧ |
| `health_6` | chest | Heart size and mediasti… | Heart size and mediasti… | yes | no risk | Standard | ⟦S:INS-MMBench:qid=health_6@labels.part⟧ ⟦S:INS-MMBench:qid=health_6@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_6@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_6@labels.match⟧ ⟦S:INS-MMBench:qid=health_6@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_6@labels.underwriting_decision⟧ |
| `health_7` | chest | The heart size and medi… | The heart size and medi… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_7@labels.part⟧ ⟦S:INS-MMBench:qid=health_7@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_7@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_7@labels.match⟧ ⟦S:INS-MMBench:qid=health_7@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_7@labels.underwriting_decision⟧ |
| `health_8` | chest | The lungs are clear. Th… | The lungs are clear. Th… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_8@labels.part⟧ ⟦S:INS-MMBench:qid=health_8@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_8@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_8@labels.match⟧ ⟦S:INS-MMBench:qid=health_8@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_8@labels.underwriting_decision⟧ |
| `health_9` | chest | The cardiomediastinal s… | The cardiomediastinal s… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_9@labels.part⟧ ⟦S:INS-MMBench:qid=health_9@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_9@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_9@labels.match⟧ ⟦S:INS-MMBench:qid=health_9@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_9@labels.underwriting_decision⟧ |
| `health_10` | chest | The trachea is midline.… | The trachea is midline.… | yes | mild risk | Higher Premium | ⟦S:INS-MMBench:qid=health_10@labels.part⟧ ⟦S:INS-MMBench:qid=health_10@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_10@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_10@labels.match⟧ ⟦S:INS-MMBench:qid=health_10@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_10@labels.underwriting_decision⟧ |
| `health_11` | chest | Frontal and lateral vie… | Frontal and lateral vie… | yes | no risk | Standard | ⟦S:INS-MMBench:qid=health_11@labels.part⟧ ⟦S:INS-MMBench:qid=health_11@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_11@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_11@labels.match⟧ ⟦S:INS-MMBench:qid=health_11@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_11@labels.underwriting_decision⟧ |

- 以本子集 12 条 health 样本为准，判断类字段 `underwriting_decision` 的取值分布为 Higher Premium×9/Declined×1/Standard×2（证据：上表逐行）⟦S:INS-MMBench:qids=health_0..health_11@labels.underwriting_decision⟧
- 可用于回答的字段清单（与本页 `source_refs` 同集合）：`part`, `original_report`, `adjusted_report`, `match`, `risk_level`, `underwriting_decision` ⟦S:INS-MMBench:qid=health_0@labels.part⟧ ⟦S:INS-MMBench:qid=health_0@labels.original_report⟧ ⟦S:INS-MMBench:qid=health_0@labels.adjusted_report⟧ ⟦S:INS-MMBench:qid=health_0@labels.match⟧ ⟦S:INS-MMBench:qid=health_0@labels.risk_level⟧ ⟦S:INS-MMBench:qid=health_0@labels.underwriting_decision⟧

## 3. 本页不回答什么

- 不给出条款级依据：本子集无条款文本，且 `answer` 列不存在（`answer_status=absent_in_source`）⟦S:INS-MMBench:qid=health_0@answer_status⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-health]] `claims-doc-ins-mmbench-health`
