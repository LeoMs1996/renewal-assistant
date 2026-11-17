"""集中配置：路径 + 环境变量（.env 手动解析，避免额外依赖）。

环境变量优先级：进程环境 > 项目根 .env > 默认值。
LLM 配置同时兼容两套变量名（备忘 #4 与 .env.example）：
  ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / MODEL_NAME   （GLM Anthropic 兼容，首选）
  ANTHROPIC_API_KEY  / ANTHROPIC_MODEL                     （.env.example 原有，回退）
缺配置时 llm.LLMClient 自动降级为规则模式（不崩溃）。
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # renewal-assistant/


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


_dotenv = _load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or _dotenv.get(name) or default


# ---- 服务 ----
HOST = env("HOST", "127.0.0.1") or "127.0.0.1"
PORT = int(env("PORT", "8000") or 8000)

# ---- 路径 ----
TRACE_DIR = Path(env("TRACE_DIR", str(BASE_DIR / "traces")) or (BASE_DIR / "traces"))
SYNTHETIC_DIR = Path(env("SYNTHETIC_DIR", str(BASE_DIR / "synthetic")) or (BASE_DIR / "synthetic"))
WIKI_DIR = Path(env("WIKI_DIR", str(BASE_DIR / "wiki")) or (BASE_DIR / "wiki"))
TRACE_DIR.mkdir(parents=True, exist_ok=True)

# ---- LLM（GLM，Anthropic 兼容接口）----
LLM_BASE_URL = env("ANTHROPIC_BASE_URL")  # 如 https://open.bigmodel.cn/api/anthropic
LLM_AUTH_TOKEN = env("ANTHROPIC_AUTH_TOKEN") or env("ANTHROPIC_API_KEY")
LLM_MODEL = env("MODEL_NAME") or env("ANTHROPIC_MODEL") or "glm-4.6"


# ---- 安全（SPEC v1.0.3：鉴权/安全头/限流，详见 server/middleware.py）----
def api_keys() -> dict[str, str]:
    """解析 RENEWAL_API_KEYS（逗号分隔 key:owner_id）→ {key: owner_id}。

    为空 = 演示模式（放行但响应头 X-Auth-Mode: demo）。动态读取进程环境
    与 .env，测试可 monkeypatch 本函数。
    """
    keys: dict[str, str] = {}
    for item in (env("RENEWAL_API_KEYS") or "").split(","):
        item = item.strip()
        if not item:
            continue
        key, sep, owner = item.partition(":")
        if sep and key.strip() and owner.strip():
            keys[key.strip()] = owner.strip()
    return keys


def rate_limit_per_min() -> int:
    """每 IP 每分钟请求上限（RENEWAL_RATE_LIMIT_PER_MIN，默认 60）。"""
    try:
        return max(1, int(env("RENEWAL_RATE_LIMIT_PER_MIN", "60") or 60))
    except ValueError:
        return 60

def chat_rate_limit_per_min() -> int:
    """`/chat` 单独配额（RENEWAL_CHAT_RATE_LIMIT_PER_MIN，默认 60，与通用配额一致）。

    安全域（t9，2026-11-17）：/chat 每次请求都会触发 LLM 推理与轨迹写入，
    其单位成本远高于静态端点。OWASP LLM10:2025 把这类“按次付费资源”的
    配额与限流列为独立缓解项（Denial of Wallet），故与通用 IP 名额分开计数。

    默认值与通用配额一致（60/min）——独立"计数桶"本身已经隔离了静态端点与
    会话端点的互相挤占；默认值刻意**不再更低**：评测/回归是 60 秒内连发
    19~38 条请求的合法批量场景（t13 实测：20/min 会把 19 条用例打成 6 条）。
    要更严就显式调低本变量；要放宽（压测/回归）就调高或置 RENEWAL_RATE_LIMIT_DISABLED=1。
    """
    try:
        return max(1, int(env("RENEWAL_CHAT_RATE_LIMIT_PER_MIN", "60") or 60))
    except ValueError:
        return 60


def rate_limit_disabled() -> bool:
    """RENEWAL_RATE_LIMIT_DISABLED=1：完全关闭限流（仅压测/回归/本地演示）。

    单独用显式开关而不是"把阈值调很大"，好处是审计时一眼能看出是否处于
    关闭态（服务启动日志会打一行 warning），不会出现"以为开着其实早调成 1e9"。
    """
    return (env("RENEWAL_RATE_LIMIT_DISABLED") or "").strip().lower() in (
        "1", "true", "yes", "on")


def expose_docs() -> bool:
    """RENEWAL_EXPOSE_DOCS：是否向匿名访问者开放 /docs /redoc /openapi.json。

    默认关闭（非演示模式下），避 OWASP API8:2023 Security Misconfiguration：
    完整的接口结构图是攻击者做参数模糊测试的第一步。本地接文档时置 1。
    """
    return (env("RENEWAL_EXPOSE_DOCS") or "").strip().lower() in (
        "1", "true", "yes", "on")

def force_rule_mode() -> bool:
    """RENEWAL_FORCE_RULE_MODE=1 时强制规则模式（CI/回归可重现）。"""
    return (env("RENEWAL_FORCE_RULE_MODE") or "").strip().lower() in (
        "1", "true", "yes", "on")


def llm_timeout_s() -> float:
    """单次 LLM HTTP 请求超时（RENEWAL_LLM_TIMEOUT_S，默认 30 秒）。

    安全域（t9，2026-11-17）实测缺陷：SDK 默认超时是 10 分钟、默认重试 2 次，
    上游一旦挂住，`/chat` 会连着挂起 30 分钟并长期占住一个 worker——OWASP
    LLM10:2025 把 "Timeouts and Throttling" 列为独立缓解项，必须显式设置。
    """
    try:
        return max(1.0, float(env("RENEWAL_LLM_TIMEOUT_S", "30") or 30))
    except ValueError:
        return 30.0


def llm_max_retries() -> int:
    """LLM 请求最大重试次数（RENEWAL_LLM_MAX_RETRIES，默认 1）。

    与图内工具重试（TOOL_MAX_ATTEMPTS）叠加时会放大最坏延迟，故默认只留 1 次。
    """
    try:
        return max(0, int(env("RENEWAL_LLM_MAX_RETRIES", "1") or 1))
    except ValueError:
        return 1


def llm_strict() -> bool:
    """RENEWAL_LLM_STRICT=1：严格模式（SPEC v1.0.5）。

    LLM 调用失败直接失败（错误码 LLM_UNAVAILABLE），不再静默回退规则模式；
    `/chat` 会在开流前探活，不可用则回 503。默认关闭——宽松模式行为与以前一致，
    但降级会在 SSE（llm_degraded）与轨迹 JSONL 里留标记。
    """
    return (env("RENEWAL_LLM_STRICT") or "").strip().lower() in (
        "1", "true", "yes", "on")


# ---- 记忆机制（对话记忆 / 长期记忆 / 跨会话记忆，详见 reviews/memory.md）----
# 上下文预算按 token 估算（memory.estimate_tokens），替代旧的固定条数截断：
#   memory_prompt_budget —— 需求解析类 prompt 的历史预算（含滚动摘要 + 记忆简报）
#   memory_chat_budget   —— 顾问/条款类 prompt 的历史预算（正文本身已占位，预算更小）
# RENEWAL_MEMORY=off 可整体退回旧截断策略（回滚闸门）。
def memory_prompt_budget() -> int:
    try:
        return max(200, int(env("RENEWAL_MEMORY_PROMPT_BUDGET", "1000") or 1000))
    except ValueError:
        return 1000


def memory_chat_budget() -> int:
    try:
        return max(120, int(env("RENEWAL_MEMORY_CHAT_BUDGET", "600") or 600))
    except ValueError:
        return 600


# ---- 合成数据声明（硬规矩 #3：所有输出标"模拟报价/合成数据"）----
DISCLAIMER = "以上均为模拟报价，数据为合成数据（虚构），仅供参考。"
