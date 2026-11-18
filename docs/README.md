# renewal-assistant —— 续保助手 + 理赔域（研究原型，**非生产系统**）

> 一句话：这是一个**可复现的研究/作业原型**，在既有「车险续保助手」之上新增了「理赔域」，并搭了一条从公开数据集抽样到可检索知识库的完整流水线。
> **先读**：[`docs/log/INDEX.md`](log/INDEX.md)（全流程总账：做了什么 / 证据在哪 / 哪些没做 / 哪里自相矛盾）。
> 详细契约：[`SPEC.md`](../SPEC.md)（续保 v1.0.6）、[`claims/SPEC-claims.md`](../claims/SPEC-claims.md)（理赔 v1.0.x）。

---

## 1. 这是什么：两条流水线 + 一条主干

| | 解决什么问题 | 关键产物 | 状态 |
|---|---|---|---|
| **主干（续保）** | 车险续保问答与报价：保单一查、条款检索、询价、确认下单；保费**只来自报价服务**，模型不得编造数字 | `server/`（FastAPI + SSE）、`mcp_servers/`（`get_policy` / `query_quote`）、`wiki/`（8 条合成条款） | ✅ 已交付（148 passed / 2 skipped） |
| **流水线① 知识侧** | 公开数据集 **INS-MMBench** 子集抽样 → 规范化为 raw → 编译成 **LLM-Wiki**（36 页，断言级引用） → 检索 + 评测 | `data/ins-mmbench/**`（抽样）、`data/llm-wiki-claims/**`（raw 54 条 + wiki 36 页 + 2 套 lint + 检索评测） | ⚠️ 主体完成，检索层(D5)刚落地、无交付日志 |
| **流水线② 理赔域** | **LangGraph 确定性流程**（报案→核验→审核→支付：中断恢复、幂等支付、状态守卫）× **Deep Agents 长程材料分析**（只抽事实与出处，不做金额/结论） | `claims/graph.py`（编排）、`claims/SPEC-claims.md`（契约）、`claims/deep_agents/**`（材料分析）、`claims/tools/**`（纯函数金科玉律） | ⚠️ 库级完成，**无 HTTP/SSE 层**（F4 未开始） |

**设计红线**（三条，贯穿全部文档）：① 金额只能服务端算；② 越权/编造 = 硬失败；③ 一切为**模拟报价 / 合成数据**。
**工作方式**：由 6 个 Agent（wiki-lead / dataset-lead / flow-engineer / deepagents-engineer / retrieval-engineer / integrator）分工完成，全程留痕：每个步骤一份 `docs/log/step-*.md` + 一条 `decisions.md` 决策。

---

## 2. 目录结构

```text
renewal-assistant/
├── SPEC.md                  # 续保域唯一契约（v1.0.6，19 条验收）——**保护对象**
├── README.md                # 本文件（对外说明）
├── server/                  # 续保后端：FastAPI + SSE 12 类事件、轨迹、指标、安全、记忆
├── mcp_servers/             # 续保 MCP 工具：get_policy / query_quote（模拟报价）
├── wiki/                    # 续保知识库（LLM-Wiki，8 条合成条款）——**保护对象，只读**
├── tests/                   # 续保测试（148 passed / 2 skipped 的来源）
├── eval/                    # 续保评测：19 条验收用例 + 运行器
├── claims/                  # 理赔域（方案 C：同仓新增子域，不改续保）
│   ├── SPEC-claims.md       #   理赔契约：11 态状态机 / 14 错误码 / MaterialsAnalysis / CLM-01~20
│   ├── ARCHITECTURE.md      #   结构说明（节点、边、中断点）
│   ├── graph.py             #   LangGraph 编排（唯一 interrupt 在 review_gate；幂等支付键；终态守卫）
│   ├── state.py / config.py #   状态字段与错误码 / 环境变量（CLAIMS_* 全部在此）
│   ├── tools/               #   纯函数：金额计算、幂等键、状态迁移守卫、模拟支付网关、逐字引用校验
│   ├── deep_agents/         #   Deep Agents：材料→事实+出处（schema 层无金额/结论），多分片 workspace 隔离
│   ├── wiki_retrieve.py     #   理赔检索（BM25+RRF，raw 级引用核查）——D5
│   ├── eval_retrieval.py    #   检索评测 CLI（Hit@1/MRR@5/引用接地率）
│   └── tests/               #   理赔测试（**不并入默认 pytest 收集**，见 §4）
├── data/
│   ├── ins-mmbench/         #   INS-MMBench 抽样（manifest/records/raw/**，大文件不入库，见 FETCH.md）
│   └── llm-wiki-claims/     #   理赔知识流水线
│       ├── raw/sources/     #     54 条规范化 raw（逐行可回溯的源头）
│       ├── wiki/            #     36 页 LLM-Wiki（4 doc / 18 section / 9 entity / 5 faq）+ index/log/schema
│       ├── scripts/         #     compile_wiki.py / wiki_lint.py / wiki_claims_lint.py / normalize_raw.py
│       └── plan.md          #     36 页的编译计划（页面清单与依据）
├── traces/                  # 续保轨迹（gitignored，含 PII，运行态）
├── traces-claims/           # 理赔轨迹（gitignored，与 traces/ 物理隔离）
├── docs/
│   ├── log/                 # 全程文档：step-*.md（每步四件套）+ INDEX.md（总账）+ decisions.md（决策台账）
│   ├── research/            # 研究结论 + evidence/（MANIFEST 登记 sha256/URL/抓取时间）
│   └── summaries/           # 早期分模块总结（历史遗留，非本次主线）
├── .venv/                   # 续保解释器（**148 passed 的基线环境**）
└── .venv-claims/            # 装了 deepagents==0.7.39 的独立解释器
```

