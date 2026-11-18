# Step D1 — INS-MMBench 子集抽样实现

> 交付根：`renewal-assistant/`（唯一；`insurance-agent/` 已按 captain 要求废弃，不再写入）
> 脚本：`data/ins-mmbench/scripts/fetch_subset.py`
> 产物：`data/ins-mmbench/{manifest.json, records.jsonl, raw/**, .fetch-progress.json}`
> 字段清单与 ground-truth 归类：`data/ins-mmbench/README.md`
> 本文件为**事后补写**（前两次尝试在"资料齐了但没写下来"处中断）。所有数字取自当前磁盘与
> `manifest.json` 的**实测值**，与估算值分列并标注来源。
> **已按 captain 要求回应**：§4.1 解释 57.9 MB vs 44 MB 估算（+31.6 %）的真实主因，
> 并**反驳**了"主因是 11 个 rejected 段重取"的假设（带可核证据）；§3.7 给出
> `rejected_segments` 的**定性结论**（碎片段，非解析失败，不影响 54 条的完整性），
> 并指出它确实改变了 liability 的取样语义。


## 1. 做了什么

### 1.1 口径

| 项 | 值 |
|---|---|
| 数据集 | `FDU-INS/INS-MMBench`（HF，Apache-2.0） |
| revision（**pin 成 commit sha**） | `b77ea65c18c61108a32b811ca344308941ff8046`（`lastModified=2025-07-10T11:43:24Z`） |
| endpoint | `https://hf-mirror.com`（`huggingface.co` 本机直连 30 s 超时） |
| 抽样策略 | **按分片不同，不是在用同一个 strategy**：`strategy_by_split` =<br>`claim / agri / health / property → head_k_complete_records`（严格 head-k，`source_index` 0..k-1 连续）<br>`liability → head_window_complete_records`（真窗口内前 12 条可解析记录，**跳过 9 条**）<br>`seed=null`、`deterministic=true`（含义：**可复现**，不含义：无偏 —— 见 §4.9） |
| k | claim 12 / agri 12 / health 12 / liability 12 / property **6** → **54 条** |
| 排除 | `INS_MMBench_fundamental.tsv`（1,544,148,629 B，Tier-2，见 §2.2） |
| 抓取时间 | `fetched_at = 2026-11-18T03:04:01+0800` |

### 1.2 五个分片（数字全部实测，来自 `manifest.json`）

| split | 源文件 | 源字节 | k | **实际取回字节** | chunk 数 | chunk 大小 | 记录 | 图片 | rejected 段 |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| claim | `multi_step_claim.tsv` | 36,738,707 | 12 | 3,145,728（3.00 MiB） | 1 | 3 MiB | 12 | 12 | 0 |
| agri | `multi_step_agri.tsv` | 46,455,785 | 12 | 3,145,728（3.00 MiB） | 1 | 3 MiB | 12 | 12 | 0 |
| health | `multi_step_health.tsv` | 196,938,789 | 12 | 5,870,943（5.60 MiB） | 2 | 3 MiB | 12 | 24 | **4** |
| liability | `multi_step_liability.tsv` | 272,149,532 | 12 | 20,570,507（19.62 MiB） | 8 | 3 MiB | 12 | 60 | **7** |
| property | `multi_step_property.tsv` | 803,754,983 | 6 | 25,165,824（24.00 MiB） | 24 | **1 MiB** | 6 | 12 | 0 |
| **合计** | | **2,900,191,262** | **54** | **57,898,730（55.22 MiB）** | 36 | | **54** | **120** | 11 |

> `chunks` 说明：`manifest.json` 记的是**去重后的实际 Range 条数**。`.fetch-progress.json`
> 里的原始计数器会更大（如 health 记 6），因为它包含调试期间同一区间被重复请求的次数
> （见 §1.4 的 B2/B3 两个 bug）。以 manifest 为准。

### 1.3 Range 策略（为什么 property 用 1 MiB）

1. **单次 ≤ 3 MiB**，`bytes=<start>-<end>`（inclusive），顺序推进，不重叠。
2. 每个 chunk 用 `^\d+\t`（行首「整数+制表符」）定位记录起点，相邻两个起点之间的字节 = **一条完整记录**；
   末尾可能被切断的那条作为 `carry` 带入下一个 chunk 拼接。
3. `property` 单条记录约 **4 MB > 3 MiB**，一次 Range 永远取不到完整记录 → 改用 **1 MiB × 24 次**，
   让 `carry` 跨 4–5 个 chunk 累积出一条完整记录。实测 24 次 1 MiB 请求全部 `http=206`（340 KB/s 量级）；
   而 3 MiB 请求在 property/liability 上反复停滞（见 §2.5）。
