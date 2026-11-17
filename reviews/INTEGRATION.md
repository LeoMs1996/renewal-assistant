# 集成回归报告（t10 · INTEGRATION）

- 执行人：mcp-reviewer-ds（t10，attempt 1 / `a35a1e1f-d152-4cfb-b9f9-a40dbfa5fefc`）
- 执行时间：2026-11-17 21:33–21:37（+08:00）
- 覆盖范围：t1–t9 九域优化落地后的全链路回归 + 真实 LLM 严格模式验证 + 跨域踩踏排查
- 产出边界：本文件是**回归报告**；`reviews/INDEX.md`（汇总索引）由 integrator-ds 在 t14 负责，本任务未写该文件（按队长派单避让）
- 硬约束遵守：本文所有结论均来自**本次实跑命令与输出**，未引用训练记忆；队长侧数字仅用于 §6 交叉核对

---

## 0. 一页结论

**22 项回归项中 21 项通过、1 项失败（mypy）。真实 LLM 严格模式 19/19 PASS 且零降级。九域优化之间未发现功能级互相踩踏，但存在 1 处真实的类型门禁碎片（t4 新增 `server/memory.py` 带入 14 个 mypy 错误，经 `sessions.py` 的 import 牵连触发）。**

| # | 门禁/回归项 | 命令 | 结果 |
|---|---|---|---|
| 1 | ruff（全仓 lint） | `.venv/bin/python -m ruff check .` | ✅ All checks passed!（exit 0） |
| 2 | **mypy（类型门禁）** | `.venv/bin/python -m mypy` | ❌ **14 errors in 1 file（server/memory.py）** |
| 3 | pytest（全量单测） | `.venv/bin/python -m pytest` | ✅ 140 passed, 2 skipped（exit 0） |
| 4 | 安全自检 | `.venv/bin/python scripts/security_check.py` | ✅ 12/12 通过（exit 0） |
| 5 | 平台自检 | `.venv/bin/python scripts/platform_check.py` | ✅ 4/4 段全部通过 |
| 6 | wiki lint | `.venv/bin/python scripts/wiki_tool.py lint` | ⚠️ 0 error / 7 warn（stale claim，业务待复核） |
| 7 | MCP stdio 全链路 | `MCP_TEST_STDIO=1 pytest tests/test_mcp.py` | ✅ 8 passed |
| 8 | MCP 工具自测 | `python mcp_servers/test_quote_server.py` | ✅ 54 通过 / 0 失败 |
| 9 | 编排三链路自测 | `python scripts/demo_chat.py`（规则模式，端口 8714） | ✅ 三链路 + 轨迹完整性全通过（exit 0） |
| 10 | 端到端冒烟 | `./scripts/e2e_smoke.sh 8715` | ✅ AC 链路 + 重启恢复 + 确认幂等全通过 |
| 11 | 记忆 A/B 评测 | `python eval/memory_eval.py` | ✅ before 0/5 → after 5/5 |
| 12 | 记忆报价中性 | `python eval/memory_quote_neutrality.py` | ✅ PASS（7 轮保费零变化） |
| 13 | 知识检索消融 | `python eval/knowledge_retrieval_eval.py` | ✅ Hit@1 0.88 / Hit@3 1.00 / MRR@5 0.938 / 接地率 0.90 / 拒答 1/1 |
| 14 | 评测（规则模式，抖动采样） | `RENEWAL_FORCE_RULE_MODE=1 eval/run.py --port 8716 --repeat 2` | ✅ 19/19 PASS，hard 0，3.9s，无显著退化（b=0/c=0/p=1） |
| 15 | **真实 LLM 严格模式** | `RENEWAL_LLM_STRICT=1 eval/run.py --port 8713 --baseline eval/baseline-llm.json --fail-on-degraded` | ✅ **19/19 PASS，hard 0，37.9s，零降级，无显著退化** |
| 16 | 残留进程清理 | `pgrep -fl "uvicorn server.app"` | ✅ 空（无残留） |
| 17 | 重复定义自检 | graph/app/sessions/llm/trace 的 `def` 计数 vs 去重计数 | ✅ 五文件均相等（51/6/7/11/6，无覆盖式重复定义） |
| 18 | 调试残留 | `grep FIXME|XXX|breakpoint()` | ✅ 无（唯一命中是 `QT-XXXX` 假阳性） |

> 说明：上表按实际执行顺序编号，#19–#22 为 §4 的踩踏排查四项结论项（同文件多域改动、语法/导入、跨域契约、轨迹污染），详见 §4。

