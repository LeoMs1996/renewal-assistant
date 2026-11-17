"""Prometheus 指标（零依赖文本暴露）+ OTel GenAI 语义约定。

依据（2026-11-17 检索，逐条 URL + 时间戳见 reviews/platform.md §一）：
- GenAI 语义约定已迁出 OTel 主仓库，现行正文在
  github.com/open-telemetry/semantic-conventions-genai（opentelemetry.io 旧页仅剩跳转）：
  * docs/gen-ai/gen-ai-metrics.md：`gen_ai.client.operation.duration` 明确
    **SHOULD NOT** 用于 inference / embeddings / execute_tool / invoke_agent，
    inference 用 `gen_ai.client.inference.duration`；agent/工作流入口调用用
    `gen_ai.invoke_agent.duration`（桶 0.1…86400）+ `gen_ai.invoke_agent.tool_calls`
    / `.inference_calls`（桶 1…128，单位 {tool_call}/{inference_call}）。
  * docs/gen-ai/client-inference.md：`gen_ai.client.inference.duration` 为 Histogram(s)，
    显式桶 0.01…81.92，必填 `gen_ai.operation.name`、`gen_ai.provider.name`，
    条件必填 `error.type` / `gen_ai.request.model`，推荐 `gen_ai.response.model`。
  * docs/gen-ai/gen-ai-token-metrics.md：`gen_ai.client.inference.usage.input_tokens`
    / `.output_tokens` 为 Counter（单位 {token}），必填 `gen_ai.operation.name`、
    `gen_ai.provider.name`、`gen_ai.token.modality`。
  * docs/gen-ai/gen-ai-agent-spans.md：LangGraph `StateGraph` 属"应用定义控制流"，
    `gen_ai.operation.name` SHOULD 为 `invoke_workflow`；`gen_ai.agent.name`
    MUST 低基数（明确不得用 "StateGraph" 之类类型名）。
  * docs/gen-ai/retrieval.md：`gen_ai.retrieval.duration` 为 Histogram(s)，桶 0.01…81.92。
  * docs/gen-ai/execute-tool.md：`gen_ai.execute_tool.duration` 为 Histogram(s)，
    桶 0.01…81.92，span 名 `execute_tool {gen_ai.tool.name}`。
- Prometheus「Metric and label naming」：指标名 SHALL 带应用前缀、用基本单位（秒）、
  累积计数以 `_total` 结尾；标签只承载低基数维度（明确点名 user id / email 这类
  无界集合会让时间序列爆炸）。
- Prometheus「Exposition formats」：HELP 文档串须转义 `\\` 与 `\n`；标签值须转义
  `\\` `"` `\n`；histogram 必须有 `{le="+Inf"}` 桶且等于 `_count`；同一
  (metric, labels) 组合不得重复；Prometheus 3.0 起 /metrics 必须返回合法 Content-Type。

命名边界（重要）：`gen_ai.*` 是语义约定保留命名空间。凡本服务自定义、semconv 未定义的
指标一律用应用前缀 `renewal_*`——因此原 `gen_ai_client_inference_requests_total`
（semconv 无此指标）改名为 `renewal_inference_requests_total`。

实现说明：进程内聚合，GET /metrics 输出 Prometheus 文本格式
（text/plain; version=0.0.4）。单进程部署（uvicorn --workers 1）语义准确；
多副本由各实例各自暴露、Prometheus 按 instance 聚合（见 deploy/）。
"""
from __future__ import annotations

import threading

from . import config

# OTel GenAI 官方推理耗时桶边界（秒），见 client-inference.md / gen-ai-metrics.md。
OTEL_DURATION_BUCKETS = [0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64,
                         1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]
# gen_ai.invoke_agent.duration 专用桶（长时 agent/工作流调用，最长 24h）。
AGENT_DURATION_BUCKETS = [0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6, 51.2,
                          102.4, 204.8, 409.6, 900, 1800, 3600, 7200, 14400,
                          43200, 86400]
# gen_ai.invoke_agent.tool_calls / .inference_calls 官方桶边界（计次，非时间）。
CALLS_BUCKETS: list[float] = [1, 2, 4, 8, 16, 32, 64, 128]
# 会话级耗时（一轮 /chat 从请求到 done），覆盖长 SSE 轮次（应用级 RED）。
CHAT_DURATION_BUCKETS = [0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300]
# 图节点耗时（LangGraph 单节点，通常毫秒级）。
NODE_DURATION_BUCKETS = [0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]