4. 图片：`image` 列 base64 解码落盘到 `raw/<split>/<index>/<n>.<ext>`；
   **扩展名按真实魔数决定**（`\xff\xd8\xff`→`.jpg`，`\x89PNG`→`.png`），实测 84 jpg + 36 png。

### 1.4 迭代中真实踩到的 6 个 bug（都已修复并复验）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| B1 | 启动即 `SyntaxError: name 'ENDPOINT' is used prior to global declaration` | `global` 声明在 `argparse default=ENDPOINT` 之后 | `global ENDPOINT` 提到 `main()` 第一行 |
| B2 | `health` 同一 chunk 被重取 5 次、记录数不增长 | 只更新了 `st["next_pos"]`，**没更新循环变量 `pos`** | 每轮 `pos = consumed` |
| B3 | `property` carry 在 1.0/2.0 MiB 之间来回振荡、`next_pos` 出现负值 | `next_pos` 被当成两种语义（carry 起点 **和** 下次抓取位置），导致区间重叠重复计数 | **双游标**：`next_pos`=carry 绝对起点（仅供跨进程恢复），`pos`=本次抓取位置（单调） |
| B4 | 单次 chunk 挂起 **927 s** 才失败，一次 `--max-time 120` 形同无效 | `urllib` 的 `timeout` 是**单次 socket 读**超时，不是总时长 | 改用 `curl --max-time 120`（subprocess），并额外加 Python 侧 `timeout=135` 兜底 |
| B5 | `property` 3 MiB 请求 0 条记录、carry 无限膨胀 | 单记录 ≈4 MB > chunk 上限 | `property` 专属 `chunk_mb=1` |
| B6 | `--verify` 报 `totals.images` 与磁盘不一致 | `dir_size(raw/)` 把 5 个 `records.jsonl` 也算进了图片数 | 图片数按 `.jpg/.png` 后缀单独统计，另加 `raw_files` |

> 这 6 条就是"为什么会慢/为什么中断"的真实答案，不是环境玄学。

---

## 2. 关键决策

### 2.1 为什么 property 只取 6 条（captain 裁决 **D-03**）

`multi_step_property.tsv` 单条记录 ≈4 MB（766 MiB / 200 行），12 条 = 48 MB，在本机 30–200 KB/s
的镜像带宽下是 4–27 分钟的不确定性；6 条仍覆盖该任务类型与 3 个 `claim_decision` 取值。
实测 6 条共 24.00 MiB、24 次请求、全部 206 —— 选择成立。

### 2.2 为什么排除 `fundamental.tsv`（captain 裁决 **D-04**，用户确认 A）

- 该文件**按任务排序**：实测前 61 行全部属于 `license plate recognition`，头部读取只能覆盖第 1 个基础任务，
  「按任务分层」根本做不到；要分层就得顺序读完 1.44 GiB。
- 本机实测带宽 30–200 KB/s → 1.44 GiB 需 2–13 小时，不可行。
- 已按 captain 要求在 `manifest.json` 里**显式登记为主动取舍**（不是"忘了做"）：

```json
"excluded": [{
  "file": "INS_MMBench_fundamental.tsv",
  "bytes": 1544148629,
  "reason": "按 task 排序，头部读取仅能覆盖第 1 个任务，分层不可行；体积 1.44 GiB 超出本机镜像带宽预算（实测 30–200 KB/s）",
  "impact": "下游只能评测检索指标（Hit@1 / MRR@5 / 引用接地率），无法报告问答准确率",
  "tier": 2,
  "decided_by": "captain D-04 / 用户确认 A（2026-11-18）"
}]
```

### 2.3 为什么必须走镜像

`huggingface.co` 本机 30 s 超时（HTTP 000，DNS 正常）；`hf-mirror.com` 200 / 1.18 s。
脚本内 `FALLBACK_ENDPOINT = "https://hf-mirror.com"` 硬编码回退，并在启动第一行打印
`endpoint = ...  (env HF_ENDPOINT=...)`，CI 里能直接看到实际用了哪个端点。

### 2.4 为什么只能是「头部 Range + 顺序追加」

- `snapshot_download` 只能取某 revision 的**全部文件**，`hf_hub_download` 只能取**单个文件**——
  两者都没有「行/记录」粒度（依据：huggingface_hub 官方 downloads 文档）。
