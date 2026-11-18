> 勘误（2026-11-18，队长裁定 D-01）：原首行写「与 insurance-agent/… 同源副本」，但该目录已按 D-01 删除。本文件即唯一版本，内容未变。
> （历史行仅做路径口径更正，结论与数字一字未改；详见文末「## 勘误记录」。）

# Step R2 — INS-MMBench 获取与抽样可行性研究

| 项 | 值 |
|---|---|
| 任务 | t2 [R2] |
| 执行者 | dataset-lead |
| attempt | 2（attempt_id `f6fbea44-ef8b-4b68-87b7-da4b4fa4b34a`；attempt 1 = `c6ac6b8c-...` 被重派作废） |
| 时间窗 | 2026-11-17 23:17 → 2026-11-18 00:45 CST |
| 产出 | `renewal-assistant/docs/research/ins-mmbench-access.md`（主交付）、本日志 |
| 结论 | ✅ 可行性确认：**只抽样不拉全量可行**，但必须换技术路线（见下） |

---

## 1. 时间线（按工具调用顺序）

| 时刻 | 动作 | 结果 |
|---|---|---|
| 23:17 | `web_call search.run` (academic) 检索 INS-MMBench 论文 | 命中 arXiv 2406.09105v2；确认 22 基础 / 12 元 / 5 场景、ICCV 2025 |
| 23:18 | `curl https://huggingface.co/api/datasets/FDU-INS/INS-MMBench` | **超时**（30 s，HTTP 000） |
| 23:18 | `web_call read.fetch` huggingface.co dataset 页 | **失败**（all fetch backends failed） |
| 23:19 | 连通性矩阵测试 4 个端点 | `hf-mirror.com` **200** / `api.github.com` **200** / `huggingface.co` **000** / `github.com` **000** |
| 23:19 | DNS 解析 | `huggingface.co → 108.160.170.26`（解析正常，是连不通，不是 DNS 问题） |
| 23:19 | `hf-mirror.com/api/datasets/FDU-INS/INS-MMBench` | ✅ 200：license `apache-2.0`、gated=false、lastModified 2025-07-10、`siblings`=8 |
| 23:19 | `api.github.com/repos/FDU-INS/INS-MMBench` | ✅ 200：size 35,310 KB、description `[ICCV '25] ...`、default_branch main |
| 23:20 | `hf-mirror .../tree/main?recursive=true` | ✅ 6 个 TSV + README + .gitattributes，总 **2,900,191,262 B** |
| 23:20 | GitHub README raw | ✅ 12,052 图 / 10,372 题、4 类保险、官方 BibTeX |
| 23:20 | `curl -r 0-3145727` 取 `multi_step_claim.tsv` 与 `INS_MMBench_fundamental.tsv` 头部 | ✅ 均 **206**，各 3 MB |
| 23:21 | CSV 解析（`csv.field_size_limit(10**9)`） | 首轮未提升 field limit → `_csv.Error: field larger than field limit (131072)`；提升后 claim 得 36 条×12 列、fundamental 得 61 条×11 列 |
| 23:22 | 取 `vlmeval/utils/dataset_config.py` | ✅ 命中 `multi_step_claim/property/agri/liability/health` 五个数据集类型判定 |
| 23:23 | Range 读 agri/health/liability/property 的 header（0-4095 B） | ✅ 4 个 header 全部拿到，health/liability/property 含 `image_path` 列 |
| 23:30 | 探测 HF parquet / datasets-server / refs 端点 | ❌ 全部不可达 → `datasets` 流式路线不可用 |
| 23:53 | 完整下载 `multi_step_claim.tsv`（36.7 MB） | ✅ 成功；CSV 精确计数 **400 行** |
| 00:09 | 完整下载 `multi_step_agri.tsv`（46.5 MB） | ⚠️ **1073 s 后超时**，只到 32.5 MB（≈30 KB/s）→ 用 70% 分片外推 ≈252 行 |
| 00:20 | 尝试「随机 byte-range 窗口 + 正则找行起点」 | ❌ **失败**：6 个窗口中 5 个取不到记录（换行间隔最大 876 KB） |
| 00:25 | 尝试「2 MB python Range 读取」 | ❌ 90 s 超时（慢网 + 大 Range 不稳） |
| 00:30 | Range 读 health/property/liability 各 600 KB | health 得 1 条完整记录（发现 `image` 是 list 字面量）；property/liability 因单行 0.7–4 MB 无法在 600 KB 内成行 |
| 00:35 | 读 arXiv HTML 全文 Table 2 | ✅ 拿到 27 行逐任务 图/题/题型 与来源数据集，独立核算与 12,052/10,372 完全吻合 |
| 00:45 | 落盘研究报告 | `renewal-assistant/docs/research/ins-mmbench-access.md` |

