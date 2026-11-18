# data/ins-mmbench/ —— INS-MMBench 数据集（大文件，**不入库**）

> 状态：C0 占位（仅 `.gitkeep`）。建立于 2026-11-17。

## 为什么整个目录被 gitignore

数据集体积远超版本库合理承载：

- GitHub 官方：单文件 >50 MiB 会告警、>100 MiB 直接拒收，仓库建议 <1 GB（依据：`docs/log/step-c0-baseline.md` 第 8 节 S2）。
- 数据集属于「可重新获取的输入」，不是源码；入库只会让 clone 变慢、diff 变噪声。

`.gitignore` 用「忽略全部 + 白名单保留占位」的写法（依据 S1 的 gitignore pattern 语义）：

```gitignore
data/ins-mmbench/**
!data/ins-mmbench/.gitkeep
!data/ins-mmbench/README.md
```

即：**目录骨架入库，数据内容不入库**。

## 预期的目录约定（C1 落地时确认）

> ⚠️ **R2 研究已修正本节**：上游**没有 `jsonl`/`parquet`**，只有 6 个 `.tsv`，且**图片是 base64 内联在 `image` 列里**（没有独立图片文件）。以「## R2 研究结论（2026-11-18）」一节为准。

```text
data/ins-mmbench/
├── raw/            # 上游原始文件（实测为 6 个 .tsv 的头部 Range 片段 *.tsv.head）
├── subset/         # C1 抽样产物（questions.jsonl + images/）
├── manifest.json   # 抽样清单：来源版本、抽样种子、条数、文件 sha256
└── README.md       # 本文件
```
`manifest.json` 是 C1 的验收物之一：**没有 manifest 的抽样结果不予采纳**（无法复现）。

## 获取方式

数据集不随仓库分发。C1 负责：

1. 用外部检索确认数据集的**当前获取渠道与许可**（≥3 来源，记 URL + 时间 + 用途）；
2. 把获取步骤写成 `data/ins-mmbench/FETCH.md`（命令 + 校验和），不把数据提交进库；
3. 抽样必须**确定性可复现**（固定种子 + 记录种子值）。

## 隐私与合规

- 数据集仅用于评测/研究，输出须标注来源。
- 若数据集中含真实个人信息字段，抽样时即脱敏，脱敏规则写进 `manifest.json`。

## 当前内容

`.gitkeep`（占位）+ `README.md`（本文件）+ `FETCH.md`（R2 产出的获取步骤草案）。**没有任何数据文件。**

---

## R2 研究结论（2026-11-18，dataset-lead）
完整报告：`renewal-assistant/docs/research/ins-mmbench-access.md`（R2 产出，唯一存放处）。

### 上游真实形态（与上文「预期」不符，已实测确认）

| 预期 | 实际（HTTP Range 实读 + HF API） |
|---|---|
| `raw/*.jsonl` 或 `*.parquet` | ❌ 不存在。全部是 **6 个 `.tsv`**，合计 **2,900,191,262 B（2.70 GiB）** |
| 图片文件可单独下载 | ❌ 不存在图片文件。图片是 **base64 内联**在 `image` 列（JPEG `/9j/`、PNG `iVBORw0KGgo`） |
| `datasets.load_dataset` 可用 | ❌ 无 parquet / 无 `dataset_infos.json` / 无 builder；datasets-server 与 parquet 端点不可达 |
| HF 直连可下 | ❌ `huggingface.co` 本机 30 s 超时；**必须** `HF_ENDPOINT=https://hf-mirror.com` |

### 许可

**Apache-2.0**（HF `cardData.license` + dataset card YAML 双重确认）。汇编自 CCPD / Stanford Cars / VQA-Med 2019 / xBD / DADA / IU-XRay 等上游数据集，**上游原始许可可能更严格**；本子集仅用于课程作业与研究，不得商用。引用见 `FETCH.md`。

### 抽样确定性说明（回应「固定种子」要求）

本方案不引入随机种子，而是**确定性的「头部前 k 条完整记录」**（`strategy=head_k_complete_records`, `seed=null`）：

- `manifest.json` 记录：`revision`（pin 的 commit sha `b77ea65c18c61108a32b811ca344308941ff8046`）、每个源文件的 `bytes_fetched` / `records` / `chunks` / **实际 HTTP Range 列表** / 结果 `sha256`、`endpoint`、`fetched_at`、`k`；
- **⚠ 实测修正（2026-11-18 03:04）**：先前写的「文件内记录同分布 → 头部 k 条等价于无偏样本」**不准确**。实测发现源文件内部**按标签排序**：`multi_step_claim.tsv` 前 12 条的 `Severity` **全部是 `minor`**；`agri` 的 `species` 全为 `grape`；`liability` 的 `weather` 全为 `sunny`、`whether an accident occurred` 全为 `Yes`；`property` 的 `disaster` 全为 `yes`；`health` 的 `part` 全为 `chest`、`match` 全为 `yes`。
  → 因此本子集**不是标签均衡的分层样本**，而是「文件顺序前 k 条」。它足以支撑**检索**类评测（Hit@1 / MRR@5 / 引用接地率），**不能**用于报告分类准确率。这与 D-04（排除 `fundamental.tsv`、只报检索指标）的结论一致，并进一步支持它。
