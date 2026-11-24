# evidence-2

## §3 上下文装配 / 记忆 / 轨迹

规定命令实测（`grep -n -E '^def |^async def |^class |BUDGET|budget|compress|invalidat|archive|profile' server/context_assembly.py server/memory.py server/trace.py | head -40`）：

- **`server/context_assembly.py` 未找到**（grep 报 `No such file or directory`）。上下文装配逻辑实际落在 `server/memory.py:663-821` 段。
- 规定命令输出恰 40 行、止于 `memory.py:503`（被 `head -40` 截断）：`memory.py` 503 行之后与 `trace.py` 的匹配不在其输出内。下表这两段取自补充 grep（同一正则去掉 `profile`，或按行号段过滤）。
- 关键词 `compress` 未找到（补充 grep `server/` + `claims/` 的 `*.py`，排除 memory.py/trace.py，34 行未截断、零命中）；压缩由 `summarize_turns` 承担。`archive` 仅命中 `memory.py:14` 注释，两文件内无同名函数。`profile` 仅命中 docstring/注释（`memory.py:7`、`433`），指 LangChain「profile」记忆形态。
- 「未读」= 只见函数签名/docstring，未读函数体。

| 模块 | 关键函数（文件:行） | 职责一句话 | 对应作业要求 |
|---|---|---|---|
| `server/memory.py`（上下文装配段 663–821） | `build_context_package` memory.py:768 | memory manager：为当前轮组装 context package（recent / summary / long_term / brief + 各项 token 明细），据 read 768–815 | 上下文预算 / 压缩 / 记忆 |
| `server/memory.py` | `prompt_context` memory.py:798 | 编排层唯一入口，返回（附加 system 文本, 历史消息）；记忆关闭时退回固定尾部 `legacy_tail` 条；调用点 graph.py:738、1134、1275 | 上下文预算 |
| `server/memory.py` | `context_report` memory.py:812 | 写入 node_end.output 的轻量预算摘要，不新增轨迹 record_type；调用点 graph.py:823 | 上下文预算（可观测） |
| `server/memory.py` | `estimate_tokens` memory.py:687 | 保守 token 估算：CJK 每字 1 token、其余每 4 字符 1 token，不用真实分词器（离线可复现） | 上下文预算 |
| `server/memory.py` | `trim_turns` memory.py:699 | 按 token 预算从新到旧保留消息，返回（保留, 被裁, 已用 tokens）；docstring 称旧实现按固定条数裁剪且无压缩 | 上下文预算 |
| `server/memory.py` | `summarize_turns` memory.py:729 | 确定性滚动摘要：从被裁轮次抽取含业务关键词/数字的句子（非 LLM 摘要），显式标注「已压缩」 | 压缩 |
| `server/memory.py` | `render_brief` memory.py:663 | 长期记忆简报渲染（未读；签名 `limit: int = 8`，由 build_context_package 调用） | 记忆 |
| `server/config.py` | `memory_prompt_budget` config.py:161、`memory_chat_budget` config.py:168 | 两档历史预算：RENEWAL_MEMORY_PROMPT_BUDGET 默认 1000（下限 200）、RENEWAL_MEMORY_CHAT_BUDGET 默认 600（下限 120） | 上下文预算 |
| `server/graph.py`（调用点） | graph.py:739、1135、1276 | 739 传 prompt 档预算（config.py:158 注释：需求解析类 prompt）；1135、1276 传 chat 档预算且 `legacy_tail=6` | 上下文预算 |
| `server/memory.py`（长期记忆读写） | `put` 277、`_upsert` 248、`active_items` 304、`get` 325、`search` 339、`superseded_items` 332 | 按字段/关键词的长期记忆写入与召回（未读；据函数名与模块 docstring：profile 单文档持续更新、未接稠密通道） | 记忆 |
| `server/memory.py` | `_expire` 218、`_prune` 232 | 过期与修剪（未读；据函数名；docstring：用 active/superseded/rejected/archived 标记代替早删） | 记忆 |
| `server/memory.py` | `facts_from_state` 429、`record_turn` 473 | 从 state 抽结构化事实写入长期记忆，对话原文不进长期记忆（memory.py:433）；record_turn 返回 written/superseded/refreshed/invalidated（memory.py:488） | 记忆 / 记忆撤回 |
| `server/memory.py` | `recall_needs` 582 | 需求记忆召回（未读）；调用点 graph.py:766 | 记忆 |
| `server/memory.py`（记忆撤回） | `forget` 381、`_mirror_invalidations` 509 | `forget`=硬删除（遗忘权）：整车主连审计账本一起清、只留时间戳墓碑（read 381–399）；`_mirror_invalidations`=把编排层 state.invalidated 落到长期记忆并附审计理由（memory.py:510） | 记忆撤回 |
| `server/graph.py`（记忆撤回编排） | graph.py:777–786、826、836 | 同事实多版本只留最新，旧值移入 `invalidated`（777 注释；537 注释称在 parse_needs 记录）；按 needs_version 过滤后随 state 下发（826、836） | 记忆撤回 |
| `server/sessions.py`（会话存储） | `load` 75、`save` 86、`append_history` 107、`_safe` 71 | 跨轮会话存储→官方 checkpointer 兼容层：docstring 称 SqliteSaver（traces/checkpoints.sqlite）、thread_id = sessions._safe(session_id)、history 裁剪尾部 20 条（均未读函数体） | 重启继续 |
| `server/graph.py`（checkpointer） | `build_graph` 1371、`get_graph` 1487、`compile(checkpointer=...)` 1403 | 优先 SqliteSaver（94）、缺包降级 InMemorySaver（78 docstring）；checkpointer=None 不持久化（1372） | 重启继续 |
| `server/trace.py`（轨迹写入） | `TraceRecorder` trace.py:40、`now_iso` trace.py:36 | 一个 trace_id 一个实例，写 `traces/<trace_id>.jsonl`，文件权限 0600；字段严格按 SPEC §5、11 类 record_type 枚举；在唯一写入点 `record()` 补缺省 latency_ms（read 1–34、40–75） | 轨迹可程序读取 |
| `server/trace.py`（轨迹读取） | `read_trace` trace.py:160 | 读整条轨迹返回 list[dict]，不存在返回 None；读端逐行 `security.redact_row` 兜底脱敏（read 160–172）；调用点 app.py:311 | 轨迹可程序读取 |
| `server/app.py`（轨迹入口） | app.py:181、app.py:311 | 181 每请求建 `TraceRecorder(trace_id=…, session_id=…)`；311 调 `read_trace(trace_id)` | 轨迹可程序读取 |
| `server/middleware.py`（轨迹读授权） | `trace_owner_allowed` middleware.py:395、`_collect_owner_ids` 382 | 轨迹读取前核对请求者 owner（未读，据函数名） | 轨迹可程序读取 |

