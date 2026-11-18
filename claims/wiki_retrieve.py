"""D5：理赔域 LLM-Wiki 检索层（复用续保 `server/wiki_search.py`，不改上游）。

为什么需要这一层（不是重复造轮子）：

1. **语料根必须可注入**。上游 `WikiSearch()` 默认读 `server.config.WIKI_DIR`（续保 8 条条款），
   且 `get_searcher()` 是进程级单例；理赔域一旦误用，会静默检索续保条款。
   本层构造时强制 `wiki_dir=claims.config.wiki_dir()`（可被 `CLAIMS_WIKI_DIR` 覆盖）。
2. **理赔 wiki 是嵌套目录**（`docs/ sections/ entities/ faqs/`），上游 `_load()` 用
   `wiki_dir.glob("*.md")` 只扫一层，会得到 0 条且**不报错**。本层重写 `_load()` 用 `rglob`。
3. **空语料必须显式失败**。上游 `available=False` 时 `search_with_score()` 返回 `([], [])`；
   对理赔流水线这是「检索不到东西但流程正常」的隐蔽故障，本层构造即断言并抛错。

复用（不重写）的部分：三通道 BM25（bigram / index / word）、RRF(k=60) 融合、
`section_for` / `excerpt` / `span_citation` 的章节级逐字引用、`verify_citations` 的词法接地、
`llm_wiki_context` 的全量上下文。

新增的判定：**引用能否回到 raw 源逐字成立**（`verify_raw_citations`）。
wiki 页的引用是断言级标记 `⟦S:INS-MMBench:<qid>@<span>⟧`（D3 规范），本层把每个标记解析到
`data/llm-wiki-claims/raw/sources/*.json`，校验 span 可解析 + 取值逐字出现在被引片段里。
依据与口径见 `docs/log/prep-d5-retrieval.md` §4.2（S1 ir_measures / S2 ALCE）。

用法：
    python -m claims.wiki_retrieve "农业保险赔付档位怎么定" --top-k 3
    python -m claims.wiki_retrieve "..." --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from claims import config
from server import wiki_search as ws

#: 导航/元文件不是知识条目（与 D3/D4 的 NON_PAGE 保持一致）。
NON_PAGE = frozenset({"index.md", "log.md", "schema.md", "README.md"})

#: D3 断言级引用标记：`⟦S:<dataset>:<ref>@<span>⟧`。
SPAN_RE = re.compile(r"⟦S:([^@⟧]+)@([^⟧]+)⟧")

#: 默认返回条数与逐字片段宽度。
DEFAULT_TOP_K = 3
#: 理赔域默认融合通道。刻意**不用**上游的 `bigram` 全量通道：上游 `_tokenize_bigram` 把英文词
#: 拆成单字母（`auto` → a/u/t/o），在「中文正文 + 英文枚举值」的理赔 wiki 上引入大量噪声，
#: 实测会让 4 个仅差一个英文词的 doc 页互相压制（见 step-d5 §3 消融表）。
#: `word`=整词（英文词/中文整段），`index`=标题+摘要+标签+章节标题（中文二元组）。
CLAIMS_CHANNELS: tuple[str, ...] = ("word", "index")
#: 证据门槛：查询内容词须在命中页全文（title+body）中出现这一比例，否则判「依据不足」。
#: 0.3 = 保守阈值（宁可拒答也不硬答）；随结果输出（min_term_support）供复查。
MIN_TERM_SUPPORT = 0.3
SPAN_WIDTH = 240

#: 引用核查结果里最多回填多少条明细（避免 JSON 过大）。
MAX_CITATION_ITEMS = 12


# --------------------------------------------------------------------------- #
# 异常：宁可显式失败，也不要静默空结果
# --------------------------------------------------------------------------- #
class WikiCorpusError(RuntimeError):
    """理赔 wiki 不可用（目录缺失/为空/检索器不可用）。"""


class WikiCorpusEmpty(WikiCorpusError):
    """语料目录不存在或没有可解析条目。"""


class WikiRankerUnavailable(WikiCorpusError):
    """BM25 检索器不可用（rank_bm25 未安装）。"""


# --------------------------------------------------------------------------- #
# 结果对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClaimsHit:
    """一条检索命中：页面级信息 + 章节级引用 + raw 级接地。"""

    wiki_id: str
    title: str
    page_type: str
    rel_path: str
    score: float
    section: str
    anchor: str
    span: str
    verbatim: bool
    grounded: bool
    coverage: float
    term_support: float
    matched_terms: tuple[str, ...]
    citations_total: int
    citations_ok: int
    citations_strict: int
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "wiki_id": self.wiki_id,
            "title": self.title,
            "type": self.page_type,
            "path": self.rel_path,
            "score": round(self.score, 4),
            "anchor": self.anchor,
            "section": self.section,
            "span": self.span,
            "verbatim": self.verbatim,
            "query_grounded": self.grounded,
            "query_coverage": self.coverage,
            "term_support": self.term_support,
            "matched_terms": list(self.matched_terms),
            "citations_total": self.citations_total,
            "citations_ok": self.citations_ok,
            "citations_strict": self.citations_strict,
            "source_refs": list(self.source_refs),
        }


# --------------------------------------------------------------------------- #
# 解析辅助
# --------------------------------------------------------------------------- #
def _frontmatter_scalar(path: Path, key: str) -> str:
    """只取一个 frontmatter 标量（上游 `WikiEntry` 没有 `type` 字段）。"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            if k.strip() == key:
                return v.strip()
    return ""


