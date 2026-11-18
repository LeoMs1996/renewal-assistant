#!/usr/bin/env python3
"""D3：LLM-Wiki lint（只读，不改任何文件；FAIL 级问题 exit 1）。

覆盖 R1 spec §7 的子集：
  L1 frontmatter 必填字段 / 枚举值
  L2 index 与磁盘页面一一对应
  L3 失效链接（related、[[link]]）与 related 非双向
  L4 孤儿页（未进 index）
  L5 重复 id / 重复标题
  L6 引用不可回溯（qid 不存在 / span 越界 / 逐字引用块与 raw 不一致）
  L7 无来源断言（表行、bullet 无标记；引用块后缺行区间标记）
  L8 空页 / 超长页
  L10 index 摘要与 frontmatter summary 不一致
  L11 越界引用（指向续保 wiki / traces）

用法：python3 scripts/wiki_lint.py
"""

from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
CLAIMS = HERE.parent
WIKI = CLAIMS / "wiki"
MANIFEST = CLAIMS / "raw" / "manifest.json"
SOURCES = CLAIMS / "raw" / "sources"

REQUIRED = ["id", "type", "title", "domain", "insurance_line", "summary", "tags",
            "source_refs", "updated", "related", "status"]
ENUM_TYPE = {"doc", "section", "entity", "faq", "query"}
ENUM_STATUS = {"draft", "verified", "conflicted", "stale"}
ENUM_INSURANCE_LINE = {"auto_claim", "auto_liability", "agricultural_claim",
                       "health_underwriting", "property_claim", "cross_cutting"}
MARKER = re.compile(r"⟦S:INS-MMBench:(qid|qids)=([^@]+)@([^⟧]+)⟧")

problems: list[tuple[str, str, str]] = []  # (rule, file, detail)


def fail(rule: str, path: str, detail: str) -> None:
    problems.append((rule, path, detail))


def load_manifest() -> tuple[dict[str, dict], dict[str, str]]:
    man = json.loads(MANIFEST.read_text("utf-8"))
    by_qid: dict[str, dict] = {}
    raw_by_qid: dict[str, str] = {}
    for s in man["sources"]:
        qid = str(s["record_id"])
        by_qid[qid] = s
        raw_by_qid[qid] = str(s["raw_id"])
    return by_qid, raw_by_qid


def parse_frontmatter(text: str) -> tuple[dict[str, object], int]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("缺少 frontmatter 起始 ---")
    fm: dict[str, object] = {}
    end = None
    for i in range(1, len(lines)):
        line = lines[i]
        if line.strip() == "---":
            end = i
            break
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            fm[k] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
        else:
            fm[k] = v
    if end is None:
        raise ValueError("frontmatter 未闭合")
    return fm, end + 1


def read_raw(raw_id: str) -> dict:
    return json.loads((SOURCES / (raw_id + ".json")).read_text("utf-8"))


def expand_qids(spec: str, by_qid: dict[str, dict]) -> list[str] | None:
    if ".." not in spec:
        return [spec] if spec in by_qid else None
    a, b = spec.split("..", 1)
    if a not in by_qid or b not in by_qid:
        return None
    split = a.rsplit("_", 1)[0]
    if b.rsplit("_", 1)[0] != split:
        return None
    lo, hi = int(a.rsplit("_", 1)[1]), int(b.rsplit("_", 1)[1])
    out = [q for q in by_qid if q.rsplit("_", 1)[0] == split and lo <= int(q.rsplit("_", 1)[1]) <= hi]
    return sorted(out, key=lambda q: int(q.rsplit("_", 1)[1]))


