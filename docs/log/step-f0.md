# Step F0 — 环境隔离与 deepagents 0.7.39 安装验证

- 任务：t15（owner: deepagents-engineer）
- 执行时间：2026-11-18 00:34–00:55（Asia/Shanghai）
- 目标：在不污染续保共享 `.venv`（基线 **148 passed, 2 skipped**）的前提下，建立装有 `deepagents==0.7.39` 的**独立**环境，并证明零回归 + 复核 R3 的四条结论。
- 一句话结果：**全部达成**。`.venv` 全程字节未变（shasum 与 `pip freeze` 双重一致），`.venv-claims` 装好 13 个新包，**两边 pytest 均 148 passed, 2 skipped**，R3 四条断言 4/4 成立（其中 A2 措辞需收紧，见 §6）。

## 1. 裁决依据（主 Agent A1）

flow-engineer 的 R3（t3）实测：装 deepagents 新增 13 个包，且 `langchain-core 1.8.0→1.8.1`、`tenacity 9.2.1→9.1.4`（**降级**）。共享 `.venv` 是续保基线运行环境。
主 Agent 裁决：**批准安装，禁止污染共享 `.venv`**；采用「整份 venv 复制」隔离。
我复核并补充的两条独立证据（详见 `docs/research/f0-deepagents-0739-install-evidence.md`）：

- **为什么隔离是必须的（不是保守）**：`deepagents 0.7.39` 的 METADATA 硬约束 `langchain-core<2.0.0,>=1.8.1`，共享环境是 `1.8.0` → 装进去必然升级 langchain-core。
- **降级真因定位**：`tenacity` 降到 9.1.4 不是 langchain-core 或 yank 导致，而是 `langchain-google-genai → google-genai 3.4.0` 的 `tenacity<9.2.0,>=8.2.3` 上限；`tenacity 9.2.1` 在 PyPI 上仍是最新且**未被 yank**。降级是确定性的、可解释的。

## 2. 做了什么（按时间顺序）

| 步骤 | 命令/动作 | 结果 |
|---|---|---|
| 1 | `shasum -a 256 .venv/bin/python` + `pip freeze > /tmp/freeze-base.txt` | `332c0783…57ce6`；75 包；`langchain-core==1.8.0`、`langgraph==1.2.20`、`langsmith==0.14.17`、`tenacity==9.2.1`、**无 deepagents** |
| 2 | `cp -a .venv .venv-claims` | 5.17s，275M→275M；`.venv-claims/bin/python -c sys.prefix` 指向 `.venv-claims`（复制后可用） |
| 3 | `.venv-claims/bin/python -m pip install deepagents==0.7.39 --dry-run` | 「Would install」13 个包，**列表内无 langgraph** |
| 4 | `.venv-claims/bin/python -m pip install deepagents==0.7.39` | `install_exit=0`，成功装 13 个包 |
| 5 | `.venv-claims/bin/python -m pip freeze > claims/requirements-claims.txt` | 86 行，含 `deepagents==0.7.39` |
| 6 | 双跑 pytest（见 §3） | A: 148 passed, 2 skipped；B: 148 passed, 2 skipped |
| 7 | R3 断言探针 `claims/deep_agents/probe_f0.py`（见 §4） | 4/4 PASS |
| 8 | 复核共享 `.venv` | shasum 与 freeze **均与基线逐字一致** |

**dry-run 原文（关键行，逐字）**：

```
Would install bracex-3.2.3 deepagents-0.7.39 filetype-1.2.0 google-auth-2.62.2 google-genai-3.4.0 langchain-1.5.0 langchain-anthropic-1.7.10 langchain-core-1.8.1 langchain-google-genai-4.5.0 pyasn1-0.6.5 pyasn1_modules-0.4.2 tenacity-9.1.4 wcmatch-12.0.3
```

**真装原文（逐字）**：

```
Successfully installed bracex-3.2.3 deepagents-0.7.39 filetype-1.2.0 google-auth-2.62.2 google-genai-3.4.0 langchain-1.5.0 langchain-anthropic-1.7.10 langchain-core-1.8.1 langchain-google-genai-4.5.0 pyasn1-0.6.5 pyasn1-modules-0.4.2 tenacity-9.1.4 wcmatch-12.0.3
```

