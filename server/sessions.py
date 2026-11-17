"""跨轮会话存储 → 官方 checkpointer 兼容层（2026-11-13 评审整改）。

历史角色：LangGraph 状态机按轮运行，会话级上下文在此持久化。
现状：graph.py 已接入官方 checkpointer（SqliteSaver，traces/checkpoints.sqlite，
thread_id = sessions._safe(session_id)），LangGraph checkpoint 成为状态持久化
的官方通道。本模块**保留为兼容层**而非直接废弃，原因：
  1) server/app.py（按约束本次不可改）每轮仍从 sessions.load() 装载快照
     组装 initial State，sessions.json 是 /chat 链路的实际恢复来源；
  2) history 裁剪（尾部 20 条）与 ephemeral 键过滤等应用层语义 checkpointer
     不承担，仍需此处实现；
  3) quote_book / 轨迹回放等周边仍引用本文件路径。
废弃计划：app.py 迁移到 get_graph().get_state(thread_id) 读状态后，本模块仅保留
history 归档职责（见 docs/summaries/orchestration.md 优化小节）。

持久化内容（备忘：上下文管理）：
- 当前需求版本（needs / needs_version）与已失效偏好（invalidated，记忆撤回）
- 最新有效报价（latest_quote，含 coverage_selection，用于预算-only 复用判断）
- 对照组原方案报价（baseline_quote）
- 对话历史（history，供 LLM 组 prompt，尾部截断）
- 无进展轮计数（no_progress_rounds，连续 2 轮无新信息退出）
- 会话状态（status：chatting / awaiting_confirm / confirmed）

存储位置：traces/sessions/{session_id}.json（JSON 落盘，重启不丢）。
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from . import config

_LOCK = threading.Lock()

# 每轮重算的临时键：不落盘（下轮由 intake/parse_needs 重新推导）
_EPHEMERAL_KEYS = {
    "message", "trace_id", "intent", "needs_sufficient", "need_quote",
    "confirmed", "confirm_error", "finish_reason", "steps", "exit_reason",
    "await_flag", "error", "citations", "excerpts", "wanted_wiki_ids",
    "corrections", "out_of_scope", "assistant_reply", "reuse_note",
    "clarify_questions",
}

# 会话快照里保留的原始历史条数（磁盘上限）。真正进 prompt 的量由 token 预算控制
# （server/memory.py#trim_turns，默认 1000 tokens），此处放宽到 40 条是为了让「滚动
# 摘要」有足够素材，且审计可回放；旧实现把 20 条直接当 prompt 预算，两者混为一谈。
_HISTORY_TAIL = int(config.env("RENEWAL_HISTORY_TAIL", "40") or 40)


def _dir() -> Path:
    d = config.TRACE_DIR / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(path: Path, text: str) -> None:
    """会话快照含保单/历史原文：写后收窄到 0600（安全域 t9）。

    这里**不**做内容脱敏：会话是运行态状态机数据（下一轮 quote 要用 vin），
    脱敏会直接弄坏业务。边界：可观测面（轨迹/日志）脱敏，运行态数据靠
    文件权限 + 保留策略（见 reviews/security.md §3.3）。
    """
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _safe(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:120] or "sess-anon"


def load(session_id: str) -> dict:
    """读会话快照；不存在返回空 dict。"""
    path = _dir() / f"{_safe(session_id)}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(session_id: str, state: dict) -> None:
    """把最终 State 中需要跨轮保留的键落盘（同事实多版本只留最新）。"""
    with _LOCK:
        keep = {
            k: v for k, v in state.items()
            if k not in _EPHEMERAL_KEYS and v is not None
        }
        history = keep.get("history") or []
        keep["history"] = history[-_HISTORY_TAIL:]
        _write(_dir().joinpath(f"{_safe(session_id)}.json"),
               json.dumps(keep, ensure_ascii=False, indent=1))
    # 长期记忆（跨会话）写入点：会话快照是本轮的最终 State，是「事实」的唯一来源。
    # 放在 save() 而不是 app.py，是为了零侵入 API 层：任何走 /chat 的轮次都会写记忆。
    # 失败绝不影响会话落盘（记忆是增强能力，不得反向放大故障面）。
    try:
        from . import memory as memory_mod
        memory_mod.record_turn(state)
    except Exception:
        pass


def append_history(session_id: str, role: str, content: str) -> None:
    """轮次结束后追加一条对话历史（user / assistant）。"""
    with _LOCK:
        snap = load(session_id)
        snap.setdefault("history", []).append({"role": role, "content": content})
        snap["history"] = snap["history"][-_HISTORY_TAIL:]
        _write(_dir().joinpath(f"{_safe(session_id)}.json"),
               json.dumps(snap, ensure_ascii=False, indent=1))