---

## 2. 关键发现（按对下游的影响排序）

### F1 — 图片是 base64 内联在 TSV 里，没有图片文件 ⭐最重

6 个文件全部是 `.tsv`，`image` 列是 base64（JPEG 头 `/9j/`、PNG 头 `iVBORw0KGgo`）。
→ 所有「先用 `allow_patterns` 只下图片子集」的设想**不成立**（没有图片文件可过滤）。
→ 抽样只能在 **文件级** 或 **记录级（HTTP Range）** 做。

### F2 — HF 直连不可达，必须走镜像 ⭐阻塞级

| 端点 | 结果 |
|---|---|
| `huggingface.co` | ❌ 30 s 超时 |
| `hf-mirror.com` | ✅ 200 / 1.18 s |
| `github.com` | ❌ 12 s 超时 |
| `api.github.com` | ✅ 200 |

→ D1 脚本**必须** `export HF_ENDPOINT=https://hf-mirror.com`，否则一上手就失败。
→ 镜像吞吐实测 30–200 KB/s，**大文件不可靠**（46 MB 都没下完）。

### F3 — `allow_patterns` 只有文件级粒度

Context7 官方文档（`huggingface_hub` downloads guide）明确：`allow_patterns`/`ignore_patterns` 是 `fnmatch` 通配，作用于**文件路径**，没有行/range/split 粒度。
→ `snapshot_download(repo_id, allow_patterns="multi_step_*.tsv")` = 1.36 GB，仍然太大。

### F4 — 记录级抽样必须「从头顺序读」，不能随机 seek ⭐技术结论

实测 `multi_step_claim.tsv` 的随机 512 KB 窗口：
```
pct=  5  cand=8  valid=6
pct= 25  cand=0  valid=0
pct= 45  cand=0  valid=0
pct= 65  cand=0  valid=0
pct= 85  cand=0  valid=0
pct= 97  cand=0  valid=0
```
根因：单个 base64 `image` 字段可达 **876 KB 无换行**。
→ 「随机 byte-range 切块抽样」路线**判死**；可行路线只有「头部 Range 读 + 顺序追加」。

### F5 — 行的真实字节数差异 40 倍（决定抽样成本）

| 文件 | 单行字节 | 依据 |
|---|---:|---|
| `multi_step_claim` | 91,847 B | 36.7 MB ÷ 400 行（精确） |
| `multi_step_agri` | 183,990 B | 32.5 MB ÷ 177 行（实测） |
| `multi_step_health` | ~492 KB | 188 MiB ÷ 400；600 KB 只得 1 行（实测） |
| `multi_step_liability` | ~680 KB | 260 MiB ÷ 400 |
| `multi_step_property` | **~4.0 MB** | 766 MiB ÷ 200；600 KB 得 0 行（实测） |

→ 抽 12 条的成本：claim 1.1 MB，property **50 MB**。property 是成本瓶颈。

### F6 — `image` 可能是 Python list 字面量（多图）

`multi_step_health` 实测：`image="['iVBORw0KGg...','...']"`，`image_path="['CXR1569_IM-0372/0.png','CXR1569_IM-0372/1.png']"`。
→ 解析必须 `ast.literal_eval` 分支，否则 `b64decode` 直接炸。这也解释了 12,052 图 vs 10,372 题的 1,680 差。

### F7 — 论文 Table 2 与 TSV 行数不一致

`multi_step_claim.tsv` **实测 400 行**，论文 Table 2 写 **270 题**（DADA 1350 图 / 270 题）。
→ 断言不能用论文数字硬编码。

