# D5 检索与使用（指针）

任务契约里的 `docs/log/step-d5-retrieval.md` 即 **`docs/log/step-d5.md`**（按队长 2026-11-18 的命名）。
研究依据与评测口径见 `docs/log/prep-d5-retrieval.md`；实现、实测输出与遗留见 `docs/log/step-d5.md`。

交付代码：

- `claims/wiki_retrieve.py` — 理赔检索层（继承 `server/wiki_search.py`，显式注入 `claims.config.wiki_dir()`，
  递归加载 `docs/sections/entities/faqs`，空语料抛错；引用可回 raw 源）
- `claims/qa_demo.py` — 问答 demo（extractive / llm，模式与降级显式标注）
- `claims/eval_retrieval.py` — 留出集评测（Hit@1 / Hit@5 / MRR@5 / 引用接地 / 负样本拒答）
- `claims/tests/test_d5_wiki_retrieval.py` — 20 条测试
