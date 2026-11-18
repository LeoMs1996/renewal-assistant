"""D5 检索层测试：语料隔离 / 空语料显式失败 / 引用回 raw / 指标公式 / 降级。

运行：`.venv/bin/python -m pytest claims/tests/test_d5_wiki_retrieval.py -q`
（claims 不在 pyproject 的默认 testpaths，续保 148 passed 口径不受影响）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from claims import config, eval_retrieval, qa_demo  # noqa: E402
from claims import wiki_retrieve as wr  # noqa: E402
from server import wiki_search as ws  # noqa: E402


@pytest.fixture(scope="module")
def searcher() -> wr.ClaimsWikiSearch:
    return wr.get_searcher()


# --------------------------------------------------------------------------- #
# 1. 语料隔离：只读 claims wiki，不读续保 wiki
# --------------------------------------------------------------------------- #
def test_loads_claims_wiki_only(searcher):
    assert searcher.entries, "claims wiki 不应为空"
    claims_root = config.wiki_dir().resolve()
    for entry in searcher.entries:
        assert claims_root in entry.path.resolve().parents, f"越界读取：{entry.path}"
    ids = {entry.wiki_id for entry in searcher.entries}
    assert ids, "wiki_id 不应为空"
    # 续保 wiki 的 id 形如 wiki-jqx / wiki-dsx；理赔域不应出现
    assert not {i for i in ids if i.startswith("wiki-")}


def test_claims_wiki_dir_differs_from_renewal():
    assert config.wiki_dir().resolve() != ws.config.WIKI_DIR.resolve()
    assert "llm-wiki-claims" in str(config.wiki_dir())


def test_renewal_searcher_untouched(searcher):
    """用理赔检索器后，续保单例仍指向续保 wiki（不共享 entries/_index）。"""
    renewal = ws.get_searcher()
    assert renewal is not searcher
    renewal_ids = {entry.wiki_id for entry in renewal.entries}
    assert not (renewal_ids & {entry.wiki_id for entry in searcher.entries})
    assert renewal.wiki_dir.resolve() == ws.config.WIKI_DIR.resolve()


# --------------------------------------------------------------------------- #
# 2. 空语料必须显式失败（队长 2026-11-18 的 blocker 项）
# --------------------------------------------------------------------------- #
def test_missing_wiki_dir_raises(monkeypatch, tmp_path):
    missing = tmp_path / "nope"
    monkeypatch.setenv("CLAIMS_WIKI_DIR", str(missing))
    with pytest.raises(wr.WikiCorpusEmpty):
        wr.ClaimsWikiSearch()


def test_empty_wiki_dir_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(wr.WikiCorpusEmpty):
        wr.ClaimsWikiSearch(empty)


def test_directory_without_frontmatter_raises(tmp_path):
    (tmp_path / "not-a-page.md").write_text("# 没有 frontmatter\n", encoding="utf-8")
    with pytest.raises(wr.WikiCorpusEmpty):
        wr.ClaimsWikiSearch(tmp_path)


# --------------------------------------------------------------------------- #
# 3. 检索 + 章节引用
# --------------------------------------------------------------------------- #
def test_search_returns_anchor_and_citations(searcher):
    hits = searcher.search("农业保险赔付档位怎么确定", top_k=3)
    assert hits
    top = hits[0]
    assert top.anchor.startswith(top.wiki_id)
    assert top.citations_total > 0
    assert top.citations_ok == top.citations_total
    assert 0.0 <= top.term_support <= 1.0


def test_corpus_summary_is_stable(searcher):
    summary = searcher.corpus_summary()
    assert summary["pages"] == len(searcher.entries)
    assert summary["pages"] >= 36, "D3/t20 交付应为 36 页；少于此值需先修 wiki"
    assert set(summary["by_type"]) >= {"doc", "section", "entity", "faq"}
    assert len(summary["content_sha256"]) == 16


# --------------------------------------------------------------------------- #
# 4. 引用回 raw：正例成立、编造被拦（负向控制）
# --------------------------------------------------------------------------- #
def _entry(body: str) -> ws.WikiEntry:
    return ws.WikiEntry(wiki_id="claims-test", version="", effective_date="",
                        source="test", title="测试页", body=body)


def test_raw_citation_valid_and_fabricated():
    raw_root = wr.claims_raw_root()
    good = "| `agri_0` | grape | ⟦S:INS-MMBench:qid=agri_0@labels.species⟧ |"
    bad = "| `agri_0` | banana | ⟦S:INS-MMBench:qid=agri_0@labels.species⟧ |"
    ok = wr.verify_raw_citations(_entry(good), raw_root=raw_root)
    assert ok["total"] == 1 and ok["ok"] == 1 and ok["strict"] == 1

    fabricated = wr.verify_raw_citations(_entry(bad), raw_root=raw_root)
    assert fabricated["total"] == 1
    assert fabricated["ok"] == 0, "取值与 raw 不符必须判未接地"
    assert "species" in fabricated["items"][0]["reason"]


def test_raw_citation_missing_source():
    body = "| x | 1 | ⟦S:INS-MMBench:qid=agri_99@labels.count⟧ |"
    report = wr.verify_raw_citations(_entry(body), raw_root=wr.claims_raw_root())
    assert report["ok"] == 0 and "raw 源缺失" in report["items"][0]["reason"]


def test_line_range_span_requires_verbatim_quote():
    raw_root = wr.claims_raw_root()
    good = ">     Please strictly output in this format:\n\n⟦S:INS-MMBench:qid=agri_0@L13-L13⟧"
    bad = ">     请严格按格式输出：\n\n⟦S:INS-MMBench:qid=agri_0@L13-L13⟧"
    assert wr.verify_raw_citations(_entry(good), raw_root=raw_root)["ok"] == 1
    assert wr.verify_raw_citations(_entry(bad), raw_root=raw_root)["ok"] == 0


# --------------------------------------------------------------------------- #
# 5. 负样本拒答（防"硬凑一条高分结果"）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("query", [
    "新能源车电池自燃怎么赔",
    "健康险等待期多久",
    "划痕险理赔流程怎么走",
    "台风导致大棚受损怎么定损",
])
def test_negative_queries_abstain(query):
    result = wr.retrieve(query)
    assert result["abstained"] is True
    assert result["best_term_support"] < wr.MIN_TERM_SUPPORT


# --------------------------------------------------------------------------- #
# 6. 指标公式（不依赖语料，固定 rank 序列即可复现）
# --------------------------------------------------------------------------- #
def test_metrics_formula():
    rows = [
        {"expect": ["a"], "rank": 1},
        {"expect": ["a"], "rank": 3},
        {"expect": ["a"], "rank": 6},
        {"expect": [], "rank": None},   # 负样本不进 Hit/MRR 分母
    ]
    m = eval_retrieval._metrics(rows, top_k=5)
    assert m["scored_queries"] == 3
    assert m["hit@1"] == pytest.approx(1 / 3, abs=1e-3)
    assert m["hit@5"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["mrr@5"] == pytest.approx((1 + 1 / 3 + 0) / 3, abs=1e-3)


def test_eval_report_shape(searcher):
    report = eval_retrieval.evaluate(searcher)
    assert report["schema"] == "d5-retrieval-eval/1"
    assert set(report["splits"]) == {"rewritten", "seen", "negative"}
    negative = report["splits"]["negative"]
    assert negative["abstention"] == "4/4"
    rewritten = report["splits"]["rewritten"]
    assert rewritten["hit@5"] >= 0.8
    assert rewritten["hit@1"] >= 0.5
    assert rewritten["grounding@3"] is not None


# --------------------------------------------------------------------------- #
# 7. 问答 demo：模式标注 + 无凭证降级
# --------------------------------------------------------------------------- #
def test_qa_demo_extractive(searcher):
    out = qa_demo.answer("农业保险赔付档位怎么确定", mode="extractive")
    assert out["mode"] == "extractive" and out["degraded"] is False
    assert out["abstained"] is False
    assert out["answer_citations"]["total"] >= 1
    assert out["answer_citations"]["resolved"] == out["answer_citations"]["total"]


def test_qa_demo_abstains_on_negative():
    out = qa_demo.answer("新能源车电池自燃怎么赔", mode="extractive")
    assert out["abstained"] is True
    assert "依据不足" in out["answer"]
    assert out["answer_citations"]["total"] == 0


def test_qa_demo_llm_degrades_without_credentials(monkeypatch):
    class _NoModel:
        available = False

    monkeypatch.setattr(qa_demo, "get_client", lambda: _NoModel())
    out = qa_demo.answer("农业保险赔付档位怎么确定", mode="llm")
    assert out["mode"] == "extractive"
    assert out["degraded"] is True
    assert out["error_type"] == "NoCredentials"
    assert out["answer"]
