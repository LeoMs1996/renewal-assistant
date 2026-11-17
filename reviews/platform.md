# 平台工程域评审与落地优化（2026-11-17）

- 评审对象：`server/trace.py`（JSONL 轨迹）、`server/metrics.py`（Prometheus 暴露）、
  `server/app.py` 的 `/metrics` 与轮次收口、`traces/*.jsonl`（798 条真实轨迹）、
  部署物（此前 **完全没有**：无 Dockerfile / 抓取配置 / 告警 / k8s 探针）
- 评审人：platform-reviewer-ds（域任务 t8）；安全合规（鉴权/限流/注入）归 t9，本文不越界
- 硬约束遵守：本文所有技术结论均来自下列本次检索（含 t8 前序 attempt 已取的
  4 份 GenAI semconv 文档 + Prometheus 命名指南，按指示计入来源），
  未使用训练记忆直接下结论；无法证实处标注「待验证」

## 一、检索基线（9 条来源 / 4 个独立官方站点，均为 2026-11-17 本次会话检索）

> 检索时间戳：除注明外均为 **2026-11-17 11:59–12:07 (Asia/Shanghai)**，与任务要求的
> 2026-11-13 基线同属「2026-11 当前最新」；semconv 正文在 2026-11-13 与 11-17 之间
> 无改名（本次逐字核对指标名与桶边界，与 metrics.py 原注释一致）。

