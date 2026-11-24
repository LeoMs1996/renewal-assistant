# PR：作业 5 收口 — 验收验证手册 + 架构 Harness 设计 + 实现过程复盘补全（仅文档 + SPEC 登记，不改代码）

## 概要

本 PR 完成作业 5 的四项交付，**不改任何运行代码、不升 SPEC 版本**：

| # | 交付物 | 位置 | 规模 |
|---|---|---|---|
| T1 | 验收验证手册 | `docs/验收验证/验收验证手册.md`（+ `screenshots/` 28 张、`_batch/` 原始记录） | 22 条记录，364 行，FAIL 0 / PARTIAL 1 |
| T2 | 架构与 Harness 设计（单文件 HTML，0 外链） | `docs/架构与Harness设计.html` | 8 节，528 行，119 个「待核」标记保留 |
| T3 | 实现过程复盘 CH2–CH9 补全 | `docs/实现过程复盘.md`（+ `_复盘_parts/` 分章源文件与 `assemble.py`） | 9 章齐全，305 行，占位符 0 |
| T4 | 收口 | `SPEC.md §8` 追加「v1.0.6（不升版）」登记行；本 PR 正文 | — |

打包（`deliverables/` 下按交付物分四个包，中文文件名 UTF-8 标志已校验，解压后相对路径成立）：`T1-验收验证手册.zip`（11.7 MB：手册 + 28 张截图 + 原始记录）· `T2-架构与Harness设计.zip`（HTML + 三份 grep 证据表）· `T3-实现过程复盘.zip`（复盘 + 分章源文件与汇编脚本）· `T4-收口-SPEC与PR.zip`（SPEC.md + PR 正文 + eval 报告）。

## 验证证据（2026-11-24，均带时间戳）

- 全量 eval：**19/19 PASS，hard 失败 0，35.4s** → `eval/report-20261124-180712.md`
- `pytest tests/`：148 passed, 2 skipped；`pytest claims/tests/`：86 passed
- 理赔门禁 `demo_claim`：8 项 PASS 8 / FAIL 0；理赔 wiki lint：36 页 FAIL 0
- 浏览器实证：SEC-01/02 注入拒绝（`get_policy.owner_id=['OWN-1001']`，注入标记 high）；SEC-05 四种路径穿越均 400
- 重启后继续：`no_progress_rounds` 跨重启 0→1→2→3，会话 chip 不变；11 轮长会话 `needs_version` 1→8、改口写入 `invalidated`
- 架构 HTML：控制台 0 错误 / 0 警告，导航高亮正确，外链 0

## 本次登记的发现（详见手册 §3 与复盘 §6）

1. **缺陷 · AC-11 回复事实错误**：条款路径未取 `use_nature`，回答误称用户「网约车」而保单为「家庭自用（非营运）」；现有 5 条断言未覆盖 → eval 仍 PASS。建议 AC-11 增加一致性断言。
2. **观察 · 报价有效性双真源**：`/confirm` 读 `traces/quotes.json`，询价幂等由 MCP 报价子进程内存态判定；评测器 `requote` 另起进程，测不到常驻路径。真实隔天无影响，建议登记为已知张力（与 X-03 同族）。
3. **观察 · 理赔 `analysis_degraded=true`**：`/health` 报 `deepagents=true` 但两案均降级为规则回退 → Deep Agents 真实分析路径本轮**未验证**。
4. UI 重复「待确认」卡（旧卡按钮不置灰）；`/docs` 在 CSP 下空白；`docs/log/INDEX.md:11` 的 `demo_claim` 示例须改为 `python -m claims.demo_claim`。
5. 未验证：上下文压缩 / 摘要路径（11 轮 `tokens_in` ≤ 2.7k 未触发）、真实凭证长会话、机器级重启。

## 不在本 PR 范围（Non-goals）

- 不修上述缺陷（作业要求「验证 + 收口」，修复需先改 SPEC 并升版）
- 不重建 llm 模式的回归基线（当前基线为 rule 模式，工具判「不可比」，b=c=0）
- 不提交 / 不暂存任何文件（遵守「不 `git add` / `commit`」约束）

## 风险与回滚

- 仅文档 + `SPEC.md` 一行**非规范性**登记；回滚 = revert 本 PR，无运行时影响。

## 审阅清单

- [ ] 手册 §3 发现清单是否与复盘 §6 #13–#15 一致
- [ ] 架构 HTML §5/§6/§7.1 的每个 `file:line` 能在 `docs/_架构_parts/evidence-*.md` 找到出处
- [ ] 复盘 §2 时间线已注明「git 仅 2 个 commit，日期来自文档」
- [ ] 截图 01–26 均为 1440×900 视口（22 为整页），无 PII 原文
