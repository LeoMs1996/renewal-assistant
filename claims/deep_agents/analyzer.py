"""F3 长程材料分析层（Deep Agents）——**唯一对外入口** `run_analysis`。

调用契约（F2 `claims/graph.py::run_analysis` 已写死，签名逐字一致）::

    def run_analysis(docs: list[dict], *, analyzer_version: str) -> dict

返回与 `claims/tools/rules_analyzer.py` **同一份** `materials-analysis/1` 结构的 dict
（调用方不区分来源，只按 `analyzer.mode` 判断是否降级）。

## 设计要点

1. **Deep Agents 只是 `analyze_materials` 节点内部的一次调用**（ARCHITECTURE §5.1）：
   本模块构建一个 `CompiledStateGraph`（`create_deep_agent(...)` 的返回值，F0 断言 A1
   已实证），invoke 一次，取 `structured_response`，再用**代码**补齐 `analyzer` /
   `coverage` / `cost`。外层确定性流程仍由 `claims/graph.py` 掌控。

2. **`response_format=ToolStrategy(MaterialsAnalysisDraft)` 是 schema 层约束**
   （F0 探到的官方入口）：材料里的「直接赔付 100 万」即使说服了模型，Draft 也没有
   对应字段，`extra="forbid"` 会让那次输出**校验失败** → `ANALYSIS_SCHEMA_INVALID`。
   这不是靠提示词，是靠类型系统。

3. **文件系统 root 永远显式**：`FilesystemBackend(root_dir=<claims/data/materials/...>)`。
   `root_dir=None` 会退化成当前工作目录（仓库根有 `.env`），`materials.safe_workspace_root()`
   会拒绝危险路径；测试覆盖 `../.env`、`../../.env`、`claims/../../.env` 三种写法。

4. **超时/失败显式抛出，绝不静默降级**：本层没有 `except: use rules_fallback` 这种分支。
   降级是 F2 的决定（`claims/graph.py` 兜底），本层只负责让失败**可见**——
   异常自带契约 §5 错误码 + `error_type`，`degraded` 恒为 `False`。

5. **时间预算**：Deep Agents 没有内置超时参数。这里在主线程用
   `stream(stream_mode="values")` 并**逐步检查墙钟 deadline**：超预算立即抛
   `AnalysisTimeout`（真能中断、不留孤儿线程）。不用工作线程的原因见
   `_run_graph_with_deadline` 的 docstring（实测主线程 6.4s 成功、线程里 90s 卡死）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import (
    AnalysisError,
    AnalysisSchemaInvalid,
    AnalysisTimeout,
    AnalysisUnavailable,
    StructuredOutputMissing,
)
from .materials import MaterialWorkspace, materialize, prepare_materials
from .prompts import PHOTO_SUBAGENT, SYSTEM_PROMPT, TEXT_SUBAGENT, user_prompt
from .schema import (
    AnalyzerInfo,
    Cost,
    Coverage,
    DocumentAnalysis,
    MaterialsAnalysis,
    MaterialsAnalysisDraft,
)

#: 本层实现标识（`analyzer.mode`）
ANALYZER_IMPL = "deepagents"
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_RECURSION_LIMIT = 40
DEFAULT_MAX_ATTEMPTS = 2  # 契约 §5：ANALYSIS_SCHEMA_INVALID 内部重试 1 次
#: 材料份数超过该值时启用子代理与 todo（ARCHITECTURE §5.1）
SUBAGENT_THRESHOLD = 3
#: 供应商侧单次回复上限（材料分析输出是结构化 JSON，不需要长文本）
MAX_OUTPUT_TOKENS = 8192


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default


@dataclass
class AnalysisConfig:
    """一次分析的运行配置（测试可整体注入；生产由环境变量解析）。"""

    #: BaseChatModel 实例，或 "provider:model" 字符串；None → 按项目凭证自动构建
    model: Any = None
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    recursion_limit: int = DEFAULT_RECURSION_LIMIT
    enable_subagents: bool = True
    keep_workspace: bool = False
    workspace_root: Path | None = None
    model_label: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> AnalysisConfig:
        """从环境变量解析（`.env` 由 `server.config` 解析，见 `resolve_model`）。"""
        model_spec = (os.environ.get("DEEPAGENTS_MODEL") or "").strip() or None
        return cls(
            model=model_spec,
            timeout_s=_env_float("DEEPAGENTS_TIMEOUT_S", DEFAULT_TIMEOUT_S),
            max_attempts=max(1, _env_int("DEEPAGENTS_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS)),
            recursion_limit=max(4, _env_int("DEEPAGENTS_RECURSION_LIMIT", DEFAULT_RECURSION_LIMIT)),
            enable_subagents=_env_flag("DEEPAGENTS_SUBAGENTS", True),
            keep_workspace=_env_flag("CLAIMS_ANALYSIS_KEEP_WORKSPACE", False),
            model_label=model_spec or "",
        )


# --------------------------------------------------------------------------- #
# 模型解析
# --------------------------------------------------------------------------- #
def _project_env(name: str) -> str | None:
    """按「进程环境 > 项目 .env」取配置，复用 `server.config.env`（只 import，不改）。"""
    try:
        from server import config as server_config  # noqa: PLC0415

        return server_config.env(name)
    except Exception:  # pragma: no cover - server 不可导入时退回纯环境变量
        return os.environ.get(name)


def resolve_model(config: AnalysisConfig) -> tuple[Any, str]:
    """解析 `create_deep_agent(model=...)` 的对象，并给出 `analyzer.model` 标签。

    三条路径（都显式，不猜）：

    1. `config.model` 是 BaseChatModel 实例（测试注入）；
    2. `config.model` 是 `"provider:model"` 字符串 → 交给 LangChain 解析；
    3. 都没有 → 用项目**既有**的 Anthropic 兼容端点凭证（`ANTHROPIC_BASE_URL` /
       `ANTHROPIC_AUTH_TOKEN` / `MODEL_NAME`，与续保域同一套），经
       `langchain_anthropic.ChatAnthropic` 构建（该包随 deepagents 一并装入 `.venv-claims`）。

    无可用凭证 → `AnalysisUnavailable(error_type="NoModelConfigured")`，
    **不**退回规则模式（那是调用方的决定）。
    """
    model = config.model
    if model is not None and not isinstance(model, str):
        label = config.model_label or getattr(model, "model_name", "") or type(model).__name__
        return model, str(label)

    if isinstance(model, str) and model and not model.strip().lower().startswith("project"):
        return model, model

    # 只有显式 `DEEPAGENTS_MODEL=project` 才复用项目凭证：
    # 否则「DEEPAGENTS_ENABLED=true」会静默打真实 API（意外花费 + 不可复现的测试）。
    if str(model).strip().lower() not in {"project", "project:anthropic", "project:anthropic-compat"}:
        raise AnalysisUnavailable(
            "未配置模型：请设置 DEEPAGENTS_MODEL（provider:model，或用 `project` 复用项目 "
            "ANTHROPIC_* 凭证）。本层不会自行猜测模型。",
            error_type="NoModelConfigured",
        )

    base_url = _project_env("ANTHROPIC_BASE_URL")
    token = _project_env("ANTHROPIC_AUTH_TOKEN") or _project_env("ANTHROPIC_API_KEY")
    name = _project_env("MODEL_NAME") or _project_env("ANTHROPIC_MODEL")
    if not (base_url and token and name):
        raise AnalysisUnavailable(
            "DEEPAGENTS_MODEL=project 但项目缺少 ANTHROPIC_BASE_URL / "
            "ANTHROPIC_AUTH_TOKEN / MODEL_NAME",
            error_type="ProjectCredentialsMissing",
        )
    try:  # 延迟导入：缺包时给出可读错误而不是 ImportError 栈
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise AnalysisUnavailable(
            f"langchain-anthropic 不可用：{type(exc).__name__}",
            error_type="ProviderPackageMissing",
        ) from exc

    chat = ChatAnthropic(
        model=name,
        anthropic_api_url=base_url,
        anthropic_api_key=token,
        max_tokens=MAX_OUTPUT_TOKENS,
        timeout=config.timeout_s,
        max_retries=0,  # 重试由本层控制，避免不可控的指数退避
    )
    return chat, f"anthropic-compat:{name}"


# --------------------------------------------------------------------------- #
# Agent 构建
# --------------------------------------------------------------------------- #
def build_agent(*, model: Any, workspace: MaterialWorkspace, config: AnalysisConfig) -> Any:
    """构建 Deep Agents 分析器（返回 `CompiledStateGraph`）。"""
    try:
        from deepagents import create_deep_agent  # noqa: PLC0415
        from deepagents.backends import FilesystemBackend  # noqa: PLC0415
        from langchain.agents.middleware import TodoListMiddleware  # noqa: PLC0415
        from langchain.agents.structured_output import ToolStrategy  # noqa: PLC0415
    except ImportError as exc:
        raise AnalysisUnavailable(
            "deepagents 未安装或不可导入（本应装在 .venv-claims）",
            error_type="DeepAgentsNotInstalled",
            detail={"import_error": str(exc)},
        ) from exc

    many_docs = len(workspace.materials) > SUBAGENT_THRESHOLD
    subagents = None
    middleware: list[Any] = []
    if many_docs and config.enable_subagents:
        # 子代理经 `task` 工具调用（不是 LangGraph 节点），同轮可并行多个（F0 断言 A3）
        subagents = [dict(PHOTO_SUBAGENT), dict(TEXT_SUBAGENT)]
        # v0.7 起 todo planning 是 opt-in（F0 断言 A4）：材料多时才打开分步进度
        middleware.append(TodoListMiddleware())

    return create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        # ← schema 层硬边界：模型无处安放金额/决策字段
        response_format=ToolStrategy(schema=MaterialsAnalysisDraft),
        # ← 文件系统只在此目录内活动；root_dir 永不省略
        backend=FilesystemBackend(
            root_dir=str(workspace.root), virtual_mode=True, max_file_size_mb=10
        ),
        middleware=tuple(middleware),
        subagents=subagents,
        name="claims-materials-analyst",
    )


# --------------------------------------------------------------------------- #
# 调用（含超时）
# --------------------------------------------------------------------------- #
def _run_graph_with_deadline(
    agent: Any, prompt: str, *, timeout_s: float, recursion_limit: int
) -> dict:
    """在主线程跑图，逐步检查墙钟 deadline；超时抛 `AnalysisTimeout`。

    为什么**不用线程**（实测踩出来的）：同一份图在主线程 `invoke` 6.4s 完成，放进工作线程
    后 90s 都拿不到结果（LangGraph/deepagents 的中间件链路在非主线程里会卡住）；而线程
    又无法强杀，超时后只能留下孤儿线程继续跑（实测让进程多挂 2 分钟）。

    改为 `stream(stream_mode="values")` + 逐步 deadline：
    - 每步之间检查预算，超预算立即抛错（真能中断，不留孤儿）；
    - 最后一步的 values 就是 `invoke` 的返回值；
    - 单次 provider 调用的硬上限由 `ChatAnthropic(timeout=...)` 兜底（见 `resolve_model`）。
    """
    import time as _time  # noqa: PLC0415

    deadline = _time.monotonic() + timeout_s
    state: dict | None = None
    steps = 0
    for step in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": recursion_limit},
        stream_mode="values",
    ):
        steps += 1
        state = step
        if _time.monotonic() > deadline:
            raise AnalysisTimeout(
                f"材料分析超时（{timeout_s:.0f}s，已跑 {steps} 步）",
                detail={"timeout_s": timeout_s, "steps": steps},
            )
    if state is None:  # pragma: no cover - stream 至少产出一次
        raise AnalysisUnavailable("图未产出任何状态", error_type="EmptyGraphStream")
    return state


# --------------------------------------------------------------------------- #
# 结果校验与回填
# --------------------------------------------------------------------------- #
def _usage_from_messages(messages: list[Any]) -> tuple[int, int, int]:
    tokens_in = tokens_out = tool_calls = 0
    for msg in messages or []:
        usage = getattr(msg, "usage_metadata", None)
        if isinstance(usage, dict):
            tokens_in += int(usage.get("input_tokens") or 0)
            tokens_out += int(usage.get("output_tokens") or 0)
        calls = getattr(msg, "tool_calls", None)
        if calls:
            tool_calls += len(calls)
    return tokens_in, tokens_out, tool_calls


def _kind_of(workspace: MaterialWorkspace, doc_id: str) -> str:
    for material in workspace.materials:
        if material.doc_id == doc_id:
            return material.kind
    return ""


def validate_and_enrich(
    payload: Any,
    *,
    workspace: MaterialWorkspace,
    model_label: str,
    impl_version: str,
    cost: tuple[int, int, int] = (0, 0, 0),
) -> MaterialsAnalysis:
    """把模型 draft 收口成最终 `MaterialsAnalysis`（逐字引用校验 + 缺失补齐 + 代码填字段）。"""
    if payload is None:
        raise StructuredOutputMissing(
            "模型未产出结构化结果（structured_response 为 None）：可能没调用 "
            "MaterialsAnalysisDraft 工具",
            detail={"expected_tool": MaterialsAnalysisDraft.__name__},
        )
    if isinstance(payload, MaterialsAnalysisDraft):
        draft = payload
    elif isinstance(payload, MaterialsAnalysis):
        draft = MaterialsAnalysisDraft(
            documents=payload.documents, missing_items=payload.missing_items
        )
    elif isinstance(payload, dict):
        try:
            draft = MaterialsAnalysisDraft.model_validate(payload)
        except Exception as exc:
            raise AnalysisSchemaInvalid(
                f"模型输出不符 materials-analysis/1：{type(exc).__name__}",
                detail={"error": str(exc)[:400]},
            ) from exc
    else:
        raise AnalysisSchemaInvalid(
            f"structured_response 类型非法：{type(payload).__name__}",
        )

    texts = workspace.texts()
    known_ids = set(texts)
    dropped_unknown_docs = 0
    documents: list[DocumentAnalysis] = []

    for doc in draft.documents:
        if doc.doc_id not in known_ids:
            dropped_unknown_docs += 1  # 编造的 doc_id：丢弃并计数（不静默）
            continue
        kept = []
        bad_quote = 0
        for fact in doc.facts:
            source_text = texts.get(fact.evidence.doc_id)
            if source_text is None:
                bad_quote += 1
                continue
            # 逐字子串校验（契约 §4.3 硬约束 2）
            if fact.evidence.quote not in source_text:
                bad_quote += 1
                continue
            kept.append(fact)
        anomalies = list(doc.anomalies)
        if bad_quote:
            anomalies.append(f"quote_not_verbatim:{bad_quote}")
        expected_kind = _kind_of(workspace, doc.doc_id)
        if doc.kind and expected_kind and doc.kind != expected_kind:
            anomalies.append(f"kind_mismatch:{doc.kind}!={expected_kind}")
        documents.append(
            doc.model_copy(
                update={
                    "facts": kept,
                    "anomalies": anomalies,
                    "kind": doc.kind or expected_kind,
                }
            )
        )

    analyzed_ids = {d.doc_id for d in documents}
    for missing_id in sorted(known_ids - analyzed_ids):
        # 模型漏了某份材料：补一条空分析并显式标注，避免"看起来都分析了"
        documents.append(
            DocumentAnalysis(
                doc_id=missing_id,
                kind=_kind_of(workspace, missing_id),
                facts=[],
                anomalies=["skipped_by_model"],
            )
        )

    tokens_in, tokens_out, tool_calls = cost
    analysis = MaterialsAnalysis.from_draft(
        draft,
        analyzer=AnalyzerInfo(mode=ANALYZER_IMPL, model=model_label, version=impl_version),
        coverage=Coverage(requested_docs=len(workspace.materials), analyzed_docs=len(analyzed_ids)),
        cost=Cost(tokens_in=tokens_in, tokens_out=tokens_out, tool_calls=tool_calls),
    )
    analysis = analysis.model_copy(
        update={
            "documents": documents,
            "missing_items": list(draft.missing_items),
        }
    )
    if dropped_unknown_docs:
        # 计数可见化：挂在该层的 anomalies 上（schema 无额外字段可用）
        analysis = analysis.model_copy(
            update={
                "documents": analysis.documents
                + [
                    DocumentAnalysis(
                        doc_id="unknown",
                        kind="",
                        anomalies=[f"unknown_doc_id_dropped:{dropped_unknown_docs}"],
                    )
                ]
            }
        )
    return analysis


def _deepagents_version() -> str:
    try:
        from importlib.metadata import version  # noqa: PLC0415

        return version("deepagents")
    except Exception:  # pragma: no cover
        return "unknown"


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def analyze(
    docs: list[dict[str, Any]] | None,
    *,
    config: AnalysisConfig,
    analyzer_version: str,
) -> dict[str, Any]:
    """可注入配置的实现体（测试用）。契约入口见 `run_analysis`。"""
    materials = prepare_materials(docs)
    workspace = materialize(materials, root=config.workspace_root)
    try:
        for attempt in range(1, max(1, config.max_attempts) + 1):
            try:
                return _analyze_once(
                    workspace,
                    config=config,
                    analyzer_version=analyzer_version,
                    attempt=attempt,
                )
            except AnalysisSchemaInvalid:
                # 只有 schema 问题内部重试（契约 §5：重试 1 次）
                if attempt >= config.max_attempts:
                    raise
        raise AssertionError("unreachable")  # pragma: no cover
    finally:
        if not config.keep_workspace:
            workspace.cleanup()


def _analyze_once(
    workspace: MaterialWorkspace,
    *,
    config: AnalysisConfig,
    analyzer_version: str,
    attempt: int,
) -> dict[str, Any]:
    model, model_label = resolve_model(config)
    agent = build_agent(model=model, workspace=workspace, config=config)
    prompt = user_prompt(workspace.manifest())
    try:
        result = _run_graph_with_deadline(
            agent,
            prompt,
            timeout_s=config.timeout_s,
            recursion_limit=config.recursion_limit,
        )
    except AnalysisError:
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        if error_type == "GraphRecursionError":
            raise AnalysisSchemaInvalid(
                f"模型未能产出合法结构化输出（第 {attempt} 次尝试后触及 recursion_limit）",
                error_type="StructuredOutputRetriesExhausted",
                detail={"attempt": attempt, "recursion_limit": config.recursion_limit},
            ) from exc
        raise AnalysisUnavailable(
            f"材料分析调用失败：{error_type}: {str(exc)[:300]}",
            error_type=error_type,
            detail={"attempt": attempt},
        ) from exc

    cost = _usage_from_messages(list(result.get("messages") or []))
    analysis = validate_and_enrich(
        result.get("structured_response"),
        workspace=workspace,
        model_label=model_label,
        impl_version=_deepagents_version(),
        cost=cost,
    )
    return analysis.model_dump(mode="json")


def run_analysis(docs: list[dict[str, Any]], *, analyzer_version: str) -> dict[str, Any]:
    """**契约入口**（F2 调用，签名逐字一致）。

    Args:
        docs: 材料列表，每项至少含 `doc_id` / `kind` / `text`。
        analyzer_version: 调用方版本标识（F2 传的是规则分析器版本号；本层不把它写进
            `analyzer.version`——那个字段必须是分析器真实版本，否则降级可观测性失真）。

    Returns:
        `materials-analysis/1` 结构的 dict，`analyzer.mode == "deepagents"`。

    Raises:
        MaterialMissing / MaterialInvalid: 材料缺失或不可读（`MATERIAL_MISSING`）
        AnalysisUnavailable: deepagents 未装 / 无模型凭证 / provider 失败（`ANALYSIS_UNAVAILABLE`）
        AnalysisTimeout: 超时（`ANALYSIS_UNAVAILABLE` + `error_type=AnalysisTimeout`）
        AnalysisSchemaInvalid: 输出不符 schema（`ANALYSIS_SCHEMA_INVALID`）

    本函数**不做**任何静默降级：失败就抛，由 F2 决定是否退回 `rules_analyzer`。
    """
    return analyze(docs, config=AnalysisConfig.from_env(), analyzer_version=analyzer_version)


__all__ = [
    "AnalysisConfig",
    "resolve_model",
    "build_agent",
    "validate_and_enrich",
    "analyze",
    "run_analysis",
    "ANALYZER_IMPL",
    "SUBAGENT_THRESHOLD",
]
