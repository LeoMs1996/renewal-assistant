# C0 基线守护 · 不可变证明

> 步骤：C0（方案 C 第 0 步，先立护栏再动土）
> 执行人：integrate / integrator（AgentTeams `insurance-intel-2026`，task t13）
> 采集时间：**2026-11-17T23:51:40+0800**
> 工作目录：`/Users/leoms/Documents/deepseek-harness-workspace/homework5/renewal-assistant`（该目录本身即 git 仓库根）

## 0. 这份文件为什么存在

方案 C = **在已交付的续保系统内部新增理赔域**。风险不是「新功能写不出来」，而是「写理赔时把续保弄坏了」。
续保系统当前的状态是 **148 passed / 2 skipped、SPEC v1.0.6、19 条验收用例全绿**——这就是要被保护的对象。

本文件把该状态固化成**可复跑的指纹**：

- C1–C4（抽样 / 萃取 / 检索 / 编排）每一步动工前后，都必须能用第 6 节的复跑命令与本文件对照；
- C5 终验直接复跑第 2 节**全部**命令，逐条比对，任一数字漂移即为回归。

**本文档一经写入不再修改**（只允许在末尾追加「复核补记」小节并注明时间与原因）。若基线本身需要升级，另开新文件 `step-c0-baseline-v2.md`，不要就地改数字。

---

## 1. 环境指纹

| 项 | 值 |
|---|---|
| 采集时间 | 2026-11-17T23:51:40+0800 |
| 主机 / 架构 | Darwin arm64（macOS 26.4） |
| Python | 3.14.2（`renewal-assistant/.venv/bin/python`） |
| git | 2.50.0 |
| 仓库 HEAD | `40541d1b89274990cd5be096fe5e15ad61149d72` |
| 分支 | `master` |
| 仓库 tracked 文件数 | 143 |
| 采集时 `git status` | 干净（无要提交的改动） |

---

## 2. 基线命令 —— 真实输出原文

以下四组均为**屏幕原文粘贴**（含进度点与空行），非转述。除 `SPEC.md` 指纹外，均使用项目自带虚拟环境 `.venv`，避免系统 python 缺依赖导致的假失败。

### 2.1 `git rev-parse HEAD`

```text
$ git rev-parse HEAD
40541d1b89274990cd5be096fe5e15ad61149d72
```

### 2.2 `python -m pytest`

```text
$ .venv/bin/python -m pytest
..............................................s......................... [ 48%]
..........s............................................................. [ 96%]
......                                                                   [100%]
148 passed, 2 skipped in 1.61s
```

- 收集数：150（148 passed + 2 skipped）；`addopts = "-q"` 见 `pyproject.toml`。
- 2 个 skip 为设计内跳过（脚本式测试由 CI 单独运行，见 `tests/conftest.py` / `mcp_servers/conftest.py` 的 `collect_ignore`）。
- **C5 判定线：`148 passed, 2 skipped`，一个都不能少，也不允许出现 `failed` / `error`。**

### 2.3 `python -m ruff check .`

```text
$ .venv/bin/python -m ruff check .
All checks passed!
exit=0
```

### 2.4 `python -m mypy`

```text
$ .venv/bin/python -m mypy
server/middleware.py:136: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
Success: no issues found in 7 source files
```

- `note:` 是 mypy 的**提示**（非错误），基线时刻即存在，属预期状态；C5 比对时应允许该行原样出现。
- `7 source files` 来自 `pyproject.toml` 的 `[tool.mypy] files` 显式白名单（`config/middleware/sessions/trace/metrics/otel_export/memory`）。**理赔域若要纳入类型门禁，必须显式追加到该白名单**——历史教训：`memory.py`、`otel_export.py` 曾因「只被导入、未列入」而漏掉 11 / 14 处类型错误。

### 2.5 `SPEC.md` 契约指纹

```text
$ shasum -a 256 SPEC.md
e3c74c6e22397f23d5fe0a22978579b9a9b342fc43263c22bffc9fc57f831d8e  SPEC.md
```

- SPEC 当前版本：**v1.0.6**（2026-11-17，见 `SPEC.md:5`），变更为非破坏性追加（`llm_degraded` 事件 / `degraded` 字段 / 轨迹可选字段）。
- **C1–C4 一律不得修改 `SPEC.md`。** 理赔域契约另立 `claims/SPEC-claims.md`，续保 SPEC 只增不改；确需改动必须单独提交并在本文件末尾追加「复核补记」。