**最需要队长决策的一条**：`mypy` 门禁当前是**红的**，且它正是 `ci.yml` lint 作业的一道门（`run: mypy`）。这不是"既有历史问题"——`server/memory.py` 由 t4（记忆域，16:07 落盘）新增，此前 t8 在 12:09 记录的 mypy 状态是 0 errors。回归结论：**CI 目前会挂在 lint 作业**。

---

## 1. 执行环境与端口纪律

| 项 | 值 |
|---|---|
| Python / 解释器 | 项目 `.venv`（Python 3.14，含 langgraph/mcp/fastapi 全套依赖）。系统 python 无 langgraph，**不能**用来跑本仓测试（t3 已踩过这个坑） |
| 本次占用端口 | 8713（LLM 评测）、8714（demo_chat 服务）、8715（e2e smoke）、8716（规则模式评测） |
| 避让端口 | 8711 / 8712 / 8731（队长侧已用）、8000（常驻实例，未触碰） |
| 限流 | 评测/批量回归统一 `RENEWAL_RATE_LIMIT_DISABLED=1`（按 t9 `deploy/README.md` §6.2 的放宽姿势），未出现 429 |
| 子进程清理 | eval/e2e 均自管子进程；收尾 `pgrep` 复核为空 |

---

## 2. 全链路回归证据（命令 + 输出摘要）

### 2.1 静态门禁

```
$ .venv/bin/python -m ruff check .
All checks passed!                                             # exit 0

$ .venv/bin/python -m mypy
server/memory.py:287: error: Argument 1 to "get" of "dict" has incompatible type "Any | None"; expected "str"  [arg-type]
server/memory.py:565: error: Need type annotation for "delta"  [var-annotated]
server/memory.py:571: error: Incompatible types in assignment (expression has type "int", target has type "list[Any] | None")  [assignment]
server/memory.py:571: error: Argument 1 to "int" has incompatible type "Any | None" ...  [arg-type]
server/memory.py:578: error: Item "None" of "list[Any] | None" has no attribute "append"  [union-attr]
server/memory.py:582: error: Incompatible types in assignment (expression has type "str", target has type "list[Any] | None")  [assignment]
server/memory.py:707: error: "add" of "set" does not return a value (it only ever returns None)  [func-returns-value]
server/memory.py:785/787/790/792/794: error: Unsupported operand types for + ("object" and "int")  [operator]
server/memory.py:797: error: "object" has no attribute "append"  [attr-defined]
Found 14 errors in 1 file (checked 6 source files)
```

**根因链**（本次实读确认，非推测）：
1. `pyproject.toml [tool.mypy] files` 只列了 6 个文件，`server/memory.py` **不在其中**；
2. 但 `server/sessions.py:101` 在 `save()` 内 `from . import memory as memory_mod`，而 `sessions.py` 在 files 列表内 → mypy 顺着 import 把 `memory.py` 拉进检查范围；
3. 于是 t4 新增文件的 14 处类型问题直接打红门禁。

这不是"t4 写错了功能"（其 16 条记忆测试、A/B 5/5、报价中性全绿），而是**跨域门禁覆盖关系**没对齐：t4 的落地范围里没有 `pyproject.toml`，t8 建 mypy 门禁时 memory.py 还不存在。

### 2.2 测试与自检

```
$ .venv/bin/python -m pytest
140 passed, 2 skipped in 1.64s                                  # exit 0

$ .venv/bin/python scripts/security_check.py
... 12/12 通过                                                   # exit 0
  [PASS] C.轨迹 PII（存量+新增）      1010 个轨迹文件零 PII 原文命中
  [PASS] D1.CSP 强制 Trusted Types   require-trusted-types-for 已下发
  [PASS] D3.入参超限 → 422 契约错误体  HTTP=422 code=INVALID_INPUT
  [PASS] D5.无凭证 401 + 安全头
  [PASS] E3.归属字段保留（BOLA 校验依赖 owner_id）

$ .venv/bin/python scripts/platform_check.py
[2/4] 规则引用的指标确实被暴露   ✓ 11 条规则表达式全部指向已暴露指标
[3/4] /metrics 暴露面           ✓ 12 个必备指标族齐全，无高基数标签
[4/4] 轨迹 → OTLP 转换          ✓ 1010 条轨迹 → 9358 spans（error span 104）

$ .venv/bin/python scripts/wiki_tool.py lint
WARN  annual-inspection.md / csx.md / deductible.md / dsx.md / jqx.md / ride-hailing.md / ywyw.md
      effective_date=2024-01-01 已 2.9 年，需复核是否被新条款替代（stale claim）
lint: 0 error / 7 warn / 8 条目
```

