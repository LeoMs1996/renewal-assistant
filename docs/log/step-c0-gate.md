# C0 步骤自检门（已勾选）· step-c0-gate

> 模板来源：`docs/log/hard-rules.md` 第 3 节。
> 执行：integrate / integrator（task t13，attempt 2），时间 2026-11-17。
> 本文件是**已填写的实例**，后续步骤（C1–C5）请复制模板另建 `step-<id>-gate.md`，不要在此追加。

## A. 开工前（Before）

- [x] **A1 已读本步任务契约与依赖结果，确认 in-scope 路径**
  → in-scope：`claims/`、`data/`、`traces-claims/`、`docs/log/`、`.gitignore`。依赖结果：无（C0 是首步）。
- [x] **A2 已读保护对象清单**
  → `docs/log/step-c0-baseline.md` §4：`server/`、`tests/`、`mcp_servers/test_*.py`、`SPEC.md`、`wiki/`、`traces/`、既有 `eval/cases/`。
- [x] **A3 外部检索 ≥3 独立来源并登记（URL + 时间 + 用途）**
  → 实际 5 条：git-scm.com/docs/gitignore / docs.github.com（大文件上限）/ OWASP Logging Cheat Sheet / trunkbaseddevelopment.com/monorepos / abseil.io SWE-book Ch16。登记表见 `step-c0-baseline.md` §8。
- [x] **A4 已检查既有实现，避免重复造轮子 / 契约冲突**
  → 关键发现：`server/config.py` 已支持 `TRACE_DIR` / `WIKI_DIR` 环境变量（`:42` / `:44`），**隔离无需改 server 代码**；既有 `wiki/` 结构与 `mcp_servers/` 模式可复用（只读）。
- [x] **A5 已明确本步不改哪些文件**
  → 见 A2；另 `pyproject.toml`（`[tool.mypy] files`、`[tool.pytest.ini_options] testpaths`）本步**不动**，避免改变基线口径。
- [x] **A6 无来源支撑的结论已标「待验证」或降级为待办**
  → 理赔节点命名（`CLAIM_STAGES`）与工具名（`verify_policy` / `assess_damage` / `settle_payment`）均标注「占位、C4 定稿」，未当作契约。

## B. 实施中（During）

- [x] **B1 只在 in-scope 路径内新增/修改**
  → `git status --porcelain -uall` 仅：`M .gitignore` + 17 个新增文件（claims/ 6、data/ 7、docs/log/ 2、traces-claims/ 2）。
- [x] **B2 工程门禁通过**
  → `ruff check .` = `All checks passed!`（含 `claims/graph.py`）；`mypy` = `Success: no issues found in 7 source files`（claims 未入白名单，故数字不变）。
- [x] **B3 运行态落盘路径已确认隔离**
  → 实测注入后 `config.TRACE_DIR` 结尾为 `traces-claims`、`config.WIKI_DIR` 结尾为 `data/llm-wiki-claims/wiki`；`traces/` 文件数注入前后均为 **1183**（零写入）。
- [x] **B4 未打印/落盘密钥或真实 PII**
  → 本步未读取 `.env`、未创建任何含个人信息的样例数据；所有占位文件为纯文档 + `.gitkeep`。
- [x] **B5 外部结论只写指引，不复制原文**
  → README 与基线文档均写 URL + 「依据见 docs/log/step-c0-baseline.md 第 8 节 Sx」，未粘贴外部大段正文。

## C. 收工前（After）

- [x] **C1 四件套文档已写**
  → 基线：`docs/log/step-c0-baseline.md`（做了什么 / 决策依据 / 验证原文 / 限制）；硬规则：`docs/log/hard-rules.md`；各目录 README 说明职责与硬约束。
- [x] **C2 验证证据为命令 + 真实输出原文**
  → 见 `step-c0-baseline.md` §2（四条命令原文粘贴），本文件 C3–C7 亦为真实输出。
- [x] **C3 `.venv/bin/python -m pytest` = `148 passed, 2 skipped`**
  → 实跑：`148 passed, 2 skipped in 1.72s`（exit 0）。
- [x] **C4 `.venv/bin/python -m ruff check .` = `All checks passed!`**
- [x] **C5 `.venv/bin/python -m mypy` = `Success: no issues found in 7 source files`**
- [x] **C6 `shasum -a 256 SPEC.md` = `e3c74c6e...`**
  → 实跑一致：`e3c74c6e22397f23d5fe0a22978579b9a9b342fc43263c22bffc9fc57f831d8e`。
- [x] **C7 `git diff 40541d1 --stat -- server tests mcp_servers wiki SPEC.md` 为空**
  → 实跑：无输出。
- [x] **C8 `git status` 只含本步预期**
  → `M .gitignore` + `claims/`、`data/`、`docs/log/`、`traces-claims/` 四个未跟踪目录；无其它改动。
- [x] **C9 遗留问题已登记**
  → `step-c0-baseline.md` §9（traces 计数不作判定线、单环境快照、gitignore 范围外风险）；另有：`claims/tests` 未并入默认 pytest 收集（须 C4/C5 决策）、`claims/` 暂无 `__init__.py`（依赖命名空间包）。
- [x] **C10 已向 captain 汇报（含 source_task_id / source_attempt_id）**
  → task t13 / attempt 2 的 update + send_message。

## 结论

C0 通过。四条基线命令与 SPEC 指纹均与 `step-c0-baseline.md` 一致；骨架为纯占位、无业务代码；隔离靠既有环境变量实现，未改动续保域任何文件。
