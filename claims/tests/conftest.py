"""理赔域测试夹具。

**不并入默认收集**（`pyproject.toml` 的 `testpaths` 不含 claims）：
续保基线的 `148 passed` 口径必须保持可比。显式运行：

    .venv/bin/python -m pytest claims/tests -q
"""

from __future__ import annotations

import os as _os
import sys
import warnings as _warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# D-22：`claims/api.py` 在**模块导入时**就 `create_app()` 并跑 preflight（strict 由
# `CLAIMS_ALLOW_RULES_ONLY` 决定）。F4 测试的 fixture 里设置已经太晚——必须在被测模块
# 被 import（即 pytest 收集阶段）之前设好，否则 `.venv`（无 deepagents）下整个模块
# collection 直接 RuntimeError。这只是把 F4 fixture 的既有意图（"单测不因解释器不同而红"）
# 提前到收集期；显式 `strict=True` 的用例仍然会走严格路径。
_os.environ.setdefault("CLAIMS_ALLOW_RULES_ONLY", "1")


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """把所有落盘路径指到 tmp_path，测试绝不写仓库里的 traces/claims data。"""
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CLAIMS_CHECKPOINT_DB", str(tmp_path / "data" / "checkpoints.sqlite"))
    monkeypatch.setenv("CLAIMS_TRACE_DIR", str(tmp_path / "traces-claims"))
    monkeypatch.setenv("DEEPAGENTS_ENABLED", "false")
    monkeypatch.setenv("CLAIMS_AMOUNT_REVIEW_THRESHOLD", "3000")
    monkeypatch.setenv("CLAIMS_DEDUCTIBLE", "500")
    monkeypatch.setenv("CLAIMS_MAX_PAYABLE", "20000")
    return tmp_path


@pytest.fixture()
def claim_input():
    """标准报案输入（合成数据）。"""

    def _make(docs_key: str = "complete", **overrides):
        from claims.tools import synthetic

        payload = {
            "owner_id": "OWN-1001",
            "policy_no": "POL-2026-0001",
            "session_id": "sess-test",
            "report": {
                "occurred_at": "2026-11-01T08:20:00+08:00",
                "location": "北京市朝阳区建国路",
                "description": "追尾事故，前保险杠与大灯受损",
                "has_injury": False,
            },
            "documents": synthetic.documents(docs_key),
        }
        payload.update(overrides)
        return payload

    return _make


# --------------------------------------------------------------------------- #
# 会话级护栏（F2c / t18）——把「环境恰好没触发」变成「环境不对就明确报错」
# --------------------------------------------------------------------------- #
_TRUTHY = {"1", "true", "yes", "on"}
_REPO_DATA = REPO_ROOT / "claims" / "data"


def _repo_data_files() -> list[str]:
    if not _REPO_DATA.exists():
        return []
    return sorted(
        str(p.relative_to(_REPO_DATA)) for p in _REPO_DATA.rglob("*") if p.is_file()
    )


@pytest.fixture(scope="session", autouse=True)
def _guard_no_real_model():
    """方案 A：**宁可整套跑不起来并明确报错，也不要静默去调真实模型**。

    - `DEEPAGENTS_MODEL` 被设置 → 直接 `pytest.exit`（退出码 3）。
      理由：本套件假定"未配置模型"，一旦配置了，F3 的显式 opt-in 就被打开，
      `test_deepagents_enabled_but_no_model_configured_falls_back` 之类用例的
      失败原因会与业务断言混在一起。
    - 环境里 `DEEPAGENTS_ENABLED=true` → 只告警（不退出）：逐个用例的 `tmp_env`
      会重新钉成 false，这里提醒属于"配置漂移"信号，而不是致命。
    """
    problems: list[str] = []
    if _os.environ.get("DEEPAGENTS_MODEL"):
        problems.append("DEEPAGENTS_MODEL=<已设置>（应留空：本套件按'未配置模型'设计）")
    if (_os.environ.get("DEEPAGENTS_ENABLED") or "").strip().lower() in _TRUTHY:
        _warnings.warn(
            "环境里 DEEPAGENTS_ENABLED=true：claims/tests 假定开关默认关闭；"
            "未使用 tmp_env 的用例可能触发真实模型调用。",
            UserWarning,
            stacklevel=1,
        )
    if problems:
        pytest.exit(
            "claims/tests 拒绝在可能调用真实模型的会话里运行：\n  - "
            + "\n  - ".join(problems)
            + "\n请 unset 这些变量后重跑（或显式 `DEEPAGENTS_MODEL= ` 置空）。",
            returncode=3,
        )
    yield


@pytest.fixture(scope="session", autouse=True)
def _guard_repo_data_untouched():
    """R2：跑完整套件后，仓库里的 `claims/data/` 不得多出文件。

    跨用例串扰的典型症状是「某条路径没被触发」——根因常是 data 目录被复用后
    `intake` 判了 `CLAIM_DUPLICATE` 提前 END。本护栏把"写进仓库"变成显式失败。
    """
    before = _repo_data_files()
    yield
    after = _repo_data_files()
    added = sorted(set(after) - set(before))
    assert not added, (
        f"测试往仓库 claims/data/ 写了文件：{added}\n"
        "说明有用例没走 tmp_env（会与其它用例互相串扰）。请把落盘路径指到 tmp_path。"
    )
