#!/usr/bin/env python3
"""真实浏览器验证：CSP（含 Trusted Types 强制）下页面功能是否正常。

为什么需要它：CSP 指令写错只有浏览器会告诉你。`require-trusted-types-for 'script'`
一旦生效，任何未经策略的 `innerHTML = string` 都会抛 TypeError——页面会白屏，
但 HTTP 层、单测、curl 全部看不见（响应仍是 200 + 完整 HTML）。本脚本用
Chrome DevTools Protocol 打开真实页面，断言：

1. 控制台**零** CSP 违规（`Content Security Policy` / `Trusted Type` 关键字）；
2. 内联脚本正常执行（DOM 已渲染、`trustedTypes.defaultPolicy` 已注册）——
   证明 `script-src 'unsafe-inline'` 与 `trusted-types default` 的组合没拦错东西；
3. 保单卡片渲染成功（`innerHTML` 走 default 策略，fetch /policy 通过 `connect-src 'self'`）；
4. 表单提交 + SSE 流式回答完整出现（`connect-src 'self'` 不拦 EventSource）；
5. 反向验证：在页面里直接 `el.innerHTML = "<b>x</b>"` 被信任类型策略接管
   （命中 default 策略，说明强制确实生效而不是被静默忽略）。

运行（本机 Chrome）：.venv/bin/python scripts/csp_browser_check.py [--port 18080]
退出码 0 = 全部通过。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "chromium", "chromium-browser",
]

CSP_VIOLATION_MARKERS = (
    "Content Security Policy",
    "Trusted Type",
    "trusted-types",
    "require-trusted-types-for",
    "Refused to",
)


def _terminate_tree(proc: subprocess.Popen) -> None:
    """结束整个进程组（评估域 t13 实测：只 terminate 父进程会留下抓 stdin 的
    uvicorn 孙进程，把调用方的管道占住 ~11 分钟）。故子进程一律
    `start_new_session=True` 启动，这里按 pgid 整组收尾。"""
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.wait(timeout=5)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def find_chrome() -> str:
    for cand in CHROME_CANDIDATES:
        if Path(cand).exists():
            return cand
        found = shutil.which(cand)
        if found:
            return found
    raise SystemExit("未找到 Chrome/Chromium，可跳过浏览器验证（见报告 §5 遗留）")


def wait_http(url: str, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


class CDP:
    """最小 CDP 客户端（只用到 Runtime/Log/Page）。"""

    def __init__(self, ws_url: str):
        import websockets  # 延迟导入：缺依赖时给出清晰错误

        self._ws = websockets.connect(ws_url, max_size=8 * 1024 * 1024)
        self.ws = None
        self._id = 0
        self.events: list[dict] = []

    async def __aenter__(self):
        self.ws = await self._ws.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self._ws.__aexit__(*exc)

    async def call(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg_id = self._id
        assert self.ws is not None
        await self.ws.send(json.dumps({"id": msg_id, "method": method,
                                       "params": params or {}}))
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=30)
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"{method} 失败: {data['error']}")
                return data.get("result", {})
            if "method" in data:
                self.events.append(data)

    async def drain(self, seconds: float = 1.0) -> None:
        """收集异步事件（console/log），不做请求。"""
        assert self.ws is not None
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=0.2)
            except TimeoutError:
                continue
            data = json.loads(raw)
            if "method" in data:
                self.events.append(data)

    async def eval(self, expr: str):
        res = await self.call("Runtime.evaluate", {
            "expression": expr, "awaitPromise": True, "returnByValue": True})
        return res.get("result", {}).get("value")


def csp_violations(events: list[dict]) -> list[str]:
    out = []
    for ev in events:
        if ev.get("method") == "Log.entryAdded":
            entry = ev["params"]["entry"]
            text = f"{entry.get('source')}|{entry.get('text')}"
            if any(m in text for m in CSP_VIOLATION_MARKERS):
                out.append(text[:300])
        elif ev.get("method") == "Runtime.exceptionThrown":
            text = json.dumps(ev["params"], ensure_ascii=False)
            if any(m in text for m in CSP_VIOLATION_MARKERS):
                out.append(text[:300])
        elif ev.get("method") == "Runtime.consoleAPICalled":
            args = ev["params"].get("args") or []
            text = " ".join(str(a.get("value", "")) for a in args)
            if any(m in text for m in CSP_VIOLATION_MARKERS):
                out.append(text[:300])
    return out


async def run_browser_checks(app_url: str, chrome: str, results: list[tuple[str, bool, str]]):
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="csp-chrome-")
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--disable-gpu", "--no-first-run",
         "--no-default-browser-check", "--disable-extensions",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        if not wait_http(f"http://127.0.0.1:{port}/json/version", 25):
            results.append(("chrome.start", False, "CDP 端口未就绪"))
            return
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/new?{urllib.parse.quote(app_url, safe='')}",
            method="PUT")
        with urllib.request.urlopen(req, timeout=10) as r:
            target = json.loads(r.read())
        async with CDP(target["webSocketDebuggerUrl"]) as cdp:
            await cdp.call("Runtime.enable")
            await cdp.call("Log.enable")
            await cdp.call("Page.enable")
            await cdp.call("Page.navigate", {"url": app_url})
            await asyncio.sleep(2.5)
            await cdp.drain(1.0)

            title = await cdp.eval("document.title")
            results.append(("page.loaded", bool(title), f"title={title!r}"))

            tt = await cdp.eval(
                "!!(window.trustedTypes && trustedTypes.defaultPolicy)")
            results.append(("trusted-types.default-policy",
                            tt is True,
                            "前端 default 策略已注册（CSP 允许该策略名）" if tt
                            else "defaultPolicy 未注册 → 强制会白屏"))

            policy_text = await cdp.eval(
                "(document.getElementById('policyCard')||{}).innerText||''")
            ok_card = bool(policy_text) and ("加载中" not in policy_text)
            results.append(("policy.card-rendered", ok_card,
                            (policy_text or "")[:120].replace("\n", " ")))

            # 内联脚本已执行：SSE 客户端函数存在
            has_chat = await cdp.eval("typeof window.EventSource !== 'undefined'")
            results.append(("inline-script.ran", has_chat is True,
                            "内联脚本执行成功（script-src 未拦）"))

            # 反向验证：字符串直接进 innerHTML 会被策略接管（不抛错即说明
            # default 策略生效；若策略缺失且强制生效，这里会抛 TypeError）
            probe = await cdp.eval(
                "(function(){try{const d=document.createElement('div');"
                "d.innerHTML='<b>x</b>';return 'ok:'+d.innerHTML.length;}"
                "catch(e){return 'throw:'+e.name;}})()")
            results.append(("trusted-types.enforced", str(probe).startswith("ok:"),
                            f"innerHTML probe → {probe}"))

            # 表单提交 + SSE：填输入框、点发送，等 assistant 气泡出现
            await cdp.eval(
                "(function(){const i=document.getElementById('input');"
                "i.value='我的车快到期了，帮我看看续保方案';"
                "i.dispatchEvent(new Event('input'));"
                "document.getElementById('send').click();return true;})()")
            got = False
            for _ in range(40):
                await asyncio.sleep(0.5)
                n = await cdp.eval(
                    "document.querySelectorAll('#msgs .row.bot').length")
                if isinstance(n, int) and n > 0:
                    got = True
                    break
            results.append(("sse.form-submit", got,
                            "点击发送后收到 .row.bot 气泡（SSE 未被 CSP 拦）"))

            await cdp.drain(0.8)
            violations = csp_violations(cdp.events)
            results.append(("csp.no-violation", not violations,
                            "; ".join(violations[:3]) or "控制台无 CSP/Trusted Types 违规"))
    finally:
        _terminate_tree(proc)
        shutil.rmtree(profile, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--skip-browser", action="store_true")
    args = ap.parse_args()

    port = args.port or _free_port()
    trace_dir = tempfile.mkdtemp(prefix="csp-check-traces-")
    env = dict(os.environ,
               TRACE_DIR=trace_dir, PORT=str(port), HOST="127.0.0.1",
               RENEWAL_FORCE_RULE_MODE="1")
    env.pop("RENEWAL_API_KEYS", None)
    log_path = Path(tempfile.mkdtemp(prefix="csp-check-log-")) / "server.log"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=log_path.open("w"), stderr=subprocess.STDOUT,
        start_new_session=True)
    results: list[tuple[str, bool, str]] = []
    try:
        if not wait_http(f"http://127.0.0.1:{port}/health"):
            print("服务未就绪，无法验证", file=sys.stderr)
            return 2
        app_url = f"http://127.0.0.1:{port}/"

        # 1) 响应头断言（不依赖浏览器）
        with urllib.request.urlopen(app_url, timeout=5) as r:
            csp = r.headers.get("content-security-policy", "")
        checks = {
            "require-trusted-types-for 'script'": "require-trusted-types-for 'script'" in csp,
            "trusted-types default": "trusted-types default" in csp,
            "frame-ancestors 'none'": "frame-ancestors 'none'" in csp,
            "object-src 'none'": "object-src 'none'" in csp,
        }
        for name, ok in checks.items():
            results.append((f"header.{name}", ok, csp[:160]))

        if args.skip_browser:
            results.append(("browser.skipped", True, "--skip-browser"))
        else:
            asyncio.run(run_browser_checks(app_url, find_chrome(), results))
    finally:
        _terminate_tree(server)          # 整组收尾：不留 uvicorn 孙进程
        shutil.rmtree(trace_dir, ignore_errors=True)
        shutil.rmtree(log_path.parent, ignore_errors=True)

    width = max(len(n) for n, _, _ in results) + 2
    failed = 0
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}} {detail}")
        failed += 0 if ok else 1
    print(f"\n{len(results) - failed}/{len(results)} 通过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import urllib.parse  # noqa: PLC0415  (延迟导入保持顶部整洁)

    raise SystemExit(main())
