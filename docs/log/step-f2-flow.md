# step-f2-flow.md —— 指针（canonical 在 step-f2.md）

> 任务卡 t10 指定日志名 `docs/log/step-f2-flow.md`；队长 2026-11-18 指示为 `docs/log/step-f2.md`。
> **完整日志只维护一份：`docs/log/step-f2.md`**（避免两份内容漂移）。本文件仅作路径指针。

- 完整日志（MCP 检索记录 / 改动清单 / 决策与被否决方案 / 命令与真实输出 / 8 条要求逐条落地 / 遗留）：**`docs/log/step-f2.md`**
- 实现：`claims/graph.py`、`claims/config.py`、`claims/state.py`、`claims/tools/**`
- 测试：`claims/tests/`（30 passed；显式 `pytest claims/tests` 运行，不并入默认收集）
- 契约：`claims/SPEC-claims.md` v1.0.0（F2 追加 §6.3 event 清单、§8.1 配置项）
- 结构：`claims/ARCHITECTURE.md`