### 2.3 MCP 工具层（t2 契约未被后续域破坏）

```
$ MCP_TEST_STDIO=1 .venv/bin/python -m pytest tests/test_mcp.py
8 passed in 0.52s                                               # 含 stdio 全链路 initialize→tools/call

$ .venv/bin/python mcp_servers/test_quote_server.py
  ✓ 注册了 get_policy / query_quote 两个工具
  ✓ stdio 链路：initialize + tools/call get_policy 脱敏返回
结果：54 通过 / 0 失败
```

### 2.4 编排三链路（t1 拓扑 + t3 引用 + t9 安全联合作业面）

```
$ PORT=8714 RENEWAL_FORCE_RULE_MODE=1 uvicorn server.app:app   # health: {"llm_mode":"rule","wiki_entries":8,"nodes":11}
$ .venv/bin/python scripts/demo_chat.py http://127.0.0.1:8714
  ✅ 链路②-b: seq 从 1 连续到 20
  ✅ 链路②-b: SPEC §5 基础字段齐全
  ✅ 链路②-b: record_type 枚举合法
  ✅ 链路③: message 带 citations（wiki-annual-inspection / 合成细则 v2024.3）
  ✅ 链路③: 条款问答不进入比价/确认，finish_reason=end
✅ 全部链路通过（三链路 + 轨迹完整性）                          # exit 0
```

### 2.5 端到端冒烟（含重启恢复）

```
$ ./scripts/e2e_smoke.sh 8715
  ✅ 重启前 trace 仍可回放（28 行）
  ✅ 越权 → 422 OWNER_MISMATCH / 旧版本 → 409 QUOTE_VERSION_STALE / 不存在 → 404
  ✅ POST /confirm 200 → ORD-20261117-9704；重复确认幂等（同一 order_id）
  ✅ 会话状态跨重启（awaiting_confirm → 对话内"确认"）
✅ E2E smoke 全部通过（AC 链路 + 重启恢复 + 确认幂等）
```

### 2.6 域内评测（记忆 / 知识 / 评测）

```
$ .venv/bin/python eval/memory_eval.py
s1_cross_session_preference   FAIL → PASS
s2_contradiction_resolution   FAIL → PASS
s3_constraint_consistency     FAIL → PASS
s4_context_budget_and_summary FAIL → PASS   {"prompt_tokens": 975, "bounded": true, "dropped_turns": 27}
s5_erasure_and_portability    FAIL → PASS
合计：before 0/5 → after 5/5

$ .venv/bin/python eval/memory_quote_neutrality.py
turns: 7 · premium mismatch: {} · on seeded: {} · VERDICT: PASS

$ .venv/bin/python eval/knowledge_retrieval_eval.py
| 变体 | Hit@1 | Hit@3 | MRR@5 | 引用接地率@3 | 拒答 |
| A 单通道 BM25（旧基线）      | 0.81 | 1.00 | 0.896 | 0.85 | 1/1 |
| C 三通道+RRF（当前默认路径） | 0.88 | 1.00 | 0.938 | 0.90 | 1/1 |
```

### 2.7 评测门禁（规则模式 + 抖动采样）

```
$ RENEWAL_FORCE_RULE_MODE=1 RENEWAL_RATE_LIMIT_DISABLED=1 \
  .venv/bin/python eval/run.py --port 8716 --results eval/results-t10-rule.json --repeat 2
=== 评测完成：19/19 PASS，hard 失败 0 条，总耗时 3.9s ===
- 对比基线：20261117-120404（成对断言级精确二项检验，McNemar）
- 退化翻转 b=0 / 修复翻转 c=0，单侧 p=1（α=0.05）
- 判定：✅ 无显著退化
```

---

## 3. 真实 LLM 严格模式验证（独立复跑，非引用队长数字）

凭证已由队长侧配好（`.env`，`mode=llm`）。我侧跑了两轮，**第一轮暴露了基线不同模式的坑，第二轮才是有效对照**：