- 若后续要做标签均衡的分层抽样，需引入 `seed` 并改成按标签桶取样（目前**未做**）。

> ⚠️ **抽样语义警示（D1b 审计修正，用前必读）**：`strategy` **不是全分片统一的**。
> `claim` / `agri` / `health` / `property` 是严格 head-k（`source_index` 0..k-1 连续）；
> **`liability` 是 `head_window_complete_records`** —— 在 8×3MiB 窗口内取前 12 条可完整解析记录，
> **跳过了 `[2,5,7,9,11,13,14,15,18]` 共 9 条**（index 序列 `0,1,3,4,6,8,10,12,16,17,19,20`）。
> 数据本身**未损坏**（54 条均完整、sha256 可校），但 liability 的 12 条**不是“前 12 条”**。
> 量化：保留的 12 条平均 **1019.4 KiB**，被跳过的 9 条反推 **705–873 KiB**（中心 816）→ 保留/跳过 = **1.17–1.45×**，
> 即**大记录被过度代表**（方向与“大记录更易丢失”的假设相反）。
> 注意 liability **没有任何金额字段**，记录大小≈5 张 JPEG 的字节量，**不可**据此推断“小额/大额案件”的偏差。
> 逐分片实情见 `manifest.json` → `splits.<name>.strategy / strict_head_k / source_indices_taken / source_indices_skipped`，
> 完整分析见 `docs/log/step-d1.md` §4.9。**本子集只能当“真实、完整、可复现”的样本，不能当“无偏、可推断总体”的样本。**

### 一条硬约束（不要违反）

**禁止随机 byte-range 切块抽样**：实测单条记录内 base64 字段可达 876 KB 无换行，6 个随机 512 KB 窗口中 5 个取不到任何完整记录。只能「从头顺序读 / 头部 Range + 顺序追加」。详见报告 §6.4。

**另一个坑（D1 实测）**：`multi_step_property.tsv` 单条记录约 4 MB，**大于一次 3 MiB 的 Range**。因此它必须：① 用 1 MiB 分块；② 让 carry 跨多个 chunk 累积到一个完整记录。实现上必须用**两个游标**（`next_pos`=carry 起点用于跨进程恢复；`pos`=本次抓取位置，单调前进），混用会导致重叠读 → 缓冲区来回振荡死循环。

---

## 逐文件字段清单与 ground truth 归类（D1，2026-11-18）

> 列名均为**实测 header**（`manifest.json` → `splits.<name>.header`），非推测。
> 证据落盘：`data/ins-mmbench/raw/<split>/records.jsonl`（54 条，含全部 metadata 字段）。
> 图例：✅GT = 可直接作 ground truth；⚠GT = 可作标签但需 D2/D5 确认口径；— = 输入/元数据，不可作 GT。

### `claim`（multi_step_claim.tsv，12 列，12 条，1 图/条）
| 字段 | 实测取值 | 归类 |
|---|---|---|
| `index` | 0..11 | — 主键 |
| `image` | base64 JPEG ×1 | — 输入 |
| `Cost_of_vehicle` / `Min_coverage` / `Max_coverage` / `Expiry_date` | 数值 / 2021-11-12 等 | — 题面给定条件（写在 `question` 里） |
| `Condition` | 本 12 条恒 `1` | ⚠GT 车况（二分类，本子集无变化） |
| `Amount` | 305.0 … 4043.0 | ⚠GT 维修估价（数值回归） |
| `Severity` | 本 12 条恒 `minor`（全库 minor150/moderate150/severe100） | ✅GT 损伤严重度（3 分类，本子集仅 1 类） |
| `expired` | `0` / `1` | ⚠GT 保单是否过期（二分类） |
| `claim` | `0.0` … `3607.0`（8 个不同值） | ✅GT 最终赔付额（数值回归） |
| `question` | 含 5 步输出模板 | — 输入 |

### `agri`（multi_step_agri.tsv，7 列，12 条，1 图/条）
| 字段 | 实测取值 | 归类 |
|---|---|---|
| `index` / `image` / `question` | — | — 主键 / 输入 |
| `species` | 本 12 条恒 `grape` | ✅GT 作物种类（分类，本子集仅 1 类） |
| `count` | `0`,`1`,`2`,`8`,`11` | ✅GT 果实计数（数值） |
| `infection` | `NO` / `YES` | ✅GT 病害二分类（本子集两值均有） |
| `claim` | `No Compensation` / `Partial Compensation` | ✅GT 理赔决定（3 分类中本子集 2 类） |