# gen_ai.agent.name 必须低基数且不得是框架类型名（StateGraph 等），见 agent-spans.md。
AGENT_NAME = "renewal-assistant"
# gen_ai.operation.name：本服务是"应用定义控制流"的 LangGraph 工作流 → invoke_workflow。
OPERATION_WORKFLOW = "invoke_workflow"
# 推理侧操作名（chat completion 形态，semconv 枚举值 chat）。
OPERATION_CHAT = "chat"

# 标签键的规范形态：(("label", "value"), ...) 已排序。这里显式起别名，
# 避免 mypy 把 dict 键推断成 tuple[str, ...] 而与其值 tuple[tuple[str, str], ...] 冲突。
MetricKey = tuple[tuple[str, str], ...]

_lock = threading.Lock()


# --------------------------------------------------------------- 文本格式转义
def _esc(value: object) -> str:
    """标签值转义（Prometheus 文本格式：`\\`、`"`、换行必须转义）。"""
    return (str(value).replace("\\", "\\\\")
            .replace('"', '\\"').replace("\n", "\\n"))


def _esc_help(value: str) -> str:
    """HELP 文档串转义（文本格式只要求转义 `\\` 与 `\n`）。"""
    return str(value).replace("\\", "\\\\").replace("\n", "\\n")


def _labels(key: MetricKey, extra: str = "") -> str:
    pairs = [f'{k}="{_esc(v)}"' for k, v in key]
    if extra:
        pairs.append(extra)
    return "{" + ",".join(pairs) + "}" if pairs else ""


# --------------------------------------------------------------- 指标类型
class _Counter:
    def __init__(self, name: str, help_: str):
        self.name, self.help = name, help_
        self.values: dict[MetricKey, float] = {}

    def inc(self, amount: float = 1.0, **labels) -> None:
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with _lock:
            self.values[key] = self.values.get(key, 0.0) + amount

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {_esc_help(self.help)}",
                 f"# TYPE {self.name} counter"]
        for key in sorted(self.values):
            lines.append(f"{self.name}{_labels(key)} {self.values[key]:g}")
        return lines


class _Histogram:
    """零依赖直方图：桶计数 + sum + count（文本格式要求 le="+Inf" 桶存在）。"""

    def __init__(self, name: str, help_: str, buckets: list[float],
                 unit: str = "seconds"):
        self.name, self.help, self.unit = name, help_, unit
        self.buckets = list(buckets)
        # (labelkey) -> [bucket_counts..., sum, count]
        self.data: dict[MetricKey, list[float]] = {}

    @property
    def full_name(self) -> str:
        return f"{self.name}_{self.unit}" if self.unit else self.name

    def observe(self, value: float, **labels) -> None:
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with _lock:
            row = self.data.setdefault(key, [0.0] * (len(self.buckets) + 2))
            for i, b in enumerate(self.buckets):
                if value <= b:
                    row[i] += 1
            row[-2] += value  # sum
            row[-1] += 1      # count

    def render(self) -> list[str]:
        full = self.full_name
        lines = [f"# HELP {full} {_esc_help(self.help)}",
                 f"# TYPE {full} histogram"]
        for key in sorted(self.data):
            row = self.data[key]
            # 桶计数在此实现中按"累计"存储（observe 时逐桶递增），文本格式要求
            # 桶按 le 递增排列且最后一个为 +Inf。
            for i, b in enumerate(self.buckets):
                lines.append(
                    f"{full}_bucket{_labels(key, f'le=\"{b:g}\"')} {row[i]:g}")
            lines.append(f"{full}_bucket{_labels(key, 'le=\"+Inf\"')} {row[-1]:g}")
            lines.append(f"{full}_sum{_labels(key)} {row[-2]:g}")
            lines.append(f"{full}_count{_labels(key)} {row[-1]:g}")
        return lines


# --------------------------------------------------- LLM 身份（provider/model）
# semconv 的 gen_ai.provider.name 是必填属性；well-known 取值表里有 deepseek /
# anthropic / openai / moonshot_ai 等，没有智谱。按 instrumentation 的"最佳认知"
# 从配置推导：识别到 deepseek 用 well-known 值；GLM 走自定义值 zhipu.glm
# （规范允许"没有 well-known 取值时 MAY 使用自定义值"）。
def llm_identity() -> tuple[str | None, str | None]:
    """返回 (gen_ai.provider.name, gen_ai.request.model)；规则模式返回 (None, None)。

    规则模式下并不存在 GenAI 推理，向 gen_ai.* 写指标会把"非 AI 调用"混入 AI 口径，
    因此直接不产出 gen_ai.* 信号（应用级 renewal_* 照常计数）。
    """
    if config.force_rule_mode():
        return None, None
    if not (config.LLM_BASE_URL and config.LLM_AUTH_TOKEN):
        return None, None
    model = config.LLM_MODEL or "unknown"
    blob = f"{config.LLM_BASE_URL} {model}".lower()
    if "deepseek" in blob:
        return "deepseek", model
    if "glm" in blob or "bigmodel" in blob or "zhipu" in blob:
        return "zhipu.glm", model
    return "unknown", model


