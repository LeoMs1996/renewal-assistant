# 前端 / SSE 链路域：评估 → 优化 → 验证总结

> 检索时间：2026-11-13（Asia/Shanghai）｜子 Agent：SSE 前端韧性｜状态：已落地并通过实测

## 1. 基准与取证方式

| 主题 | 结论 | 来源 |
|---|---|---|
| SSE 事件字段语义 | `id:` 标识事件序号（断线重连时浏览器回传 `Last-Event-ID`）、`retry:` 指定重连间隔、以空行分隔事件 | **待验证**：本轮检索未取到 MDN/W3C 原文，仅取到社区整理（[SSE 协议参考](https://raw.githubusercontent.com/curiositech/windags-skills/refs/heads/main/skills/llm-streaming-response-handler/references/sse-protocol.md)）。实现按该语义落地，但不作为「合规」结论 |
| 连接关闭语义 | 客户端以**流自然关闭**判定完成；服务端必须显式结束响应，否则客户端只能等超时 | 本轮以**本机实测**为准（见 §4），非文档引用 |

> 本域的判断主要来自**实测**而非文档：对 SSE 这类协议细节，跑一遍比读一段规范更可靠。

## 2. 优化前的差距

| 问题 | 影响 |
|---|---|
| 无心跳，空闲链路易被代理/浏览器掐断 | 长耗时规划（多轮询价）中途断流 |
| 断线丢失用户输入与已收结果 | 用户需重打一遍问题 |
| 无事件 `id:` | 无法做断线续传/幂等重发 |
| 服务端未声明续传能力 | 前端无从判断该重发还是等待 |

## 3. 已实施改动（`web/index.html` + `server/app.py`）

1. **服务端心跳**：生产者线程迭代 LangGraph 流、主循环带 15s 超时取件；超时下发 `: ping` 注释行（SSE 注释，解析层忽略）。
2. **事件序号**：每帧带 `id: N`；响应头 `X-Resume-Supported: false` 明示「不按序号续传」。
3. **前端断线韧性**：解析 `id:`/`retry:`；断线时保留**已收部分结果 + 用户输入**，展示断线条并提供一键重发（重发携带 `Last-Event-ID`，服务端安全忽略并记入轨迹）。
4. **`RENEWAL_FORCE_RULE_MODE=1`**：为前端/eval 提供确定性后端（无需 LLM 凭证），便于复现问题。

## 4. 关键缺陷：SSE 永不结束（本次最严重的一条）

**现象**：`/chat` 在发出 `done` 前就"停住"，`curl` 等到超时；`eval` 整轮挂死；心跳也不再输出。

**定位过程（值得留档）**：
1. `tail` 吞输出 → 改为落盘 + `python -u`，才看到卡在 `compare` 之后；
2. 进程内直接 `compiled.stream()` → **0.01s 跑完**，排除图本身；
3. 改为在工作线程里跑 → **同样跑完**，排除 checkpointer/线程问题；
4. 用 `faulthandler` 抓栈 → 事件循环在 `selectors` 空转、执行器线程空闲 → **不是死锁，是等一个永远不会来的东西**；
5. 读代码发现哨兵类型错配：

```python
# 生产者
await q.put((None, None))     # 投递元组
# 消费者
if chunk is None:             # 判的是 None 本体 → 永不成立
    break
else:
    mode, payload = chunk     # (None, None) 被解包，循环继续 await 下一条
```

**修复**：哨兵改为 `None` 本体并加注释说明为何不能用元组。该约定已写入 `SPEC §4.5 SSE 结束约定`。

## 5. 验证证据

```
# 修复前
curl /chat --max-time 30   → total=30.0s（超时），done 事件缺失，仅 1 次 ping
# 修复后
curl /chat                → 正常结束，事件序列 ... await_confirm → node_end → done
eval 19 条用例             → 19/19 PASS（此前整轮挂死无法完成）
```

## 6. 遗留项

| 项 | 说明 | 建议 |
|---|---|---|
| 续传未实现 | 仅声明 `X-Resume-Supported: false`，断线靠前端**全量重发** | 若要真续传：服务端按 `Last-Event-ID` 重放缓冲区事件，需引入事件缓冲与幂等键 |
| 心跳周期固定 15s | 未按链路类型自适应 | 长任务（多险种逐项询价）可降到 10s，并加 `retry:` 建议值 |
| 前端仍是单文件内联 | 影响 CSP 收紧 | 拆 `app.js` 后接 nonce/hash |
| SSE 关闭逻辑缺自动化断言 | 目前靠人工 curl + eval 间接覆盖 | 加 `tests/test_sse.py`：断言流在 N 秒内关闭且最后一帧为 `done` |