### F8 — 12,052 与 10,372 的差额可完全解释（建立信任）

基础层 8,856 题 = 8,856 图（1:1）；场景层 1,516 题 = 3,196 图。
差额 1,680 = DADA(1350−270=1080) + xBD(400−200=200) + IU-XRay(800−400=400) ✔

---

## 3. 抽样方案决策

| 方案 | 判定 | 理由 |
|---|---|---|
| 全量下载 2.90 GB | ❌ 否决 | 慢网 4–27 h，且 46 MB 都无法稳定下完 |
| `snapshot_download(allow_patterns="multi_step_*.tsv")` | ❌ 否决 | 1.36 GB，粒度太粗 |
| `datasets.load_dataset(..., streaming=True)` | ❌ 否决 | 无 parquet / 无 builder / datasets-server 不可达 |
| 随机 byte-range 切块 | ❌ 否决 | 实测 5/6 窗口取不到记录（F4） |
| **头部 Range 读 + 顺序追加 + CSV 校验** | ✅ **采用** | 已实测成功 4 次；60 题仅 ≈68 MB（全量 2.3%） |
| 基础层 1.44 GB 单文件 | ⚠️ 降级为 Tier-2 可选 | 文件按任务排序，头部读只能拿第 1 个任务；全读代价 1.44 GB |

**最终子集：Tier-1「场景 5×12」= 60 题**
- 覆盖 5/5 场景任务 × 4/4 保险类型（auto×2 / property / health / agricultural）
- 网络流量 ≈ 68 MB，磁盘（解码后）≈ 52 MB，含 raw ≈ 119 MB
- 理由：场景任务是自由文本多步推理，最适合 LLM-Wiki 萃取（每步都要写理由 → 天然产出规则条目）

---

## 4. 已实测成功的可复用片段（交给 D1）

```bash
# 关键 1：镜像
export HF_ENDPOINT=https://hf-mirror.com

# 关键 2：头部 Range（<=3MiB，206 = Range 生效）
curl -sS --retry 5 --retry-delay 5 --retry-all-errors -r 0-1258290 -L \
  "https://hf-mirror.com/datasets/FDU-INS/INS-MMBench/resolve/main/multi_step_claim.tsv" \
  -o claim.head -w "HTTP=%{http_code} bytes=%{size_download}\n"
```

```python
# 关键 3：解析三件套
csv.field_size_limit(10**9)                     # 否则 _csv.Error: field larger than field limit (131072)
txt = open(p, encoding="utf-8", errors="replace").read()
txt = txt[:txt.rfind("\n")]                     # 丢弃被 Range 截断的尾部残record
rows = list(csv.reader(io.StringIO(txt), delimiter="\t", quotechar='"'))
good = [r for r in rows[1:] if len(r) == len(rows[0])]   # 列数校验

# 关键 4：image 有两种形态
imgs = ast.literal_eval(raw) if raw.strip().startswith("[") else [raw]
```

---

## 5. 未决 / 交由下游

1. **revision pin**：报告里给了 `main`；建议 D1 首次运行时调 `hf-mirror.com/api/datasets/.../refs` 或 `.../commits/main` 取 commit sha 并写进 `manifest.json`（本机 `/refs` 端点不可达，需 D1 用别的路径确认）。
2. **`fundamental.tsv` 的 22 任务分层**：Tier-2 未实测（要全读 1.44 GB 或做二分探测），本作业**不纳入**；如需要，单独立项。
3. **`multi_step_property` 的 12 条 = 50 MB**：若慢网仍超时，回退为 6 条（≈25 MB），并在子集 README 里声明 property 采样数减半。
4. **场景任务的参考答案**：语义上「答案」在 `question` 的输出模板里 + 论文 Table 5 的 5 个 step，不是独立列。LLM-Wiki 萃取时需按 step 拆成结构化事实，不能期待一个 `answer` 字段。

---

## 6. 验收自检