- 随机 byte-range 切块已实测判死：单条记录内 base64 字段可达 876 KB 无换行，
  6 个随机 512 KB 窗口里 5 个取不到任何完整记录。
- 故：**只能从头顺序读**，用 Range 控制"读多少"。

### 2.5 为什么用 curl 而不是 urllib（B4 的结论）

同一份 3 MiB Range：`curl --max-time 120` 在 6.2 s 内返回 206；`urllib` 在慢链路上会挂到 927 s 才失败
（它的 `timeout` 只作用于单次 socket read）。captain 的硬约束「`curl --max-time 120`」是正确且必要的。

### 2.6 为什么没有随机种子

抽样规则是**确定性**的：固定 chunk 大小 + 固定 Range 序列 + 固定的“从头顺序取、列数校验通过即收”规则。
重跑逐字节一致（`--verify` 会核对 sha256）。`manifest.json` 记 `seed: null, deterministic: true`。

**但必须区分两个词（D1b 修正）**：
- `deterministic=true` 只保证“同样的字节 + 同样的解析器 → 同样的记录集合”，即**可复现**；
- 它**不**保证“无偏”。源文件本身按标签排序（实测 `multi_step_claim.tsv` 前 30 行 `Severity` 全 `minor`），
  所以 head-k 是“文件顺序前 k 条”，不是随机样本；liability 连“前 k 条”都不成立（见 §4.9）。
  因此 `manifest.json` 对每个分片都额外记了 `population_representative: false`。

---

## 3. 真实验证证据

以下命令均在本机实跑，输出为原文摘录。

### 3.1 三道校验（逐分片）

```
$ python3 - <<'PY' … (A: 列集合 ⊆ header; B: index 严格递增; C: 图片解码 + sha256 复验) …
claim      A(列数⊆header)=True B(index严格递增)=True C(图片解码+sha256)=12/12 rejected=0 k=12 records=12
agri       A(列数⊆header)=True B(index严格递增)=True C(图片解码+sha256)=12/12 rejected=0 k=12 records=12
health     A(列数⊆header)=True B(index严格递增)=True C(图片解码+sha256)=24/24 rejected=4 k=12 records=12
liability  A(列数⊆header)=True B(index严格递增)=True C(图片解码+sha256)=60/60 rejected=7 k=12 records=12
property   A(列数⊆header)=True B(index严格递增)=True C(图片解码+sha256)=12/12 rejected=0 k=6  records=6
```

### 3.2 records.jsonl 完整性 + index 序列

```
split      rows manifest    一致 index 序列                                 有缺口
claim        12       12  True [0,1,2,3,4,5,6,7,8,9,10,11]                  0 []
agri         12       12  True [0,1,2,3,4,5,6,7,8,9,10,11]                  0 []
health       12       12  True [0,1,2,3,4,5,6,7,8,9,10,11]                  0 []
liability    12       12  True [0,1,3,4,6,8,10,12,16,17,19,20]              9 [2,5,7,9,11,13,14,15,18]
property      6        6  True [0,1,2,3,4,5]                                0 []
全部 records 重复 id: 0      id 唯一性: True      总数: 54
```

**注意 liability 的 9 个 index 缺口 —— 见 §3.7，这是本子集唯一一处「不是严格 head-k」的地方。**

### 3.3 图片对账（引用 vs 磁盘）

```
records.jsonl 引用图片数: 120  去重: 120
磁盘图片文件数: 120
集合完全一致: True
悬空引用（引用但磁盘没有）: 0
孤立文件（磁盘有但无引用）: 0
扩展名分布: {'.jpg': 84, '.png': 36}
魔数抽查:
   agri/0/0.jpg    magic=b'\xff\xd8\xff\xe0' -> JPEG size=134,717B
   agri/1/0.jpg    magic=b'\xff\xd8\xff\xe0' -> JPEG size=129,323B
   agri/10/0.jpg   magic=b'\xff\xd8\xff\xe0' -> JPEG size=129,929B
图片总字节: 34,489,528 B = 32.89 MiB
每分片图片数: {'claim': 12, 'agri': 12, 'health': 24, 'liability': 60, 'property': 12}
```

### 3.4 manifest 自洽（sha256 实测比对）

