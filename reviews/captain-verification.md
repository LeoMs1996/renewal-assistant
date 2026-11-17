# 队长侧独立验证记录（captain-verification · 2026-11-17）

> 本文件由团队队长（captain）在 9 个域任务完成后**独立执行**，用于交叉验证各域自述结论，不替代各域报告。
> 所有命令均在工作目录 `renewal-assistant/` 下执行，Python 使用 `.venv/bin/python`，端口与常驻 8000 隔离。

## 0. 环境与前提

| 项 | 值 |
|---|---|
| 模型路由 | DeepSeek Anthropic 兼容端点，`MODEL_NAME=deepseek-chat` |
| 凭证配置 | `.env`（已备份旧 GLM 配置为 `.env.glm.bak`，`.gitignore` 已加 `.env.*` 与 `!.env.example`） |
| 探活结论 | `mode=llm`、`degraded=False`、`error_type=None` —— **项目首次真正走模型而非规则兜底** |
| 严格模式 | `RENEWAL_LLM_STRICT=1` |

## 1. 真实 LLM 严格模式全量评测（首次真实模型全绿）

```bash
RENEWAL_LLM_STRICT=1 .venv/bin/python eval/run.py \
  --port 8711 --results eval/results-llm-strict-captain.json --fail-on-degraded
```

| 指标 | 结果 |
|---|---|
| 服务模式 | `/health.llm_mode=llm`（strict=True） |
| 用例结果 | **19/19 PASS**，hard 失败 0 条 |
| 降级断言 | `--fail-on-degraded` 未触发（零降级） |
| 耗时 | 36.1s |
| 报告 | `eval/report-20261117-213209.md` |
| 快照 | `eval/results-llm-strict-captain.json` |

覆盖：AC-01…AC-14 全 PASS（含 AC-10 网约车转人工、AC-12 24h 过期 409、AC-13 幂等+越权），SEC-01…SEC-05 注入用例全 PASS（系统提示套取 / 跨车主越权 / 虚构投保 / 伪装系统指令 / 路径穿越）。

## 2. LLM 模式回归基线归档（闭环 t7 指出的缺口）

```bash
RENEWAL_LLM_STRICT=1 .venv/bin/python eval/run.py \
  --port 8712 --results eval/results-llm-baseline.json \
  --baseline eval/baseline-llm.json --save-baseline
```

| 指标 | 结果 |
|---|---|
| 结果 | 19/19 PASS，hard 0，66.5s |
| 基线文件 | `eval/baseline-llm.json`（13328 bytes） |
| 基线元信息 | `stamp=20261117-213250`，`mode=llm`，19 cases |

**意义**：t7 曾指出「`--diff` 基线模式=rule vs 本次=llm 不可比 → CI 退化对比对 LLM 跑法永远失效」。归档 LLM 基线后，同模式对比才真正生效；跨模式时 run.py 会如实报「不可比」而非给出错误结论（本轮实测确认该行为）。

## 3. 端到端冒烟（真实模型，重启恢复 + 幂等）

```bash
./scripts/e2e_smoke.sh 8731
# E2E_EXIT=0
```

| 阶段 | 结果 |
|---|---|
| phaseA | 全通过：比价链路节点链 7 节点完整、MCP 真实调用 `['get_policy','query_quote','query_quote']`、DSX 保额 200 万 tiers 计价、compare 差异表；改保额 300 万触发重询价；附加险 YWYW 行项；条款问答带 citation（`wiki-annual-inspection`）且不进比价；轨迹 28 行 seq 连续 |
| phaseB | 全通过：kill 服务重启后轨迹仍可回放；`/confirm` 错误码矩阵 422 `OWNER_MISMATCH` / 409 `QUOTE_VERSION_STALE` / 404；确认成功 `ORD-20261117-1339` 且重复确认幂等；会话状态跨重启（`awaiting_confirm` → 对话内"确认"推送 `confirmed`） |

## 4. 全量回归与静态检查

```bash
.venv/bin/python -m pytest        # 140 passed, 2 skipped in 1.21s   (exit 0)
.venv/bin/python -m ruff check .  # All checks passed!
```

| 项 | 开工前 | 本轮结束 |
|---|---|---|
| pytest | 76 passed / 2 skipped | **140 passed / 2 skipped**（+64 断言） |
| ruff | 有 I001 残留 | **全仓零告警** |

该结果证明 9 个域的改动在合并后仍互相兼容，未出现互相踩踏。

## 5. 与各域自述的一致性核对

| 域 | 自述关键结论 | 队长侧交叉验证 |
|---|---|---|
| t1 编排 | 19/19 PASS、25 断言、删无效锁 | 认同；其 F6（LLM 降级不可观测）已由 t11 闭环 |
| t2 MCP | 协议级 isError、stdio 接线 | 认同；e2e 中 MCP 工具真实调用成功 |
| t3 知识检索 | 引用接地 16/16、Hit@1 0.81→0.88 | 认同；e2e 条款问答带 citation |
| t4 记忆 | 跨会话记忆、报价中性哨兵 | 认同；AC-02/03/06 保费断言全 PASS |
| t5 API/SSE | 原生 SSE、12 事件契约 | 认同；e2e 事件流完整 |
| t6 前端 | SSE 解析器 CR 行尾、Trusted Types | 未做浏览器端复测（依赖 t9 CSP 11/11 结论） |
| t7 评测 | McNemar 回归、覆盖矩阵 | 认同；本轮真实 LLM 基线正是其缺口的补足 |
| t8 平台 | mypy 11→0、指标空转修复 | 认同；pytest/ruff 我侧复跑一致 |
| t9 安全 | 注入 5/5、PII 687→0、限流 429 | 认同；SEC-01…05 在真实模型下同样 PASS |