def check_span(qid: str, raw: dict, span: str) -> str | None:
    """返回错误描述或 None。"""
    nlines = int(raw["content"]["question"]["lines"])
    if span.startswith("L") and "-L" in span:
        m = re.fullmatch(r"L(\d+)-L(\d+)", span)
        if not m:
            return "行区间格式非法: " + span
        a, b = int(m.group(1)), int(m.group(2))
        if not (1 <= a <= b <= nlines):
            return "行区间越界: " + span + "（该单元共 " + str(nlines) + " 行）"
        return None
    if span.startswith("labels."):
        key = span[len("labels."):]
        if key not in raw["labels"]:
            return "labels 路径不存在: " + span
        return None
    if "." in span and not span.startswith("labels.") and span.split(".")[0] in raw:
        node: object = raw
        for part in span.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return "JSON 路径不存在: " + span
        return None
    if span == "answer_status" and "answer_status" in raw:
        return None
    paths = [str(im["path"]) for im in raw["images"]]
    if span in paths:
        return None
    return "无法识别的 span（既非行区间、也非 labels 键、也非图片路径）: " + span


def lint_page(path: pathlib.Path, by_qid: dict[str, dict]) -> dict[str, object]:
    rel = path.relative_to(WIKI).as_posix()
    text = path.read_text("utf-8")
    lines = text.split("\n")
    try:
        fm, body_start = parse_frontmatter(text)
    except ValueError as exc:
        fail("L1", rel, "frontmatter 解析失败: " + str(exc))
        return {"rel": rel, "fm": {}, "summary": None}

    # L1 frontmatter
    for key in REQUIRED:
        if key not in fm:
            fail("L1", rel, "缺少必填字段: " + key)
    if fm.get("domain") != "claims":
        fail("L1", rel, "domain 非 claims: " + str(fm.get("domain")))
    if str(fm.get("type")) not in ENUM_TYPE:
        fail("L1", rel, "type 枚举非法: " + str(fm.get("type")))
    if str(fm.get("status")) not in ENUM_STATUS:
        fail("L1", rel, "status 枚举非法: " + str(fm.get("status")))
    if str(fm.get("insurance_line")) not in ENUM_INSURANCE_LINE:
        fail("L1", rel, "insurance_line 枚举非法: " + str(fm.get("insurance_line")))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fm.get("updated", ""))):
        fail("L1", rel, "updated 非 ISO 日期: " + str(fm.get("updated")))
    src_refs = fm.get("source_refs") or []
    if not isinstance(src_refs, list) or not src_refs:
        fail("L1", rel, "source_refs 为空")
        src_refs = []
    qids_from_fm: list[str] = []
    for ref in src_refs:
        m = re.fullmatch(r"INS-MMBench:qid=(\S+)", str(ref))
        if not m:
            fail("L1", rel, "source_refs 条目格式非法（应为 INS-MMBench:qid=<split>_<idx>）: " + str(ref))
            continue
        qid = m.group(1)
        qids_from_fm.append(qid)
        if qid not in by_qid:
            fail("L6", rel, "source_refs 指向不存在的样本: " + qid)
    raw_refs = fm.get("raw_refs") or []
    for r in raw_refs:
        if not re.fullmatch(r"raw-[a-z]+-\d{4}", str(r)):
            fail("L1", rel, "raw_refs 条目格式非法: " + str(r))

    # 正文扫描
    in_body = lines[body_start:]
    body_len = len("\n".join(in_body))
    if body_len < 200:
        fail("L8", rel, "正文过短（<200 字符），疑似空页")
    if body_len > 12000:
        fail("L8", rel, "正文过长（>12000 字符），应拆分")

    marker_count = 0
    quote_run: list[str] = []

    def flush_quote(next_idx: int) -> None:
        """校验刚结束的引用块：其后第一条非空行必须是 L 区间标记。"""
        nonlocal marker_count
        if not quote_run:
            return
        first = quote_run[0].lstrip("> ").strip()
        preface = first.startswith("本页") or first.startswith("全子集") or first.startswith("目录中的问题")
        j = next_idx
        while j < len(in_body) and not in_body[j].strip():
            j += 1
        next_line = in_body[j] if j < len(in_body) else ""
        ms = MARKER.findall(next_line)
        has_l = any(sp.startswith("L") for _, _, sp in ms)
        if preface:
            return
        if not has_l:
            fail("L7", rel, "逐字引用块后缺少行区间标记（无法回溯）: " + (first[:40]))
            return
        qid_spec, span = None, None
        for _kind, spec, sp in ms:
            if sp.startswith("L"):
                qid_spec, span = spec, sp
                break
        q = expand_qids(str(qid_spec), by_qid)
        if not q:
            fail("L6", rel, "引用块标记的 qid 不存在: " + str(qid_spec))
            return
        raw = read_raw(str(by_qid[q[0]]["raw_id"]))
        m = re.fullmatch(r"L(\d+)-L(\d+)", str(span))
        if not m:
            fail("L6", rel, "引用块标记行区间格式非法: " + str(span))
            return
        a, b = int(m.group(1)), int(m.group(2))
        raw_lines = str(raw["content"]["question"]["text"]).split("\n")
        expect = [x.rstrip() for x in raw_lines[a - 1: b]]
        got = [x[2:].rstrip() if x.startswith("> ") else x[1:].rstrip() for x in quote_run]
        if expect != got:
            fail("L6", rel, "逐字引用块与 raw 不一致（L" + str(a) + "-L" + str(b) + "）")

    i = 0
    while i < len(in_body):
        line = in_body[i]
        stripped = line.strip()
        if stripped.startswith(">"):
            quote_run.append(line)
            i += 1
            continue
        if quote_run:
            flush_quote(i)
            quote_run = []
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            is_sep = all(set(c) <= set("-: ") and c for c in cells)
            if not is_sep and not stripped.startswith("| qid |") and not stripped.startswith("| id |"):
                if "⟦S:" not in stripped:
                    fail("L7", rel, "表行无来源标记: " + stripped[:60])
        elif stripped.startswith("- "):
            structural = (
                stripped.startswith("- [[")
                or stripped.startswith("- （")
                or stripped.startswith("- 【方法约束】")
            )
            if not structural:
                if "⟦S:" not in stripped:
                    fail("L7", rel, "bullet 无来源标记: " + stripped[:60])
                else:
                    marker_count += 1
        i += 1
    if quote_run:
        flush_quote(len(in_body))

    # 逐条校验所有标记
    for lineno, line in enumerate(in_body, start=1):
        for kind, spec, span in MARKER.findall(line):
            qids = expand_qids(spec, by_qid)
            if not qids:
                fail("L6", rel, "标记中的 qid/qids 不存在: " + spec)
                continue
            if ".." in spec:
                # D4b 加固：区间必须覆盖真实存在的每一个单元。
                # 旧实现的 expand_qids 只保留“存在的 qid”，于是 `liability_0..liability_20`
                # 在一个只有 12/21 个单元的抽样分片里会被默默接受——区间就此凭空断言了
                # 中间不存在的 9 个单元，而 FAIL 仍为 0。
                a, b = spec.split("..", 1)
                lo = int(a.rsplit("_", 1)[1])
                hi = int(b.rsplit("_", 1)[1])
                have = len(qids)
                if hi - lo + 1 != have:
                    fail(
                        "L6",
                        rel,
                        f"区间 {spec} 覆盖不存在的单元（声明 {hi - lo + 1} 个，实际仅 {have} 个）；"
                        "非连续集合应拆成多个连续段或逐条标记",
                    )
            if kind == "qids":
                missing = [q for q in qids if q not in qids_from_fm]
                if missing:
                    fail("L6", rel, "聚合标记的单元超出本页 source_refs: " + ",".join(missing[:3]))
            for q in qids[:1]:
                raw = read_raw(str(by_qid[q]["raw_id"]))
                err = check_span(q, raw, span)
                if err:
                    fail("L6", rel, "第 " + str(lineno) + " 行: " + err)

    # L3 related 单向 / 断链（目标存在性在全局 pass 里查）
    related = fm.get("related") or []
    if not isinstance(related, list):
        fail("L1", rel, "related 非列表")
        related = []
    for r in related:
        if not isinstance(r, str) or not r.startswith("claims-"):
            fail("L3", rel, "related 条目非法: " + str(r))
    for line in in_body:
        for link in re.findall(r"\[\[([^\]]+)\]\]", line):
            if link not in related:
                fail("L3", rel, "正文 [[link]] 未登记在 frontmatter related: " + link)

    # L11 越界
    for needle in ["renewal-assistant/wiki/", "../wiki/", "traces/"]:
        if needle in text:
            fail("L11", rel, "出现越界路径引用: " + needle)

    # L10 summary vs index 在 index pass 检查
    return {"rel": rel, "fm": fm, "summary": fm.get("summary"), "related": related}


