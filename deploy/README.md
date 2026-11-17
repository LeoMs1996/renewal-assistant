# 部署与可观测性（平台工程域 t8，2026-11-17）

本目录把「观测面」从源码里搬出来，变成运维能消费的东西：镜像、抓取配置、告警、
探针、OTLP 链路。设计依据逐条见 `reviews/platform.md` §一（检索时间 2026-11-17）。

```
deploy/
├── Dockerfile                 # 非 root、单 worker、依赖锁定
├── .dockerignore
├── docker-compose.yml         # app + prometheus + otel-collector（演示用）
├── prometheus/prometheus.yml  # 抓取配置（15s，/metrics）
├── prometheus/rules/renewal.yml # 4 条记录规则 + 7 条告警
├── otel/collector.yaml        # OTLP receiver(4317/4318) → batch → debug
└── k8s/deployment.yaml        # 三探针 + 只读根文件系统 + 轨迹导出 sidecar
    k8s/service.yaml           # Service + ServiceMonitor
```

## 1. 本地一键起（演示/联调）

```bash
docker compose -f deploy/docker-compose.yml up -d --build
curl -s localhost:8000/metrics | head -20      # Prometheus 文本格式
open http://localhost:9090/targets             # renewal-assistant 应为 UP
open http://localhost:9090/alerts
# 把已有轨迹一次性推成 OTel span（debug exporter 打到 collector 日志）
docker compose -f deploy/docker-compose.yml run --rm trace-export
```

无 Docker 环境时（当前开发机就没装）可以只跑离线链路，等价性由
`scripts/platform_check.py` 覆盖：

```bash
.venv/bin/python scripts/platform_check.py     # YAML + 规则 + /metrics + 轨迹转换
.venv/bin/python -m server.otel_export --trace-dir traces --out /tmp/spans.json
```

## 2. 指标口径（谁在暴露什么）

`GET /metrics`，`text/plain; version=0.0.4`，共 14 个指标族，分两类命名空间：

| 类别 | 指标 | 说明 |
|---|---|---|
| semconv（GenAI） | `gen_ai_client_inference_duration_seconds` | OTel `gen_ai.client.inference.duration`，桶 0.01…81.92s |
| | `gen_ai_client_inference_usage_input_tokens_total` / `..._output_tokens_total` | usage 计数器，带 `gen_ai_token_modality="text"` |
| | `gen_ai_invoke_agent_duration_seconds` | `gen_ai.invoke_agent.duration`，桶 0.1…86400s，`gen_ai_operation_name="invoke_workflow"` |
| | `gen_ai_invoke_agent_tool_calls` / `..._inference_calls` | 单轮调用内计次分布，桶 1…128 |
| | `gen_ai_retrieval_duration_seconds` | 检索耗时 |
| | `gen_ai_execute_tool_duration_seconds` | 工具耗时（`gen_ai_tool_name`） |
| 应用（renewal_） | `renewal_chat_requests_total` / `renewal_chat_duration_seconds` | 轮次 RED |
| | `renewal_node_duration_seconds` | 图节点耗时（10 个节点） |
| | `renewal_tool_calls_total` / `renewal_errors_total` / `renewal_inference_requests_total` | 计数 |

规则（Prometheus 官方 naming 指南）：

- **时间一律秒**、累积计数一律 `_total`、指标名带前缀；
- **标签只放低基数维度**：node / outcome / code / provider / model / tool name；
  `trace_id`、`session_id`、`owner_id` 一律不进标签（有单测守）；
- `gen_ai.*` 是语义约定保留命名空间：semconv 没有的指标（如"推理请求数"）改用
  `renewal_*` 前缀。规则模式（无 LLM 凭证）**不产出** `gen_ai.*`，避免把规则应答
  混进 AI 口径。

## 3. 告警（`prometheus/rules/renewal.yml`）

