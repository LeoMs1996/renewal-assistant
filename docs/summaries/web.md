# web/index.html — 前端对话工作台 小结

## 一、做了什么

实现 `web/index.html`（约 30KB，单文件、零构建、原生 JS，无任何外部依赖/CDN）：

- **页头**：醒目橙色徽标「模拟报价 · 合成数据」；身份下拉（OWN-1001 张伟 / OWN-1002 李静，含车牌+车型提示）；会话 ID chip；「刷新保单」按钮。身份由前端 `owner_id` 传入 `/chat`，**不做对话自报身份**；切换身份自动开新会话（避免跨车主串上下文）并清空 latestQuote。
- **左栏对话流**（POST /chat，SSE）：
  - `token` 增量渲染（createTextNode 逐字追加，自动滚底）；
  - `message` 完整消息 + `citations`（显示条款 source + version）；
  - `quote` 报价卡（quote_id / quote_version / valid_until / line_items 表格 / premium_total，标注"保费由报价服务计算"）；
  - `clarify` 澄清问题卡；`await_confirm` 待确认卡（confirmables 列表 + 「确认投保」按钮 → POST /confirm，携带 SPEC §4.4 四字段）；`confirmed` 订单卡（order_id）；`error` 错误卡（code/message/node）；`done` 按 finish_reason 提示结束原因；
  - `node_start` / `tool_call` / `tool_result` 以脉动状态行轻量展示状态机/工具进度。
  - 网络失败（后端未就绪）→ 友好错误卡提示启动服务（127.0.0.1:8000）；所有不可信内容经 `esc()` 转义（innerHTML 方案的 XSS 防护）。
- **右栏双栏**：
  - 原保单卡（GET /policy/{owner_id}）：车主/车辆/保单 KV、险种表（保额/保费/免赔）、`days_to_expiry` 倒计时天数、`expiring_soon=true` 时橙色高亮卡片+「临近到期」徽标；注明脱敏说明。
  - 轨迹抽屉（GET /trace/{trace_id}）：可折叠，支持手动输入 trace_id 加载；每轮对话 done 后自动回填最新 trace_id 并加载；按 §5 record_type 渲染时间线（工具/LLM/错误节点不同颜色，显示 ts/node/latency_ms/检索命中 wiki_id）。

## 二、关键决策与依据（含 Context7 文档要点）

1. **SSE 消费手写 fetch + ReadableStream**（需求指定）。Context7（MDN /mdn/content）查证要点：
   - `response.body.getReader()` 会锁定流，`TextDecoder` 必须以 `{stream:true}` 逐 chunk 解码以正确处理多字节 UTF-8 字符跨 chunk 断裂；
   - MDN 官方 line-iterator 模式即「累积 buffer + 正则/IndexOf 切行 + 保留 remainder」——我据此实现 `parseSSEChunkDispatcher`：buffer 累积、按 `\n` 切行、`\r$` 归一、空行 dispatch、`:` 注释行忽略、`event:`/`data:` 前缀解析、多行 data 以 `\n` join。**不使用 EventSource**，因为 /chat 是 POST（EventSource 只支持 GET）。
2. **确认按钮的 quote_version 来源**：从最近的 `quote`（或 await_confirm 携带的 quote_id）事件缓存 `latestQuote`，await_confirm 卡若无缓存则禁用按钮，避免提交脏数据。
3. **confirm 错误码本地化提示**：409/404/422 的 QUOTE_EXPIRED / QUOTE_VERSION_STALE / QUOTE_NOT_FOUND / OWNER_MISMATCH 均给出中文处置建议（对应 AC-12 等场景）。
4. **零依赖**：无 CDN、无框架，双击/静态服务均可打开；后端未就绪时页面功能不崩（每处 fetch 均有 catch + 占位提示）。

## 三、验证证据

1. JS 语法：提取 `<script>` 内容 → `node --check` 通过，退出码 0：
   ```
   JS SYNTAX OK
   exit=0
   ```
2. HTML 标签配对：Python `html.parser` 栈式核对（void 元素白名单豁免）：
   ```
   tag pairing errors: NONE
   unclosed tags: NONE
   ```
3. SSE 解析器单测（node，极端逐字符喂入模拟跨 chunk 断裂 + 多行 data + 注释行 + CRLF）：
   ```
   3 个事件均正确解析（token/message 多行 data join/done）
   SSE PARSER TEST PASS
   exit=0
   ```
4. 浏览器实机渲染：未做（后端 server/ 尚未由后端 Agent 交付，无端到端页面可跑）。已核对所有 DOM id 引用（$() 调用的 id 均在 HTML 中定义）。

## 四、遗留问题与交接

- **未做浏览器无头实测**：等 server/ Agent 交付后在浏览器/无头环境走一遍 SSE 全事件链（quote → await_confirm → confirm → confirmed），重点看 token 流式滚动与轨迹抽屉自动加载。
- **假设后端行为**：`/confirm` 非 200 时错误体为 `{"error":{code,message}}` 或 FastAPI 默认 `detail`，前端两种都兜了；若后端最终错误格式不同，只需改 `doConfirm` 的解析。
- **比较表（AC-05 原方案 vs 新方案对照）**：SPEC §4.1 SSE 事件无独立 compare 事件，预期后端在 `message`/`await_confirm.summary` 里给出；若后端后续新增结构化 compare 事件，前端需补一张对照卡模板。
- **clarify 问题未做成可点选项**：当前渲染为列表+提示文字（SPEC clarify 事件只给 `questions: [string]`，无选项语义）；如需点击补全可在后端给出结构化选项后增强。
