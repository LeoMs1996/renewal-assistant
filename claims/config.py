"""理赔域配置（F2）。

原则：**只读环境变量，不改 `server/config.py`**。续保域已有的 `TRACE_DIR` /
`WIKI_DIR` 环境变量机制在这里被复用，但理赔域自己解析路径，避免依赖
`server.config` 的 import 时序（它在 import 时就 mkdir 了 `traces/`）。

环境变量（全部可选）：
- `DEEPAGENTS_ENABLED`           默认 false；true 时材料分析尝试走 F3 的 Deep Agents 实现
- `DEEPAGENTS_PYTHON`            记录用（F3/F0 落地解释器路径），本模块不 subprocess
- `CLAIMS_TRACE_DIR`             默认 `<repo>/traces-claims`（与续保 `traces/` 隔离）
- `CLAIMS_CHECKPOINT_DB`         默认 `<repo>/claims/data/checkpoints.sqlite`
- `CLAIMS_DATA_DIR`              默认 `<repo>/claims/data`（材料/缓存/幂等登记）
- `CLAIMS_WIKI_DIR`              默认 `<repo>/data/llm-wiki-claims/wiki`
- `CLAIMS_AMOUNT_REVIEW_THRESHOLD`  **演示值，非业务依据，生产需按保单条款配置**
- `CLAIMS_DEDUCTIBLE`             演示值（免赔额）
- `CLAIMS_MAX_PAYABLE`            演示值（单案上限）
"""

from __future__ import annotations

import os
from pathlib import Path

CLAIMS_DIR = Path(__file__).resolve().parent
REPO_ROOT = CLAIMS_DIR.parent

#: 演示值。**不是业务规则**，生产必须按保单条款/监管要求配置，禁止据此对外承诺。
DEFAULT_AMOUNT_REVIEW_THRESHOLD = 3000.0
DEFAULT_DEDUCTIBLE = 500.0
DEFAULT_MAX_PAYABLE = 20000.0


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _path(name: str, default: Path) -> Path:
    return Path(_env(name, str(default))).expanduser()


def deepagents_enabled() -> bool:
    return _env("DEEPAGENTS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def deepagents_python() -> str:
    """F3 的独立解释器路径（仅记录用；本域不 subprocess 调用）。"""
    return _env("DEEPAGENTS_PYTHON", str(REPO_ROOT / ".venv-claims" / "bin" / "python"))


def trace_dir() -> Path:
    return _path("CLAIMS_TRACE_DIR", REPO_ROOT / "traces-claims")


def data_dir() -> Path:
    return _path("CLAIMS_DATA_DIR", CLAIMS_DIR / "data")


def checkpoint_db() -> Path:
    return _path("CLAIMS_CHECKPOINT_DB", data_dir() / "checkpoints.sqlite")


def wiki_dir() -> Path:
    return _path("CLAIMS_WIKI_DIR", REPO_ROOT / "data" / "llm-wiki-claims" / "wiki")


def idempotency_dir() -> Path:
    return data_dir() / "idempotency"


def analysis_cache_dir() -> Path:
    return data_dir() / "cache"


def amount_review_threshold() -> float:
    """演示值：> 该金额（元）需人工审核。生产按保单条款配置。"""
    return float(_env("CLAIMS_AMOUNT_REVIEW_THRESHOLD", str(DEFAULT_AMOUNT_REVIEW_THRESHOLD)))


def deductible() -> float:
    """演示值：免赔额（元）。"""
    return float(_env("CLAIMS_DEDUCTIBLE", str(DEFAULT_DEDUCTIBLE)))


def max_payable() -> float:
    """演示值：单案赔付上限（元）。"""
    return float(_env("CLAIMS_MAX_PAYABLE", str(DEFAULT_MAX_PAYABLE)))


def ensure_dirs() -> None:
    for path in (trace_dir(), data_dir(), idempotency_dir(), analysis_cache_dir()):
        path.mkdir(parents=True, exist_ok=True)
