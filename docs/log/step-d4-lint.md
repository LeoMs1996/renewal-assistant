# step-d4 · D4 质检（pilot QC：3 页口径）

> 任务：`t7`（attempt 1，`896f9d76-9abc-4a60-9ebc-a72de02c8ec9`）｜执行：wiki-lead｜日期：2026-11-18
> **定位（按船长澄清）**：t7 是 **pilot QC + 工具验证**，不是最终质检；全量 36 页质检由 t23 承接。
> 结论：两套 lint 在 3 页上**均 0 error**；人工复核 44 条断言 + 4 个逐字引用块，**发现 7 类缺陷并全部修复**（修复前按断言计 18/44 需修）。

---

## 1. 做了什么（改动清单）

| 文件 | 性质 | 职责 |
|---|---|---|
| `data/llm-wiki-claims/scripts/wiki_claims_lint.py` | **新增**（独立第二套检查器） | E1 frontmatter / E2 index 一致性 / E3 孤儿 / E4 重复 / E5 死链 source_refs+双射 / E6 空页超长 / E7 正文死链 / E8 log 一致性 / E9 span 可解析；`--sample N --seed` 提供可复现抽样 |
| `data/llm-wiki-claims/scripts/compile_wiki.py` | 修改 | 修 7 类复核缺陷；`claim_type` → `insurance_line`；span 语法扩到 JSON 路径；schema 增改名记录 |
| `data/llm-wiki-claims/scripts/wiki_lint.py` | 修改 | 同步 `insurance_line`、`【方法约束】` 免标记、JSON 路径 span、图片路径误判修正 |
| `data/llm-wiki-claims/wiki/{docs,sections,faqs}/*.md` | 重建 | 3 页按修复后模板重生成（幂等） |
| `data/llm-wiki-claims/wiki/{schema.md,index.md,log.md,README.md}` | 重建/更新 | 同步字段改名与 schema 说明 |
| `docs/log/step-d4-lint.md` | 新增 | 本日志 |

**没碰**：`raw/**`、续保 `wiki/`、`server/`、`tests/`、`mcp_servers/`、`SPEC.md`、`traces/`。`git status -- wiki traces server tests SPEC.md mcp_servers` 与 `git diff 40541d1 -- …` 均为空。

---

## 2. 质检口径与来源（先检索，不自创标准）

| # | 来源 | URL | 检索时间 | 支撑的检查项 |
|---|---|---|---|---|
| S1 | Karpathy《LLM Wiki》gist 原文 | https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw | 2026-11-18 | lint 对象：页面间矛盾、被新源取代的过期断言、**孤儿页（无入链）**、缺失概念页、**缺失互链**；index/log 的角色 |
| S2 | `chenhz01/memory-wiki` README | https://github.com/chenhz01/memory-wiki | 2026-11-18 | 具体检查项清单：**未被索引的孤儿、缺日期、标题重复、超长文件、相对链接断裂**；`lint` **exit 1** 作 CI 门禁；ingest 不得静默覆盖 |
| S3 | `nashsu/llm_wiki` README | https://raw.githubusercontent.com/nashsu/llm_wiki/main/README.md | 2026-11-18 | 每页 YAML frontmatter + `sources[]` 溯源；隔离页/稀疏社区作为「知识缺口」信号；人工 review 用**受限动作集**防幻觉 |
| S4（复用 R1） | R1 `docs/research/llmwiki-spec.md` §7 | 本地 | 2026-11-18 | L1–L11 的级别划分：**只自动修派生文件，语义改动必须人工** |

> 另有一次 `search.run`（「wiki lint checklist / 自动化 vs 人工」）**返回 0 条达标证据**（`no_page_content`），已在 §6 登记为缺口；上述口径仅由 S1–S4 支撑，未引入任何未读到的内容。

**口径落点**：S2 的 5 项 + S1 的 4 项 → 全部映射到 E1–E9（见 §3.1）；S4 的「谁能自动修」→ 决定 lint **只报告不自动改**（本步一次都没有自动写页面，全部靠修生成器重跑）。