| 任务要求 | 状态 | 证据 |
|---|---|---|
| HF repo 文件清单与体量 | ✅ | §2 表，S3 API，总 2,900,191,262 B |
| 12,052 图 / 10,372 题 / 22+12+5 | ✅ | §4.1 Table 2 逐任务 + 独立核算吻合 |
| 数据字段（JSON/parquet 结构、图片路径规则、答案字段、保险类型、任务标签字段名） | ✅ | §3 六份实测 header；图片为 base64 内联（非路径）；答案字段：基础层 `answer`∈{A,B,C,D}，场景层无 `answer` 列 |
| 子集下载方式 + 明确的「不全量」过滤条件 | ✅ | §6.1/§6.2 六条硬约束 |
| 许可与引用 | ✅ | §9 Apache-2.0 + 官方 BibTeX + ICCV 2025 |
| 抽样设计（保险类型 × 任务层级、体量与理由） | ✅ | §7 |
| 可直接执行的命令草案 + 磁盘预估 | ✅ | §8（bash + python 全量脚本）+ §8.4 |
| HF 不可达时的回退方案 | ✅ | §5 可达性矩阵 + §11 回退表（已实际启用镜像） |
| ≥3 个独立来源、记录 URL+时间 | ✅ | §1 共 9 条（S1–S7 外部 + S8/S9 实测） |
| 禁止凭记忆写字段名 | ✅ | 全部列名来自 Range 读取的实际 header 字节（S8） |

---

## 勘误记录

### 勘误 1（2026-11-18，任务 t28 / D2b，队长裁定 D-01）—— 清除已删除路径的陈旧引用

**背景**：`homework5/insurance-agent/` 目录已按 D-01 裁决删除，但本日志与配套研究报告里仍残留该路径，读者会去找一个不存在的目录。本次**只做路径口径更正**，**结论、数字、来源表、验收自检一字未改**。

| # | 位置 | 改前 | 改后 | 为什么 |
|---|---|---|---|---|
| 1 | 本文件第 1 行 | `> **同源副本**：与 `insurance-agent/docs/log/step-r2.md` 内容一致。` | `> 勘误（2026-11-18，队长裁定 D-01）：原首行写「与 insurance-agent/… 同源副本」，但该目录已按 D-01 删除。本文件即唯一版本，内容未变。` + 一行说明 | 指向的目录已不存在；且“副本/以那份为准”会让读者去错位置。改为“唯一版本”并留痕 |
| 2 | 本文件第 11 行（现为第 12 行，首行改两行导致 +1 位移；`\| 产出 \|` 行） | `insurance-agent/docs/research/ins-mmbench-access.md`（主交付） | `renewal-assistant/docs/research/ins-mmbench-access.md`（主交付） | 改成**真实存在**的交付路径（左列为 D-01 已删除路径，仅作勘误对照） |
| 3 | 本文件第 40 行（现为第 41 行；时间线 00:45 行） | `insurance-agent/docs/research/ins-mmbench-access.md` | `renewal-assistant/docs/research/ins-mmbench-access.md` | 同上（左列为 D-01 已删除路径，仅作勘误对照） |
| 4 | `docs/research/ins-mmbench-access.md` 第 1 行 | `> **同源副本**：本文件与 `insurance-agent/...` 内容一致…以 `insurance-agent/...` 下的版本为准。` | `> **唯一版本**（2026-11-18 勘误，队长裁定 D-01）：本文件即唯一交付版本；原写的 `insurance-agent/...` 副本已按 D-01 删除。内容未变。` | 同上；并明确“本文件才是正本” |

**未改动的内容（审计对照）**：
- 第 2–11 行的任务表（任务号 / 执行者 / attempt_id / 时间窗 / 结论）——原样；
- 第 1 章 9 条来源表（S1–S9，URL 与检索时间）——原样；
- 第 2 章 F1–F8 全部数字（2,900,191,262 B / 12,052 图 / 10,372 题 / 876 KB / 400 行 vs 270 题 …）——原样；
- 第 3 章抽样方案决策表、第 4 章可复用片段、第 5 章未决事项、第 6 章验收自检表——原样。

**遗留（不在本人写作用域，未改）**：
- `docs/research/evidence/probe_langgraph_api.py` 第 4–6 行 docstring 的调用示例仍写 `insurance-agent/docs/research/evidence/probe_langgraph_api.py`（属 flow-engineer 的证据文件，D-01 已删除路径）→ **待 flow-engineer 更正**。