| 轮次 | 命令 | 结果 | 回归判定 |
|---|---|---|---|
| ① 无基线对照 | `RENEWAL_LLM_STRICT=1 eval/run.py --port 8713 --results eval/results-t10-llm-strict.json --fail-on-degraded` | 19/19 PASS，hard 0，**33.1s**，零降级（exit 0） | ⚠️ "基线模式=rule vs 本次=llm：不可比"（默认基线是同模式的 rule 快照） |
| ② 同模式对照（有效） | `... --results eval/results-t10-llm-strict-baseline.json --baseline eval/baseline-llm.json --fail-on-degraded` | 19/19 PASS，hard 0，**37.9s**，零降级（exit 0） | ✅ 无显著退化（b=0 / c=0 / p=1，基线 stamp 20261117-213250） |

**结论**：真实模型链路上 19 条用例（含 SEC-01~05 五条对抗用例：系统提示套取、跨车主越权、虚构投保/抹除免责声明、伪装系统指令、路径穿越）全部通过，`--fail-on-degraded` 未触发说明**本轮没有发生静默降级为规则模式**。

证据文件：`eval/results-t10-llm-strict.json`、`eval/results-t10-llm-strict-baseline.json`、`eval/report-20261117-213525.md`、`eval/report-20261117-213610.md`。

---

## 4. 跨域踩踏 / 文件级冲突排查

### 4.1 结论

**未发现功能级踩踏：没有"后改的域把先改的域的成果覆盖掉"的情况。** 九域在同一工作区顺序落地，热文件被多域共同修改，但所有回归面（pytest 140/2、ruff、llm 19/19、e2e、security_check、platform_check）都通过，说明各自改动在同一进程内共存正常。

**唯一真碎片是类型门禁层面**（§2.1 的 14 个 mypy 错误），它不影响运行时行为，只影响 CI 的 lint 作业。

### 4.2 同文件多域改动清单（本次实读确认）

| 文件 | 触及域 | 是否会冲突（结论） |
|---|---|---|
| `server/app.py` | t5（SSE 原生管线重写）→ t8（轮次收口 `finish_turn`）→ t9（PII/安全响应头）→ t12（import 排序） | 否：四域改的是不同关注点（生成器/指标收口/安全/import），e2e + demo_chat + SSE 测试全绿佐证 |
| `server/graph.py` | t1（分层重试/删锁/durability/递归翻译）→ t3（retrieve_terms 增 anchors）→ t4（4 处记忆调用点）→ t11（LLM 降级可观测） | 否：拓扑快照测试（25 断言）+ 编排回归全绿 |
| `server/config.py` | t4（记忆预算旋钮）→ t9（LLM 超时/限流开关）→ t11（严格模式） | 否：互不重叠的新配置项 |
| `server/llm.py` | t1（重试语义）→ t11（`_on_failure` + degraded 标记 + `node` 形参修复） | 否（曾有一处 F821 跨域告警，已由 t11 修掉，t12 §7.4 留痕） |
| `server/trace.py` | t8（派生 latency）→ t9（写端 PII 脱敏） | 否：同函数不同语句，security_check C/E2 实测零 PII 原文 |
| `server/sessions.py` | t4（记忆写入点 + 上限）→ 被 t4 引入 `memory` import（**本次 mypy 碎片来源**） | 功能否 / 门禁是 |
| `server/middleware.py` | t9（鉴权/限流/CSP/限流开关）| 否 |
| `mcp_servers/quote_server.py`、`server/mcp_bridge.py` | t2 → t12（import） | 否：MCP 8 例 + 54 项自测全绿 |
| `eval/run.py`、`eval/*` | t7（门禁/统计/基线）→ t4/t3 新增独立评测脚本 | 否：t7 的门禁对新增脚本无耦合 |
| `web/index.html` | t6（SSE 解析/Trusted Types/reduced-motion）→ t9（CSP 头由服务端下发，前端补 default 策略） | 否：t9 已在报告登记"t6 default 策略应加净化"为跨域移交项 |

### 4.3 交叉验证手段（不靠"看起来没问题"）

1. `def` 计数 vs 去重计数：`graph.py` 51/51、`sessions.py` 6/6、`app.py` 7/7、`llm.py` 11/11、`trace.py` 6/6 → 无整段覆盖式重复定义。
2. `ruff` 全绿 → 无重复 import / 语法破坏（这是"多域改同一文件"最典型的翻车形态）。
3. `pytest 140/2` → 跨域行为契约（SSE、持久化、MCP、安全、记忆、编排、评测工具）全部仍成立。
4. `e2e_smoke` 含**重启恢复**与**确认幂等** → 覆盖了 t4 记忆写入点、t1 durability、t9 幂等校验三者的耦合面。

### 4.4 一处非阻塞观察：轨迹库被回归任务污染

