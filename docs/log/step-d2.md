# step-d2 指针

完整日志（四件套 + 验证输出）在 **`docs/log/step-d2-normalize.md`**（文件名以任务契约为准）。

为避免两处维护，本文件只作指针。D2 的一行摘要：

> 54 条抽样记录 → `data/llm-wiki-claims/raw/sources/` 54 个不可变源单元（`raw-<split>-<idx4>.json`）+ `raw/manifest.json` + `plan.md`（36 页 / 三层切分 / 单元→页面映射）；
> 生成器 `scripts/normalize_raw.py` 幂等（连跑两次 56 产物 sha256 一致）、`check` 校验 54/54 覆盖率 + 120 图 sha256 + 逐字保真；
> `wiki/`、续保 `wiki/`、`server/`、`traces/` 零改动。