**`diff /tmp/freeze-base.txt /tmp/freeze-claims.txt` 全文（逐字）**：

```
7a8
> bracex==3.2.3
12a14
> deepagents==0.7.39
15a18,20
> filetype==1.2.0
> google-auth==2.62.2
> google-genai==3.4.0
28c33,36
< langchain-core==1.8.0
---
> langchain==1.5.0
> langchain-anthropic==1.7.10
> langchain-core==1.8.1
> langchain-google-genai==4.5.0
47a56,57
> pyasn1==0.6.5
> pyasn1_modules==0.4.2
66c76
< tenacity==9.2.1
---
> tenacity==9.1.4
72a83
> wcmatch==12.0.3
```

> 即：**+13 新增，2 处版本变动（langchain-core 升、tenacity 降），langgraph 不动**。与 R3 的数量结论一致。

## 3. 零回归双跑（核心验收，原文）

### 3.1 严格按任务书写法 `.venv/bin/python -m pytest -q`

`pyproject.toml` 已有 `addopts = "-q"`，命令行再给 `-q` 实际等于 `-qq`，**汇总行会被吞掉**（只剩进度点）。原文如下：

```
..............................................s......................... [ 48%]
..........s............................................................. [ 96%]
......                                                                   [100%]
RUN_A_EXIT=0
```

```
..............................................s......................... [ 48%]
..........s............................................................. [ 96%]
......                                                                   [100%]
RUN_B_EXIT=0
```

两行列数与「2 个 s」与 C0 基线一致，但没有可核对的数字汇总行。

### 3.2 追加一次带汇总行的同构跑（`-o addopts=""` 抵消重复的 `-q`）

```
### RUN A (final): .venv/bin/python -m pytest -q -o addopts=''
..............................................s......................... [ 48%]
..........s............................................................. [ 96%]
......                                                                   [100%]
148 passed, 2 skipped in 1.53s
RUN_A_EXIT=0

### RUN B (final): .venv-claims/bin/python -m pytest -q -o addopts=''
..............................................s......................... [ 48%]
..........s............................................................. [ 96%]
......                                                                   [100%]
148 passed, 2 skipped in 1.63s
RUN_B_EXIT=0
```

**结论**：`langchain-core 1.8.1` + `tenacity 9.1.4` 环境下，续保 148 tests **零回归**（与 C0 基线一字不差）。

### 3.3 共享 `.venv` 完整性（装完之后再测）

```
### POST-INSTALL shared .venv integrity check 2026-11-17T16:42:05Z
332c0783571fe1260d5f1832321d7691109ccaf3e9b6ee1fa41ce08194b57ce6  .venv/bin/python
langchain-core==1.8.0
langgraph==1.2.20
langsmith==0.14.17
tenacity==9.2.1
deepagents in shared venv: 0
diff base-before vs base-after:
(identical)
```

全部工作结束后再复核一次：

```
332c0783571fe1260d5f1832321d7691109ccaf3e9b6ee1fa41ce08194b57ce6  .venv/bin/python
SHARED_VENV_PIP_FREEZE_IDENTICAL=yes
```

## 4. R3 四条断言：探针实证（`claims/deep_agents/probe_f0.py`）

探针设计：完全离线——用 `RecordingFakeModel(BaseChatModel)` 回放 `AIMessage` 并记录 `bind_tools` 收到的工具名（从而观察**模型可见工具面**），不读 `.env`、不发网络请求、临时文件只落 `tempfile.mkdtemp()`。

运行原文：