---

## 3. 验证证据

### 3.1 哪些能自动、哪些必须人工（脚本化边界）

| 检查 | 自动？ | 实现 | 依据 |
|---|---|---|---|
| frontmatter 完整性/枚举 | ✅ | E1 | S3、S4 |
| index ↔ 磁盘双向一致、摘要/类型漂移 | ✅ | E2 | S1、S2 |
| 孤儿页（无入链且不在 index） | ✅ | E3 | S1（orphan pages）、S2（orphans not in index） |
| 重复页（id/title/slug） | ✅ | E4 | S2（duplicate titles） |
| 死链 source_refs（qid 不在 manifest / raw 文件缺失 / 与 raw_refs 非双射） | ✅ | E5 | S3（`sources[]` 溯源） |
| 空页 / 超长页 | ✅ | E6 | S2（overlong files） |
| 正文 `[[link]]` 死链 | ✅ | E7 | S2（broken relative links） |
| log 可 grep + 每页有 ingest 记录 | ✅ | E8 | S1（log 前缀与 grep 用法） |
| span 可解析（行区间越界 / labels 键不存在 / JSON 路径不存在 / 图片路径不存在） | ✅ | E9 | S4（断言级引用） |
| **引用存在但语义张冠李戴** | ❌ **必须人工** | — | 这是本轮实际抓到 7 处缺陷的主要来源；字符串比对永远判不出「标记指向 A 字段、句子在说 B 事」 |
| 摘要是否真概括了页面内容 | ❌ 人工 | — | 可用长度启发式（W1）挡明显异常，语义准确度只能人判 |
| 跨页说法是否冲突（同一实体两页口径不一致） | ❌ 人工（≥2 页才有意义） | — | S1「矛盾优先」；3 页阶段无法系统验证 |
| 该主题是否还有未建的页（覆盖缺口） | ❌ 人工 | — | S1「缺失概念页」；需对照 `plan.md` §3 主题表与业务问题流 |

### 3.2 两套 lint 的原文输出（交叉验证）

```text
$ python3 data/llm-wiki-claims/scripts/wiki_claims_lint.py --sample 10
=== wiki_claims_lint（独立实现）===
pages=3 index_rows=3 ERROR=0 WARN=0

=== 可复现随机抽样（seed=20261118，n=3）===
  sections/agri-insured-subject.md
  docs/ins-mmbench-agricultural.md
  faqs/agri.md
  注：语料仅 3 页，不足 10 页，已全取
D4 exit=0

$ python3 data/llm-wiki-claims/scripts/wiki_lint.py
pages=3 index_rows=3 FAIL=0 WARN=0
D3 exit=0
```

两套检查器**结构不同、判定路径不同**（D3 版走「段落扫描 + 引用块配对」，D4 版走「逐页面元数据 + 全局集合运算」），结论一致 → 不是同一实现的自我确认。

### 3.3 负向控制（证明 lint 真咬得住）

| # | 注入的错误 | 谁抓到 | 输出 |
|---|---|---|---|
| A | 逐字引用块里 `Species`→`Specie` | D3 lint | `[L6] 逐字引用块与 raw 不一致（L9-L9）` |
| B | 删 frontmatter `claim_type`（改名前的字段） | D3 lint | `[L1] 缺少必填字段` + `枚举非法: None` |
| C | 删整页 `faqs/agri.md` | D3 lint | `[L2] 索引指向不存在的页面` + `[L3] related 指向不存在的页面` |
| D | 注入编造 bullet（"赔付上限通常为保额 80%"） | D3 lint | `[L7] bullet 无来源标记` |
| E | 把 `@sample.task_layer` 改成 `@sample.nonexistent_key` | **D4 lint** | `[E] E9 … JSON 路径不存在：sample.nonexistent_key` |

E 是本轮新增的：证明 span 校验不止认「labels.键」，也认 JSON 路径，改错路径同样会 FAIL。

### 3.4 幂等与隔离

