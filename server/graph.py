"""LangGraph 状态机实现（SPEC §6）：11 节点 + 边拓扑与 SPEC §6.2 一致。

节点通过 get_stream_writer() 发出自定义事件（LangGraph 1.x 官方流式通道，
Context7 查证：graph.stream(stream_mode=["custom","values"]) 消费），事件格式：
    {"event": <SSE 事件名>, "data": {...}, "trace": {TraceRecorder.record 关键字参数}}
app.py 把自定义事件翻译成 SSE 帧并写轨迹 JSONL（SPEC §4.1 / §5）。

相对 SPEC §6.2 显式边表的必要旁路（错误/跨轮分支，已在 docs/summaries/orchestration.md 说明）：
  parse_needs → fallback   保单未找到(AC-04) / 步数上限 / 无进展退出
  retrieve_terms → confirm 跨轮确认：await_confirm 挂起后用户回复"确认"，
                          下一轮经 START→intake 重入图，是 SPEC 边
                          "await_confirm → confirm（用户已确认）"的跨轮实现
  quote → fallback         报价工具业务错误（纠正提示，不中断协议）

硬规矩（备忘 #3）：保费数字只来自 query_quote 返回；compare/fallback 的文案
只引用报价结果与 wiki 摘录中的数字，规则模式与 LLM 模式同规。
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from . import config, mcp_bridge, memory, quote_book, security, sessions, wiki_search
from . import trace as trace_mod
from .llm import LLM_UNAVAILABLE, LLMUnavailableError, get_client

# ---------------------------------------------------------------------------
# 官方 checkpointer 持久化（2026-11-13 评审整改）
# ---------------------------------------------------------------------------
# Context7 查证（docs.langchain.com/oss/python/langgraph/checkpointers，2026-11-13）：
# - langgraph-checkpoint-sqlite 为独立安装包（SqliteSaver/AsyncSqliteSaver），
#   InMemorySaver 内置于 langgraph-checkpoint；
# - 编译时 builder.compile(checkpointer=...)，invoke/stream 需带
#   config={"configurable": {"thread_id": ...}}，thread_id 为 checkpoint 主键。
try:  # 生产：SQLite 落盘，跨进程重启状态不丢
    import sqlite3 as _sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver
    _SQLITE_SAVER_AVAILABLE = True
except ImportError:  # 实验环境兜底：进程内 saver（生产需装独立包，待验证）
    _SQLITE_SAVER_AVAILABLE = False
    from langgraph.checkpoint.memory import InMemorySaver


CHECKPOINT_DB = None          # 进程级 saver 单例（连接须 check_same_thread=False）
CHECKPOINT_RETENTION_DAYS = 30  # checkpoint 保留期（官方 persistence 文档：防无限增长）

# 执行期参数（2026-11 官方 graph-api / checkpointers 语义，检索 2026-11-17）：
# - durability：checkpoint 落盘时机。"sync" = 每个 superstep 结束前同步落盘（崩溃
#   不丢中间状态，确认投保这类写路径需要它）；"async" = 下一步开始前异步落盘（默认）；
#   "exit" = 仅在 run 结束时落盘（最省 I/O，崩溃丢中间态）。
# - recursion_limit：superstep 上限，超限抛 GraphRecursionError（非普通异常，
#   不在 except Exception 之外单独处理就会退化成 INTERNAL 错误码）。
GRAPH_DURABILITY = (config.env("RENEWAL_GRAPH_DURABILITY", "sync") or "sync").strip().lower()
if GRAPH_DURABILITY not in ("sync", "async", "exit"):
    GRAPH_DURABILITY = "sync"
RECURSION_LIMIT = int(config.env("RENEWAL_RECURSION_LIMIT", "40") or 40)
TOOL_MAX_ATTEMPTS = int(config.env("RENEWAL_TOOL_MAX_ATTEMPTS", "3") or 3)

# 并发安全（本轮评审整改，证据见 reviews/orchestration.md F2）：
# 旧版 _RUN_LOCK 声称串行化共享 sqlite 连接，实测该锁只覆盖「生成器构造」而不
# 覆盖图执行，两路并发流仍并行跑（探针可复现），既无效也无必要——
# langgraph.checkpoint.sqlite.SqliteSaver 内部自带 threading.Lock（已安装包源码
# langgraph/checkpoint/sqlite/__init__.py:100 `self.lock`，其 docstring 写明
# "check_same_thread=False is OK as the implementation uses a lock"），
# 故删除该锁，仅保留 WAL + busy_timeout 作为跨连接写冲突兜底。


def _make_checkpointer():
    """优先 SqliteSaver（traces/checkpoints.sqlite），缺包降级 InMemorySaver。

    官方基线（docs.langchain.com/oss/python/langgraph/persistence，检索 2026-11-13）：
    - SQLite saver 面向本地/实验；生产建议 PostgresSaver（本报告 P1 项）。
    - 需防止 checkpoint 无限增长：定期清理超期 thread（官方建议 cron 删 N 天前数据）。
    并发安全：app.py 在 run_in_executor 线程池中并发驱动同一 saver 实例。
    SqliteSaver 内部对自身读写持 threading.Lock（已安装包源码 sqlite/__init__.py:100）
    → 进程内多线程共享一个 saver 是安全的；此处另以 WAL + busy_timeout 兜底跨连接
    写冲突（多 worker 场景），不再依赖调用方加锁。
    """
    global CHECKPOINT_DB
    if _SQLITE_SAVER_AVAILABLE:
        CHECKPOINT_DB = config.TRACE_DIR / "checkpoints.sqlite"
        conn = _sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")       # 降低写锁粒度
        conn.execute("PRAGMA busy_timeout=5000")      # 写冲突时等待而非抛错
        saver = SqliteSaver(conn)
        _cleanup_old_checkpoints(saver)
        return saver
    return InMemorySaver()


def _cleanup_old_checkpoints(saver, retention_days: int = CHECKPOINT_RETENTION_DAYS) -> int:
    """删除保留期外未再活跃的 thread（官方 persistence：防 checkpoint 无限增长）。

    以各 thread 最新 checkpoint 的 ts 判龄；失败静默（清理是尽力而为，不阻断启动）。
    返回删除的 thread 数（供测试/日志用）。
    """
    removed = 0
    try:
        cutoff = (datetime.now().timestamp()
                  - retention_days * 86400)
        latest_by_thread: dict[str, datetime] = {}
        for tup in saver.list({"configurable": {}}):
            try:
                cp = tup.checkpoint
                tid = tup.config.get("configurable", {}).get("thread_id", "")
                ts = datetime.fromisoformat(cp["ts"])
                ts = ts.timestamp() if ts.tzinfo is None else ts.timestamp()
                if tid and (tid not in latest_by_thread or ts > latest_by_thread[tid]):
                    latest_by_thread[tid] = ts
            except Exception:
                continue
        for tid, ts in latest_by_thread.items():
            if ts < cutoff:
                saver.delete_thread(tid)
                removed += 1
    except Exception:
        pass
    return removed

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

STEP_LIMIT = 8                 # 单轮步数上限（备忘 g）
NO_PROGRESS_LIMIT = 2          # 连续 N 轮无新信息 → 退出（备忘 g）
DISCONTINUED_KEYWORDS = {       # 停售险种关键词 → 险种代码（rates.json discontinued）
    "发动机进水": "FDJJS", "涉水险": "FDJJS",
    "自燃": "ZRRS", "玻璃单独": "BLDPOX", "玻璃险": "BLDPOX",
}
DSX_TIERS = [500000, 1000000, 2000000, 3000000]  # 三者险可选档位（rates.json）
MAX_QUOTE_AGE_REUSE_OK = True  # 复用仅在 valid_until 内（备忘 c）
_RATE_DEFAULT_SUM_CACHE: dict | None = None  # 费率表固定保额默认值缓存（_selection_key 归一化用）

CONFIRM_WORDS = re.compile(r"确认|就这|就按|按此|投保吧|同意|成交|没问题|可以投|就这么")
TERMS_WORDS = re.compile(r"条款|免赔|年检|赔不赔|怎么赔|什么意思|是什么|区别|规定|免责|拒赔")
RENEWAL_WORDS = re.compile(
    r"续保|到期|报价|比价|方案|险种|保额|三者|第三者|车损|交强|医保外|外用药|划痕|"
    r"座位|车上人员|预算|加个?|去掉|不要|删掉|退掉|调整|提高|升到|改成|网约|滴滴|营运"
)
RIDE_HAILING_WORDS = re.compile(r"网约|滴滴|顺风车|拉客|跑单|营运用?途|营运")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class RenewalState(TypedDict, total=False):
    # ---- SPEC §6.2 状态对象 ----
    session_id: str
    trace_id: str
    owner_id: str
    vin: str
    policy: dict | None            # get_policy 结果（含 owner/policy/days_to_expiry）
    needs: dict | None             # 当前需求（唯一版本，多版本只留最新）
    quotes: list[dict]             # 本会话全部报价摘要（轨迹可证询价次数；整体替换语义）
    comparison: dict | None
    citations: list[dict]
    llm_degraded: list[dict]        # LLM 降级留痕（v1.0.5：SSE + 轨迹双标记）
    await_flag: bool
    error: dict | None
    # ---- 路由辅助键 ----
    intent: str                    # renewal / compare / terms / chitchat / confirm
    needs_sufficient: bool
    need_quote: bool
    confirmed: bool
    confirm_error: str | None      # QUOTE_EXPIRED / QUOTE_VERSION_STALE / QUOTE_NOT_FOUND
    finish_reason: str             # end / await_user / error
    # ---- 编排扩展键（会话级见 sessions.py）----
    message: str                   # 本轮用户输入
    history: list[dict]            # 对话历史（硬盘上限 40 条；进 prompt 的量按 token 预算裁）
    needs_version: int             # 需求版本号（变更即 +1）
    invalidated: list[dict]        # 记忆撤回：被改口失效的旧偏好
    # ---- 记忆机制域扩展键（详见 reviews/memory.md）----
    memory_seeded: list[str]       # 本轮由跨会话记忆补齐的需求字段（可审计）
    memory_ctx: dict               # 本轮 context package 预算明细（写入 node_end.output）
    no_progress_rounds: int
    steps: int
    exit_reason: str | None        # step_limit / no_progress
    latest_quote: dict | None      # 最新需求报价（含 coverage_selection）
    baseline_quote: dict | None    # 原方案续保报价（对照组）
    excerpts: dict                 # wiki_id -> 摘录文本（组 prompt 用，不入轨迹）
    wanted_wiki_ids: list[str]     # parse_needs 要求检索必须包含的条目
    corrections: list[dict]        # 不可行动作纠正（JQX_REQUIRED / COVERAGE_DISCONTINUED / RIDER_*）
    out_of_scope: str | None       # ride_hailing → 不报价转人工
    status: str                    # chatting / awaiting_confirm / confirmed
    assistant_reply: str           # 本轮最后一条助手消息（历史归档用）
    reuse_note: dict | None        # 报价复用记录（询价次数佐证）
    clarify_questions: list[str]


# ---------------------------------------------------------------------------
# 事件发射（SSE + 轨迹）
# ---------------------------------------------------------------------------

def _emit(event: str, data: dict, trace: dict | None = None) -> None:
    """经 LangGraph 自定义流通道发事件；app.py 翻译为 SSE 并写轨迹。"""
    try:
        get_stream_writer()({"event": event, "data": data, "trace": trace})
    except Exception:
        pass  # invoke()（非流式）场景下无写入器，静默跳过


def _node_start(state: RenewalState, node: str) -> float:
    _emit("node_start",
          {"trace_id": state.get("trace_id", ""), "session_id": state.get("session_id", ""),
           "node": node, "ts": trace_mod.now_iso()},
          {"record_type": "node_start", "node": node, "event": {"node": node}})
    return datetime.now().timestamp()


def _node_end(state: RenewalState, node: str, output: dict, t0: float) -> None:
    latency = round((datetime.now().timestamp() - t0) * 1000, 2)
    _emit("node_end",
          {"trace_id": state.get("trace_id", ""), "session_id": state.get("session_id", ""),
           "node": node, "output": output, "latency_ms": latency},
          {"record_type": "node_end", "node": node, "output": output, "latency_ms": latency})


def _steps(state: RenewalState) -> int:
    return int(state.get("steps", 0)) + 1


def _over_step_limit(state: RenewalState) -> bool:
    return int(state.get("steps", 0)) >= STEP_LIMIT


def _llm_result_trace(node: str, result) -> dict:
    spec = {"record_type": "llm_response", "node": node}
    if result is not None:
        spec["output"] = result.text
        # v1.0.5：本行到底是 llm 还是 rule、是否因故障降级，全部可查
        spec["mode"] = result.mode
        if getattr(result, "degraded", False):
            spec["degraded"] = True
            spec["error_type"] = getattr(result, "error_type", None)
        if result.tokens_in is not None:
            spec["tokens_in"] = result.tokens_in
        if result.tokens_out is not None:
            spec["tokens_out"] = result.tokens_out
    return spec


def _llm_event(state: RenewalState, node: str, result,
               extra_input: dict | None = None) -> dict | None:
    """记录一次 LLM 调用结果：`llm_response`（既有）+ 降级时 `llm_degraded`（v1.0.5）。

    返回降级标记 dict（无结果/未降级 → None）。节点把它并入 State.llm_degraded，
    供 app.py 在 done 帧给出 degraded=true —— SSE 与轨迹 JSONL 双证据，不再静默。
    """
    if result is None:
        return None
    spec = _llm_result_trace(node, result)
    if extra_input:
        spec["input"] = extra_input
    _emit("llm_response", {"node": node, "mode": result.mode}, spec)
    if not getattr(result, "degraded", False):
        return None
    marker = {
        "node": node,
        "code": LLM_UNAVAILABLE,
        "error_type": getattr(result, "error_type", None),
        "message": getattr(result, "error_message", None),
        "strict": False,
        "at": trace_mod.now_iso(),
    }
    _emit("llm_degraded", marker,
          {"record_type": "llm_degraded", "node": node, "output": marker,
           # SPEC v1.0.5：顶层可查询字段（便于 grep/指标聚合）
           "degraded": True, "error_type": marker["error_type"]})
    return marker


def ensure_disclaimer(content: str) -> tuple[str, bool]:
    """输出侧强制性免责声明（硬规矩 #3）。

    为何要在服务端强制而不是只写进系统提示：OWASP LLM01:2025 明确"系统提示里的
    限制不总被遵守，且可被注入绕过"；免责声明是合规底线，不能依赖模型自觉。
    轨迹额外记 `event.security.disclaimer_appended`，便于评测区分
    "模型自己带了"与"服务端兜底补的"（否则断言会被兜底逻辑悄悄变成永远通过）。
    """
    if config.DISCLAIMER in content:
        return content, False
    return content.rstrip() + "\n" + config.DISCLAIMER, True


def _message_event(state: RenewalState, node: str, content: str,
                   citations: list[dict] | None = None) -> None:
    """发 SSE message + 轨迹 assistant_message。citations 去掉 score。"""
    cites = [{k: c[k] for k in ("wiki_id", "source", "version")}
             for c in (citations or []) if "wiki_id" in c]
    content, appended = ensure_disclaimer(content)
    payload = {"role": "assistant", "content": content, "citations": cites}
    trace_spec: dict = {"record_type": "assistant_message",
                        "node": node, "output": content}
    if appended:
        trace_spec["event"] = {"security": {"disclaimer_appended": True}}
    _emit("message", payload, trace_spec)


def _citations_for_message(state: RenewalState, wanted: list[str]) -> list[dict]:
    """从已检索命中中取指定条目（未命中则补录，保证引用有据）。"""
    hits = list(state.get("citations") or [])
    have = {h["wiki_id"] for h in hits}
    searcher = wiki_search.get_searcher()
    for wid in wanted:
        if wid not in have:
            for e in searcher.entries:
                if e.wiki_id == wid:
                    hits.append({"wiki_id": e.wiki_id, "source": e.source,
                                 "version": e.version, "score": 0.0})
                    break
    return hits


# ---------------------------------------------------------------------------
# MCP 工具调用封装（带 SSE/轨迹事件与计时）
# ---------------------------------------------------------------------------

def _call_tool(state: RenewalState, node: str, tool: str, arguments: dict) -> dict:
    _emit("tool_call", {"trace_id": state.get("trace_id", ""), "tool": tool,
                        "arguments": arguments},
          {"record_type": "tool_call", "node": node, "input": arguments})
    rec_input = {"record_type": "tool_result", "node": node, "input": arguments}
    t0 = datetime.now().timestamp()
    dispatch: dict[str, Callable[..., dict]] = {
        "get_policy": mcp_bridge.get_policy,
        "query_quote": mcp_bridge.query_quote,
    }
    # 安全域（t9）：授权断言先于桥接（最小权限 / OWASP LLM06 Excessive Agency）。
    # 当前入参全部由服务端从会话状态构造；此锁保证“将来若有人把模型输出
    # 直接喂给工具”时不会静默越权。违规不抛到图外，而是转成工具错误回给节点。
    try:
        security.authorize_tool_args(tool, arguments, state.get("owner_id") or None)
    except security.SecurityViolation as e:
        result = {"error": {"code": e.code, "message": e.message}}
        _emit("tool_result", {"trace_id": state.get("trace_id", ""), "tool": tool,
                              "result": result, "error": result["error"]},
              {**rec_input, "output": result, "error": result["error"]})
        return result
    fn = dispatch[tool]
    attempts = 0
    result: dict = {}
    while True:
        attempts += 1
        try:
            result = fn(**arguments)
            break
        except mcp_bridge.ToolError as e:
            # 业务错误（参数非法/费率缺失/越权）：重试无意义，直接回给节点做纠正提示
            result = {"error": {"code": e.code, "message": e.message}}
            break
        except Exception as e:
            # 传输/协议类故障（stdio 子进程崩溃、连接中断、桥接层异常）：节点内重试。
            # 必须在这里做：LangGraph 的节点级 RetryPolicy 只在异常抛出节点时才生效，
            # 而本函数历史上把异常全收进返回值 → 图级重试永远不会触发（F1）。
            if attempts < TOOL_MAX_ATTEMPTS:
                time.sleep(min(0.5 * 2 ** (attempts - 1), 2.0))
                continue
            result = {"error": {"code": "TOOL_INTERNAL", "message": f"{type(e).__name__}: {e}"}}
            break
    latency = round((datetime.now().timestamp() - t0) * 1000, 2)
    _emit("tool_result", {"trace_id": state.get("trace_id", ""), "tool": tool,
                          "result": result,
                          **({"error": result["error"]} if "error" in result else {})},
          {**rec_input, "output": result, "latency_ms": latency,
           **({"error": result["error"]} if "error" in result else {})})
    return result


def _untrusted_history(history: list[dict]) -> list[dict]:
    """把历史里的用户消息包进不可信定界块（OWASP LLM01:2025 缓解措施 6）。

    原因：注入可以从上一轮潜入——本轮消息干净并不代表上下文干净。
    助手/系统消息是服务端生成的，视为可信，不动。
    """
    out: list[dict] = []
    for msg in history:
        if msg.get("role") == "user":
            out.append({**msg, "content": security.wrap_untrusted(msg.get("content") or "")})
        else:
            out.append(msg)
    return out


def _quote_expired(quote: dict) -> bool:
    try:
        return datetime.now().astimezone() > datetime.fromisoformat(quote["valid_until"])
    except Exception:
        return True


# ---------------------------------------------------------------------------
# 需求解析（GLM 结构化输出 + 关键词规则降级，备忘 a）
# ---------------------------------------------------------------------------

NEEDS_SCHEMA = {
    "type": "object",
    "properties": {
        "budget_yuan": {
            "type": ["integer", "null"],
            "description": "车主明确的预算上限（元）。未提及为 null",
        },
        "sum_insured_changes": {
            "type": "array",
            "description": "保额调整：险种代码与新的保额（元）",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string",
                             "enum": ["JQX", "CSX", "DSX", "YWYW", "SJRX", "CKRX", "BLPS"]},
                    "sum_insured": {"type": "integer"},
                },
                "required": ["code", "sum_insured"],
            },
        },
        "add_coverages": {
            "type": "array",
            "description": "新增投保险种代码",
            "items": {"type": "string",
                      "enum": ["CSX", "DSX", "YWYW", "SJRX", "CKRX", "BLPS"]},
        },
        "remove_coverages": {
            "type": "array",
            "description": "车主要求去掉的险种代码（注意：JQX 交强险法定不可删）",
            "items": {"type": "string"},
        },
        "use_nature_change": {
            "type": ["string", "null"],
            "description": "使用性质变更，如『网约车（营运）』；未提及为 null",
        },
        "terms_question": {
            "type": "boolean",
            "description": "本轮是否为条款/理赔规则咨询（而非续保方案调整）",
        },
    },
    "required": ["budget_yuan", "sum_insured_changes", "add_coverages",
                 "remove_coverages", "use_nature_change", "terms_question"],
}

NEEDS_SYSTEM = (
    "你是车险续保需求解析器。从车主消息中抽取结构化需求，只输出工具调用，"
    "不编造未提及的字段：没提到就给 null / 空数组。险种代码：JQX交强险、"
    "CSX车损险、DSX三者险、YWYW医保外用药、SJRX/CKRX车上人员（司机/乘客）、"
    "BLPS划痕险。三者险保额档位：50/100/200/300万。金额一律换算为元。"
)

_COVERAGE_ALIASES = [
    (re.compile(r"三者|第三者"), "DSX"),
    (re.compile(r"车损"), "CSX"),
    (re.compile(r"交强"), "JQX"),
    (re.compile(r"医保外|外用药"), "YWYW"),
    (re.compile(r"划痕"), "BLPS"),
    (re.compile(r"司机|座位.*司机|车上人员.*司机"), "SJRX"),
    (re.compile(r"乘客"), "CKRX"),
]


def _wan_to_yuan(m: re.Match) -> int:
    return int(float(m.group(1)) * 10000)


# 保额升降档的显式目标档位（“从100万升到200万” → 取 200 万）
_UPGRADE_RE = re.compile(r"(?:升到|提到|调到|增加到|提高到|涨到|改为|改成|调整到)\s*(\d+(?:\.\d+)?)\s*万")


def _rule_parse_needs(message: str) -> dict:
    """降级模式：关键词规则解析（备忘 a：缺配置时规则模式）。"""
    needs: dict = {
        "budget_yuan": None,
        "sum_insured_changes": [],
        "add_coverages": [],
        "remove_coverages": [],
        "use_nature_change": None,
        "terms_question": bool(TERMS_WORDS.search(message)),
    }
    # 预算
    mb = re.search(r"预算[^0-9]{0,6}(\d+(?:\.\d+)?)(万|w|W|元)|"
                   r"(\d+(?:\.\d+)?)(万|w|W|元)?[^。]{0,4}以内|不超过(\d+(?:\.\d+)?)(万|w|W|元)",
                   message)
    if mb:
        num = next(g for g in mb.groups() if g and re.match(r"^\d", g))
        unit = next((g for g in mb.groups() if g and not re.match(r"^\d", g)), "元")
        val = float(num) * (10000 if unit in ("万", "w", "W") else 1)
        needs["budget_yuan"] = int(val)
    # 用途变更（硬信号：不可依赖 LLM）
    if RIDE_HAILING_WORDS.search(message) and re.search(r"网约|滴滴|营运|跑单|拉客|顺风", message):
        needs["use_nature_change"] = "网约车（营运）"
    # 保额调整：险种 + 万
    for pat, code in _COVERAGE_ALIASES:
        m = re.search(r"(?:" + pat.pattern + r")[^0-9]{0,10}(?:保额)?[^0-9]{0,6}(\d+(?:\.\d+)?)万", message)
        if m:
            # 升降档语义修正（AC-06 根因）：本正则取首个数字，遇到
            # 「三者险从 100 万升到 200 万」会把旧的 100 万当成目标档位。
            # 规则：消息里出现显式目标动词（升到/调到…）时，以动词后的档位为准。
            up = _UPGRADE_RE.search(message)
            sum_insured = (int(float(up.group(1)) * 10000) if up
                           else int(float(m.group(1)) * 10000))
            needs["sum_insured_changes"].append(
                {"code": code, "sum_insured": sum_insured})
    # 新增险种
    for pat, code in _COVERAGE_ALIASES:
        if code in ("JQX",):
            continue
        if re.search(r"(加|买|投|上)个?(?:" + pat.pattern + r")", message):
            needs["add_coverages"].append(code)
    # 删除险种
    for pat, code in _COVERAGE_ALIASES:
        if re.search(r"(不要|去掉|删掉|取消|退掉|不投)[^。]{0,8}(?:" + pat.pattern + r")", message):
            needs["remove_coverages"].append(code)
    return needs


def _merge_needs(llm_needs: dict | None, rule_needs: dict) -> dict:
    """GLM 结果为主、规则结果补缺；硬信号（用途变更）永远以规则为准。"""
    merged = dict(rule_needs)
    if llm_needs:
        for k in ("budget_yuan", "use_nature_change", "terms_question"):
            if merged.get(k) in (None, False) and llm_needs.get(k) not in (None, False):
                merged[k] = llm_needs[k]
        for k in ("sum_insured_changes", "add_coverages", "remove_coverages"):
            if llm_needs.get(k):
                merged[k] = llm_needs[k]
    return merged

def _accumulate_needs(prev: dict, delta: dict) -> dict:
    """跨轮需求累积：本轮解析视为增量，叠加到常驻需求上（同险种代码后者覆盖前者）。

    - budget / use_nature：本轮未提及则沿用旧值（改口则覆盖 → 记忆撤回在 parse_needs 记录）
    - sum_insured_changes：按 code 合并，本轮新值覆盖旧值
    - add / remove：累积互斥（后说的动作抵消先前的相反动作）
    """
    merged = dict(delta)
    for k in ("budget_yuan", "use_nature_change"):
        if merged.get(k) is None:
            merged[k] = prev.get(k)
    chg = {c["code"]: c for c in prev.get("sum_insured_changes") or []}
    for c in delta.get("sum_insured_changes") or []:
        chg[c["code"]] = c
    merged["sum_insured_changes"] = list(chg.values())
    removes = list(dict.fromkeys((prev.get("remove_coverages") or [])
                                 + (delta.get("remove_coverages") or [])))
    adds = list(dict.fromkeys((prev.get("add_coverages") or [])
                              + (delta.get("add_coverages") or [])))
    rem_set, add_set = set(removes), set(adds)
    merged["add_coverages"] = [c for c in adds if c not in rem_set]
    merged["remove_coverages"] = [c for c in removes if c not in add_set]
    merged["terms_question"] = delta.get("terms_question", False)
    return merged


def _needs_fingerprint(needs: dict) -> str:
    return json.dumps(needs, ensure_ascii=False, sort_keys=True)


def _detect_corrections(state: RenewalState, needs: dict, message: str) -> list[dict]:
    """不可行动作识别（AC-07/08/09）：返回纠正项，不进入询价。"""
    corrections: list[dict] = []
    rates = json.loads((config.SYNTHETIC_DIR / "rates.json").read_text(encoding="utf-8"))
    # 停售险种
    for kw, code in DISCONTINUED_KEYWORDS.items():
        if kw in message:
            d = next((x for x in rates["discontinued_coverages"] if x["code"] == code), None)
            if d:
                corrections.append({
                    "code": "COVERAGE_DISCONTINUED",
                    "coverage": d["name"],
                    "note": f"{d['name']}已自 {d['discontinued_since']} 停售：{d['note']}",
                    "replacement": d["replacement"],
                    "wiki_id": "wiki-csx",
                })
    # 删除交强险
    if re.search(r"(不要|去掉|删掉|取消|退掉|不投)[^。]{0,8}交强", message) \
            or "JQX" in (needs.get("remove_coverages") or []):
        corrections.append({
            "code": "JQX_REQUIRED",
            "coverage": "交强险",
            "note": "交强险为法定强制保险，不可删除",
            "replacement": None,
            "wiki_id": "wiki-jqx",
        })
    # 附加险前置
    policy = (state.get("policy") or {}).get("policy") or {}
    has_code = {c["code"] for c in policy.get("coverages", [])}
    added = set(needs.get("add_coverages") or [])
    kept = has_code - set(needs.get("remove_coverages") or [])
    if ("YWYW" in added or "YWYW" in has_code) and not (kept | added) & {"DSX", "SJRX", "CKRX"} \
            and "DSX" in (needs.get("remove_coverages") or []):
        corrections.append({
            "code": "RIDER_PREREQUISITE_MISSING",
            "coverage": "医保外用药责任险",
            "note": "医保外用药为附加险，需同单投保三者险（DSX）或车上人员责任险",
            "replacement": "DSX",
            "wiki_id": "wiki-ywyw",
        })
    return corrections


# ---------------------------------------------------------------------------
# 险种选择构建（needs × 原保单基线 → coverage_selection）
# ---------------------------------------------------------------------------

def _build_selection(state: RenewalState, needs: dict) -> list[dict]:
    policy = (state.get("policy") or {}).get("policy") or {}
    base = {c["code"]: dict(c) for c in policy.get("coverages", [])}
    sel: dict[str, dict] = {
        code: ({"code": code, "sum_insured": int(c["sum_insured"])}
               # JQX（交强险）保额为法定固定值，非用户可选：不进选择，
               # 与 quote_node 对照组 base_sel 归一化口径一致（SPEC v1.0.2）
               if c.get("sum_insured") and code != "JQX" else {"code": code})
        for code, c in base.items()
    }
    # 保额调整
    for ch in needs.get("sum_insured_changes") or []:
        code = ch.get("code")
        if code in sel or code in ("DSX", "CSX", "SJRX", "CKRX", "YWYW"):
            sel[code] = {"code": code, "sum_insured": int(ch["sum_insured"])}
    # 删除（JQX 不可删，parse_needs 已纠正，此处兜底跳过）
    for code in needs.get("remove_coverages") or []:
        if code != "JQX":
            sel.pop(code, None)
    # 新增（缺省 sum_insured 交给报价服务取费率表默认）
    for code in needs.get("add_coverages") or []:
        if code not in sel:
            sel[code] = {"code": code}
    # CSX 沿用原保单车损保额（报价服务缺省规则）
    if "CSX" in sel and "sum_insured" not in sel["CSX"] and "CSX" in base:
        sel["CSX"]["sum_insured"] = base["CSX"]["sum_insured"]
    out = list(sel.values())
    out.sort(key=lambda x: (x["code"] != "JQX", x["code"]))
    return out


def _rate_default_sum() -> dict[str, int]:
    """费率表中带固定 sum_insured 默认值的险种（懒加载缓存，rates.json v2025.1：
    JQX=200000 / YWYW=50000 / BLPS=5000）。"""
    global _RATE_DEFAULT_SUM_CACHE
    if _RATE_DEFAULT_SUM_CACHE is None:
        rates = json.loads(
            (config.SYNTHETIC_DIR / "rates.json").read_text(encoding="utf-8"))
        _RATE_DEFAULT_SUM_CACHE = {
            code: int(spec["sum_insured"])
            for code, spec in (rates.get("base_premium") or {}).items()
            if spec.get("sum_insured")
        }
    return _RATE_DEFAULT_SUM_CACHE


def _selection_key(selection: list[dict], use_nature: str | None) -> str:
    """同语义选择 → 同 key（SPEC v1.0.2 归一化规则）：
    剔除『等于费率表默认值』的 sum_insured——固定保额险种（JQX/YWYW/BLPS）
    保额由费率表给定而非用户选择，携带与否不改变报价语义；否则同语义
    选择会因携带方式不同（原保单带入 vs 报价服务缺省折叠）生成不同 key，
    幂等/复用失效导致重复询价（eval AC-05）。"""
    defaults = _rate_default_sum()
    norm = sorted(
        (it["code"],
         None if ("sum_insured" not in it or it.get("sum_insured") == defaults.get(it["code"]))
         else it.get("sum_insured"))
        for it in selection)
    return json.dumps({"sel": norm, "use": use_nature},
                      ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# 节点实现
# ---------------------------------------------------------------------------

def intake(state: RenewalState) -> RenewalState:
    """意图识别（确定性关键词规则，LLM/规则模式行为一致）。"""
    t0 = _node_start(state, "intake")
    message = state.get("message", "")
    status = state.get("status") or "chatting"
    intent = "chitchat"
    if status == "awaiting_confirm" and CONFIRM_WORDS.search(message):
        intent = "confirm"
    elif (TERMS_WORDS.search(message) and not RENEWAL_WORDS.search(message)):
        # P1a 修复（评审 review.md AC-08）：停售险种关键词（如“我想买发动机进水险”）
        # 必须走 renewal → parse_needs._detect_corrections 产出 COVERAGE_DISCONTINUED
        # 纠正码，不再误路由到条款咨询绕过纠正；纯条款问答（无续保/停售信号）仍走 terms。
        intent = "terms"
    elif RENEWAL_WORDS.search(message) or CONFIRM_WORDS.search(message) \
            or any(kw in message for kw in DISCONTINUED_KEYWORDS):
        intent = "renewal"
    output = {"intent": intent, "status": status}
    _node_end(state, "intake", output, t0)
    return {"intent": intent, "steps": _steps(state)}


def get_policy_node(state: RenewalState) -> RenewalState:
    """调 MCP get_policy 装载保单上下文（AC-01/02/04：查无此人不编造）。"""
    t0 = _node_start(state, "get_policy")
    owner_id = state.get("owner_id", "")
    result = _call_tool(state, "get_policy", "get_policy", {"owner_id": owner_id})
    policy_ctx = result if result.get("found") else None
    output = {"found": bool(policy_ctx),
              "days_to_expiry": result.get("days_to_expiry"),
              "expiring_soon": result.get("expiring_soon")}
    _node_end(state, "get_policy", output, t0)
    update: RenewalState = {"policy": policy_ctx, "steps": _steps(state)}
    if policy_ctx:
        update["vin"] = policy_ctx["owner"]["vin"]
        # AC-01：临期主动提示
        if policy_ctx.get("expiring_soon"):
            _message_event(
                state, "get_policy",
                f"提示：您的保单（{policy_ctx['policy']['policy_id']}）"
                f"将于 {policy_ctx['policy']['end_date']} 到期，"
                f"距到期仅 {policy_ctx['days_to_expiry']} 天，建议尽快续保以免脱保。\n"
                f"{config.DISCLAIMER}")
    return update


def parse_needs(state: RenewalState) -> RenewalState:
    """解析需求：GLM 结构化输出优先，关键词规则降级（备忘 a/b）。

    - 需求变更 → needs_version+1，旧偏好移入 invalidated（记忆撤回，轨迹留痕）
    - 连续 2 轮无新信息 → exit_reason=no_progress
    - 营运用途 → out_of_scope=ride_hailing（不报价转人工，备忘 d）
    - 不可行动作 → corrections（纠正提示，AC-07/08/09）
    - 保额调整但未给档位 → clarify（备忘 a）
    """
    t0 = _node_start(state, "parse_needs")
    message = state.get("message", "")
    client = get_client()
    # 上下文预算（记忆机制域）：memory.prompt_context 统一产出
    #   ① 按 token 预算裁剪的历史（替代固定条数 history[-8:]）
    #   ② 被裁轮次的确定性滚动摘要
    #   ③ 跨会话长期记忆简报（带来源/新鲜度）
    mem_system, mem_history = memory.prompt_context(
        state, budget_tokens=config.memory_prompt_budget())

    rule_needs = _rule_parse_needs(message)
    llm_needs, llm_res = None, None
    marker = None                     # LLM 降级标记（v1.0.5）
    if client.available:
        # LLM01 缓解措施 6：外部内容隔离——历史里的用户消息与本轮消息
        # 均包进不可信定界块，系统提示追加安全约束（幂等）。
        msgs = _untrusted_history(mem_history) + [
            {"role": "user", "content": security.wrap_untrusted(message)}]
        _emit("llm_call", {"node": "parse_needs"},
              {"record_type": "llm_call", "node": "parse_needs",
               "input": {"system": "needs-extractor(tool-use)", "messages": msgs}})
        llm_needs, llm_res = client.chat_tool_json(
            system=security.guard_system_prompt(NEEDS_SYSTEM + mem_system),
            messages=msgs,
            tool_name="extract_needs",
            tool_description="抽取车主续保需求为结构化 JSON",
            input_schema=NEEDS_SCHEMA, node="parse_needs")
        marker = _llm_event(state, "parse_needs", llm_res, {"tool": "extract_needs"})

    needs = _merge_needs(llm_needs, rule_needs)
    prev_needs = state.get("needs") or {}
    fresh_needs = needs                      # 本轮原始解析（澄清判断用）
    # 跨会话记忆：仅当车主显式指代既往会话（「上次 / 还是按老方案」）时，把长期记忆
    # 当作**默认值底座**，且优先级低于本轮解析与会话内累积。依据 Oracle 2026-06-05
    # 的冲突优先级（当前消息 > 结构化记忆）：记忆是证据不是事实，错用会直接改保费。
    memory_delta, memory_seeded = memory.recall_needs(state)
    if state.get("intent") == "confirm" and (prev_needs or memory_seeded):
        needs = dict(prev_needs or memory_delta)  # 确认轮不改需求，避免误标记失效
    elif prev_needs and memory_seeded:
        needs = _accumulate_needs(
            _accumulate_needs(prev_needs, memory_delta), needs)   # 会话内 > 长期记忆
    elif prev_needs:
        needs = _accumulate_needs(prev_needs, needs)  # 常驻需求累积（备忘 b）
    elif memory_seeded:
        needs = _accumulate_needs(memory_delta, needs)  # 新会话：记忆打底

    # ---- 记忆撤回：同事实多版本只留最新，旧值移入 invalidated ----
    invalidated = list(state.get("invalidated") or [])
    version = int(state.get("needs_version") or 0)
    fp_now, fp_prev = _needs_fingerprint(needs), _needs_fingerprint(prev_needs)
    if prev_needs and fp_now != fp_prev:
        version += 1
        for key in set(list(prev_needs) + list(needs)):
            if prev_needs.get(key) != needs.get(key) and prev_needs.get(key) not in (None, [], False):
                invalidated.append({
                    "field": key, "old": prev_needs.get(key), "new": needs.get(key),
                    "needs_version": version, "reason": "车主改口，旧偏好失效",
                })
    elif not prev_needs:
        version = max(version, 1)

    # ---- 无进展检测（备忘 g：连续 2 轮无新信息）----
    renewal_like = state.get("intent") in ("renewal", "compare")
    no_progress = int(state.get("no_progress_rounds") or 0)
    info_added = (not prev_needs) or fp_now != fp_prev
    no_progress = 0 if info_added else no_progress + (1 if renewal_like else 0)

    corrections = _detect_corrections(state, needs, message)
    out_of_scope = "ride_hailing" if needs.get("use_nature_change") and \
        "营运" in (needs.get("use_nature_change") or "") else None

    # ---- 澄清判断：保额调整无档位值 ----
    clarify_questions: list[str] = []
    if not out_of_scope and not corrections:
        ambiguous = re.search(r"三者|第三者|保额", message) and \
            re.search(r"提高|升|调整|调高|改", message) and \
            not fresh_needs.get("sum_insured_changes") and \
            state.get("intent") != "confirm"
        if ambiguous:
            clarify_questions = [
                "您希望把第三者责任险保额调整到多少？可选档位：50万 / 100万 / 200万 / 300万"
            ]

    confirmed = state.get("intent") == "confirm"
    sufficient = not clarify_questions

    wanted = [c["wiki_id"] for c in corrections]
    if out_of_scope:
        wanted.append("wiki-ride-hailing")

    # 记忆机制域可观测性：不新增轨迹 record_type（SPEC §5 封闭枚举），
    # 把「本轮 context package 预算 + 记忆补了哪些字段」放进 parse_needs 的 node_end.output。
    mem_report = memory.context_report({**state, "history": mem_history})
    output = {
        "needs_version": version,
        "invalidated": [i for i in invalidated if i.get("needs_version") == version],
        "no_progress_rounds": no_progress,
        "corrections": corrections or None,
        "out_of_scope": out_of_scope,
        "needs_sufficient": sufficient,
        "mode": "llm" if llm_needs else "rule",
        "memory": {**mem_report, "seeded": memory_seeded},
    }
    _node_end(state, "parse_needs", output, t0)
    update: RenewalState = {
        "needs": needs, "needs_version": version, "invalidated": invalidated,
        "no_progress_rounds": no_progress, "needs_sufficient": sufficient,
        "steps": _steps(state), "clarify_questions": clarify_questions,
        "corrections": corrections, "out_of_scope": out_of_scope,
        "wanted_wiki_ids": wanted,
        "memory_seeded": memory_seeded, "memory_ctx": mem_report,
    }
    if marker:  # v1.0.5：降级留痕随 State 走，供 done 帧汇总
        update["llm_degraded"] = list(state.get("llm_degraded") or []) + [marker]
    if confirmed:
        update["confirmed"] = True
    return update


def clarify(state: RenewalState) -> RenewalState:
    """信息不足：澄清问题 + 挂起等待用户（finish_reason=await_user）。"""
    t0 = _node_start(state, "clarify")
    questions = state.get("clarify_questions") or ["请补充您的续保需求（如险种增删/保额调整/预算）"]
    content = "为了给您准确报价，还需要确认：\n" + \
        "\n".join(f"- {q}" for q in questions) + f"\n{config.DISCLAIMER}"
    _emit("clarify", {"questions": questions})
    _message_event(state, "clarify", content)
    _node_end(state, "clarify", {"questions": questions}, t0)
    return {"await_flag": True, "finish_reason": "await_user",
            "assistant_reply": content, "steps": _steps(state)}


def retrieve_terms(state: RenewalState) -> RenewalState:
    """BM25 检索 wiki/ 条款 Top-3（SPEC §5：retrieval 事件带来源+版本+score）。"""
    t0 = _node_start(state, "retrieve_terms")
    message = state.get("message", "")
    needs = state.get("needs") or {}
    query = message
    if needs.get("sum_insured_changes") or needs.get("budget_yuan"):
        query += " 三者险保额档位 保费 费率"
    searcher = wiki_search.get_searcher()
    citations: list[dict] = []
    excerpts: dict = {}
    if searcher.available:
        entries, scores = searcher.search_with_score(query, top_k=3)
        citations = wiki_search.hits_for_trace(entries, scores)
        for e in citations:
            ent = next(x for x in searcher.entries if x.wiki_id == e["wiki_id"])
            excerpts[e["wiki_id"]] = wiki_search.excerpt(ent, 400, query)
        _emit("retrieval", {"hits": citations},
              {"record_type": "retrieval", "node": "retrieve_terms",
               "input": query, "output": citations})

    # parse_needs 要求必含的条目（纠正/超范围引用）
    wanted = list(state.get("wanted_wiki_ids") or [])
    have = {c["wiki_id"] for c in citations}
    for wid in wanted:
        if wid not in have:
            ent = next((x for x in searcher.entries if x.wiki_id == wid), None)
            if ent:
                citations.append({"wiki_id": ent.wiki_id, "source": ent.source,
                                  "version": ent.version, "score": 0.0})
                excerpts[ent.wiki_id] = wiki_search.excerpt(ent, 400, query)

    # ---- 路由决策 ----
    intent = state.get("intent")
    need_quote = (
        intent in ("renewal", "compare")
        and not state.get("corrections")
        and not state.get("out_of_scope")
        and not state.get("confirmed")
        and (state.get("policy") or {}).get("found", False)
    )
    # LLM-Wiki 全量上下文模式（Karpathy 2026：小语料暴力上下文优于切片）：
    # 语料在预算内时注入全部条目，RRF Top-K 仍作为引用归因（citations）与轨迹。
    # 引用溯源：未接地的命中（词面无任何重叠）降权剔除，防“晓辩式引用失败”。
    grounding = wiki_search.verify_citations(query, [
        next(x for x in searcher.entries if x.wiki_id == c["wiki_id"])
        for c in citations if c["score"] > 0]) if citations else []
    ungrounded = {g["wiki_id"] for g in grounding if not g["grounded"]}
    if ungrounded and len(citations) > len(ungrounded):
        citations = [c for c in citations if c["wiki_id"] not in ungrounded]
        excerpts = {k: v for k, v in excerpts.items() if k not in ungrounded}
    wiki_full = wiki_search.llm_wiki_context(searcher.entries)
    expected = sum(len(e.body) + len(f"[{e.wiki_id}] {e.title}（{e.source} {e.version}）\n")
                   for e in searcher.entries) + 2 * (len(searcher.entries) - 1)  # 含 \n\n 连接符
    retrieval_mode = "llm-wiki-full" if len(wiki_full) >= expected else "rrf-topk"
    if retrieval_mode == "llm-wiki-full":
        # 小语料（当前 wiki 约 7KB）：全量注入带锚点条目，引用仍按 RRF 归因
        for e in searcher.entries:
            excerpts.setdefault(e.wiki_id, f"{e.title}（{e.source} {e.version}）\n{e.body}")
    _node_end(state, "retrieve_terms",
              {"hits": [c["wiki_id"] for c in citations], "need_quote": need_quote,
               "mode": retrieval_mode, "grounded": [g["wiki_id"] for g in grounding],
               # 2026-11-17 知识检索域整改：引用可审计到章节（wiki_id#章节）+ 证据覆盖率，
               # 只进节点详情，不污染 retrieval 事件 output 的 SPEC §5 四字段契约。
               "anchors": {g["wiki_id"]: g["anchor"] for g in grounding
                           if g["wiki_id"] in {c["wiki_id"] for c in citations}},
               "evidence_coverage": {g["wiki_id"]: g["coverage"] for g in grounding
                                     if g["wiki_id"] in {c["wiki_id"] for c in citations}}}, t0)
    return {"citations": citations, "excerpts": excerpts, "need_quote": need_quote,
            "steps": _steps(state)}


def _do_quote(state: RenewalState, selection: list[dict],
              use_nature: str | None) -> dict:
    """单次询价 + 登记 quote_book（/confirm 校验依据）。"""
    result = _call_tool(state, "quote", "query_quote", {
        "vin": state.get("vin", ""), "coverage_selection": selection,
        **({"use_nature": use_nature} if use_nature else {}),
    })
    if "error" in result:
        return result
    quote_book.register(result)
    return result


def quote_node(state: RenewalState) -> RenewalState:
    """询价节点（备忘 c）：
    - 险种选择与用途均未变 且 最新报价仍在 valid_until 内 → 复用，不重复调
      query_quote（轨迹无 tool_call 记录可证）；否则重新询价
    - 同时取原方案续保报价作对照组（skill 第 3 步）
    """
    t0 = _node_start(state, "quote")
    needs = state.get("needs") or {}
    use_nature = needs.get("use_nature_change")
    selection = _build_selection(state, needs)
    key = _selection_key(selection, use_nature)

    prev = state.get("latest_quote")
    reused = None
    if prev and prev.get("coverage_selection_key") == key \
            and not _quote_expired(prev) and "error" not in prev:
        reused = prev

    quotes = list(state.get("quotes") or [])
    reuse_note = None
    error = None
    if reused is not None:
        latest = reused
        reuse_note = {"quote_id": reused["quote_id"],
                      "reason": "需求未变化或仅预算调整，且报价仍在有效期内，复用已有报价"}
        _emit("quote", {"quote_id": latest["quote_id"],
                        "quote_version": latest["quote_version"],
                        "premium_total": latest["premium_total"],
                        "valid_until": latest["valid_until"],
                        "line_items": latest["line_items"]})
    else:
        latest = _do_quote(state, selection, use_nature)
        if "error" in latest:
            error = latest["error"]
        else:
            latest = {**latest, "coverage_selection_key": key,
                      "coverage_selection": selection}
            quotes.append({k: v for k, v in latest.items()
                           if k in ("quote_id", "quote_version", "premium_total",
                                    "valid_until", "rates_version")})
            _emit("quote", {"quote_id": latest["quote_id"],
                            "quote_version": latest["quote_version"],
                            "premium_total": latest["premium_total"],
                            "valid_until": latest["valid_until"],
                            "line_items": latest["line_items"]})

    # 对照组：原方案续保报价（仅在险种选择有变化时才额外询价）
    baseline = state.get("baseline_quote")
    policy = (state.get("policy") or {}).get("policy") or {}
    base_sel = [{"code": c["code"],
                 **({"sum_insured": c["sum_insured"]} if c["code"] != "JQX" else {})}
                for c in policy.get("coverages", [])]
    base_key = _selection_key(base_sel, None)
    if error is None:
        if base_key == key and reused is None:
            baseline = latest
        elif not baseline or baseline.get("coverage_selection_key") != base_key \
                or _quote_expired(baseline):
            if "error" in (baseline or {}) or base_key != key:
                bres = _do_quote(state, base_sel, None)
                if "error" not in bres:
                    baseline = {**bres, "coverage_selection_key": base_key,
                                "coverage_selection": base_sel}

    _node_end(state, "quote", {
        "quote_id": (latest or {}).get("quote_id"),
        "reused": reused is not None,
        "baseline_quote_id": (baseline or {}).get("quote_id"),
        **({"error": error} if error else {}),
    }, t0)
    update: RenewalState = {"quotes": quotes, "steps": _steps(state)}
    if error:
        update["error"] = error
        update["need_quote"] = False
    else:
        update["latest_quote"] = latest
        update["baseline_quote"] = baseline
        update["reuse_note"] = reuse_note
    return update


def _compare_text(state: RenewalState) -> tuple[str, list[dict]]:
    """按 skill 七步生成比较文案（先保障后价格），返回 (文本, citations)。"""
    policy_ctx = state.get("policy") or {}
    policy = policy_ctx.get("policy") or {}
    needs = state.get("needs") or {}
    latest = state.get("latest_quote") or {}
    baseline = state.get("baseline_quote") or latest
    old_by_code = {c["code"]: c for c in policy.get("coverages", [])}
    new_by_code = {li["code"]: li for li in latest.get("line_items", [])}
    # baseline（原方案对照）只参与下方价格行，不进保障差异表；原这里预建了
    # base_by_code 但未使用（ruff F841），2026-11-13 清理死代码。

    def _fmt(si, prem):
        return f"{(si or 0) / 10000:.0f}万 / {prem or 0:.2f}元"

    rows = []
    for code in sorted(set(old_by_code) | set(new_by_code)):
        name = (new_by_code.get(code) or old_by_code.get(code) or {}).get("name", code)
        old, new = old_by_code.get(code), new_by_code.get(code)
        if old and new:
            diff = "保额调整" if old["sum_insured"] != new["sum_insured"] else "维持"
        elif old:
            diff = "新方案删除"
        else:
            diff = "新方案新增"
        rows.append(f"| {name} | {_fmt(old and old['sum_insured'], old and old['premium'])} "
                    f"| {_fmt(new and new['sum_insured'], new and new['premium'])} | {diff} |")

    old_total = policy.get("premium_total")
    base_total = baseline.get("premium_total")
    new_total = latest.get("premium_total")
    delta = round(new_total - base_total, 2) if new_total and base_total else None
    factors = latest.get("factors_applied") or {}

    cite_ids = []
    if "DSX" in new_by_code and "DSX" in old_by_code and \
            old_by_code["DSX"]["sum_insured"] != new_by_code["DSX"]["sum_insured"]:
        cite_ids.append("wiki-dsx")
    if delta is not None and delta > 0:
        cite_ids.append("wiki-rate-surcharge")
    citations = _citations_for_message(state, cite_ids)

    lines = [
        "【模拟报价 · 合成数据】续保方案比较"
        f"（费率版本 {latest.get('rates_version', 'n/a')}）",
        "",
        "## 一、保障差异（先看保障，再看价格）",
        "| 险种 | 原保单（保额/保费） | 新方案（保额/保费） | 差异 |",
        "|---|---|---|---|",
        *rows,
        "",
        "## 二、价格对比",
        f"- 原保单上年总保费：{old_total:.2f} 元",
        f"- 原方案按现行费率续保（对照）：{base_total:.2f} 元"
        f"（报价 {baseline.get('quote_id', '-')}，24h 内有效）",
        f"- 新方案总保费：{new_total:.2f} 元"
        f"（报价 {latest.get('quote_id', '-')} v{latest.get('quote_version', 1)}，"
        f"{latest.get('valid_until', '-')} 前有效）",
    ]
    if delta is not None:
        arrow = "上浮" if delta > 0 else "下降"
        lines.append(f"- 与原方案续保价相比：{arrow} {abs(delta):.2f} 元")
    lines += [
        f"- 试算系数：NCD {factors.get('ncd_coefficient', '-')} · "
        f"用途 {factors.get('use_nature_factor', '-')} · "
        f"车龄 {factors.get('vehicle_age_factor', '-')}（仅作用于车损险部分）",
    ]
    if delta is not None and delta > 0:
        excerpts = state.get("excerpts") or {}
        sur = excerpts.get("wiki-rate-surcharge", "")
        lines += [
            "",
            "## 三、保费上浮说明",
            f"本次上浮主要来自保额/险种结构调整与费率系数"
            f"（费率版本 {latest.get('rates_version', '-')}）。"
            "NCD 无赔款优待系数规则：连续无出险年份越长系数越低，出险则上浮。",
        ]
        if sur:
            lines.append(f"条款摘录：{sur}")
    budget = needs.get("budget_yuan")
    if budget and new_total:
        over = round(new_total - budget, 2)
        if over > 0:
            lines.append(f"\n⚠️ 预算提示：新方案总保费超出您 {budget} 元预算 {over:.2f} 元，"
                         "可考虑调低三者险档位或减附加险。")
        else:
            lines.append(f"\n✅ 预算匹配：新方案总保费在您 {budget} 元预算内"
                         f"（剩余 {abs(over):.2f} 元）。")
    cite_str = "；".join(f"[{c['wiki_id']} {c['source']} {c['version']}]"
                         for c in citations) or "（本表数字均来自报价服务计算）"
    lines += ["", f"依据：{cite_str}", "",
              "是否按新方案投保？您也可以选择按原方案续保（见上方对照价）。"]
    return "\n".join(lines), citations


def compare(state: RenewalState) -> RenewalState:
    """比较节点（备忘 e）：skill 七步——先保障差异后价格，citations 带来源+版本。"""
    t0 = _node_start(state, "compare")
    text, citations = _compare_text(state)

    # LLM 模式：在确定性表格基础上追加一段顾问建议（数字已给定，禁止编造）
    client = get_client()
    marker = None                     # LLM 降级标记（v1.0.5）
    if client.available:
        # 记忆机制域：统一走 token 预算 + 滚动摘要 + 记忆简报（旧实现是固定 [-6:]）
        mem_system, mem_history = memory.prompt_context(
            state, budget_tokens=config.memory_chat_budget(), legacy_tail=6)
        sys = security.guard_system_prompt(
            "你是续保顾问。基于给定的比较表写 3 句以内的建议，先保障后价格；"
            "只能使用材料中出现的数字，不得引入任何新数字或新条款；"
            "结尾提醒报价 24 小时有效。" + config.DISCLAIMER + mem_system)
        _emit("llm_call", {"node": "compare"},
              {"record_type": "llm_call", "node": "compare",
               "input": {"system": "advisor", "messages": 1 + len(mem_history)}})
        res = client.chat(system=sys, messages=_untrusted_history(mem_history) + [
            {"role": "user", "content": f"比较表：\n{text}"}], node="compare")
        marker = _llm_event(state, "compare", res)
        if res.mode == "llm" and res.text.strip():
            text = text + "\n\n顾问建议：" + res.text.strip()

    _message_event(state, "compare", text, citations)
    _node_end(state, "compare", {"quote_id": (state.get("latest_quote") or {}).get("quote_id"),
                                 "citations": [c["wiki_id"] for c in citations]}, t0)
    update: RenewalState = {"comparison": {"text": text}, "citations": citations,
                            "assistant_reply": text, "steps": _steps(state)}
    if marker:
        update["llm_degraded"] = list(state.get("llm_degraded") or []) + [marker]
    return update


def await_confirm_node(state: RenewalState) -> RenewalState:
    """输出待确认项，挂起等待用户确认（SPEC §4.1 await_confirm 事件）。"""
    t0 = _node_start(state, "await_confirm")
    latest = state.get("latest_quote") or {}
    summary = (f"新方案总保费 {latest.get('premium_total', 0):.2f} 元"
               f"（{latest.get('quote_id', '-')} v{latest.get('quote_version', 1)}，"
               f"{latest.get('valid_until', '-')} 前确认有效，模拟报价）")
    confirmables = [
        f"按新方案投保（总保费 {latest.get('premium_total', 0):.2f} 元）",
    ]
    baseline = state.get("baseline_quote")
    if baseline and baseline.get("quote_id") != latest.get("quote_id"):
        confirmables.append(
            f"按原方案续保（总保费 {baseline.get('premium_total', 0):.2f} 元）")
    _emit("await_confirm", {"quote_id": latest.get("quote_id"),
                            "summary": summary, "confirmables": confirmables})
    _node_end(state, "await_confirm", {"quote_id": latest.get("quote_id")}, t0)
    return {"await_flag": True, "finish_reason": "await_user",
            "status": "awaiting_confirm", "steps": _steps(state)}


def confirm_node(state: RenewalState) -> RenewalState:
    """确认节点（备忘 f）：校验 quote_version 与 valid_until；
    QUOTE_EXPIRED / QUOTE_VERSION_STALE → 路由回 quote 重新报价。"""
    t0 = _node_start(state, "confirm")
    latest = state.get("latest_quote") or {}
    confirm_error = None
    order = None
    if not latest.get("quote_id"):
        confirm_error = "QUOTE_NOT_FOUND"
    else:
        current = quote_book.get_quote(latest["quote_id"])
        if current is None:
            confirm_error = "QUOTE_NOT_FOUND"
        elif quote_book.is_expired(current):
            confirm_error = "QUOTE_EXPIRED"
        elif int(current["quote_version"]) != int(latest.get("quote_version", 1)):
            confirm_error = "QUOTE_VERSION_STALE"
        else:
            order = quote_book.create_order(current)
    output: dict = {"quote_id": latest.get("quote_id")}
    update: RenewalState = {"steps": _steps(state)}
    if confirm_error:
        output["error"] = confirm_error
        _emit("error", {"code": confirm_error, "node": "confirm",
                        "message": f"确认失败：{confirm_error}，将重新报价"},
              {"record_type": "error", "node": "confirm",
               "error": {"code": confirm_error, "message": "确认失败，走重新报价分支"}})
        update["confirm_error"] = confirm_error
        update["confirmed"] = False
    else:
        _emit("confirmed", {"order_id": order["order_id"],
                            "quote_id": latest["quote_id"]})
        output["order_id"] = order["order_id"]
        update["finish_reason"] = "end"
        update["status"] = "confirmed"
        update["confirmed"] = False
        _message_event(
            state, "confirm",
            f"已确认投保（模拟）：订单号 {order['order_id']}，"
            f"报价 {latest['quote_id']}，总保费 {order['premium_total']:.2f} 元，"
            f"生效 {order['effective_date']} 至 {order['end_date']}。\n{config.DISCLAIMER}")
    _node_end(state, "confirm", output, t0)
    return update


def fallback(state: RenewalState) -> RenewalState:
    """兜底：条款直答 / 闲聊 / 查无保单 / 纠正提示 / 超范围转人工 / 退出说明。"""
    t0 = _node_start(state, "fallback")
    # 退出原因（备忘 g：步数上限/无进展，触发原因写入轨迹 node_end.output）
    if int(state.get("steps", 0)) >= STEP_LIMIT:
        exit_reason = "step_limit"
    elif int(state.get("no_progress_rounds") or 0) >= NO_PROGRESS_LIMIT:
        exit_reason = "no_progress"
    else:
        exit_reason = None
    intent = state.get("intent")
    message = state.get("message", "")
    citations: list[dict] = []
    client = get_client()
    marker = None                     # LLM 降级标记（v1.0.5）

    if not (state.get("policy") or {}).get("found") and intent in ("renewal", "confirm"):
        text = (f"未找到车主 {state.get('owner_id', '')} 的保单（合成数据中不存在），"
                f"请核对 owner_id 后重试。我不会编造保单信息。\n{config.DISCLAIMER}")
    elif state.get("corrections"):
        c = state["corrections"][0]
        citations = _citations_for_message(state, [x["wiki_id"] for x in state["corrections"]])
        fix = f"建议改投 {c['replacement']}。" if c.get("replacement") else ""
        text = (f"⚠️ 无法按此报价：{c['note']}。{fix}"
                f"如需调整方案请告诉我，我会重新为您试算。\n{config.DISCLAIMER}")
    elif state.get("out_of_scope") == "ride_hailing":
        citations = _citations_for_message(state, ["wiki-ride-hailing"])
        text = ("您的车辆将变更为网约车/营运用途，这属于『危险程度显著增加』的重大变更，"
                "已超出续保助手的自动报价范围，需要转人工核保处理。\n"
                "要点（依据《合成机动车保险用途变更管理办法（虚构）》）：\n"
                "- 用途变更须及时通知保险人并按营运费率批改（合成费率表营运系数 1.6）\n"
                "- 未通知的营运期间出险，商业险可能拒赔或按比例赔付\n\n"
                "已为您转接人工核保（演示流程）。"
                f"\n{config.DISCLAIMER}")
    elif exit_reason:
        reason = exit_reason
        text = {
            "step_limit": f"本轮处理步数已达上限（{STEP_LIMIT} 步），为避免循环先暂停。"
                          "请简化需求或分步提出，我们继续。",
            "no_progress": f"连续 {NO_PROGRESS_LIMIT} 轮未收到新的需求信息，先结束本轮。"
                           "如需调整方案，请直接说明险种/保额/预算的变化。",
        }.get(reason, "本轮结束。")
        text += f"\n{config.DISCLAIMER}"
    elif intent == "terms":
        excerpts = state.get("excerpts") or {}
        citations = _citations_for_message(state, list(excerpts)[:3] or
                                           [c["wiki_id"] for c in state.get("citations", [])][:3])
        if client.available and excerpts:
            body = "\n\n".join(f"[{wid}]\n{tx}" for wid, tx in excerpts.items())
            # 记忆机制域：条款问答也吃同一套预算（多轮追问「那这个赔多少」要靠历史）
            mem_system, mem_history = memory.prompt_context(
                state, budget_tokens=config.memory_chat_budget(), legacy_tail=6)
            sys = security.guard_system_prompt(
                "你是车险条款顾问。只依据给定条款摘录回答，答案后不得引入摘录外的"
                "数字或承诺；无法确定时明确说『依据不足，无法确定』。"
                + config.DISCLAIMER + mem_system)
            _emit("llm_call", {"node": "fallback"},
                  {"record_type": "llm_call", "node": "fallback",
                   "input": {"system": "terms-advisor", "messages": 1 + len(mem_history)}})
            res = client.chat(system=sys, messages=_untrusted_history(mem_history) + [
                {"role": "user",
                 "content": f"问题：{security.wrap_untrusted(message)}\n\n条款摘录：\n{body}"}],
                node="fallback")
            marker = _llm_event(state, "fallback", res)
            text = res.text if res.mode == "llm" else None
        else:
            text = None
        if not text:
            if excerpts:
                first_wid = next(iter(excerpts))
                text = (f"根据条款知识库（{first_wid}）：{excerpts[first_wid]}\n"
                        f"（规则模式摘录式回答）\n{config.DISCLAIMER}")
            else:
                text = (f"未在条款知识库中检索到相关内容，依据不足，无法确定。"
                        f"请换个说法或咨询人工客服。\n{config.DISCLAIMER}")
    else:
        text = ("您好，我是车险续保助手（模拟报价·合成数据）。"
                "可以帮您：查看原保单、调整险种/保额、比价续保方案、解答条款问题。"
                "请问需要什么帮助？")
    _message_event(state, "fallback", text, citations)
    _node_end(state, "fallback", {"intent": intent, "exit_reason": exit_reason,
                                  "citations": [c["wiki_id"] for c in citations]}, t0)
    update = {"finish_reason": "end", "assistant_reply": text,
              "exit_reason": exit_reason, "steps": _steps(state)}
    if marker:
        update["llm_degraded"] = list(state.get("llm_degraded") or []) + [marker]
    return update


# ---------------------------------------------------------------------------
# 路由函数
# ---------------------------------------------------------------------------

def route_after_intake(state: RenewalState) -> str:
    if _over_step_limit(state):
        return "fallback"
    intent = state.get("intent")
    if intent in ("renewal", "compare", "confirm"):
        return "get_policy"
    if intent == "terms":
        return "retrieve_terms"
    return "fallback"


def route_after_parse_needs(state: RenewalState) -> str:
    if _over_step_limit(state):
        return "fallback"
    if int(state.get("no_progress_rounds") or 0) >= NO_PROGRESS_LIMIT:
        return "fallback"
    if not (state.get("policy") or {}).get("found"):
        return "fallback"          # AC-04：查无保单 → 兜底提示
    if not state.get("needs_sufficient"):
        return "clarify"
    return "retrieve_terms"


def route_after_retrieve_terms(state: RenewalState) -> str:
    if _over_step_limit(state):
        return "fallback"
    if state.get("confirmed"):
        return "confirm"           # 跨轮确认（await_confirm→confirm 的跨轮实现）
    if state.get("need_quote"):
        return "quote"
    return "fallback"


def route_after_quote(state: RenewalState) -> str:
    if state.get("error") or _over_step_limit(state):
        return "fallback"          # 报价工具业务错误 → 纠正提示
    return "compare"


def route_after_await_confirm(state: RenewalState) -> str:
    return "confirm" if state.get("confirmed") else END


def route_after_confirm(state: RenewalState) -> str:
    if state.get("confirm_error") in ("QUOTE_EXPIRED", "QUOTE_VERSION_STALE"):
        return "quote"             # SPEC §6.2：过期/版本失效 → 重新报价
    return END


# ---------------------------------------------------------------------------
# 组图（拓扑 = SPEC §6.2 + 文件头注明的事务性旁路）
# ---------------------------------------------------------------------------

def build_graph(checkpointer=None):
    """checkpointer=None 时不持久化；传入官方 saver 实例即启用 checkpoint。"""
    builder = StateGraph(RenewalState)
    builder.add_node("intake", intake)
    builder.add_node("get_policy", get_policy_node)
    builder.add_node("parse_needs", parse_needs)
    builder.add_node("clarify", clarify)
    builder.add_node("retrieve_terms", retrieve_terms)
    builder.add_node("quote", quote_node)
    builder.add_node("compare", compare)
    builder.add_node("await_confirm", await_confirm_node)
    builder.add_node("confirm", confirm_node)
    builder.add_node("fallback", fallback)

    builder.add_edge(START, "intake")
    builder.add_conditional_edges("intake", route_after_intake,
                                  ["get_policy", "retrieve_terms", "fallback"])
    builder.add_edge("get_policy", "parse_needs")
    builder.add_conditional_edges("parse_needs", route_after_parse_needs,
                                  ["clarify", "retrieve_terms", "fallback"])
    builder.add_edge("clarify", END)               # await_user 挂起
    builder.add_conditional_edges("retrieve_terms", route_after_retrieve_terms,
                                  ["quote", "fallback", "confirm"])
    builder.add_conditional_edges("quote", route_after_quote,
                                  ["compare", "fallback"])
# （quote 的主路径边 quote→compare 由上方条件边实现）
    builder.add_edge("compare", "await_confirm")
    builder.add_conditional_edges("await_confirm", route_after_await_confirm,
                                  ["confirm", END])  # await_user 挂起
    builder.add_conditional_edges("confirm", route_after_confirm,
                                  ["quote", END])
    builder.add_edge("fallback", END)
    return builder.compile(checkpointer=checkpointer)


_compiled = None


class _ThreadHandle:
    """编排执行入口（app.py 只认 stream/invoke/get_state 三个方法）。

    职责：
    1. 注入 checkpointer 主键——app.py 的 config 不带 configurable.thread_id，
       本层从 initial State 的 session_id 派生（官方 persistence：thread_id 是
       checkpoint 存取主键）；
    2. 注入执行期参数 durability / recursion_limit（官方 graph-api / checkpointers
       语义，检索 2026-11-17）；recursion_limit 以环境变量为硬天花板，调用方可降不可升；
    3. 把框架级异常翻译成协议内事件：GraphRecursionError 属 RecursionError 族，
       若不单独捕获，会落到 app.py 的兜底 except → SSE error 码退化成 INTERNAL，
       运维无法区分「模型/工具出错」与「图跑飞了」。

    并发（F2 整改）：已删除旧版无效的进程级 _RUN_LOCK，理由见文件顶部注释。
    """

    def __init__(self, inner):
        self._inner = inner

    def _config(self, initial, config):
        cfg = dict(config or {})
        conf = dict(cfg.get("configurable") or {})
        conf.setdefault("thread_id", sessions._safe(
            str((initial or {}).get("session_id") or "sess-anon")))
        cfg["configurable"] = conf
        # recursion_limit 语义 = 「上限」而非「默认值」：调用方（如 app.py）可传更小
        # 的值；环境变量 RENEWAL_RECURSION_LIMIT 是运维可降的硬天花板（≥ 1）
        try:
            asked = int(cfg.get("recursion_limit", RECURSION_LIMIT))
        except (TypeError, ValueError):
            asked = RECURSION_LIMIT
        cfg["recursion_limit"] = max(1, min(asked, RECURSION_LIMIT))
        return cfg

    def stream(self, initial, config=None, **kwargs):
        cfg = self._config(initial, config)
        kwargs.setdefault("durability", GRAPH_DURABILITY)
        return self._stream_guarded(initial, cfg, **kwargs)

    def _stream_guarded(self, initial, cfg, **kwargs):
        """生成器包装：框架级异常 → 协议内 error 事件 + 终态 finish_reason。"""
        try:
            yield from self._inner.stream(initial, cfg, **kwargs)
        except GraphRecursionError as exc:
            detail = str(exc)[:500]
            yield ("custom", {
                "event": "error",
                "data": {"code": "GRAPH_RECURSION_LIMIT",
                         "message": f"图执行超过 superstep 上限，本轮已中止：{detail}"},
                "trace": {"record_type": "error", "node": "graph",
                          "error": {"code": "GRAPH_RECURSION_LIMIT", "message": detail}},
            })
            # 终态交代：app.py 取最后一份 values 作为 final_state → done.finish_reason=error
            yield ("values", {"finish_reason": "error",
                              "exit_reason": "recursion_limit"})
        except LLMUnavailableError as exc:
            # 严格模式（SPEC v1.0.5，RENEWAL_LLM_STRICT=1）：LLM 失败必须显式失败，
            # 不允许静默降级成「看起来成功」的规则模式回答。
            detail = str(exc)[:500]
            yield ("custom", {
                "event": "error",
                "data": {"code": LLM_UNAVAILABLE, "message": detail,
                         "node": getattr(exc, "node", None),
                         "error_type": getattr(exc, "error_type", None)},
                "trace": {"record_type": "error",
                          "node": getattr(exc, "node", "graph"),
                          "error": {"code": LLM_UNAVAILABLE, "message": detail,
                                    "error_type": getattr(exc, "error_type", None)}},
            })
            yield ("values", {"finish_reason": "error",
                              "exit_reason": "llm_unavailable"})

    def invoke(self, initial, config=None, **kwargs):
        kwargs.setdefault("durability", GRAPH_DURABILITY)
        return self._inner.invoke(initial, self._config(initial, config), **kwargs)

    def get_state(self, config):
        return self._inner.get_state(config)
def get_graph(checkpointer="default"):
    """默认启用官方 checkpointer（SqliteSaver 优先）；传 None 可关闭。"""
    global _compiled
    if _compiled is None:
        cp = _make_checkpointer() if checkpointer == "default" else checkpointer
        _compiled = _ThreadHandle(build_graph(cp))
    return _compiled