```
deepagents: 0.7.39
langchain_core: 1.8.1
langchain: 1.5.0
langgraph: 1.2.20

[PASS] A1 create_deep_agent(...) 返回 CompiledStateGraph（R3 §3：内部就是 LangGraph 图）
EVIDENCE: type=langgraph.graph.state.CompiledStateGraph; isinstance(CompiledStateGraph)=True; graph nodes=['PatchToolCallsMiddleware.before_agent', '_ParentNotifierMiddleware.after_agent', 'model', 'tools']

[PASS] A2 FilesystemBackend(root_dir=...) 可实例化、可读写、不向模型暴露 shell（R3 §4）
EVIDENCE: root_dir=probe-f0-d037qwec/…; file_ops=['write', 'read', 'ls', 'glob', 'grep', 'edit']; write→WriteResult(error=None, path='/probe.txt'); read→'"ReadResult(error=None, file_data={\'content\': \'hello-f0\''; model-visible tools=['delete', 'edit_file', 'glob', 'grep', 'ls', 'read_file', 'task', 'write_file']; 模型可见 shell 能力={"FilesystemBackend has 'execute' method": False, "FilesystemBackend has 'shell' attr": False, "'execute' in model-visible tools": False}; filesystem.py 中 shell 语义令牌=none; 内部 subprocess 仅为 ripgrep 加速：Popen 次数=4, argv 列表+`--`终止符=True, Python grep 回退=True; 对照组 local_shell.py 中 shell 语义令牌={'shell=True': 2}, LocalShellBackend.execute=True

[PASS] A4 v0.7 起 todo planning 为 opt-in：默认无 write_todos，显式传 TodoListMiddleware 才有（R3 §4）
EVIDENCE: default agent tools=['delete', 'edit_file', 'glob', 'grep', 'ls', 'read_file', 'task', 'write_file'] (write_todos absent=True); with TodoListMiddleware tools=['delete', 'edit_file', 'glob', 'grep', 'ls', 'read_file', 'task', 'write_file', 'write_todos'] (write_todos present=True)

[PASS] A3 子代理经 task 工具调用，且同一轮可并行多个（R3 §4）
EVIDENCE: 'task' in main tools=True; 主模型首轮一次 AIMessage 带 tool_calls=2; task ToolMessage 数=2; alpha generate_calls=1, beta generate_calls=1; task 工具描述含并行指令=True; tool_call_ids=['call_a', 'call_b']

SUMMARY: 4/4 assertions passed on deepagents 0.7.39
```

逐条解读：

1. **A1｜返回类型**：`create_deep_agent()` 返回 `langgraph.graph.state.CompiledStateGraph`，`isinstance` 为 True，图节点为 `model` / `tools` + 两个中间件钩子 → **R3 §3「内部就是 LangGraph 图」成立**，可与本项目既有 `StateGraph` 编排共存（同一个 langgraph 1.2.20）。
2. **A2｜FilesystemBackend**：可 `root_dir=` 实例化，`write`/`read` 真实落盘并读回 `hello-f0`；模型可见工具为 `ls/read_file/write_file/edit_file/delete/glob/grep/task`，**没有 `execute`**；类上无 `execute`/`shell` 属性；源码无 `shell=True`/`os.system`/`os.execv`/`os.popen`。对照组 `LocalShellBackend` 有 `execute` 且有 2 处 `shell=True` → **能力隔离是显式的**。
3. **A3｜task 并行**：主模型**一条** `AIMessage` 带 2 个 `task` tool_calls（`call_a`/`call_b`），产出 **2 条** `ToolMessage`，两个子代理模型各被调用 **1 次** → 同一轮并行扇出成立；`TASK_TOOL_DESCRIPTION` 原文含「Launch multiple agents concurrently when their tasks are independent, using a single message with multiple tool calls」。
4. **A4｜todo opt-in**：默认工具面无 `write_todos`；显式 `middleware=[TodoListMiddleware()]` 后出现 → **R3 §4 成立**（注意 `TodoListMiddleware` 来自 `langchain.agents.middleware`，不在 `deepagents` 顶层）。

## 5. 对 F3 设计的直接影响（给 t9/t11 用）

- 用 `create_deep_agent(backend=FilesystemBackend(root_dir=<材料目录>))` 就能拿到「只读/写文件、不能执行命令」的分析层，正好匹配「只做材料分析、不产出金额与决策」的边界。
- `create_deep_agent` 签名里**存在 `response_format`**（`ToolStrategy | ProviderStrategy | AutoStrategy | type[BaseModel] | dict`）——这是后续把输出**强约束成 schema** 的官方入口，可在 API 层卡住「不许给金额/结论」。
- 子代理由 `task` 工具扇出、同轮并行，适合「多份材料并行分析」；子代理规格为 `SubAgent` TypedDict：`name/description/tools/model/middleware/interrupt_on/skills/permissions/response_format/system_prompt/mode`（含 `model`，即可给不同材料分析配不同模型）。
- **默认没有 todo**：长程材料分析若要可观测的分步进度，必须显式传 `TodoListMiddleware()`，否则 UI 上不会有 `write_todos` 流。

