---
id: claims-entity-primary-responsibility
type: entity
title: 事故主责判定
domain: claims
insurance_line: auto_liability
summary: primary_responsibility/causes 实体登记：12 个单元，逐属性可回溯。
tags: [ins-mmbench, liability, entity]
source_refs: [INS-MMBench:qid=liability_0, INS-MMBench:qid=liability_1, INS-MMBench:qid=liability_3, INS-MMBench:qid=liability_4, INS-MMBench:qid=liability_6, INS-MMBench:qid=liability_8, INS-MMBench:qid=liability_10, INS-MMBench:qid=liability_12, INS-MMBench:qid=liability_16, INS-MMBench:qid=liability_17, INS-MMBench:qid=liability_19, INS-MMBench:qid=liability_20]
raw_refs: [raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020]
updated: 2026-11-18
related: [claims-section-liability-causation]
status: verified
---
# 事故主责判定（实体页）

> 本页把「事故主责判定」登记为跨样本实体：只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。

## 1. 字段出处（逐字，取首单元 `liability_0`）

> Please strictly output in the following format:
> 1. Weather: sunny/rainy/snowy/foggy
> 2. Scene: highway/tunnel/mountain/urban/rural
> 3. Linear: arterials/curve/intersection/T-junction/ramp
> 4. Accident Occurred: Yes/No.
> 5. Accident Cause: one sentence brief description
> 6. Main Responsible Party: Ego-car/Pedestrian/Other car/Both

⟦S:INS-MMBench:qid=liability_0@L9-L15⟧

## 2. 属性事实（逐单元、逐属性带标记）

| qid | `primary_responsibility` | `causes` | 原文定位 |
|---|---|---|---|
| `liability_0` | Both | The vehicles does not notice the coming… | ⟦S:INS-MMBench:qid=liability_0@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_0@labels.causes⟧ |
| `liability_1` | Ego-car | The ego-car's vision is blocked or blur… | ⟦S:INS-MMBench:qid=liability_1@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_1@labels.causes⟧ |
| `liability_3` | Both | vehicles do not notice the coming vehic… | ⟦S:INS-MMBench:qid=liability_3@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_3@labels.causes⟧ |
| `liability_4` | Ego-car | Ego-car evades other vehicles, pedestri… | ⟦S:INS-MMBench:qid=liability_4@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_4@labels.causes⟧ |
| `liability_6` | Ego-car | Ego-car turns or changes lanes without … | ⟦S:INS-MMBench:qid=liability_6@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_6@labels.causes⟧ |
| `liability_8` | Both | vehicles drive too fast with short brak… | ⟦S:INS-MMBench:qid=liability_8@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_8@labels.causes⟧ |
| `liability_10` | Ego-car | Ego-car turns or changes lanes without … | ⟦S:INS-MMBench:qid=liability_10@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_10@labels.causes⟧ |
| `liability_12` | Both | vehicles do not give way to normal driv… | ⟦S:INS-MMBench:qid=liability_12@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_12@labels.causes⟧ |
| `liability_16` | Ego-car | Ego-car drives too fast and the braking… | ⟦S:INS-MMBench:qid=liability_16@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_16@labels.causes⟧ |
| `liability_17` | Both | vehicles drive too fast with short brak… | ⟦S:INS-MMBench:qid=liability_17@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_17@labels.causes⟧ |
| `liability_19` | Both | vehicles drive too fast with short brak… | ⟦S:INS-MMBench:qid=liability_19@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_19@labels.causes⟧ |
| `liability_20` | Pedestrian | Pedestrian does not notice the coming v… | ⟦S:INS-MMBench:qid=liability_20@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_20@labels.causes⟧ |

## 3. 取值分布（派生自 §2，不是外部知识）

- 本实体在子集中出现于 12 个单元（liability 分片），每个属性均可在 §2 对应单元格回溯；取值分布：primary_responsibility=Both×6/Ego-car×5/Pedestrian×1；causes=The vehicles does not n…×1/The ego-car's vision is…×1/vehicles do not notice …×1/Ego-car evades other ve…×1/Ego-car turns or change…×2/vehicles drive too fast…×3/vehicles do not give wa…×1/Ego-car drives too fast…×1/Pedestrian does not not…×1⟦S:INS-MMBench:qids=liability_0..liability_1@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qids=liability_3..liability_4@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_6@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_8@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_10@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qid=liability_12@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qids=liability_16..liability_17@labels.primary_responsibility⟧ ⟦S:INS-MMBench:qids=liability_19..liability_20@labels.primary_responsibility⟧
- 属性个数：2（`primary_responsibility`, `causes`）；本页不含任何未在上述单元格出现过的取值⟦S:INS-MMBench:qid=liability_0@labels.primary_responsibility⟧

## 4. 相关条目

- [[claims-section-liability-causation]] `claims-section-liability-causation`