def _provider() -> str | None:  # 向后兼容旧调用点
    return llm_identity()[0]


def _genai_labels(**extra) -> dict | None:
    """gen_ai.* 指标公共标签（provider/model 必填，缺失即不产出）。"""
    provider, model = llm_identity()
    if provider is None:
        return None
    labels = {"gen_ai_provider_name": provider, "gen_ai_request_model": model}
    labels.update(extra)
    return labels


# ------------------------------------------------------------ 指标定义
chat_requests = _Counter(
    "renewal_chat_requests_total", "完成的 /chat 轮次计数（outcome=done|error）")
errors_total = _Counter(
    "renewal_errors_total", "轨迹 error 记录计数（code 为低基数错误类）")
tool_calls = _Counter(
    "renewal_tool_calls_total", "编排图 tool_call 计数（按节点）")
inference_requests = _Counter(
    "renewal_inference_requests_total",
    "LLM 推理调用计数（应用级；semconv 无 gen_ai.*.requests 指标，故用应用前缀）")
tokens_in_total = _Counter(
    "gen_ai_client_inference_usage_input_tokens_total",
    "LLM 输入 token 累计（OTel gen_ai.client.inference.usage.input_tokens）")
tokens_out_total = _Counter(
    "gen_ai_client_inference_usage_output_tokens_total",
    "LLM 输出 token 累计（OTel gen_ai.client.inference.usage.output_tokens）")

chat_duration = _Histogram(
    "renewal_chat_duration",
    "一轮 /chat（请求→done/error 事件）总耗时", CHAT_DURATION_BUCKETS)
inference_duration = _Histogram(
    "gen_ai_client_inference_duration",
    "LLM 推理调用耗时（OTel gen_ai.client.inference.duration）",
    OTEL_DURATION_BUCKETS)
node_duration = _Histogram(
    "renewal_node_duration",
    "编排图单节点耗时（SPEC §5 node_end latency_ms）", NODE_DURATION_BUCKETS)
agent_duration = _Histogram(
    "gen_ai_invoke_agent_duration",
    "一次 /chat 触发的工作流入口调用耗时（OTel gen_ai.invoke_agent.duration）",
    AGENT_DURATION_BUCKETS)
agent_tool_calls = _Histogram(
    "gen_ai_invoke_agent_tool_calls",
    "单次工作流调用内的工具调用数（OTel gen_ai.invoke_agent.tool_calls）",
    CALLS_BUCKETS, unit="")
agent_inference_calls = _Histogram(
    "gen_ai_invoke_agent_inference_calls",
    "单次工作流调用内的推理调用数（OTel gen_ai.invoke_agent.inference_calls）",
    CALLS_BUCKETS, unit="")
retrieval_duration = _Histogram(
    "gen_ai_retrieval_duration",
    "知识检索耗时（OTel gen_ai.retrieval.duration）", OTEL_DURATION_BUCKETS)
execute_tool_duration = _Histogram(
    "gen_ai_execute_tool_duration",
    "工具执行耗时（OTel gen_ai.execute_tool.duration）", OTEL_DURATION_BUCKETS)

_ALL: list[_Counter | _Histogram] = [
        chat_requests, errors_total, tool_calls, inference_requests,
        tokens_in_total, tokens_out_total,
        chat_duration, inference_duration, node_duration, agent_duration,
        agent_tool_calls, agent_inference_calls, retrieval_duration,
        execute_tool_duration]


def render() -> str:
    """输出 Prometheus 文本暴露格式（GET /metrics 响应体）。"""
    lines: list[str] = []
    for m in _ALL:
        lines.extend(m.render())
    return "\n".join(lines) + "\n"


def reset() -> None:
    """清空全部指标与轮次状态（测试用）。"""
    with _lock:
        for m in _ALL:
            if isinstance(m, _Counter):
                m.values.clear()
            else:
                m.data.clear()
        _turns.clear()


# --------------------------------------------- 轮次状态（agent 级指标聚合）
# gen_ai.invoke_agent.* 是"每次调用"的分布（而非累计计数），因此必须按 trace_id
# 聚合一轮内的工具/推理调用次数，在轮次结束时一次性 observe。状态随轮次结束清除；
# 生产上若某轮异常未收口，用 _MAX_TURNS 兜底裁剪，避免内存无界增长。
_MAX_TURNS = 4096
_turns: dict[str, dict] = {}


