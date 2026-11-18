---
id: claims-faq-liability
type: faq
title: 如何判定事故是否发生以及主责归属？
domain: claims
insurance_line: auto_liability
summary: liability 任务语料能支持到的回答范围（12 条样本，逐条引用）。
tags: [ins-mmbench, liability, faq]
source_refs: [INS-MMBench:qid=liability_0, INS-MMBench:qid=liability_1, INS-MMBench:qid=liability_3, INS-MMBench:qid=liability_4, INS-MMBench:qid=liability_6, INS-MMBench:qid=liability_8, INS-MMBench:qid=liability_10, INS-MMBench:qid=liability_12, INS-MMBench:qid=liability_16, INS-MMBench:qid=liability_17, INS-MMBench:qid=liability_19, INS-MMBench:qid=liability_20]
raw_refs: [raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto]
status: verified
---
# 如何判定事故是否发生以及主责归属？

> 本页只回答「本子集语料能支持到什么程度」：答案由样本字段与题干规约拼成，不是业务建议。

目录中的问题：仅凭连续行车记录仪图像，如何逐步判定是否发生事故、成因与主要责任方？

## 1. 题干规约（逐字，取首单元 `liability_0`）

> Please strictly output in the following format:
> 1. Weather: sunny/rainy/snowy/foggy
> 2. Scene: highway/tunnel/mountain/urban/rural
> 3. Linear: arterials/curve/intersection/T-junction/ramp
> 4. Accident Occurred: Yes/No.
> 5. Accident Cause: one sentence brief description
> 6. Main Responsible Party: Ego-car/Pedestrian/Other car/Both

⟦S:INS-MMBench:qid=liability_0@L9-L15⟧

## 2. 本子集能给出的答案（逐条引用）

| qid | `weather` | `light` | `scenes` | `linear` | `whether an accident occurred` | `causes` | `primary_responsibility` | 原文定位 |
|---|---|---|---|---|---|---|---|---|
| `liability_0` | sunny | night | urban | intersection | Yes | The vehicles does not n… | Both | ⟦S:INS-MMBench:qid=liability_0@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_0@labels.light⟧ ⟦S:INS-MMBench:qid=liability_0@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_0@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_0@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_0@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_0@labels.primary_responsibility⟧ |
| `liability_1` | sunny | day | rural | T-junction | Yes | The ego-car's vision is… | Ego-car | ⟦S:INS-MMBench:qid=liability_1@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_1@labels.light⟧ ⟦S:INS-MMBench:qid=liability_1@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_1@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_1@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_1@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_1@labels.primary_responsibility⟧ |
| `liability_3` | sunny | day | urban | arterials | Yes | vehicles do not notice … | Both | ⟦S:INS-MMBench:qid=liability_3@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_3@labels.light⟧ ⟦S:INS-MMBench:qid=liability_3@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_3@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_3@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_3@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_3@labels.primary_responsibility⟧ |
| `liability_4` | sunny | day | urban | arterials | Yes | Ego-car evades other ve… | Ego-car | ⟦S:INS-MMBench:qid=liability_4@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_4@labels.light⟧ ⟦S:INS-MMBench:qid=liability_4@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_4@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_4@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_4@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_4@labels.primary_responsibility⟧ |
| `liability_6` | sunny | day | urban | arterials | Yes | Ego-car turns or change… | Ego-car | ⟦S:INS-MMBench:qid=liability_6@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_6@labels.light⟧ ⟦S:INS-MMBench:qid=liability_6@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_6@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_6@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_6@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_6@labels.primary_responsibility⟧ |
| `liability_8` | sunny | day | urban | intersection | Yes | vehicles drive too fast… | Both | ⟦S:INS-MMBench:qid=liability_8@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_8@labels.light⟧ ⟦S:INS-MMBench:qid=liability_8@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_8@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_8@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_8@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_8@labels.primary_responsibility⟧ |
| `liability_10` | sunny | day | urban | T-junction | Yes | Ego-car turns or change… | Ego-car | ⟦S:INS-MMBench:qid=liability_10@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_10@labels.light⟧ ⟦S:INS-MMBench:qid=liability_10@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_10@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_10@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_10@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_10@labels.primary_responsibility⟧ |
| `liability_12` | sunny | day | urban | curve | Yes | vehicles do not give wa… | Both | ⟦S:INS-MMBench:qid=liability_12@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_12@labels.light⟧ ⟦S:INS-MMBench:qid=liability_12@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_12@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_12@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_12@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_12@labels.primary_responsibility⟧ |
| `liability_16` | sunny | day | rural | intersection | Yes | Ego-car drives too fast… | Ego-car | ⟦S:INS-MMBench:qid=liability_16@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_16@labels.light⟧ ⟦S:INS-MMBench:qid=liability_16@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_16@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_16@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_16@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_16@labels.primary_responsibility⟧ |
| `liability_17` | sunny | night | urban | intersection | Yes | vehicles drive too fast… | Both | ⟦S:INS-MMBench:qid=liability_17@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_17@labels.light⟧ ⟦S:INS-MMBench:qid=liability_17@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_17@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_17@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_17@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_17@labels.primary_responsibility⟧ |
| `liability_19` | sunny | day | urban | T-junction | Yes | vehicles drive too fast… | Both | ⟦S:INS-MMBench:qid=liability_19@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_19@labels.light⟧ ⟦S:INS-MMBench:qid=liability_19@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_19@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_19@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_19@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_19@labels.primary_responsibility⟧ |
| `liability_20` | sunny | day | urban | arterials | Yes | Pedestrian does not not… | Pedestrian | ⟦S:INS-MMBench:qid=liability_20@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_20@labels.light⟧ ⟦S:INS-MMBench:qid=liability_20@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_20@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_20@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_20@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_20@labels.primary_responsibility⟧ |

- 以本子集 12 条 liability 样本为准，判断类字段 `primary_responsibility` 的取值分布为 Both×6/Ego-car×5/Pedestrian×1（证据：上表逐行）⟦S:INS-MMBench:qids=liability_0..liability_1@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qids=liability_3..liability_4@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_6@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_8@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_10@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_12@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qids=liability_16..liability_17@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qids=liability_19..liability_20@labels.primary_responsibility⟧
- 可用于回答的字段清单（与本页 `source_refs` 同集合）：`weather`, `light`, `scenes`, `linear`, `whether an accident occurred`, `causes`, `primary_responsibility` ⟦S:INS-MMBench:qid=liability_0@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_0@labels.light⟧ ⟦S:INS-MMBench:qid=liability_0@labels.scenes⟧ ⟦S:INS-MMBench:qid=liability_0@labels.linear⟧ ⟦S:INS-MMBench:qid=liability_0@labels.whether an accident occurred⟧ ⟦S:INS-MMBench:qid=liability_0@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_0@labels.primary_responsibility⟧

## 3. 本页不回答什么

- 不给出条款级依据：本子集无条款文本，且 `answer` 列不存在（`answer_status=absent_in_source`）⟦S:INS-MMBench:qid=liability_0@answer_status⟧

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
