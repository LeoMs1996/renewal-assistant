# 编排Agent小结 — server/graph.py 状态机 + server/app.py SSE 接入

日期：2026-11-12 ｜ 契约：SPEC.md v1.0.0 ｜ 模式：规则模式实测（.env 缺失，LLM 分支代码就绪）

## 一、做了什么

- **server/graph.py**：把 11 节点 stub 变成真实现（intake / get_policy / parse_needs /
  clarify / retrieve_terms / quote / compare / await_confirm / confirm / fallback / END），
  拓扑按 SPEC §6.2，另加 3 条必要旁路（见下"关键决策"第 6 条）。
- **server/app.py**：`POST /chat` 由 stub 演示流改为驱动 LangGraph——
  `graph.stream(initial, stream_mode=["custom","values"])`，节点内
  `get_stream_writer()` 发的自定义事件在此翻译为 SPEC §4.1 的 SSE 事件并写轨迹
  JSONL（§5）。`/health` 的 `graph` 字段改为 `"langgraph"`。其余端点未动。
- **server/sessions.py（新增）**：跨轮会话存储（traces/sessions/{sid}.json 落盘），
  保存常驻需求（needs/needs_version/invalidated）、latest_quote（含
  coverage_selection_key）、baseline_quote、对话历史（尾部 20 条）、
  no_progress_rounds、status（awaiting_confirm 等）。
- **server/llm.py**：新增 `chat_tool_json()`——Anthropic 兼容接口 tool-use 强约束
  JSON（tool_choice={"type":"tool"}），失败/规则模式返回 (None, None) 由调用方降级。
- **scripts/demo_chat.py（新增）**：httpx 直连 /chat 的三链路自测 + 轨迹完整性校验。

## 二、关键决策与依据（含 Context7 文档要点）

1. **SSE 桥接用 LangGraph 官方自定义流通道**。Context7 查证（/websites/langchain_oss_python_langgraph，
   LangGraph 1.x）：节点内 `from langgraph.config import get_stream_writer` 发事件，
   `graph.stream(stream_mode=["custom","values"])` 消费；无 reducer 的 State 键为
   整体替换语义、节点返回 partial update 即可。这避免自造轮子，也使 invoke()
   （无流上下文）时写入器静默降级。本项目 langgraph==1.2.20。
2. **跨轮上下文用自研 sessions 而非 checkpointer**：SPEC 状态机每轮从 START→intake
   重入（挂起=END + await_user），且需要自定义合并语义（需求累积/失效标记/历史截断），
   JSON 落盘的会话快照比 checkpointer 更直白且重启不丢。
3. **parse_needs 双轨**：GLM 结构化输出（tool-use）优先，关键词规则解析兜底且
   **硬信号（网约车/停售险名/删交强）永远以规则为准**——这些触发硬失败/转人工分支，
   不能依赖模型。规则与 LLM 结果按字段合并（LLM 为主、规则补缺）。
4. **需求累积语义（备忘 b/c 的前提）**：每轮解析结果视为增量叠加到常驻需求
   （sum_insured_changes 按险种代码后者覆盖前者；add/remove 互斥抵消）。
   这样"只改预算"轮不会冲掉此前的保额调整 → 险种选择 key 不变 → 复用报价。
   改口（200万→300万）时旧值移入 `invalidated` 并在 parse_needs 的 node_end.output
   留痕（记忆撤回）；纯确认轮不改需求、不误标失效。
5. **报价复用判定（备忘 c）**：`coverage_selection_key`（归一化险种+保额+用途）
   与上次报价相同且 `valid_until` 未过 → 不调 query_quote（轨迹无 tool_call 可证）；
   否则询价并同步取"原方案续保报价"作对照组（skill 第 3 步）。
   预算-only 轮实测 query_quote 调用次数=0、quote_id 不变。
6. **拓扑旁路（3 条，SPEC §6.2 未显式列出但为 §7 验收所必需）**：
   - `parse_needs → fallback`：查无保单（AC-04 兜底不编造）/ 步数上限 / 无进展退出；
   - `retrieve_terms → confirm`：跨轮确认。SPEC 边 "await_confirm → confirm（用户已确认）"
     在"挂起即 END、下轮重入 START"的模型下只能这样实现；
   - `quote → fallback`：报价工具业务错误（RATE_NOT_FOUND 等）→ 纠正提示。
   如需严格化应修 SPEC 升版本（当前仅记录于此）。
