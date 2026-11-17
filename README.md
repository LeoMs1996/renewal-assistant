# 车险续保助手（renewal-assistant）

对话式车险续保顾问：LangGraph 状态机编排 + MCP 报价工具（get_policy / query_quote）+ BM25 条款检索（citations 带来源与版本）+ 轨迹 JSONL 全程可回放。

> **唯一契约 = [SPEC.md](SPEC.md)（v1.0.2）**：字段/接口/事件/状态机一律以它为准。v1.0.0 → v1.0.2 变更见 §9。
> **数据声明：所有保单/车主/费率/条款均为虚构合成数据，所有报价均为模拟报价。**

架构与设计详见 [docs/设计方案.md](docs/设计方案.md)；各阶段实现小结在 [docs/summaries/](docs/summaries/)；评测结果在 [eval/report.md](eval/report.md)。

## 1. 环境要求

- Python **3.14**（系统 Python 受 PEP 668 限制，请用项目 `.venv`）
- 依赖版本（当前实测）：fastapi 0.162.4 · uvicorn 0.54.0 · langgraph 1.2.20 · **mcp 2.3.0**（SDK 2.x，`MCPServer`）· rank-bm25 0.2.2 · anthropic 2.8.0 · httpx 0.28.1
- 模型：GLM（Anthropic 兼容接口）。**缺凭证时自动降级规则模式**，`/health` 的 `llm_mode` 如实标注（`rule`/`llm`），服务不崩溃。

## 2. 安装

```bash
cd renewal-assistant
python3 -m venv .venv            # 若 .venv 已存在可跳过
.venv/bin/pip install -r requirements.txt
```

## 3. 配置（GLM 模型接入）

```bash
cp .env.example .env
# 编辑 .env，填入 GLM 三变量（Anthropic 兼容接口，此组优先）：
#   ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
#   ANTHROPIC_AUTH_TOKEN=<你的GLM令牌>
#   MODEL_NAME=glm-4.6
```

- 代码不含任何密钥，凭证只从 `.env` 读取（`.env` 已被 `.gitignore` 忽略）。
- 不配置上述变量即运行规则模式（关键词规则解析，输出带【规则模式】标注）。
- 早期已知问题（GLM tool-use 把可空字段序列化为字符串 `"null"` 导致 `INVALID_USE_NATURE`）**已修复**：`server/llm.py` 在工具 JSON 出口统一归一化（normalize_tool_json，见 docs/summaries/repair.md），LLM 模式下 MCP 自测 / demo_chat / e2e_smoke / eval 全链路已实测通过。剩余一处规则模式独立缺陷见 §5 末尾备注。

## 4. 启动

```bash
.venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8000
```

- Web 工作台：<http://127.0.0.1:8000/>（身份下拉选择车主，对话 + 报价卡 + 轨迹抽屉）
- 健康检查：`GET /health` → `{"llm_mode": "rule|llm", "graph": "langgraph", "nodes": 11, "wiki_entries": 8}`
- REST：`POST /chat`（SSE 12 种事件）、`GET /policy/{owner_id}`、`GET /trace/{trace_id}`、`POST /confirm`（详见 SPEC §4）

## 5. 测试命令

```bash
# ① MCP 报价服务自测（54 断言：脱敏/幂等/三档三者险/六规则/24h）
.venv/bin/python mcp_servers/test_quote_server.py

# ② 三链路自测（比价→await_confirm / 改保额复用报价 / 条款问答带 citation）+ 轨迹完整性
#    需 8000 端口服务已启动
.venv/bin/python scripts/demo_chat.py

# ③ 端到端串测（AC 链路 + 重启恢复 + 确认幂等；自管 uvicorn，不占 8000，可带端口参数）
./scripts/e2e_smoke.sh 8123

# ④ 19 场景一键评测（AC-01~14 + SEC-01~05 对抗用例；自管 8123；--diff 对比上一份报告）
RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python eval/run.py
RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python eval/run.py --diff

# ⑤ 单测 / 静态检查（等价于 CI 的四道闸门）
.venv/bin/python -m pytest tests/ mcp_servers/
.venv/bin/python tests/test_llm_normalization.py
ruff check . && mypy

# ⑥ MCP 真实协议链路（子进程 + JSON-RPC 握手）
MCP_TRANSPORT=stdio .venv/bin/python mcp_servers/test_quote_server.py
```

