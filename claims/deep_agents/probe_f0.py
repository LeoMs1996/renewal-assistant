"""F0 探针：在 deepagents==0.7.39 上逐条验证 R3（docs/research/r3-langgraph-deepagents.md）的 4 条结论。

设计原则
- 完全离线：用 RecordingFakeModel（BaseChatModel 子类）代替真实 LLM，不读 .env、不发网络请求。
- 不写项目目录：临时文件只落在 tempfile.mkdtemp()。
- 每条断言独立打印 EVIDENCE / VERDICT，便于直接贴进 step-f0.md。

运行：
    .venv-claims/bin/python claims/deep_agents/probe_f0.py
"""

from __future__ import annotations

import inspect
import json
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

RESULTS: list[dict[str, Any]] = []


def record(assertion: str, ok: bool, evidence: str) -> None:
    RESULTS.append({"assertion": assertion, "ok": ok, "evidence": evidence})
    print(f"\n[{'PASS' if ok else 'FAIL'}] {assertion}")
    print(f"EVIDENCE: {evidence}")


class RecordingFakeModel(BaseChatModel):
    """按脚本回放 AIMessage，并记录被 bind 的工具名（用于观察模型可见工具面）。"""

    replies: list[AIMessage]
    idx: int = 0
    bound_tools: list[str] = []
    generate_calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def bind_tools(self, tools: Any, **kwargs: Any) -> RecordingFakeModel:  # noqa: ANN401
        names = []
        for t in tools:
            name = getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None)
            if name:
                names.append(name)
        self.bound_tools = sorted(set(self.bound_tools) | set(names))
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> ChatResult:
        self.generate_calls += 1
        msg = self.replies[min(self.idx, len(self.replies) - 1)]
        self.idx += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def build_fake(*replies: AIMessage) -> RecordingFakeModel:
    return RecordingFakeModel(replies=list(replies) or [AIMessage(content="ok")])


def invoke_once(agent: Any, text: str = "hi") -> Any:  # noqa: ANN401
    return agent.invoke({"messages": [HumanMessage(content=text)]})


