"""D5 检索质量评测：Hit@1 / Hit@5 / MRR@5 + 引用接地率（含负样本拒答）。

口径来源（详见 `docs/log/prep-d5-retrieval.md` §4）：

- Hit@k / MRR@k 按 ir_measures 文档的 TREC 口径：`Hit@k = Success@k`（top-k 内出现目标页即 1，
  **不是** Recall@k）；`MRR@k = mean(1/首个命中排名)`。见
  https://ir-measur.es/en/latest/measures.html
- 引用接地率 = 返回证据（top-3）里的断言级引用中，能解析回 raw 源并逐字成立的比例。
  `grounding` 含字段存在性断言；`strict` 只算取值逐字/引用块逐字（更接近 ALCE 的 citation
  precision，但不做 NLI 蕴含，见 ALCE arXiv:2305.14627）。

**防循环论证**：查询集按 `rewritten`（自然改写，主指标）/ `seen`（页面标题拷贝，泄漏上界）/
`negative`（语料未覆盖，只测拒答）三类**分开报数**，不混成一个总分。

用法：
    python -m claims.eval_retrieval              # 全量 + 落盘 JSON
    python -m claims.eval_retrieval --json       # 额外打印 JSON
    python -m claims.eval_retrieval --wiki-dir data/llm-wiki-claims/wiki
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from claims import config
from claims import wiki_retrieve as wr

TOP_K = 5          # Hit@5 / MRR@5 的截断
GROUNDING_K = 3    # 引用接地只算实际会展示给用户的前 3 条证据

#: 标注集（**预注册**：先写查询与期望，再跑；miss 不回调查询，避免对评测集过拟合）。
LABELED: list[dict] = [
    # --- rewritten：自然中文问法，不贴 raw 题干 ---------------------------------
    {"kind": "rewritten", "q": "农业保险赔付档位怎么确定",
     "expect": ("claims-faq-agri",)},
    {"kind": "rewritten", "q": "病害感染情况和赔付结论是什么关系",
     "expect": ("claims-faq-agri", "claims-section-agri-compensation-tier",
                "claims-entity-compensation-tier")},
    {"kind": "rewritten", "q": "这批农业险样本有多少条",
     "expect": ("claims-doc-ins-mmbench-agricultural", "claims-faq-agri")},
    {"kind": "rewritten", "q": "农业险样本要求模型输出哪些字段",
     "expect": ("claims-section-agri-compensation-tier", "claims-faq-agri")},
    {"kind": "rewritten", "q": "果穗数量的分布情况",
     "expect": ("claims-section-agri-insured-subject",)},
    {"kind": "rewritten", "q": "作物物种字段有哪些取值",
     "expect": ("claims-section-agri-insured-subject",)},
    {"kind": "rewritten", "q": "哪些样本判了部分赔付",
     "expect": ("claims-faq-agri",)},
    {"kind": "rewritten", "q": "车损理赔金额受保额和损失金额什么约束",
     "expect": ("claims-faq-claim", "claims-section-claim-coverage-limits")},
    {"kind": "rewritten", "q": "保单过期还能不能理赔",
     "expect": ("claims-section-claim-policy-validity", "claims-entity-policy-expiry")},
    {"kind": "rewritten", "q": "健康险风险等级怎么判定",
     "expect": ("claims-section-health-risk-level", "claims-faq-health")},
    {"kind": "rewritten", "q": "影像检查部位和核保决定如何对应",
     "expect": ("claims-section-health-imaging-part", "claims-faq-health")},
    {"kind": "rewritten", "q": "财产险要识别哪些灾种",
     "expect": ("claims-section-property-disaster-type",)},
    {"kind": "rewritten", "q": "事故主责怎么认定",
     "expect": ("claims-section-liability-causation",
                "claims-entity-primary-responsibility")},
    {"kind": "rewritten", "q": "道路场景和天气光照怎么记录",
     "expect": ("claims-section-liability-environment",
                "claims-section-liability-scene-context")},
    # --- seen：页面标题拷贝（数据泄漏上界，只作对照） --------------------------
    {"kind": "seen", "q": "INS-MMBench 子集：agricultural 保险样本总览",
     "expect": ("claims-doc-ins-mmbench-agricultural",)},
    {"kind": "seen", "q": "INS-MMBench 子集：auto 保险样本总览",
     "expect": ("claims-doc-ins-mmbench-auto",)},
    {"kind": "seen", "q": "INS-MMBench 子集：health 保险样本总览",
     "expect": ("claims-doc-ins-mmbench-health",)},
    {"kind": "seen", "q": "INS-MMBench 子集：property 保险样本总览",
     "expect": ("claims-doc-ins-mmbench-property",)},
    {"kind": "seen", "q": "农业保险赔付档位如何确定？",
     "expect": ("claims-faq-agri",)},
    {"kind": "seen", "q": "灾种识别（property_risk_management）",
     "expect": ("claims-section-property-disaster-type",)},
    # --- negative：语料未覆盖，期望拒答 ---------------------------------------
    {"kind": "negative", "q": "新能源车电池自燃怎么赔", "expect": ()},
    {"kind": "negative", "q": "健康险等待期多久", "expect": ()},
    {"kind": "negative", "q": "划痕险理赔流程怎么走", "expect": ()},
    {"kind": "negative", "q": "台风导致大棚受损怎么定损", "expect": ()},
]


def _metrics(rows: list[dict], top_k: int = TOP_K) -> dict:
    positives = [r for r in rows if r["expect"]]
    hit1 = sum(1 for r in positives if r["rank"] == 1) / len(positives) if positives else 0.0
    hitk = sum(1 for r in positives if r["rank"] and r["rank"] <= top_k) / len(positives) \
        if positives else 0.0
    mrr = sum((1.0 / r["rank"]) if (r["rank"] and r["rank"] <= top_k) else 0.0
              for r in positives) / len(positives) \
        if positives else 0.0
    return {
        "queries": len(rows),
        "scored_queries": len(positives),
        "hit@1": round(hit1, 3),
        f"hit@{top_k}": round(hitk, 3),
        f"mrr@{top_k}": round(mrr, 3),
    }


def evaluate(searcher: wr.ClaimsWikiSearch, top_k: int = TOP_K) -> dict:
    rows: list[dict] = []
    for case in LABELED:
        result = wr.retrieve(case["q"], top_k=top_k, searcher=searcher)
        ids = [hit["wiki_id"] for hit in result["hits"]]
        expect = tuple(case["expect"])
        rank = next((i + 1 for i, wid in enumerate(ids) if wid in expect), None)
        shown = result["hits"][:GROUNDING_K]
        total = sum(hit["citations_total"] for hit in shown)
        ok = sum(hit["citations_ok"] for hit in shown)
        strict = sum(hit["citations_strict"] for hit in shown)
        rows.append({
            "kind": case["kind"],
            "query": case["q"],
            "expect": list(expect),
            "got": ids,
            "rank": rank,
            "abstained": result["abstained"],
            "best_term_support": result["best_term_support"],
            "citations_total": total,
            "citations_ok": ok,
            "citations_strict": strict,
        })

    splits: dict[str, dict] = {}
    for kind in ("rewritten", "seen", "negative"):
        subset = [r for r in rows if r["kind"] == kind]
        metrics = _metrics(subset, top_k)
        if kind == "negative":
            metrics["abstention"] = (
                f"{sum(1 for r in subset if r['abstained'])}/{len(subset)}")
        else:
            total = sum(r["citations_total"] for r in subset)
            ok = sum(r["citations_ok"] for r in subset)
            strict = sum(r["citations_strict"] for r in subset)
            metrics["grounding@3"] = round(ok / total, 3) if total else None
            metrics["strict_grounding@3"] = round(strict / total, 3) if total else None
            metrics["citations"] = {"total": total, "ok": ok, "strict": strict}
        metrics["per_query"] = subset
        splits[kind] = metrics

    return {
        "schema": "d5-retrieval-eval/1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "config": {"top_k": top_k, "grounding_k": GROUNDING_K,
                   "min_term_support": wr.MIN_TERM_SUPPORT},
        "corpus": searcher.corpus_summary(),
        "splits": splits,
    }


def _print_report(report: dict) -> None:
    corpus = report["corpus"]
    print(f"语料：{corpus['pages']} 页 / {corpus['chars']} 字符 "
          f"{corpus['by_type']} sha256:{corpus['content_sha256']}")
    print(f"截断：Hit@{report['config']['top_k']} / MRR@{report['config']['top_k']}，"
          f"引用接地看 top-{report['config']['grounding_k']}，"
          f"拒答门槛 term_support<{report['config']['min_term_support']}")
    print()
    print("| 查询集 | 条数 | Hit@1 | Hit@5 | MRR@5 | 引用接地 | 逐字级 | 拒答 |")
    print("|---|---|---|---|---|---|---|---|")
    for kind, m in report["splits"].items():
        print(f"| {kind} | {m['queries']} | {m.get('hit@1', '—')} | {m.get('hit@5', '—')} | "
              f"{m.get('mrr@5', '—')} | {m.get('grounding@3', '—')} | "
              f"{m.get('strict_grounding@3', '—')} | {m.get('abstention', '—')} |")
    print()
    for kind in ("rewritten", "negative"):
        print(f"### {kind} 逐条")
        for row in report["splits"][kind]["per_query"]:
            first = row["got"][0] if row["got"] else None
            print(f"- {'✓' if (row['rank'] or row['abstained']) else '✗'} rank={row['rank']} "
                  f"abstained={row['abstained']} support={row['best_term_support']} "
                  f"top1={first}  q={row['query']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="理赔 LLM-Wiki 检索质量评测")
    parser.add_argument("--wiki-dir", default=None, help="覆盖语料根（默认 claims.config.wiki_dir()）")
    parser.add_argument("--json", action="store_true", help="打印机器可读 JSON")
    args = parser.parse_args(argv)

    searcher = wr.get_searcher(args.wiki_dir)
    report = evaluate(searcher)
    _print_report(report)

    out_dir = Path(config.data_dir()) / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"d5-retrieval-{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")
    if "--json" in (argv if argv is not None else sys.argv):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
