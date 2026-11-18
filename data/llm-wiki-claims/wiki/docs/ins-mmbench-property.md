---
id: claims-doc-ins-mmbench-property
type: doc
title: INS-MMBench 子集：property 保险样本总览
domain: claims
insurance_line: property_claim
summary: INS-MMBench 子集 property 保险 6 条样本的登记页：字段齐全、逐行可回溯。
tags: [ins-mmbench, property, doc]
source_refs: [INS-MMBench:qid=property_0, INS-MMBench:qid=property_1, INS-MMBench:qid=property_2, INS-MMBench:qid=property_3, INS-MMBench:qid=property_4, INS-MMBench:qid=property_5]
raw_refs: [raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005]
updated: 2026-11-18
related: [claims-entity-claim-decision, claims-faq-property, claims-section-property-claim-decision, claims-section-property-damage-count, claims-section-property-disaster-type]
status: verified
---
# INS-MMBench 子集：property 保险样本总览

> 本页是抽样层登记页：只登记「本子集里有哪些样本、字段是否齐全」，不做业务推断。
> 全子集 54 条，本页覆盖 property 的 6 条。

## 1. 样本清单（逐行可回溯）

| qid | 任务 | 图片数 | 题干行数 | 定位 |
|---|---|---|---|---|
| `property_0` | property_risk_management | 2 | 14 | ⟦S:INS-MMBench:qid=property_0@L1-L14⟧ |
| `property_1` | property_risk_management | 2 | 14 | ⟦S:INS-MMBench:qid=property_1@L1-L14⟧ |
| `property_2` | property_risk_management | 2 | 14 | ⟦S:INS-MMBench:qid=property_2@L1-L14⟧ |
| `property_3` | property_risk_management | 2 | 14 | ⟦S:INS-MMBench:qid=property_3@L1-L14⟧ |
| `property_4` | property_risk_management | 2 | 14 | ⟦S:INS-MMBench:qid=property_4@L1-L14⟧ |
| `property_5` | property_risk_management | 2 | 14 | ⟦S:INS-MMBench:qid=property_5@L1-L14⟧ |

## 2. 字段齐全度（由上表聚合，非外部知识）

- 本页 6 条样本共出现 5 个 LABEL 键：`disaster`(6 条), `type`(6 条), `number`(6 条), `damage_number`(6 条), `claim_decision`(6 条)（证据：下列标记逐键覆盖真正含该键的单元；§1 表只登记每条样本本身的定位）⟦S:INS-MMBench:qids=property_0..property_5@labels.disaster⟧ ⟦S:INS-MMBench:qids=property_0..property_5@labels.type⟧ ⟦S:INS-MMBench:qids=property_0..property_5@labels.number⟧ ⟦S:INS-MMBench:qids=property_0..property_5@labels.damage_number⟧ ⟦S:INS-MMBench:qids=property_0..property_5@labels.claim_decision⟧

## 3. 题干规约（逐字，取首单元 `property_0`）

> Please strictly output in this format:
> 1. Disaster Occurred: Yes/No
> 2. Disaster Type: <type>
> 3. House Count: <number>
> 4. Damaged House Count: <number>
> 5. Insurance Decision: <No Compensation/Partial Compensation/Full Compensation>. Reason: <Reason>

⟦S:INS-MMBench:qid=property_0@L9-L14⟧

## 4. 层级说明

- 本子集 54 条的 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`：**分层实际只落在 `task_name` 这一层**（本页对应 `property_risk_management`），不存在更粗/更细的层级区分度⟦S:INS-MMBench:qid=property_0@sample.task_layer⟧⟦S:INS-MMBench:qid=property_0@sample.meta_task⟧

## 5. 图片引用前提

- 本页 12 张图片**未入库**（避免 33 MiB 重复）：引用形态为 `data/ins-mmbench/raw/<split>/<index>/<n>.jpg`，已在 manifest 固定 sha256；新 clone 需先按 `data/ins-mmbench/FETCH.md` 重取，再跑 `python3 data/llm-wiki-claims/scripts/normalize_raw.py check` 复核⟦S:INS-MMBench:qid=property_0@property/0/0.png⟧

## 6. 相关条目

- [[claims-entity-claim-decision]] `claims-entity-claim-decision`
- [[claims-faq-property]] `claims-faq-property`
- [[claims-section-property-claim-decision]] `claims-section-property-claim-decision`
- [[claims-section-property-damage-count]] `claims-section-property-damage-count`
- [[claims-section-property-disaster-type]] `claims-section-property-disaster-type`
