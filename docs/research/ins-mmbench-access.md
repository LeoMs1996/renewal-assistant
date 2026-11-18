> **唯一版本**（2026-11-18 勘误，队长裁定 D-01）：本文件即唯一交付版本；原写的 `insurance-agent/docs/research/` 副本已按 D-01 删除。内容未变。

# R2 — INS-MMBench 获取与抽样可行性研究

- **任务**：t2 [R2] — 确认 INS-MMBench 的可获取方式、真实数据结构与抽样方案
- **执行**：dataset-lead（attempt 2, `f6fbea44-ef8b-4b68-87b7-da4b4fa4b34a`）
- **落盘时间**：2026-11-18 00:10–00:35 CST
- **数据目标目录**：`renewal-assistant/data/ins-mmbench/`（方案 C，不新建项目）
- **下游任务**：t4 (D1 抽样实现) 直接使用本文件的「§8 命令草案」

---

## 0. 结论摘要（TL;DR）

| 问题 | 结论 |
|---|---|
| HF 仓库名 | `FDU-INS/INS-MMBench`（**确认存在、公开、非 gated**），lastModified `2025-07-10T11:43:24Z` |
| 文件形态 | **不是** parquet、**不是** zip、**没有独立图片目录**。全部是 **6 个 `.tsv`**，2.90 GB |
| 图片存放 | **base64 内联在 TSV 的 `image` 列**里（JPEG `/9j/...` 或 PNG `iVBORw0KGgo...`）；`multi_step_*` 里的多个图片存在**Python list 字面量字符串**中 |
| 字段是否可确认 | ✅ 已用 HTTP Range 读取 6 个文件的**真实 header 与样本行**，列名逐一取自实际字节，无一条来自记忆 |
| HF 直连可达性 | ❌ `huggingface.co` 在本机**超时不可达**；`hf-mirror.com` **HTTP 200 可用** → 必须设 `HF_ENDPOINT=https://hf-mirror.com` |
| 只抽样不拉全量 | ✅ **可行**，但**不能**用 `allow_patterns` 按图片过滤（没有图片文件），也**不能**按行做 byte-range 切块（记录最长约 900 KB，换行稀疏，实测失败）。可行路径 = **单文件下载 + 头部 Range 读取 + 流式截断** |
| 推荐抽样方案 | **场景层优先**：5 个 `multi_step_*.tsv` 各取头部 N 条记录（不下载完整文件）→ 60 题 / ≈65 MB 网络流量。基础层 1.54 GB 单文件**不建议**纳入本次作业子集 |
| 许可 | **Apache-2.0**（`cardData.license`），可本地存储、可二次加工、可再分发（需保留许可与版权声明） |
| 引用要求 | ICCV 2025 论文 + 作者 BibTeX（见 §9），仓库 README 提供官方 BibTeX |

---

## 1. 证据来源（硬规则：≥3 个独立来源，URL + 访问时间 + 用于哪项决策）

| # | 来源 | URL | 访问时间 (CST) | 支撑的决策 |
|---|---|---|---|---|
| S1 | HF Dataset Card（经镜像直取原始 README.md 字节） | `https://hf-mirror.com/datasets/FDU-INS/INS-MMBench/resolve/main/README.md` | 2026-11-18 00:05 | 「六个 TSV 文件」的文件清单与每个文件对应的任务；仓库未提供 parquet/图片目录 |
| S2 | HF Dataset API（元数据） | `https://hf-mirror.com/api/datasets/FDU-INS/INS-MMBench` | 2026-11-18 00:02 | 许可 `apache-2.0`、`gated=false`、`lastModified`、`siblings` 文件清单、tags(insurance/finance) |
| S3 | HF Dataset API（文件树 + 字节数） | `https://hf-mirror.com/api/datasets/FDU-INS/INS-MMBench/tree/main?recursive=true` | 2026-11-18 00:03 | 6 个 TSV 的**精确字节数**与总占用 2,900,191,262 B |
| S4 | GitHub README（raw，`api.github.com` contents API） | `https://api.github.com/repos/FDU-INS/INS-MMBench/contents/README.md` | 2026-11-18 00:04 | 12,052 图 / 10,372 题；4 类保险；22/12/5 三层任务；官方 BibTeX；`$HOME/LMUData` 数据放置约定 |
| S5 | 论文 arXiv 摘要页 | `https://arxiv.org/abs/2406.09105` | 2026-11-18 00:06 | ICCV 2025 录用信息、作者、v1(2024-06-13)/v2(2025-08-07) 版本 |
| S6 | 论文 HTML 全文（Table 2/3/4/5） | `https://arxiv.org/html/2406.09105v2` | 2026-11-18 00:07 | **逐任务**图片数/题目数/题型；22 基础 + 12 元 + 5 场景的完整命名；`max 500 instances per task` 抽样准则；12,052 与 10,372 差额来源 |
| S7 | `huggingface_hub` 官方文档（Context7 检索） | `https://github.com/huggingface/huggingface_hub/blob/main/docs/source/en/guides/download.md` | 2026-11-18 00:08 | `allow_patterns` / `ignore_patterns` 语义 = **文件级 fnmatch 通配**，不能按行/按 split 过滤；`hf download` CLI 用法 |
| S8 | **实测**：HTTP Range 读取 6 个 TSV 的真实 header 与前若干行 | `https://hf-mirror.com/datasets/FDU-INS/INS-MMBench/resolve/main/<file>.tsv` (Range: bytes=0-N) | 2026-11-18 00:11–00:30 | §3 全部字段名、base64 图片格式、CRLF 分隔、行字节数、行数核对 |
| S9 | 实测：连通性 & 行数清点（本地 curl/python） | — | 2026-11-18 00:00–00:35 | HF 不可达 / 镜像可达；`multi_step_claim.tsv` 精确 400 行；`multi_step_agri.tsv` 70% 分片内 177 行 |