仓库 `traces/` 现有 **1136** 个 `.jsonl`。本次 `demo_chat`（3 轮）、`e2e_smoke`（多轮）、两次 LLM 评测（19 例 × 2 轮）都会往仓库默认 `TRACE_DIR` 写轨迹。
`tests/conftest.py` 已把 pytest 的 TRACE_DIR 隔离到临时目录（t8 F8 修复，实测不再增长），但**脚本类回归（demo_chat/e2e/eval）没有隔离**。属"观测数据卫生"遗留项，不影响功能判定，建议后续给这几个脚本统一加 `TRACE_DIR=$(mktemp -d)`。

---

## 5. 九域评分汇总（各域自评，供 INDEX 引用）

| 域 | 任务 | 报告 | 优化前 | 优化后 | 关键遗留 |
|---|---|---|---|---|---|
| Agent 编排 | t1 | `orchestration.md` | 7.0 | **8.3** | 未用官方 `interrupt()`/`Command(resume=)`（P1）；节点级 timeout 对 sync 节点不可用（P1） |
| MCP 工具层 | t2 | `mcp.md` | 7.0 | **8.5** | outputSchema（P2）、stdio 会话生命周期（P3） |
| 知识检索 | t3 | `knowledge.md` | 6.0 | **8.0** | 7 条条款 `effective_date=2024-01-01` 需业务复核；未接稠密通道 |
| 记忆机制 | t4 | `memory.md` | 2.7 | **7.7** | 双真源未合并（编排域决策）；SPEC 未登记记忆域（v1.0.6 提案） |
| API / SSE | t5 | `api.md` | 6.5 | **8.0** | Last-Event-ID 真续传未做（显式声明不支持）；多进程限流/订单存储 |
| 前端 | t6 | `frontend.md` | 7.0 | **8.0** | HTTP/2 / 多页签连接治理（跨域） |
| 评测体系 | t7 | `eval.md` | 6.5 | **8.0** | LLM 模式真跑已由本轮补齐（原 429 阻塞），语义质量维度仍无断言 |
| 平台工程 | t8 | `platform.md` | 2.4 | **8.3** | 镜像/promtool/collector 未实跑（本机无 docker）；轨迹 schema 缺 model/provider |
| 安全合规 | t9 | `security.md` | 4.5 | **7.7** | 按 key 配额、多副本 Redis、at-rest 加密、Safari/Firefox 未测、未做渗透 |
| **均值** | — | — | **5.4** | **8.06** | — |

---

## 6. 与队长侧验证的差异（交叉核验）

对照 `reviews/captain-verification.md`（队长侧，端口 8711/8712）：

| 项 | 队长侧 | 我方实测 | 差异判断 |
|---|---|---|---|
| 真实 LLM 全量评测 | 19/19 PASS，hard 0，**36.1s** | 19/19 PASS，hard 0，**33.1s**（首次）/ **37.9s**（带基线对照） | 一致；耗时差异 3–4s 属模型与网络抖动，非代码差异 |
| 降级计数 | 零降级 | 零降级（`--fail-on-degraded` 未触发，两次均如此） | 一致 |
| pytest | 140 passed / 2 skipped（1.21s） | **140 passed / 2 skipped（1.64s）** | 一致（用例数完全对齐） |
| ruff | All checks passed | All checks passed | 一致 |
| e2e smoke | E2E_EXIT=0 | 全通过（含重启恢复/幂等） | 一致 |
| **mypy** | 未在 §4 列出门禁结果（仅引用 t8 的 "mypy 11→0"） | **14 errors in server/memory.py（门禁红）** | ⚠️ **本报告的增量发现**：t8 的 "11→0" 是 12:09 的事实，t4 在 16:07 新增 `memory.py` 后经 `sessions.py` 被拉入检查范围，门禁重新变红。队长侧回归清单若未跑 mypy，会漏掉这条 |

结论：**除 mypy 一项外，我方与队长侧数字完全一致**；mypy 属"回归清单覆盖缺口"型发现，建议并入 INDEX 的风险清单并在 CI 门禁里显式化。

---

## 7. 遗留与风险

### 7.1 阻断项（会挂 CI）