def claims_raw_root(wiki_dir: Path | None = None) -> Path:
    """raw 源根：默认是 wiki 目录的兄弟 `raw/`，可用 `CLAIMS_RAW_DIR` 覆盖。"""
    override = os.environ.get("CLAIMS_RAW_DIR")
    if override:
        return Path(override).expanduser()
    base = Path(wiki_dir) if wiki_dir else config.wiki_dir()
    return base.parent / "raw"


def _split_qid(qid: str) -> tuple[str, int]:
    split, _, idx = qid.rpartition("_")
    return split, int(idx)


def _expand_qids(spec: str) -> list[str]:
    """`qid=agri_0` / `qids=agri_0..agri_11` → qid 列表。"""
    body = spec.split("=", 1)[-1]
    if ".." in body:
        lo, hi = body.split("..", 1)
        split, start = _split_qid(lo)
        _split2, end = _split_qid(hi)
        return [f"{split}_{i}" for i in range(start, end + 1)]
    return [body]


def _raw_of(qid: str, raw_root: Path) -> dict | None:
    try:
        split, idx = _split_qid(qid)
    except (ValueError, TypeError):
        return None
    path = raw_root / "sources" / f"raw-{split}-{idx:04d}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _json_path(node: object, path: str) -> tuple[bool, object]:
    cur = node
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def _quote_block_before(lines: list[str], index: int) -> list[str]:
    """标记行之前的连续引用块（`> ...`），用于 L 区间 span 的逐字核对。"""
    buf: list[str] = []
    j = index - 1
    blanks = 0
    while j >= 0:
        raw = lines[j]
        if raw.startswith(">"):
            buf.append(raw[1:].lstrip())
            blanks = 0
            j -= 1
            continue
        if raw.strip() == "":
            # 页面格式是「引用块 + 空行 + 标记行」，空行要跳过；但最多 2 行，避免跨段误挂。
            blanks += 1
            if blanks <= 2:
                j -= 1
                continue
        break
    return list(reversed(buf))