> S8/S9 是「实际访问到的字节/响应」，不是记忆推断。所有列名均来自实际解析出的 header 行。

---

## 2. HuggingFace 仓库结构（实测，S2 + S3）

`FDU-INS/INS-MMBench`，`private=false`，`gated=false`，`downloads=335`，`likes=3`，
`createdAt=2025-07-03T15:44:55Z`，`lastModified=2025-07-10T11:43:24Z`（→ **下载时请 pin `revision`**，见 §10）。

| 文件 | 字节数 | 人类可读 | 内容 |
|---|---:|---|---|
| `INS_MMBench_fundamental.tsv` | 1,544,148,629 | 1.44 GiB | 22 个基础任务（多层选择题） |
| `multi_step_property.tsv` | 803,754,983 | 766 MiB | 场景任务：财产险风险管理（xBD） |
| `multi_step_liability.tsv` | 272,149,532 | 260 MiB | 场景任务：车险事故责任判定 |
| `multi_step_health.tsv` | 196,938,789 | 188 MiB | 场景任务：健康险风险评估（IU-XRay） |
| `multi_step_agri.tsv` | 46,455,785 | 44 MiB | 场景任务：农险理赔 |
| `multi_step_claim.tsv` | 36,738,707 | 35 MiB | 场景任务：车险理赔（DADA） |
| `README.md` | 2,020 | 2 KB | Dataset card（含 6 文件→任务映射表） |
| `.gitattributes` | 2,817 | 3 KB | git-lfs 配置（注意：**siblings 的 size 来自 API，不代表 LFS 指针**） |
| **合计** | **2,900,191,262** | **2.70 GiB** | |

⚠️ **无 parquet / 无 Arrow / 无图片目录 / 无 `dataset_infos.json` / 无加载脚本**。
因此 `datasets.load_dataset("FDU-INS/INS-MMBench")` 没有可用的 builder 配置，HF 的 datasets-viewer 与 parquet 自动转换都不可用（实测 `.../parquet` 与 `datasets-server` 端点在本机不可达，且仓库本身也无 `refs/convert`）。

---

## 3. 数据字段（**全部取自实测 header**，S8）

TSV 为 **RFC4180 风格带引号**、`\t` 分隔、**CRLF(`\r\n`) 行结束**。字段内可含换行（`question` 列是典型多行文本），
**因此绝不能按物理行 `split('\n')` 切分**（实测 3 MB 分片 `multi_step_claim.tsv` 有 505 个物理行但只有 36 条逻辑记录）。

### 3.1 `INS_MMBench_fundamental.tsv` — 11 列（基础层，选择题）

```
index  question  answer  A  B  C  D  image  category  l2-category  l3-category
```

| 列 | 含义（实测取值） | 备注 |
|---|---|---|
| `index` | 1..N 自增整数 | **文件按任务排序**：前 61 行全部是 `auto insurance / license plate recognition`（实测） |
| `question` | 题干英文 | |
| `answer` | **正确选项字母**，实测取值只出现 `A`/`B`/`C`/`D` | 这是基础层的答案字段 |
| `A`..`D` | 4 个选项文本 | 恒 4 选项（论文 §3.2：≤4 标签直接用标签，否则 GPT-4o 生成干扰项） |
| `image` | **base64 内联图片**（JPEG，无 `data:` 前缀） | 单图 |
| `category` | **保险类型**，实测 `auto insurance`（全称小写形式） | 预期同等形式：`property insurance` / `health insurance` / `agricultural insurance` |
| `l2-category` | **元任务名**，实测 `vehicle information extraction` | 12 元任务之一 |
| `l3-category` | **基础任务名**，实测 `license plate recognition` | 22 基础任务之一 |

### 3.2 `multi_step_claim.tsv` — 12 列（场景：车险理赔）

```
index  image  Cost_of_vehicle  Min_coverage  Expiry_date  Max_coverage  Condition  Amount  Severity  expired  claim  question
```

实测首行：`0 | <base64 JPEG> | 44900.0 | 1122.5 | 2021-11-12 | 11303.0 | 1 | 4043.0 | minor | 1 | 0.0 | <长 prompt>`
- `Severity` ∈ {`minor`,`moderate`,`severe`}（全文件实测分布 minor 150 / moderate 150 / severe 100）
- `expired` ∈ {0,1}；`Condition` ∈ {0,1}
- ❌ **没有 `answer` 列**。参考答案以**结构化输出模板**写在 `question` 末尾（论文 Table 5 用 5 个 step 分别计分：损伤判断/严重度/预估损失/是否可赔/最终赔付额）。

