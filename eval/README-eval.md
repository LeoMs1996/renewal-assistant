# eval/ 评测体系说明（2026-11 重构后）

> 本文件面向维护者：怎么跑、门禁怎么判、基线怎么更新、哪些维度还没覆盖。
> 分域评审报告见 [`../reviews/eval.md`](../reviews/eval.md)。

## 一、目录与职责

| 文件 | 职责 |
|---|---|
| `run.py` | 用例执行 + 断言引擎 + 报告生成 + CI 门禁（自管 uvicorn，独立端口） |
| `cases/*.json` | 19 条验收用例（AC-01~14 功能 + SEC-01~05 对抗），声明式断言 |
| `dimensions.py` | **维度分类法唯一来源**：断言器 → 维度映射、缺口登记、覆盖矩阵渲染 |
| `stats.py` | 基线快照（`baseline.json`）+ 成对显著性检验（McNemar 精确二项） |
| `lint_cases.py` | 用例静态校验（坏用例前置拦截，CI 第一道门） |
| `baseline.json` | 入仓基线（规则模式、`--repeat 2`），回归对比的参照 |
| `results.json` | 每次运行的机器可读快照（CI 归档；不参与判定） |
| `report-<stamp>.md` / `report.md` | 人读报告（含覆盖矩阵、稳定性、回归对比） |

## 二、两种模式，不能混跑

- **规则模式**（`RENEWAL_FORCE_RULE_MODE=1`）：确定性、无外部依赖 → CI 与基线用这个。
- **LLM 模式**（`.env` 配好凭证）：真实模型路径，但存在采样抖动与额度风险。

报告头区分「配置模式」与「有效模式」：`/health.llm_mode=llm` 只说明配了凭证，
不代表真调到了模型。SPEC v1.0.5 起降级会留三处证据（SSE `llm_degraded` /
轨迹 `degraded=True` / `done.degraded=true`），评测在 **LLM 模式下把任一命中判为
用例 FAIL（错误码 `LLM_DEGRADED`，hard 断言）**，不再是「打一行告警」。报告与
`results.json` 都会写「LLM 参与度」（`llm_participation`）：配置模式 / 有效模式 /
真实调用率 / 降级数 / 规则兜底数 / 涉及用例。

两种「模型没跑」严格区分：

| 错误码 | 含义 | 证据 | 判定 |
|---|---|---|---|
| `LLM_DEGRADED` | 宽松模式：请求开始后某次模型调用失败，回退规则 | `llm_degraded` 事件 / 轨迹 `degraded=True` / `done.degraded` / 无标记的 `mode=rule` | LLM 模式下该用例 FAIL |
| `LLM_UNAVAILABLE` | 严格模式：开流前探活失败，`/chat` 直接 503，一个 token 都没产生 | HTTP 503 + `error.code=LLM_UNAVAILABLE` | 用例执行失败，`--fail-on-degraded` 退出码 1 |

**显式规则模式（`RENEWAL_FORCE_RULE_MODE=1`）不误报**：配置上就没启用 LLM，
`mode=rule` 是预期行为，不产生降级判定（t11 反例 8623 的口径）。

## 三、常用命令

```bash
# 全量评测（CI 同款：四道门禁全开，规则模式）
RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python eval/run.py --port 8481 --repeat 2 \
  --fail-on-hard --fail-on-degraded --min-pass-rate 1.0 --fail-on-regression

# 真实模型链路（本地/定时任务，需凭证）：严格模式不允许静默降级
RENEWAL_LLM_STRICT=1 .venv/bin/python eval/run.py --port 8483 \
  --fail-on-hard --fail-on-degraded --min-pass-rate 1.0 \
  --baseline eval/baseline-llm.json

# 多域/多人并行：快照写到独立文件，避免共享 eval/results.json 互相覆盖（t7 事故）
.venv/bin/python eval/run.py --port 8485 --results /tmp/eval-mydomain/results.json

# 只跑某个目录的用例（临时实验，勿污染 cases/）
.venv/bin/python eval/run.py --port 8482 --cases /tmp/my_cases

# 用例静态校验（改过 cases/ 必跑）
.venv/bin/python eval/lint_cases.py            # 人读
.venv/bin/python eval/lint_cases.py --json     # 机器读

# 单独比较两份快照
.venv/bin/python eval/stats.py --baseline eval/baseline.json --current eval/results.json
```

## 四、四道 CI 门禁

