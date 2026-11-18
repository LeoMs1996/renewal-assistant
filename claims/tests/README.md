# claims/tests/ —— 理赔域测试 · 占位

> 状态：**C0 占位，无测试**。建立于 2026-11-17。

## 重要：本目录当前**不被** `pytest` 默认收集

`pyproject.toml` 里：

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "mcp_servers"]
```

因此 `.venv/bin/python -m pytest` 的基线数字（`148 passed, 2 skipped`）**不会**因本目录新增而变化。

**这是刻意的隔离**：C0 不能改动基线口径。若后续要把理赔测试并入默认收集，必须：

1. 由 C4/C5 明确决策；
2. 修改 `testpaths` 后**同步更新** `docs/log/step-c0-baseline.md` 的期望数字（在其末尾追加「复核补记」，**不得就地改原文**）；
3. 在报告中写明新基线与旧基线的差异原因。

## 单独运行（推荐，先这样跑）

```bash
cd renewal-assistant
.venv/bin/python -m pytest claims/tests -q
```

> 目前本目录为空，该命令会以 **exit 5 / no tests collected** 结束——这是占位期的正常现象，不是失败（有测试文件后才会真正收集）。

## 测试约定

- 合成数据：所有报案人、证件、票据、金额一律虚构，并在用例里注明「模拟/合成」。
- 确定性优先：状态机迁移、金额计算、权限拒绝必须有纯函数单测，不依赖 LLM。
- 对抗用例不可省：越权读取、编造金额、注入指令（材料里藏 prompt）→ 必须有用例证明被拒绝。
- 不写 `traces/`、`wiki/`：测试如需落盘，用 `tmp_path` 或 `TRACE_DIR=traces-claims`。

## 当前内容

无。此文件仅为目录占位与测试纪律声明。