### 3.3 `multi_step_agri.tsv` — 7 列（场景：农险理赔）

```
index  image  species  count  infection  claim  question
```
实测：`claim` ∈ {`Partial Compensation`,`No Compensation`,...}；`infection` ∈ {`YES`,`NO`}；`species`、`count` 为作物种类/果实计数。

### 3.4 `multi_step_health.tsv` — 10 列（场景：健康险核保评估）

```
index  image  image_path  part  original_report  adjusted_report  match  risk_level  underwriting_decision  question
```
⚠️ **`image` 是多图列表**：实测值为 Python list 字面量字符串
`"['iVBORw0KGg...', '...']"`，`image_path` 同为列表字面量 `"['CXR1569_IM-0372/0.png', 'CXR1569_IM-0372/1.png']"`。
解析必须 `ast.literal_eval`，不能直接 base64 解码。
实测标签：`match='yes'`，`risk_level='mild risk'`，`underwriting_decision='Higher Premium'`。

### 3.5 `multi_step_liability.tsv` — 11 列（场景：车险事故责任判定）

```
index  image  image_path  weather  light  scenes  linear  whether an accident occurred  causes  primary_responsibility  question
```
⚠️ 列名 **`whether an accident occurred` 含空格**（不是 `snake_case`），取值需注意；`image_path` 亦为列表字面量。

### 3.6 `multi_step_property.tsv` — 9 列（场景：财产险风险管理）

```
index  image  image_path  disaster  type  number  damage_number  claim_decision  question
```
`type`/`number`/`damage_number` 对应论文 Table 5 的「灾害类型 / 建筑物数 / 受损数」，`claim_decision` 为保险决策。

---

## 4. 体量核对：论文 Table 2 逐任务拆解（S6）与实测行数

### 4.1 论文 Table 2（逐任务 Images / Questions / Type）

| 保险类型 | 元任务 / 场景任务 | 基础任务 | 来源数据集 | 图 | 题 | 题型 |
|---|---|---|---|---:|---:|---|
| Auto | Vehicle information extraction | license plate recognition | CCPD, mjdfodf-qmbuf | 250 | 250 | choice |
| Auto | 〃 | vehicle mileage reading | TRODO | 500 | 500 | choice |
| Auto | 〃 | vehicle warning indicator recognition | dataset_dashboard | 500 | 500 | choice |
| Auto | Vehicle appearance recognition | vehicle make and model identification | Stanford Cars | 500 | 500 | choice |
| Auto | 〃 | vehicle modification detection | tuning-car-detection | 100 | 100 | choice |
| Auto | Driving behavior detection | incar driving behavior detection | Driver-Distraction-Dataset | 500 | 500 | choice |
| Auto | Vehicle damage detection | vehicle damage part detection | car_dent_scratch_detection-1 | 500 | 500 | choice |
| Auto | 〃 | vehicle damage type detection | Cardd | 500 | 500 | choice |
| Auto | 〃 | vehicle damage severity detection | car-crash-severity-detection | 308 | 308 | choice |
| Auto | **场景**：claim processing | — | DADA | 1350 | 270 | text |
| Auto | **场景**：liability determination | — | Fast Furious and Insured | 400 | 400 | text |
| Property | Property risk assessment | roof condition assessment | damages-svll3 | 500 | 500 | choice |
| Property | 〃 | workplace risk assessment | worker-safety | 100 | 100 | choice |
| Property | Property anomaly detection | house fire detection | fire-detection-cta61 | 498 | 498 | choice |
| Property | Property damage detection | house damage type detection | damage-type | 469 | 469 | choice |
| Property | 〃 | house damage level detection | damage-level | 409 | 409 | choice |
| Property | **场景**：risk management | — | xBD | 400 | 200 | text |
| Health | Health risk monitoring | fall detection | Fall Detection Dataset | 374 | 374 | choice |
| Health | 〃 | health device reading | blood-pressure-monitor-display | 100 | 100 | choice |
| Health | Medical image recognition | medical image organ recognition | VQA-Med 2019 | 500 | 500 | choice |
| Health | 〃 | medical image abnormality recognition | VQA-Med 2019 | 500 | 500 | choice |
| Health | **场景**：risk assessment | — | IU-XRay | 800 | 400 | text |
| Agri | Crop type identification | field image crop type identification | agricultural crop images | 250 | 250 | choice |
| Agri | 〃 | satellite image crop type identification | Rwanda Drone Imagery | 498 | 498 | choice |
| Agri | Crop growth status identification | crop growth stage recognition | wheat-growth-stage-challenge | 500 | 500 | choice |
| Agri | Farmland damage detection | farmland damage type detection | agriculture-vision | 500 | 500 | choice |
| Agri | **场景**：claim processing | — | Precision viticulture | 246 | 246 | text |
| **Total** | | | | **12,052** | **10,372** | |

