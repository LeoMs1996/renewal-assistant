# 作业提交说明 — renewal-assistant

> 本文件用于作业提交时指明仓库地址与交付物位置。所有数字均为 2026-11-24 实测。

## 1. 仓库地址

| 项 | 值 |
|---|---|
| **仓库地址（提交用）** | **https://github.com/LeoMs1996/renewal-assistant** |
| 克隆地址 | `git clone https://github.com/LeoMs1996/renewal-assistant.git` |
| 可见性 | **public**（无需登录即可查看） |
| 默认分支 | `master` |
| 最新提交 | [`43035c5`](https://github.com/LeoMs1996/renewal-assistant/commit/43035c5)（2026-11-24 23:44:34 +0800） |
| 版本库规模 | 413 个文件（不含被 `.gitignore` 排除的本地文件） |

## 2. 项目简介

**车险续保助手**：FastAPI + LangGraph 状态机（11 节点）的对话式续保顾问，通过 MCP 报价服务生成**模拟报价**，结合 BM25 + RRF 的 LLM-Wiki 条款库输出带条款依据的方案比较，经车主确认后完成投保；另含独立的**理赔域**（`claims/`，LangGraph 原生 `interrupt()` + Deep Agents 材料分析层）。契约以 [`SPEC.md`](SPEC.md)（v1.0.6）为唯一事实源。

## 3. 作业交付物（仓库内路径）

| # | 交付物 | 路径 | 说明 |
|---|---|---|---|
| T1 | 验收验证手册 | [`docs/验收验证/验收验证手册.md`](https://github.com/LeoMs1996/renewal-assistant/blob/master/docs/%E9%AA%8C%E6%94%B6%E9%AA%8C%E8%AF%81/%E9%AA%8C%E6%94%B6%E9%AA%8C%E8%AF%81%E6%89%8B%E5%86%8C.md) | 22 条记录（操作/截图/预期/实际/结论/轨迹），28 张截图在 `docs/验收验证/screenshots/`，原始记录在 `docs/验收验证/_batch/` |
| T2 | 架构与 Harness 设计 | [`docs/架构与Harness设计.html`](https://github.com/LeoMs1996/renewal-assistant/blob/master/docs/%E6%9E%B6%E6%9E%84%E4%B8%8EHarness%E8%AE%BE%E8%AE%A1.html) | 单文件 HTML、0 外链，每个论断附 `file:line` 证据，未核实项保留「待核」标记 |
| T3 | 实现过程复盘 | [`docs/实现过程复盘.md`](https://github.com/LeoMs1996/renewal-assistant/blob/master/docs/%E5%AE%9E%E7%8E%B0%E8%BF%87%E7%A8%8B%E5%A4%8D%E7%9B%98.md) | 9 章：时间线、两轮评估、LLM-Wiki 实现过程、理赔 + Deep Agents、踩坑表、遗留、复跑命令、决策索引 |
| T4 | 收口 | [`SPEC.md §8`](SPEC.md) · [`docs/PR-BODY.md`](docs/PR-BODY.md) | SPEC 追加「v1.0.6（不升版）」验收登记；PR 正文含证据、发现与非目标 |

浏览器打开 [**docs/ 目录**](https://github.com/LeoMs1996/renewal-assistant/tree/master/docs) 可看到全部文档；架构 HTML 在 GitHub 上会以源码显示，请下载后用浏览器打开。

## 4. 验收结果摘要（2026-11-24）

| 项 | 结果 |
|---|---|
| 全量评测 `eval/run.py` | **19/19 PASS，hard 失败 0**（35.4s） |
| `pytest tests/` / `pytest claims/tests/` | 148 passed, 2 skipped / 86 passed |
| 理赔端到端门禁 `claims/demo_claim.py` | 8 项 PASS 8 |
| 手册 22 条记录 | FAIL 0；PARTIAL 1（对话记忆问答不支持，属产品边界） |

已如实登记的发现（详见手册 §3）：AC-11 回复事实错误（断言未覆盖）、报价有效性双真源、理赔 Deep Agents 实际降级为规则回退。

## 5. 本地运行（三步）

```bash
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt   # 续保域
cp .env.example .env                                                       # 填入模型凭证（不入库）
RENEWAL_EXPOSE_DOCS=1 .venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000 ；全量回归：`.venv/bin/python -m eval.run`。理赔域需独立的 `.venv-claims`（见 [`claims/README.md`](claims/README.md)）。

## 6. 未纳入版本库的内容（刻意排除）

| 内容 | 原因 |
|---|---|
| `.env`（含模型密钥） | 敏感凭证，仅提交模板 `.env.example` |
| `.venv/`、`.venv-claims/` | 可按第 5 节重建（约 580 MB） |
| `traces/`、`traces-claims/` | 运行时轨迹与会话（约 139 MB），含合成车主数据 |
| `data/ins-mmbench/raw/` | INS-MMBench 数据集原始文件（约 33 MB），脚本 `data/ins-mmbench/scripts/fetch_subset.py` 可重新拉取 |
| `deliverables/`、`*.zip` | 打包产物，可由源文件重新生成 |
