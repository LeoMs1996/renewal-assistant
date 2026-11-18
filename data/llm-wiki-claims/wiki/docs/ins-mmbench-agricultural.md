---
id: claims-doc-ins-mmbench-agricultural
type: doc
title: INS-MMBench 子集：agricultural 保险样本总览
domain: claims
insurance_line: agricultural_claim
summary: INS-MMBench 子集 agri 保险 12 条样本的登记页：字段齐全、逐行可回溯。
tags: [ins-mmbench, agri, doc]
source_refs: [INS-MMBench:qid=agri_0, INS-MMBench:qid=agri_1, INS-MMBench:qid=agri_2, INS-MMBench:qid=agri_3, INS-MMBench:qid=agri_4, INS-MMBench:qid=agri_5, INS-MMBench:qid=agri_6, INS-MMBench:qid=agri_7, INS-MMBench:qid=agri_8, INS-MMBench:qid=agri_9, INS-MMBench:qid=agri_10, INS-MMBench:qid=agri_11]
raw_refs: [raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011]
updated: 2026-11-18
related: [claims-entity-infection-status, claims-faq-agri, claims-section-agri-compensation-tier, claims-section-agri-infection-status, claims-section-agri-insured-subject]
status: verified
---
# INS-MMBench 子集：agricultural 保险样本总览

> 本页是抽样层登记页：只登记「本子集里有哪些样本、字段是否齐全」，不做业务推断。
> 全子集 54 条，本页覆盖 agricultural 的 12 条。

## 1. 样本清单（逐行可回溯）

| qid | 任务 | 图片数 | 题干行数 | 定位 |
|---|---|---|---|---|
| `agri_0` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_0@L1-L17⟧ |
| `agri_1` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_1@L1-L17⟧ |
| `agri_2` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_2@L1-L17⟧ |
| `agri_3` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_3@L1-L17⟧ |
| `agri_4` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_4@L1-L17⟧ |
| `agri_5` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_5@L1-L17⟧ |
| `agri_6` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_6@L1-L17⟧ |
| `agri_7` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_7@L1-L17⟧ |
| `agri_8` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_8@L1-L17⟧ |
| `agri_9` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_9@L1-L17⟧ |
| `agri_10` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_10@L1-L17⟧ |
| `agri_11` | agri_claim_processing | 1 | 17 | ⟦S:INS-MMBench:qid=agri_11@L1-L17⟧ |

## 2. 字段齐全度（由上表聚合，非外部知识）

- 本页 12 条样本共出现 4 个 LABEL 键：`species`(12 条), `count`(12 条), `infection`(12 条), `claim`(12 条)（证据：下列标记逐键覆盖真正含该键的单元；§1 表只登记每条样本本身的定位）⟦S:INS-MMBench:qids=agri_0..agri_11@labels.species⟧ ⟦S:INS-MMBench:qids=agri_0..agri_11@labels.count⟧ ⟦S:INS-MMBench:qids=agri_0..agri_11@labels.infection⟧ ⟦S:INS-MMBench:qids=agri_0..agri_11@labels.claim⟧

## 3. 题干规约（逐字，取首单元 `agri_0`）

>     Please strictly output in this format:
>     1. Crop species: <species>
>     2. Fruit cluster count: <a specific number>
>     3. Pest/Disease infection: Yes/No
>     4. Insurance decision: No Compensation/Partial Compensation/Full Compensation. Reason: <Reason>

⟦S:INS-MMBench:qid=agri_0@L13-L17⟧

## 4. 层级说明

- 本子集 54 条的 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`：**分层实际只落在 `task_name` 这一层**（本页对应 `agri_claim_processing`），不存在更粗/更细的层级区分度⟦S:INS-MMBench:qid=agri_0@sample.task_layer⟧⟦S:INS-MMBench:qid=agri_0@sample.meta_task⟧

## 5. 图片引用前提

- 本页 12 张图片**未入库**（避免 33 MiB 重复）：引用形态为 `data/ins-mmbench/raw/<split>/<index>/<n>.jpg`，已在 manifest 固定 sha256；新 clone 需先按 `data/ins-mmbench/FETCH.md` 重取，再跑 `python3 data/llm-wiki-claims/scripts/normalize_raw.py check` 复核⟦S:INS-MMBench:qid=agri_0@agri/0/0.jpg⟧

## 6. 相关条目

- [[claims-entity-infection-status]] `claims-entity-infection-status`
- [[claims-faq-agri]] `claims-faq-agri`
- [[claims-section-agri-compensation-tier]] `claims-section-agri-compensation-tier`
- [[claims-section-agri-infection-status]] `claims-section-agri-infection-status`
- [[claims-section-agri-insured-subject]] `claims-section-agri-insured-subject`