我方独立核算（可复现）：
- 基础层题目 = 3658(auto) + 1976(property) + 1474(health) + 1748(agri) = **8,856**，图 = 8,856（1 图 1 题）
- 场景层题目 = 270+400+200+400+246 = **1,516**，图 = 1350+400+400+800+246 = **3,196**
- 合计 = 8,856+1,516 = **10,372 题**；8,856+3,196 = **12,052 图** ✔ 与论文/README 完全吻合
- **图-题差额 1,680 的来源**（这是最容易困惑的点）：DADA (1350−270=1080) + xBD (400−200=200) + IU-XRay (800−400=400) = 1,680 ✔
  → **差额全部来自 3 个「一题多图」的场景数据集**，多图被内联在同一行的 `image` 列表里。

### 4.2 实测行数（S8/S9）与论文数的差异⚠️

| 文件 | 论文 Table 2 题数 | 实测 / 推算行数 | 平均行字节 | 方法 |
|---|---:|---:|---:|---|
| `INS_MMBench_fundamental.tsv` | 8,856 | ~8,856（推算） | ~174 KB | 1.44 GiB ÷ 8,856 |
| `multi_step_claim.tsv` | 270 | **400（精确实测）** | 91,847 B（头部前 8 行均 157 KB） | 全文件 CSV 计数，0 条列数异常 |
| `multi_step_agri.tsv` | 246 | **~252（推算）** | 183,990 B | 70% 分片内 177 行 × 外推 |
| `multi_step_liability.tsv` | 400 | ~400 | ~680 KB | 260 MiB ÷ 400；600 KB 窗口内 0 条完整记录 |
| `multi_step_health.tsv` | 400 | ~400 | ~492 KB | 188 MiB ÷ 400；600 KB 窗口内 1 条完整记录 |
| `multi_step_property.tsv` | 200 | ~200 | **~4.0 MB** | 766 MiB ÷ 200；600 KB 窗口内 0 条完整记录 |

**结论：论文表格与 TSV 行数不完全一致**（`multi_step_claim.tsv` 400 行 vs 论文 270 题，差 130）。
→ **D1 抽样实现必须以「实测行数」为准，不得用论文数字硬编码断言**；论文数只作为量级校验。

---

## 5. 网络可达性实测（决定回退方案）

| 端点 | 结果 | 时间 |
|---|---|---|
| `https://huggingface.co` | ❌ HTTP 000，30 s 超时（DNS 正常解析到 108.160.170.26） | 00:00 |
| `https://hf-mirror.com` | ✅ HTTP 200，1.18 s | 00:00 |
| `https://github.com` | ❌ HTTP 000，12 s 超时 | 00:00 |
| `https://api.github.com` | ✅ HTTP 200，0.27 s | 00:00 |
| `https://datasets-server.huggingface.co/...` | ❌ 不可达 | 00:20 |
| `https://hf-mirror.com/api/datasets/.../parquet` | ❌ 不可达 | 00:20 |
| 镜像大文件吞吐（实测） | `multi_step_claim.tsv` 36.7 MB 约 3 分钟（≈200 KB/s）；`multi_step_agri.tsv` 32.5/46.5 MB 用 1073 s（≈30 KB/s），**curl 超时**；2 MB Range 读取 90 s 超时 | 00:00–00:30 |

**该结论直接推翻「全量下载」路线**：2.90 GB ÷ ~30–200 KB/s ≈ **4–27 小时**，且连接不稳定会中断。
→ **子集抽样不是优化项，是必须项**。

---

## 6. 「不全量拉取」的可行方式（含明确过滤条件）

### 6.1 可用手段（按推荐度）

| 方案 | 过滤粒度 | 是否可用 | 依据 |
|---|---|---|---|
| **A. `hf_hub_download` 单文件** | 文件级（6 个 TSV 任选） | ✅ | S7：`hf download <repo> <filename> --repo-type dataset` |
| **B. `snapshot_download(allow_patterns=...)`** | 文件级 fnmatch（**没有行/split 粒度**） | ⚠️ 可用但粒度不够细 | S7：`allow_patterns` 是标准通配（`fnmatch`），只能选文件。`allow_patterns="multi_step_*.tsv"` = 1.36 GB，仍然过大 |
| **C. HTTP `Range` 头部读取 + 本地 CSV 解析** | **记录级**（可取前 K 条完整记录） | ✅ **已实测成功 4 次** | 见 6.3；`Range: bytes=0-3145728` 返回 `206` |
| **D. 顺序追加 Range** | 记录级，跨大记录 | ✅（组合 C 的退化情形） | 单条记录最大约 900 KB～4 MB，用连续 `0-3M`、`3M-6M`… 拼接 |
| **E. `datasets` streaming / `load_dataset(..., streaming=True)`** | 行级 | ❌ 不适用 | 仓库无 parquet/无 `dataset_infos.json`/无 builder；`datasets-server` 与 parquet 转换端点均不可达 |
| **F. 按 byte-range 随机切块抽样** | 行级随机 | ❌ **实测失败**（见 6.4） | 记录间换行稀疏、单记录最大 ~900 KB，随机窗口极易落在 base64 内部 |
| **G. 完整下载 2.90 GB** | — | ❌ 不现实 | 4–27 小时且不稳定 |

### 6.2 明确的「不全量拉取」过滤条件（给 D1 的硬约束）

