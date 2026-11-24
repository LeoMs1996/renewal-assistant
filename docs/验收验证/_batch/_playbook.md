# 浏览器验收批次 Playbook（每个批次代理开工前只读这一份）

## 环境（已就绪，勿动）
- 服务 `http://127.0.0.1:8000`，`llm_mode=llm`，11 节点，8 wiki。**禁止启动/停止/重启服务。** 限流 60 次/分钟，串行操作即可。
- 项目根 `renewal-assistant/`。结果文件 `docs/验收验证/_batch/<批次>.md`（追加）；截图目录 `docs/验收验证/screenshots/`，已有 01–11 号，你从 **12** 起编号，**纯 ASCII 文件名**。
- chrome-devtools 截图**只能写临时目录**：`filePath=/var/folders/8p/w0g1llx97lzf93_tzn0v343r0000gn/T/batch1a-shots/<名>.png`，然后用 bash `cp` 到 screenshots/。
- 页面：`list_pages` 找 `车险续保助手 · 对话工作台`（通常 pageId=2），`resize_page` 1440×900。

## 上下文硬约束（前任因违反而耗尽）
1. **禁止 `take_snapshot`**（a11y 树巨大）。所有页面操作与读取用 `evaluate_script`，返回 **≤400 字符** 的 JSON。
2. **禁止回看截图**（read_image 等）。截图只落盘。
3. **禁止 cat 轨迹/SSE 全文**；用 python 只打印需要的字段。
4. `read` 文件带 offset/limit，单次 ≤60 行。bash 输出 `| head -30`。
5. **每完成一个场景立刻 `cat >>` 追加到批次文件**。每场景 ≤15 次调用。

## 页面 id 图
`select#ownerSel`（OWN-1001 张伟 / OWN-1002 李静，change 自动新建会话）· `#sessionChip` · `#policyCard` · `div#msgs`（消息流）· `textarea#input` · `button#send` · 「确认投保」按钮 · `details#traceDrawer` + `#traceInput` + `#traceLoadBtn` + `ul#traceList`。
没有「新会话」按钮：**刷新页面 = 新会话**（默认 OWN-1001）。切换身份也会新建会话。

## 发送一轮并等待（模板，直接复用）
```js
async () => {
  const m = document.querySelector('#msgs');
  const cnt = () => (m.innerText.match(/流结束/g) || []).length;
  const before = cnt();
  const inp = document.querySelector('#input');
  inp.value = '<话术>'; inp.dispatchEvent(new Event('input', {bubbles: true}));
  document.querySelector('#send').click();
  const t0 = Date.now();
  while (Date.now() - t0 < 150000) { await new Promise(r => setTimeout(r, 1000)); if (cnt() > before) break; }
  const txt = m.innerText;
  return JSON.stringify({chip: document.querySelector('#sessionChip').innerText, dur: Math.round((Date.now()-t0)/1000), qt: (txt.match(/QT-[0-9A-Za-z-]+/g)||[]).slice(-2), cards: (txt.match(/待确认投保方案/g)||[]).length, tail: txt.slice(-380)});
}
```
切换身份：`const s=document.querySelector('#ownerSel'); s.value=s.options[1].value; s.dispatchEvent(new Event('change',{bubbles:true}));`

## 用例定义
`eval/cases/AC-xx.json`（steps 含话术，assertions 含预期）。紧凑打印：
`python3 -c "import json;d=json.load(open('eval/cases/AC-06.json'));[print(k, json.dumps(v,ensure_ascii=False)[:400]) for k,v in d.items()]"`

## 轨迹取证
- 文件 `traces/trc-*.jsonl`；找本会话的：`grep -l "<session_id>" $(ls -t traces/trc-*.jsonl | head -8)`。
- schema：`ts, trace_id, session_id, seq, record_type, node, event, input, output`（node_start 的 record_type 是 `{"node":name}` 对象）。
- 抽取（只打印需要的）：`python3 -c "import json;[print(r['seq'],r['record_type'] if isinstance(r['record_type'],str) else r['record_type'].get('node'),str(r.get('output'))[:160]) for r in map(json.loads,open('traces/TRC.jsonl'))]" | head -30`
- `GET /trace/{id}` 返回 JSON **数组**（非 JSONL），条数 = 文件记录数。
- 抽屉回放：`d=document.querySelector('#traceDrawer');d.open=true;document.querySelector('#traceInput').value=ID;document.querySelector('#traceLoadBtn').click();` 轮询 `#traceList.children.length`。

## 条目格式（镜像已有条目；「实际」≤6 行）
```
### [NN] AC-xx <标题>
- 操作：
- 截图：screenshots/12-ACxx-xxx.png
- 预期：<SPEC 条款 + 用例 asserts 摘要>
- 实际：
- 结论：PASS | FAIL | PARTIAL（逐条对 asserts）
- 轨迹证据：trace_id=…；节点链/关键字段 ≤3 行
- 备注：诚实记录弱点；需重启才能验的写「归 1C」
- 会话 ID：
```

## 诚实纪律
FAIL 就写 FAIL 并给证据；不粉饰；不改业务代码；不 `git add`/`commit`；不碰 `docs/` 下除 `验收验证/` 以外的路径。
