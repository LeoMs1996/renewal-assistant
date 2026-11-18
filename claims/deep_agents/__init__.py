"""F3 长程材料分析层（Deep Agents）。

对外只有一个入口（F2 `claims/graph.py` 调用的契约）::

    from claims.deep_agents import analyzer as deep_analyzer
    result = deep_analyzer.run_analysis(docs, analyzer_version=...)

本 `__init__` **不导入** deepagents（那是重依赖）：即使 `.venv` 里没装 deepagents，
`import claims.deep_agents` 也不会失败，只有真正调用 `run_analysis` 时才报
`AnalysisUnavailable(error_type="DeepAgentsNotInstalled")`。
"""

from __future__ import annotations

from . import analyzer, errors, materials, prompts, schema
from .schema import MaterialsAnalysis, MaterialsAnalysisDraft

__all__ = [
    "analyzer",
    "errors",
    "materials",
    "prompts",
    "schema",
    "MaterialsAnalysis",
    "MaterialsAnalysisDraft",
]