# --------------------------------------------------------------------------- #
# 检索器
# --------------------------------------------------------------------------- #
class ClaimsWikiSearch(ws.WikiSearch):
    """理赔 LLM-Wiki 检索器：继承上游检索逻辑，修掉语料根/递归/空语料三处坑。"""

    def __init__(
        self,
        wiki_dir: Path | str | None = None,
        channels: tuple[str, ...] = CLAIMS_CHANNELS,
    ) -> None:
        super().__init__(wiki_dir=Path(wiki_dir) if wiki_dir else config.wiki_dir(),
                         channels=channels)
        # `super().__init__` 已调用本类重写的 `_load()`；这里做显式断言。
        if not self.entries:
            raise WikiCorpusEmpty(
                f"理赔 wiki 无可解析条目：{self.wiki_dir}（拒绝静默返回空结果）")
        if not self._index:
            raise WikiRankerUnavailable(
                "rank_bm25 不可用或索引构建失败：请确认已安装 rank-bm25 后重试")

    # -- 装载 ---------------------------------------------------------------
    def _load(self) -> None:  # noqa: D401 - 覆盖上游，行为见模块 docstring
        root = Path(self.wiki_dir)
        if not root.is_dir():
            raise WikiCorpusEmpty(f"理赔 wiki 目录不存在：{root}")
        for path in sorted(root.rglob("*.md")):
            if path.name in NON_PAGE:
                continue
            entry = ws._parse_entry(path)
            if entry is None:
                continue
            # 理赔页有 `type: doc|section|entity|faq|query`，上游 WikiEntry 不存该字段。
            entry.page_type = _frontmatter_scalar(path, "type") or path.parent.name
            entry.rel_path = path.relative_to(root).as_posix()
            self.entries.append(entry)
        if ws.BM25Okapi is None or not self.entries:
            return
        corpora = {
            "bigram": [ws._tokenize_bigram(e.title + "\n" + e.body) for e in self.entries],
            "index": [ws._tokenize_bigram(e.index_field) or ["∅"] for e in self.entries],
            "word": [ws._tokenize_word(e.title + "\n" + e.body) for e in self.entries],
        }
        for name in self.channels:
            docs = corpora.get(name)
            if docs:
                self._index[name] = ws.BM25Okapi(docs)

    # -- 检索 ---------------------------------------------------------------
    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[ClaimsHit]:
        """三通道 BM25 + RRF，返回带章节引用与 raw 接地的命中。"""
        entries, scores = self.search_with_score(query, top_k=top_k)
        if not entries:
            return []
        checks = {c["wiki_id"]: c for c in ws.verify_citations(query, entries)}
        out: list[ClaimsHit] = []
        for entry, score in zip(entries, scores, strict=False):
            chk = checks.get(entry.wiki_id, {})
            span = ws.span_citation(entry, query)
            report = verify_raw_citations(
                entry, span["section"], claims_raw_root(self.wiki_dir))
            out.append(
                ClaimsHit(
                    wiki_id=entry.wiki_id,
                    title=entry.title,
                    page_type=getattr(entry, "page_type", ""),
                    rel_path=getattr(entry, "rel_path", ""),
                    score=float(score),
                    section=span["section"],
                    anchor=span["anchor"],
                    span=ws.excerpt(entry, SPAN_WIDTH, query),
                    verbatim=bool(span["verbatim"]),
                    grounded=bool(chk.get("grounded", False)),
                    coverage=float(chk.get("coverage", 0.0)),
                    term_support=_term_support(query, entry),
                    matched_terms=tuple(chk.get("matched_terms", [])),
                    citations_total=int(report["total"]),
                    citations_ok=int(report["ok"]),
                    citations_strict=int(report["strict"]),
                    source_refs=tuple(
                        _source_refs(self.wiki_dir / getattr(entry, "rel_path", ""))),
                )
            )
        return out

    def corpus_summary(self) -> dict:
        """语料指纹：页数、字符数、按类型分布、内容 sha256（评测可复现用）。"""
        import hashlib

        by_type: dict[str, int] = {}
        digest = hashlib.sha256()
        total_chars = 0
        for entry in sorted(self.entries, key=lambda e: e.wiki_id):
            page_type = getattr(entry, "page_type", "?")
            by_type[page_type] = by_type.get(page_type, 0) + 1
            total_chars += len(entry.body)
            digest.update(entry.wiki_id.encode())
            digest.update(entry.body.encode())
        return {
            "pages": len(self.entries),
            "chars": total_chars,
            "by_type": dict(sorted(by_type.items())),
            "content_sha256": digest.hexdigest()[:16],
            "wiki_dir": str(self.wiki_dir),
        }


