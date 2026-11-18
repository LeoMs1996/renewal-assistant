---
id: claims-doc-ins-mmbench-health
type: doc
title: INS-MMBench 子集：health 保险样本总览
domain: claims
insurance_line: health_underwriting
summary: INS-MMBench 子集 health 保险 12 条样本的登记页：字段齐全、逐行可回溯。
tags: [ins-mmbench, health, doc]
source_refs: [INS-MMBench:qid=health_0, INS-MMBench:qid=health_1, INS-MMBench:qid=health_2, INS-MMBench:qid=health_3, INS-MMBench:qid=health_4, INS-MMBench:qid=health_5, INS-MMBench:qid=health_6, INS-MMBench:qid=health_7, INS-MMBench:qid=health_8, INS-MMBench:qid=health_9, INS-MMBench:qid=health_10, INS-MMBench:qid=health_11]
raw_refs: [raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011]
updated: 2026-11-18
related: [claims-entity-report-consistency, claims-entity-underwriting-decision, claims-faq-health, claims-section-health-imaging-part, claims-section-health-report-consistency, claims-section-health-risk-level, claims-section-health-underwriting-decision]
status: verified
---
# INS-MMBench 子集：health 保险样本总览

> 本页是抽样层登记页：只登记「本子集里有哪些样本、字段是否齐全」，不做业务推断。
> 全子集 54 条，本页覆盖 health 的 12 条。

## 1. 样本清单（逐行可回溯）

| qid | 任务 | 图片数 | 题干行数 | 定位 |
|---|---|---|---|---|
| `health_0` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_0@L1-L13⟧ |
| `health_1` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_1@L1-L13⟧ |
| `health_2` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_2@L1-L13⟧ |
| `health_3` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_3@L1-L13⟧ |
| `health_4` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_4@L1-L13⟧ |
| `health_5` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_5@L1-L13⟧ |
| `health_6` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_6@L1-L13⟧ |
| `health_7` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_7@L1-L13⟧ |
| `health_8` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_8@L1-L13⟧ |
| `health_9` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_9@L1-L13⟧ |
| `health_10` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_10@L1-L13⟧ |
| `health_11` | health_risk_assessment | 2 | 13 | ⟦S:INS-MMBench:qid=health_11@L1-L13⟧ |

## 2. 字段齐全度（由上表聚合，非外部知识）

- 本页 12 条样本共出现 6 个 LABEL 键：`part`(12 条), `original_report`(12 条), `adjusted_report`(12 条), `match`(12 条), `risk_level`(12 条), `underwriting_decision`(12 条)（证据：下列标记逐键覆盖真正含该键的单元；§1 表只登记每条样本本身的定位）⟦S:INS-MMBench:qids=health_0..health_11@labels.part⟧ ⟦S:INS-MMBench:qids=health_0..health_11@labels.original_report⟧ ⟦S:INS-MMBench:qids=health_0..health_11@labels.adjusted_report⟧ ⟦S:INS-MMBench:qids=health_0..health_11@labels.match⟧ ⟦S:INS-MMBench:qids=health_0..health_11@labels.risk_level⟧ ⟦S:INS-MMBench:qids=health_0..health_11@labels.underwriting_decision⟧

## 3. 题干规约（逐字，取首单元 `health_0`）

> Please strictly output in the following format:
> 1. Scan Region: <Scan Region>
> 2. Scan Result Match: Yes/No.
> 3. Health Risk Severity: Low/Moderate/High.
> 4. Underwriting Evaluation: Declined/Standard/Higher Premium. Reason: <Reason>

⟦S:INS-MMBench:qid=health_0@L9-L13⟧

## 4. 层级说明

- 本子集 54 条的 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`：**分层实际只落在 `task_name` 这一层**（本页对应 `health_risk_assessment`），不存在更粗/更细的层级区分度⟦S:INS-MMBench:qid=health_0@sample.task_layer⟧⟦S:INS-MMBench:qid=health_0@sample.meta_task⟧

## 5. 图片引用前提

- 本页 24 张图片**未入库**（避免 33 MiB 重复）：引用形态为 `data/ins-mmbench/raw/<split>/<index>/<n>.jpg`，已在 manifest 固定 sha256；新 clone 需先按 `data/ins-mmbench/FETCH.md` 重取，再跑 `python3 data/llm-wiki-claims/scripts/normalize_raw.py check` 复核⟦S:INS-MMBench:qid=health_0@health/0/0.png⟧

## 6. 相关条目

- [[claims-entity-report-consistency]] `claims-entity-report-consistency`
- [[claims-entity-underwriting-decision]] `claims-entity-underwriting-decision`
- [[claims-faq-health]] `claims-faq-health`
- [[claims-section-health-imaging-part]] `claims-section-health-imaging-part`
- [[claims-section-health-report-consistency]] `claims-section-health-report-consistency`
- [[claims-section-health-risk-level]] `claims-section-health-risk-level`
- [[claims-section-health-underwriting-decision]] `claims-section-health-underwriting-decision`
