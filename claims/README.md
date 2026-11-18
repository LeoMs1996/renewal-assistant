# claims/ —— 理赔域（方案 C，新增子域）

> 状态：**C0 骨架占位，无业务代码**。建立于 2026-11-17。
> 所属：`renewal-assistant` 仓库内新增的独立子域，**复用**续保域的基础设施（轨迹、指标、LLM 客户端、SSE），**不修改**它们。

## 1. 职责边界

本域负责「车险理赔」全流程的确定性编排与长程材料分析：

```
报案(intake) → 核验(verify) → 审核(review) → 支付(settle)
                     ↑                │
                     └── 补件/退回 ────┘
```

与续保域的关系：

| | 续保域（既有，只读） | 理赔域（本目录） |
|---|---|---|
| 业务 | 报价 / 续保问答 | 报案 / 核验 / 审核 / 支付 |
| 契约 | `SPEC.md`（v1.0.6） | `claims/SPEC-claims.md`（占位，未定稿） |
| 编排 | `server/graph.py` | `claims/graph.py`（占位） |
| 知识 | `wiki/`（LLM-Wiki，只读） | `data/llm-wiki-claims/wiki/` |
| 轨迹 | `traces/`（只读） | `traces-claims/` |
| 测试 | `tests/`、`mcp_servers/test_*.py` | `claims/tests/` |

**一句话：理赔域只能新增，不许改续保域的任何一个字节。** 保护对象清单见 `docs/log/step-c0-baseline.md` 第 4 节。

## 2. 目录职责（当前全部为占位）

| 路径 | 职责 | 状态 |
|---|---|---|
| `SPEC-claims.md` | 理赔域契约（字段 / 状态机 / 事件 / 验收） | 占位，待 C4 定稿 |
| `graph.py` | LangGraph 编排（报案→核验→审核→支付） | 占位，函数恒抛 `NotImplementedError` |
| `deep_agents/` | Deep Agents 长程材料分析（事故材料、医疗票据、定损单） | 占位 |
| `tools/` | 理赔工具 / MCP server（核验、定损、支付） | 占位 |
| `tests/` | 理赔域测试 | 占位（当前未被 `pytest` 默认收集，见该目录 README） |

## 3. 复用续保基础设施的方式（不改源码）

`server/config.py` 已把运行态路径做成环境变量，**注入即可隔离**：

```bash
# 理赔域启动时必须注入（缺一即可能污染续保目录）
export TRACE_DIR="$PWD/traces-claims"
export WIKI_DIR="$PWD/data/llm-wiki-claims/wiki"
```

- 复用 `server/trace.py` → 轨迹落到 `traces-claims/`，续保 `traces/` 不受影响。
- 复用 `server/wiki_search.py` → 检索 `data/llm-wiki-claims/wiki/`，续保 `wiki/` 不受影响。
- 复用 `server/metrics.py` / `server/llm.py` 时，指标前缀与模型配置须另设（避免与续保指标混淆）——留待 C4 决策并登记。

## 4. 工程门禁（新代码必须过）

```bash
.venv/bin/python -m ruff check .          # E/F/I/B/UP，行长 100
.venv/bin/python -m mypy                  # 仅白名单文件；纳入 claims 需显式追加 pyproject.toml [tool.mypy].files
.venv/bin/python -m pytest                # 必须仍为 148 passed, 2 skipped
```

> 注意：`mypy` 采用**显式白名单**。历史上 `memory.py` / `otel_export.py` 因「只被导入、未列入」漏掉 11 / 14 处类型错误。理赔域新增模块若要进类型门禁，必须显式加进 `pyproject.toml`，并同步更新 `docs/log/step-c0-baseline.md` 的期望数字（走「复核补记」，不改原文）。

## 5. 每一步的文档纪律

开工前请看 `docs/log/hard-rules.md`：**先检索 ≥3 独立来源（URL + 时间 + 用途）→ 再动手 → 四件套文档 → 复跑基线**。
