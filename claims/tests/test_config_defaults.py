"""默认值守卫：`DEEPAGENTS_ENABLED` 默认 `false` 是整套理赔测试的**单点依赖**。

背景（t16/F2b 发现的 R1）：`claims/tests/conftest.py::tmp_env` 把
`DEEPAGENTS_ENABLED=false` 显式写死，其余用例因此不会碰真实模型。
但**默认值本身**（`claims/config.py` 里 `_env("DEEPAGENTS_ENABLED", "false")` 的那个
`"false"`）此前没有任何测试覆盖——一旦它被改成 `true`，凡是没走 `tmp_env` 的用例
（以及将来忘记挂 fixture 的新用例）都会去打真实模型：慢、需要凭证、失败现象还会与
业务断言混在一起，极难定位。

本文件据此把「默认值」变成被测对象：
- 断言的是**源码里的默认字面量**（源头），不只是 `deepagents_enabled()` 读出来的值；
- 断言运行期在**没有环境变量**时确实得到 `False`；
- **不使用 `tmp_env`**（否则就成了循环依赖：用被测的 fixture 去验证它保护的东西）。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "claims" / "config.py"

#: 依赖 `tmp_env` 的用例数（用于失败信息；运行期动态统计更准确）
_ENV_VAR = "DEEPAGENTS_ENABLED"


def _dependent_test_count() -> int:
    """统计 claims/tests 下显式使用 `tmp_env` 的用例数量（失败信息里给出真实后果）。"""
    count = 0
    for path in (REPO_ROOT / "claims" / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                args = {a.arg for a in node.args.args}
                if "tmp_env" in args:
                    count += 1
    return count


def _source_default_literal() -> str | None:
    """从 `claims/config.py` 的 AST 里取 `_env("DEEPAGENTS_ENABLED", "<字面量>")` 的默认值。"""
    tree = ast.parse(CONFIG_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "_env" or len(node.args) < 2:
            continue
        key = node.args[0]
        default = node.args[1]
        if isinstance(key, ast.Constant) and key.value == _ENV_VAR and isinstance(default, ast.Constant):
            return default.value
    return None


# --------------------------------------------------------------------------- #
# 1. 默认值守卫（核心）
# --------------------------------------------------------------------------- #
def test_default_deepagents_enabled_is_false():
    """默认必须是 false。

    失败后果（写进消息，避免后来者把它当"无害的开关"随手改）：
    ``tmp_env`` 外的用例会真的去调 Deep Agents / 真实模型。
    """
    n = _dependent_test_count()
    literal = _source_default_literal()
    assert literal is not None, (
        f"没能在 {CONFIG_PATH} 里找到 `_env(\"{_ENV_VAR}\", ...)` 的默认值——"
        "配置读取方式变了？请同步更新本守卫测试，不要直接删掉它。"
    )
    assert str(literal).strip().lower() == "false", (
        f"{_ENV_VAR} 的源码默认值必须是字符串 'false'（实际 {literal!r}）。\n"
        f"改成 true/1/yes/on 会让 {n} 条依赖 tmp_env 的用例（以及将来忘记挂 fixture 的新用例）"
        "去调用真实模型：慢、需要凭证、失败现象与业务断言混在一起——"
        "宁可测试跑不起来并明确报错，也不要静默打真实模型。"
    )


def test_default_deepagents_enabled_runtime_is_false(monkeypatch):
    """运行期：环境变量缺失时 `config.deepagents_enabled()` 必须是 False。"""
    monkeypatch.delenv(_ENV_VAR, raising=False)
    from claims import config

    assert config.deepagents_enabled() is False, (
        f"未设置 {_ENV_VAR} 时 deepagents_enabled() 必须为 False（否则测试会打真实模型）"
    )


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on"])
def test_explicit_truthy_values_still_enable(monkeypatch, truthy):
    """显式真值仍然生效——守卫只锁「默认」，不锁「能力」。"""
    monkeypatch.setenv(_ENV_VAR, truthy)
    from claims import config

    assert config.deepagents_enabled() is True


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off", "", "  "])
def test_explicit_falsy_values_disable(monkeypatch, falsy):
    monkeypatch.setenv(_ENV_VAR, falsy)
    from claims import config

    assert config.deepagents_enabled() is False


# --------------------------------------------------------------------------- #
# 2. 测试侧的默认口径也要被钉住（否则"默认值对 + fixture 漏设"仍然会打模型）
# --------------------------------------------------------------------------- #
def test_tmp_env_fixture_pins_deepagents_off():
    """`tmp_env` 必须显式把开关设为 false（不只依赖 config 默认值）。"""
    conftest_src = (REPO_ROOT / "claims" / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert 'setenv("DEEPAGENTS_ENABLED", "false")' in conftest_src, (
        "claims/tests/conftest.py 的 tmp_env 必须显式 setenv(DEEPAGENTS_ENABLED, false)："
        "只靠 config 默认值的话，将来某人改默认值会连带影响所有用例。"
    )


def test_env_is_clean_for_this_test():
    """本文件自身不依赖任何环境变量注入（证明守卫不靠 fixture 才成立）。"""
    assert os.environ.get(_ENV_VAR) is None or os.environ[_ENV_VAR].strip().lower() in {
        "0",
        "false",
        "no",
        "off",
        "",
    }
