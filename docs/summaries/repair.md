# 修复验证Agent总结（repair.md）

日期：2026-11-12 · SPEC v1.0.1 · 验证环境：LLM 模式（.env 已配 GLM 凭证，测试服务独立端口 8301）

## 一、做了什么（含补修部分）

本 Agent 不改业务逻辑，只做三件事：**核对落盘改动自洽 → 真实回归验证 → 补录本总结**。

1. **通读并确认 4 处修复自洽**（逐行核对，无需补修）：
   - `server/llm.py`：新增 `normalize_tool_json()`（L169-186）+ `_NULL_SENTINELS = {"null","none","nil",""}`（L166），并在工具 JSON 出口 `chat_tool_json` 的解析链路统一调用（L114）——字符串哨兵 strip 后小写判定，递归处理 dict/list，深度上限 12 防御异常嵌套，非哨兵字符串原样保留。
   - `server/graph.py`：AC-08 修复落在 `intake` 路由（L449-456）——停售关键词（`DISCONTINUED_KEYWORDS`，L37）优先判为 `renewal` 意图，交给 `parse_needs._detect_corrections`（L356-368）产出 `COVERAGE_DISCONTINUED` 纠正码；纯条款问答（无续保/停售信号）仍走 `terms`。
   - `mcp_servers/quote_server.py`：AC-12 修复为「序号文件 + 登记簿双源续号」——`_init_quote_seq()`（L84-107）启动时从 `traces/quote_seq.json` 与 `traces/quotes.json`（含 orders 内 quote_id）取各日期最大序号；`_next_quote_id()`（L122-133）持锁自增、进程内撞号防御、`_persist_quote_seq()`（L111-118）临时文件 + replace 原子写回；调用点 L417。
   - `SPEC.md` 升 **v1.0.1**（L361 变更记录）：①AC-10 书面裁决（网约车一律不报价、转人工、引 wiki-ride-hailing，1.6 系数仅留 rates 数据层）；②补录 BLPS 费率（`synthetic/rates.json` L39-42：base_premium=400.0）；③quote_id 序号持久化登记。`eval/cases/AC-10.json` 已按裁决口径重写（询价 0 次 + 无 quote/await_confirm 事件 + 引 wiki-ride-hailing），`AC-03.json` 断言不变（BLPS 费率补齐后 OWN-1002 可正常手算对账）。
2. **真实回归**（详见第三节）：MCP 54 项自测、demo_chat 三链路（LLM 模式）、"null" 归一化专项回归、AC-12 跨进程续号实测、AC-08 路由实测。
3. **修复代码行号与 review.md P0/P1 根因对照**（见第二节表）。

## 二、关键决策与依据

| review.md 根因 | 严重度 | 已修位置（文件:行） | 验证证据 |
|---|---|---|---|
| ①GLM tool-use 把可空字段序列化为字符串 `"null"` → `INVALID_USE_NATURE` 整轮无报价 | **P0** | `server/llm.py:166`（哨兵集）、`llm.py:169-186`（归一化函数）、`llm.py:114`（工具出口接线） | 专项回归 5 组断言全过 + LLM 模式 demo 三链路全程无 `INVALID_USE_NATURE` |
| ②停售关键词被 intake 误判 terms，绕过纠正 | **P1** | `server/graph.py:37`（关键词表）、`graph.py:449-456`（路由）、`graph.py:356-368`（纠正产出）、`graph.py:546`（接线） | 8301 实测「发动机进水损失险」→ intent=renewal → 节点链含 parse_needs，SSE 含 `COVERAGE_DISCONTINUED` |
| ③`_QUOTE_SEQ` 进程内计数器，重启撞号 | **P1** | `mcp_servers/quote_server.py:69/84-107`（双源恢复）、`:111-118`（原子持久化）、`:122-133`（自增+撞号防御）、`:417`（调用点） | 两个独立进程连续询价：`QT-20261112-0025` → `QT-20261112-0026`，`traces/quote_seq.json` 同步 24→26，无撞号 |

设计要点评价（核对结论，非本 Agent 决策）：归一化放在 `chat_tool_json` 出口而非 graph 各节点，单点覆盖所有工具字段，是正确取舍；序号双源（文件 + 登记簿兜底）保证即便 seq 文件被删也不回退重号；`_persist_quote_seq` 失败静默不阻断报价，可接受（仍有兜底）。

## 三、验证证据（命令 + 输出摘录，全部退出码 0）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `.venv/bin/python mcp_servers/test_quote_server.py` | **54 通过 / 0 失败**（exit 0）：脱敏/幂等/三档三者险/三业务错误/24h 过期/网约车 1.6 系数/NCD/stdio 冒烟 |
| 2 | `uvicorn server.app:app --port 8301`（独立端口，避开常驻 8000 旧规则进程） | `/health` → `{"llm_mode":"llm","graph":"langgraph","nodes":11}`（真实 LLM 模式） |
| 3 | `.venv/bin/python scripts/demo_chat.py http://127.0.0.1:8301` | **exit 0**：链路①比价→await_confirm（节点链 7 节完整、query_quote×2、DSX=200万）；链路②改保额 200→300万 重新询价、仅改预算询价 0 次复用同 quote_id；链路③条款问答 citation={wiki-annual-inspection, source, v2024.3}；四份轨迹 seq 连续、§5 字段齐全、record_type 合法 |
| 4 | "null" 归一化回归（`normalize_tool_json` 直调） | **5 组全过**：`"null"/"None"/""/" nil "`→None、`"家用车"` 与数字结构原样保留、`["null","三者险"]`→`[None,...]`；并确认 `chat_tool_json` 出口已接线（llm.py:114） |
| 5 | AC-12 跨进程：两个独立 Python 进程各询价一次 | `QT-20261112-0025` / `QT-20261112-0026`，`traces/quote_seq.json` → `{"20261112": 26}`，无撞号 |
| 6 | AC-08 路由：`POST /chat`「我想加一份发动机进水损失险」 | intent=renewal（非 terms），节点链 intake→get_policy→parse_needs→retrieve_terms，SSE 含 `COVERAGE_DISCONTINUED` |

## 四、遗留问题与交接

1. **复审未跑**：本 Agent 只做修复点验证；完整的 `eval/run.py` 14 条 AC 复审（LLM 模式 + `--diff` 对 report-20261112-105638 基线）应由评测Agent/主 Agent 统一跑一轮，预期 P0 修复后 AC-01/03/05/06/13 回绿、AC-08/12 转过；AC-10 按新口径用例应转 PASS。
2. **`scripts/e2e_smoke.sh` 未回归**（review.md 指出其在 LLM 模式曾被 'null' 击穿且无 quote 时 IndexError 崩溃）：P0 已修主因，但脚本自身的 IndexError 优雅报错未修，建议下轮补。
3. **多进程并发写序号文件的窄窗口竞态**：`_SEQ_LOCK` 仅进程内生效，两个进程同时自增可能写同名 seq 文件后互相覆盖（登记簿兜底可缓解但非绝对）；单机演示场景可接受，如需严格全局唯一建议文件锁（fcntl）。
4. **quote 存储仍进程内**（`_QUOTES`）：跨进程 `/confirm` 查不到他进程报价返回 QUOTE_NOT_FOUND，SPEC 未要求持久化，维持现状。
5. 测试服务 8301 已在验证后关闭；常驻 8000 旧规则模式进程未动（按备忘 #4）。