---

## 3. 怎么跑（**两个解释器，别混用**）

### 3.1 为什么必须两个解释器

`deepagents==0.7.39` 会把 `tenacity` 降到 9.1.4、`langchain-core` 升到 1.8.1（真因：`google-genai` 要求 `tenacity<9.2.0`）。续保基线是既成事实的 148 passed，**不接受共享 venv 的包漂移**，所以复制出 `.venv-claims` 单独装。
契约依据：`claims/SPEC-claims.md` **§8.0 运行前提（blocker：解释器）**；决策：`decisions.md` D-05 / D-22。

| 解释器 | 用途 | 不能做什么 |
|---|---|---|
| `.venv/bin/python` | 续保基线、`claims/tests`（降级路径） | 不能验收 Deep Agents：`DEEPAGENTS_ENABLED=true` 时 F3 抛 `DeepAgentsNotInstalled`，**静默降级为规则模式**（"假绿"） |
| `.venv-claims/bin/python` | 理赔全链（含 `claims/deep_agents/**`） | 不必用来跑续保基线（也能跑，但不是口径） |

### 3.2 最小可跑命令（①–④ 已实测；⑤ 本次未执行）

```bash
cd renewal-assistant

# ① 三套测试（口径见 INDEX.md §4，数字带时间戳）
.venv/bin/python -m pytest -o addopts="" -q                                  # 续保：148 passed, 2 skipped
.venv/bin/python -m pytest claims/tests -o addopts="" -q                    # 理赔流程（降级路径）
.venv-claims/bin/python -m pytest claims/deep_agents/tests -o addopts="" -q # Deep Agents（必须此解释器）

# ② 理赔流程最小 demo（库级，无 HTTP；写 tmp，不污染仓库）
T=$(mktemp -d)
PYTHONPATH=. CLAIMS_DATA_DIR=$T/data CLAIMS_CHECKPOINT_DB=$T/ck.sqlite CLAIMS_TRACE_DIR=$T/traces \
.venv/bin/python -c "
from claims.graph import run_claim_turn
from claims.tools import synthetic
out = run_claim_turn({'owner_id':'OWN-1001','policy_no':'POL-2026-0001','session_id':'demo',
  'report':{'occurred_at':'2026-11-01T08:20:00+08:00','location':'北京','description':'追尾','has_injury':False},
  'documents':synthetic.documents('complete')}, thread_id='demo-1')
print('status =', out.get('status'), '| payable =', (out.get('assessment') or {}).get('payable_amount'))
"
# 期望：status = paid | payable = 2100.0   （2600 定损 − 500 免赔额；金额全部由服务端算）

# ③ 理赔知识检索（LLM-Wiki 36 页，含 raw 级引用核查）
PYTHONPATH=. .venv/bin/python -m claims.wiki_retrieve "免赔额" --top-k 3
PYTHONPATH=. .venv/bin/python -m claims.eval_retrieval            # 检索评测（只报检索指标）
#   实测（20:32:18）：语料 36 页/122995 字符；rewritten Hit@1=0.714 MRR@5=0.827 引用接地=1.0；
#   negative 拒答 4/4。注意：查询集规模小（6/14/4），不能做统计推断。

# ④ wiki 质检（两套 lint）
.venv/bin/python data/llm-wiki-claims/scripts/wiki_lint.py         # 期望 pages=36 index_rows=36 FAIL=0
.venv/bin/python data/llm-wiki-claims/scripts/wiki_claims_lint.py  # 期望 ERROR=0

# ⑤ 【未验证】续保服务 + 端到端冒烟（会起 uvicorn，默认 8123，不占 SPEC 的 8000）
#   状态：**本轮未执行 → 未验证**（避免与并行任务抢端口/改运行态），不得当“已实测”引用。
#   若要用作验收，请先自己跑一遍并记录输出。
#   覆盖范围以脚本头注释为准：AC-01/02/04/05/06/11/12/13/14 + 重启恢复。
./scripts/e2e_smoke.sh 8123
```

