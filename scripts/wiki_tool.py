#!/usr/bin/env python
"""wiki/ 维护工具：LLM-Wiki 模式的 index / log / lint 三个操作落地。

模式来源（2026-11 检索，见 reviews/knowledge.md §2）：
  - Karpathy, "LLM Wiki" idea file（primary source, 2026-04，
    https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f ，检索 2026-11-17）：
    · 三层架构：raw sources / wiki（LLM 维护）/ schema（约定文档）
    · 三操作：Ingest / Query / **Lint**
    · 两个导航文件：`index.md`（内容目录：链接 + 一句话摘要 + 元数据）、
      `log.md`（只追加的时间账本，`## [YYYY-MM-DD] action | title` 前缀可被 grep 解析）
    · Query 顺序：先读 index → 定位页面 → 钻取条目 → 语料变大再回退混合检索
  - 本项目语料 8 条 / ~8KB，正处在「index 足够、无需向量库」的规模区间。

用法：
    python scripts/wiki_tool.py index            # 重新生成 wiki/index.md
    python scripts/wiki_tool.py lint             # 健康检查（非 0 退出码 = 有 error）
    python scripts/wiki_tool.py log "lint | 说明"  # 追加一条 log.md 记录

只读写 wiki/ 目录；不修改条目正文，正文改动由人/LLM 按 schema（wiki/README.md）进行。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import wiki_search  # noqa: E402

WIKI_DIR = ROOT / "wiki"
INDEX_FILE = WIKI_DIR / "index.md"
LOG_FILE = WIKI_DIR / "log.md"

REQUIRED_FIELDS = ("id", "version", "effective_date", "source", "summary", "tags", "category")


def load_entries() -> list[wiki_search.WikiEntry]:
    return wiki_search.WikiSearch(WIKI_DIR).entries


def render_index(entries: list[wiki_search.WikiEntry]) -> str:
    """按 category 分组的目录：链接 + 一句话摘要 + 版本 + 标签（不含时间戳，保证幂等）。"""
    by_cat: dict[str, list[wiki_search.WikiEntry]] = {}
    for e in entries:
        by_cat.setdefault(e.category or "未分类", []).append(e)

    total_chars = sum(len(e.body) for e in entries)
    out = [
        "# 条款 Wiki 索引（index.md）",
        "",
        "> 本文件由 `python scripts/wiki_tool.py index` 生成，**勿手改**。",
        "> 模式：LLM-Wiki（Karpathy 2026-04，见 `wiki/README.md` 与本文件末尾出处）。",
        f"> 条目数：{len(entries)} · 正文语料：{total_chars} 字符 · "
        "章节锚点格式：`wiki_id#章节标题`。",
        "",
        "**查询顺序**：先读本目录定位 `wiki_id` → 读条目对应章节 → 语料增长到"
        " index 不够用时再回退 `server/wiki_search.py` 的 RRF 混合检索。",
        "",
        "| wiki_id | 标题 | 一句话摘要 | 版本 | 标签 |",
        "|---|---|---|---|---|",
    ]
    for cat in sorted(by_cat):
        rows = sorted(by_cat[cat], key=lambda e: e.wiki_id)
        out.append(f"| **{cat}** | | | | |")
        for e in rows:
            out.append(
                f"| [`{e.wiki_id}`]({e.path.name}) | {e.title} | {e.summary} | "
                f"{e.version} | {', '.join(e.tags)} |"
            )
    out += ["", "## 互链图（related）", ""]
    for e in sorted(entries, key=lambda x: x.wiki_id):
        links = ", ".join(f"`{r}`" for r in e.related) or "—"
        out.append(f"- `{e.wiki_id}` → {links}")
    out += [
        "",
        "---",
        "",
        "出处：Karpathy《llm-wiki.md》idea file（2026-04；检索 2026-11-17）"
        "<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>。",
        "",
    ]
    return "\n".join(out)


def lint(entries: list[wiki_search.WikiEntry]) -> tuple[list[str], list[str]]:
    """健康检查（对齐 gist 的 Lint 操作：孤儿页/缺失交叉引用/过期声明/索引新鲜度）。"""
    errors: list[str] = []
    warns: list[str] = []
    ids = {e.wiki_id for e in entries}

    for e in entries:
        raw = e.path.read_text(encoding="utf-8")
        head = raw.split("\n---\n", 1)[0]
        present = {ln.split(":", 1)[0].strip() for ln in head.splitlines() if ":" in ln}
        missing = [f for f in REQUIRED_FIELDS if f not in present]
        if missing:
            errors.append(f"{e.path.name}: front-matter 缺字段 {missing}")
        if not e.summary:
            errors.append(f"{e.path.name}: summary 为空（index 一句话摘要不可缺）")
        if not e.sections:
            warns.append(f"{e.path.name}: 无 `##` 章节，锚点引用退化为整条引用")
        seen: set[str] = set()
        for heading, _ in e.sections:
            if heading in seen:
                errors.append(f"{e.path.name}: 章节标题重复 `{heading}`（锚点会冲突）")
            seen.add(heading)
        for r in e.related:
            if r not in ids:
                errors.append(f"{e.path.name}: related 指向不存在的条目 `{r}`")
            elif e.wiki_id not in next(x for x in entries if x.wiki_id == r).related:
                errors.append(f"{e.path.name}: 交叉引用非双向 `{r}`（应在对方 related 里回指）")
        for target in e.wikilinks:
            if target not in ids:
                errors.append(f"{e.path.name}: 正文 [[{target}]] 指向不存在的条目")
        # 过期声明（gist: stale claims that newer sources have superseded）
        try:
            years = (date.today() - date.fromisoformat(e.effective_date)).days / 365.25
            if years > 2:
                warns.append(
                    f"{e.path.name}: effective_date={e.effective_date} 已 {years:.1f} 年，"
                    "需复核是否被新条款替代（stale claim）"
                )
        except ValueError:
            errors.append(f"{e.path.name}: effective_date 不是 ISO 日期: {e.effective_date!r}")

    inbound = {e.wiki_id: 0 for e in entries}
    for e in entries:
        for r in list(e.related) + list(e.wikilinks):
            if r in inbound:
                inbound[r] += 1
    for wid, n in inbound.items():
        if n == 0:
            warns.append(f"{wid}: 孤儿页（无任何入链，索引/图视图里不可达）")

    if INDEX_FILE.exists():
        if INDEX_FILE.read_text(encoding="utf-8") != render_index(entries):
            errors.append("wiki/index.md 与条目不一致（请运行 `python scripts/wiki_tool.py index`）")
    else:
        errors.append("wiki/index.md 缺失（LLM-Wiki 导航入口不存在）")
    if not LOG_FILE.exists():
        warns.append("wiki/log.md 缺失（无操作账本）")
    else:
        lines = [ln for ln in LOG_FILE.read_text(encoding="utf-8").splitlines()
                 if ln.startswith("## [")]
        if not lines:
            warns.append("wiki/log.md 无 `## [YYYY-MM-DD] ...` 记录")
    return errors, warns


def append_log(action: str) -> None:
    today = date.today().isoformat()
    entry = f"## [{today}] {action}\n"
    if LOG_FILE.exists():
        text = LOG_FILE.read_text(encoding="utf-8")
    else:
        text = "# Wiki 操作账本（log.md）\n\n> 只追加；前缀 `## [YYYY-MM-DD] action | 标题` "
        text += "可被 `grep \"^## \\[\"` 解析（Karpathy 2026-04 约定）。\n\n"
    LOG_FILE.write_text(text.rstrip() + "\n\n" + entry, encoding="utf-8")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "lint"
    entries = load_entries()
    if cmd == "index":
        INDEX_FILE.write_text(render_index(entries), encoding="utf-8")
        print(f"index.md 已生成：{len(entries)} 条目 → {INDEX_FILE}")
        return 0
    if cmd == "log":
        append_log(" ".join(argv[2:]) or "lint | 手工记录")
        print("log.md 已追加")
        return 0
    if cmd == "lint":
        errors, warns = lint(entries)
        for w in warns:
            print(f"WARN  {w}")
        for e in errors:
            print(f"ERROR {e}")
        print(f"lint: {len(errors)} error / {len(warns)} warn / {len(entries)} 条目")
        return 1 if errors else 0
    print(f"未知命令 {cmd!r}，可用：index | lint | log", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