```text
$ 两次 build 后比对 6 个生成物 sha256
IDEMPOTENT: 6 个生成物 sha256 一致

$ git status --short -- wiki traces server tests SPEC.md mcp_servers
（空输出）
$ git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md
（空输出）
```

---

## 4. 人工复核：44 条断言 + 4 个逐字引用块，7 类缺陷

复核方法（可复现）：把每一页的**断言行**（bullet / 表数据行）连同其标记抽出，再把标记解析成 raw 里的实际值（`labels.*` / 行区间原文 / JSON 路径值 / 图片路径），逐条判断「该证据是否支撑这句话」。

| 页 | 断言数 | 逐字引用块 |
|---|---|---|
| `docs/ins-mmbench-agricultural.md` | 15（12 表行 + 3 bullet） | 1 |
| `sections/agri-insured-subject.md` | 14（12 表行 + 2 bullet） | 2 |
| `faqs/agri.md` | 15（12 表行 + 3 bullet） | 1 |
| 合计 | **44** | **4（逐字比对全部一致）** |

### 4.1 发现的 7 类缺陷（全部已修）

| ID | 缺陷 | 性质 | 修法 |
|---|---|---|---|
| F1 | FAQ「（证据：逐行见下）」指向**页面上不存在的表** | 悬空证据指针 | FAQ §2 补逐单元表，指针改为「上表逐行」 |
| F2 | FAQ「字段清单（4 个）」只挂 1 个字段标记 | 引用覆盖不足 | 改为 4 个字段标记各一 |
| F3 | FAQ「`answer` 列不存在」挂的是 `labels.claim` | **支撑错配**（标记指向别的字段） | 改挂 `@answer_status`（raw 根字段），并扩展 span 语法支持 JSON 路径 |
| F4 | section「不得用于分类准确率」是**评测口径约束**，却挂了数据标记 | 政策句伪装成样本断言 | 改为 `- 【方法约束】` 开头、不挂标记；两套 lint 同步支持该前缀（免标记） |
| F5 | doc「4 个 LABEL 键完全一致」只用 `labels.species` 一个标记 | 引用覆盖不足 | 改为 4 个区间标记逐键覆盖 |
| F6 | doc §1 表的「LABEL 键」列挂 `@L1-L17`（题干行区间） | **支撑错配**：题干行区间证明不了 labels 的键 | 删除该列；键的断言改由 §2 的键级标记承担；表只登记样本定位 |
| F7 | doc §4「`task_layer` 全为 scenario」挂 `@labels.species` | **支撑错配** | 改挂 `@sample.task_layer` + `@sample.meta_task`（层级事实来自 `sample` 段） |

**通过率（如实）**：
- 修复前：按断言计 **18/44 需修（40.9%）**——其中 F6 一处模式缺陷覆盖 doc 页 12 行；按**缺陷模式**计 **7 类**。
- 修复后：44/44 断言均有能支撑它的标记；两套 lint `0 error`；幂等保持。
- 逐字引用块：4/4 与 raw 完全一致（含行首缩进），0 例外。

> 说明：F3/F6/F7 三处**字符串比对抓不到**——标记都合法、qid 都存在、span 也都能解析，只是指向了错误的字段。这正是「lint 自动 + 人工复核」必须并存的原因，也是 t23 需要 ≥6 页人工抽检的理由。

### 4.2 字段改名（船长裁决二）：`claim_type` → `insurance_line`

- 生成器 `CLAIM_TYPE` → `INSURANCE_LINE`，frontmatter 键改为 `insurance_line`；值域不变（6 个业务类型）。
- 两套 lint 的必填列表与枚举检查同步改；`schema.md` 增加 **§2.1 改名记录**（含理由与旧名映射），避免后来人以为是两个字段。
- 残留检查：`grep -rn claim_type` 在 `data/llm-wiki-claims/**` 仅剩 schema 的改名记录 + 生成器模板文本，**0 处误用**。

### 4.3 回答船长关于 id 的坑（我的 lint 用哪个？）

**两套 lint 都按 frontmatter `id` 匹配，不用文件名**：