### `health`（multi_step_health.tsv，10 列，12 条，2 图/条）
| 字段 | 实测取值 | 归类 |
|---|---|---|
| `index` / `image`（list 字面量） / `image_path`（list 字面量） | — | — 主键 / 输入 / 元数据（原图路径，可追溯） |
| `part` | 本 12 条恒 `chest` | ✅GT 部位分类（本子集仅 1 类） |
| `original_report` / `adjusted_report` | 放射报告文本（11 个不同值） | — 输入（喂给模型的已知信息） |
| `match` | 本 12 条恒 `yes` | ⚠GT 报告-影像一致性（二分类） |
| `risk_level` | `no risk` / `mild risk` / `severe risk` | ✅GT 风险等级（3 分类） |
| `underwriting_decision` | `Standard` / `Higher Premium` / `Declined` | ✅GT 核保决定（3 分类） |

### `liability`（multi_step_liability.tsv，11 列，12 条，5 图/条）
| 字段 | 实测取值 | 归类 |
|---|---|---|
| `index` / `image`（list） / `image_path`（list） | — | — 主键 / 输入 / 元数据 |
| `weather` | 本 12 条恒 `sunny` | ✅GT 天气（分类，本子集仅 1 类） |
| `light` | `day` / `night` | ✅GT 光照（二分类） |
| `scenes` | `rural` / `urban` | ✅GT 场景（二分类） |
| `linear` | `arterials` / `curve` / `intersection` / `T-junction` | ✅GT 道路线形（4+ 分类） |
| `whether an accident occurred` | 本 12 条恒 `Yes` | ⚠GT 事故判定（二分类；字段名**含空格**） |
| `causes` | 9 个不同自由文本描述 | ⚠GT 事故原因（开放文本，建议改为多分类或语义匹配） |
| `primary_responsibility` | `Ego-car` / `Pedestrian` / `Both` | ✅GT 主责方（3 分类） |

### `property`（multi_step_property.tsv，9 列，6 条，2 图/条）
| 字段 | 实测取值 | 归类 |
|---|---|---|
| `index` / `image`（list） / `image_path`（list） | — | — 主键 / 输入 / 元数据 |
| `disaster` | 本 6 条恒 `yes` | ⚠GT 是否受灾（二分类，本子集无变化） |
| `type` | `flooding` / `hurricane` / `wildfire` | ✅GT 灾害类型（3 分类） |
| `number` | `3`,`17`,`30`,`37`,`243` | ✅GT 建筑总数（数值） |
| `damage_number` | `0`,`1`,`30` | ✅GT 受损数（数值） |
| **`claim_decision`** | `No compensation` / `Partial compensation` / `Full compensation` | **✅GT 疑似可作 property 分片标签**（3 分类，本 6 条三类齐全）——**待 D2/D5 判定（captain 台账 O-02）** |

### 对 D5 指标选择的直接影响

| 指标 | 是否可用 | 依据 |
|---|---|---|
| Hit@1 / MRR@5 / 引用接地率 | ✅ | 与标签无关，54 条都有 `question` + 图片 + 文本元数据 |
| 分类准确率（`risk_level` / `underwriting_decision` / `claim_decision` / `primary_responsibility` / `type` / `infection`） | ⚠ 受限可用 | 这些字段在子集内有多值，但样本量 6–12，只能做示例性对比，不能报告统计显著 |
| 分类准确率（`Severity` / `species` / `weather` / `disaster` / `part` / `match`） | ❌ 不可用 | 头部 k 条在这些字段上**标签单一**（见 §抽样确定性说明的实测修正） |
| 数值回归（`claim` / `Amount` / `count` / `number` / `damage_number`） | ⚠ 受限可用 | 可算 MAE/MAPE，但样本 6–12 |

---

## D1 产物与复现

```bash
export HF_ENDPOINT=https://hf-mirror.com        # 本机必需
python data/ins-mmbench/scripts/fetch_subset.py          # 抽样（幂等，断点续传）
python data/ins-mmbench/scripts/fetch_subset.py --verify # 校验 manifest/records/磁盘 三者一致
python data/ins-mmbench/scripts/fetch_subset.py --reset  # 清空重抽
```

- 详细过程与实测数字：`docs/log/step-d1.md`
- 旧 `FETCH.md`（R2 的命令草案）已被 `scripts/fetch_subset.py` 取代，现只留一行指针。
- 产物分布（实测 2026-11-18 03:04）：`records.jsonl` 54 条；图片 **120 张**；`raw/` **125 个文件 / 33.0 MiB**；网络共取 **55.2 MiB**（源全 2.70 GiB 的 **2.00%**）。
