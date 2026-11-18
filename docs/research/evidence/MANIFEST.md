# MANIFEST — docs/research/evidence

> 本文件是检索留证的**权威清单**。html 渲染快照不入库（见 .gitignore 说明），
> 靠本清单的 `sha256 + URL + 抓取时间` 复现"当时读到的原文"。
>
> 规范：新增证据必须在此登记一行；URL 未知的标 `待补`，由抓取者补齐。
> 复用说明：`mdx/` 下是官方文档**源文件**（比 html 更可审阅），优先引用它们。

## 1. 官方文档源文件（mdx/，入库）

| 文件 | 抓取时间 | 大小 | sha256(前16) | 来源 URL | 用途 |
|---|---|---|---|---|---|
| `mdx/da-backends.mdx` | 2026-11-17 23:19 | 52K | `8640a69a42d76208` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/backends.mdx | 文件后端类型 |
| `mdx/da-comparison.mdx` | 2026-11-17 23:19 | 12K | `43dbc16ad6d38a05` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/comparison.mdx | 与 Claude SDK 对比 |
| `mdx/da-context-engineering.mdx` | 2026-11-17 23:19 | 28K | `9222a950b624f2b1` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/context-engineering.mdx | 20k/85% 压缩 |
| `mdx/da-customization.mdx` | 2026-11-17 23:19 | 48K | `73bf69fbbcd3aa6e` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/customization.mdx | middleware 定制 |
| `mdx/da-fault-tolerance.mdx` | 2026-11-17 23:19 | 16K | `393160c6010c48cf` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/fault-tolerance.mdx | 容错与重试 |
| `mdx/da-going-to-production.mdx` | 2026-11-17 23:19 | 48K | `24a6a63a472070b6` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/going-to-production.mdx | 生产期 durability |
| `mdx/da-human-in-the-loop.mdx` | 2026-11-17 23:19 | 32K | `fade9f5dfb881ad8` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/human-in-the-loop.mdx | interrupt_on 审批 |
| `mdx/da-models.mdx` | 2026-11-17 23:19 | 12K | `edf6319febae916b` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/models.mdx | 模型要求 |
| `mdx/da-overview.mdx` | 2026-11-17 23:19 | 28K | `3c055f4c7f7f1aaa` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/overview.mdx | deep agent 定位 |
| `mdx/da-permissions.mdx` | 2026-11-17 23:19 | 12K | `f9a4c558e413de03` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/permissions.mdx | 文件权限规则 |
| `mdx/da-subagents.mdx` | 2026-11-17 23:19 | 48K | `4e3188a3926f8744` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/deepagents/subagents.mdx | task 工具委派 |
| `mdx/lg-checkpointers.mdx` | 2026-11-17 23:19 | 60K | `0808ee739f515565` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/checkpointers.mdx | durability 三档 |
| `mdx/lg-fault-tolerance.mdx` | 2026-11-17 23:19 | 52K | `551fc4c9462c41af` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/fault-tolerance.mdx | retry 与幂等键 |
| `mdx/lg-graph-api-control-flow.mdx` | 2026-11-17 23:19 | 36K | `43b071c7c31fdbdb` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/graph-api-control-flow.mdx | recursion 上限 |
| `mdx/lg-graph-api-send-command.mdx` | 2026-11-17 23:19 | 16K | `5dbab833fc84165b` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/graph-api-send-command.mdx | Command 与 Send |
| `mdx/lg-graph-api.mdx` | 2026-11-17 23:19 | 36K | `2b01961392024053` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/graph-api.mdx | recursion 与单元选择 |
| `mdx/lg-interrupts.mdx` | 2026-11-17 23:19 | 64K | `29451d6fc51a38b3` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/interrupts.mdx | interrupt 语义 |
| `mdx/lg-persistence.mdx` | 2026-11-17 23:19 | 8.0K | `0d33a9d4c828ecfe` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/persistence.mdx | checkpointer 概览 |
| `mdx/lg-use-subgraphs.mdx` | 2026-11-17 23:19 | 56K | `4f8d9201d0d3d380` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/use-subgraphs.mdx | 子图 checkpointer |
| `mdx/lg-workflows-agents.mdx` | 2026-11-17 23:19 | 44K | `4b804859e2bf77e9` | https://raw.githubusercontent.com/langchain-ai/docs/main/src/oss/langgraph/workflows-agents.mdx | workflow vs agent |

## 2. 元数据与本地实测（入库）

