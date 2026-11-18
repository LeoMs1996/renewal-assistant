"""D5 问答 demo：理赔 LLM-Wiki 检索 → 带引用回答（模式与降级显式标注）。

两条路径：

- `extractive`（默认，确定性、无网络）：把检索到的章节逐字片段按引用锚点拼成答案；
  证据不足（`retrieve()` 判 `abstained`）时明确输出「依据不足」，不硬答。
- `llm`（显式开启）：复用续保 `server.llm.get_client()`（同一 GLM/Anthropic 兼容通道），
  只喂检索到的 wiki 证据，要求逐句标注 `[wiki_id#section]`；模型不可用时**降级为 extractive**
  并在输出里写明 `degraded=True` 与 `error_type`（对齐 SPEC-claims §9 的降级留痕要求）。

LLM 路径的开启方式（默认关闭，避免 CI 里意外出网）：
    CLAIMS_QA_LLM=1 python -m claims.qa_demo "..." --mode llm
    python -m claims.qa_demo "..." --mode auto      # 有凭证且 CLAIMS_QA_LLM=1 才走 LLM

用法：
    python -m claims.qa_demo "农业保险赔付档位怎么确定"
    python -m claims.qa_demo "..." --mode llm --json
"""

from __future__ import annotations

import argparse
import json
import os
import re

from claims import wiki_retrieve as wr
from server.llm import get_client

SYSTEM = (
    "你是保险理赔知识库问答助手。只能使用给定的 wiki 证据回答，不得引入外部知识，不得编造条款。"
    "每个结论后用 [wiki_id#章节] 标注引用；证据不足以回答时，明确说「依据不足」，并说明缺什么。"
)

ANSWER_CITE_RE = re.compile(r"\[([a-z0-9][a-z0-9\-]+)(?:#([^\]\n]+))?\]")

#: 进入 LLM 上下文的单页最大字符数（36 页语料单页通常 < 4k）。
PAGE_CHAR_CAP = 4000


def _evidence_block(searcher: wr.ClaimsWikiSearch, hits: list[dict]) -> str:
    by_id = {entry.wiki_id: entry for entry in searcher.entries}
    parts: list[str] = []
    for hit in hits:
        entry = by_id.get(hit["wiki_id"])
        if entry is None:
            continue
        section = hit["section"] or ""
        text = wr._section_text(entry, section)[:PAGE_CHAR_CAP]
        parts.append(f"[{hit['wiki_id']}#{section}] {hit['title']}\n{text}")
    return "\n\n".join(parts)


def extractive_answer(query: str, result: dict) -> str:
    """确定性答案：引用锚点 + 逐字片段。"""
    if result["abstained"]:
        return (f"【依据不足】claims wiki 未覆盖该问题（查询词最高支持 "
                f"{result['best_term_support']}，门槛 {result['min_term_support']}）。"
                "不给出结论，避免编造。")
    lines = ["【依据】以下片段来自理赔 LLM-Wiki，引用可回到 raw 源逐字核对："]
    for hit in result["hits"]:
        lines.append(
            f"- [{hit['anchor']}] {hit['title']}：{hit['span']}"
            f"（引用接地 {hit['citations_ok']}/{hit['citations_total']}；"
            f"逐字级 {hit['citations_strict']}/{hit['citations_total']}）")
    return "\n".join(lines)


def _llm_allowed() -> bool:
    return os.environ.get("CLAIMS_QA_LLM", "").strip().lower() in {"1", "true", "yes", "on"}


def llm_answer(query: str, result: dict, searcher: wr.ClaimsWikiSearch) -> dict:
    """真实模型答案；不可用/失败时返回带降级信息的兜底。"""
    client = get_client()
    if not client.available:
        return {"answer": extractive_answer(query, result), "mode": "extractive",
                "degraded": True, "error_type": "NoCredentials",
                "error_message": "ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN 未配置"}
    prompt = (f"问题：{query}\n\n证据：\n"
              f"{_evidence_block(searcher, result['hits'])}\n\n"
              "请基于上述证据回答；每句结论后标注 [wiki_id#章节]；证据不足就说「依据不足」。")
    res = client.chat(system=SYSTEM, messages=[{"role": "user", "content": prompt}],
                      max_tokens=600, node="claims_d5_demo")
    if res.mode != "llm":
        return {"answer": extractive_answer(query, result), "mode": "extractive",
                "degraded": True, "error_type": res.error_type or "LLMUnavailable",
                "error_message": res.error_message or "模型调用失败"}
    return {"answer": res.text, "mode": "llm", "degraded": False,
            "tokens_in": res.tokens_in, "tokens_out": res.tokens_out}


def _answer_citations(answer: str, hits: list[dict]) -> dict:
    """答案里的 `[wiki_id#section]` 能否解析到本次检索到的证据。"""
    known = {hit["wiki_id"]: hit["anchor"] for hit in hits}
    refs, resolved = [], 0
    for wiki_id, section in ANSWER_CITE_RE.findall(answer):
        if not wiki_id.startswith("claims-"):
            continue
        ok = wiki_id in known
        resolved += 1 if ok else 0
        refs.append({"wiki_id": wiki_id, "section": section.strip(), "resolved": ok})
    return {"total": len(refs), "resolved": resolved,
            "resolvable_rate": round(resolved / len(refs), 3) if refs else None}


def answer(query: str, mode: str = "auto", top_k: int = wr.DEFAULT_TOP_K) -> dict:
    searcher = wr.get_searcher()
    result = wr.retrieve(query, top_k=top_k, searcher=searcher)

    if mode == "extractive":
        body = {"answer": extractive_answer(query, result), "mode": "extractive",
                "degraded": False}
    elif mode == "llm" or (mode == "auto" and _llm_allowed()):
        body = llm_answer(query, result, searcher)
    else:
        body = {"answer": extractive_answer(query, result), "mode": "extractive",
                "degraded": False,
                "reason": "llm 未启用（默认关闭；置 CLAIMS_QA_LLM=1 或 --mode llm）"}

    return {
        "query": query,
        **body,
        "abstained": result["abstained"],
        "best_term_support": result["best_term_support"],
        "corpus": result["corpus"],
        "grounding": {"rate": result["grounding_rate"],
                      "strict_rate": result["strict_verbatim_rate"],
                      "total": result["citations"]["total"],
                      "ok": result["citations"]["ok"],
                      "strict": result["citations"]["strict"]},
        "answer_citations": _answer_citations(body["answer"], result["hits"]),
        "evidence": [h["anchor"] for h in result["hits"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="理赔 LLM-Wiki 问答 demo")
    parser.add_argument("query")
    parser.add_argument("--mode", choices=["auto", "extractive", "llm"], default="auto")
    parser.add_argument("--top-k", type=int, default=wr.DEFAULT_TOP_K)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    out = answer(args.query, mode=args.mode, top_k=args.top_k)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print(f"问题：{out['query']}")
    print(f"模式：{out['mode']}（degraded={out['degraded']}"
          + (f"，原因：{out.get('error_type')}" if out.get("degraded") else "") + "）")
    print(f"语料：{out['corpus']['pages']} 页，sha256 {out['corpus']['content_sha256']}")
    print(f"证据：{out['evidence']}")
    print(f"引用接地：{out['grounding']['ok']}/{out['grounding']['total']}"
          f"（率 {out['grounding']['rate']}，逐字级 {out['grounding']['strict_rate']}）")
    print(f"答案引用可解析：{out['answer_citations']['resolved']}/{out['answer_citations']['total']}")
    print("\n" + out["answer"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