def _source_refs(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return []
    for line in m.group(1).splitlines():
        if line.startswith("source_refs:"):
            body = line.split(":", 1)[1].strip()
            if body.startswith("[") and body.endswith("]"):
                return [x.strip() for x in body[1:-1].split(",") if x.strip()]
    return []


def _section_text(entry: ws.WikiEntry, section: str) -> str:
    if not section:
        return entry.body
    for heading, text in entry.sections:
        if heading == section:
            return text
    return entry.body


def _term_support(query: str, entry: ws.WikiEntry) -> float:
    """查询内容词在命中页全文（title+body）中的支持率（防硬凑高分的证据门槛）。"""
    terms = _query_terms(query)
    if not terms:
        return 0.0
    text = entry.title + "\n" + entry.body
    return round(sum(1 for term in terms if term in text) / len(terms), 3)


def _query_terms(query: str) -> list[str]:
    terms = [t for t in ws._tokenize_bigram(query) if len(t) >= 2]
    # 只用英文/数字词；`_tokenize_word` 会把整段中文当一个词，当支持率分母会系统性压低。
    terms += [w for w in ws._tokenize_word(query)
              if len(w) >= 2 and re.fullmatch(r"[a-z0-9_\-]+", w)]
    return list(dict.fromkeys(terms))


# --------------------------------------------------------------------------- #
# 引用核查：wiki 标记 → raw 源逐字
# --------------------------------------------------------------------------- #
def _labels_level(raw: dict, key: str, haystack: str) -> tuple[str | None, str]:
    """labels.X 的接地强度：value=取值逐字出现；field=只出现字段名（存在性断言）。"""
    if not isinstance(raw.get("labels"), dict) or key not in raw["labels"]:
        return None, f"labels 缺键 {key}"
    value = str(raw["labels"][key])
    if value in haystack:
        return "value", ""
    # 表格单元格会截断长文本（如 “The vehicles does not n…”），只要前缀逐字出现就
    # 算可回溯（存在性级，不计入逐字级）；零前缀匹配仍会落到 field 检查。
    if len(value) >= 16 and value[:16] in haystack:
        return "field", ""
    if key in haystack:
        return "field", ""
    return None, f"键与取值均未出现：{key}"


def _check_marker(ref_spec: str, span: str, cited_line: str, quote_block: list[str],
                  body: str, raw_root: Path) -> tuple[bool, str, str]:
    """校验单个标记能否回到 raw 源成立；返回 (ok, level, 原因)。

    level：`value` / `verbatim` = 逐字级；`field` / `range` = 存在性/可解析级。
    """
    qids = _expand_qids(ref_spec)
    aggregate = len(qids) > 1
    levels: list[str] = []
    for qid in qids:
        raw = _raw_of(qid, raw_root)
        if raw is None:
            return False, "", f"raw 源缺失：{qid}"
        question_lines = list(raw["content"]["question"]["text"].splitlines())
        if re.fullmatch(r"L\d+-L\d+", span):
            a, b = (int(x) for x in span.replace("L", "").split("-"))
            if not (1 <= a <= b <= len(question_lines)):
                return False, "", f"{qid} 行区间越界 {span}（{len(question_lines)} 行）"
            if aggregate or not quote_block:
                levels.append("range")
                continue
            wanted = {ln.strip() for ln in question_lines if ln.strip()}
            for quoted in quote_block:
                if quoted.strip() and quoted.strip() not in wanted:
                    return False, "", f"{qid} 引用块非逐字：{quoted.strip()[:40]}"
            levels.append("verbatim")
        elif span.startswith("labels."):
            # 先把标记本身从证据文本里剔除：标记里含 `labels.<key>`，不剔除会让
            # “字段名出现”永远为真，编造的取值就无法被拦下（负向控制见测试）。
            clean = SPAN_RE.sub("", body if aggregate else cited_line)
            level, reason = _labels_level(raw, span.split(".", 1)[1], clean)
            if level is None:
                return False, "", f"{qid} {reason}"
            levels.append(level)
        elif span == "answer_status":
            if "answer_status" not in raw:
                return False, "", f"{qid} 缺 answer_status"
            levels.append("field")
        elif "." in span and span.split(".")[0] in raw:
            ok, _ = _json_path(raw, span)
            if not ok:
                return False, "", f"{qid} JSON 路径不存在：{span}"
            levels.append("field")
        else:
            image_paths = [str(im.get("path", "")) for im in raw.get("images", [])]
            if span not in image_paths:
                return False, "", f"{qid} 图片路径不存在：{span}"
            levels.append("field")
    strict = all(level in {"value", "verbatim"} for level in levels)
    return True, ("strict" if strict else "presence"), ""


def verify_raw_citations(entry: ws.WikiEntry, section: str = "",
                         raw_root: Path | None = None) -> dict:
    """把某页（或某章节）的断言级引用逐条解析回 raw，统计接地率。

    `rate` 用 `ok`（含字段存在性断言）；`strict_rate` 只算逐字级（value/verbatim）。
    """
    text = _section_text(entry, section)
    lines = text.split("\n")
    raw_root = raw_root or claims_raw_root()
    items: list[dict] = []
    total = ok = strict = 0
    for i, line in enumerate(lines):
        for ref_spec, span in SPAN_RE.findall(line):
            total += 1
            passed, level, reason = _check_marker(
                ref_spec, span, line, _quote_block_before(lines, i), text, raw_root)
            ok += 1 if passed else 0
            strict += 1 if (passed and level == "strict") else 0
            if len(items) < MAX_CITATION_ITEMS:
                items.append({"ref": ref_spec, "span": span,
                              "ok": passed, "level": level, "reason": reason})
    return {
        "total": total,
        "ok": ok,
        "strict": strict,
        "rate": round(ok / total, 3) if total else 1.0,
        "strict_rate": round(strict / total, 3) if total else 1.0,
        "items": items,
    }


# --------------------------------------------------------------------------- #
# 对外接口
# --------------------------------------------------------------------------- #
_CACHE: dict[str, ClaimsWikiSearch] = {}


def get_searcher(wiki_dir: Path | str | None = None) -> ClaimsWikiSearch:
    """按解析后的绝对路径缓存（测试改 `CLAIMS_WIKI_DIR` 后不会拿到旧实例）。"""
    target = Path(wiki_dir) if wiki_dir else config.wiki_dir()
    key = str(target.expanduser().resolve())
    if key not in _CACHE:
        _CACHE[key] = ClaimsWikiSearch(target)
    return _CACHE[key]


def retrieve(query: str, top_k: int = DEFAULT_TOP_K,
             searcher: ClaimsWikiSearch | None = None) -> dict:
    """检索 + 引用：返回命中、接地率、是否应拒答。"""
    searcher = searcher or get_searcher()
    hits = searcher.search(query, top_k=top_k)
    total = sum(h.citations_total for h in hits)
    ok = sum(h.citations_ok for h in hits)
    strict = sum(h.citations_strict for h in hits)
    best_support = max((h.term_support for h in hits), default=0.0)
    return {
        "query": query,
        "corpus": searcher.corpus_summary(),
        "hits": [h.to_dict() for h in hits],
        "citations": {"total": total, "ok": ok, "strict": strict,
                      "rate": round(ok / total, 3) if total else None,
                      "strict_rate": round(strict / total, 3) if total else None},
        "grounding_rate": round(ok / total, 3) if total else None,
        "strict_verbatim_rate": round(strict / total, 3) if total else None,
        "min_term_support": MIN_TERM_SUPPORT,
        "best_term_support": round(best_support, 3),
        # 无命中 / 查询词在证据里支持不足 = 语料未覆盖；有命中但没有一条词法接地 = 也不该硬答。
        "abstained": (not hits) or best_support < MIN_TERM_SUPPORT
                     or (not any(h.grounded for h in hits)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="理赔 LLM-Wiki 检索（BM25+RRF，含 raw 级引用核查）")
    parser.add_argument("query", help="查询文本")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args(argv)

    result = retrieve(args.query, top_k=args.top_k)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    corpus = result["corpus"]
    print(f"语料：{corpus['pages']} 页 / {corpus['chars']} 字符 "
          f"（{corpus['by_type']}，sha256:{corpus['content_sha256']}）")
    if result["abstained"]:
        print("判定：依据不足（语料未覆盖该问题）")
    for i, hit in enumerate(result["hits"], start=1):
        print(f"\n[{i}] {hit['anchor']}  score={hit['score']}  type={hit['type']}")
        print(f"    {hit['span']}")
        print(f"    引用接地：{hit['citations_ok']}/{hit['citations_total']}"
              f"（逐字级 {hit['citations_strict']}/{hit['citations_total']}，"
              f"查询词支持 {hit['term_support']}）")
    print(f"\n引用接地率：{result['grounding_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