**§3 未找到 / 未查**
- `server/context_assembly.py`：未找到（文件不存在）→ 已改记 memory.py 落点。
- 关键词 `compress`：未找到（零命中）。
- `TraceRecorder.record()` 行号：未查（缩进方法，`^def` 正则不命中）。
- `memory.record_turn(` 在 graph.py / app.py 内未命中（grep `memory\.(record_turn|recall_needs|render_brief|prompt_context|context_report|…)\(` 仅返回 prompt_context×3、recall_needs、context_report）；其他文件见文末补注。

## §4 安全与平台面

规定命令实测（`grep -n -E 'untrusted_user_input|authorize_tool_args|rate_limit|RateLimit|CSP|X-Frame|PII|mask|redact|REVIEWER|api_key|429|403' server/security.py server/middleware.py | head -40`）：

- 输出恰 40 行：security.py 26 处（1–243，该文件匹配已完整）+ middleware.py 前 14 处（止于 283，被 `head -40` 截断）。补 grep `middleware.py` 行号 ≥284 再得 9 处（300、319、325、348、352、360、361、370、373），合计 49 处。
- `REVIEWER`：两文件零命中。`X-Frame`：区分大小写零命中，实际写法为小写 `x-frame-options`（middleware.py:271，补充 grep）。401 不在规定正则内，取自补充 grep（162、211）。
- 「未读」= 只见签名/docstring，未读函数体。