| 文件 | 抓取时间 | 大小 | sha256(前16) | 来源 URL | 用途 |
|---|---|---|---|---|---|
| `deepagents-graph.py` | 2026-11-17 23:20 | 52K | `d266ce645cbc7738` | https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/deepagents/graph.py | agent 工厂签名 |
| `probe_langgraph_api.py` | 2026-11-17 23:20 | 8.0K | `d54b08d0f28307d0` | 本地实测（无外部来源） | 实测探针脚本 |
| `probe-durability.txt` | 2026-11-17 23:54 | 4.0K | `c017caa567c4ef71` | 本地实测（无外部来源） | durability 实测 |
| `probe-introspect.txt` | 2026-11-17 23:20 | 8.0K | `0c60d086c295aaea` | 本地实测（无外部来源） | API 签名实测 |
| `probe-phase1.txt` | 2026-11-17 23:20 | 4.0K | `40346a2996c4f0dd` | 本地实测（无外部来源） | interrupt 暂停 |
| `probe-phase2.txt` | 2026-11-17 23:20 | 4.0K | `66a6a47e7bcdbc81` | 本地实测（无外部来源） | 跨进程恢复 |
| `probe-recursion.txt` | 2026-11-17 23:54 | 4.0K | `865c2c0c0012062b` | 本地实测（无外部来源） | recursion 实测 |
| `pypi-deepagents-0.7.39.json` | 2026-11-17 23:19 | 12K | `f382fabd056f1d8e` | https://pypi.org/pypi/deepagents/0.7.39/json | 版本与依赖 |
| `pypi-langchain-1.5.0.json` | 2026-11-18 00:26 | 8.0K | `1e9c76c0bf7c4476` | https://pypi.org/pypi/langchain/1.5.0/json | langgraph 约束 |
| `pypi-langgraph-1.2.20.json` | 2026-11-18 00:26 | 8.0K | `ba019c1b4311f50d` | https://pypi.org/pypi/langgraph/1.2.20/json | 本机版本依赖 |

## 3. HTML 渲染快照（不入库，仅登记指纹）

| 文件 | 抓取时间 | 大小 | sha256(前16) | 备注 |
|---|---|---|---|---|
| `add-human-in-the-loop.html` | 2026-11-17 23:18 | 412K | `32262cf4a2fc9e14` | 渲染快照，对应 mdx/ 同名源文件 |
| `durable-execution.html` | 2026-11-17 23:18 | 460K | `232eb0053859a134` | 渲染快照，对应 mdx/ 同名源文件 |
| `durable-execution.html.txt` | 2026-11-17 23:19 | 300K | `38df759781eccfdc` | 渲染快照，对应 mdx/ 同名源文件 |
| `graph-api.html` | 2026-11-17 23:18 | 712K | `d02533bcbb96a408` | 渲染快照，对应 mdx/ 同名源文件 |
| `graph-api.html.txt` | 2026-11-17 23:19 | 440K | `d941a1d536db03d9` | 渲染快照，对应 mdx/ 同名源文件 |
| `lg-interrupts.html` | 2026-11-17 23:17 | 1.2M | `9fd56d28c8c88f51` | 渲染快照，对应 mdx/ 同名源文件 |
| `overview.html` | 2026-11-17 23:18 | 788K | `989758890304600c` | 渲染快照，对应 mdx/ 同名源文件 |
| `overview.html.txt` | 2026-11-17 23:19 | 476K | `80c7d5a22b24585c` | 渲染快照，对应 mdx/ 同名源文件 |
| `persistence.html` | 2026-11-17 23:18 | 448K | `232eb0053859a134` | 渲染快照，对应 mdx/ 同名源文件 |
| `use-subgraphs.html` | 2026-11-17 23:18 | 2.0M | `6c287288b31902e7` | 渲染快照，对应 mdx/ 同名源文件 |

## 4. 入库策略与依据

- **入库**：mdx 源文档、pypi json、probe 脚本与输出、本 MANIFEST（文本，可审阅、可 diff）
- **不入库**：`*.html` / `*.html.txt`（渲染副本，7.1M），规则见 `.gitignore` 第 65-66 行
- **依据**：[GitHub 大文件规则](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)（>50 MiB 告警、>100 MiB 拒收、建议仓库 <1 GB）
- **复现**：按 URL 重抓后比对 sha256 前 16 位；若页面改版导致不一致，须在同一行追加「改版复核」备注而非覆盖旧值

## 5. 已知陈旧引用（有意不修）

| 文件 | 陈旧内容 | 为什么不改 |
|---|---|---|
| `probe_langgraph_api.py` | docstring 第 4–6 行的调用示例仍写 `insurance-agent/docs/research/evidence/...`（该目录已按 D-01 删除） | 本文件 sha256 已登记在 §2，**改一个字节就会使本节与磁盘不一致**，从而破坏"证据可复现"链。一个过时的使用示例的价值远低于证据链的完整性，故保留原样。读者若需运行，按 §2 登记的路径改为 `renewal-assistant/docs/research/evidence/probe_langgraph_api.py` 即可 |

> 记录于 2026-11-18；t28 已将该遗留项登在 `docs/log/step-r2.md` 的「勘误记录·遗留」节。