7. **compare 先保障后价格**（skill 七步）：确定性生成差异表/价格对比/系数/上浮说明
   （上浮引 wiki-rate-surcharge + rates_version），citations 全部带
   {wiki_id, source, version}；LLM 模式只追加一段"顾问建议"且 prompt 明令
   只能用给定数字——规则/LLM 两模式都不可能编造保费（硬规矩 #3）。
8. **步数上限与无进展**（备忘 g）：State.steps 每节点 +1，≥8（STEP_LIMIT）路由
   fallback；no_progress_rounds 连续 2 轮（需求指纹无变化且意图为续保类）触发退出。
   触发原因写入 fallback 的 node_end.output（exit_reason=step_limit/no_progress）。

## 三、验证证据

- `python3 scripts/demo_chat.py` → **exit 0**，断言全部通过：
  - 链路① OWN-1001 比价：节点链 `intake→get_policy→parse_needs→retrieve_terms→
    quote→compare→await_confirm`，query_quote×2（新方案+对照），DSX=200万，
    done=await_user；
  - 链路②-a 改 300万：重新询价（query_quote×1，DSX=300万），parse_needs 轨迹含
    `"invalidated":[{"field":"sum_insured_changes","old":[…200万],"new":[…300万],
    "reason":"车主改口，旧偏好失效"}]`；
  - 链路②-b 仅改预算 20000：**query_quote 调用次数=0**、quote_id 复用、预算提示出现；
  - 链路③ 条款问答（新会话）：不进比价，citation=
    `{wiki_id: wiki-annual-inspection, source:《合成机动车理赔适用条件细则（虚构）》, version: v2024.3}`，
    done=end；
  - 轨迹：4 个 trace JSONL seq 从 1 连续、§5 基础字段齐全、record_type 枚举合法、
    retrieval.output 含 [wiki_id/source/version/score]。
- 附加实测（同法 POST /chat）：
  - 确认轮（"确认，按新方案投保"）→ `confirmed` 事件 `ORD-20261112-1266`，
    done=end，确认轮 invalidated=[]（不误标失效）；
  - 网约车轮 → **不调 query_quote、无 await_confirm**，回复含"转人工"，
    citations 含 wiki-ride-hailing（备忘 d）。
- `/health` → `{"status":"ok","llm_mode":"rule","graph":"langgraph","nodes":11}`。

## 四、遗留问题与交接

1. **LLM 分支未实测**：当前无 .env（GLM 凭证），parse_needs/compare/fallback 的
   LLM 路径仅代码就绪 + 降级路径实测。配好 ANTHROPIC_BASE_URL/AUTH_TOKEN/MODEL_NAME
   后建议重跑 demo_chat.py 并观察 llm_call/llm_response 轨迹与 tokens 计量。
2. **SSE `token` 事件暂不发送**：节点内用非流式 chat（一次性 message 事件）。
   若前端要打字机效果，需在 compare/fallback 内改用 stream_chat 并逐 delta 发 token。
3. **SPEC 旁路边未入契约**：第二部分第 6 条的 3 条边建议下版 SPEC 收录
   （retrieve_terms→confirm 尤其影响后续 eval Agent 写断言）。
4. **AC-10 语义按编排任务书实现**（网约车→不报价转人工）；SPEC §7 AC-10 原文
   期望"营运系数 1.6 生效、保费对比体现"。二者矛盾时以当前任务书为准，eval Agent
   需注意 AC-10 改按"转人工+引 wiki-ride-hailing"断言（报价服务侧 1.6 系数计算
   仍有 mcp_servers/test_quote_server.py 覆盖）。
5. **clarify 覆盖面窄**：仅"保额调整未给档位"一种澄清场景；预算冲突、语义模糊等
   未触发 clarify（预算超支走 compare 内提示）。eval 可按需扩展。
6. traces/sessions/ 与 traces/quotes.json 已被 .gitignore 覆盖（quotes.json 原有），
   sessions 目录同在 traces/ 下，无需改 git。
