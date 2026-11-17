"""轨迹 JSONL 写入（字段严格按 SPEC.md §5，禁止自创字段）。

每行字段：ts / trace_id / session_id / seq / record_type / node / event /
input / output / latency_ms / tokens_in / tokens_out / error
（SPEC v1.0.5 追加可选字段：mode / degraded / error_type，仅 LLM 相关记录使用）。
record_type 枚举：node_start / node_end / tool_call / tool_result / llm_call /
llm_response / llm_degraded / retrieval / user_message / assistant_message / error
（llm_degraded 为 SPEC v1.0.5 新增：LLM 降级留痕，非破坏性追加）。

平台工程域（2026-11-17）：实测 387 条历史轨迹发现 llm_response 256 条中 256 条、
retrieval 376 条中 376 条 **没有 latency_ms** —— 编排层从不上报这两类耗时，
导致 /metrics 的 gen_ai.client.inference.duration / gen_ai.retrieval.duration
长期空转（有指标名、无数据点）。这里在唯一写入点（record()）用单调时钟补齐
缺省 latency_ms——只写 §5 已定义字段，不新增字段、不改 SPEC：
  * llm_response ← 最近一次 llm_call 的时钟差（涵盖重试前的单次调用）
  * tool_result  ← 最近一次 tool_call（若图未自带）
  * retrieval    ← 所在节点 node_start 至今（上界，含节点内前置代码）
派生值语义在 reviews/platform.md 中登记；需要精确端点耗时应由编排层直接上报。
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from . import config, security

RECORD_TYPES = {
    "node_start", "node_end", "tool_call", "tool_result",
    "llm_call", "llm_response", "llm_degraded", "retrieval",
    "user_message", "assistant_message", "error",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class TraceRecorder:
    """一个对话轮次（trace_id）一个实例，线程不安全（单轮单协程使用）。"""

    def __init__(self, trace_id: str, session_id: str, trace_dir: Path | None = None):
        self.trace_id = trace_id
        self.session_id = session_id
        self.trace_dir = trace_dir or config.TRACE_DIR
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.trace_dir / f"{trace_id}.jsonl"
        # 安全域（t9）：轨迹是 PII 载体，文件权限收窄到 0600（工作态数据
        # 靠权限保护，可观测面靠上面的内容脱敏，两条边界分开管）。
        try:
            self.path.touch(mode=0o600, exist_ok=True)
            self.path.chmod(0o600)
        except OSError:  # 非常规文件系统/容器卷：不阻断主流程
            pass
        self._seq = 0
        # 单调时钟打点：键 "llm" / "tool" / "node:<name>"。仅记录本实例（本轮）
        # 的最近时间戳，随对象生命周期结束而释放，不做跨轮共享。
        self._marks: dict[str, float] = {}

    # -------------------------------------------------- 缺省耗时派生
    def _fill_latency(self, record_type: str, node: str | None,
                      latency_ms: float | None, now: float) -> float | None:
        """补齐 llm_response / tool_result / retrieval 的缺省耗时（毫秒）。

        只在调用方未显式给 latency_ms 时介入；有实测值则原样返回，绝不覆盖。
        依据见模块 docstring（387 条历史轨迹的实测缺口）。
        """
        def _delta(key: str) -> float | None:
            t0 = self._marks.get(key)
            if t0 is None or now < t0:
                return None
            return round((now - t0) * 1000.0, 2)

        if record_type == "llm_call":
            self._marks["llm"] = now
        elif record_type == "tool_call":
            self._marks["tool"] = now
        elif record_type == "node_start" and node:
            self._marks[f"node:{node}"] = now

        if latency_ms is not None:
            return latency_ms
        if record_type == "llm_response":
            return _delta("llm")
        if record_type == "tool_result":
            return _delta("tool")
        if record_type == "retrieval" and node:
            return _delta(f"node:{node}")
        return None
    def record(
        self,
        record_type: str,
        *,
        node: str | None = None,
        event: dict | None = None,
        input=None,
        output=None,
        latency_ms: float | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        error: dict | None = None,
        # SPEC v1.0.5 追加（可选，向后兼容：不传则不出现在行里）
        mode: str | None = None,
        degraded: bool | None = None,
        error_type: str | None = None,
    ) -> dict:
        if record_type not in RECORD_TYPES:
            raise ValueError(f"非法 record_type: {record_type}（SPEC §5）")
        self._seq += 1
        now = time.monotonic()  # 单调时钟：墙钟回拨不影响耗时
        latency_ms = self._fill_latency(record_type, node, latency_ms, now)
        row = {
            "ts": now_iso(),
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "seq": self._seq,
            "record_type": record_type,
            "node": node,
            "event": event,
            "input": input,
            "output": output,
        }
        if latency_ms is not None:
            row["latency_ms"] = latency_ms
        if tokens_in is not None:
            row["tokens_in"] = tokens_in
        if tokens_out is not None:
            row["tokens_out"] = tokens_out
        if error is not None:
            row["error"] = error
        # SPEC v1.0.5：LLM 降级可观测字段（llm_response / llm_degraded 使用）
        if mode is not None:
            row["mode"] = mode
        if degraded is not None:
            row["degraded"] = degraded
        if error_type is not None:
            row["error_type"] = error_type
        # 安全域（t9，2026-11-17）：唯一写入点做 PII 脱敏，默认不落原文
        # （OWASP LLM02:2025 · Tokenization and Redaction）。脱敏是幂等的，
        # 已脱敏值不会被二次改写；RENEWAL_TRACE_PII=keep 时原样落盘（仅调试）。
        row = security.redact_row(row)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        # 平台工程（2026-11-13）：轨迹行同步喂 Prometheus 指标（OTel GenAI
        # 语义约定命名）。record() 是所有遥测的必经点，JSONL 与 /metrics
        # 永远同源；指标异常不得影响轨迹落盘，故捕获一切异常。
        try:
            from . import metrics
            metrics.observe_record(row)
        except Exception:
            pass
        return row

    @property
    def seq(self) -> int:
        return self._seq


def read_trace(trace_id: str, trace_dir: Path | None = None) -> list[dict] | None:
    """读取整条轨迹；不存在返回 None。"""
    path = (trace_dir or config.TRACE_DIR) / f"{trace_id}.jsonl"
    if not path.is_file():
        return None
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            # 读端同样脱敏：628 条存量历史轨迹文件里仍有 PII 原文，
            # /trace API 是外部可见面，必须在出口处兜住（幂等）。
            rows.append(security.redact_row(json.loads(line)))
    return rows