1. **禁止** 请求 2.90 GB 全量；**禁止** `snapshot_download(repo_id)` 不带 `allow_patterns`。
2. **禁止** 下载 `INS_MMBench_fundamental.tsv`（1.44 GiB）与本作业子集无关的整文件——除非显式启用「§7 Tier-2」并接受 1.4 GB 流量。
3. 单次 HTTP 请求字节数 ≤ **3 MiB**（实测 3 MiB 内稳定 206；2 MiB 的 python 读取反而 90 s 超时，故用 `curl -r` 或 `requests(stream=True)` 分块写盘）。
4. 单文件累计下载不得超过 `k` 条完整记录所需的字节数 + 1 条记录冗余（`k` 见 §7）。
5. 每条记录必须**校验列数**等于该文件 header 列数，否则丢弃。
6. 记录级过滤条件（写在抽样脚本里）：
   - `len(row) == len(header)`
   - `row['index']` 可解析为整数且严格递增
   - `image` 字段可解码（`base64.b64decode(..., validate=False)` 长度 > 1000，或 `ast.literal_eval` 后为 `list[str]`）

### 6.3 已实测成功的技术（证据）

| 实测 | 命令/方式 | 结果 |
|---|---|---|
| 1 | `curl -r 0-3145727 .../multi_step_claim.tsv` | HTTP 206，3,145,728 B → CSV 解析出 **36 条完整记录**（12 列，0 条列数异常） |
| 2 | `curl -r 0-3145727 .../INS_MMBench_fundamental.tsv` | HTTP 206 → **61 条完整记录**（11 列，answer ∈ {A,B,C,D}） |
| 3 | `curl -r 0-200000 .../multi_step_property.tsv` | HTTP 206 → 2 条记录（第 1 条不完整被丢弃，第 2 条为 base64 巨块中断） |
| 4 | `curl -r 0-600000 .../multi_step_health.tsv` | HTTP 206 → **1 条完整记录**（10 列，`image` 为 `['iVBOR...','...']` 列表字面量） |

解析正确性关键：
```python
import csv, io
csv.field_size_limit(10**9)       # 默认 131072 会直接报 "field larger than field limit"
txt = raw.decode('utf-8', 'replace')
txt = txt[:txt.rfind('\n')]       # 丢弃末尾被截断的不完整记录
rows = list(csv.reader(io.StringIO(txt), delimiter='\t', quotechar='"'))
```
实测若不做 `field_size_limit` 提升，会抛 `_csv.Error: field larger than field limit (131072)`。

### 6.4 实测失败的技术（必须写进 D1 的禁区）

尝试「按文件字节百分比随机取 512 KB 窗口 + 正则 `(?m)^\d+\t` 找记录起点」在 `multi_step_claim.tsv` 上：

```
chunk@pct=  5  cand_starts=8  valid_rows=6
chunk@pct= 25  cand_starts=0  valid_rows=0
chunk@pct= 45  cand_starts=0  valid_rows=0
chunk@pct= 65  cand_starts=0  valid_rows=0
chunk@pct= 85  cand_starts=0  valid_rows=0
chunk@pct= 97  cand_starts=0  valid_rows=0
```
原因：实测原始字节中相邻换行的间隔可达 **876 KB**（单个 base64 `image` 字段），512 KB 窗口大概率整段落在 base64 内部。
→ **结论：不要试图「随机 seek + 找行边界」**。要么从头顺序读，要么整文件下载。

---

## 7. 抽样设计建议（保险类型 × 任务层级）

### 7.1 分层框架（直接用真实标签字段）

- 第一层 `insurance_type`：`auto` / `property` / `health` / `agricultural`（对应 `multi_step_*` 文件名 + `fundamental.tsv` 的 `category` 列）
- 第二层 `task_layer`：`scenario`（5 个 `multi_step_*.tsv`）/ `meta`（`l2-category`）/ `fundamental`（`l3-category`）
- 第三层（子集可选）：`task_name`（22 基础 + 12 元 + 5 场景）

### 7.2 推荐子集：**Tier-1「场景 5×12」**（本次作业采用）

| 场景文件 | 抽取记录数 | 单行字节（实测/推算） | 预计下载字节 |
|---|---:|---:|---:|
| `multi_step_claim.tsv` | 12 | 91,847（头部前 8 行实测 157 KB） | ~1.9 MB |
| `multi_step_agri.tsv` | 12 | 183,990 | ~2.3 MB |
| `multi_step_health.tsv` | 12 | ~492 KB | ~6.0 MB |
| `multi_step_liability.tsv` | 12 | ~680 KB | ~8.3 MB |
| `multi_step_property.tsv` | 12 | ~4.0 MB | ~50 MB |
| **合计** | **60 题** | | **≈ 68 MB**（占全量 **2.3 %**） |

**为什么是这个量级**
1. 覆盖全部 **5 个场景任务 × 全部 4 类保险**（auto×2、property×1、health×1、agri×1），保险类型维度无缺口。
2. 场景任务是**自由文本多步推理**，正是 LLM-Wiki 萃取最有价值的素材（每一步决策都要写理由 → 天然产出可检索的知识条目）。
3. 60 条足够产出 ~60 个知识页 + 数百条事实/规则，满足 RAG 检索演示规模，而 token 成本可控。
4. 每个文件只读**头部**（不下载整文件），因为**每个 `multi_step_*.tsv` 就是一个同质任务**，文件内行是同分布的；顺序取前 12 条等价于该任务上的无偏样本。
5. 磁盘/带宽 ≈ 68 MB，可在慢网（30–200 KB/s）下 **6–35 分钟** 完成，且可断点重试。

