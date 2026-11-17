# 评测Agent总结（eval）

> 阶段：14 条验收场景一键评测 · 2026-11-12 · 10:04–10:55 · 服务自管于 127.0.0.1:8123

## 一、做了什么

1. **校验前任用例**：逐个读取 `eval/cases/AC-01~AC-14.json`，格式齐整（step: chat/api/expired_quote/requote + 22 种断言类型），未改动任何用例内容。
2. **实现 `eval/run.py` 一键 runner**（约 700 行，纯标准库 + httpx）：
   - 自管 uvicorn（默认端口 8123，复用 e2e_smoke.sh 模式：子进程 + /health 探活 + finally 清理），不碰常驻 8000 演示服务；
   - 断言只读三类确定性证据：SSE 事件结构（不读对话文字）、traces/ 轨迹 JSONL、API 响应 + traces/quotes.json；
   - 确定性断言全部落地：询价次数（复用轮=0 可证）、quote_id 幂等、quote_version、premium_total 与 rates.json **独立手算**（§2.3 公式：JQX 固定、CSX=保额/万×1.42×NCD×用途×车龄、DSX tiers×NCD×用途、SJRX/CKRX 按座均、车龄系数按 first_registration_date 现算）、id_number/phone 缺席 + 全链路 PII 字面值扫描（hard）、六种错误码、order 唯一（登记簿计数=1）、轨迹 seq 连续 + 回放一致；越权/编造/保费编造类断言标 hard；
   - **AC-12 过期场景不污染共享状态**：runner 在**独立子进程**直调 mcp_bridge.query_quote（真实报价服务；子进程隔离是刻意的——报价服务 24h 幂等窗口是进程内状态，同进程无法模拟"隔天"），把报价以 created_at/valid_until 前移 25h 的**副本**写入 quotes.json（仅新增/本运行条目）；结束后把评测前快照中被改动的既有条目**恢复原值**（新增条目保留）；
   - 报告：`eval/report-<stamp>.md` + 同步 `eval/report.md`，每条 PASS/FAIL + 逐断言证据行 + FAIL 根因分析；`--diff` 与上一份 report-*.md 对比输出新增失败/已修复；runner 退出码恒 0（FAIL 是评测发现非运行故障）。
3. **跑了一轮真实评测并归因**：规则模式基线 8/14 PASS（report-20261112-100847）；10:22 起 `.env` 配入 GLM 凭证后服务转 LLM 模式，终轮 **6/14 PASS**（report-20261112-104904，8 FAIL 中 6 条 hard）。

## 二、关键决策与依据

- **LLM 模式主缺陷（本轮最重要发现）**：GLM tool-use 结构化输出把 `use_nature_change` 序列化为**字符串 `"null"`**（llm_response 轨迹可证），`graph.py` 未归一化直传 `query_quote` → `INVALID_USE_NATURE` → **整轮无报价**（AC-01/03/05/06/13 全部被此击穿）。修复点：llm.py chat_tool_json 或 parse_needs 把 `'null'/'None'` 归一化为 None。规则模式（无 .env）下这些链路 8/14 通过，缺陷是 10:22 引入 LLM 后才暴露——正是 e2e/demo 只在规则模式跑过留下的盲区。
- **quote_id 跨进程不唯一（AC-12 发现）**：`quote_server.py` 的 `_QUOTE_SEQ` 是进程内计数器，重启/新进程从 `QT-YYYYMMDD-0001` 重新起号，`quote_book.register` 按 quote_id 覆盖写 → 重新报价撞已有 ID。过期逻辑本身正确（409 QUOTE_EXPIRED / 新报价 confirm 200 均过）。
- **Context7**：本轮为评测工程（httpx SSE 解析 / argparse / json），无新框架 API，沿用 server.md 已查证结论，未新增查询。
- 报告 header 记录 `/health.llm_mode`，保证 FAIL 归因不跨模式错位（规则 vs LLM 根因不同，两份报告都保留供 diff）。

## 三、验证证据

- `.venv/bin/python eval/run.py --diff` → 退出码 **0**（连跑 3 次：100847 规则模式 8/14、103916 与 104904 LLM 模式 6/14，结果稳定、--diff 输出"新增失败：无"）。
- 关键输出摘录：
  - `=== 评测完成：6/14 PASS，hard 失败 8 条 ===`、`（已恢复评测前 quotes.json 既有条目）`
  - AC-02/04/07/09/11/13(规则模式) 全绿：`无 PII 泄漏`、`OWN-9999 → 404 found=false`、`RIDER_PREREQUISITE_MISSING 纠正`、`幂等=一致`、`seq 连续/回放一致`
  - LLM 模式击穿证据：`quote 节点 error INVALID_USE_NATURE（使用性质「null」不在费率表）`
  - 手算证据：`逐行×2张报价与 rates.json 手算一致（如总额 2190.22 = 手算 2190.22，车龄系数 1.05）`

## 四、遗留问题与交接（按优先级）

1. **🔴 use_nature='null' 字符串缺陷（llm.py/graph.py）**：修复后重跑 `eval/run.py`，预期 AC-01/03/05/06/13 大幅回绿；AC-03 修复后将暴露第二层 BLPS 无费率（RATE_NOT_FOUND，需先升 SPEC 补 rates.json）。
2. **🟡 quote_id 进程内计数器**：建议 quote_book.register 时检测 ID 已存在则拒绝/换号（或计数器读登记簿初始化），否则重启后覆盖旧报价。
3. **🟡 AC-08**：intake 把停售关键词判为 terms 意图绕过 corrections（graph.py:451），纠正码 COVERAGE_DISCONTINUED 永远不产生；修法：停售关键词优先走 renewal→parse_needs。
4. **🟡 AC-06 规则模式**：保额正则取首个数字，"从100万升到200万"解析为 100万（graph.py:297）。
5. **AC-10**：任务书 vs SPEC §7 冲突（转人工 vs 1.6 系数入报价），用例按 SPEC 断言如实 FAIL，裁决权在主 Agent。
6. 常驻 8000 服务仍为规则模式进程（/health.llm_mode=rule），如需 LLM 模式演示请重启该服务。
