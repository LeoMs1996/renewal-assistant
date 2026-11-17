"""条款知识检索（wiki/ → LLM-Wiki 模式）。

2026-11-13 基线改造 + 2026-11-17 二次整改（详见 reviews/knowledge.md）：

1. **LLM-Wiki 结构**（Karpathy 2026-04 idea file，检索 2026-11-17）：
   `wiki/index.md` 为内容目录（一句话摘要 + 标签 + 互链）、`wiki/log.md` 为操作账本，
   条目带 summary/tags/related/章节锚点 —— 检索因此可以「先读目录定位、再读章节」。
2. **三通道混合检索 + RRF(k=60)**：字面二元组通道（精确字面）、索引通道
   （title+summary+tags+related+章节标题，等价于字段加权的轻量 BM25F）、词级通道
   （英文/数字词 + 中文整段）。融合只用排名，免分数归一化。
3. **层级检索 navigate()**：index 通道先召回候选页（目录级），再在候选内用正文通道
   钻取排序；候选为空时回退全通道 RRF —— 对齐 gist 的 Query 顺序。
4. **引用溯源到章节/字面片段**（citation grounding）：`span_citation()` 给出
   `wiki_id#章节` 锚点 + 正文逐字片段；`verify_citations()` 做词法级支撑核查
   （命中条目正文须含 query 关键词），并给出 evidence_coverage，
   防「逐字但不对题」的引用（TRACE 2026 / CiteAnchor 2026 的字段级核查口径）。

SPEC §5 retrieval output 必含字段 [{wiki_id, source, version, score}]；
excerpt/grounding/anchor 信息仅供上层组 prompt 与轨迹节点详情，不写入 retrieval 事件 output。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # 允许依赖未装时优雅降级
    BM25Okapi = None

_FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SENT_END = "。！？；\n"

# 混合检索通道（顺序影响 RRF 并列时的稳定性，不影响权重——RRF 只用排名）
DEFAULT_CHANNELS: tuple[str, ...] = ("bigram", "index", "word")
CHANNEL_TOP_N = 10      # 每通道进入融合的候选数
NAV_CANDIDATES = 5      # 层级检索：目录通道先放行的候选页数


@dataclass
class WikiEntry:
    wiki_id: str
    version: str
    effective_date: str
    source: str
    title: str
    body: str
    path: Path = field(repr=False, default_factory=Path)
    summary: str = ""
    tags: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    category: str = ""

    @property
    def sections(self) -> list[tuple[str, str]]:
        """`## 标题` 切分出的 (标题, 正文) 列表；无 `##` 时退化为 [(标题, body)]。"""
        marks = list(_HEADING_RE.finditer(self.body))
        if not marks:
            return [(self.title, self.body)]
        out: list[tuple[str, str]] = []
        for i, m in enumerate(marks):
            start = m.end()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(self.body)
            out.append((m.group(1).strip(), self.body[start:end].strip()))
        return out

    @property
    def wikilinks(self) -> tuple[str, ...]:
        """正文里的 [[wiki-id]] 交叉引用。"""
        return tuple(dict.fromkeys(_WIKILINK_RE.findall(self.body)))

    @property
    def index_field(self) -> str:
        """索引字段：目录级信息 + 章节标题（字段加权的来源，LLM-Wiki 的 index 等价物）。"""
        parts = [self.title, self.summary, " ".join(self.tags),
                 " ".join(self.related), self.category]
        parts += [heading for heading, _ in self.sections]
        return "\n".join(p for p in parts if p)

    @property
    def tokens(self) -> list[str]:
        return _tokenize_bigram(self.title + "\n" + self.body) + \
            _tokenize_word(self.title + "\n" + self.body)


def _tokenize_bigram(text: str) -> list[str]:
    """二元组通道：中文按字符二元组（+单字），英文/数字按词（精确字面匹配）。"""
    tokens: list[str] = []
    buf: list[str] = []
    word: list[str] = []
    for ch in text.lower():
        if _CJK_RE.match(ch):
            if word:
                tokens.extend(word)
                word = []
            buf.append(ch)
        elif ch.isalnum():
            if buf:
                tokens.extend(_bigrams(buf))
                buf = []
            word.append(ch)
        else:
            if buf:
                tokens.extend(_bigrams(buf))
                buf = []
            if word:
                tokens.extend(word)
                word = []
    if buf:
        tokens.extend(_bigrams(buf))
    if word:
        tokens.extend(word)
    return tokens


def _tokenize_word(text: str) -> list[str]:
    """词级通道：英文/数字词 + 中文连续段整串（与二元组通道形成粒度差异，供 RRF 融合）。"""
    words = re.findall(r"[a-z0-9]+", text.lower())
    for seg in re.split(r"[^\u4e00-\u9fff]+", text):
        if len(seg) >= 2:
            words.append(seg)
    return words


def tokenize(text: str) -> list[str]:
    """兼容入口：双通道词表之和。"""
    return _tokenize_bigram(text) + _tokenize_word(text)


def _bigrams(chars: list[str]) -> list[str]:
    out = list(chars)  # 单字
    out += [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
    return out


def _split_meta(values: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in values.split(",") if v.strip())


def _parse_entry(path: Path) -> WikiEntry | None:
    text = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(text)
    meta: dict[str, str] = {}
    body = text
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = text[m.end():]
    if "id" not in meta:
        return None
    title = body.lstrip().splitlines()[0].lstrip("# ").strip() if body.strip() else ""
    return WikiEntry(
        wiki_id=meta["id"],
        version=meta.get("version", ""),
        effective_date=meta.get("effective_date", ""),
        source=meta.get("source", ""),
        title=title,
        body=body.strip(),
        path=path,
        summary=meta.get("summary", ""),
        tags=_split_meta(meta.get("tags", "")),
        related=_split_meta(meta.get("related", "")),
        category=meta.get("category", ""),
    )


RRF_K = 60  # Cormack et al. SIGIR 2009；2026 生产实现默认值（见 reviews/knowledge.md §2）


def _rrf_fuse(ranked_lists: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal Rank Fusion：score(d)=Σ 1/(k+rank)。只用排名不用原始分，免归一化。"""
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, idx in enumerate(lst, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return scores


class WikiSearch:
    def __init__(self, wiki_dir: Path | None = None,
                 channels: tuple[str, ...] = DEFAULT_CHANNELS):
        self.wiki_dir = wiki_dir or config.WIKI_DIR
        self.channels = channels
        self.entries: list[WikiEntry] = []
        self._index: dict[str, object] = {}   # channel -> BM25Okapi
        self.last_diagnostics: dict[str, list[str]] = {}
        self._load()

    # -- 装载 ---------------------------------------------------------------
    def _load(self) -> None:
        for path in sorted(self.wiki_dir.glob("*.md")):
            if path.name in ("index.md", "log.md"):   # 导航文件不是知识条目
                continue
            entry = _parse_entry(path)
            if entry:
                self.entries.append(entry)
        if BM25Okapi is None or not self.entries:
            return
        corpora = {
            "bigram": [_tokenize_bigram(e.title + "\n" + e.body) for e in self.entries],
            "index": [_tokenize_bigram(e.index_field) or ["∅"] for e in self.entries],
            "word": [_tokenize_word(e.title + "\n" + e.body) for e in self.entries],
        }
        for name in self.channels:
            docs = corpora.get(name)
            if docs:
                self._index[name] = BM25Okapi(docs)

    @property
    def available(self) -> bool:
        return bool(self.entries) and bool(self._index)

    @property
    def total_chars(self) -> int:
        """全量语料字符数（LLM-Wiki 暴力上下文预算判断）。"""
        return sum(len(e.body) for e in self.entries)

    # -- 检索 ---------------------------------------------------------------
    def _rankings(self, query: str) -> dict[str, list[int]]:
        """每通道各自召回 Top-N（只保留正分），返回 {通道: [doc_idx...]}。"""
        q_tokens = {
            "bigram": _tokenize_bigram(query),
            "index": _tokenize_bigram(query),
            "word": _tokenize_word(query),
        }
        out: dict[str, list[int]] = {}
        for name, bm25 in self._index.items():
            q = q_tokens.get(name) or []
            if not q:
                out[name] = []
                continue
            scores = bm25.get_scores(q)
            ranked = sorted(range(len(self.entries)), key=lambda i: scores[i], reverse=True)
            out[name] = [i for i in ranked if scores[i] > 0][:CHANNEL_TOP_N]
        self.last_diagnostics = {
            name: [self.entries[i].wiki_id for i in idxs] for name, idxs in out.items()}
        return out

    def search_with_score(self, query: str, top_k: int = 3,
                          channels: tuple[str, ...] | None = None):
        """多通道 BM25 + RRF(k=60) 融合检索。返回 (entries, scores)。"""
        if not self.available:
            return [], []
        rankings = self._rankings(query)
        use = channels or self.channels
        fused = _rrf_fuse([rankings.get(c, []) for c in use])
        top = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [self.entries[i] for i, _ in top], [float(s) for _, s in top]

    def navigate(self, query: str, top_k: int = 3):
        """层级检索：index 通道先定位候选页，再在候选内用正文通道钻取。

        对齐 Karpathy gist 的 Query 顺序（读 index → 钻取页面 → 必要时回退混合检索）。
        候选为空（目录字段无命中）时回退全通道 RRF，避免目录召回不全导致漏检。
        """
        if not self.available:
            return [], []
        rankings = self._rankings(query)
        candidates = rankings.get("index", [])[:NAV_CANDIDATES]
        if not candidates or "bigram" not in self._index:
            return self.search_with_score(query, top_k)
        scores = self._index["bigram"].get_scores(_tokenize_bigram(query))
        ranked = sorted((i for i in candidates if scores[i] > 0),
                        key=lambda i: scores[i], reverse=True)[:top_k]
        if not ranked:
            return self.search_with_score(query, top_k)
        return [self.entries[i] for i in ranked], \
            [1.0 / (RRF_K + r) for r in range(1, len(ranked) + 1)]


def hits_for_trace(entries: list[WikiEntry], scores: list[float]) -> list[dict]:
    """轨迹 retrieval 事件 output：严格 [{wiki_id, source, version, score}]（SPEC §5）。"""
    return [
        {"wiki_id": e.wiki_id, "source": e.source, "version": e.version, "score": round(s, 4)}
        for e, s in zip(entries, scores, strict=False)
    ]


def _content_terms(query: str) -> list[str]:
    """查询内容词：二元组/单字（长度≥2）+ 英文数字词，去重保序。"""
    terms = [t for t in _tokenize_bigram(query) if len(t) >= 2]
    terms += [t for t in _tokenize_word(query) if len(t) >= 2]
    return list(dict.fromkeys(terms))


def section_for(entry: WikiEntry, query: str) -> str:
    """命中最强的章节标题（引用锚点用）：章节内命中词最多者胜，平票取靠前章节。"""
    terms = [t for t in _content_terms(query) if t in entry.body]
    if not terms:
        return ""
    best, best_hits = "", 0
    for heading, text in entry.sections:
        hits = sum(1 for t in terms if t in text or t in heading)
        if hits > best_hits:
            best, best_hits = heading, hits
    return best


def span_citation(entry: WikiEntry, query: str = "", width: int = 160) -> dict:
    """章节级引用凭据：锚点 + 正文逐字片段（可回溯、可校验 verbatim）。"""
    heading = section_for(entry, query)
    span = excerpt(entry, width, query)
    return {
        "wiki_id": entry.wiki_id,
        "anchor": f"{entry.wiki_id}#{heading}" if heading else entry.wiki_id,
        "section": heading,
        "span": span,
        "verbatim": span.strip("…") in entry.body,
    }


def excerpt(entry: WikiEntry, width: int = 160, query: str = "") -> str:
    """截取正文；给 query 时定位命中词段，并向句子/行边界扩展（citation grounding）。

    返回值始终是正文的**逐字子串**（两端可能带省略号），供上层组 prompt 与引用回溯。
    """
    body = entry.body
    if query:
        heading = section_for(entry, query)
        seg_start, seg_text = 0, body
        if heading:
            pos = body.find("## " + heading)
            if pos >= 0:
                seg_start, seg_text = pos, body[pos:]
    else:
        seg_text, seg_start = body, 0

    if query and seg_text:
        hits = [t for t in _content_terms(query) if t in seg_text]
        if hits:
            term = min(hits, key=lambda t: seg_text.find(t))
            pos = seg_text.find(term)
            start = max(0, pos - width // 3)
            end = min(len(seg_text), start + width)
            # 向句子边界微调（最多放宽 40 字符），保证摘录读起来是完整句子
            for _ in range(40):
                if start > 0 and seg_text[start - 1] not in _SENT_END:
                    start -= 1
                else:
                    break
            for _ in range(40):
                if end < len(seg_text) and seg_text[end - 1] not in _SENT_END:
                    end += 1
                else:
                    break
            span = body[seg_start + start:seg_start + end]
            head = "…" if seg_start + start > 0 else ""
            tail = "…" if seg_start + end < len(body) else ""
            return f"{head}{span}{tail}"
    return (body[:width] + "…") if len(body) > width else body


def verify_citations(query: str, entries: list[WikiEntry]) -> list[dict]:
    """词法级引用核查（entailment-lite）：命中条目正文/标题须实际包含 query 关键词。

    返回 [{wiki_id, grounded(bool), matched_terms, anchor, section, coverage,
    verbatim}]。完全无词面重叠的引用判定为未接地（ALCE 式引用支撑校验的无模型近似）。
    coverage = 命中内容词 / **语料内可命中的**查询内容词（分母只算语料里真的出现过的词，
    否则中文二元组跨词边界（如「险包」）会系统性地把覆盖率压低），
    用于识别「逐字但不对题」的引用。详 reviews/knowledge.md。
    """
    terms = _content_terms(query)
    vocab = "\n".join(e.title + "\n" + e.body for e in entries)
    in_corpus = [t for t in terms if t in vocab]
    out: list[dict] = []
    for e in entries:
        matched = [t for t in in_corpus if t in e.body or t in e.title]
        span = span_citation(e, query)
        out.append({
            "wiki_id": e.wiki_id,
            "grounded": bool(matched),
            "matched_terms": matched[:5],
            "anchor": span["anchor"],
            "section": span["section"],
            "verbatim": span["verbatim"],
            "coverage": (round(len(matched) / len(in_corpus), 3)
                         if in_corpus else 0.0),
        })
    return out


def llm_wiki_context(entries: list[WikiEntry], char_budget: int = 24000) -> str:
    """LLM-Wiki 全量上下文（Karpathy 2026-04：小语料下暴力上下文优于切片检索）。

    语料在预算内时输出全部条目（带 [wiki_id] 锚点标题），供 prompt 注入；
    超出预算即截断，上层按是否覆盖全部条目判断回退 RRF Top-K 摘录模式。
    末尾附 index.md 目录（先读目录定位、再读条目的导航层），不改变条目块格式，
    保证「全量条目是否都进上下文」的判据不受导航层影响。
    """
    parts: list[str] = []
    used = 0
    for e in entries:
        block = f"[{e.wiki_id}] {e.title}（{e.source} {e.version}）\n{e.body}"
        if used + len(block) > char_budget:
            break
        parts.append(block)
        used += len(block)
    context = "\n\n".join(parts)
    nav = wiki_nav(entries)
    if nav and used + len(nav) <= char_budget:
        context += "\n\n---\n【index.md 目录｜先看目录定位 wiki_id，再看上面条目原文】\n" + nav
    return context


def wiki_nav(entries: list[WikiEntry]) -> str:
    """紧凑目录层（index.md 的等价物）：wiki_id | 摘要 | 章节锚点。"""
    rows = []
    for e in entries:
        anchors = "／".join(h for h, _ in e.sections)
        rows.append(f"- [{e.wiki_id}] {e.title}（{e.version}）｜{e.summary}｜章节：{anchors}")
    return "\n".join(rows)


_instance: WikiSearch | None = None


def get_searcher() -> WikiSearch:
    global _instance
    if _instance is None:
        _instance = WikiSearch()
    return _instance