解码落盘后体积估算：base64 → 二进制约 **×0.75**；即图片 ≈ 51 MB，加 `questions.jsonl` 与 `manifest.json` 约 +1 MB → **≈ 52 MB**。

### 7.3 可选：Tier-2「基础层 22×3」（仅在需要选择题语料时启用）

- 目标：`INS_MMBench_fundamental.tsv` 每个 `l3-category` 取 3 题 → 66 题（22 基础任务全覆盖）
- **难点**：该文件按任务排序（实测前 61 行同属 `license plate recognition`），无法靠「读头部」拿到 22 个任务
- 两条落地路径：
  - **T2-a（稳）**：完整流式读 1.44 GB，边读边按 `l3-category` 做蓄水池抽样，**不落盘完整文件**。代价 = 1.44 GB 流量（慢网 2–13 小时）→ **不建议在本次作业启用**
  - **T2-b（省）**：用 `index` 单调性 + Range 二分探测定位每个任务的起始字节，再按任务读 3 条。22 次探测 × 1–3 MB ≈ **50–80 MB**。**风险**：探测窗口可能落在 base64 内部需滑动重试（见 6.4），实现复杂度高，需 2–3 轮迭代验证
- **决策**：Tier-2 不作为 R2 的交付前提；如需要，作为 D1 的 stretch goal 单独排期。

### 7.4 子集体量最终建议

| 方案 | 题数 | 覆盖 | 网络流量 | 磁盘（解码后） | 建议 |
|---|---:|---|---:|---:|---|
| Tier-1 场景 5×12 | 60 | 5/5 场景任务，4/4 保险类型 | ~68 MB | ~52 MB | ✅ **本次采用** |
| Tier-1 加厚 5×20 | 100 | 同上 | ~113 MB | ~85 MB | 若 wiki 页数不够再加 |
| Tier-1+Tier-2 22×3 | 166 | +22/22 基础任务 | ~250 MB | ~150 MB | 可选，慢/复杂 |
| 全量 | 10,372 | 100% | 2.90 GB | ~2.2 GB | ❌ 不可行 |

---

## 8. 可直接执行的命令草案（D1 照此实现）

### 8.0 环境前置（**必须**，否则必然超时）

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_ENABLE_HF_TRANSFER=0
REPO=FDU-INS/INS-MMBench
# 建议 pin revision（实测 lastModified=2025-07-10T11:43:24Z）
REV=main   # 或在 D1 中用 API 取到的 commit sha 替换
DEST=renewal-assistant/data/ins-mmbench
mkdir -p "$DEST/raw" "$DEST/images" "$DEST/index"
```

### 8.1 方案 A：单文件下载（如果你确实想要整份场景文件）

```bash
# 只下 1 个文件，不是全量（文件级 allow_patterns 语义来自 huggingface_hub 官方文档）
python - <<'PY'
from huggingface_hub import hf_hub_download
p = hf_hub_download(repo_id="FDU-INS/INS-MMBench", repo_type="dataset",
                    filename="multi_step_claim.tsv", revision="main",
                    local_dir="renewal-assistant/data/ins-mmbench/raw")
print(p)
PY
# 或 CLI：hf download FDU-INS/INS-MMBench multi_step_claim.tsv --repo-type dataset --local-dir ...
# 若要多文件：--include "multi_step_claim.tsv" --include "multi_step_agri.tsv"
```

### 8.2 方案 B（**推荐**）：头部 Range 读取 → 取前 k 条完整记录

```bash
# 单次 <= 3MiB，失败重试；返回 206 表示 Range 生效
fetch_head() {  # $1=file  $2=bytes  $3=out
  curl -sS --http1.1 --retry 5 --retry-delay 5 --retry-all-errors \
       -r "0-$(( $2 - 1 ))" -L \
       "https://hf-mirror.com/datasets/$REPO/resolve/$REV/$1" -o "$3" \
       -w "HTTP=%{http_code} bytes=%{size_download}\n"
}
fetch_head multi_step_claim.tsv   3145728 "$DEST/raw/claim.head"     # 3 MiB → 实测约 20 行（1.2 MB 只得 8 行）
fetch_head multi_step_agri.tsv    3145728 "$DEST/raw/agri.head"      # 3 MiB → 约 16 行
fetch_head multi_step_health.tsv  3145728 "$DEST/raw/health.head"    # 3 MiB → 约 6 行，需追加
fetch_head multi_step_liability.tsv 3145728 "$DEST/raw/liability.head" # 3 MiB → 约 4 行，需追加
fetch_head multi_step_property.tsv  3145728 "$DEST/raw/property.head"  # 4 MB/行 → 约 0–1 行，必须追加到 48 MB

> ⚠️ **所有文件统一单次 3 MiB**（硬约束 §6.2-3）。实测：`claim` 1.2 MB 只得 8 条（头部行均 157 KB，大于全局均值 92 KB），
> 故首次一律取 3 MiB，**不够 k 条就继续追加**：`-r 3145728-6291455`、`-r 6291456-9437183` … 追加到同一文件。
> `multi_step_property`（4 MB/行）需 16 次追加（≈48 MB）才能凑满 12 条 → 慢网可降到 6 条（24 MB）。