| 门禁 | 参数 | 语义 |
|---|---|---|
| hard 零容忍 | `--fail-on-hard` | 任一 hard 断言失败即退出码 1（保费编造 / 越权 / PII / 轨迹不可回放 / 注入顺从） |
| 全量通过率 | `--min-pass-rate 1.0` | 用例级通过率低于阈值即 1（当前要求全绿） |
| 回归显著性 | `--fail-on-regression` | 与 `baseline.json` 成对比较：hard 断言退化 **或** 断言级显著退化（精确单侧二项 p<α）即 1；**模式不一致直接判不可比** |
| LLM 降级 | `--fail-on-degraded` | LLM 模式下出现 `LLM_DEGRADED`（降级/规则兜底）或 `LLM_UNAVAILABLE`（严格模式 503）即 1；规则模式下是 no-op |

为什么不用「通过率跌 2pp」这种阈值门禁：本套用例只有 19 条，单条用例 = 5.3pp，
噪声与信号同量级（参见 ossaihub CI 阈值模式文档的明确警告「eval 集 <20 条时噪声主导」）。
改用**断言级成对检验**（90 条断言，只统计翻转样本），单条断言翻转不会被误判为退化。

### CI 里到底验不验模型？

默认 CI（`.github/workflows/ci.yml`）用 `RENEWAL_FORCE_RULE_MODE=1` 跑：
**只验证业务逻辑，不验证模型链路**，这是确定性回归的刻意取舍。

> **要真正验证模型链路，CI 应以 `RENEWAL_LLM_STRICT=1` 运行**（并配好凭证）——
> 严格模式下 `/chat` 开流前会探活，LLM 不可用时直接 503 `LLM_UNAVAILABLE`，
> 评测会明确失败（`--fail-on-degraded` 退出码 1），而不是静默通过。
> 反过来，若用默认的宽松模式跑 LLM 评测，降级也会被本套断言判为
> `LLM_DEGRADED` 失败——不存在「模型没跑但全绿」的灰色地带。

建议用定时任务（nightly）跑严格模式 LLM 评测并单独维护
`baseline-llm.json`，与规则模式基线分离。

## 五、基线更新流程（重要）

基线是「上一版公认合格」的快照，**不是自动追随最新运行**：

```bash
# 1) 在主干上跑一轮全绿（含 --repeat 2，暴露抖动）
RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python eval/run.py --port 8481 --repeat 2
# 2) 人工确认 report.md 里没有 FAIL、没有「规则兜底」告警、覆盖矩阵无异常
# 3) 回写基线并在 PR 描述里说明为什么更新
RENEWAL_FORCE_RULE_MODE=1 .venv/bin/python eval/run.py --port 8481 --repeat 2 --save-baseline
```

- 规则模式与 LLM 模式**各维护一份基线**（例如 `baseline.json` / `baseline-llm.json`），
  跨模式比较会被 `mode_mismatch` 拦下。
- 基线只应在「确认是修复/预期变化」后更新；频繁更新会掩盖渐进退化。

## 六、维度覆盖与已知缺口

维度矩阵每次运行都写进 `report.md` 的「维度覆盖矩阵」小节，来源是 `dimensions.py`。
新增断言器时必须同时登记 `DIM_OF`，否则 `lint_cases.py` 报 ERROR（防止维度静默丢样本）。

当前 10 个维度全部有用例断言。明确**不引入**的两类维度及原因：

- `llm_judge_quality`（话术质量）：需 model-graded 断言（promptfoo `llm-rubric` / LangSmith
  LLM-as-judge）。本项目纪律是「只读确定性证据」，引入 judge 会带来判定噪声 + 外部模型依赖；
  前置条件：凭证稳定 + 人工标注 ≥30 条校准集。
- `cost`（token 成本）：无预算契约，规则模式无 token 消耗。

弱覆盖（已登记缺口）：`performance` 只有 ≤60s 软预算（拦挂死，不卡抖动）；
`compliance` 只有免责声明关键词断言（非语义判定）。

## 七、新增/修改用例的 SOP

1. 复制现有 case 结构：`id / title / spec / steps / assertions`（对抗用例加 `adversarial: true`）。
2. 断言必须**确定性可观测**：SSE 事件、`traces/*.jsonl` 字段、API 响应、报价登记簿。
   不要断言自由文本的措辞（那是 judge 的活）。
3. 每条断言写**唯一的 `desc`**（基线快照的稳定键，重名会被 lint E6 拦下）。
4. 契约级防线（保费/越权/PII/轨迹/注入）标 `"hard": true`。
5. 跑 `eval/lint_cases.py` → 0 ERROR 再提 PR；SPEC §7 验收清单里必须有同名条目（E8 双向校验）。
