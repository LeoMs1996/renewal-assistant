"""材料准备与工作区落盘（Deep Agents 文件系统的输入侧）。

为什么要把材料写成**文件**而不是全塞进 prompt：长材料会撑爆上下文，Deep Agents 的
文件系统工具（`ls` / `read_file` / `grep`）才是官方的长程材料处理方式（R3 §4、F0 S3）。
模型拿到的是「清单 + 路径」，按需读取。

安全约束（F0 已实证，见 `docs/research/f0-deepagents-0739-install-evidence.md`）：

1. `FilesystemBackend(root_dir=None)` 会**默认取当前工作目录**（源码
   `self.cwd = Path(root_dir).resolve() if root_dir else Path.cwd()`）。仓库根有 `.env`，
   所以本模块**永远**显式传 `root_dir`，且用 `safe_workspace_root()` 断言它是
   `claims/data/materials` 下的子目录、不是仓库根、也不是仓库根的祖先。
2. `virtual_mode=True`（默认）时 `..` / `~` / 越界绝对路径由 backend 直接拒绝
   （实测抛 `ValueError: Path traversal not allowed`）。测试
   `tests/test_materials_security.py` 覆盖 `../.env`、`../../.env`、`claims/../../.env`。
3. `doc_id` 会进文件名，必须先过白名单正则，否则可构造 `../../.env` 之类的路径注入。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import MaterialInvalid, MaterialMissing

#: 单份材料正文上限（字符）。超出即截断，但**显式**记录在 anomaly 里，绝不静默。
MAX_DOC_CHARS = 1_000_000
#: doc_id 白名单：只允许字母数字与 . _ -，长度受限（进文件名，防路径注入）
DOC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class Material:
    """一份待分析材料（已规范化）。"""

    doc_id: str
    kind: str
    text: str
    sha256: str
    original_chars: int
    truncated: bool = False
    source: dict[str, Any] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        return f"{self.doc_id}.txt"

    def manifest_row(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "kind": self.kind,
            "file": self.filename,
            "sha256": self.sha256,
            "chars": len(self.text),
            "original_chars": self.original_chars,
            "truncated": self.truncated,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def prepare_materials(docs: list[dict[str, Any]] | None) -> list[Material]:
    """校验并规范化输入材料。

    明确区分三种情况（都要**显式**，不静默吞掉）：

    - `docs` 为空/不是列表 → `MaterialMissing`（契约 §5，调用方据此转 `need_info`）
    - 单条结构非法（非 dict / 缺 `doc_id` / `doc_id` 不合白名单）→ `MaterialInvalid`
    - 正文为空或空白（不可读）→ `MaterialInvalid`（不猜、不补）

    超长正文会被截断到 `MAX_DOC_CHARS`，并在 `Material.truncated` 上标记，
    由调用方写进 `documents[*].anomalies`。
    """
    if not docs:
        raise MaterialMissing("未提供任何材料（docs 为空）", error_type="EmptyMaterials")
    if not isinstance(docs, list):
        raise MaterialInvalid(
            f"docs 必须是 list[dict]，实际为 {type(docs).__name__}",
            error_type="InvalidDocsArgument",
        )

    materials: list[Material] = []
    seen: set[str] = set()
    for idx, doc in enumerate(docs):
        if not isinstance(doc, dict):
            raise MaterialInvalid(
                f"第 {idx} 条材料不是 dict，而是 {type(doc).__name__}",
                error_type="InvalidMaterialEntry",
                detail={"index": idx},
            )
        raw_id = doc.get("doc_id")
        doc_id = "" if raw_id is None else str(raw_id).strip()
        if not doc_id:
            raise MaterialInvalid(
                f"第 {idx} 条材料缺少 doc_id",
                error_type="MissingDocId",
                detail={"index": idx},
            )
        if not DOC_ID_RE.match(doc_id):
            # 关键安全点：doc_id 会拼进文件名，非法字符一律拒绝
            raise MaterialInvalid(
                f"doc_id 非法（只允许字母数字与 . _ -，长度 1..64）：{doc_id[:80]!r}",
                error_type="InvalidDocId",
                detail={"index": idx, "doc_id": doc_id[:80]},
            )
        if doc_id in seen:
            raise MaterialInvalid(
                f"doc_id 重复：{doc_id}",
                error_type="DuplicateDocId",
                detail={"doc_id": doc_id},
            )
        seen.add(doc_id)

        raw_text = doc.get("text", doc.get("content", ""))
        if raw_text is None:
            raise MaterialInvalid(
                f"材料 {doc_id} 的正文为 None",
                error_type="EmptyMaterial",
                detail={"doc_id": doc_id},
            )
        text = str(raw_text)
        if not text.strip():
            raise MaterialInvalid(
                f"材料 {doc_id} 的正文为空（不可读）",
                error_type="EmptyMaterial",
                detail={"doc_id": doc_id},
            )

        original_chars = len(text)
        truncated = original_chars > MAX_DOC_CHARS
        if truncated:
            text = text[:MAX_DOC_CHARS]

        materials.append(
            Material(
                doc_id=doc_id,
                kind=str(doc.get("kind", "") or ""),
                text=text,
                sha256=_sha256(text),
                original_chars=original_chars,
                truncated=truncated,
                source={
                    "filename": str(doc.get("filename", "") or ""),
                    "pages": doc.get("pages"),
                },
            )
        )
    return materials


def repo_root() -> Path:
    """仓库根（`claims/` 的父目录）。"""
    return Path(__file__).resolve().parents[2]


def materials_root() -> Path:
    """材料工作区根：**`<CLAIMS_DATA_DIR>/materials`**（默认 `claims/data/materials`）。

    t22 / I5-c 修复：这里过去把 `claims/data/materials` 写死，导致 `claims/tests` 的
    `tmp_env`（`CLAIMS_DATA_DIR=<tmp>`）**看着隔离、实际仍写仓库**——比不隔离更危险，
    因为人会基于"测试用临时目录"这个假设省掉人工检查。

    现在根统一从 F2 的 `claims.config.data_dir()` 取（该函数逐次读环境变量，所以
    monkeypatch/`DEEPAGENTS_*` 风格的 per-test 覆盖立刻生效），与
    `analysis_cache_dir()` / `idempotency_dir()` / `checkpoint_db()` 同一根。
    """
    try:  # 只 import 不改：配置权威在 F2 的 claims/config.py
        from claims import config as claims_config  # noqa: PLC0415

        base = Path(claims_config.data_dir())
    except Exception:  # pragma: no cover - claims.config 不可导入时退回模块相对路径
        base = Path(__file__).resolve().parents[1] / "data"
    return base / "materials"


def safe_workspace_root(candidate: str | Path | None = None) -> Path:
    """返回并断言一个**安全**的 Deep Agents `root_dir`。

    安全定义（任一不满足即抛 `MaterialInvalid`，绝不"尽力而为"）：

    1. 解析后必须是绝对路径；
    2. 必须位于 `<CLAIMS_DATA_DIR>/materials/` 之内（等于或更深；默认 `claims/data/materials/`）；
    3. 不得等于仓库根、也不得是仓库根的祖先（否则 `.env` 可被 `read_file "/.env"` 触及）。
    """
    root = Path(candidate) if candidate is not None else materials_root()
    resolved = root.resolve()
    allowed_base = materials_root().resolve()
    repo = repo_root().resolve()

    if resolved == repo or repo.is_relative_to(resolved):
        raise MaterialInvalid(
            f"拒绝对仓库根或其祖先使用 FilesystemBackend：{resolved}",
            error_type="UnsafeWorkspaceRoot",
            detail={"root": str(resolved), "repo_root": str(repo)},
        )
    if not (resolved == allowed_base or resolved.is_relative_to(allowed_base)):
        raise MaterialInvalid(
            f"工作区必须位于 {allowed_base} 之内，实际为 {resolved}",
            error_type="UnsafeWorkspaceRoot",
            detail={"root": str(resolved), "allowed_base": str(allowed_base)},
        )
    return resolved


@dataclass
class MaterialWorkspace:
    """一次分析的材料工作区（临时目录，用完可删）。"""

    root: Path
    materials: list[Material]

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME

    def manifest(self) -> list[dict[str, Any]]:
        return [m.manifest_row() for m in self.materials]

    def texts(self) -> dict[str, str]:
        """doc_id -> 正文（逐字校验用）。"""
        return {m.doc_id: m.text for m in self.materials}

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def materialize(materials: list[Material], *, root: str | Path | None = None) -> MaterialWorkspace:
    """把材料写成文件 + manifest，返回工作区。`root` 强制走 `safe_workspace_root()`。"""
    base = safe_workspace_root(root)
    base.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="analysis-", dir=base))
    for material in materials:
        (workdir / material.filename).write_text(material.text, encoding="utf-8")
    (workdir / MANIFEST_NAME).write_text(
        json.dumps(
            {"schema_version": "materials-manifest/1", "documents": [m.manifest_row() for m in materials]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return MaterialWorkspace(root=workdir, materials=materials)


__all__ = [
    "MAX_DOC_CHARS",
    "MANIFEST_NAME",
    "DOC_ID_RE",
    "Material",
    "MaterialWorkspace",
    "prepare_materials",
    "materialize",
    "materials_root",
    "repo_root",
    "safe_workspace_root",
]
