# 回归评测（regression-eval）总结

> 回归评测Agent · 2026-11-12 18:26–18:32 · LLM 模式全量回归

## 一、做了什么

1. **eval/run.py 全 14 条**（LLM 模式，自管 uvicorn 独立端口 8401，不碰常驻 8000）→ **14/14 PASS，hard 失败 0 条**，退出码 0。
2. 最新报告 `eval/report-20261112-182638.md` 已同步为 `eval/report.md`（runner 自动同步，diff -q 验证 SAME）。
3. **--diff 对比指定基线 `eval/report-20261112-135004.md`**（基线 13/14，唯一 FAIL = AC-05）：
   - 新增失败：**无**
   - 已修复：**AC-05**（险种结构差异表）
   - 注：run.py 内置 `--diff` 按 mtime 取最近基线，任务指定 135004，故用同款解析逻辑（`## AC-xx …— PASS|FAIL`）手动对比，结论一致。
4. **scripts/e2e_smoke.sh 8402** 全链路 → **全部通过，退出码 0**：phaseA（AC-01/02/04/05/06/11/14 链路 + 附加险 + citation）+ phaseB（重启恢复、轨迹回放、/confirm 错误码矩阵 422/409/404、确认幂等同一 `ORD-20261112-2210`、对话内确认 SSE `confirmed`）。

## 二、关键决策与依据

- **AC-05 由 FAIL → PASS 的归因**：基线报告指出两层根因——① LLM 模式 `use_nature_change="null"` 字符串直传 → `INVALID_USE_NATURE`（已在 `server/llm.py` normalize_tool_json 修复）；② 规则模式 `_build_selection` 含 JQX sum_insured 导致 selection_key 不等、同语义询价 2 次。本轮 LLM 模式 8/8 断言全过（含"复用轮询价 0 次"），第①层已证修复；第②层属规则模式路径，本轮未触发（服务以 LLM 模式跑），留待规则模式回归时确认。
- **端口纪律**：8401（eval）/8402（e2e），均先确认空闲；常驻 8000 旧进程未动。
- 硬规矩遵守：未读取/打印 .env 内容；报告仅引用 SSE 事件结构与轨迹 JSONL；报价均来自报价服务。

## 三、验证证据

| 命令 | 结果 |
|---|---|
| `.venv/bin/python eval/run.py --port 8401` | `14/14 PASS，hard 失败 0 条`，exit 0，llm_mode=llm |
| 手动 diff（135004 vs 182638，同 run.py 解析逻辑） | 基线 13/14；新增失败 无；已修复 AC-05 |
| `diff -q eval/report.md eval/report-20261112-182638.md` | SAME |
| `./scripts/e2e_smoke.sh 8402` | `✅ E2E smoke 全部通过`，exit 0（ORD-20261112-2210 幂等复现） |

## 四、遗留问题

- **规则模式路径未在本轮回归**（评测以 LLM 模式为目标）：AC-05 第②层根因（JQX sum_insured 进 selection_key 致同语义二次询价）在规则模式是否仍存在，建议跑一轮 `llm_mode=rule` 确认。
- `e2e_smoke.sh` 对"无 quote"场景的健壮性（IndexError）未在本轮触发路径内，历史遗留未修。
- `traces/quote_seq.json` 多进程并发写仍有窄窗口竞态（单机演示可接受）。
