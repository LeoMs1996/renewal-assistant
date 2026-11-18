"""t22 / I5-c 回归：`CLAIMS_DATA_DIR` 必须**真正**搬走 F3 的材料工作区。

X1 对账发现的问题：`materials.py` 把工作区写成 `claims/data/materials` 硬编码，
于是 `claims/tests` 里 `CLAIMS_DATA_DIR=<tmp>` 的隔离**只对 F2 生效、对 F3 无效**——
测试看着在临时目录跑，F3 仍往仓库里写材料。这是「我以为隔离了、其实没有」，
比不隔离更危险（人会因此省掉人工检查）。

因此这里的断言不用"路径字符串相等"这种弱证据，而是**文件系统事实**：
对比仓库 `claims/data/` 在分析前后的 `(inode, mtime_ns, size)` 快照，必须逐字相同。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from claims.deep_agents import analyzer, errors, materials
from claims.deep_agents.analyzer import AnalysisConfig
from claims.deep_agents.materials import materials_root, repo_root, safe_workspace_root

from .conftest import make_fake

REPO = repo_root()
REPO_DATA = REPO / "claims" / "data"


def _snapshot(root: Path) -> dict[str, tuple[int, int, int]]:
    """目录树快照：相对路径 -> (inode, mtime_ns, size)。"""
    if not root.exists():
        return {}
    snap: dict[str, tuple[int, int, int]] = {}
    for path in sorted(root.rglob("*")):
        st = path.lstat()
        snap[str(path.relative_to(root))] = (st.st_ino, st.st_mtime_ns, st.st_size)
    return snap


def _payload(doc_id: str = "doc-0001", quote: str = "2026年11月1日8时20分许") -> dict[str, Any]:
    return {
        "schema_version": "materials-analysis/1",
        "documents": [
            {
                "doc_id": doc_id,
                "kind": "police_report",
                "facts": [
                    {
                        "key": "accident_time",
                        "value": quote,
                        "confidence": 0.9,
                        "evidence": {"doc_id": doc_id, "span": "L2", "quote": quote},
                    }
                ],
                "consistency_notes": [],
                "anomalies": [],
            }
        ],
        "missing_items": [],
    }


def test_claims_data_dir_moves_workspace_and_leaves_repo_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, police_doc: dict[str, Any]
) -> None:
    """设 `CLAIMS_DATA_DIR=<tmp>` 后跑一次分析：仓库 `claims/data` 零新增（inode/mtime 对比）。"""
    env_data_dir = tmp_path / "claims-data"
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(env_data_dir))

    before = _snapshot(REPO_DATA)

    out = analyzer.analyze(
        [police_doc],
        config=AnalysisConfig(
            model=make_fake(_payload()),
            enable_subagents=False,
            keep_workspace=True,  # 保留工作区，才能证明它确实落在 tmp 而不是仓库
        ),
        analyzer_version="rules-1",
    )

    after = _snapshot(REPO_DATA)

    assert out["analyzer"]["mode"] == "deepagents"
    # ① 仓库侧：一个字节、一个 inode 都不许变
    assert after == before, (
        "仓库 claims/data 在分析后发生了变化（F3 又写回仓库了）："
        f"新增={sorted(set(after) - set(before))} 消失={sorted(set(before) - set(after))}"
    )
    # ② 临时侧：材料确实落在 CLAIMS_DATA_DIR 之下
    workdirs = sorted((env_data_dir / "materials").glob("analysis-*"))
    assert len(workdirs) == 1, f"未在 CLAIMS_DATA_DIR 下创建工作区：{workdirs}"
    assert (workdirs[0] / "manifest.json").is_file()
    assert (workdirs[0] / "doc-0001.txt").is_file()
    assert workdirs[0].resolve().is_relative_to(env_data_dir.resolve())


def test_timeout_leaves_no_workspace_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, police_doc: dict[str, Any]
) -> None:
    """超时路径（异常退出）也必须清理工作区——否则失败重试会堆垃圾目录。"""
    env_data_dir = tmp_path / "claims-data-timeout"
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(env_data_dir))
    before = _snapshot(REPO_DATA)

    slow = make_fake(_payload(), delay=1.5)
    with pytest.raises(errors.AnalysisTimeout):
        analyzer.analyze(
            [police_doc],
            config=AnalysisConfig(model=slow, enable_subagents=False, timeout_s=0.2),
            analyzer_version="rules-1",
        )

    assert _snapshot(REPO_DATA) == before, "超时路径把工作区漏在仓库里了"
    assert list((env_data_dir / "materials").glob("analysis-*")) == [], "超时后工作区未清理"


def test_claims_data_dir_moves_workspace_with_default_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, police_doc: dict[str, Any]
) -> None:
    """默认（不留工作区）路径下同样不得写仓库。"""
    env_data_dir = tmp_path / "claims-data-2"
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(env_data_dir))
    before = _snapshot(REPO_DATA)

    analyzer.analyze(
        [police_doc],
        config=AnalysisConfig(model=make_fake(_payload()), enable_subagents=False),
        analyzer_version="rules-1",
    )

    assert _snapshot(REPO_DATA) == before
    assert (env_data_dir / "materials").is_dir()
    assert list((env_data_dir / "materials").glob("analysis-*")) == []


def test_materials_root_follows_env_each_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`materials_root()` 逐次读环境变量（不是 import 时缓存）。"""
    monkeypatch.delenv("CLAIMS_DATA_DIR", raising=False)
    assert materials_root().resolve() == (REPO / "claims" / "data" / "materials").resolve()

    first = tmp_path / "a"
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(first))
    assert materials_root().resolve() == (first / "materials").resolve()

    second = tmp_path / "b"
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(second))
    assert materials_root().resolve() == (second / "materials").resolve()