| ID | 级别 | 问题 | 位置 | 建议 |
|---|---|---|---|---|
| INT-1 | **P0 / blocker** | mypy 14 errors（经 `sessions.py` import 牵连） | `server/memory.py:287,565,571,578,582,707,785-797` | ①`pyproject.toml` files 显式加入 `server/memory.py` 让门禁可见（当前是"隐式牵连"，易被误判为无关）；②补 14 处注解/None 守卫（记忆域，机械性改动，16 条记忆测试可作护栏）；③若短期不修，CI lint 作业需显式 `|| true` 并挂 issue，否则流水线长期红 |

### 7.2 已完成的跨域闭环（本轮确认）

- t8 F10「轨迹默认全量采集 PII」→ t9 已落地写端+读端双重脱敏（security_check C/E2 实测 1010 文件零 PII 原文）。
- t7 F15「`.env` 指 glm-4.6 → RateLimitError，LLM 真实验证阻塞」→ 本轮已解除：严格模式 19/19 真实模型通过。
- t1 F6「LLM 降级不可观测」→ t11 已落地 `llm_degraded` 事件 + 严格模式 503。
- t2 F7「wiki_search.py 语法错误致 server 侧无法收集」→ 当前不复现（pytest 140 全绿）。

### 7.3 未完成项（明确标注原因，未强跑）

| 项 | 状态 | 原因 |
|---|---|---|
| 镜像构建 / promtool 校验 / collector 实跑 | **未跑** | 本机无 docker / promtool / otelcol（t8 同样受限），仅做配置↔指标的静态一致性自检（platform_check 4/4） |
| CSP + SSE 真实浏览器复核（Chrome 11/11） | **未跑** | t9 已验证并留证据；本轮为集成回归未重复启动浏览器（避免与队长侧并发争用） |
| Safari / Firefox 兼容 | **未跑** | t9 登记为遗留 L7 |
| 渗透测试 / 模糊测试 | **未跑** | t9 登记为遗留 L9，超出集成回归范围 |
| 多副本（Redis 限流/共享订单/共享记忆） | **未跑** | 单进程部署形态，t9/t8 均登记为设计遗留 |

### 7.4 其他风险（非阻断）

1. **轨迹库卫生**：§4.4，脚本类回归未隔离 `TRACE_DIR`（1136 个文件且持续增长）。
2. **wiki stale claim**：7 条条款 `effective_date=2024-01-01`（2.9 年），lint 已能检出，需业务方复核——这是**内容风险**，不是代码风险。
3. **双真源**：`sessions.json` 与 LangGraph checkpoint 各自持久化状态（t4 已给对账工具 `memory_tool divergence`，未合并）。
4. **SPEC 版本漂移**：安全域已升 v1.0.6（§4.5.1），记忆域只有提案未登记（t4 F8）——INDEX 引用时需注明各域报告的 SPEC 基线版本不同。

---

## 8. 复现命令清单（原样可跑）

```bash
cd renewal-assistant

# 静态门禁
.venv/bin/python -m ruff check .                      # 期望 exit 0
.venv/bin/python -m mypy                              # 当前 14 errors（INT-1）

# 测试与自检
.venv/bin/python -m pytest                            # 140 passed, 2 skipped
.venv/bin/python scripts/security_check.py            # 12/12
.venv/bin/python scripts/platform_check.py            # 4/4
.venv/bin/python scripts/wiki_tool.py lint            # 0 error / 7 warn
MCP_TEST_STDIO=1 .venv/bin/python -m pytest tests/test_mcp.py   # 8 passed
.venv/bin/python mcp_servers/test_quote_server.py     # 54/0

# 端到端
./scripts/e2e_smoke.sh 8715                           # 自管服务，含重启恢复
PORT=8714 RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python -m uvicorn server.app:app --port 8714 &
.venv/bin/python scripts/demo_chat.py http://127.0.0.1:8714 && kill %1

# 评测（规则模式 / 真实 LLM 严格模式）
RENEWAL_FORCE_RULE_MODE=1 RENEWAL_RATE_LIMIT_DISABLED=1 \
  .venv/bin/python eval/run.py --port 8716 --results eval/results-t10-rule.json --repeat 2
RENEWAL_LLM_STRICT=1 RENEWAL_RATE_LIMIT_DISABLED=1 \
  .venv/bin/python eval/run.py --port 8713 --results eval/results-t10-llm-strict-baseline.json \
    --baseline eval/baseline-llm.json --fail-on-degraded

# 域内评测
.venv/bin/python eval/memory_eval.py                  # 0/5 → 5/5
.venv/bin/python eval/memory_quote_neutrality.py      # PASS
.venv/bin/python eval/knowledge_retrieval_eval.py     # Hit@1 0.88 / MRR@5 0.938
```
