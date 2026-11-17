#!/usr/bin/env python
"""知识检索域离线评测：单通道 → 双通道 → 三通道 → 层级检索的消融对比。

评估口径（2026-11 检索基线，见 reviews/knowledge.md §2）：
  - Hit@1 / Hit@3 / MRR@5：工业 RAG 检索评测的常用口径（Hit@1/3/5 + MRR@5
    见 "Comparing BM25, Multilingual-E5, and RRF for RAG"（JAIC 2026-10-17））。
  - 引用接地率（citation grounding precision）：Top-3 引用中通过逐字支撑核查的比例
    （TRACE 2026 用 Grounding Score 与人评 citation precision 对齐；CiteAnchor 2026
    做字段级核查，区分「引用有效」与「可回溯到唯一来源」）。
  - 拒答（abstention）：语料未覆盖的问题不应给出接地引用。

用法：
    python eval/knowledge_retrieval_eval.py            # 全变体对比
    python eval/knowledge_retrieval_eval.py --json     # 额外输出机器可读结果
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import wiki_search  # noqa: E402

# 标注集：expect 为可接受命中集合（多值时表示业务上等价、任一中即算命中）
LABELED: list[dict] = [
    {"q": "网约车营运期间出事故保险赔吗", "expect": ("wiki-ride-hailing",)},
    {"q": "三者险买多少保额合适", "expect": ("wiki-dsx",)},
    {"q": "交强险死亡伤残赔偿限额是多少", "expect": ("wiki-jqx",)},
    {"q": "去年出险两次今年保费涨多少", "expect": ("wiki-rate-surcharge",)},
    {"q": "涉水行驶发动机进水车损险赔吗", "expect": ("wiki-csx",)},
    {"q": "不计免赔还要单独买吗", "expect": ("wiki-deductible",)},
    {"q": "医保外用药责任险要不要加", "expect": ("wiki-ywyw",)},
    {"q": "车辆未年检出事故能不能赔", "expect": ("wiki-annual-inspection",)},
    {"q": "200万三者险基准保费多少", "expect": ("wiki-dsx",)},
    {"q": "连续三年没出险NCD系数是多少", "expect": ("wiki-rate-surcharge",)},
    {"q": "玻璃单独破碎还能单独投保吗", "expect": ("wiki-csx",)},
    {"q": "无责情况下交强险按多少赔", "expect": ("wiki-jqx",)},
    {"q": "全车盗抢的绝对免赔率", "expect": ("wiki-deductible", "wiki-csx")},
    {"q": "附加险的投保前提是什么", "expect": ("wiki-ywyw",)},
    {"q": "车龄超过十年续保要验车吗", "expect": ("wiki-csx",)},
    {"q": "顺风车合乘算营运吗", "expect": ("wiki-ride-hailing",)},
    # 负样本：语料未覆盖 → 期望「不接地/不引用」
    {"q": "划痕险理赔流程怎么走", "expect": ()},
]

VARIANTS: dict[str, dict] = {
    "A 单通道 BM25（2026-11-13 前基线）": {"channels": ("bigram",), "mode": "fusion"},
    "B 双通道+RRF（2026-11-13 改造）": {"channels": ("bigram", "word"), "mode": "fusion"},
    "C 三通道+RRF（本轮 +index 目录字段）": {"channels": ("bigram", "index", "word"),
                                             "mode": "fusion"},
    "D 层级检索 navigate（本轮 index→正文钻取）": {"channels": ("bigram", "index", "word"),
                                                  "mode": "hierarchical"},
}


def evaluate(searcher: wiki_search.WikiSearch, mode: str) -> dict:
    hit1 = hit3 = 0.0
    rr_sum = 0.0
    grounded_num = grounded_den = 0
    abstain_ok = abstain_total = 0
    per_query: list[dict] = []

    for case in LABELED:
        query, expect = case["q"], case["expect"]
        if mode == "hierarchical":
            entries, _scores = searcher.navigate(query, top_k=5)
        else:
            entries, _scores = searcher.search_with_score(query, top_k=5)
        ids = [e.wiki_id for e in entries]

        if not expect:  # 负样本：不应出现接地引用
            abstain_total += 1
            checks = wiki_search.verify_citations(query, entries[:3])
            if not any(c["grounded"] for c in checks):
                abstain_ok += 1
            per_query.append({"query": query, "expect": [], "got": ids,
                              "abstained": not any(c["grounded"] for c in checks)})
            continue

        rank = next((i + 1 for i, wid in enumerate(ids) if wid in expect), None)
        hit1 += 1.0 if rank == 1 else 0.0
        hit3 += 1.0 if rank and rank <= 3 else 0.0
        rr_sum += 1.0 / rank if rank else 0.0

        checks = wiki_search.verify_citations(query, entries[:3])
        grounded_num += sum(1 for c in checks if c["grounded"])
        grounded_den += len(checks)
        per_query.append({"query": query, "expect": list(expect), "got": ids,
                          "rank": rank,
                          "anchors": [c["anchor"] for c in checks if c["grounded"]]})

    n = sum(1 for c in LABELED if c["expect"])
    return {
        "hit@1": round(hit1 / n, 3),
        "hit@3": round(hit3 / n, 3),
        "mrr@5": round(rr_sum / n, 3),
        "grounding_precision@3": round(grounded_num / grounded_den, 3) if grounded_den else 0.0,
        "abstention": f"{abstain_ok}/{abstain_total}" if abstain_total else "n/a",
        "per_query": per_query,
    }


def main(argv: list[str]) -> int:
    searcher_default = wiki_search.WikiSearch()
    results = {}
    for name, cfg in VARIANTS.items():
        searcher = wiki_search.WikiSearch(channels=cfg["channels"])
        results[name] = evaluate(searcher, cfg["mode"])

    entries = searcher_default.entries
    catalog = {
        "corpus": {"entries": len(entries), "chars": searcher_default.total_chars,
                   "labeled_queries": len(LABELED),
                   "positive": sum(1 for c in LABELED if c["expect"])},
        "llm_wiki": {
            "full_context_chars": len(wiki_search.llm_wiki_context(entries)),
            "nav_chars": len(wiki_search.wiki_nav(entries)),
            "budget": 24000,
        },
        "variants": results,
    }

    print(f"语料：{catalog['corpus']['entries']} 条目 / {catalog['corpus']['chars']} 字符 · "
          f"标注查询 {catalog['corpus']['labeled_queries']} 条"
          f"（正样本 {catalog['corpus']['positive']}）")
    print(f"LLM-Wiki 全量上下文：{catalog['llm_wiki']['full_context_chars']} 字符"
          f"（预算 {catalog['llm_wiki']['budget']}，导航层 {catalog['llm_wiki']['nav_chars']}）")
    print()
    print("| 变体 | Hit@1 | Hit@3 | MRR@5 | 引用接地率@3 | 拒答 |")
    print("|---|---|---|---|---|---|")
    for name, r in results.items():
        print(f"| {name} | {r['hit@1']:.2f} | {r['hit@3']:.2f} | {r['mrr@5']:.3f} | "
              f"{r['grounding_precision@3']:.2f} | {r['abstention']} |")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / "eval" / f"knowledge-retrieval-eval-{stamp}.json"
    out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out.relative_to(ROOT)}")
    if "--json" in argv:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