| 告警 | 触发 | 严重度 |
|---|---|---|
| `RenewalInstanceDown` | `up{job=...}==0` 持续 2m | critical |
| `RenewalHighChatErrorRatio` | /chat 错误率 >5%（5m） | critical |
| `RenewalNoTraffic` | 有进程但 10m 无轮次收口 | warning |
| `RenewalInferenceSlow` | 推理 p95 >10s（10m） | warning |
| `RenewalChatSlow` | 轮次 p95 >30s（10m） | warning |
| `RenewalNodeSlow` | 某节点 p95 >2s（10m） | warning |
| `RenewalGenAIMetricsMissing` | 有推理但缺 `gen_ai.*`（provider/model 推导失败） | warning |

记录规则产出 `job:renewal_chat_error_ratio:rate5m` 等 4 条，告警与仪表盘复用同一口径。

## 4. 轨迹 → OTel（`server/otel_export.py`）

```
traces/*.jsonl ──(server/otel_export.py)──> OTLP/HTTP JSON ──> collector:4318 ──> 后端
```

- 一轮对话 = 一个 trace = 根 span `invoke_workflow renewal-assistant`；
  节点 → `node.<name>`，推理 → `chat`(CLIENT)，工具 → `execute_tool <tool>`，
  检索 → `retrieval`；错误落 `status.code=2` + `error.type`。
- `traceId`/`spanId` 由 trace_id/seq 确定性派生（同一轨迹重复导出 id 不变）。
- **不导出 input/output 原文**（semconv：敏感内容 SHOULD NOT 默认采集）；
  只留节点名、文档数、token 数、错误码。
- 历史轨迹没有 `latency_ms` 的 retrieval 会退化为「节点上界」，并在 span 上标
  `renewal.duration.derived="node_start"`。

CLI：

```bash
python -m server.otel_export --trace-dir traces --out spans.json         # 离线
python -m server.otel_export --trace-dir traces --endpoint http://host:4318 --batch 50
```

## 5. Kubernetes

- 三探针都打 `/health`：`startupProbe` 2s×30（60s 冷启动预算）、`readinessProbe` 5s、
  `livenessProbe` 20s；依据见 `k8s/deployment.yaml` 头部注释。
- `readOnlyRootFilesystem: true` + `emptyDir` 挂 `/app/traces`（轨迹必须可写）。
- **扩容单位是 Pod 副本，不是 `--workers`**：指标是进程内聚合，多 worker 会让
  `rate()` 随命中率抖动。副本数 >1 时 SSE 会话粘性交给上游 LB。
- 轨迹出集群靠 `trace-export` sidecar（共享同一 emptyDir）；要长期留存就把卷换成
  PVC（RWX 或每 Pod 独立 PVC + 导出），方案见 `service.yaml` 注释。
- 密钥走 Secret（`RENEWAL_API_KEYS` / `ANTHROPIC_*` / `MODEL_NAME`），镜像里没有 `.env`。

## 6. 安全运行时配置（安全域 t9，2026-11-17）

完整基准与差距分析见 `reviews/security.md`；这里只给运维动作。

### 6.1 鉴权

| 变量 | 默认 | 说明 |
|---|---|---|
| `RENEWAL_API_KEYS` | 空（**演示模式**） | `key:owner_id` 逗号分隔；**空 = 匿名放行**（响应头 `X-Auth-Mode: demo`，stderr 打一次 `auth_demo_mode` 告警）。生产必须配 |
| `RENEWAL_EXPOSE_DOCS` | `0` | 非演示模式下 `/docs` `/redoc` `/openapi.json` 需 `X-API-Key`（OWASP API8:2023）；本地看文档置 `1` |

### 6.2 限流：维度与放宽方式

**维度选择（为何不是“按会话”或“按 key”）**：

| 维度 | 是否采用 | 理由 |
|---|---|---|
| 按 IP（1 分钟滑动窗口） | ✅ 主维度 | 鉴权前就能判定，最便宜、最先拒（OWASP DoS Cheat Sheet：cheap validation first）；攻击者拿不到 key 也受限 |
| 按 endpoint（`/chat` 独立桶） | ✅ 叠加 | `/chat` 触发 LLM 推理与轨迹写入，单位成本高出两个数量级；独立桶避免静态轮询把会话预算吃光（Denial of Wallet，LLM10:2025） |
| 按会话（session_id） | ❌ 不用 | `session_id` 由客户端自报，可任意伪造 → 限流形同虚设 |
| 按 API-Key / owner | ⏳ 待做 | 语义最准（一人一预算），但需要把限流器挪到鉴权之后（当前顺序是“便宜的先拒”）；见 `reviews/security.md` §6 遗留 L1 |

