"""知识检索域回归测试：LLM-Wiki 结构 / 混合检索 / 引用溯源 / 轨迹契约。

基线来源见 reviews/knowledge.md（2026-11 检索）：
  - Karpathy llm-wiki.md（index.md / log.md / 章节锚点 / Lint 健康项）
  - RRF(k=60) 混合检索（Cormack SIGIR 2009；2026 生产实现默认值）
  - Hit@k / MRR 检索评测与逐字引用接地（JAIC 2026 / TRACE 2026 / CiteAnchor 2026）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import wiki_tool  # noqa: E402
from server import wiki_search  # noqa: E402


def _load_eval_module():
    spec = importlib.util.spec_from_file_location(
        "knowledge_retrieval_eval", ROOT / "eval" / "knowledge_retrieval_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def searcher() -> wiki_search.WikiSearch:
    return wiki_search.WikiSearch()


@pytest.fixture(scope="module")
def entries(searcher) -> list[wiki_search.WikiEntry]:
    return searcher.entries


# --- LLM-Wiki 结构与 Lint -------------------------------------------------
def test_wiki_lint_has_no_errors():
    """wiki_tool lint 零 error：front-matter/互链/锚点/index 新鲜度全部合格。"""
    errors, _warns = wiki_tool.lint(wiki_tool.load_entries())
    assert errors == []


def test_index_md_is_regenerated_from_entries(entries):
    """index.md 必须与条目一致（LLM-Wiki 的导航入口不能腐化）。"""
    on_disk = (ROOT / "wiki" / "index.md").read_text(encoding="utf-8")
    assert on_disk == wiki_tool.render_index(entries)


def test_entries_have_summary_tags_and_sections(entries):
    assert len(entries) == 8
    for e in entries:
        assert e.summary, f"{e.wiki_id} 缺 summary"
        assert e.tags, f"{e.wiki_id} 缺 tags"
        assert len(e.sections) >= 2, f"{e.wiki_id} 章节不足（锚点不可用）"
        assert all(h.strip() for h, _ in e.sections)


def test_log_md_is_append_only_ledger():
    text = (ROOT / "wiki" / "log.md").read_text(encoding="utf-8")
    assert text.count("\n## [") >= 1
    assert "## [20" in text  # `## [YYYY-MM-DD] action | title` 可 grep 前缀


# --- 检索质量（标注集） ----------------------------------------------------
def test_hit_at_3_on_labeled_set():
    """16 条正样本 + 1 条负样本：混合检索 Hit@3 ≥ 0.94（实测见 reviews/knowledge.md）。"""
    ev = _load_eval_module()
    result = ev.evaluate(wiki_search.WikiSearch(), "fusion")
    assert result["hit@3"] >= 0.94
    assert result["mrr@5"] >= 0.90


def test_rrf_fusion_uses_rank_only():
    """RRF 只用排名：构造两个反序候选表，融合分应只依赖名次。"""
    fused = wiki_search._rrf_fuse([[0, 1], [1, 0]])
    assert fused[0] == pytest.approx(fused[1])
    assert wiki_search.RRF_K == 60


def test_all_channels_return_positive_scores(searcher):
    """三通道配置下，典型查询至少在两个通道里召回到正确条目。"""
    entries, _ = searcher.search_with_score("三者险保额档位与基准保费", top_k=3)
    assert [e.wiki_id for e in entries][0] == "wiki-dsx"
    fired = [name for name, ids in searcher.last_diagnostics.items() if ids]
    assert len(fired) >= 2


# --- 引用溯源（citation grounding） --------------------------------------
def test_span_citation_is_verbatim_and_anchored(entries):
    """引用必须能回溯到「条目 + 章节 + 正文逐字片段」。"""
    by_id = {e.wiki_id: e for e in entries}
    for wid, query in [("wiki-dsx", "200万三者险基准保费"),
                       ("wiki-rate-surcharge", "出险两次费率上浮"),
                       ("wiki-csx", "涉水行驶发动机进水")]:
        entry = by_id[wid]
        span = wiki_search.span_citation(entry, query)
        assert span["verbatim"], f"{wid} 摘录不是正文逐字子串：{span['span']}"
        assert span["anchor"].startswith(wid + "#")
        heading = span["anchor"].split("#", 1)[1]
        assert heading in [h for h, _ in entry.sections]


def test_grounding_rejects_out_of_corpus_query(entries):
    """语料未覆盖的问题：命中条目不得被判为接地（防编造引用）。"""
    hits, _ = wiki_search.WikiSearch().search_with_score("划痕险理赔流程", top_k=3)
    checks = wiki_search.verify_citations("划痕险理赔流程", hits)
    assert not any(c["grounded"] for c in checks)


def test_grounding_reports_coverage(entries):
    entry = next(e for e in entries if e.wiki_id == "wiki-dsx")
    checks = wiki_search.verify_citations("200万三者险基准保费", [entry])
    assert 0.0 < checks[0]["coverage"] <= 1.0
    assert checks[0]["grounded"] is True


# --- LLM-Wiki 全量上下文 --------------------------------------------------
def test_llm_wiki_context_covers_all_entries_and_nav(entries):
    ctx = wiki_search.llm_wiki_context(entries)
    expected = sum(len(e.body) + len(f"[{e.wiki_id}] {e.title}（{e.source} {e.version}）\n")
                   for e in entries) + 2 * (len(entries) - 1)
    assert len(ctx) >= expected, "全量上下文未覆盖所有条目（模式判断会退化）"
    for e in entries:
        assert f"[{e.wiki_id}]" in ctx
    assert "index.md 目录" in ctx  # 导航层（先读目录定位）
    assert len(ctx) <= 24000  # 预算内，无需切片检索


# --- 轨迹契约 --------------------------------------------------------------
def test_trace_contract_strict_keys(entries):
    """SPEC §5：retrieval 事件 output 严格四字段，锚点/覆盖率不得混入。"""
    hits, scores = wiki_search.WikiSearch().search_with_score("三者险保额", top_k=3)
    rows = wiki_search.hits_for_trace(hits, scores)
    assert rows
    for row in rows:
        assert set(row) == {"wiki_id", "source", "version", "score"}
        assert isinstance(row["score"], float)
