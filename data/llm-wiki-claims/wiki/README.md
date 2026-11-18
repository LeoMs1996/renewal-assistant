# data/llm-wiki-claims/wiki/ —— 理赔 LLM-Wiki（**入库**，与续保 `wiki/` 物理分离）

> 状态：**D3 样张阶段**（2026-11-18）。已落 3 页 + `index.md` + `log.md` + `schema.md`；计划 36 页，其余 33 页由后续任务补齐。
> 生成方式：`data/llm-wiki-claims/scripts/compile_wiki.py`（**勿手改**）；校验：`scripts/wiki_lint.py`。

## 先读这三份

| 文件 | 作用 |
|---|---|
| `schema.md` | 本语料根的 schema：frontmatter 必填、`insurance_line` 枚举、span 语法、正文约定、已知边界 |
| `index.md` | 目录（每页一行：链接/标题/类型/摘要/tags/updated），脚本重建，**勿手改** |
| `log.md` | 只追加账本，`grep '^## \['` 可回溯每页的 `page/units/qids/result/lint` |

## 为什么必须和续保 `wiki/` 分开

续保 `wiki/`（`renewal-assistant/wiki/`）是**已交付且被测试间接依赖的知识库**，属保护对象，只读。
理赔知识若混进去，会同时污染两件事：续保检索的语料分布、以及理赔条目的可审计性（分不清哪条是续保口径、哪条是理赔口径）。

所以物理分目录 + 运行时用环境变量指过去：

```bash
export WIKI_DIR="$PWD/data/llm-wiki-claims/wiki"
```

`server/config.py` 已支持该变量（默认 `${BASE_DIR}/wiki`），**无需改一行 server 代码**即可复用 `server/wiki_search.py`。

## 页面约定（摘要，完整见 `schema.md`）

- frontmatter 9 必填：`id/type/title/domain(=claims)/summary/tags/source_refs/updated/related` + `status`，另有 `insurance_line`（旧名 `claim_type`，已改名）与 `raw_refs`。
- 引用是**断言级**：`⟦S:INS-MMBench:qid=<split>_<idx>@labels.<键>⟧`（字段）、`@L<a>-L<b>`（题干行区间）、`@<图片路径>`（视觉证据）。禁止「来源：raw-xxx」这类粗引用。
- 正文只允许两类内容：逐字引用块（`>` + 行区间标记）与样本表行（每行带字段标记）；聚合陈述必须带区间标记，且单元集合 ⊆ 本页 `source_refs`。
- `related` 必须双向，且只在**已编译**页面之间连边。

## 质量门（每次改页面后必跑）

```bash
python3 data/llm-wiki-claims/scripts/compile_wiki.py build --all   # 或 --pages <id,...>
python3 data/llm-wiki-claims/scripts/wiki_lint.py                  # FAIL>0 即 exit 1
python3 data/llm-wiki-claims/scripts/compile_wiki.py check         # 逐字节可复现校验
```

lint 覆盖：frontmatter/枚举（L1）、index↔磁盘（L2）、断链与非双向 related（L3）、孤儿页（L4）、
重复 id/标题（L5）、引用不可回溯（L6，含逐字比对）、无来源断言（L7）、空/超长页（L8）、
摘要漂移（L10）、越界引用（L11）。

## 已知边界（页面正文里也会写）

- 54 条 `task_layer` 全为 `scenario`：**分层只落在 `task_name`**，不存在更粗/更细的层级区分度。
- 54 条 `answer` 全为 `null`：页面不得编造标准答案；D5 只评检索/接地指标。
- 图片未入 `raw/assets/`：引用为 `data/ins-mmbench/raw/...`，新 clone 需按 `data/ins-mmbench/FETCH.md` 重取后复核 sha256。

## 硬规则

- 禁止写入续保 `wiki/`；禁止把理赔条目复制一份进续保目录。
- 一切内容基于公开数据集（INS-MMBench，Apache-2.0，revision `b77ea65c…`）或合成数据，不得含真实 PII。
- 手改页面会被 `check` 判为「非幂等」、被 lint 判为 L6 不一致——改内容请改生成器或 raw，不要改产物。