以上命令 2026-11-13 实测均退出码 0：pytest 18 passed、MCP 自测 54/54、LLM 归一化 15/15、评测 **19/19 PASS**（规则模式，含 5 条对抗用例）。
> AC-06（「从 100 万升到 200 万」取首个数字）已于 **v1.0.4** 修复：规则模式改为识别 `升到/调到/改为` 等显式目标动词后取档位，因此**不再需要**用 LLM 模式规避。完整的 2026-11-13 优化与复评见 `docs/评估与优化报告-20261113.md` 附录 A。

## 6. 测试身份

| owner_id | 车主 | 场景 |
|---|---|---|
| `OWN-1001` | 张伟 | 临期续保（保单 2026-12-05 到期，`expiring_soon=true`） |
| `OWN-1002` | 李静 | 非临期询价（2027-06-20 到期，保单含划痕险 BLPS；SPEC v1.0.1 已补录 BLPS 费率 base_premium=400.0（synthetic/rates.json），询价正常计价，不再返回 `RATE_NOT_FOUND`） |
| `OWN-9999` | — | 查无此人（404 `found=false`，兜底不编造） |

## 7. 任务恢复方式

服务重启后**无需重开对话**，直接续跑：

- 会话状态落盘于 `traces/sessions/{session_id}.json`（常驻需求 needs/needs_version/invalidated、最新报价 latest_quote、原方案对照 baseline_quote、对话历史尾部 20 条、挂起状态 awaiting_confirm）；
- 报价与订单落盘于 `traces/quotes.json`（重复确认同一 quote 返回同一 order_id，幂等）；
- 历史轨迹 `traces/{trace_id}.jsonl` 随时可经 `GET /trace/{trace_id}` 回放。

复现路径：`./scripts/e2e_smoke.sh` 阶段 A 写入 session/quote → kill 服务 → 重启 → 阶段 B 用重启前的 quote 确认成功（integration.md 实测：跨重启 confirm 200 且幂等）。

## 8. 目录速览

```
SPEC.md            # 唯一契约（v1.0.2）
server/            # FastAPI + LangGraph 状态机 + SSE + 会话/轨迹/报价登记
mcp_servers/       # quote-server（MCP 2.x，stdio）：get_policy / query_quote
web/index.html     # 前端对话工作台（单文件零构建）
wiki/              # 条款知识库 8 条（BM25 检索源）
synthetic/         # 合成数据 owner/policy/rates
skills/            # renew_compare.md 比价七步技能
eval/              # 19 场景用例（AC-01~14 + SEC-01~05）+ run.py 一键评测 + report*.md
scripts/           # demo_chat.py / e2e_smoke.sh
traces/            # 轨迹 JSONL + sessions/ + quotes.json（gitignore）
docs/              # 设计方案 / 演示记录 / summaries（各阶段小结）
```

## 9. SPEC 版本变更说明（v1.0.0 → v1.0.4）

| 版本 | 日期 | 变更内容 | 来源小结 |
|---|---|---|---|
| v1.0.1 | 2026-11-12 | ① AC-10 书面裁决：网约车营运用途**不报价、转人工、引 wiki-ride-hailing**（1.6 营运系数仅保留在 rates 数据层，不再入自动报价）；② 补录 BLPS（划痕险）费率 base_premium=400.0（synthetic/rates.json）；③ quote_id 序号持久化登记（traces/quote_seq.json，跨进程不撞号） | docs/summaries/repair.md |
| v1.0.2 | 2026-11-12 | §3 报价规则新增第 7 条「选择键归一化」：sum_insured 等于费率表默认值视为与缺省等价、JQX 固定保额不携带；需求无变化时同键只询价一次（修复 AC-05 重复询价） | docs/summaries/final-repair.md |