```text
wiki_lint.py:358   id_to_rel = {str(i["fm"].get("id", "")): str(i["rel"]) for i in infos.values()}
wiki_lint.py:366   if str(info["fm"].get("id")) not in other["related"]:   # 双向校验也按 id
wiki_claims_lint.py:279   slug = pathlib.Path(p).stem                      # ← 唯一用文件名的地方
```

唯一按文件名的是 **E4 的 slug 重复检查**（判的是「两个不同目录下同名文件」），这是**有意**的：文件名重复是真问题，`related` 比对则一律用 id。D3 的 L3 与 D4 的 E3/E4 都用 id，不会出现你踩到的那种 4 条误报。

---

## 5. 3 页阶段能确认 vs 必须等 t23

| 项 | 3 页阶段 | 36 页后（t23） |
|---|---|---|
| lint 工具能咬住问题（4+1 次负向控制） | ✅ 已确认 | 需补 2 次专打 entity 页 |
| frontmatter/index/log/span 的结构一致性 | ✅ 已确认（3/3 页） | 全量复核 + 跨分片一致性 |
| 逐字引用与 raw 完全一致 | ✅ 已确认（4/4 块） | 全量（预计 100+ 块） |
| 引用是否**语义支撑**断言 | ✅ 已建立方法并抓到 7 类 | **≥6 页抽样人工复核**（本轮 44 条断言已是 3 页全量） |
| 跨页冲突（同一实体两页口径不一致） | ❌ 无法验证（仅 3 页且同分片） | 必须做，尤其 entity 页 vs section 页 |
| 覆盖缺口（该建未建的页） | ❌ 无法验证 | 对照 `plan.md` §3 主题表核 36 页 |
| index 的 L0 体量（≤3k tokens） | ⚠️ 1.5 KB 远未触发 | 36 页后必须量，可能触发分卷 |
| entity 页「属性带标记」 | ❌ 模板未实现（`body_entity()` 待 t20） | 必须验，且要新增 2 次负向控制 |

**t23 的可复现抽样命令（已内建）**：

```bash
python3 data/llm-wiki-claims/scripts/wiki_claims_lint.py --sample 10 --seed 20261118
```

---

## 6. 遗留与交接

| # | 事项 | 承接方 | 说明 |
|---|---|---|---|
| 1 | 剩余 33 页 + `body_entity()` + 分批 lint | **t20** | 每批 `build` → `wiki_lint.py` + `wiki_claims_lint.py` 均 0 error 再进下一批；entity 页额外要求「每个属性带 `@labels.*` 或行区间」 |
| 2 | 36 页全量质检 + ≥6 页人工抽样 | **t23** | 复用本步方法与 `--sample --seed`；重点补：跨页冲突、覆盖缺口、index 体量、entity 页负向控制 |
| 3 | `claim_type` → `insurance_line` 已改完（3 页口径） | ✅ 已完成 | t20 生成新页时自然继承；`schema.md` §2.1 有改名记录 |
| 4 | 「语义张冠李戴」无法自动化 | 长期 | 建议 t23 把本步的「断言—证据解析表」脚本化（把 bullet/表行 + 标记 + raw 实际值打成一张表供人判），我本轮是临时脚本，未入库 |
| 5 | 一次 `search.run` 0 证据 | 已登记 | 「wiki lint checklist / 自动化 vs 人工」方向无达标证据，口径由 S1–S4 支撑，未引入未读到的内容 |
| 6 | 本步是**自审**（D3 页 + 我写的 lint） | 需注意 | 我既是页作者又是质检者；交叉验证靠「另写一套 lint + 船长独立比对脚本」缓解，但**不能替代第三方评审**。建议 t23 由其它 Agent 执行，或至少由船长抽检 |

**一句话交接**：lint 工具与方法已固化并验证有效（能咬住注入缺陷，也能在人工复核里定位「引用错配」）；3 页口径下 `0 error` 是**工具可信**的证据，不是「36 页质量已保证」的结论。
