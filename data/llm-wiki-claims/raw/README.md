# data/llm-wiki-claims/raw/ —— 抽样原文（溯源证据，**入库**）

> 状态：**D2 已落地**（2026-11-18）。54 个源单元 + 1 份清单，全部由脚本生成，**勿手改**。
> 生成器：`data/llm-wiki-claims/scripts/normalize_raw.py`（`build` 生成 / `check` 校验）。
> 规范依据：`docs/research/llmwiki-spec.md`（R1 定稿）§2 raw 层职责与 §6 断言级引用。

## 这里放什么

从 INS-MMBench 抽出的**原文片段与其元数据**，是 LLM-Wiki 条目的**上游证据**（只读层）：

```
data/ins-mmbench/raw/<split>/records.jsonl      ← D1 抽样（不入库，源材料）
        ↓ D2 规范化（本脚本，不改写/不摘要/不翻译）
data/llm-wiki-claims/raw/sources/*.json         ← 本目录：每单元一个源文件（入库）
        ↓ D3 编译（一次一个单元）
data/llm-wiki-claims/wiki/*.md                  ← LLM-Wiki 条目（入库）
```

## 目录

| 路径 | 内容 | 入库 |
|---|---|---|
| `raw/sources/raw-<split>-<index:04d>.json` | **54** 个源单元（一条抽样记录 = 一个单元） | 是 |
| `raw/manifest.json` | 源清单：id / split / source_index / records_line / sha256 / 图片 / ingest 顺序 | 是 |
| `raw/assets/` | **不放图片**，只放说明（见该目录 README） | 是 |
| `../plan.md` | 三层切分与页面清单（D3 执行契约） | 是 |

## 源文件 schema（`d2-raw-1.0`）

| 字段 | 说明 |
|---|---|
| `raw_id` | 稳定 id：`raw-<split>-<source_index:04d>`，**不含随机数与时间戳**，重跑不变 |
| `unit` | `{unit_id, kind:"record", sub_units:["question","labels","images"], ingest_order}` |
| `source` | `dataset / revision(commit sha) / license / split / source_file / source_index / record_id / records_path / records_line / record_line_sha256` —— 反查 `records.jsonl` 的**行号与内容哈希** |
| `sample` | `insurance_type / task_layer / task_name / meta_task`（原样） |
| `content` | `question{text,chars,lines,sha256}` + `options` + `answer`（后两者原样，本子集均为 `null`） |
| `answer_status` | 恒为 `absent_in_source`：场景分片本身无 `answer` 列（D1/R2 实测），**不得据此编造标准答案** |
| `labels` | 原始标签字典，**逐字保留**（键顺序同源） |
| `images[]` | `path / bytes / sha256 / asset_ref / asset_sha256_verified` |
| `spans` | `question`（行号 1-based）/ `labels`（JSON 路径）/ `images`（asset 引用） |

## 引用写法（D3 用）

| 证据 | 写法 |
|---|---|
| 题干行 | `⟦S:raw-claim-0000@L3-L7⟧`（`content.question.text` 按 `\n` 切行） |
| 标签字段 | `⟦S:raw-claim-0000@labels.Amount⟧` |
| 图片 | `⟦S:raw-claim-0000@claim/0/0.jpg⟧` |

## 图片为什么不在本目录

图片共 120 张 / 33 MiB，已在 D1 落到 `data/ins-mmbench/raw/<split>/<index>/`（该目录被 gitignore，属可重取的输入）。
本层只记 `asset_ref`（仓库相对路径）+ `bytes` + `sha256`，**不复制**：避免 33 MiB 重复入库，同时保证可校验。
代价与处置见 `raw/assets/README.md` 与 `../plan.md` §8。

## 幂等与校验（改任何东西前后都要跑）

```bash
python3 data/llm-wiki-claims/scripts/normalize_raw.py build   # 重新生成（幂等）
python3 data/llm-wiki-claims/scripts/normalize_raw.py check   # 只校验；不一致 exit 1
```

`check` 覆盖：54 个源文件与清单一致、内容逐字节可复现（连跑两次 sha256 相同）、无孤立源文件。
生成器在 build 时还会**逐张校验 120 张图片的 sha256**，并在校验脚本里逐记录核对 `question`/`labels`/`answer` 与
`records.jsonl` 逐字一致（不一致直接 FAIL 退出）。

## 硬规则

- 一切文本为公开数据集（INS-MMBench，Apache-2.0，revision `b77ea65c…`）；真实 PII 禁止入内。
- **禁止改写**：`question`/`labels` 必须与 `records.jsonl` 逐字一致；需要「解释」的内容属于 `wiki/` 层，不属于 `raw/`。
- 修正源数据只能靠重跑生成器（改输入或改脚本），不得手改 `raw/sources/*.json`。
