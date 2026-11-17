# 文档同步Agent总结（doc-sync）

日期：2026-11-12 · SPEC v1.0.2 · 只改文档，未触碰任何代码/数据/评测文件

## 一、做了什么

1. **README.md**：删除 §3「规则模式规避」临时提示（`use_nature='null'` 缺陷已由 v1.0.1 修复），改为修复说明 + 指向剩余规则模式 AC-06 独立缺陷的备注；§5 实测口径更新为 LLM 模式全过；§6 OWN-1002 行补 BLPS 费率已补录（v1.0.1，base_premium=400.0，不再 `RATE_NOT_FOUND`）；新增 **§9 SPEC v1.0.1/v1.0.2 版本变更说明表**；头部与目录速览的 SPEC 版本号升为 v1.0.2。
2. **docs/设计方案.md**：头部版本升 v1.1.0（对应 SPEC v1.0.2）；Q4 AC-10 由「⚠️ 裁决说明（冲突待裁）」改写为「✅ 裁决已定（SPEC v1.0.1）」，统一为"不报价+转人工+引 wiki-ride-hailing"口径，并注明 AC-10 用例已重写、全量评测 PASS；§5 评测结果表更新为完整演进链（8/14 → 6/14 → 13/14 → 终修靶向 2/2 → 182425 遗留留档），FAIL 根因清单逐条标注修复去向；新增 **§5.5 三轮评审演进**（引用 review.md / repair.md / final-repair.md）；端到端证据补 LLM 模式复验。
3. **docs/演示记录.md**：删除「mv .env 规避」准备步骤，改为推荐 LLM 模式（含规则模式双数字表述陷阱提示）；/health 示例输出更新为 `llm_mode=llm`（附 rule 降级说明）；AC-10 表述统一为「SPEC v1.0.1 裁决口径」；§5 实测结论更新为本轮复验数字。

## 二、决策与依据

- **最新结果口径**：以最新全量 LLM 报告 report-20261112-134930/135004（13/14，hard 0）为终态主数字；181630（v1.0.2 靶向 2/2）与 182425（当前 report.md，规则模式 AC-06 缺陷留档）按时间线如实并列，不把靶向 2/2 夸大为"全量 14/14"。依据：repair.md/final-repair.md 的报告索引与 final-repair.md 遗留 #1。
- **AC-10 表述**：完全遵循 SPEC v1.0.1 书面裁决（repair.md 一手记录），三份文档口径统一，消除旧"任务书 vs SPEC 冲突"的过时表述。
- **README §3 不留死角**：缺陷删除的同时，把仍存在的规则模式 AC-06 正则缺陷挪到 §5 备注 + 演示记录准备段，避免"读起来零缺陷"的误导。

## 三、验证证据（全部真实运行，退出码 0；独立端口 8403/8404，未动常驻 8000）

| 命令 | 结果 |
|---|---|
| `.venv/bin/python mcp_servers/test_quote_server.py` | exit 0，54 通过 / 0 失败 |
| `uvicorn server.app:app --port 8403`（/health） | `{"llm_mode":"llm","graph":"langgraph","nodes":11,"wiki_entries":8}` |
| `.venv/bin/python scripts/demo_chat.py http://127.0.0.1:8403` | exit 0，三链路 + 轨迹完整性全过（LLM 模式） |
| `./scripts/e2e_smoke.sh 8404` | exit 0，AC 链路 + 重启恢复 + 确认幂等全过（LLM 模式） |
| 引用路径交叉核对（三份文档提取文件名 → 全库解析） | 除正文简写片段（`105638.md`、`AC-01~AC-14.json`）外全部存在 |

测试服务 8403 已于验证后关闭；8404 为 e2e_smoke 自管进程，随脚本 finally 清理。

## 四、遗留问题与交接

1. **规则模式 AC-06 保额正则取首数字**（graph.py parse_needs 附近）：唯一遗留缺陷，已在 README §5、设计方案 §5、演示记录准备段三处如实标注（LLM 模式不受影响）；修复属代码层小改，无需升 SPEC，修后建议重跑 `eval/run.py --diff` 并同步删除三处标注。
2. **report.md 当前内容为 182425 靶向报告**（2 条用例）：如需"最新全量"作为 report.md 门面，可重跑一轮全量 eval 覆盖之（本轮文档已按时间线引用多份报告，不依赖此动作）。
3. `scripts/e2e_smoke.sh` 的"无 quote 时不崩溃"防御（review.md P0-2 后半）仍未修，本轮 LLM 模式下全过未触发；留待代码层任务。
