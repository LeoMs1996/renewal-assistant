---
id: claims-entity-underwriting-decision
type: entity
title: 核保决定
domain: claims
insurance_line: health_underwriting
summary: underwriting_decision/risk_level 实体登记：12 个单元，逐属性可回溯。
tags: [ins-mmbench, health, entity]
source_refs: [INS-MMBench:qid=health_0, INS-MMBench:qid=health_1, INS-MMBench:qid=health_2, INS-MMBench:qid=health_3, INS-MMBench:qid=health_4, INS-MMBench:qid=health_5, INS-MMBench:qid=health_6, INS-MMBench:qid=health_7, INS-MMBench:qid=health_8, INS-MMBench:qid=health_9, INS-MMBench:qid=health_10, INS-MMBench:qid=health_11]
raw_refs: [raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-health, claims-section-health-risk-level, claims-section-health-underwriting-decision]
status: verified
---
# 核保决定（实体页）

> 本页把「核保决定」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

## 1. 字段出处（逐字，取首单元 `health_0`）

> Please strictly output in the following format:
> 1. Scan Region: <Scan Region>
> 2. Scan Result Match: Yes/No.
> 3. Health Risk Severity: Low/Moderate/High.
> 4. Underwriting Evaluation: Declined/Standard/Higher Premium. Reason: <Reason>

⟦S:INS-MMBench:qid=health_0@L9-L13⟧

## 2. 属性事实（逐单元、逐属性带标记）

| qid | `underwriting_decision` | `risk_level` | 原文定位 |
|---|---|---|---|
| `health_0` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_0@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_0@labels.risk_level⟧ |
| `health_1` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_1@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_1@labels.risk_level⟧ |
| `health_2` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_2@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_2@labels.risk_level⟧ |
| `health_3` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_3@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_3@labels.risk_level⟧ |
| `health_4` | Declined | severe risk | ⟦S:INS-MMBench:qid=health_4@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_4@labels.risk_level⟧ |
| `health_5` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_5@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_5@labels.risk_level⟧ |
| `health_6` | Standard | no risk | ⟦S:INS-MMBench:qid=health_6@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_6@labels.risk_level⟧ |
| `health_7` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_7@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_7@labels.risk_level⟧ |
| `health_8` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_8@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_8@labels.risk_level⟧ |
| `health_9` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_9@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_9@labels.risk_level⟧ |
| `health_10` | Higher Premium | mild risk | ⟦S:INS-MMBench:qid=health_10@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_10@labels.risk_level⟧ |
| `health_11` | Standard | no risk | ⟦S:INS-MMBench:qid=health_11@labels.underwriting_decision⟧ ⟦S:INS-MMBench:qid=health_11@labels.risk_level⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 12 个单元（health 分片），每个属性均可在 §2 对应单元格回溯；取值分布：underwriting_decision=Higher Premium×9/Declined×1/Standard×2；risk_level=mild risk×9/severe risk×1/no risk×2⟦S:INS-MMBench:qids=health_0..health_11@labels.underwriting_decision⟧
- 属性个数：2（`underwriting_decision`, `risk_level`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=health_0@labels.underwriting_decision⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-health]] `claims-doc-ins-mmbench-health`
- [[claims-section-health-risk-level]] `claims-section-health-risk-level`
- [[claims-section-health-underwriting-decision]] `claims-section-health-underwriting-decision`