## 6. R3 需要收紧的一处措辞（不改 R3 文件，仅报告）

R3 §4 表述「FilesystemBackend 可实例化且**不执行 shell**」在「模型可见能力」层面成立，但严格讲**不精确**：`deepagents/backends/filesystem.py` 内部 `import subprocess`，`grep` 工具会 `subprocess.Popen` 调本机 `rg`（4 处 Popen 调用）。安全上无碍——**argv 列表传参、`-F` 固定字符串模式、pattern 前有 `--` 终止符、无 `shell=True`，且失败自动回退纯 Python grep**——但准确表述应为：

> FilesystemBackend **不向模型暴露 shell 执行能力**（无 `execute` 工具、不接受模型构造的命令行）；实现内部仅为 grep 加速以固定 argv fork `rg`。

建议由 flow-engineer 在 R3 里改这一句（我不改他人产物）。这属于文档精度问题，不构成对 R3 结论的推翻。

## 7. 回滚方法

- **只需删除隔离环境**：`rm -rf /Users/leoms/Documents/deepseek-harness-workspace/homework5/renewal-assistant/.venv-claims`
- 共享 `.venv` **全程未被写入**（`cp -a` 只读源；所有 pip 操作都显式指向 `.venv-claims/bin/python`），因此续保基线无需任何恢复动作。证据：`.venv/bin/python` shasum `332c0783…57ce6` 在操作前后一致，`pip freeze` 与 `/tmp/freeze-base.txt` 逐字相同。
- 本任务新增的项目内文件（可保留，不影响 `.venv`）：`claims/requirements-claims.txt`、`claims/deep_agents/probe_f0.py`、`docs/log/step-f0.md`、`docs/research/f0-deepagents-0739-install-evidence.md`。

## 8. 遗留与风险

- **L1｜磁盘**：`.venv` 275M → `.venv-claims` 304M（+29M）。当前磁盘余量 130G，无压力；若 CI 上要复现，建议用 `uv venv` 直接建而不是复制。
- **L2｜依赖面偏大**：`langchain-anthropic`、`langchain-google-genai`、`google-genai`、`google-auth` 是 deepagents 的**硬依赖**（非 extra），共约 8 个包与我们实际用的 provider 无关。若将来要瘦身，可考虑 `pip install --no-deps` 子集 + 手写 constraints，但会脱离官方支持路径，需单独立项评估。
- **L3｜tenacity 被压在 <9.2.0**：只要 `langchain-google-genai` 在依赖图里，`tenacity` 就无法回到 9.2.1。若上游放宽，我们这边无需改动即可升级。
- **L4｜未验证真实模型**：本次全部用离线假模型，**没有**跑真实 LLM 的 tool-calling。真实 provider（GLM/OpenAI 兼容端点）对「同轮多 tool_calls」的支持度需在 F3 联调时单独验证——这是 A3 结论的唯一外推风险。
- **L5｜未做 `--dry-run` 之外的最小复现实验**：`pip install deepagents` 在**共享 `.venv`** 上的实际破坏面未实测（按裁决也不该测）。若将来要合流到共享环境，需重新评估 `langchain-core 1.8.0→1.8.1` 对续保的影响（本次双跑已证明运行时无回归，但那是隔离环境内的证据）。

## 9. 交付物清单

| 文件 | 说明 |
|---|---|
| `.venv-claims/` | 隔离环境（304M），`deepagents==0.7.39` + 13 新包，**可随时删除** |
| `claims/requirements-claims.txt` | `.venv-claims` 的 `pip freeze`（86 行，含 `deepagents==0.7.39`） |
| `claims/deep_agents/probe_f0.py` | 离线探针，4 条 R3 断言，可重复运行：`.venv-claims/bin/python claims/deep_agents/probe_f0.py` |
| `docs/research/f0-deepagents-0739-install-evidence.md` | ≥3 外部来源（PyPI JSON / 官方 docs / GitHub README）+ 安装产物 METADATA 证据 + 决策映射 |
| `docs/log/step-f0.md` | 本文件 |