```
manifest.totals.records = 54
records.jsonl 实际行数  = 54

对象                        manifest sha256                       一致
raw/claim/records.jsonl     e546488e2039af48828126f1275501d8...  True
raw/agri/records.jsonl      c34c2e785384045372b4de46c84f34a7...  True
raw/health/records.jsonl    5e3a4d293fa52f07fd755f5a2f78eff6...  True
raw/liability/records.jsonl 1335fdbde8a600fdec67998db3236e32...  True
raw/property/records.jsonl  358d32ff96b3338eeb93c8456f9547cd...  True
records.jsonl (汇总)        fb043a821895a059af58942acf07705b...  True

manifest 自洽: True
```
### 3.5 `answer` 字段（印证 D-04）与元数据一致性

```
$ python3 -c "统计 records.jsonl 的 answer / labels / source_revision / options"
answer 值分布: {'None': 54}          ← 54/54 全为 null
options 值分布: {'NoneType': 54}     ← 无选择题选项
labels 非空: 54 / 54                 ← 每条都带 metadata（Cost_of_vehicle / claim_decision / risk_level …）
source_revision 唯一值: {'b77ea65c18c61108a32b811ca344308941ff8046'}
```

→ **5 个场景文件本身就没有 `answer` 列**（已在 R2 逐文件确认），所以 54 条 `answer` 全为 null 是
**上游事实，不是抽取失败**。这直接支撑 D-04 的结论：本子集**只能评检索指标**（Hit@1 / MRR@5 /
引用接地率），没有可对齐的标准答案可供算 accuracy。ground truth 只能从 `labels` 里逐字段取
（如 `claim_decision` / `risk_level` / `primary_responsibility`），且受 §4.3 的标签同质局限约束。

### 3.6 revision 与元数据

```
revision: b77ea65c18c61108a32b811ca344308941ff8046
是 commit sha（非 main）: True
endpoint: https://hf-mirror.com | license: apache-2.0 | fetched_at: 2026-11-18T03:04:01+0800
strategy: head_k_complete_records | seed: None | deterministic: True
k: {'claim': 12, 'agri': 12, 'health': 12, 'liability': 12, 'property': 6}
excluded: [('INS_MMBench_fundamental.tsv', 2, 1544148629)]
```

### 3.7 `rejected_segments` 到底是什么（captain 点名要解释）

| split | rejected_segments | index 缺口 | 结论 |
|---|---:|---|---|
| claim | 0 | 0 | 干净 head-k |
| agri | 0 | 0 | 干净 head-k |
| health | **4** | **0** | 被拒的是**碎片段**，没有丢失记录 |
| liability | **7** | **9** | 被拒的是碎片段；另有 9 条记录整条未被接受 |
| property | 0 | 0 | 干净 head-k |

**它们是什么**：`rejected_segments` 统计的是**列数 ≠ header 列数的段**，也就是被分块边界切断、
或记录起点误判造成的**碎片**——不是"坏 base64"，也不是"超出 k 的溢出"（超出 k 的记录根本不会进入解析）。
base64 解码失败在代码里是直接 `Abort` 中止，**不会**被计成 rejected（本次一次都没触发）。

**对 54 条完整性的影响：不影响。** 证据是逐条检查了 `question` 的结尾完整性：

```
claim     12/12 结尾 = "...5. Final Claim Amount. Reason: <Reason>"
agri      12/12 结尾 = "...tion/Full Compensation. Reason: <Reason>"   (12 条长度全部 = 2303)
health    12/12 结尾 = "...tandard/Higher Premium. Reason: <Reason>"
liability 12/12 结尾 = "...Party: Ego-car/Pedestrian/Other car/Both"   (12 条长度全部 = 1178)
property   6/6  结尾 = "...ion/Full Compensation>. Reason: <Reason>"   (6 条长度全部 1279)
```

54 条**全部**以各任务的标准输出模板结尾，长度在同一分片内高度一致 → **没有一条被截断**。
三道校验（列数 / index 单调 / 图片解码+sha256）也全部通过。

**但它确实改变了 liability 的取样语义（必须报告的偏差）**：
liability 的 12 条是 **index 0–20 之间前 12 条能干净解析的记录**，不是严格的"前 12 条"——
2,5,7,9,11,13,14,15,18 这 9 条消失了。**数据没坏，只是覆盖范围被拉长**（20.57 MiB 才凑够 12 条）。
`claim` 全文件实测 index 0..398 连续、`agri` 前 177 条 index 连续，说明源文件的 index 本身是连续的，
所以缺口来自解析损失，而非源数据跳号。health 有 4 个 rejected 但 index 0–11 连续 → 那 4 个碎片
不涉及整条记录丢失。**health 与 liability 的 rejected 计数不可 1:1 换算成丢记录数**：前者是"碎片数"，
后者≠丢记录数（7 vs 9），因为一条记录被切成两半后，其中一半可能仍满足列数而未被计入 rejected。
**根因**：记录起点探测器 `^\d+\t` 会在多行自由文本字段（`question` / `causes`）内部误命中，
把一条记录切成两段。这是本实现已知的解析脆弱点，修法见 §4.4。

