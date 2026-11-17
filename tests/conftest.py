"""pytest 收集配置。

有两个"脚本式"测试文件在模块顶层就执行断言并 `sys.exit()`（设计为
`python <file>` 直接运行、退出码即结论）。pytest 导入它们时会被 SystemExit
打断集合并报 INTERNALERROR。这里排除它们在 pytest 侧收集，改由 CI 以脚本
方式独立运行，两种入口都保留、互不干扰。

- tests/test_llm_normalization.py  → pytest 侧排除（脚本运行）
- mcp_servers/test_quote_server.py → 由 mcp_servers/conftest.py 排除
"""

# 平台工程域（2026-11-17）：单测跑 /chat 时会真实写轨迹 JSONL。此前 conftest
# 没有隔离 TRACE_DIR，导致每跑一次 tests/ 就往仓库 traces/ 里塞几百个文件
# （本次实测：跑完整套件后 traces/ 从 387 涨到 760）。这里在导入 server 之前
# 把 TRACE_DIR 指到临时目录，保证「测试不污染生产观测数据」。
# 用 setdefault：显式指定 TRACE_DIR 的 CI/本地场景仍然生效。
import os
import tempfile

os.environ.setdefault(
    "TRACE_DIR", tempfile.mkdtemp(prefix="renewal-test-traces-"))

collect_ignore = ["test_llm_normalization.py"]
