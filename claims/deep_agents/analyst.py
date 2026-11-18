"""`analyst.py` → `analyzer.py` 的别名。

`claims/ARCHITECTURE.md` §5.1 写的是 `analyst.py::run_analysis`，`claims/SPEC-claims.md`
§8.1 与 F2 的 `claims/graph.py` 写的是 `claims.deep_agents.analyzer.run_analysis`。
以**契约（SPEC + 调用方代码）为准**：`analyzer.py` 是实现，这里只做转发，
让两种写法都能工作。
"""

from __future__ import annotations

from .analyzer import (  # noqa: F401
    ANALYZER_IMPL,
    SUBAGENT_THRESHOLD,
    AnalysisConfig,
    analyze,
    build_agent,
    resolve_model,
    run_analysis,
    validate_and_enrich,
)

__all__ = [
    "AnalysisConfig",
    "run_analysis",
    "analyze",
    "build_agent",
    "resolve_model",
    "validate_and_enrich",
    "ANALYZER_IMPL",
    "SUBAGENT_THRESHOLD",
]