> `PYTHONPATH=.` 是必须的：`claims/` 不是安装包（`python -m claims.xxx` 在仓库根才能 import）。

### 3.3 环境变量（理赔域，全部可选）

`claims/config.py` 是唯一来源（`claims/SPEC-claims.md` §8.1 有总表）：`DEEPAGENTS_ENABLED`（默认 false）、`DEEPAGENTS_MODEL`、`CLAIMS_TRACE_DIR`（默认 `traces-claims`）、`CLAIMS_DATA_DIR`、`CLAIMS_CHECKPOINT_DB`、`CLAIMS_WIKI_DIR`（默认 `data/llm-wiki-claims/wiki`）、`CLAIMS_AMOUNT_REVIEW_THRESHOLD`（3000，**演示值**）、`CLAIMS_DEDUCTIBLE`（500，演示值）、`CLAIMS_MAX_PAYABLE`（20000，演示值）。
密钥只从 `.env` 读（`ANTHROPIC_*` / `MODEL_NAME`），**仓库内不含任何密钥**。

---

## 4. 局限（请勿当成生产系统）

1. **合成数据 + 模拟报价**：保单、条款、报价、支付网关全部是合成的；`MockPaymentGateway` 只在内存里记账。所有输出应理解为"演示"，不是承保或理赔结论。
2. **理赔域没有 HTTP/SSE 层**：`claims/graph.py` 是**库**（`ClaimGraph.invoke/resume`），前端/接口层属于尚未开始的 F4。
3. **Deep Agents 只在 `.venv-claims` 真实生效**：`.venv` 下会静默降级为规则抽取；验收 F3 必须写明解释器（否则"全绿"是假的）。
4. **知识侧只能评检索，不能报问答准确率**：INS-MMBench 的 5 个场景文件**没有 `answer` 列**（`fundamental.tsv` 因 1.44 GiB + 按任务排序被排除）。因此只报 Hit@1 / MRR@5 / 引用接地率（决策 D-04，属主动取舍）。
5. **循环论证的边界**：wiki 的每条断言都能回到 raw（36 页 1200 条断言全量可解析），但 raw 与评测集同源——**"能回溯"不等于"结论正确"**。
6. **抽样偏差**：liability 分片非严格 head-k（跳过 9 条），保留样本在"记录体积"维度偏高约 1.2×；property 只有 6 条，比例型结论无统计意义（`decisions.md` D-03 / D-14）。
7. **图片未入库**：`raw/assets/` 为空（省 33 MiB），新 clone 需按 `data/ins-mmbench/FETCH.md` 重取。
8. **两套 venv 是硬约束**：任何 CI/验收脚本写错解释器，都会得到"假绿"或 20 条 `ModuleNotFoundError` 假红。
9. **未完成**：F4（端到端集成）、C5（终验）、D5 的交付日志。逐项见 [`docs/log/INDEX.md §6`](log/INDEX.md)。

---

## 5. 从哪开始读

| 想知道什么 | 看哪 |
|---|---|
| 全流程做了什么 / 证据 / 缺口 | [`docs/log/INDEX.md`](log/INDEX.md) |
| 每条关键决策及其依据 | [`docs/log/decisions.md`](log/decisions.md) |
| 理赔域契约（状态机/错误码/schema/验收 20+4 条） | [`claims/SPEC-claims.md`](../claims/SPEC-claims.md) |
| 续保域契约（19 条验收） | [`SPEC.md`](../SPEC.md) |
| 跨域接口对账（2 blocker + 9 degradation） | [`docs/log/integration-contract.md`](log/integration-contract.md) |
| 知识库质检（36 页 lint + 引用复核） | [`docs/log/step-d4.md`](log/step-d4.md) |
| 研究证据（官方文档源 + sha256 清单） | [`docs/research/evidence/MANIFEST.md`](research/evidence/MANIFEST.md) |
| 工作纪律（每次改码前 ≥3 外部来源） | [`docs/log/hard-rules.md`](log/hard-rules.md) |

---

*本 README 由 integrator 在 t24 汇总（2026-11-18）；只描述现状，不承诺路线图。数字与状态以 `docs/log/INDEX.md` 的时间戳为准。*
