"""GLM 客户端（Anthropic 兼容接口）。

- 配置从 .env / 环境变量读取（见 config.py），代码不含密钥。
- 缺配置时降级为规则模式：所有回复带「规则模式」标注，不崩溃（备忘 #4）。
- 保费等数字一律由报价服务计算，规则模式只做文字组织，绝不编造数字。
- **降级可观测 + 严格模式**（SPEC v1.0.5，编排域 F6 整改）：
  * 运行时调用失败（429 / 超时 / 连接断开）**不再静默**：返回结果带
    `degraded=True` + `error_type`，调用方据此在 SSE 与轨迹里落 `llm_degraded` 标记；
  * `RENEWAL_LLM_STRICT=1` 时改为抛 `LLMUnavailableError`（错误码
    `LLM_UNAVAILABLE`），由编排层翻译为明确失败，而非「看起来成功」；
  * `available=False`（无凭证 / `RENEWAL_FORCE_RULE_MODE=1`）是**显式配置**的规则
    模式，不算降级、不打标记（严格模式下同样不报错）。
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass

from . import config

LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
PREFLIGHT_TTL_SECONDS = 30.0  # 严格模式探活成功缓存时长（避免每轮多打一次模型）


class LLMUnavailableError(RuntimeError):
    """严格模式（RENEWAL_LLM_STRICT=1）下 LLM 调用失败：不允许静默降级。

    编排层（server/graph.py::_stream_guarded）把它翻译成
    SSE `error{code=LLM_UNAVAILABLE}` + `done.finish_reason=error`；
    `/chat` 开流前探活失败则直接 503（server/app.py）。
    """

    code = LLM_UNAVAILABLE

    def __init__(self, node: str, error_type: str, message: str):
        self.node = node
        self.error_type = error_type
        self.message = message
        super().__init__(f"LLM 调用失败（node={node}, {error_type}）：{message}")


@dataclass
class LLMResult:
    text: str
    tokens_in: int | None
    tokens_out: int | None
    mode: str  # "llm" | "rule"
    # 降级标记（v1.0.5）：mode=="rule" 且 degraded=True = 「本应是 llm、因故障降级」
    degraded: bool = False
    error_type: str | None = None
    error_message: str | None = None


class LLMClient:
    """统一对话客户端。available=False 表示规则模式。"""

    def __init__(self) -> None:
        self.base_url = config.LLM_BASE_URL
        self.token = config.LLM_AUTH_TOKEN
        self.model = config.LLM_MODEL
        # RENEWAL_FORCE_RULE_MODE=1：强制规则模式（确定性、无外部网络依赖）。
        # 用途：CI/回归评测必须可重现，不受 .env 里是否配了 LLM 凭证影响
        # （2026-11-13 新增，配套 .github/workflows/ci.yml）。
        self.available = (bool(self.base_url and self.token)
                          and not config.force_rule_mode())
        # v1.0.5：严格模式 + 降级留痕（编排域 F6）
        self.strict = config.llm_strict()
        self.degradations: list[dict] = []  # 进程内降级事件（/health 与测试可读）
        self._preflight_ok_until = 0.0
        self._client = None
        if self.available:
            try:
                import anthropic  # 延迟导入，未装 SDK 也可跑规则模式

                # 安全域（t9）：显式超时 + 有限重试。SDK 默认 10 分钟/2 次重试，
                # 上游挂住会让 /chat 挂起半小时（实测过一次，见 reviews/security.md F11）。
                self._client = anthropic.Anthropic(
                    base_url=self.base_url, api_key=self.token,
                    timeout=config.llm_timeout_s(),
                    max_retries=config.llm_max_retries(),
                )
            except Exception:
                self._client = None
                self.available = False

    # ---------- 降级 / 严格模式（SPEC v1.0.5） ----------
    def _on_failure(self, node: str, exc: Exception) -> dict:
        """登记一次 LLM 运行时失败；严格模式直接抛 LLMUnavailableError。"""
        error_type = type(exc).__name__
        message = str(exc)[:200]
        record = {"node": node, "code": LLM_UNAVAILABLE,
                  "error_type": error_type, "message": message,
                  "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.degradations.append(record)
        if self.strict:
            raise LLMUnavailableError(node=node, error_type=error_type,
                                      message=message) from exc
        return record

    @staticmethod
    def _degraded_text(messages: list[dict], exc: Exception) -> str:
        return (f"【规则模式兜底：模型调用失败（{type(exc).__name__}）】\n"
                + _rule_reply(messages))

    def preflight(self) -> dict:
        """严格模式开流前探活：最小调用确认 provider 可达（成功结果缓存 TTL 秒）。

        返回 `{"ok": bool, ...}`；ok=False 时由 app.py 直接回 503 `LLM_UNAVAILABLE`。
        非严格模式 / 显式规则模式（无凭证、FORCE_RULE_MODE）一律 ok=True（跳过）。
        """
        if not self.strict:
            return {"ok": True, "skipped": "non_strict"}
        if not self.available:
            return {"ok": True, "skipped": "rule_mode_by_config"}
        now = time.monotonic()
        if self._preflight_ok_until > now:
            return {"ok": True, "cached": True}
        try:
            assert self._client is not None
            # 探活走最短路径：关掉 SDK 自带重试并限时，避免把失败拖成秒级
            probe = (self._client.with_options(max_retries=0, timeout=10.0)
                     if hasattr(self._client, "with_options") else self._client)
            probe.messages.create(model=self.model, max_tokens=1,
                                  messages=[{"role": "user", "content": "ping"}])
            self._preflight_ok_until = now + PREFLIGHT_TTL_SECONDS
            return {"ok": True}
        except Exception as exc:  # 探活失败本身不录降级（没跑过业务调用）
            return {"ok": False, "code": LLM_UNAVAILABLE, "node": "preflight",
                    "error_type": type(exc).__name__, "message": str(exc)[:200]}

    # ---------- 非流式 ----------

    def chat(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        node: str = "chat",
    ) -> LLMResult:
        if not self.available:
            return LLMResult(text=_rule_reply(messages), tokens_in=None,
                             tokens_out=None, mode="rule")
        try:
            assert self._client is not None
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            text = "".join(
                blk.text for blk in resp.content if getattr(blk, "type", "") == "text"
            )
            return LLMResult(
                text=text,
                tokens_in=getattr(resp.usage, "input_tokens", None),
                tokens_out=getattr(resp.usage, "output_tokens", None),
                mode="llm",
            )
        except Exception as exc:  # 运行时失败 → 留痕降级；严格模式抛错（v1.0.5）
            record = self._on_failure(node, exc)
            return LLMResult(
                text=self._degraded_text(messages, exc),
                tokens_in=None, tokens_out=None, mode="rule",
                degraded=True, error_type=record["error_type"],
                error_message=record["message"],
            )
    def chat_tool_json(
        self,
        system: str,
        messages: list[dict],
        tool_name: str,
        tool_description: str,
        input_schema: dict,
        max_tokens: int = 1024,
        node: str = "chat_tool_json",
    ) -> tuple[dict | None, LLMResult | None]:
        """用 tool-use 强制模型返回符合 input_schema 的 JSON。

        返回 (parsed_dict, LLMResult)。规则模式 / 调用失败 / 无 tool_use 块
        一律返回 (None, None)，由调用方降级到关键词规则解析（备忘 #4）。

        修复（P0，评审 review.md）：部分模型会把可空字段序列化为
        字符串 "null"/"None"/""（schema 声明 ["string","null"] 时尤甚），
        此处统一做归一化（normalize_tool_json），对所有可空字段通用。
        """
        if not self.available:
            return None, None
        try:
            assert self._client is not None
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=[{
                    "name": tool_name,
                    "description": tool_description,
                    "input_schema": input_schema,
                }],
                tool_choice={"type": "tool", "name": tool_name},
            )
            for blk in resp.content:
                if getattr(blk, "type", "") == "tool_use":
                    data = blk.input if isinstance(blk.input, dict) else None
                    data = normalize_tool_json(data)
                    return data, LLMResult(
                        text=json.dumps(data, ensure_ascii=False) if data else "",
                        tokens_in=getattr(resp.usage, "input_tokens", None),
                        tokens_out=getattr(resp.usage, "output_tokens", None),
                        mode="llm",
                    )
            return None, None
        except Exception as exc:  # 留痕降级；严格模式抛错（v1.0.5）
            record = self._on_failure(node, exc)
            return None, LLMResult(text="", tokens_in=None, tokens_out=None,
                                   mode="rule", degraded=True,
                                   error_type=record["error_type"],
                                   error_message=record["message"])

    # ---------- 流式（token 事件用） ----------
    def stream_chat(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        node: str = "stream_chat",
    ) -> Iterator[tuple[str, LLMResult]]:
        """yield (delta, partial_result)；最后一个 partial_result 汇总 token 计量。"""
        if not self.available:
            text = _rule_reply(messages)
            for ch in text:
                yield ch, LLMResult(text="", tokens_in=None, tokens_out=None, mode="rule")
            yield "", LLMResult(text=text, tokens_in=None, tokens_out=None, mode="rule")
            return
        try:
            assert self._client is not None
            collected: list[str] = []
            with self._client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    collected.append(text)
                    yield text, LLMResult(text="", tokens_in=None, tokens_out=None, mode="llm")
                usage = stream.usage_message.get("usage", {}) if isinstance(stream.usage_message, dict) else {}
            yield "", LLMResult(
                text="".join(collected),
                tokens_in=usage.get("input_tokens"),
                tokens_out=usage.get("output_tokens"),
                mode="llm",
            )
        except Exception as exc:  # 留痕降级；严格模式抛错（v1.0.5）
            record = self._on_failure(node, exc)
            text = self._degraded_text(messages, exc)
            for ch in text:
                yield ch, LLMResult(text="", tokens_in=None, tokens_out=None, mode="rule")
            yield "", LLMResult(text=text, tokens_in=None, tokens_out=None, mode="rule",
                                 degraded=True, error_type=record["error_type"],
                                 error_message=record["message"])


# 可空字段的字符串哨兵：模型 tool-use 输出中代表 None 的字符串（P0 修复）
_NULL_SENTINELS = {"null", "none", "nil", ""}


def normalize_tool_json(data, _depth: int = 0):
    """递归归一化结构化输出：把表示“空”的字符串哨兵转为真正的 None。

    评审 review.md P0 根因：GLM tool-use 会把 schema 中 type=["string","null"]
    的可空字段（如 use_nature_change / budget_yuan）序列化为字符串 "null"/
    "None"/""，下游未归一化直传报价服务 → INVALID_USE_NATURE「使用性质『null』」。
    此函数对所有可空字段通用，也处理列表与嵌套 dict；仅修剪空串哨兵，
    不改动其它字符串值（"null " 等带空白先 strip 再判定）。
    """
    if _depth > 12:  # 防御：异常深嵌套不递归
        return data
    if isinstance(data, str):
        return None if data.strip().lower() in _NULL_SENTINELS else data
    if isinstance(data, dict):
        return {k: normalize_tool_json(v, _depth + 1) for k, v in data.items()}
    if isinstance(data, list):
        return [normalize_tool_json(v, _depth + 1) for v in data]
    return data


def _rule_reply(messages: list[dict]) -> str:
    """规则模式：基于最近一条用户消息的确定性应答模板。"""
    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )
    keywords = {
        "到期": "您的保单临近到期，建议尽快办理续保以免脱保。",
        "续保": "已为您准备续保方案比较，请稍候（规则模式：编排逻辑待接入）。",
        "报价": "保费由报价服务计算生成（模拟报价），当前为规则模式，暂不生成具体数字。",
        "条款": "条款内容来自合成条款知识库（虚构），可提供带来源与版本的摘录。",
    }
    hits = [v for k, v in keywords.items() if k in last_user]
    body = " ".join(hits) if hits else "已收到您的消息（规则模式：当前为状态机骨架阶段，编排逻辑待接入）。"
    return f"【规则模式】{body}\n{config.DISCLAIMER}"


_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
