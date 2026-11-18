"""`schemas.py` → `schema.py` 的别名。

历史原因：`docs/research/r3-langgraph-deepagents.md` / 队长任务书里出现过 `schemas.py`，
而契约 `claims/SPEC-claims.md` §4.3 写的是 `claims/deep_agents/schema.py`。
两个名字都保留，避免调用方踩坑；**规范名是 `schema.py`**（契约优先）。
"""

from __future__ import annotations

from .schema import *  # noqa: F403
from .schema import __all__ as _schema_all

__all__ = list(_schema_all)
