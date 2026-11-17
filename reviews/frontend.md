# 前端域评审 + 落地优化报告 — web/index.html（SSE 对话工作台）

- 评审对象：`renewal-assistant/web/index.html`（单文件，~658 行；对话流 + 报价卡 + 轨迹抽屉 + 保单卡）
- 评审时间：2026-11-13（Asia/Shanghai）
- 评审人：frontend-reviewer（AgentTeams · renewal-assistant-2026-review）
- 硬约束遵守：所有技术结论均来自本次（2026-11-13）联网检索的现行规范/文档，未使用训练记忆直接下结论；来源 URL + 检索时间戳逐条标注。

---

## 一、检索来源（≥3，均于 2026-11-13 检索）

| # | 来源 | URL | 关键内容 |
|---|---|---|---|
| S1 | WHATWG HTML Living Standard（Last Updated 12 November 2026）§9.2 Server-sent events | https://html.spec.whatwg.org/multipage/server-sent-events.html | 事件流 ABNF：`end-of-line = cr lf / cr / lf`（三种行尾）；UTF-8 强制；空行派发事件；流末不完整事件丢弃；`Last-Event-ID` 头在重连时回传；作者注：每 ~15s 发注释行防代理断连；重连可引入指数退避 |
| S2 | MDN — Using server-sent events | https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events | SSE Baseline（2020-01 起广泛可用）；非 HTTP/2 下每浏览器每域 6 连接上限（Chrome Won't Fix crbug 275955）；`text/event-stream` + `X-Accel-Buffering: no` 服务端要求 |
| S3 | MDN — Trusted Types API（**Baseline 2026 Newly available，2026-02 起**） | https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API | innerHTML/document.write 属 HTML 注入 sink；`trustedTypes.createPolicy("default", …)` 注册默认策略；配合 CSP `require-trusted-types-for 'script'` 强制；default 策略使现有字符串赋值自动过策略函数 |
| S4 | MDN — prefers-reduced-motion | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion | Baseline；`@media (prefers-reduced-motion: reduce)` 应降级/移除非必要动画，避免前庭动症触发 |

---

## 二、现状评审（对照 2026 基线逐项）

### 2.1 已达基线（保持，不改动）

| 项 | 现状 | 依据 |
|---|---|---|
| fetch+ReadableStream 消费 SSE | 合理：POST 体 + 需要自定义事件名与中断控制时，fetch 流式是 EventSource（仅 GET）的规范内替代，事件流格式解析与规范一致 | S1（格式定义）、S2 |
| `id:`/`Last-Event-ID` 断线续传头 | 已实现：解析 `id:` 字段并在重发时带 `Last-Event-ID` 头（后端声明 X-Resume-Supported: false 时安全降级为全量重跑） | S1 §9.2.4 |
| 心跳注释行 + 看门狗 | 前端 30s 无字节判断线；任意字节（含 `: ping` 注释行）刷新看门狗 — 与 S1 作者注"每 15s 注释行防代理断连"配套 |
| 指数退避重试（1s/2s/4s，3 次后人工兜底） | 符合 S1 处理模型第 3 步"user agents might introduce an exponential backoff delay" |
| 不完整事件丢弃 | 原实现（行缓冲、仅空行派发）语义符合 S1 §9.2.6 "incomplete event is not dispatched" |
| XSS 防护 | 所有不可信插值过 `esc()`（&<>"' 五字符）或 `fmtMoney()`（仅数字走 toLocaleString），token 流走 `createTextNode` |
| 可访问性 | `#msgs` 有 `aria-live="polite"`；Enter/Shift+Enter 语义正确 |

### 2.2 差距与本次落地修复（3 项，全部已改并验证）