| 变量 | 默认 | 说明 |
|---|---|---|
| `RENEWAL_RATE_LIMIT_PER_MIN` | `60` | 通用（除 `/chat` 外全部端点）每 IP 每分钟 |
| `RENEWAL_CHAT_RATE_LIMIT_PER_MIN` | `60` | `/chat` 独立桶。默认与通用值一致：独立桶已足够隔离，再压低会误伤合法批量（评测回归 60 秒内连发 19 条） |
| `RENEWAL_RATE_LIMIT_DISABLED` | `0` | `1` = **完全关闭限流**（压测/全量回归）。启动后首个请求会打一行 `rate_limit_disabled` 告警，便于审计 |

超限响应固定为 **429 + `Retry-After`（秒）+ `{"error":{"code":"RATE_LIMITED"}}`**，不静默丢请求、不断连接。

**批量/评测/压测三种安全做法（按推荐度排序）**：

```bash
# ① 推荐：把批量任务与生产实例隔离——独立进程 + 独立 TRACE_DIR + 放开阈值
TRACE_DIR=$(mktemp -d) RENEWAL_RATE_LIMIT_PER_MIN=10000 \
  RENEWAL_CHAT_RATE_LIMIT_PER_MIN=10000 uvicorn server.app:app --port 8123

# ② 或：显式关闭闸门（会在日志留痕，不会被误认为“限流开着”）
RENEWAL_RATE_LIMIT_DISABLED=1 uvicorn server.app:app --port 8123

# ③ 不推荐：直接调大阈值后忘了改回——审计看不出限流已失效，故本服务提供①②
```

**多副本部署**：限流是进程内内存实现（单进程语义准确）；副本数 >1 时每个副本各自计数，等效配额会被放大 N 倍，需要换 Redis/网关侧限流（遗留 L2）。

### 6.3 数据面

| 项 | 口径 |
|---|---|
| 轨迹/会话文件权限 | `0600`（含 PII 的运行态与观测面数据） |
| 轨迹内容 | 写端 + 读端双重脱敏（身份证/手机号/车牌/VIN/邮箱保形掩码，车主姓名 `***`，`owner_id` 保留供 BOLA 校验） |
| `RENEWAL_TRACE_PII=keep` | 关掉脱敏，**仅本机调试**；生产禁开 |
| 响应缓存 | `/policy` `/trace` `/chat` `/confirm` 均 `Cache-Control: no-store` |
| 存量清理 | `python scripts/trace_purge_pii.py --apply`（已对 967 个历史文件执行过，再跑为幂等空操作） |

### 6.4 自检

```bash
python scripts/security_check.py            # 凭证/忽略规则/轨迹PII/CSP/脱敏，CI 门禁
python scripts/security_check.py --browser  # 追加真实浏览器 CSP+SSE 验证（需本机 Chrome）
```

## 7. 已知限制 / 未验证项

1. **镜像未实际构建**：开发机无 Docker，`docker build` 未跑过；Dockerfile 语法与
   `.dockerignore` 已人工核对，首次上线请在 CI 里补 build/push 环节。
2. **`promtool check rules` 未执行**（本机无 promtool）：PromQL 以
   `scripts/platform_check.py` 的"指标是否被暴露"断言替代，语法层面仍需在
   Prometheus 侧 `--web.enable-lifecycle` 热加载验证一次。
3. **collector 未实跑**：`otel/collector.yaml` 按 OTLP receiver 文档编写，
   `debug` exporter 无需后端即可验证链路；真实后端（Tempo/Jaeger）配置已留注释。
4. **重复导出**：sidecar 每 120s 全量重发，同一 spanId 会重复到达后端
   （OTLP 规范承认该取舍，见 §Known Limitations/Duplicate Data），后端按 spanId 去重。
5. **历史轨迹的 model/provider 标签**取自导出时的进程配置，不代表当时的模型
   （轨迹 schema 无该字段）——修复点在编排域，见 `reviews/platform.md` §六。
