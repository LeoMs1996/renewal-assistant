---
id: claims-section-liability-causation
type: section
title: 事故成因与主责（auto_liability_determination）
domain: claims
insurance_line: auto_liability
summary: causes/primary_responsibility 在 12 条 liability 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, liability, section]
source_refs: [INS-MMBench:qid=liability_0, INS-MMBench:qid=liability_1, INS-MMBench:qid=liability_3, INS-MMBench:qid=liability_4, INS-MMBench:qid=liability_6, INS-MMBench:qid=liability_8, INS-MMBench:qid=liability_10, INS-MMBench:qid=liability_12, INS-MMBench:qid=liability_16, INS-MMBench:qid=liability_17, INS-MMBench:qid=liability_19, INS-MMBench:qid=liability_20]
raw_refs: [raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-entity-primary-responsibility, claims-section-liability-accident-occurrence, claims-section-liability-environment, claims-section-liability-scene-context]
status: verified
---
# 事故成因与主责（auto_liability_determination）

> 本页只陈述本子集中 `causes`, `primary_responsibility` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `liability_0`）

> Please strictly output in the following format:
> 1. Weather: sunny/rainy/snowy/foggy
> 2. Scene: highway/tunnel/mountain/urban/rural
> 3. Linear: arterials/curve/intersection/T-junction/ramp
> 4. Accident Occurred: Yes/No.
> 5. Accident Cause: one sentence brief description
> 6. Main Responsible Party: Ego-car/Pedestrian/Other car/Both

⟦S:INS-MMBench:qid=liability_0@L9-L15⟧

## 2. 样本事实（逐行 span 级）

| qid | `causes` | `primary_responsibility` | 原文定位 |
|---|---|---|---|
| `liability_0` | The vehicles does not notice the coming vehicles when crossing the road | Both | ⟦S:INS-MMBench:qid=liability_0@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_0@labels.primary_responsibility⟧ |
| `liability_1` | The ego-car's vision is blocked or blurred, and there is no time to brake | Ego-car | ⟦S:INS-MMBench:qid=liability_1@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_1@labels.primary_responsibility⟧ |
| `liability_3` | vehicles do not notice the coming vehicles when turning or changling lanes | Both | ⟦S:INS-MMBench:qid=liability_3@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_3@labels.primary_responsibility⟧ |
| `liability_4` | Ego-car evades other vehicles, pedestrians or objects and changes lanes emergen… | Ego-car | ⟦S:INS-MMBench:qid=liability_4@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_4@labels.primary_responsibility⟧ |
| `liability_6` | Ego-car turns or changes lanes without giving way to normal vehicles in the lane | Ego-car | ⟦S:INS-MMBench:qid=liability_6@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_6@labels.primary_responsibility⟧ |
| `liability_8` | vehicles drive too fast with short braking distance | Both | ⟦S:INS-MMBench:qid=liability_8@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_8@labels.primary_responsibility⟧ |
| `liability_10` | Ego-car turns or changes lanes without giving way to normal vehicles in the lane | Ego-car | ⟦S:INS-MMBench:qid=liability_10@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_10@labels.primary_responsibility⟧ |
| `liability_12` | vehicles do not give way to normal driving vehicles when turning or changing la… | Both | ⟦S:INS-MMBench:qid=liability_12@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_12@labels.primary_responsibility⟧ |
| `liability_16` | Ego-car drives too fast and the braking distance is short | Ego-car | ⟦S:INS-MMBench:qid=liability_16@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_16@labels.primary_responsibility⟧ |
| `liability_17` | vehicles drive too fast with short braking distance | Both | ⟦S:INS-MMBench:qid=liability_17@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_17@labels.primary_responsibility⟧ |
| `liability_19` | vehicles drive too fast with short braking distance | Both | ⟦S:INS-MMBench:qid=liability_19@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_19@labels.primary_responsibility⟧ |
| `liability_20` | Pedestrian does not notice the coming vehicles when crossing the street | Pedestrian | ⟦S:INS-MMBench:qid=liability_20@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_20@labels.primary_responsibility⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：causes=The vehicles does not n…×1/The ego-car's vision is…×1/vehicles do not notice …×1/Ego-car evades other ve…×1/Ego-car turns or change…×2/vehicles drive too fast…×3/vehicles do not give wa…×1/Ego-car drives too fast…×1/Pedestrian does not not…×1；primary_responsibility=Both×6/Ego-car×5/Pedestrian×1（证据：§2 全 12 行）⟦S:INS-MMBench:qids=liability_0..liability_1@labels.causes⟧ ⟦S:INS-MMBench:qids=liability_3..liability_4@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_6@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_8@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_10@labels.causes⟧ ⟦S:INS-MMBench:qid=liability_12@labels.causes⟧ ⟦S:INS-MMBench:qids=liability_16..liability_17@labels.causes⟧ ⟦S:INS-MMBench:qids=liability_19..liability_20@labels.causes⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-entity-primary-responsibility]] `claims-entity-primary-responsibility`
- [[claims-section-liability-accident-occurrence]] `claims-section-liability-accident-occurrence`
- [[claims-section-liability-environment]] `claims-section-liability-environment`
- [[claims-section-liability-scene-context]] `claims-section-liability-scene-context`