## 6. 未覆盖 / 待后续

1. **未做**：多副本/Redis 限流、Safari/Firefox 浏览器实测、OWASP API Top10 原文逐条核对、渗透测试（t9 报告 §8 已如实登记）
2. **未做**：真实 LLM 的 nightly 回归（需 CI 定时任务 + 凭证托管）
3. **未做**：前端浏览器端人工复核（Trusted Types/CSP 的浏览器证据取自 t9 的 `reviews/security-live-evidence.json`）
4. `e2e_smoke.sh` 在无 quote 时的 IndexError 健壮性问题仍在（历史遗留，不影响正常链路）
5. `traces/` 中约 411 个评审期间测试产生的轨迹文件未清理（t8 已记录，未删除）

## 7. 收口后复验（t15 / t16 落地后，2026-11-17 21:41）

队 t15（SEC 断言语境化）、t16（memory.py 类型修复）落地后重新全量复验，**本节数据取代 §4 的旧数字**：

| 项 | §4（t15/t16 前） | §7（t15/t16 后） |
|---|---|---|
| pytest | 140 passed / 2 skipped | **148 passed / 2 skipped** |
| mypy | 14 errors（均在 server/memory.py） | **Success: no issues found in 6 source files** |
| ruff | All checks passed | All checks passed（不变） |
| tests/test_memory.py | 16 passed | 16 passed（行为未变） |
| memory A/B | 5/5 | **before 0/5 → after 5/5**（重跑确认） |
| 报价中性哨兵 | PASS | **PASS（turns 7, premium mismatch {}）** |

实跑命令与输出：

```bash
.venv/bin/python -m pytest                    # 148 passed, 2 skipped in 1.17s
.venv/bin/python -m mypy                      # Success: no issues found in 6 source files
.venv/bin/python -m ruff check .              # All checks passed!
.venv/bin/python eval/memory_quote_neutrality.py  # turns: 7 / premium mismatch: {} / VERDICT: PASS
.venv/bin/python eval/memory_eval.py          # 合计：before 0/5 → after 5/5
```

另：**N-01 已由队长修复** —— `SPEC.md` 中重复的 `### 4.5.1 安全增强（v1.0.6）` 空壳标题（原 305 行）已删除；现 435 行，标题唯一性检查（`grep -E '^#{2,4} ' | sort | uniq -d`）无重复。
## 8. 终局验收（2026-11-17 21:4x，全部 16 任务 completed 后）

### 8.1 门禁六件套（今日最终态）

```bash
.venv/bin/python -m mypy            # Success: no issues found in 7 source files
.venv/bin/python -m pytest          # 148 passed, 2 skipped in 1.36s
.venv/bin/python -m ruff check .    # All checks passed!
.venv/bin/python scripts/security_check.py   # 12/12 通过
.venv/bin/python scripts/platform_check.py   # 4/4 全部通过（1176 轨迹 → 10962 spans）
```

### 8.2 队长最后一项加固（门禁清单 ≠ 被检查面）

`server/memory.py` 原先**不在** `pyproject.toml [tool.mypy] files` 中，仅因被 `sessions.py` 导入而「顺带」被检查——t16 的 14 处错误正是这样漏进主干的。已于 `2026-11-17` 显式加入 files 清单（附注释说明原因），mypy 现检查 **7** 个源文件而不是 6。

### 8.3 最终交付物（`reviews/`，共 12 份 Markdown + 2 份证据 JSON，3224 行）

| 文件 | 性质 |
|---|---|
| `INDEX.md`（41.6 KB / 364 行） | **单一入口**：9 域评分 5.51→8.06、跨域遗留账本（已闭环 16 / 未闭环 23）|
| `captain-verification.md`（本文件） | 队长侧独立验证 + 与各域自述的一致性核对 |
| `INTEGRATION.md`（22 KB / 329 行） | t10 全链路回归证据（22 项中 21 通过，唯一红项 mypy 已闭环）|
| `orchestration.md` 34.9 KB · `mcp.md` 12.6 KB · `knowledge.md` 29.5 KB · `memory.md` 40.3 KB · `api.md` 6.2 KB · `frontend.md` 7.3 KB · `eval.md` 43.7 KB · `platform.md` 24.3 KB · `security.md` 45.0 KB | 9 份分域报告 |
| `security-live-evidence.json` · `security-wiki-injection-evidence.json` | 真实模型证据附件 |

### 8.4 与目标的对应关系

| 目标要求 | 达成证据 |
|---|---|
| 按域拆分（10 域）| t1–t10 各一域 + t11/t12/t13/t14/t15/t16 六项跨域收口 |
| 先检索 2026 最新基线再评审 | 9/9 域均建检索基线章（INDEX §三：64 条来源、约 13 个官方站点；3 处偏差已如实标注）|
| 评审 + 实现补齐 | 9 域评分均提升（最小 +1.0，最大 +5.9），代码落入 `server/`·`mcp_servers/`·`web/`·`eval/`·`deploy/`·`scripts/` |
| 分域报告存 `reviews/` | 9 份域报告 + 证据 JSON（已列于 8.3）|
| 出汇总索引 | `reviews/INDEX.md` |
| **真实 LLM 验证** | §1（队长侧）与 `INTEGRATION.md` §3（独立复跑）：均 19/19 PASS、零降级；LLM 基线 `eval/baseline-llm.json` |

### 8.5 明确未做（不美化）

见 §6 与 INDEX §4.B/4.C/4.E：X-02/X-06/X-07 需 SPEC 升版；N-02（`traces/` 991 文件）、N-03（eval 报告 40+ 份未归档）；LLM 基线尚未接入 CI 常规门禁；Redis 多副本限流、Safari/Firefox、OWASP 原文核对、渗透测试、nightly 回归均未做。