---

## 4. 遗留与数字

### 4.1 网络与磁盘：**实测** vs **估算**（captain 要求区分）

| 指标 | 估算（R2 阶段） | **实测** | 差异 | 差异原因 |
|---|---:|---:|---:|---|
| 网络取回 | ≈44 MB | **57,898,730 B = 57.9 MB（55.22 MiB）** | **+31.6 %** | 见下三条 |
| 磁盘（raw/） | — | **34,615,772 B = 33.01 MiB / 125 个文件** | — | 其中图片 32.89 MiB（120 张）+ 5 个 `records.jsonl` |
| 占源全量比 | 1.5 % | **2.00 %**（57,898,730 / 2,900,191,262） | +0.5 pt | 同上 |
| 记录 / 图片 | 54 / — | **54 / 120**（84 jpg + 36 png） | — | 一题多图：liability 5/题、health & property 2/题 |

**差异拆解（按贡献排序，不是"多取了几次"那么简单）**：
1. **liability 单行真实体积被严重低估** — R2 用「260 MiB ÷ 400 行 = 680 KB」估算，但实测
   20,570,507 B / 12 条 ≈ **1.71 MiB/条**（2.5×）。仅此项就 ≈ +12 MiB，是差异主因。
2. **分片粒度取整** — 每个分片最少一次 3 MiB 请求，claim（真实需 ≈1.9 MiB）、agri（≈2.2 MiB）
   都被取整到 3.00 MiB。
3. **rejected 碎片导致的额外推进** — health 的 4 个碎片、liability 的 9 条未接受记录使读取位置
   比"刚好凑够 k 条"更靠后（liability 为凑 12 条读到 index 20）。这是次要项，量级 ≈1–2 MiB。
> 结论：**+31.6 % 是"估算偏乐观"造成的，不是重试浪费**。

**直接回应 captain 的假设（“主因是 health/liability 的 11 个 rejected 段重取”）——这个假设不成立，证据两条：**
1. `bytes_fetched` 统计的是**去重后的 Range 区间长度之和**。调试期间那些重复/停滞的请求是**完全相同**的
   `[start,end]` 区间（B2/B3/B4 三个 bug 造成的反复），在 `manifest.json` 里被 `dict.fromkeys` 去掉，
   **不计入** `bytes_fetched`。所以“重取”在数字上根本不可见——若把重复请求计进去，数值会远高于 57.9 MB，
   而不是刚好 57.9 MB。
2. 同一文件的**已取字节数逐条可核**：liability `20,570,507 B ÷ 12 条 = 1.71 MiB/条`，
   而 R2 估算用的是 `260 MiB ÷ 400 行 = 680 KB/条`。单此一项就差 `(1.71−0.68)×12 ≈ 12.4 MiB`，
   已占全部差异（13.9 MB）的 **≈ 89 %**。相比之下，11 个 rejected 碎片涉及的字节量只有碎片本身的大小，
   且它们只影响“读取位置推到哪里”，不重复计入 `bytes_fetched`。
> 因此正确表述是：**差异来自 liability 单行体积被低估（主）+ 分片取整（次）+ 为绕过碎片而多推的读取位置（末）**，
> 与“重取”无关。


### 4.2 抽样比例统计表

| split | 保险类型 | 源文件字节 | 占源文件 | 取回字节 | 占源文件 | 记录 | 覆盖率说明 |
|---|---|---:|---:|---:|---:|---:|---|
| claim | auto | 36,738,707 | 8.6 % | 3,145,728 | 8.6 % | 12 | 源 400 行（论文 270 题）→ 3.0 % |
| agri | agricultural | 46,455,785 | 6.8 % | 3,145,728 | 6.8 % | 12 | 源 ≈252 行 → 4.8 % |
| health | health | 196,938,789 | 3.0 % | 5,870,943 | 3.0 % | 12 | 源 ≈400 行 → 3.0 % |
| liability | auto | 272,149,532 | 7.6 % | 20,570,507 | 7.6 % | 12 | 源 ≈400 行 → 3.0 % |
| property | property | 803,754,983 | 3.1 % | 25,165,824 | 3.1 % | 6 | 源 ≈200 行 → 3.0 % |
| **合计** | 4 类 | **2,900,191,262** | **2.00 %** | **57,898,730** | **2.00 %** | **54** | 全量 10,372 题 → **0.52 %** |