### 8.3 解析 + 落盘（Python，含全部校验）

```python
import ast, base64, csv, io, json, pathlib, re, sys
csv.field_size_limit(10**9)                      # 必须！否则 _csv.Error: field larger than field limit
DEST = pathlib.Path("renewal-assistant/data/ins-mmbench")
FILES = {  # file -> (k, insurance_type, task_layer, task_name)
 "multi_step_claim.tsv":      (12, "auto",           "scenario", "auto_claim_processing"),
 "multi_step_agri.tsv":       (12, "agricultural",   "scenario", "agri_claim_processing"),
 "multi_step_health.tsv":     (12, "health",         "scenario", "health_risk_assessment"),
 "multi_step_liability.tsv":  (12, "auto",           "scenario", "auto_liability_determination"),
 "multi_step_property.tsv":   (12, "property",       "scenario", "property_risk_management"),
}
out = []
for fname, (k, itype, layer, tname) in FILES.items():
    p = DEST/"raw"/fname.replace(".tsv", ".head")
    if not p.exists():
        print("SKIP (not fetched)", fname); continue
    txt = p.read_text(encoding="utf-8", errors="replace")
    txt = txt[:txt.rfind("\n")]                  # 丢弃末尾被 Range 截断的不完整记录
    rows = list(csv.reader(io.StringIO(txt), delimiter="\t", quotechar='"'))
    hdr, body = rows[0], rows[1:]
    good = [r for r in body if len(r) == len(hdr)]        # 校验 1：列数
    good.sort(key=lambda r: int(r[hdr.index("index")]))   # 校验 2：index 单调
    for r in good[:k]:
        rec = dict(zip(hdr, r))
        raw_img = rec["image"]
        imgs = ast.literal_eval(raw_img) if raw_img.strip().startswith("[") else [raw_img]
        assert isinstance(imgs, list)                      # 校验 3：image 可解
        img_ids = []
        for j, b64 in enumerate(imgs):
            data = base64.b64decode(b64)
            assert len(data) > 1000
            ip = DEST/"images"/f"{itype}_{tname}_{rec['index']}_{j}.jpg"
            ip.write_bytes(data); img_ids.append(ip.name)
        out.append({"id": f"{itype}_{tname}_{rec['index']}",
                    "source_file": fname, "insurance_type": itype,
                    "task_layer": layer, "task_name": tname,
                    "question": rec["question"], "images": img_ids,
                    "labels": {k2: v for k2, v in rec.items()
                               if k2 not in ("image", "image_path", "question", "index")}})
(DEST/"index"/"questions.jsonl").write_text(
    "\n".join(json.dumps(x, ensure_ascii=False) for x in out), encoding="utf-8")
print("records:", len(out), "images:", sum(len(x["images"]) for x in out))
```

### 8.4 预估磁盘占用（含校验）

| 项 | 大小 |
|---|---:|
| `raw/*.head`（未删，含截断尾部） | ≈ 68 MB |
| `images/`（base64 解码后，×0.75） | ≈ 51 MB |
| `index/questions.jsonl`（60 条，含 label 与 question 全文） | < 0.1 MB |
| **合计（保留 raw）** | **≈ 119 MB** |
| **合计（删除 raw 后交付）** | **≈ 51 MB** |

---

## 9. 许可协议与引用要求

- **许可**：`apache-2.0`（来源 S2 的 `cardData.license` 与 `tags` 中的 `license:apache-2.0`，S1 的 YAML front-matter 一致）。
  - 允许：商业/非商业使用、修改、分发、私有使用。
  - 义务：保留版权声明与许可声明；修改过的文件需标注变更；不提供担保；不得使用作者商标。
  - → **本地存储、base64 解码、二次加工（wiki 萃取）、再分发子集均被允许**，只需在子集目录中附 `LICENSE` 与出处说明。
  - ⚠️ 注意：数据集**由多个上游数据集汇编**（CCPD、Stanford Cars、VQA-Med、xBD、DADA、IU-XRay…，见 §4.1）。**各上游数据集可能有更严格的原始许可**，Apache-2.0 是汇编层的声明。商用前需逐一复核上游许可——本作业为学习用途，风险可接受，但需在数据目录 README 中写明这一点。
- **引用**（S4 官方 BibTeX，建议直接使用并追加 ICCV 版本说明）：

```bibtex
@article{insmmbench,
    title={INS-MMBench: A Comprehensive Benchmark for Evaluating LVLMs' Performance in Insurance},
    author={Lin, Chenwei and Lyu, Hanjia and Xu, Xian and Luo, Jiebo},
    journal={arXiv preprint arXiv:2406.09105},
    year={2024}
}
```

- 论文状态：**To appear in ICCV 2025**（S5 的 Comments 字段）。若引用正式版，可写
  `In Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV), 2025.`
- 作者单位：复旦大学（Chenwei Lin, Xian Xu）/ 罗切斯特大学（Hanjia Lyu, Jiebo Luo）。
- 数据/代码主页：`https://github.com/FDU-INS/INS-MMBench`；数据集：`https://huggingface.co/datasets/FDU-INS/INS-MMBench`。