def main() -> int:
    from deepagents import create_deep_agent
    from deepagents.backends import FilesystemBackend
    from langgraph.graph.state import CompiledStateGraph

    print("=" * 78)
    print("deepagents probe — environment")
    from importlib.metadata import version as _v

    import deepagents

    print("deepagents:", _v("deepagents"))
    print("langchain_core:", _v("langchain-core"))
    print("langchain:", _v("langchain"))
    print("langgraph:", _v("langgraph"))

    tmpdir = Path(tempfile.mkdtemp(prefix="probe-f0-"))
    backend = FilesystemBackend(root_dir=tmpdir)

    # ---------------------------------------------------------------- A1
    model = build_fake(AIMessage(content="finished"))
    agent = create_deep_agent(model=model, backend=backend)
    ok1 = isinstance(agent, CompiledStateGraph)
    record(
        "A1 create_deep_agent(...) 返回 CompiledStateGraph（R3 §3：内部就是 LangGraph 图）",
        ok1,
        f"type={type(agent).__module__}.{type(agent).__name__}; "
        f"isinstance(CompiledStateGraph)={ok1}; "
        f"graph nodes={sorted(n for n in agent.get_graph().nodes if not n.startswith('__'))}",
    )

    # ---------------------------------------------------------------- A2
    fs_methods = [m for m in dir(FilesystemBackend) if not m.startswith("_")]
    file_ops = [m for m in ("write", "read", "ls", "glob", "grep", "edit") if m in fs_methods]
    write_res = backend.write("/probe.txt", "hello-f0")
    read_res = backend.read("/probe.txt")
    read_text = read_res if isinstance(read_res, str) else json.dumps(read_res, ensure_ascii=False, default=str)
    # 真实走一遍 invoke，让 bind_tools 被调用，才能看到模型可见工具面
    invoke_once(agent)
    tool_names = model.bound_tools
    # 源码层交叉验证：文件系统后端本体是否含 shell 执行能力；LocalShellBackend 是对照组
    from deepagents.backends import LocalShellBackend
    fs_src = Path(inspect.getfile(FilesystemBackend)).read_text(errors="ignore")
    ls_src = Path(inspect.getfile(LocalShellBackend)).read_text(errors="ignore")
    # 区分两类事实：（a）模型可用的 shell 工具；（b）实现内部是否 fork 子进程
    model_shell = {
        "FilesystemBackend has 'execute' method": hasattr(FilesystemBackend, "execute"),
        "FilesystemBackend has 'shell' attr": hasattr(FilesystemBackend, "shell"),
        "'execute' in model-visible tools": "execute" in tool_names,
    }
    # 真正的 shell 语义：shell=True / os.system / os.execv（模型可控命令行）
    unsafe_tokens = ("shell=True", "os.system", "os.execv", "os.popen")
    fs_unsafe = {t: fs_src.count(t) for t in unsafe_tokens if fs_src.count(t)}
    ls_unsafe = {t: ls_src.count(t) for t in unsafe_tokens if ls_src.count(t)}
    # 实现内部仅用于 ripgrep 加速：argv 列表 + `--` 终止符 + 无 shell=True
    rg_argv_style = ("cmd.extend([\"--\", pattern, \".\"])" in fs_src) or ("\"--\", pattern" in fs_src)
    rg_popen = fs_src.count("subprocess.Popen")
    rg_fallback = "using Python grep fallback" in fs_src
    ok2 = (
        not any(model_shell.values())
        and not fs_unsafe
        and "hello-f0" in read_text
        and bool(file_ops)
        and rg_argv_style
        and rg_popen >= 1
    )
    record(
        "A2 FilesystemBackend(root_dir=...) 可实例化、可读写、不向模型暴露 shell（R3 §4）",
        ok2,
        f"root_dir={tmpdir.name}/…; file_ops={file_ops}; write→{write_res}; read→{read_text[:56]!r}; "
        f"model-visible tools={tool_names}; "
        f"模型可见 shell 能力={model_shell}; "
        f"filesystem.py 中 shell 语义令牌={fs_unsafe or 'none'}; "
        f"内部 subprocess 仅为 ripgrep 加速：Popen 次数={rg_popen}, argv 列表+`--`终止符={rg_argv_style}, "
        f"Python grep 回退={rg_fallback}; "
        f"对照组 local_shell.py 中 shell 语义令牌={ls_unsafe}, LocalShellBackend.execute={hasattr(LocalShellBackend, 'execute')}",
    )

    # ---------------------------------------------------------------- A4（先做，构造上更简单）
    from langchain.agents.middleware import TodoListMiddleware

    default_model = build_fake(AIMessage(content="done"))
    default_agent = create_deep_agent(model=default_model, backend=FilesystemBackend(root_dir=tmpdir))
    invoke_once(default_agent)
    todo_model = build_fake(AIMessage(content="done"))
    todo_agent = create_deep_agent(
        model=todo_model,
        backend=FilesystemBackend(root_dir=tmpdir),
        middleware=[TodoListMiddleware()],
    )
    invoke_once(todo_agent)
    ok4 = ("write_todos" not in default_model.bound_tools) and ("write_todos" in todo_model.bound_tools)
    record(
        "A4 v0.7 起 todo planning 为 opt-in：默认无 write_todos，显式传 TodoListMiddleware 才有（R3 §4）",
        ok4,
        f"default agent tools={default_model.bound_tools} (write_todos absent="
        f"{'write_todos' not in default_model.bound_tools}); "
        f"with TodoListMiddleware tools={todo_model.bound_tools} "
        f"(write_todos present={'write_todos' in todo_model.bound_tools})",
    )

    # ---------------------------------------------------------------- A3
    from deepagents.middleware.subagents import SubAgent

    alpha_model = build_fake(AIMessage(content="alpha report"))
    beta_model = build_fake(AIMessage(content="beta report"))
    subagents: list[SubAgent] = [
        {"name": "alpha", "description": "分析材料 A", "system_prompt": "you are alpha", "model": alpha_model},
        {"name": "beta", "description": "分析材料 B", "system_prompt": "you are beta", "model": beta_model},
    ]
    main_model = build_fake(
        AIMessage(
            content="",
            tool_calls=[
                {"name": "task", "args": {"description": "run alpha", "subagent_type": "alpha"}, "id": "call_a"},
                {"name": "task", "args": {"description": "run beta", "subagent_type": "beta"}, "id": "call_b"},
            ],
        ),
        AIMessage(content="both done"),
    )
    multi_agent = create_deep_agent(
        model=main_model,
        backend=FilesystemBackend(root_dir=tmpdir),
        subagents=subagents,
    )
    out = invoke_once(multi_agent, "dispatch both")
    tool_msgs = [m for m in out["messages"] if isinstance(m, ToolMessage)]
    task_msgs = [m for m in tool_msgs if getattr(m, "name", None) == "task"]
    # 主模型只被调用一次（第一轮）就发出两个 task 调用 ⇒ 同一轮并行扇出
    ok3 = (
        "task" in main_model.bound_tools
        and len(task_msgs) == 2
        and alpha_model.generate_calls == 1
        and beta_model.generate_calls == 1
    )
    from deepagents.middleware.subagents import TASK_TOOL_DESCRIPTION

    record(
        "A3 子代理经 task 工具调用，且同一轮可并行多个（R3 §4）",
        ok3,
        f"'task' in main tools={'task' in main_model.bound_tools}; "
        f"主模型首轮一次 AIMessage 带 tool_calls=2; "
        f"task ToolMessage 数={len(task_msgs)}; "
        f"alpha generate_calls={alpha_model.generate_calls}, beta generate_calls={beta_model.generate_calls}; "
        f"task 工具描述含并行指令={'Launch multiple agents concurrently' in TASK_TOOL_DESCRIPTION}; "
        f"tool_call_ids={[m.tool_call_id for m in task_msgs]}",
    )

    print("\n" + "=" * 78)
    passed = sum(1 for r in RESULTS if r["ok"])
    print(f"SUMMARY: {passed}/{len(RESULTS)} assertions passed on deepagents {deepagents.__version__}")
    for r in RESULTS:
        print(f"  {'PASS' if r['ok'] else 'FAIL'} — {r['assertion']}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
