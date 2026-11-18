---
id: claims-faq-agri
type: faq
title: 农业保险赔付档位如何确定？
domain: claims
insurance_line: agricultural_claim
summary: agri 任务语料能支持到的回答范围（12 条样本，逐条引用）。
tags: [ins-mmbench, agri, faq]
source_refs: [INS-MMBench:qid=agri_0, INS-MMBench:qid=agri_1, INS-MMBench:qid=agri_2, INS-MMBench:qid=agri_3, INS-MMBench:qid=agri_4, INS-MMBench:qid=agri_5, INS-MMBench:qid=agri_6, INS-MMBench:qid=agri_7, INS-MMBench:qid=agri_8, INS-MMBench:qid=agri_9, INS-MMBench:qid=agri_10, INS-MMBench:qid=agri_11]
raw_refs: [raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-agricultural]
status: verified
---
# 农业保险赔付档位如何确定？

> 本页只回答「本子集语料能支持到什么程度」：答案由样本字段与题干规约拼成，不是业务建议。

目录中的问题：给定标的物种、数量与病害感染情况，赔付档位（不赔/部分/全额）如何确定？

## 1. 题干规约（逐字，取首单元 `agri_0`）

>     Please strictly output in this format:
>     1. Crop species: <species>
>     2. Fruit cluster count: <a specific number>
>     3. Pest/Disease infection: Yes/No
>     4. Insurance decision: No Compensation/Partial Compensation/Full Compensation. Reason: <Reason>

⟦S:INS-MMBench:qid=agri_0@L13-L17⟧

## 2. 本子集能给出的答案（逐条引用）

| qid | `species` | `count` | `infection` | `claim` | 原文定位 |
|---|---|---|---|---|---|
| `agri_0` | grape | 1 | YES | Partial Compensation | ⟦S:INS-MMBench:qid=agri_0@labels.species⟧ ⟦S:INS-MMBench:qid=agri_0@labels.count⟧ ⟦S:INS-MMBench:qid=agri_0@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_0@labels.claim⟧ |
| `agri_1` | grape | 2 | YES | Partial Compensation | ⟦S:INS-MMBench:qid=agri_1@labels.species⟧ ⟦S:INS-MMBench:qid=agri_1@labels.count⟧ ⟦S:INS-MMBench:qid=agri_1@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_1@labels.claim⟧ |
| `agri_2` | grape | 0 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_2@labels.species⟧ ⟦S:INS-MMBench:qid=agri_2@labels.count⟧ ⟦S:INS-MMBench:qid=agri_2@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_2@labels.claim⟧ |
| `agri_3` | grape | 11 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_3@labels.species⟧ ⟦S:INS-MMBench:qid=agri_3@labels.count⟧ ⟦S:INS-MMBench:qid=agri_3@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_3@labels.claim⟧ |
| `agri_4` | grape | 9 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_4@labels.species⟧ ⟦S:INS-MMBench:qid=agri_4@labels.count⟧ ⟦S:INS-MMBench:qid=agri_4@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_4@labels.claim⟧ |
| `agri_5` | grape | 8 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_5@labels.species⟧ ⟦S:INS-MMBench:qid=agri_5@labels.count⟧ ⟦S:INS-MMBench:qid=agri_5@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_5@labels.claim⟧ |
| `agri_6` | grape | 0 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_6@labels.species⟧ ⟦S:INS-MMBench:qid=agri_6@labels.count⟧ ⟦S:INS-MMBench:qid=agri_6@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_6@labels.claim⟧ |
| `agri_7` | grape | 0 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_7@labels.species⟧ ⟦S:INS-MMBench:qid=agri_7@labels.count⟧ ⟦S:INS-MMBench:qid=agri_7@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_7@labels.claim⟧ |
| `agri_8` | grape | 0 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_8@labels.species⟧ ⟦S:INS-MMBench:qid=agri_8@labels.count⟧ ⟦S:INS-MMBench:qid=agri_8@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_8@labels.claim⟧ |
| `agri_9` | grape | 0 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_9@labels.species⟧ ⟦S:INS-MMBench:qid=agri_9@labels.count⟧ ⟦S:INS-MMBench:qid=agri_9@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_9@labels.claim⟧ |
| `agri_10` | grape | 0 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_10@labels.species⟧ ⟦S:INS-MMBench:qid=agri_10@labels.count⟧ ⟦S:INS-MMBench:qid=agri_10@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_10@labels.claim⟧ |
| `agri_11` | grape | 0 | NO | No Compensation | ⟦S:INS-MMBench:qid=agri_11@labels.species⟧ ⟦S:INS-MMBench:qid=agri_11@labels.count⟧ ⟦S:INS-MMBench:qid=agri_11@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_11@labels.claim⟧ |

- 以本子集 12 条 agri 样本为准，判断类字段 `claim` 的取值分布为 Partial Compensation×2/No Compensation×10（证据：上表逐行）⟦S:INS-MMBench:qids=agri_0..agri_11@labels.claim⟧
- 可用于回答的字段清单（与本页 `source_refs` 同集合）：`species`, `count`, `infection`, `claim` ⟦S:INS-MMBench:qid=agri_0@labels.species⟧ ⟦S:INS-MMBench:qid=agri_0@labels.count⟧ ⟦S:INS-MMBench:qid=agri_0@labels.infection⟧ ⟦S:INS-MMBench:qid=agri_0@labels.claim⟧

## 3. 本页不回答什么

- 不给出条款级依据：本子集无条款文本，且 `answer` 列不存在（`answer_status=absent_in_source`）⟦S:INS-MMBench:qid=agri_0@answer_status⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-agricultural]] `claims-doc-ins-mmbench-agricultural`
