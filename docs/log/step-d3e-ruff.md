# step-d3e · D3e ruff 清零（wiki 脚本域）

> 任务：`t30`（attempt 2，`6f4c369d-ef36-4c41-b045-f837d2eebafb`）｜执行：wiki-lead｜日期：2026-11-19
> 结论：`ruff check data/llm-wiki-claims/scripts/` → **All checks passed!**；两套 lint 0；**40 个 md sha256 与修前基线逐字节一致**（证明只动了格式，没动行为）；未改 `pyproject.toml`、未做任何豁免。

---

## 1. 做了什么（改动清单）

只改 2 个文件，共 6 处（5 条初始告警 + 1 条修完后续暴露的），**全部是纯格式/死代码清理**：

| 文件 | 位置 | 规则 | 改法 |
|---|---|---|---|
| `scripts/wiki_lint.py` | 23 行 | `F401` | 删除未使用的 `import sys`（该文件确实不再用 `sys`） |
| `scripts/wiki_lint.py` | 206 行 | `B007` | `for kind, spec, sp in ms:` → `for _kind, …`（循环变量未使用，加下划线前缀） |
| `scripts/wiki_lint.py` | 208 行 | `F841` | 解包元组时把 `kind_kind = kind` 的赋值去掉（只保留 `qid_spec, span = spec, sp`） |
| `scripts/wiki_lint.py` | 360 行 | `F841` | 删除未使用的 `indexed_ids = {r["id"] for r in rows}`（集合推导无副作用，判重实际用的是 `indexed_paths`） |
| `scripts/wiki_claims_lint.py` | 371 行 | `E702` | `print(...); return 2` 拆成两行 |
| `scripts/wiki_claims_lint.py` | 379 行 | `E702` | 同上（`--sample 必须 > 0` 分支） |

> 关于 `F841` 与 `B007` 的先后：先删掉 `kind_kind` 的赋值，`kind` 随之变成"只解包不使用"，ruff 才报 `B007`。所以是 **5 条初始 + 1 条连锁**，不是 6 条独立问题。

**没改**：`pyproject.toml`（无豁免）、`raw/**`、`wiki/*.md`、`plan.md`、`claims/**`、`server/**`。

---

## 2. 规则码分类与判断依据

| 规则 | 含义 | 为何是"格式类" | 风险控制 |
|---|---|---|---|
| `F401` | 导入未使用 | 删导入不改变任何执行路径 | 删前 `grep 'sys\.'` 确认该文件 0 处使用 |
| `F841` | 局部变量赋值未使用 | 删除的赋值右侧是常量/无副作用表达式（`kind`、集合推导） | 只删"纯赋值"，不删任何带调用/IO 的表达式 |
| `B007` | 循环控制变量未在循环体使用 | 改名 `_kind` 是纯命名变更 | ruff 只要求下划线前缀，语义不变 |
| `E702` | 一行多条语句（分号） | 拆行是最保守的格式变更 | 拆后逻辑顺序不变，`return` 仍在同一分支 |

**没有豁免，也没有放宽任何规则**：`per-file-ignores` 未新增条目；`line-length = 100` 保持原样（本次也没有 `E501` 问题，说明脚本里没有超长行）。

---

## 3. 验证证据（命令 + 真实输出）

### 3.1 修前基线（用于证明"行为没变"）

```text
$ (cd data/llm-wiki-claims/wiki && shasum -a 256 $(find . -name '*.md' | sort)) > /tmp/base_before.txt
$ wc -l < /tmp/base_before.txt
40
$ shasum -a 256 /tmp/base_before.txt
fa5179bf8b441825a00647fa20671e499407b5a68dfe6724fb5ceb3cfb47482b  /tmp/base_before.txt
```

### 3.2 四项验收（原文）

```text
$ .venv/bin/python -m ruff check data/llm-wiki-claims/scripts/
All checks passed!

$ python3 data/llm-wiki-claims/scripts/wiki_lint.py
pages=36 index_rows=36 FAIL=0 WARN=0            # exit=0

$ python3 data/llm-wiki-claims/scripts/wiki_claims_lint.py
pages=36 index_rows=36 ERROR=0 WARN=0          # exit=0

$ python3 .../compile_wiki.py build --all   # 第 1 次
$ diff /tmp/base_before.txt /tmp/after1.txt
（无输出）
✅ 与修前基线 40 md sha256 完全一致

$ python3 .../compile_wiki.py build --all   # 第 2 次
$ diff /tmp/after1.txt /tmp/after2.txt
（无输出）
✅ 两次 build --all 一致（幂等）
```

### 3.3 附带确认（未越界）

```text
$ git status --short -- wiki traces server tests SPEC.md mcp_servers claims
?? claims/                     # 他人域的既有未跟踪目录，非本次改动

$ .venv/bin/python -m ruff check . --output-format=concise
All checks passed!             # 全仓也已清零（他人域同批修完）
```

---

## 4. 豁免与遗留

| # | 项 | 说明 |
|---|---|---|
| 1 | 豁免 | **无**。未新增 `per-file-ignores`，未降低任何规则等级 |
| 2 | 页产物 | 与修前基线 sha256 完全一致 → 说明 ruff 修复没有触碰任何会影响产物的逻辑 |
| 3 | 全仓现状 | `ruff check .` 已是 `All checks passed!`，C5 可直接把 ruff 当门禁 |
| 4 | 建议（非本任务） | 把 `ruff check data/llm-wiki-claims/scripts/` 加进 CI 或 `docs/log/hard-rules.md` 的收工清单（C4 目前只写了 `ruff check .`，够用） |

**一句话交接**：6 处全是格式/死代码清理，`ruff check` 域内与全仓均 `All checks passed!`；40 个 md sha256 与修前逐字节一致，两套 lint 仍 0，未做任何规则豁免。