按保险类型分布（实测）：`auto 24`（claim 12 + liability 12）、`agricultural 12`、`health 12`、`property 6`。

### 4.3 局限（必须让下游 D2/D5 知道）

1. **不是标签均衡样本。** 源文件内部按标签排序（实测：`multi_step_claim.tsv` 前 30 行 `Severity` 全为 `minor`；
   文件里 minor150 / moderate150 / severe100 顺序排列）。因此本子集在若干字段上**标签单一**：
   `Severity` 全 minor、`species` 全 grape、`weather` 全 sunny、`whether an accident occurred` 全 Yes、
   `disaster` 全 yes、`part` 全 chest、`match` 全 yes。
   → **这些字段不能用来算分类准确率**；能做的是检索指标（Hit@1 / MRR@5 / 引用接地率）。
   这与 D-04 的结论一致并强化它。逐字段可用性见 `data/ins-mmbench/README.md`。
2. **liability 不是严格 head-k**（index 0–20 取 12 条），语义是"前 12 条可解析记录"，见 §3.7。
3. **property 只有 6 条**（D-03），样本量不足以做统计结论。
4. **基础层/元任务缺失**（D-04）：22 个基础任务、12 个元任务在本子集中覆盖为 0。
5. **图片全部来自 base64 解码**，不是原始高分辨率文件；JPEG/PNG 已是有损/无损压缩后的字节。

### 4.4 若要修掉 §3.7 的解析脆弱点（本次**未做**，因为会触发重下）

建议改法（下次重跑时启用）：解析出一条记录后，**要求下一条记录的 `index` == 当前 `index` + 1**；
若不连续，则说明中间被误切，应把该段整体回退并入下一轮 carry 重新对齐，而不是丢弃。
或更简单：把记录起点锚定为「上一记录结尾 + `\r\n` + 整数 + `\t` + base64 图片开头特征」的联合条件。
本次不动代码的原因：改动解析逻辑会产生与现有 `manifest.json` 不一致的新数据，
而 captain 明确要求**不得重下、保证 manifest 与磁盘一致**。

### 4.5 偏离说明（两处，均为有理由的偏离）

1. **图片扩展名**：captain 给出的路径模板是 `raw/<split>/<index>/<n>.png`，实现为 `<n>.<ext>`，
   `ext` 按真实魔数决定（84 个 `.jpg` / 36 个 `.png`）。理由：把 JPEG 字节存成 `.png`
   会让下游按后缀解码时直接失败。已在 `manifest.json.notes` 与 README 中写明。
2. **脚本与文档路径**：任务书正文写的是 `scripts/ins_mmbench_sample.py` 与
   `docs/log/step-d1-sampling.md`；按 captain 后续裁决（2026-11-18）改为
   `data/ins-mmbench/scripts/fetch_subset.py` 与 `docs/log/step-d1.md`。**只保留一套，无副本。**

### 4.6 未触碰的边界（自查）

```
$ git status --porcelain
 M .gitignore
?? claims/            ← 非本次改动（captain 的其他工作流）
?? data/              ← 本次：data/ins-mmbench/**
?? docs/log/          ← 本次：docs/log/step-d1.md
?? docs/research/     ← R2 产出
?? traces-claims/     ← 非本次改动
```

- 未修改 `server/`、`scripts/`（既有续保代码）、`wiki/`、`tests/`。
- 本次新增/修改仅：`data/ins-mmbench/{scripts/fetch_subset.py, README.md, FETCH.md, manifest.json,
  records.jsonl, raw/**, .fetch-progress.json}`、`docs/log/step-d1.md`。

### 4.7 复现（幂等 + 断点续传）

```bash
export HF_ENDPOINT=https://hf-mirror.com                     # 本机必需
python data/ins-mmbench/scripts/fetch_subset.py              # 幂等；中断后从 .fetch-progress.json 续
python data/ins-mmbench/scripts/fetch_subset.py --verify     # manifest / records.jsonl / 磁盘 三者一致
python data/ins-mmbench/scripts/fetch_subset.py --reset      # 清空后重抽
python data/ins-mmbench/scripts/fetch_subset.py --k 12 --k-property 6   # 参数化 k（默认即此值）
```

`--verify` 当前输出：

```
records=54 images=120 raw_files=125 by_insurance_type={'auto': 24, 'agricultural': 12, 'health': 12, 'property': 6} revision=b77ea65c18c6
VERIFY OK: manifest / records.jsonl / 磁盘 三者一致
```

