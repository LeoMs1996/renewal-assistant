# 文档Agent小结（documentation）

> 阶段：交付文档 · 2026-11-12 · 产出：docs/设计方案.md、README.md、docs/演示记录.md

## 一、做了什么

1. 通读 SPEC.md v1.0.0 全文 + docs/summaries/ 全部 7 份阶段小结 + eval/report*.md（规则基线 100847、LLM 104904，并本轮新跑 105725），交叉核对后撰写三份交付文档（**只引用不重写**）：
   - **docs/设计方案.md**：业务流程图；SPEC 契约条目逐框对应到代码文件的映射表；7 条关键设计问答（需求变化失效面 / 重启恢复 / 旧报价不可确认 / 超范围转人工 / 上下文常驻集与压缩 / 改口撤回 / 兜底退出与 3 条 SPEC 旁路），每条注明轨迹佐证字段；评测判定器构成；14 场景双模式结果引用。
   - **README.md**：环境（含精确依赖版本）、安装、GLM 配置（cp .env.example → 填三变量）、启动、四组测试命令、三个测试身份（含 OWN-1002 的 BLPS/RATE_NOT_FOUND 提示）、任务恢复方式、目录速览。
   - **docs/演示记录.md**：5 分钟演示脚本（启动→比价选方案→改保额复用/重报价对比→重启继续→确认，附 curl 无浏览器序列），全部链路指向 e2e_smoke.sh 可复现。
2. **真实运行了全部四组验证命令**取证后才写入文档（见三）。

## 二、关键决策与依据

- **AC-10 采用双口径如实记录**：设计问答按备忘 #3"转人工+引 wiki-ride-hailing"口径描述行为，同时明确标注 SPEC §7 原文（1.6 系数入报价）与任务书的冲突及裁决权归属——eval 用例按 SPEC 断言的 FAIL 不遮掩。
- **LLM 模式已知缺陷必须写进 README/演示记录**：10:22 配入 `.env` 后服务转 LLM 模式，`use_nature='null'` 缺陷（eval.md 遗留 #1）会击穿报价链路。文档如实给出规避方法（临时移开 .env 走规则模式），而非假装全绿。
- **所有版本号来自实测 `pip list`**（langgraph 1.2.20 / mcp 2.3.0 等），不凭记忆；MCP 2.x `MCPServer` 更名等 Context7 要点直接引用 mcp-quote-server.md，本轮无新框架用法、未新增查询。
- 数字全部对账小结原文：DSX 200万=1520×0.85=1292、300万=1780×0.85=1513、订单 ORD-20261112-1266 等，未自造任何数字。

## 三、验证证据

| 命令 | 结果 |
|---|---|
| `.venv/bin/python mcp_servers/test_quote_server.py` | exit 0，"54 通过 / 0 失败" |
| `.venv/bin/python scripts/demo_chat.py` | exit 0，"✅ 全部链路通过（三链路 + 轨迹完整性）" |
| `./scripts/e2e_smoke.sh 8124`（.env 在位，LLM 模式） | **exit 1**——复现 eval.md 遗留 #1：quote 节点 INVALID_USE_NATURE → fallback（根因同 eval/report 104904，非文档改动引入） |
| `mv .env /tmp && ./scripts/e2e_smoke.sh 8124 && mv 回` | **exit 0**，"✅ E2E smoke 全部通过（AC 链路 + 重启恢复 + 确认幂等）"；.env 已恢复（342 字节，权限 600） |
| `.venv/bin/python eval/run.py` | exit 0，"6/14 PASS，hard 失败 8 条"（llm_mode=llm），新报告 report-20261112-105725.md |
| 引用路径交叉核对 | 设计方案/README/演示记录引用的 20 个文件路径全部存在（OK=20/20） |

## 四、遗留问题与交接

1. **README §3 与演示记录的"规则模式规避"提示是临时的**：`use_nature='null'` 修复（llm.py/graph.py 归一化）后应删除该提示并重跑 eval 确认 AC-01/03/05/06/13 回绿。
2. eval/run.py 本轮新增 report-20261112-105725.md（LLM 6/14，与 104904 一致，无回归）；report.md 已同步为最新一份。
3. 常驻 8000 服务本轮未被触碰（仍为规则模式进程）；文档假设其继续可用，若重启用 LLM 凭证启动则演示需按 README §3 提示操作。
4. 设计方案 Q7 的 3 条旁路未入 SPEC（沿 orchestration.md 遗留 #3），如后续升 SPEC 版本需同步更新设计方案 §2 表与 Q7。
