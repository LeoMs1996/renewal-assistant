"""F3 显式错误类型——**不允许静默降级**。

契约事实（`claims/graph.py::run_analysis`）：F2 在 `DEEPAGENTS_ENABLED=true` 时调用本层，
并用 `except Exception: pass` 兜底转 `rules_fallback`。因此本层的纪律是：

- **绝不**在本层内部偷偷切换到规则模式（那会让「降级」变得不可观测）；
- 一切不可用/超时/不合 schema 的情况**抛异常**，且异常自带契约 §5 的错误码与
  `error_type`，供 F2 在轨迹里落 `llm_degraded{error_type=...}`；
- `degraded` 恒为 `False`：本层没有发生任何降级动作，降级是调用方的决定。

错误码全部取自契约 §5（14 个），**不新增错误码**（新增即改契约）。超时/模型不可用这类
场景共用 `ANALYSIS_UNAVAILABLE`，靠 `error_type` 区分（与续保 `LLM_UNAVAILABLE` 同构）。
"""

from __future__ import annotations

from typing import Any


class AnalysisError(RuntimeError):
    """F3 所有错误的基类。"""

    code: str = "ANALYSIS_UNAVAILABLE"
    default_error_type: str = "AnalysisError"

    def __init__(
        self,
        message: str,
        *,
        error_type: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type or self.default_error_type
        self.detail = detail or {}
        #: 本层不做降级；恒 False，避免调用方误判「已经降级过」
        self.degraded = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "error_type": self.error_type,
            "message": self.message,
            "degraded": self.degraded,
            "detail": self.detail,
        }

    def __str__(self) -> str:  # pragma: no cover - 展示用
        return f"[{self.code}/{self.error_type}] {self.message}"


class MaterialMissing(AnalysisError):
    """材料缺失/为空（契约 §5 `MATERIAL_MISSING`，422，不可重试）。"""

    code = "MATERIAL_MISSING"
    default_error_type = "MaterialMissing"


class MaterialInvalid(AnalysisError):
    """材料不可读/结构非法（同一错误码，调用方据此转 `need_info`）。"""

    code = "MATERIAL_MISSING"
    default_error_type = "MaterialInvalid"


class AnalysisUnavailable(AnalysisError):
    """深代理不可用：包缺失、无模型凭证、provider 报错（契约 §5 `ANALYSIS_UNAVAILABLE`）。"""

    code = "ANALYSIS_UNAVAILABLE"
    default_error_type = "AnalysisUnavailable"


class AnalysisTimeout(AnalysisUnavailable):
    """分析超时。与其他不可用共用错误码，`error_type` 区分为 `AnalysisTimeout`。"""

    default_error_type = "AnalysisTimeout"


class AnalysisSchemaInvalid(AnalysisError):
    """模型输出不符 `materials-analysis/1`（契约 §5 `ANALYSIS_SCHEMA_INVALID`，502）。"""

    code = "ANALYSIS_SCHEMA_INVALID"
    default_error_type = "AnalysisSchemaInvalid"


class StructuredOutputMissing(AnalysisSchemaInvalid):
    """模型没有按 `response_format` 调用结构化输出工具（structured_response 为 None）。"""

    default_error_type = "StructuredOutputMissing"


__all__ = [
    "AnalysisError",
    "MaterialMissing",
    "MaterialInvalid",
    "AnalysisUnavailable",
    "AnalysisTimeout",
    "AnalysisSchemaInvalid",
    "StructuredOutputMissing",
]
