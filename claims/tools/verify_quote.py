"""材料引用校验：`quote` 必须是原材料的**逐字子串**（契约 §4.3 硬约束 2）。

沿用 LLM-Wiki 的断言级引用口径（`docs/research/llmwiki-spec.md` §6）：无出处/改写的
"引用"一律作废，宁可丢事实，也不让模型的话直接进金额链路。
"""

from __future__ import annotations


def normalize(text: str) -> str:
    """仅做空白归一（不改变文字本身），用于跨行引用的子串比较。"""
    return " ".join(text.split())


def is_verbatim(quote: str, source: str) -> bool:
    """quote 是否为 source 的逐字子串（允许空白差异）。"""
    if not quote or not source:
        return False
    return normalize(quote) in normalize(source)


def filter_facts(analysis: dict, sources: dict[str, str]) -> tuple[dict, list[str]]:
    """丢弃无出处/非逐字的事实，返回 (过滤后的 analysis, 被丢弃的 key 列表)。

    - `sources`: `{doc_id: 材料全文}`
    - 只保留 `evidence.quote` 逐字命中该 doc 的 fact；其余记入 dropped。
    """
    dropped: list[str] = []
    out = dict(analysis)
    documents = []
    for doc in analysis.get("documents", []):
        doc_id = doc.get("doc_id", "")
        source = sources.get(doc_id, "")
        kept = []
        for fact in doc.get("facts", []):
            evidence = fact.get("evidence") or {}
            quote = evidence.get("quote", "")
            if evidence.get("doc_id", doc_id) != doc_id or not is_verbatim(quote, source):
                dropped.append(str(fact.get("key", "?")))
                continue
            kept.append(fact)
        new_doc = dict(doc)
        new_doc["facts"] = kept
        documents.append(new_doc)
    out["documents"] = documents
    return out, dropped