def _turn(trace_id: str) -> dict:
    with _lock:
        state = _turns.get(trace_id)
        if state is None:
            if len(_turns) >= _MAX_TURNS:
                _turns.pop(next(iter(_turns)), None)
            state = {"tool": 0, "inference": 0, "error": ""}
            _turns[trace_id] = state
        return state


def turn_counts(trace_id: str) -> dict:
    """读取当前轮次计数（测试/诊断用，不改变状态）。"""
    with _lock:
        return dict(_turns.get(trace_id) or {"tool": 0, "inference": 0, "error": ""})


def finish_turn(trace_id: str, duration_s: float, outcome: str) -> None:
    """一轮 /chat 收口：应用级 RED + agent 级 semconv 指标一起落。"""
    chat_duration.observe(duration_s, outcome=outcome)
    chat_requests.inc(outcome=outcome)
    state = _turn(trace_id)
    labels = _genai_labels(gen_ai_operation_name=OPERATION_WORKFLOW,
                           gen_ai_agent_name=AGENT_NAME,
                           error_type=state.get("error") or "")
    if labels is not None:
        agent_duration.observe(duration_s, **labels)
        agent_tool_calls.observe(float(state.get("tool", 0)),
                                 gen_ai_operation_name=OPERATION_WORKFLOW,
                                 gen_ai_agent_name=AGENT_NAME)
        agent_inference_calls.observe(float(state.get("inference", 0)),
                                      gen_ai_operation_name=OPERATION_WORKFLOW,
                                      gen_ai_agent_name=AGENT_NAME)
    with _lock:
        _turns.pop(trace_id, None)


# ------------------------------------------------- 轨迹行 → 指标（唯一入口）
# TraceRecorder.record() 是所有遥测的必经点：在这里把 SPEC §5 字段映射为
# OTel GenAI 指标，保证 JSONL 与 /metrics 永远同源（不会两套口径）。
def observe_record(row: dict) -> None:
    rt = row.get("record_type")
    trace_id = str(row.get("trace_id") or "")
    if rt == "llm_response":
        lat = row.get("latency_ms")
        labels = _genai_labels(gen_ai_operation_name=OPERATION_CHAT)
        if labels is not None:
            if isinstance(lat, (int, float)) and lat >= 0:
                inference_duration.observe(lat / 1000.0,
                                           error_type="", **labels)
            ti, to = row.get("tokens_in"), row.get("tokens_out")
            # 规则模式无 token 统计（None）：不计数，避免把"未知"当 0 混入成本口径。
            token_labels = dict(labels, gen_ai_token_modality="text")
            if isinstance(ti, (int, float)):
                tokens_in_total.inc(float(ti), **token_labels)
            if isinstance(to, (int, float)):
                tokens_out_total.inc(float(to), **token_labels)
            inference_requests.inc(
                1, gen_ai_operation_name=OPERATION_CHAT, error_type="")
        if trace_id:
            _turn(trace_id)["inference"] += 1
    elif rt == "llm_call":
        pass  # 请求计数在 llm_response/error 收口，防止失败调用双计
    elif rt == "tool_call":
        node = row.get("node") or "unknown"
        tool_calls.inc(node=node)
        if trace_id:
            _turn(trace_id)["tool"] += 1
    elif rt == "tool_result":
        lat = row.get("latency_ms")
        node = row.get("node") or "unknown"
        if isinstance(lat, (int, float)) and lat >= 0:
            execute_tool_duration.observe(lat / 1000.0,
                                          gen_ai_tool_name=node)
    elif rt == "retrieval":
        lat = row.get("latency_ms")
        if isinstance(lat, (int, float)) and lat >= 0:
            retrieval_duration.observe(
                lat / 1000.0, gen_ai_operation_name="retrieval",
                node=row.get("node") or "unknown")
    elif rt == "node_end":
        lat = row.get("latency_ms")
        if isinstance(lat, (int, float)) and lat >= 0:
            node_duration.observe(lat / 1000.0,
                                  node=row.get("node") or "unknown")
    elif rt == "error":
        err = row.get("error") or {}
        code = str(err.get("code") or "unknown")[:64]  # 低基数截断
        errors_total.inc(code=code)
        if trace_id:
            _turn(trace_id)["error"] = code
        labels = _genai_labels(gen_ai_operation_name=OPERATION_CHAT)
        if labels is not None:
            inference_requests.inc(1, error_type=code, **labels)
            # 故意不向 inference_duration 写样本：错误调用没有可信耗时，
            # 写 0.0 会把 p95 拉低、污染延迟分布（延迟直方图只统计真实调用）。
