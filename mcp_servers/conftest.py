"""pytest 收集配置（同 tests/conftest.py 的理由）。

test_quote_server.py 是脚本式测试（模块顶层执行 + sys.exit），由 CI 以
`python mcp_servers/test_quote_server.py` 独立运行。
"""

collect_ignore = ["test_quote_server.py"]