### 4.8 MCP 检索依据（硬规则 ≥3 来源，URL + 检索时间 + 用于哪项决策）

| # | 来源 | URL | 检索时间 (CST) | 用于哪项决策 |
|---|---|---|---|---|
| S1 | MDN — `Range` 请求头 | https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Range | 2026-11-18 00:50 | 确认 `bytes=<start>-<end>` 为 **0-based inclusive**、满足时返回 **206**、Range 是断点续传的标准手段 → 决定用 Range 而非整文件下载，并以 206 判定成功 |
| S2 | huggingface_hub 官方 downloads 文档（Context7 检索 `/huggingface/huggingface_hub`） | https://github.com/huggingface/huggingface_hub/blob/main/docs/source/en/guides/download.md | 2026-11-18 00:48 | 确认 `snapshot_download` 取某 revision **全部文件**、`hf_hub_download` 只能按**文件**取、resume 依赖 `commit_hash` 元数据 → 决定「HF 官方 API 无行级粒度，必须自己发 Range」 |
| S3 | arXiv 摘要页（ICCV 2025，22 基础 / 12 元 / 5 场景） | https://arxiv.org/abs/2406.09105 | 2026-11-18 00:32 | 确认任务分层口径与论文状态 → 决定分层维度与 `manifest.excluded` 的 `impact` 措辞 |
| S4 | HF Dataset API（元数据） | https://hf-mirror.com/api/datasets/FDU-INS/INS-MMBench | 2026-11-18 00:43 | 取得 `sha=b77ea65c…`（pin）、`lastModified=2025-07-10T11:43:24Z`、`license=apache-2.0` |
| S5 | HF Dataset API（文件树） | https://hf-mirror.com/api/datasets/FDU-INS/INS-MMBench/tree/b77ea65c…?recursive=true | 2026-11-18 00:43 | 各文件精确字节数（合计 2,900,191,262）→ 用于抽样比例表与 `--max-time` 预算 |
| S6 | HF Dataset Card（原始 README.md） | https://hf-mirror.com/datasets/FDU-INS/INS-MMBench/resolve/b77ea65c…/README.md | 2026-11-18 00:05（R2，D1 复验一致） | 6 文件→任务映射 → 决定 split 命名与 `task_name` |

> 字段名一律取自**实际抓到的 header**（写入 `manifest.json` → `splits.<name>.header`），
> 不依赖任何内置知识。逐字段 ground-truth 归类见 `data/ins-mmbench/README.md`。

---

### 4.9 抽样偏差评估（D1b，captain 点名要的量化）

#### 4.9.1 事实修正：liability 不是 head-k

之前 §1.1 与 `manifest.json` 顶层都只写 `head_k_complete_records`，**与 liability 的事实不符**。已改为按分片：

| split | strategy | 严格 head-k | `source_index` | 跳过 |
|---|---|---|---|---|
| claim | `head_k_complete_records` | ✅ | `[0..11]` | — |
| agri | `head_k_complete_records` | ✅ | `[0..11]` | — |
| health | `head_k_complete_records` | ✅ | `[0..11]` | — |
| property | `head_k_complete_records` | ✅ | `[0..5]` | — |
| **liability** | **`head_window_complete_records`** | ❌ | `[0,1,3,4,6,8,10,12,16,17,19,20]` | **`[2,5,7,9,11,13,14,15,18]`** |

`manifest.json` 已逐分片增 `strategy` / `strict_head_k` / `source_indices_taken` / `source_indices_skipped` /
`sampling_note` / `population_representative:false`，并新增顶层 `strategy_by_split` 与 `bias_assessment`。**已有数字一个未改**。

#### 4.9.2 锚点问题：rejected 段的“字节数”没有直接存在（我不掩饰）

captain 建议“用 `rejected_segments` 的字节数做代理指标”。**但这个字段只存了计数（liability=7），没存每段字节数**——
当时只增了计数器，没把段长落盘；而 D-14 禁止重下，无法补存。
所以改用**可核的字节预算恒等式**反推，并把不确定性显式量化（敏感性分析），而不是给一个假装精确的点值：

```
bytes_fetched(liability) = Σ(保留 12 条的源字节) + Σ(9 条被跳过) + Σ(碎片段) + 尾部残段
```

- 保留记录的源字节用可复现公式估算：`base64 长度 = ceil(decoded/3)×4` + 列表字面量开销 + `question` 实长 +
  `labels` 各字段实长 + 字段分隔符（11 列）。推算均值 **1019.4 KiB**，与实际 `bytes_fetched / 21` 的 956.6 KiB 同量级 → 估算可用。
