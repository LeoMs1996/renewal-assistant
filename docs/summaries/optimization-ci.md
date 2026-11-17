# 工程质量 / CI 域：评估 → 优化 → 验证总结

> 检索时间：2026-11-13（Asia/Shanghai）｜子 Agent：CI 工程化｜状态：已落地，本地全绿

## 1. 基准

| 基准 | 结论要点 | 来源 |
|---|---|---|
| Ruff Linter | 单工具覆盖 pycodestyle/pyflakes/import 排序/pyupgrade 等规则集，`select` 可按需裁剪，`per-file-ignores` 处理脚本式文件 | [The Ruff Linter · docs.astral.sh](https://docs.astral.sh/ruff/linter/) |
| GitHub Actions workflow 语法 | job 之间用 `needs` 表达依赖、`if: always()` 做汇总闸门、`upload-artifact` 留存报告 | [Workflow syntax for GitHub Actions（官方文档镜像）](https://github.com/hexrayssa/rax/blob/29a85cccd0c65484b3c02b4a87334efab7c9c6ca/docs/development/capi-releases/references/github-workflow-syntax.md)（官方 docs.github.com 原文本轮未直接抓取 → **待验证**，仅作语法参考） |

## 2. 优化前的差距

| 差距 | 影响 |
|---|---|
| **零 CI**：没有 `.github/`，一切靠本地手动跑 | 回归不可见，评审只能人工点 |
| 依赖未锁定：`requirements.txt` 是 7 行裸包名 | 构建不可重现，"我这儿能跑"无法证伪 |
| `python -m pytest tests/` 直接 `INTERNALERROR` | 两个脚本式测试在模块顶层 `sys.exit()`，pytest 导入即崩，等于**测试入口不可用** |
| 无 lint / 无类型检查 | 未使用变量、未定义名这类问题只能靠运行才暴露（本轮已实际踩到：`a_retrieval_hit`、`stamp`、`path` 三处 NameError） |
| eval 无机器门禁 | 报告全绿与否靠人看 |

## 3. 已实施改动

1. **`pyproject.toml`（新增）**：`[project]` 版本 v1.0.4；`[tool.ruff]` 规则集 `E,F,I,B,UP`（忽略 E501/B008/UP031 并注明理由）；`[tool.pytest.ini_options]`；`[tool.mypy]` **渐进式**仅覆盖 4 个纯逻辑模块（避免一次性被 LangGraph 动态 State 淹没）。
2. **依赖三层**：
   - `requirements.txt`：改区间约束（原先无版本）；
   - `requirements.lock.txt`（新增）：13 个关键运行时依赖精确锁定；
   - `requirements-dev.txt`（新增）：pytest / ruff / mypy。
3. **修好 pytest 入口**：`tests/conftest.py`、`mcp_servers/conftest.py` 用 `collect_ignore` 排除脚本式测试（保留 `python <file>` 直接运行的双入口），pytest 从 `INTERNALERROR` 变为正常收集。
4. **`.github/workflows/ci.yml`（新增）**：四道闸门
   ```
   lint  ：ruff check . + ruff format --check（不阻断）+ mypy
   test  ：pytest tests/ mcp_servers/ + 两个脚本式测试
   eval  ：python eval/run.py（规则模式）+ MCP stdio 专项 + 报告 grep 门禁 + artifact
   gate  ：needs 汇总，任一失败即失败（供分支保护勾选）
   ```
   全程 `RENEWAL_FORCE_RULE_MODE=1`，不依赖 LLM 凭证。
5. **修掉 lint 实际发现的问题**：`base_by_code` 未使用变量（删除）、两处 `zip()` 补 `strict=False`、35 处自动修复（import 排序、`Optional` → `|` 等）。

## 4. 验证证据（本地实跑，等价于 CI 各步）

```
ruff check .                → All checks passed!
mypy                        → Success: no issues found in 4 source files
pytest tests/ mcp_servers/  → 18 passed
python tests/test_llm_normalization.py       → 15 通过 / 0 失败
python mcp_servers/test_quote_server.py      → 54 通过 / 0 失败
MCP_TRANSPORT=stdio python mcp_servers/...   → 54 通过 / 0 失败
RENEWAL_FORCE_RULE_MODE=1 python eval/run.py → 19/19 PASS
```

## 5. 遗留项

| 项 | 说明 | 建议 |
|---|---|---|
| CI 尚未在 GitHub 真跑过 | 工作区不是 git 仓库，无法 push 验证 | 首次 push 后确认四道闸门全绿；必要时按实际失败调 `per-file-ignores` |
| mypy 覆盖面小 | 只 4 个文件，`graph.py`/`app.py` 未纳入 | 逐季扩面，先把 `trace.py`→`quote_book`→`sessions` 全绿，再啃 graph 的 TypedDict |
| `ruff format` 不阻断 | 一次性 format 会改动大量文件，暂只提示 | 单独一个 PR 做全量 format，之后改为阻断 |
| 无覆盖率门槛 | 未装 coverage | 加 `pytest --cov`，先设"不低于当前"的棘轮（ratchet） |
| 无依赖漏洞扫描 | 未接 Dependabot / pip-audit | 开 Dependabot + 每周 `pip-audit` |