def test_safe_workspace_root_base_follows_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_data_dir = tmp_path / "claims-data"
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(env_data_dir))

    assert safe_workspace_root() == (env_data_dir / "materials").resolve()
    # 落在新根之内的子目录允许
    child = env_data_dir / "materials" / "sub"
    child.mkdir(parents=True)
    assert safe_workspace_root(child) == child.resolve()


def test_repo_root_still_rejected_even_when_env_points_elsewhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """改根不能顺带放宽安全断言：仓库根/上级仍必须拒绝。"""
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(tmp_path / "claims-data"))
    for dangerous in (REPO, REPO.parent, REPO / "claims", Path("/")):
        with pytest.raises(errors.MaterialInvalid) as excinfo:
            safe_workspace_root(dangerous)
        assert excinfo.value.error_type == "UnsafeWorkspaceRoot"

    # 既不在新根内、也不在仓库内 → 同样拒绝
    with pytest.raises(errors.MaterialInvalid):
        safe_workspace_root(tmp_path / "somewhere-else")


def test_workspace_under_env_root_cannot_read_repo_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """换了根之后，越界读 `.env` 依然被 backend 拒绝（防护不随根漂移）。"""
    from deepagents.backends import FilesystemBackend

    env_data_dir = tmp_path / "claims-data"
    monkeypatch.setenv("CLAIMS_DATA_DIR", str(env_data_dir))
    root = materials.safe_workspace_root()
    root.mkdir(parents=True, exist_ok=True)

    backend = FilesystemBackend(root_dir=str(root), virtual_mode=True)
    for attack in ("../.env", "../../.env", str(REPO / ".env")):
        try:
            result = backend.read(attack)
        except Exception as exc:  # noqa: BLE001
            assert "ANTHROPIC" not in str(exc) and "sk-" not in str(exc)
            continue
        payload = str(result)
        assert "ANTHROPIC" not in payload and "sk-" not in payload
        # 若没抛异常就必须是 error 结果，不能是内容
        assert "error" in payload, f"越界读取返回了内容：{payload[:200]}"