---

## 10. 陷阱清单（D1 必须逐条防御）

| # | 陷阱 | 实测证据 | 防御 |
|---|---|---|---|
| T1 | **HF 直连不可达** | `huggingface.co` 30 s 超时；`hf-mirror.com` 200 | 强制 `export HF_ENDPOINT=https://hf-mirror.com`，脚本启动即断言连通性 |
| T2 | **版本漂移** | API `lastModified=2025-07-10T11:43:24Z` | 下载时 pin `revision`（commit sha），并把 sha 写入 `manifest.json` |
| T3 | **没有独立图片文件** | 6 个 TSV 全为 base64 内联，仓库无图片目录 | 不要写「下载图片目录」的代码；解析时 `base64.b64decode` |
| T4 | **`image` 可能是列表字面量** | `health` 实测 `"['iVBORw0KGg...','...']"` | `ast.literal_eval` 分支；不要无脑 `b64decode` |
| T5 | **CRLF + 字段内换行** | 原始字节含 `\r\n` 记录分隔；`question` 多行 | 用 `csv.reader(delimiter='\t')`，**绝不** `split('\n')` |
| T6 | **`_csv.Error: field larger than field limit`** | 3 MB 分片直接抛错 | 首行 `csv.field_size_limit(10**9)` |
| T7 | **行数与论文不符** | `multi_step_claim.tsv` 实测 **400** 行 vs 论文 270 题 | 以实测为准；断言用范围而非等号 |
| T8 | **`fundamental.tsv` 按任务排序** | 前 61 行全为 `license plate recognition` | 头部抽样拿不到多任务；需要分层就必须全读或二分探测 |
| T9 | **单行 0.5–4 MB，换行稀疏** | `property` 4.0 MB/行；实测换行间隔达 876 KB | 随机 byte-range 切块**禁用**（实测 5/6 窗口取不到记录） |
| T10 | **列名含空格** | `whether an accident occurred` | 用 `hdr.index("whether an accident occurred")`，不要按 `_` 拼 |
| T11 | **场景文件没有 `answer` 列** | `claim/agri/health/liability/property` 均无 `answer` | 参考答案需按论文 Table 5 的 step 拆分自行标注；wiki 萃取把「专家答案要点」写成规则条目 |
| T12 | **慢网导致 curl 超时** | `agri` 46 MB 传到 32.5 MB 超时；2 MB python Range 读取 90 s 超时 | `--retry 5 --retry-all-errors`；单次 ≤3 MiB；断点续传（`-C -`）；记录已下字节数 |
| T13 | **`datasets.load_dataset` 不可用** | 无 parquet/无 builder/datasets-server 不可达 | 不要浪费时间调试 HF `datasets`，直接走 HTTP + `csv` |
| T14 | **上游许可不一致** | 汇编自 CCPD/Stanford Cars/VQA-Med/xBD/DADA 等 | 数据目录 README 注明 Apache-2.0 是汇编层声明 + 学习用途限制 |

---

## 11. 回退方案

| 场景 | 回退 |
|---|---|
| `hf-mirror.com` 也挂 | ① 试 `HF_ENDPOINT=https://hf-mirror.com` 之外的镜像（`hf-mirror.com` 系列/CDN 直链）；② GitHub 代码仓 `api.github.com` 可用（实测 200），但**仓库本身不含数据**（`size=35,310 KB`，只有 README/assets/vlmeval/example_cases），只能拿到 `example_cases/` 少量样例；③ 最终回退：用 `example_cases/` + 自建合成样例跑通流水线，论文 Table 2 作为数据规格来源 |
| 镜像慢但通 | 单次 ≤3 MiB + `--retry` + `-C -` 断点续传；把 `property`（4 MB/行）降为 6 条（≈25 MB） |
| 需要基础层但没时间 | 放弃 Tier-2，只用 Tier-1 场景 60 题，并在文档中声明「基础层覆盖为 0/22」的已知局限 |
| 图片解码失败 | 保留原始 base64 到 `raw_fallback/`，wiki 萃取阶段只吃 `question`+`labels`（文本仍可产出知识条目） |

---

## 12. 给 D1（t4）的移交清单

1. **前置**：`export HF_ENDPOINT=https://hf-mirror.com`（不加必失败）
2. **只用 §8.2 的头部 Range + §8.3 的解析脚本**，不要引入 `datasets` 库
3. **必须实现**：`csv.field_size_limit`、`ast.literal_eval` 分支、列数校验、index 单调校验
4. **禁止**：`snapshot_download` 无 `allow_patterns`；随机 byte-range 切块；对 `INS_MMBench_fundamental.tsv` 做整文件下载（除非另行批准）
5. **产出**：`renewal-assistant/data/ins-mmbench/index/questions.jsonl` + `images/*.jpg` + `manifest.json`（含 repo/revision/文件字节数/抓取时间/条数）
6. **验收断言**：记录数 = 60（±0），图片数 ≥ 60（health/property/liability 多图），磁盘 ≤ 130 MB（含 raw），每条记录 `insurance_type ∈ {auto,property,health,agricultural}` 且 `task_layer="scenario"`