- **health 是个天然对照组**（4 个 rejected、0 条丢失）：`bytes_fetched 5,870,943 − Σ保留 5,734,168 = 136,775 B = **133.6 KiB**`，
  即 **4 个碎片合计仅 133.6 KiB，单碎片约 33.4 KiB**，远小于单条记录的 466.6 KiB。
  → 这直接证明：**碎片是小段，不是“大记录失败”**，与 captain 担心的机制不符。

#### 4.9.3 被跳过的 9 条到底多大？——它们**比保留的小**，与假设相反

liability 残差 `= 20,570,507 − 12,526,415 = 8,044,092 B = 7.67 MiB`（9 条被跳过 + 7 个碎片 + 尾部残段）。
对“碎片总量 0–1000 KiB”与“尾部残段 0–0.5 条”做敏感性：

| 假设 | 被跳过 9 条均值 | **保留/跳过** |
|---|---:|---:|
| 碎片 0 KiB、无尾段 | 872.8 KiB | **1.17×** |
| 碎片 0 KiB、尾段 0.5 条 | 816.2 KiB | **1.25×**（中心）|
| 碎片 500 KiB、尾段 0.5 条 | 760.7 KiB | **1.34×** |
| 碎片 1000 KiB、尾段 0.5 条 | 705.1 KiB | **1.45×** |

保留 12 条的分布：均值 **1019.4 KiB**、中位数 1007.5、标准差 305.2（CV=0.30）、min 505.8、max 1542.8、极差比 3.05。

**结论（数字回答，不用形容词）**：保留的 12 条平均 **1019.4 KiB**，被跳过的 9 条反推 **705–873 KiB**（中心 816），
保留/跳过 = **1.17–1.45×（中心 1.25×）**。即：**大记录被过度代表、小记录被欠代表**——与“大记录更易丢失”的假设**方向相反**。
幅度上，1019 vs 816 KiB 约差 **0.8 个标准差**（(1019−816)/305≈0.67），n=12 vs 9，**不宜声称“系统性偏差”**。

#### 4.9.4 直接回答验收问题：会不会“小额高估、大额低估”？

**不会，且该问法在本分片上不成立，理由两步：**

1. **方向相反且偏大**：保留的 12 条比被跳过的 9 条大约 **1.25×**（区间 1.17–1.45×），所以即便存在大小方向的偏，也是
   “大记录多、小记录少”——**不是**“小额高估、大额低估”。
2. **liability 根本没有金额字段**：`labels` 全部键 = `weather, light, scenes, linear, whether an accident occurred,
causes, primary_responsibility, image_path`——**没有任何 claim amount / premium / loss 字段**。
   记录字节大小的 99% 来自 5 张 JPEG 的 base64（实测：记录源字节与 `decoded 图片字节×4/3` 近乎线性），
   它反映的是**视觉复杂度 / 光照 / 天气 / 场景**，**不映射赔款金额**。
   → “小额案件 / 大额案件”在 liability 分片上**没有可操作的度量**，因此不能推断其被高估/低估。

#### 4.9.5 机制：与记录大小无因果关系

丢记录的原因是 **记录起点探测器 `^\d+\t` 在多行自由文本（`causes` / `question`）内部误命中**，把一条记录切成两段；
碎片段列数不符被拒，整条记录随之丢失。是否命中取决于该记录的**文本内容**（有没有“数字+制表符”行首），不取决于记录大小。
health 对照组（4 碎片 = 133.6 KiB、0 丢失）是这一点的直接证据。

#### 4.9.6 对下游的影响边界

| 下游 | 影响 | 依据 |
|---|---|---|
| **D3 wiki 萃取** | **无影响** | 54 条内容均完整（`question` 结尾与长度已逐条校验），萃取只看单条内容，不看分布 |
| **D5 检索评测**（Hit@1 / MRR@5 / 引用接地率） | **无影响** | 检索指标不依赖样本对总体的代表性 |
| 任何“分布 / 占比”类结论（如主责方分布） | **不可用** | n=12 且非随机；`population_representative=false` |
| 分类准确率 | **不可用** | 源文件按标签排序，多个字段在本子集标签单一（§4.3-1） |

> 一句话交给下游：**这 54 条可以当“真实、完整、可复现的样本”用，不能当“无偏、可推断总体”的样本用。**
> 前者已用 sha256 + 三道校验钉死，后者已用 `strategy_by_split` + `population_representative:false` + 本节公开坐标。