---

## 3. 辅助指纹（非命令输出，供交叉核对）

| 项 | 基线值 | 说明 |
|---|---|---|
| `.gitignore` sha256 | `0befe581845b7334f7ee4ab96da5c65e0cd3196005d2317a29bf8d5e98bd422f` | **本次改动前**的指纹；C0 会追加理赔域隔离段（见第 7 节） |
| `.gitignore` 行数 | 31 | 同上 |
| `pyproject.toml` sha256 | `9f2ba0e7af2eb6817ca9cf7cfd6ee1156477f8c05ec38fc51030fb8d7587b8d1` | 本次**不应**变化 |
| 验收用例 | 19（`eval/cases/AC-01..14.json` + `SEC-01..05.json`） | C5 需要 19/19 全绿 |
| LLM-Wiki 条目 | 11 个 `.md`（8 条目 + `index.md` + `log.md` + `README.md`） | 续保知识库，**只读** |
| `traces/` 文件数 | 1183 | 已整体 gitignore（运行态/PII），不入库，仅作现场记录 |

---

## 4. 这些是「保护对象」—— C1–C4 的硬边界

| 路径 | 允许 | 禁止 |
|---|---|---|
| `server/**` | — | **禁止修改**（理赔域如确需复用，走「导入 + 传参」而非改源码；必要时另开任务并单独评审） |
| `tests/**`、`mcp_servers/test_*.py` | — | **禁止修改/删除**（148 条即基线） |
| `SPEC.md` | — | **禁止修改** |
| `wiki/**` | — | **禁止写入**（理赔知识走 `data/llm-wiki-claims/wiki/`） |
| `traces/**` | — | **禁止写入**（理赔轨迹走 `traces-claims/`） |
| `eval/cases/**` | — | 禁止修改既有 19 条；新增理赔用例另建 `eval/cases-claims/`（C3/C4 决定） |
| `claims/**` | 新增 | 仅本域源码 |
| `data/**`、`traces-claims/**` | 新增 | 仅本域数据与运行态 |

---

## 5. 目录骨架与物理隔离（本次建立）

```text
renewal-assistant/
├── claims/                          # 理赔域源码（本步仅占位）
│   ├── README.md                    #   域职责 + 隔离规约
│   ├── SPEC-claims.md               #   理赔域契约占位（勿写进 SPEC.md）
│   ├── graph.py                     #   LangGraph 编排占位（节点未实现）
│   ├── deep_agents/README.md        #   长程材料分析（Deep Agents）占位
│   ├── tools/README.md              #   理赔工具/MCP 占位
│   └── tests/README.md              #   理赔测试占位
├── data/
│   ├── ins-mmbench/                 #   INS-MMBench 子集（大文件，gitignored，仅留占位）
│   └── llm-wiki-claims/
│       ├── raw/                     #   抽样原文（可入库，溯源证据）
│       └── wiki/                     #   理赔 LLM-Wiki（入库）—— 与 wiki/ 物理分离
├── traces-claims/                   # 理赔轨迹（gitignored，仅留占位）—— 与 traces/ 物理分离
└── docs/log/                        # 全程文档（本文件 + hard-rules.md）
```

**隔离不是靠约定，是靠路径 + 环境变量。** 既有 `server/config.py` 已支持：

```python
TRACE_DIR = Path(env("TRACE_DIR", str(BASE_DIR / "traces")) ...)
WIKI_DIR  = Path(env("WIKI_DIR",  str(BASE_DIR / "wiki"))   ...)
```

因此理赔域运行时**必须**注入 `TRACE_DIR=traces-claims`、`WIKI_DIR=data/llm-wiki-claims/wiki`（见 `traces-claims/README.md`、`data/llm-wiki-claims/wiki/README.md`）。这样即使误调用续保 `trace.py` / `wiki_search.py`，落盘位置也不会污染续保目录——**不需要改 `server/` 一行代码**。

---

## 6. C5 复跑方式（照抄即可）

```bash
cd renewal-assistant
git rev-parse HEAD                                   # 期望：HEAD 前移（允许），但 40541d1 必须是祖先
git merge-base --is-ancestor 40541d1 HEAD && echo OK  # 基线仍在历史中
.venv/bin/python -m pytest                           # 期望：148 passed, 2 skipped
.venv/bin/python -m ruff check .                     # 期望：All checks passed!
.venv/bin/python -m mypy                             # 期望：Success: no issues found in 7 source files
shasum -a 256 SPEC.md                                # 期望：e3c74c6e... 完全一致
git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md
                                                     # 期望：空输出（保护对象零改动）
```