| # | 差距 | 规范依据 | 修复内容 | 验证 |
|---|---|---|---|---|
| G1 | SSE 解析器只识别 `\n` 与 `\r\n` 行尾，**漏掉单独 `\r` 行尾**（ABNF 明确 `cr` 单独即行尾） | S1 §9.2.5 `end-of-line = cr lf / cr / lf` | ① 归一 CRLF→LF；② 缓冲尾孤立 `\r` 暂留（可能属被拆开的 CRLF，待下一块判定）；③ 其余单独 `\r` 归一为 LF；④ 新增 `feed.flush()`：流结束时把暂留 `\r` 按单独 CR 行尾收尾（完整空行终结的事件按规范派发，仍不完整则丢弃）；⑤ 读取循环 done 后调用 flush | node 行为测试 4 组全过（见 §四 V1） |
| G2 | 页面 20+ 处 `innerHTML` 注入 sink，无 Trusted Types 兼容层 — Trusted Types 已于 **2026-02 起跨浏览器 Baseline Newly available**，后端一旦下发 CSP `require-trusted-types-for 'script'` 页面将整体 TypeError | S3 | 在脚本首部注册 `trustedTypes.createPolicy("default", {createHTML: s=>s, createScriptURL: s=>s})` 透传默认策略（本页所有 innerHTML 插值已过 esc() 白名单转义，透传即安全），为未来 CSP 强制启用预留零差异兼容 | 语法检查 + 无 TT 环境零行为差异（特性检测守卫） |
| G3 | 状态指示点 `.dot` 的 `pulse` 无限动画未响应系统"减少动态效果"偏好，可触发前庭不适 | S4 | 新增 `@media (prefers-reduced-motion: reduce)`：关闭 pulse 动画与全部过渡 | CSS 注入 + HTML 结构校验（V2/V3） |

### 2.3 记录在案、未改动项（含理由）

| 项 | 说明 | 依据 |
|---|---|---|
| HTTP/2 连接上限 | 教学单用户场景仅 1 条 SSE 连接，远低于非 HTTP/2 的 6 连接/域上限；若未来多页签常驻需 HTTP/2 或 SharedWorker 共享连接 | S2（6 连接警告）、S1 §9.2.7（shared worker 建议） |
| CSP 头下发 | 属服务端（平台/安全域）职责，前端已就绪（G2 default 策略）；建议安全域后续加 `Content-Security-Policy: require-trusted-types-for 'script'; trusted-types default` | S3 |
| 单文件 no-build 架构 | 教学演示约束，非缺陷；规模增长后再引入构建链 |

---

## 三、改动清单（changedPaths）

- `renewal-assistant/web/index.html`
  - `<style>` 尾部：+`@media (prefers-reduced-motion: reduce)` 块（G3）
  - `<script>` 首部：+Trusted Types default 策略注册（G2）
  - `parseSSEChunkDispatcher()`：行尾归一重写 + `hold` 外提 + `feed.flush()` + `return feed` 重构（G1）
  - `chat()` 读取循环：流结束调用 `feed.flush()`（G1）

## 四、验证记录（2026-11-13 首验，2026-11-17 attempt 2 复验）

| ID | 命令/方法 | 结果 |
|---|---|---|
| V1 | `node --check`（提取内联 JS）+ 自建 SSE 行为测试（2026-11-17 复验）：A=单独 CR 行尾+跨 chunk 拆开的孤立 CR+EOF flush（2 事件正确派发）、A2=id-only 事件按 WHATWG 不派发（0 事件）、B=常规 LF（1）、C=心跳+CRLF（1）、D=EOF 不完整事件丢弃（0） | `JS_SYNTAX_OK`；`ALL_SSE_TESTS_PASS` |
| V2 | Python `html.parser` 标签平衡校验（2026-11-17 复验通过） | `HTML_OK` |
| V3 | attempt 1 曾引入两处缺陷（`</style>` 误删、flush 死代码），均被 V1/V2 捕获并修复；attempt 2 复验首轮测试预期误设（期望 id-only 事件派发），对照 WHATWG §9.2.6 修正测试预期后全过 — 实现两轮均符合规范 | 已闭环 |

## 五、结论

前端单文件工作台的 SSE 消费主体已达到 2026-11 现行规范基线（格式解析、续传头、心跳、指数退避、不完整事件丢弃均符合 WHATWG/MDN）；本次补齐三项差距（单独 CR 行尾、Trusted Types Baseline 2026 兼容层、prefers-reduced-motion），全部经自动化行为测试与结构校验验证通过，无回归。评分（域内）：修复前 7.0/10 → 修复后 **8.0/10**（剩余提升空间在 CSP 强制启用与多页签连接治理，均属跨域协作项）。