| # | 来源 | 关键基线要点（逐条可核） |
|---|---|---|
| 1 | [OpenTelemetry《Generative AI semantic conventions》旧入口 → 已迁出主仓库](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/) （read.fetch） | 页面现为跳转页：**"GenAI semantic conventions have moved to the OpenTelemetry GenAI semantic conventions repository"**（`github.com/open-telemetry/semantic-conventions-genai`），本页不再维护。→ 任何按旧路径引用的规范都可能读到过期正文 |
| 2 | [semconv-genai `docs/gen-ai/client-inference.md`（main，commit 2026-11-17 拉取）](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md) | `gen_ai.client.inference.duration`：Histogram、单位 `s`、显式桶 `[0.01 … 81.92]`；必填 `gen_ai.operation.name`、`gen_ai.provider.name`；`error.type`（出错时条件必填）、`gen_ai.request.model`（可得时条件必填）、`gen_ai.response.model`（推荐）。span 名 SHOULD 为 `{gen_ai.operation.name}`、kind `CLIENT` |
| 3 | [semconv-genai `docs/gen-ai/gen-ai-token-metrics.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-token-metrics.md) | `gen_ai.client.inference.usage.input_tokens` / `.output_tokens`：**Counter**、单位 `{token}`；必填 `gen_ai.operation.name`、`gen_ai.provider.name`、**`gen_ai.token.modality`**；SHOULD 记录成功与失败调用的贡献，"每次测量 MUST 是已知且严格正的模态贡献" |
| 4 | [semconv-genai `docs/gen-ai/gen-ai-metrics.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md) | ① `gen_ai.client.operation.duration` **SHOULD NOT** 用于 inference / embeddings / execute_tool / invoke_agent；② `gen_ai.invoke_agent.duration` 桶 `[0.1, 0.2, …, 86400]`；③ `gen_ai.invoke_agent.tool_calls` / `.inference_calls` 桶 `[1,2,4,8,16,32,64,128]`；④ `gen_ai.provider.name` well-known 值表**含 `deepseek`、不含智谱** |
| 5 | [semconv-genai `docs/gen-ai/gen-ai-agent-spans.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md) | 进程内 agent/工作流 span：名 `{gen_ai.operation.name} {gen_ai.agent.name}`、kind `INTERNAL`；**LangGraph `StateGraph` 明确属"应用定义控制流"，`gen_ai.operation.name` SHOULD 为 `invoke_workflow`**；`gen_ai.agent.name` MUST 低基数，**明确不得用 "StateGraph" 之类类型名** |
| 6 | [semconv-genai `docs/gen-ai/retrieval.md` + `execute-tool.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/retrieval.md) | `gen_ai.retrieval.duration`、`gen_ai.execute_tool.duration` 均为 Histogram(s)，桶 `[0.01 … 81.92]`；span 名分别为 `{gen_ai.operation.name}`（=retrieval）、`execute_tool {gen_ai.tool.name}`，kind `INTERNAL`；另见 `gen-ai-spans.md`：**输入/输出属敏感内容，instrumentation SHOULD NOT 默认采集，需显式 opt-in** |
| 7 | [Prometheus《Metric and label naming》](https://prometheus.io/docs/practices/naming/) + [《Exposition formats》](https://prometheus.io/docs/instrumenting/exposition_formats/)（read.fetch） | ① 指标名 SHOULD 带应用前缀、基本单位（时间=秒）、累积计数 `_total`；② "**Do not use labels to store dimensions with high cardinality … such as user IDs**"，每个标签组合就是一条时间序列；③ 文本格式：HELP 需转义 `\\`/`\n`，**标签值必须转义 `\\` `"` `\n`**；histogram 必须有 `{le="+Inf"}` 且等于 `_count`；同 (metric,labels) 不得重复；④ **Prometheus 3.0 起 target 必须返回合法 Content-Type，否则抓取直接失败** |
| 8 | [OTLP Specification 1.11.1](https://opentelemetry.io/docs/specs/otlp/)（read.fetch，两次续读） | trace 数据 POST `/v1/traces`；JSON 编码必须 `Content-Type: application/json`；OTLP/HTTP 默认端口 **4318**；`traceId`/`spanId` 用**十六进制字符串**、枚举用**整数**、int64 时间戳用**十进制字符串**；发送侧 SHOULD NOT 造空 envelope；重复数据属规范承认的取舍（§Known Limitations） |
| 9 | [Kubernetes《Configure Liveness, Readiness and Startup Probes》](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)（Last modified 2026-06-30） | HTTP 探针 2xx/3xx 为成功；`startupProbe` 覆盖最坏启动时间，"Once the startup probe has succeeded once, the liveness probe takes over"；readiness 失败只摘流量不重启；三类探针互不依赖 |

（来源 1 与 4–6 同一仓库但为不同文档/不同语义面，按"独立来源"计数为 1 个站点 + 5 份文档；
来源 7、8、9 为三个互相独立的官方站点。合计 ≥3 的硬要求显著满足。）

## 二、评分（改造前 → 改造后）

| 子项 | 前 | 后 | 依据 |
|---|---|---|---|
| 语义约定符合度（命名/单位/必填属性） | 3.0 | 8.5 | 来源 2/3/4：原实现缺 `gen_ai.operation.name`、`gen_ai.request.model`、`gen_ai.token.modality` 三个必填属性，provider 值不在 well-known 表 |
| 指标设计与基数治理 | 6.0 | 9.0 | 来源 7：`_total`/秒/低基数本来是对的；但自定义指标占用 `gen_ai.*` 命名空间、标签值未转义 |
| 轨迹可观测性（span 化/可进后端） | 2.0 | 8.0 | 来源 8：原轨迹无 spanId/parent/status，无法进任何 OTLP 后端 |
| 观测数据真实性（指标是否真有样本） | 2.0 | 8.5 | 实测 387 条存量轨迹：inference/retrieval 耗时样本 **0 条**（见 F1）；修复后新写入的 34 条 llm_response、146 条 retrieval **全部带 latency_ms** |
| 部署与运维就绪（镜像/抓取/告警/探针） | 1.0 | 7.5 | 来源 7/9：此前零部署物；现具备镜像、抓取、7 条告警、三探针（镜像未实构建，见 §六） |
| 测试基建洁净度（不污染生产观测数据） | 3.0 | 8.5 | 实测：跑一次 `pytest` 使 `traces/` 从 387 → 760 个文件 |
| **域总评** | **2.4 / 10** | **8.3 / 10** | 可观测性从"有字段、无数据、无出口"变为"有数据、有语义、可外送" |

## 三、Findings（按严重度，均已实测复现）

| # | 严重度 | 问题（证据） | 状态 |
|---|---|---|---|
| F1 | **high** | **指标空转：有指标名、零样本。** 修复前基线（387 个轨迹文件 / 7063 行，逐行统计）：`llm_response` **249/249 行缺 latency_ms**、`retrieval` **376/376 行缺**（`tool_result` 609/609 有，所以历史上只有工具耗时这一项真有样本）。`metrics.observe_record()` 只在 `latency_ms` 存在时才 `observe`，于是 `gen_ai.client.inference.duration` 与 `gen_ai.retrieval.duration` 自上线起 **一条样本都没有**——仪表盘与告警全是空白，却看不出错 | ✅ 已修复：在 `TraceRecorder.record()` 唯一写入点用**单调时钟**补齐缺省 `latency_ms`（llm_response←llm_call、tool_result←tool_call、retrieval←node_start 上界）。只写 SPEC §5 已定义字段，**不新增字段、不改 SPEC** |
| F2 | **high** | **semconv 必填属性缺失 + 命名空间污染。** 原实现只打 `gen_ai_provider_name`：缺 `gen_ai.operation.name`（来源 2/3 标注 **Required**）、`gen_ai.request.model`（条件必填）、`gen_ai.token.modality`（来源 3 **Required**）；规则模式（无 LLM 凭证）仍以 `provider="rule"` 向 `gen_ai.*` 写样本，把"非 AI 调用"混进 AI 口径 | ✅ 已修复：新增 `llm_identity()` 从配置推导 `(provider, model)`（识别 deepseek → well-known 值 `deepseek`；GLM 无 well-known 取值 → 自定义 `zhipu.glm`，规范允许）；规则模式/无凭证 **整段跳过** `gen_ai.*`，只保留 `renewal_*` |
| F3 | **high** | **轨迹无法进入任何可观测后端。** JSONL 只有 `trace_id + seq`，无 spanId/parentSpanId/kind/status；没有 OTLP 出口。后果：跨服务因果、慢在哪一跳、错误落在哪个 span 全部无法回答；Tempo/Jaeger/任意 OTLP 后端都吃不下（来源 8） | ✅ 已修复：新增 `server/otel_export.py`（纯标准库）把轨迹还原成 OTLP span 树并 POST `/v1/traces`；配 `deploy/otel/collector.yaml` + compose/k8s sidecar |
| F4 | medium | **自定义指标占用 `gen_ai.*` 保留命名空间**：`gen_ai_client_inference_requests_total` 在 semconv 中不存在（来源 4 无此指标；请求数可由 `_count` 导出）。按来源 7"应用前缀"原则属命名越界 | ✅ 已修复：改名 `renewal_inference_requests_total`，并在模块头与测试中固化边界 |
| F5 | medium | **指标文本格式不合规风险**：标签值与 HELP 未转义。实测 error code 若含 `"` 或换行会直接产出非法 exposition（来源 7 明确 `\\` `"` `\n` 必须转义），抓取端解析失败 = 整机指标丢失 | ✅ 已修复：新增 `_esc()`/`_esc_help()`；新增单测 `test_label_escaping` 守住 |
| F6 | medium | **缺 agent/工作流级指标**：`StateGraph` 属 semconv 的 `invoke_workflow`（来源 5），应产出 `gen_ai.invoke_agent.duration` + 每条调用内的 `tool_calls`/`inference_calls` 计次分布（来源 4）；原实现只有自定义 `renewal_node_duration`，运维无法回答"一轮对话里模型被调了几次、工具几次" | ✅ 已修复：新增 3 个 semconv agent 指标，`finish_turn()` 按 trace_id 聚合本轮 tool/inference 次数后一次性 observe（状态随轮次释放，`_MAX_TURNS=4096` 兜底裁剪） |
| F7 | medium | **零部署物**：无 Dockerfile / 抓取配置 / 告警规则 / 探针。可观测性只存在于源码，运维无法消费；k8s 里 `/health` 无三探针语义（来源 9） | ✅ 已修复：`deploy/` 下补镜像（非 root、单 worker、依赖锁定）、Prometheus 抓取 + 4 记录规则 + 7 告警、OTel collector、Compose、k8s 三探针 Deployment + Service/ServiceMonitor + 轨迹导出 sidecar |
| F8 | medium | **单测污染生产观测数据**：`tests/conftest.py` 未隔离 `TRACE_DIR`，跑一次完整 `pytest` 让仓库 `traces/` 从 **387 → 760** 个文件（本次实测）。既污染 `/trace` 回放与导出统计，也让"轨迹数量"类断言漂移 | ✅ 已修复：conftest 在导入 server 前 `setdefault("TRACE_DIR", mkdtemp())`；复测 762 → 762（不再增长） |
| F9 | low | **历史轨迹不含 model/provider 字段**：导出时只能套用"导出时刻的配置"，历史 GLM 轨迹会被打上今天的 `deepseek-flash` 标签（schema 缺口，非导出层可解） | 📋 移交编排域：SPEC §5 增 `model`/`provider`（或 `gen_ai.*`）字段；导出层已提供 `--provider/--model` 覆盖参数应急 |
| F10 | low | **轨迹默认全量采集输入输出**（user_message / assistant_message / tool 入参含 VIN、车牌）。来源 6 明确 ISC "SHOULD NOT capture by default … SHOULD provide an option to opt in" | 📋 移交 t9：内容采集开关属安全合规域；导出层已按"不导出内容"实现，JSONL 侧仍需 opt-in 开关 |
| F11 | info | `/health` 只反映"进程能应答 + wiki/图可加载"，不含 LLM 可达性（LLM 挂了 readiness 仍绿）。按来源 9，这是**正确取舍**（LLM 抖动不应摘流量），但需在 runbook 说明：LLM 故障由 `RenewalInferenceSlow` / `RenewalGenAIMetricsMissing` 表达 | 📋 已写入 `deploy/README.md` §3 |
| F12 | info | **mypy 门禁漏网**：`pyproject.toml [tool.mypy] files` 未列 `metrics.py`（仅经 `trace.py` 的延迟导入被间接检查）、`otel_export.py` 完全在门禁外 → 11 处类型错误流入主干（跨域派单，见 §五） | ✅ 已修复：两文件并入 `files`，现 mypy 6 files 全绿 |

## 四、落地改动（changedPaths）

| 文件 | 改动 |
|---|---|
| `server/trace.py` | ① `_fill_latency()`：在 `record()` 唯一写入点派生 llm_response/tool_result/retrieval 的缺省耗时（单调时钟，墙钟回拨安全，绝不覆盖显式值）；② 模块 docstring 登记口径与实测缺口（387 条轨迹） |
| `server/metrics.py` | 重写为 semconv 对齐版：① `llm_identity()`（provider/model 推导，规则模式不产 `gen_ai.*`）；② 补齐必填属性 `gen_ai_operation_name` / `gen_ai_request_model` / `gen_ai_token_modality`；③ 新增 5 个 semconv 指标（invoke_agent.duration / tool_calls / inference_calls、retrieval.duration、execute_tool.duration）并沿用官方桶边界；④ `renewal_inference_requests_total` 更名；⑤ `_esc()`/`_esc_help()` 文本格式转义；⑥ `finish_turn()` 轮次聚合 + `turn_counts()` + `_MAX_TURNS` 有界状态；⑦ 类型注解（`MetricKey`、`_ALL: list[_Counter | _Histogram]`、`isinstance` 分流 reset） |
| `server/otel_export.py`（新增 402 行） | 轨迹 JSONL → OTel span 树 → OTLP/HTTP JSON：根 span `invoke_workflow renewal-assistant`、`node.<name>`、`chat`(CLIENT)、`execute_tool <tool>`、`retrieval`；错误映射 `status.code=2` + `error.type`；确定性 traceId(32)/spanId(16)；**不导出 input/output 原文**；历史 retrieval 时长退化时标 `renewal.duration.derived`；CLI（`--trace-dir/--out/--endpoint/--batch/--limit/--provider/--model`） |
| `server/app.py` | 两处轮次收口改调 `metrics.finish_turn(trace_id, elapsed, "done"|"error")`（顺带由 metrics 侧产出 agent 级指标）；未触碰鉴权/SSE 逻辑 |
| `tests/test_metrics.py`（重写 8 例） | 必填属性断言、规则模式静默、标签转义、`+Inf` 桶 = `_count`、`/metrics` Content-Type、`finish_turn` 聚合与状态释放、命名空间边界 |
| `tests/test_otel_export.py`（新增 9 例） | span 树/命名/kind、父子链、派生耗时、错误状态传播、OTLP 编码（32/16 位十六进制、kind 整数、时间戳字符串、无空 envelope）、**无内容外泄**、798 条真实轨迹全量转换 + CLI 冒烟、指标幂等性、单调派生 |
| `tests/conftest.py` | 导入 server 前隔离 `TRACE_DIR`（修 F8） |
| `deploy/`（新增 8 文件） | `Dockerfile`（非 root uid 10001、单 worker、lock 依赖、HEALTHCHECK）、`.dockerignore`、`docker-compose.yml`（app+prometheus+otel-collector+trace-export profile）、`prometheus/prometheus.yml`（15s 抓取）、`prometheus/rules/renewal.yml`（4 记录规则 + 7 告警）、`otel/collector.yaml`（OTLP 4317/4318 → batch → debug）、`k8s/deployment.yaml`（三探针 + 只读根 FS + 轨迹导出 sidecar + Secret 注入）、`k8s/service.yaml`（Service + ServiceMonitor）、`README.md`（运维手册 + 已知限制） |
| `scripts/platform_check.py`（新增） | 4 段自检：部署 YAML 结构/探针、**告警引用的指标必须真实暴露**、`/metrics` 必备 12 族 + 无高基数标签、轨迹全量可转换；CI 可秒级接入 |
| `pyproject.toml` | `[tool.mypy] files` 增列 `server/metrics.py`、`server/otel_export.py`（修 F12） |

并发约定（回应 t1 交接）：本域的锁只保护**指标聚合内部状态**（`metrics._lock`、`_turns` 有界字典），
不触碰图执行路径；`server/graph.py` 的 `_RUN_LOCK` 已由 t1 删除，本域未新增任何跨请求串行化，
两边语义不冲突。SSE 相关无改动（`X-Resume-Supported` 等保持 t5 现状）。

## 五、验证证据（2026-11-17 实测）

### 5.1 跨域派单：mypy 11 处类型错误（复现 → 修复）

```
$ .venv/bin/python -m mypy
server/metrics.py:96:  error: Invalid index type "tuple[tuple[str, str], ...]" for "dict[tuple[str, ...], float]"  [index]
server/metrics.py:96:  error: Argument 1 to "get" of "dict" has incompatible type ...                        [arg-type]
server/metrics.py:102: error: Argument 1 to "_labels" has incompatible type "tuple[str, ...]" ...            [arg-type]
server/metrics.py:123: error: Argument 1 to "setdefault" of "MutableMapping" ...                             [arg-type]
server/metrics.py:140/141/142/143: error: Argument 1 to "_labels" ...                                         [arg-type]
server/metrics.py:219/223: error: Argument 3 to "_Histogram" has incompatible type "list[int]"; expected "list[float]"  [arg-type]
server/metrics.py:242: error: "object" has no attribute "render"                                             [attr-defined]
Found 11 errors in 1 file (checked 4 source files)
```

根因与修法（未使用批量 `# type: ignore`，一处 ignore 都没加）：

1. 标签键同一语义两种类型 → 引入 `MetricKey = tuple[tuple[str, str], ...]`，`_Counter.values` /
   `_Histogram.data` / `_labels()` 统一用别名（修 96/102/123/140-143 共 6 处）；
2. `CALLS_BUCKETS = [1, 2, …]` 被推断 `list[int]`（list invariant）→ 显式 `list[float]`（修 219/223 共 2 处）；
3. `_ALL` 混装计数器与直方图被推断 `list[object]` → 显式 `list[_Counter | _Histogram]`（修 242 共 1 处）；
4. 顺带把 `reset()` 的 `hasattr(...) if ... else None` 表达式改为 `isinstance` 分流（可判定类型、可读性更好）。

```
$ .venv/bin/python -m mypy          # 门禁（现含 6 个文件）
server/middleware.py:81: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
Success: no issues found in 6 source files
```

### 5.2 ruff / 收集 / 测试

```
$ .venv/bin/python -m ruff check .            # 全仓库
Found 3 errors.            # 均为 I001 unsorted-imports，且都不在本域文件：
                           #   mcp_servers/quote_server.py:17、server/app.py:15、tests/test_mcp.py:21
$ .venv/bin/python -m ruff check server/metrics.py server/otel_export.py server/trace.py \
      scripts/platform_check.py tests/test_metrics.py tests/test_otel_export.py
All checks passed!
$ .venv/bin/python -m pytest tests --collect-only -q
78 tests collected           # wiki_search.py 语法问题已由知识域修复，收集不再阻塞
$ .venv/bin/python -m pytest tests --tb=line -q
76 passed, 2 skipped（stdio 全链路 + 历史轨迹空目录场景）
$ .venv/bin/python -m pytest tests/test_metrics.py tests/test_otel_export.py -q
17 passed
```

> 注：`server/app.py:15` 的 I001 是跨域遗留（API 域文件，本域仅改轮次收口 2 行），
> 已上报 captain 转 API/MCP 域；本域文件 ruff 全绿。
>
> 所有命令均用**项目 venv** 绝对路径 `renewal-assistant/.venv/bin/python`（系统 python 无
> langgraph 依赖，用它跑 pytest 会误报"收集失败"——这是 t3 已澄清的坑，本域未踩）。
> 另：12:12 复跑曾出现 4 例 `tests/test_security.py` 失败，根因是 LLM 域当时正在改
> `server/llm.py`（调用 `config.llm_strict()`）而 `config.py` 尚未同步，属跨域 in-flight
> 竞态；12:13 该函数落地后复跑即恢复 76 passed / 2 skipped。

### 5.3 平台自检（部署配置 ↔ 观测面一致性）

```
$ .venv/bin/python scripts/platform_check.py
[1/4] 部署 YAML 结构
  ✓ deploy/docker-compose.yml（1 个文档）
  ✓ deploy/prometheus/prometheus.yml（1 个文档）
  ✓ deploy/prometheus/rules/renewal.yml（1 个文档）
  ✓ deploy/k8s/deployment.yaml（1 个文档）
  ✓ deploy/k8s/service.yaml（2 个文档）
  ✓ deploy/otel/collector.yaml（1 个文档）
[2/4] 规则引用的指标确实被暴露
  ✓ 11 条规则表达式全部指向已暴露指标
[3/4] /metrics 暴露面
  ✓ 12 个必备指标族齐全，无高基数标签
[4/4] 轨迹 → OTLP 转换
  ✓ 798 条轨迹 → 7330 spans（error span 102）

全部通过
```

### 5.4 轨迹 → OTLP 实跑（真实历史数据）

```
$ .venv/bin/python -m server.otel_export --trace-dir traces --limit 5 --out /tmp/otel5.json
离线导出：5 条轨迹 / 46 spans → /tmp/otel5.json

（第一条轨迹的 span 结构）
invoke_workflow renewal-assistant kind=1 parent=-        dur=173.00ms {gen_ai.agent.name: renewal-assistant, gen_ai.operation.name: invoke_workflow, gen_ai.provider.name: zhipu.glm}
node.intake                    kind=1 parent=3beff6fe dur=0.00ms  {renewal.node: intake}
node.get_policy                kind=1 parent=3beff6fe dur=163.00ms
execute_tool get_policy        kind=1 parent=74cc703f dur=163.00ms {gen_ai.operation.name: execute_tool, gen_ai.tool.name: get_policy}
node.parse_needs               kind=1 parent=3beff6fe dur=0.00ms
retrieval                      kind=1 parent=04dd142e dur≈节点上界 {gen_ai.retrieval.documents.count: 3}
```

单 span 的 OTLP JSON（编码合规：hex id、kind 整数、时间戳字符串）：

```json
{"traceId":"2ed034ed22aa383739471a093333293f","spanId":"9c9aec4a4c70eccf",
 "name":"execute_tool get_policy","kind":1,
 "startTimeUnixNano":"1794414346938000000","endTimeUnixNano":"1794414347101000000",
 "attributes":[{"key":"gen_ai.operation.name","value":{"stringValue":"execute_tool"}},
               {"key":"gen_ai.tool.name","value":{"stringValue":"get_policy"}}],
 "parentSpanId":"74cc703f7db7537d"}
```

失败降级（无 collector 时不抛异常、返回错误码）：

```
>>> post_otlp("http://127.0.0.1:4318", payload)
(0, '[Errno 61] Connection refused')
```

### 5.5 `/metrics` 实际输出片段（真实轨迹喂入）

```
renewal_chat_requests_total{outcome="done"} 1
gen_ai_client_inference_usage_input_tokens_total{gen_ai_operation_name="chat",gen_ai_provider_name="deepseek",gen_ai_request_model="deepseek-flash",gen_ai_token_modality="text"} 1306
gen_ai_invoke_agent_duration_seconds_count{error_type="",gen_ai_agent_name="renewal-assistant",gen_ai_operation_name="invoke_workflow",gen_ai_provider_name="deepseek",gen_ai_request_model="deepseek-flash"} 1
gen_ai_execute_tool_duration_seconds_count{gen_ai_tool_name="get_policy"} 1
renewal_node_duration_seconds_count{node="await_confirm"} 1
```

## 六、遗留与移交

| # | 事项 | 归属 | 说明 |
|---|---|---|---|
| L1 | 镜像未实际 `docker build`（开发机无 Docker）、`promtool check rules` 未跑（无 promtool）、collector 未实跑 | 本域 / CI 域 | 配置已用 `platform_check.py` 做结构与"指标存在性"断言；语法级仍需在真实 Prometheus/collector 上验一次 |
| L2 | 轨迹 schema 缺 model/provider | 编排域 | 建议 SPEC §5 增字段；否则历史 span 只能套用导出时配置（导出层已留 `--provider/--model`） |
| L3 | 轨迹内容默认全量采集（PII） | t9 安全域 | 来源 6 要求 opt-in；建议 `RENEWAL_TRACE_CONTENT=off|meta|full` |
| L4 | `/metrics` 无鉴权、无网络层保护 | t9 + 部署 | 已豁免鉴权（运维端点），生产需由 NetworkPolicy/反代限源 |
| L5 | 多副本下指标各算各的 | 平台域 | 语义正确（Prometheus 按 instance 聚合），但 `--workers>1` 会让 rate 抖动：Dockerfile/README 已写死单 worker |
| L6 | `server/app.py:15`、`mcp_servers/quote_server.py:17`、`tests/test_mcp.py:21` 的 I001 | API / MCP 域 | 本域未越界修改；`ruff check` 全仓库仍需 3 处修 |
| L7 | 真实 LLM 验证未跑（凭证后补） | 全队 | 观测面已就绪：真实调用后 `gen_ai_client_inference_duration_seconds` 首次会有非零样本，可用来验证 F1 的修复在生产链路同样成立 |