最后一条是**关键判定**：`server/ tests/ mcp_servers/ wiki/ SPEC.md` 相对 `40541d1` 的 diff 必须为空。若不为空，说明理赔域改动了保护对象，C5 直接判失败。

---

## 7. 本步骤变更清单（唯一允许的改动）

| 类型 | 路径 |
|---|---|
| 新增目录骨架 | `claims/**`、`data/**`、`traces-claims/**`、`docs/log/**` |
| 修改既有文件 | `.gitignore`（追加「理赔域隔离」段，见下） |

`.gitignore` 追加内容与依据：

1. `data/ins-mmbench/**`（白名单保留 `.gitkeep`/`README.md`）—— 第三方数据集体积大，入库会拖垮仓库。依据：GitHub 官方 50 MiB 警告 / 100 MiB 拒收、仓库建议 <1 GB（见第 8 节来源 S2）。
2. `traces-claims/**`（白名单保留 `.gitkeep`/`README.md`）—— 理赔轨迹含报案人 PII，与续保 `traces/` 同属运行态。
3. 注释同步更新，说明「为什么忽略」而非只写「忽略什么」。

`data/llm-wiki-claims/` **不忽略**：它是知识产物（LLM-Wiki 条目 + 抽样原文），属交付物；仅当 `raw/` 单文件超过 10 MiB 时才追加忽略（阈值与处置见 `data/README.md`）。

---

## 8. 硬规则依据：本次 MCP 检索记录（≥3 独立来源）

检索时间统一为 **2026-11-17**，工具 `web_call search.run` / `read.fetch`。用途 = 该来源支撑了本步骤的哪条决策。

| # | 来源 | URL | 检索时间 | 用于支撑的决策 |
|---|---|---|---|---|
| S1 | Git 官方文档 · gitignore（pattern 语义、优先级、嵌套 `.gitignore`、「排除全部但保留某目录」示例） | https://git-scm.com/docs/gitignore | 2026-11-17 | 「忽略大目录但保留占位文件」必须用 `dir/**` + `!` 白名单，且父目录本身不能被忽略，否则 `!` 失效——本文件第 7 节的写法即据此 |
| S2 | GitHub Docs · About large files on GitHub（50 MiB 警告 / 100 MiB 阻断 / 仓库建议 <1 GB） | https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github | 2026-11-17 | `data/ins-mmbench/` 必须 gitignore；LFS 与 Release 是超限时的替代，本地演示仓库不引入 LFS |
| S3 | OWASP Cheat Sheet · Logging（审计日志用途、baseline 建立、「日志的不可否认性难以真正实现」的告警） | https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html | 2026-11-17 | 基线留档需**可复跑的原始输出**而非结论转述；同时提醒：本基线是「工程对照」，不宣称密码学不可否认性 |
| S4 | Trunk Based Development · Monorepos（单一 trunk、原子提交、结构化目录树避免混乱布局） | https://trunkbaseddevelopment.com/monorepos/ | 2026-11-17 | 在同仓库新增子域＝新增结构化子树 + 原子提交；子域之间靠目录边界隔离，不新建仓库 |
| S5 | Software Engineering at Google · Ch16 Version Control（仓库作为 source of truth、版本控制策略） | https://abseil.io/resources/swe-book/html/ch16.html | 2026-11-17 | 基线以 commit 为锚（`40541d1`）+ 文件内容哈希双重固定，避免「只认 tag」的漂移 |

> 说明：S1–S5 均于本次会话内实际抓取（`read.fetch` 返回正文摘录），非模型内置记忆。上述决策与来源的对应关系可在各 README 中复核。

---

## 9. 已知限制（诚实登记）

1. **`traces/` 未纳入指纹计数**：1183 个文件是评审期测试产物，数量会随任何测试运行增长；只登记、不作判定线。
2. **基线是单机单环境快照**：Python 3.14.2 / arm64 macOS。C5 若换环境复跑，Python 小版本差异需单独说明，不得直接判回归。
3. **`git status` 干净 ≠ 无风险**：`traces/`、`.venv/` 等已 gitignore，本基线只覆盖**入库内容**。
4. **§2.2 的耗时数字（1.61s）不构成判定线**，仅证明当次执行完成。
