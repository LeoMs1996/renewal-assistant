---
id: claims-section-liability-environment
type: section
title: 天气与光照条件（auto_liability_determination）
domain: claims
insurance_line: auto_liability
summary: weather/light 在 12 条 liability 样本中的字段事实与题干规约（逐条 span 可回溯）。
tags: [ins-mmbench, liability, section]
source_refs: [INS-MMBench:qid=liability_0, INS-MMBench:qid=liability_1, INS-MMBench:qid=liability_3, INS-MMBench:qid=liability_4, INS-MMBench:qid=liability_6, INS-MMBench:qid=liability_8, INS-MMBench:qid=liability_10, INS-MMBench:qid=liability_12, INS-MMBench:qid=liability_16, INS-MMBench:qid=liability_17, INS-MMBench:qid=liability_19, INS-MMBench:qid=liability_20]
raw_refs: [raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020]
updated: 2026-11-18
related: [claims-doc-ins-mmbench-auto, claims-section-liability-accident-occurrence, claims-section-liability-causation, claims-section-liability-scene-context]
status: verified
---
# 天气与光照条件（auto_liability_determination）

> 本页只陈述本子集中 `weather`, `light` 的 12 条样本事实与题干规约，不引入外部条款知识。

## 1. 题干规约（逐字，取首单元 `liability_0`）

> 1. Weather: Identify the prevailing weather conditions in the images. (sunny, rainy, snowy, foggy)

⟦S:INS-MMBench:qid=liability_0@L2-L2⟧

> Please strictly output in the following format:
> 1. Weather: sunny/rainy/snowy/foggy
> 2. Scene: highway/tunnel/mountain/urban/rural
> 3. Linear: arterials/curve/intersection/T-junction/ramp
> 4. Accident Occurred: Yes/No.
> 5. Accident Cause: one sentence brief description
> 6. Main Responsible Party: Ego-car/Pedestrian/Other car/Both

⟦S:INS-MMBench:qid=liability_0@L9-L15⟧

## 2. 样本事实（逐行 span 级）

| qid | `weather` | `light` | 原文定位 |
|---|---|---|---|
| `liability_0` | sunny | night | ⟦S:INS-MMBench:qid=liability_0@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_0@labels.light⟧ |
| `liability_1` | sunny | day | ⟦S:INS-MMBench:qid=liability_1@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_1@labels.light⟧ |
| `liability_3` | sunny | day | ⟦S:INS-MMBench:qid=liability_3@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_3@labels.light⟧ |
| `liability_4` | sunny | day | ⟦S:INS-MMBench:qid=liability_4@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_4@labels.light⟧ |
| `liability_6` | sunny | day | ⟦S:INS-MMBench:qid=liability_6@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_6@labels.light⟧ |
| `liability_8` | sunny | day | ⟦S:INS-MMBench:qid=liability_8@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_8@labels.light⟧ |
| `liability_10` | sunny | day | ⟦S:INS-MMBench:qid=liability_10@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_10@labels.light⟧ |
| `liability_12` | sunny | day | ⟦S:INS-MMBench:qid=liability_12@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_12@labels.light⟧ |
| `liability_16` | sunny | day | ⟦S:INS-MMBench:qid=liability_16@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_16@labels.light⟧ |
| `liability_17` | sunny | night | ⟦S:INS-MMBench:qid=liability_17@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_17@labels.light⟧ |
| `liability_19` | sunny | day | ⟦S:INS-MMBench:qid=liability_19@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_19@labels.light⟧ |
| `liability_20` | sunny | day | ⟦S:INS-MMBench:qid=liability_20@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_20@labels.light⟧ |

## 3. 聚合观察（派生自上表，不是外部知识）

- 12/12 条样本均具备上述字段；取值分布：weather=sunny×12；light=night×2/day×10（证据：§2 全 12 行）⟦S:INS-MMBench:qids=liability_0..liability_1@labels.weather⟧ ⟦S:INS-MMBench:qids=liability_3..liability_4@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_6@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_8@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_10@labels.weather⟧ ⟦S:INS-MMBench:qid=liability_12@labels.weather⟧ ⟦S:INS-MMBench:qids=liability_16..liability_17@labels.weather⟧ ⟦S:INS-MMBench:qids=liability_19..liability_20@labels.weather⟧
- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；该句是评测口径约束，不是样本事实，故不挂引用标记

## 4. 相关条目

- [[claims-doc-ins-mmbench-auto]] `claims-doc-ins-mmbench-auto`
- [[claims-section-liability-accident-occurrence]] `claims-section-liability-accident-occurrence`
- [[claims-section-liability-causation]] `claims-section-liability-causation`
- [[claims-section-liability-scene-context]] `claims-section-liability-scene-context`