| 能力 | 文件:行 | 否决情形（被拒绝 / 脱敏 / 限流的请求） |
|---|---|---|
| PII 保形脱敏 | `_PII_KEYS` security.py:45、`_mask_text` 58、`redact_text` 67、`redact_obj` 76、`redact_row` 107 | 任意字符串先过值正则（身份证 / 手机号 / 车牌 / VIN / 邮箱，security.py:28–57 窗口，行号未 grep）→ 保形脱敏、保留首尾；字段名命中 `_PII_KEYS`（id_number、phone、plate_no、vin、email、owner_name 等）→ 整体替换 `***`；`name` 仅在含车主标记键的对象内脱敏，险种名（如「交强险」）不动（read 28–57；77 docstring） |
| 脱敏开关 | `pii_mode` security.py:98（docstring 99、return 104） | 默认 `redact`；仅 `RENEWAL_TRACE_PII=keep`（本机调试）时轨迹落原文。写入点为 `trace.record()`（security.py:16），读端 `read_trace` 逐行 `redact_row` 兜底（见 §3，trace.py:160） |
| 输入清洗与限长 | `max_message_chars` security.py:177、`sanitize_input` 186 | 入模型文本去控制字符/零宽字符（LLM01 混淆载体），超出 `max_message_chars()` 的部分被截断——清洗/截断而非拒绝（read 186–212） |
| 不可信内容定界 | 常量 security.py:159–160、`neutralize_delimiters` 195、`wrap_untrusted` 201、`guard_system_prompt` 206 | 外部内容包进 `<untrusted_user_input>` 块；用户文本里出现同名开/闭标签时改写为 `<untrusted_user_input_>`（防闭合逃逸，非拒绝）；系统提示幂等追加安全约束（read 186–212） |
| 注入检测 | `scan_untrusted` security.py:213 | 返回 score / level / signals；docstring 明言「只做标记，不做拒绝」→ 本函数无否决（read 213–260）。调用方是否据 level=high 拒绝：未查 |
| 工具调用授权 | `SecurityViolation` security.py:234、`authorize_tool_args` 243、`TOOL_OWNER_BOUND`（213–260 窗口内，行号未 grep） | 车主绑定工具（当前仅 `get_policy` 的 `owner_id`）：无会话车主身份 → 抛 `TOOL_FORBIDDEN`「无会话车主身份」；入参 owner_id ≠ 会话车主 → `TOOL_FORBIDDEN`「与会话车主不一致」；入参缺该键（None）则跳过不校验。docstring 称现有调用点入参均由服务端构造，本函数是纵深防御第二道锁（read 213–260） |
| API-Key 鉴权 | `AuthMiddleware` middleware.py:157、`key_fingerprint` 84、`lookup_key` 89、`config.api_keys()` 184 | X-API-Key 缺失或不在 RENEWAL_API_KEYS → 401 `UNAUTHORIZED` + `WWW-Authenticate: ApiKey`（211），日志 `auth_rejected` 只记密钥指纹；密钥对应 owner 与请求 owner_id 不符 → 403（162 docstring、235），日志不记 claimed（232）。**非否决**：未配置密钥表 = 演示模式放行并加 `X-Auth-Mode: demo` 头；`exempt_paths(demo)`（59）内路径免鉴权（read 157–216） |
| trace_id 白名单 | `AuthMiddleware` 内，middleware.py:157–216 窗口（行号未 grep） | `/trace/{trace_id}` 不匹配 `TRACE_ID_RE` → 400 `TRACE_ID_INVALID`（防路径穿越；演示/强制模式一视同仁）（read 157–216） |
| 轨迹读授权 | `_collect_owner_ids` middleware.py:382、`trace_owner_allowed` 395 | 未读函数体（位于「trace 内容 owner 校验」小节）；据函数名推断为轨迹内出现非请求者 owner_id 时拒绝，返回码未核实 |
| 安全响应头 | `_CSP` middleware.py:257、CSP 头 276、`x-frame-options: DENY` 271（补充 grep）、`SecurityHeadersMiddleware` 280 | 非否决（加固）：CSP 以 `default-src 'self'` 起、因单文件内联 JS/CSS 保留 `unsafe-inline` 其余收紧（13–16）；X-Frame-Options DENY；PII 端点响应禁缓存（注释 54、300）；挂最外层使 401/403/429 响应同样带安全头（283） |
| 限流 | `reset_rate_limiter` middleware.py:319、`RateLimitMiddleware` 325、`rate_limit_disabled()` 348 | 每 IP 60s 滑动窗口，默认 60 次/分钟（RENEWAL_RATE_LIMIT_PER_MIN，docstring）；`/chat` 单独计数桶与阈值（`chat_rate_limit_per_min()`，360–361）；窗口内超限 → 429 `RATE_LIMITED` + `Retry-After`（373–376）+ `rate_limited` 日志（370）。开关：`RENEWAL_RATE_LIMIT_DISABLED=1` 整体关闭并记 `rate_limit_disabled`（352）。内存实现，docstring 自述多副本需换 Redis（read 325–384） |

**§4 未找到 / 未查**
- `REVIEWER`：未找到（security.py / middleware.py 零命中；其他目录未查）。
- `X-Frame`（规定的大小写写法）：未找到；小写形式在 middleware.py:271。
- `scan_untrusted` 调用方是否拒绝：未查。
- `trace_owner_allowed` 函数体：未读，否决情形未核实。
- 限流阈值、消息长度上限的 config 默认值：未读（限流 60 次/分钟取自 docstring）。

## 补注（后补 grep，供 §3/§4 引用）

- `TraceRecorder` 方法行号（`grep -n -E '^    def ' server/trace.py`）：`__init__` trace.py:43、`_fill_latency` 62、`record` 91、`seq` 156。
- `record_turn(` 调用点（grep `server/` + `claims/` 的 `*.py`）：仅 `server/sessions.py:102`（`memory_mod.record_turn(state)`，位于 `save` 86–106 内）与定义 memory.py:473——长期记忆写入挂在会话保存路径，不在 graph.py / app.py。