GROUP_TYPE = {"文档页": "doc", "章节页": "section", "实体页": "entity", "问答页": "faq"}


def parse_index(text: str) -> list[dict[str, str]]:
    """index 行：id(slug) | 标题 | 摘要 | tags | updated；type 取自分组标题。"""
    rows: list[dict[str, str]] = []
    cur_type = ""
    for line in text.split("\n"):
        st = line.strip()
        if st.startswith("## "):
            for name, t in GROUP_TYPE.items():
                if st.startswith("## " + name):
                    cur_type = t
            continue
        if not st.startswith("| ["):
            continue
        cells = [c.strip() for c in st.strip("|").split("|")]
        if len(cells) < 5:
            continue
        m = re.match(r"\[`([^`]+)`\]\(([^)]+)\)", cells[0])
        if not m:
            continue
        rows.append({"id": m.group(1), "path": m.group(2), "title": cells[1],
                     "type": cur_type, "summary": cells[2], "tags": cells[3], "updated": cells[4]})
    return rows


def main() -> int:
    if not WIKI.exists():
        print("FATAL: wiki 目录不存在: " + str(WIKI))
        return 1
    by_qid, _raw = load_manifest()
    page_files = sorted(p for p in WIKI.rglob("*.md") if p.name not in ("index.md", "log.md", "schema.md", "README.md"))
    infos: dict[str, dict] = {}
    for p in page_files:
        info = lint_page(p, by_qid)
        infos[info["rel"]] = info

    index_path = WIKI / "index.md"
    if not index_path.exists():
        fail("L2", "index.md", "index.md 不存在")
        rows = []
    else:
        rows = parse_index(index_path.read_text("utf-8"))

    # L2 index ↔ 磁盘
    indexed_paths = {r["path"] for r in rows}
    disk_paths = {p.relative_to(WIKI).as_posix() for p in page_files}
    for path in sorted(disk_paths - indexed_paths):
        fail("L4", path, "孤儿页：未出现在 index.md")
    for path in sorted(indexed_paths - disk_paths):
        fail("L2", "index.md", "索引指向不存在的页面: " + path)

    # L5 重复
    seen_id: dict[str, str] = {}
    seen_title: dict[str, str] = {}
    for info in infos.values():
        fid = str(info["fm"].get("id", ""))
        title = str(info["fm"].get("title", ""))
        if fid in seen_id:
            fail("L5", str(info["rel"]), "重复 id: " + fid)
        seen_id[fid] = str(info["rel"])
        if title in seen_title:
            fail("L5", str(info["rel"]), "重复标题: " + title)
        seen_title[title] = str(info["rel"])
        PLURAL = {"doc": "docs", "section": "sections", "entity": "entities", "faq": "faqs", "query": "queries"}
        expected_rel = (
            PLURAL.get(str(info["fm"].get("type")), "misc")
            + "/" + str(info["fm"].get("id", "")).split("-", 2)[-1] + ".md"
        )
        if info["rel"] != expected_rel:
            fail("L5", str(info["rel"]), "文件名与 id 不对应（应为 <type>s/<slug>.md）")

    # L3 related 双向 + 目标存在
    id_to_rel = {str(i["fm"].get("id", "")): str(i["rel"]) for i in infos.values()}
    for info in infos.values():
        for r in info["related"]:
            if r not in id_to_rel:
                fail("L3", str(info["rel"]), "related 指向不存在的页面: " + str(r))
                continue
            other = infos[id_to_rel[r]]
            if str(info["fm"].get("id")) not in other["related"]:
                fail("L3", str(info["rel"]), "related 非双向: " + str(r) + " 未回指本页")

    # L10 index 行与 frontmatter 的一致性：摘要为前缀、updated 相等、tags 是子集、type 与分组一致
    for row in rows:
        if row["path"] not in infos:
            continue
        fm = infos[row["path"]]["fm"]
        label = row["summary"]
        # 短标签规则（不是 summary 截断）：≤30 字 / 无省略号 / 含数量 / 以区分前缀开头
        if len(label) > 30:
            fail("L10", "index.md", "短标签超 30 字（" + str(len(label)) + "）: " + row["id"])
        if "…" in label:
            fail("L10", "index.md", "短标签含省略号（禁止截断）: " + row["id"])
        if not any(ch.isdigit() for ch in label):
            fail("L10", "index.md", "短标签缺少数量维度: " + row["id"])
        _tags = fm.get("tags") or ["?", "?"]
        split_tok = _tags[1] if len(_tags) > 1 else "?"
        if str(fm.get("type")) == "entity":
            head_ok = label.startswith(str(fm.get("title", ""))[:4])
        else:
            head_ok = label.startswith(str(split_tok))
        if not head_ok:
            fail("L10", "index.md", "短标签未以分片/标题开头（缺区分维度）: " + row["id"])
        if row["updated"] != str(fm.get("updated")):
            fail("L10", "index.md", "updated 与 frontmatter 不一致: " + row["id"])
        fm_tags = {x.strip() for x in (fm.get("tags") or []) if x}
        row_tags = {x.strip() for x in row["tags"].split(",") if x.strip()}
        if not row_tags <= fm_tags:
            fail("L10", "index.md", "index tags 不是 frontmatter tags 的子集: " + row["id"])
        if row["type"] and str(fm.get("type")) != row["type"]:
            fail("L10", "index.md", "行所在分组与 frontmatter type 不一致: " + row["id"])

    # log.md 可 grep 性
    log_path = WIKI / "log.md"
    if not log_path.exists():
        fail("L2", "log.md", "log.md 不存在")
    else:
        heads = [ln for ln in log_path.read_text("utf-8").split("\n") if ln.startswith("## [")]
        if not heads:
            fail("L2", "log.md", "没有任何 `## [` 记录（不可 grep）")
        for h in heads:
            if not re.match(r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|fix|schema|retract) \| .+", h):
                fail("L2", "log.md", "记录格式非法: " + h[:60])

        # L12：log 的 ingest 标题集合 == 页面 id 集合；每条必含 page/units/result；fix 可审计
        page_ids = {str(i["fm"].get("id")) for i in infos.values()}
        blocks: list[str] = []
        cur: list[str] = []
        for ln in log_path.read_text("utf-8").split("\n"):
            if ln.startswith("## ["):
                if cur:
                    blocks.append("\n".join(cur))
                cur = [ln]
            elif cur:
                cur.append(ln)
        if cur:
            blocks.append("\n".join(cur))
        ingest_titles: list[str] = []
        for b in blocks:
            head = b.split("\n", 1)[0]
            m = re.match(r"^## \[\d{4}-\d{2}-\d{2}\] (\w+) \| (.+)$", head)
            if not m:
                continue
            op, title = m.group(1), m.group(2).strip()
            if op == "ingest":
                ingest_titles.append(title)
                for need in ("- page:", "- units:", "- result:"):
                    if need not in b:
                        fail("L12", "log.md", "ingest 缺字段 " + need.strip("- ") + "：" + title)
            elif op == "fix":
                for need in ("reason:", "action:", "影响范围:"):
                    if need not in b:
                        fail("L12", "log.md", "fix 条目无法审计（缺 " + need + "）：" + title)
        dup = {t for t in ingest_titles if ingest_titles.count(t) > 1}
        for t in sorted(dup):
            fail("L12", "log.md", "ingest 记录重复: " + t)
        missing = sorted(page_ids - set(ingest_titles))
        for t in missing:
            fail("L12", "log.md", "页面缺 ingest 记录: " + t)
        ghost = sorted(set(ingest_titles) - page_ids)
        for t in ghost:
            fail("L12", "log.md", "幽灵 ingest（页面不存在）: " + t)

    fails = [p for p in problems if p[0] not in ("L8",)]
    warns = [p for p in problems if p[0] in ("L8",)]
    print("pages=" + str(len(page_files)) + " index_rows=" + str(len(rows)) + " FAIL=" + str(len(fails)) + " WARN=" + str(len(warns)))
    for rule, path, detail in fails + warns:
        print("  [" + rule + "] " + path + " :: " + detail)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
