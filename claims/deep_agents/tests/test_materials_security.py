"""文件系统边界测试——**这是本轮最要命的一条安全红线**。

背景（F0 已核实）：`FilesystemBackend(root_dir=None)` 会退化成 `Path.cwd()`，而仓库根有
`.env`（真实模型凭证）。所以：

1. 本层必须**永远**显式传 `root_dir`；
2. 必须证明模型拿不到 `.env`：`../.env`、`../../.env`、`claims/../../.env` 三种写法都要失败；
3. `doc_id` 会拼进文件名，必须挡住 `../` 这类路径注入。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from claims.deep_agents import errors, materials
from claims.deep_agents.analyzer import AnalysisConfig, build_agent
from claims.deep_agents.materials import (
    materials_root,
    prepare_materials,
    repo_root,
    safe_workspace_root,
)

REPO = repo_root()


@pytest.fixture()
def work_root() -> Path:
    """在 `claims/data/materials` 下开一个干净的临时工作区（用完删掉）。"""
    path = materials_root() / f"_pytest-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        import shutil

        shutil.rmtree(path, ignore_errors=True)

def test_repo_env_file_exists_so_test_is_meaningful() -> None:
    """.env 必须真实存在，否则「读不到 .env」的断言毫无意义。"""
    assert (REPO / ".env").is_file(), "仓库根应有 .env（本测试的前提）"


@pytest.mark.parametrize(
    "attack_path",
    ["../.env", "../../.env", "claims/../../.env", "/../../.env", "../" * 8 + ".env"],
)
def test_filesystem_backend_blocks_traversal_to_dotenv(work_root: Path, attack_path: str) -> None:
    """模型若尝试用相对路径越界读 `.env`，backend 必须拒绝（或读不到内容）。"""
    from deepagents.backends import FilesystemBackend

    backend = FilesystemBackend(root_dir=str(work_root), virtual_mode=True)
    try:
        result = backend.read(attack_path)
    except ValueError as exc:  # 预期：virtual_mode 下抛 "Path traversal not allowed"
        assert "traversal" in str(exc).lower() or "not allowed" in str(exc).lower()
        assert "ANTHROPIC" not in str(exc)
        return
    except Exception as exc:  # noqa: BLE001 - 其他异常也可接受，但必须不泄密
        assert "ANTHROPIC" not in str(exc) and "sk-" not in str(exc)
        return
    payload = str(result)
    assert "ANTHROPIC" not in payload and "sk-" not in payload, f"泄露了 .env 内容: {payload}"
    raise AssertionError(f"越界读取未被拒绝：{attack_path} -> {payload[:200]}")

def test_dotenv_is_outside_workspace_root(work_root: Path) -> None:
    """结构性证明：`.env` 不在工作区里，工作区也不含仓库根。"""
    resolved_root = work_root.resolve()
    dotenv = (REPO / ".env").resolve()
    assert not dotenv.is_relative_to(resolved_root)
    # 工作区在仓库内，但绝不能是仓库根或其祖先（否则 .env 可被读到）
    assert not REPO.is_relative_to(resolved_root)


@pytest.mark.parametrize(
    "candidate",
    [
        "repo_root",
        "repo_parent",
        "claims_dir",
        "claims_data_dir",
        "root",
        "/tmp",
    ],
)
def test_safe_workspace_root_rejects_dangerous_paths(candidate: str) -> None:
    mapping = {
        "repo_root": REPO,
        "repo_parent": REPO.parent,
        "claims_dir": REPO / "claims",
        "claims_data_dir": REPO / "claims" / "data",
        "root": Path("/"),
        "/tmp": Path("/tmp"),
    }
    with pytest.raises(errors.MaterialInvalid) as excinfo:
        safe_workspace_root(mapping[candidate])
    assert excinfo.value.error_type == "UnsafeWorkspaceRoot"
    assert excinfo.value.code == "MATERIAL_MISSING"


def test_safe_workspace_root_accepts_materials_dir(work_root: Path) -> None:
    assert safe_workspace_root(materials_root()) == materials_root().resolve()
    assert safe_workspace_root(work_root) == work_root.resolve()


@pytest.mark.parametrize(
    "bad_doc_id",
    ["../.env", "..", "../../etc/passwd", "/etc/passwd", "a/b", "a\\b", "", " ", "x" * 65],
)
def test_doc_id_path_injection_rejected(bad_doc_id: str) -> None:
    """doc_id 进文件名，必须过白名单；否则可构造路径注入。"""
    with pytest.raises(errors.MaterialInvalid):
        prepare_materials([{"doc_id": bad_doc_id, "kind": "photo", "text": "内容"}])


def test_materialized_files_stay_inside_workspace(work_root: Path) -> None:
    mats = prepare_materials([{"doc_id": "doc-0001", "kind": "photo", "text": "表面划痕"}])
    workspace = materials.materialize(mats, root=work_root)
    try:
        resolved = workspace.root.resolve()
        assert resolved.is_relative_to(work_root.resolve())
        assert (resolved / "doc-0001.txt").is_file()
        assert (resolved / "manifest.json").is_file()
        assert not any(p.name == ".env" for p in resolved.rglob("*"))
    finally:
        workspace.cleanup()


def test_build_agent_passes_explicit_root_never_none(work_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """回归防线：`build_agent` 传给 FilesystemBackend 的 root_dir 绝不能是 None/缺省。"""
    import deepagents.backends as dbe

    captured: dict[str, object] = {}

    class SpyBackend(dbe.FilesystemBackend):  # type: ignore[misc,valid-type]
        def __init__(self, root_dir=None, **kwargs):  # noqa: ANN001, ANN003
            captured["root_dir"] = root_dir
            captured["kwargs"] = kwargs
            super().__init__(root_dir=root_dir, **kwargs)

    monkeypatch.setattr(dbe, "FilesystemBackend", SpyBackend)

    mats = prepare_materials([{"doc_id": "doc-0001", "kind": "photo", "text": "表面划痕"}])
    workspace = materials.materialize(mats, root=work_root)
    try:
        from .conftest import make_fake

        build_agent(model=make_fake(), workspace=workspace, config=AnalysisConfig())
    finally:
        workspace.cleanup()

    root_dir = captured.get("root_dir")
    assert root_dir is not None, "root_dir 传了 None —— 会退化成 cwd（仓库根有 .env）！"
    assert Path(str(root_dir)).resolve() == workspace.root.resolve()
    assert captured["kwargs"].get("virtual_mode") is True  # type: ignore[union-attr]
