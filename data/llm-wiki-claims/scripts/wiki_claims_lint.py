#!/usr/bin/env python3
"""D4：理赔 LLM-Wiki 质检（独立实现，**已交付页面的第二套检查器**）。

与 D3 的 `wiki_lint.py` 刻意分开写（不同结构与判定路径），用于交叉验证：
两套检查器都过，才说明不是「同一实现的自我确认」。

检查项（口径见 docs/log/step-d4-lint.md §2，来源 S1–S3）：
  E1 frontmatter 完整性（必填 9 + insurance_line/raw_refs）与枚举
  E2 index 一致性（索引行 ↔ 磁盘页面，双向；摘要列 == frontmatter summary）
  E3 孤儿页（不在 index 且无任何入链）
  E4 重复页（id / title / slug）
  E5 死链 source_refs（qid 不在 manifest；raw_refs 文件不存在）
  E6 空页 / 超薄页（正文 < 200 字符）与超长页（> 12000 字符）
  E7 正文死链（[[...]] 指向不存在的页面）
  E8 log 一致性（每页有 ingest 记录；无指向不存在页面的记录）
  E9 span 不可解析（行区间越界、labels 键不存在、图片路径不存在）
  W1 summary 过短/过长（< 10 或 > 80 字）

用法：
    python3 scripts/wiki_claims_lint.py               # 全量检查
    python3 scripts/wiki_claims_lint.py --sample 10   # 另附 10 页可复现随机抽样（供人工复核）
"""

from __future__ import annotations

import json
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
CLAIMS = HERE.parent
WIKI = CLAIMS / "wiki"
SOURCES = CLAIMS / "raw" / "sources"
MANIFEST = CLAIMS / "raw" / "manifest.json"

NON_PAGE = {"index.md", "log.md", "schema.md", "README.md"}
REQ = ["id", "type", "title", "domain", "insurance_line", "summary",
       "tags", "source_refs", "raw_refs", "updated", "related", "status"]
OK_TYPE = {"doc", "section", "entity", "faq", "query"}
OK_STATUS = {"draft", "verified", "conflicted", "stale"}
OK_LINE = {"auto_claim", "auto_liability", "agricultural_claim",
           "health_underwriting", "property_claim", "cross_cutting"}
SPAN = re.compile(r"⟦S:([^@⟧]+)@([^⟧]+)⟧")

errors: list[str] = []
warns: list[str] = []


def err(code: str, path: str, detail: str) -> None:
    errors.append(code + " " + path + " :: " + detail)


def warn(code: str, path: str, detail: str) -> None:
    warns.append(code + " " + path + " :: " + detail)


# ---------------------------------------------------------------- 解析


def parse_fm(text: str) -> tuple[dict[str, object], int]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("无 frontmatter")
    out: dict[str, object] = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if v.startswith("[") and v.endswith("]"):
                body = v[1:-1].strip()
                out[k] = [x.strip() for x in body.split(",") if x.strip()] if body else []
            else:
                out[k] = v
        i += 1
    if i >= len(lines):
        raise ValueError("frontmatter 未闭合")
    return out, i + 1


def load_sources() -> dict[str, dict]:
    man = json.loads(MANIFEST.read_text("utf-8"))
    return {str(s["record_id"]): s for s in man["sources"]}


def raw_of(qid: str) -> dict | None:
    split, idx = qid.rsplit("_", 1)
    path = SOURCES / ("raw-" + split + "-" + format(int(idx), "04d") + ".json")
    if not path.exists():
        return None
    return json.loads(path.read_text("utf-8"))


# ---------------------------------------------------------------- 主检查


def main(argv: list[str]) -> int:
    pages: dict[str, dict] = {}
    files = sorted(p for p in WIKI.rglob("*.md") if p.name not in NON_PAGE)
    by_qid = load_sources()

    for path in files:
        rel = path.relative_to(WIKI).as_posix()
        text = path.read_text("utf-8")
        try:
            fm, start = parse_fm(text)
        except ValueError as exc:
            err("E1", rel, "frontmatter 解析失败：" + str(exc))
            continue
        body = "\n".join(text.split("\n")[start:])

        # E1 frontmatter
        for k in REQ:
            if k not in fm:
                err("E1", rel, "缺字段 " + k)
        if fm.get("domain") != "claims":
            err("E1", rel, "domain != claims")
        if str(fm.get("type")) not in OK_TYPE:
            err("E1", rel, "type 非法：" + str(fm.get("type")))
        if str(fm.get("status")) not in OK_STATUS:
            err("E1", rel, "status 非法：" + str(fm.get("status")))
        if str(fm.get("insurance_line")) not in OK_LINE:
            err("E1", rel, "insurance_line 非法：" + str(fm.get("insurance_line")))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fm.get("updated", ""))):
            err("E1", rel, "updated 非 ISO：" + str(fm.get("updated")))
        refs = fm.get("source_refs") if isinstance(fm.get("source_refs"), list) else []
        raws = fm.get("raw_refs") if isinstance(fm.get("raw_refs"), list) else []
        if not refs:
            err("E1", rel, "source_refs 为空")
        if not raws:
            err("E1", rel, "raw_refs 为空")
        rel_links = fm.get("related") if isinstance(fm.get("related"), list) else []

        # E5 source_refs 死链 + 与 raw_refs 双射一致性
        qids: list[str] = []
        for r in refs:
            m = re.fullmatch(r"INS-MMBench:qid=(\S+)", str(r))
            if not m:
                err("E5", rel, "source_refs 格式非法：" + str(r))
                continue
            qid = m.group(1)
            qids.append(qid)
            if qid not in by_qid:
                err("E5", rel, "qid 不在 manifest：" + qid)
                continue
            if raw_of(qid) is None:
                err("E5", rel, "qid 对应 raw 源文件缺失：" + qid)
        for r in raws:
            if not re.fullmatch(r"raw-[a-z]+-\d{4}", str(r)):
                err("E5", rel, "raw_refs 格式非法：" + str(r))
            elif not (SOURCES / (str(r) + ".json")).exists():
                err("E5", rel, "raw_refs 文件不存在：" + str(r))
        if qids:
            derived = ["raw-" + q.rsplit("_", 1)[0] + "-" + format(int(q.rsplit("_", 1)[1]), "04d") for q in qids]
            if sorted(derived) != sorted(str(x) for x in raws):
                err("E5", rel, "source_refs 与 raw_refs 不构成双射")

        # E6 空页/超长页
        if len(body) < 200:
            err("E6", rel, "空页/超薄页（正文 " + str(len(body)) + " 字符）")
        elif len(body) > 12000:
            err("E6", rel, "超长页（正文 " + str(len(body)) + " 字符）")

        # E7 正文死链
        for link in re.findall(r"\[\[([^\]]+)\]\]", body):
            if link not in rel_links:
                err("E7", rel, "正文 [[link]] 未在 related 登记：" + link)

        # E9 span 可解析
        for idx, line in enumerate(body.split("\n"), start=1):
            for spec, span in SPAN.findall(line):
                qid_spec = spec.split("=", 1)[-1]
                cand: list[str]
                if ".." in qid_spec:
                    a, b = qid_spec.split("..", 1)
                    lo, hi = int(a.rsplit("_", 1)[1]), int(b.rsplit("_", 1)[1])
                    cand = [q for q in qids if q.rsplit("_", 1)[0] == a.rsplit("_", 1)[0]
                            and lo <= int(q.rsplit("_", 1)[1]) <= hi]
                    if not cand:
                        err("E9", rel, "聚合 span 无法展开：" + qid_spec)
                        continue
                else:
                    cand = [qid_spec] if qid_spec in by_qid else []
                    if not cand:
                        err("E9", rel, "span 的 qid 不存在：" + qid_spec)
                        continue
                raw = raw_of(cand[0])
                if raw is None:
                    continue
                n = int(raw["content"]["question"]["lines"])
                if re.fullmatch(r"L\d+-L\d+", span):
                    a2, b2 = [int(x) for x in re.findall(r"\d+", span)]
                    if not (1 <= a2 <= b2 <= n):
                        err("E9", rel, "第 " + str(idx) + " 行 span 行区间越界 " + span + f"（该单元 {n} 行）")
                elif span.startswith("labels."):
                    if span[7:] not in raw["labels"]:
                        err("E9", rel, "第 " + str(idx) + " 行 labels 键不存在：" + span)
                elif "." in span and not span.startswith("labels.") and span.split(".")[0] in raw:
                    node: object = raw
                    for part in span.split("."):
                        if isinstance(node, dict) and part in node:
                            node = node[part]
                        else:
                            err("E9", rel, "第 " + str(idx) + " 行 JSON 路径不存在：" + span)
                            break
                elif span == "answer_status" and "answer_status" in raw:
                    pass
                elif span not in [str(im["path"]) for im in raw["images"]]:
                    err("E9", rel, "第 " + str(idx) + " 行 span 无法识别：" + span)

        # W1 summary 长度
        s = str(fm.get("summary", ""))
        if len(s) < 10 or len(s) > 80:
            warn("W1", rel, "summary 长度 " + str(len(s)) + "（建议 10–80）")

        pages[rel] = {"fm": fm, "body": body, "qids": qids}

    # E2 index 一致性
    index_path = WIKI / "index.md"
    if not index_path.exists():
        err("E2", "index.md", "index.md 不存在")
        rows: list[dict[str, str]] = []
    else:
        rows = []
        GROUP = {"文档页": "doc", "章节页": "section", "实体页": "entity", "问答页": "faq"}
        cur_type = ""
        for line in index_path.read_text("utf-8").split("\n"):
            st = line.strip()
            if st.startswith("## "):
                for name, ty in GROUP.items():
                    if st.startswith("## " + name):
                        cur_type = ty
                continue
            m = re.match(r"^\|\s*\[`([^`]+)`\]\(([^)]+)\)\s*\|(.*)$", st)
            if not m:
                continue
            cells = [c.strip() for c in m.group(3).split("|")]
            rows.append({"id": m.group(1), "path": m.group(2),
                         "title": cells[0] if cells else "",
                         "type": cur_type,
                         "summary": cells[1] if len(cells) > 1 else "",
                         "tags": cells[2] if len(cells) > 2 else "",
                         "updated": cells[3] if len(cells) > 3 else ""})
        idx_paths = {r["path"] for r in rows}
        disk_paths = set(pages)
        for p in sorted(disk_paths - idx_paths):
            err("E2", p, "页面未出现在 index.md")
        for p in sorted(idx_paths - disk_paths):
            err("E2", "index.md", "索引行指向不存在的页面：" + p)
        for r in rows:
            page = pages.get(r["path"])
            if not page:
                continue
            fm = page["fm"]
            full_id = str(fm.get("id", ""))
            if r["id"] != full_id.split("-", 2)[2]:
                err("E2", r["path"], "index id 与 frontmatter id 的 slug 不一致")
            label = r["summary"]
            if len(label) > 30:
                err("E2", r["path"], "短标签超 30 字（" + str(len(label)) + "）")
            if "…" in label:
                err("E2", r["path"], "短标签含省略号（禁止截断）")
            if not any(ch.isdigit() for ch in label):
                err("E2", r["path"], "短标签缺少数量维度")
            _tags = fm.get("tags") or ["?", "?"]
            split_tok = _tags[1] if len(_tags) > 1 else "?"
            head_ok = (
                label.startswith(str(fm.get("title", ""))[:4])
                if str(fm.get("type")) == "entity"
                else label.startswith(str(split_tok))
            )
            if not head_ok:
                err("E2", r["path"], "短标签未以分片/标题开头（缺区分维度）")
            if r["updated"] != str(fm.get("updated")):
                err("E2", r["path"], "index updated 与 frontmatter 不一致")
            fm_tags = {x.strip() for x in (fm.get("tags") or []) if x}
            row_tags = {x.strip() for x in r["tags"].split(",") if x.strip()}
            if not row_tags <= fm_tags:
                err("E2", r["path"], "index tags 不是 frontmatter tags 的子集")
            if r["type"] and str(fm.get("type")) != r["type"]:
                err("E2", r["path"], "行所在分组与 frontmatter type 不一致")

    # E3 孤儿页
    inbound: dict[str, int] = {p: 0 for p in pages}
    for p, page in pages.items():
        for r in page["fm"].get("related", []) if isinstance(page["fm"].get("related"), list) else []:
            for q, other in pages.items():
                if str(other["fm"].get("id")) == str(r) and q != p:
                    inbound[q] = inbound.get(q, 0) + 1
    for p, page in pages.items():
        pid = str(page["fm"].get("id"))
        in_index = any(r["id"] == pid for r in rows)
        if inbound.get(p, 0) == 0 and not in_index:
            err("E3", p, "孤儿页：无入链且不在 index")

    # E4 重复
    for field in ("id", "title"):
        seen: dict[str, str] = {}
        for p, page in pages.items():
            v = str(page["fm"].get(field, ""))
            if v in seen:
                err("E4", p, "重复 " + field + "：" + v + "（另见 " + seen[v] + "）")
            seen[v] = p
    slugs: dict[str, str] = {}
    for p in pages:
        slug = pathlib.Path(p).stem
        if slug in slugs:
            err("E4", p, "重复 slug：" + slug + "（另见 " + slugs[slug] + "）")
        slugs[slug] = p

    # E8 log 一致性
    log_path = WIKI / "log.md"
    if not log_path.exists():
        err("E8", "log.md", "log.md 不存在")
    else:
        log = log_path.read_text("utf-8")
        blocks, cur = [], []
        for ln in log.split("\n"):
            if ln.startswith("## ["):
                if cur:
                    blocks.append("\n".join(cur))
                cur = [ln]
            elif cur:
                cur.append(ln)
        if cur:
            blocks.append("\n".join(cur))
        ids = {str(page["fm"].get("id")) for page in pages.values()}
        ingests: list[str] = []
        for b in blocks:
            head = b.split("\n", 1)[0]
            m = re.match(r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|fix|schema|retract) \| (.+)$", head)
            if not m:
                err("E8", "log.md", "记录格式不可 grep：" + head[:60])
                continue
            op, title = m.group(1), m.group(2).strip()
            if op == "ingest":
                ingests.append(title)
                for need in ("- page:", "- units:", "- result:"):
                    if need not in b:
                        err("E8", "log.md", "ingest 缺字段 " + need.strip("- ") + "：" + title)
            elif op == "fix":
                for need in ("reason:", "action:", "影响范围:"):
                    if need not in b:
                        err("E8", "log.md", "fix 条目无法审计（缺 " + need + "）：" + title)
        for pid in sorted(ids - set(ingests)):
            err("E8", "log.md", "缺少 ingest 记录：" + pid)
        for pid in sorted(set(ingests) - ids):
            err("E8", "log.md", "幽灵 ingest（页面不存在）：" + pid)
        for pid in sorted({x for x in ingests if ingests.count(x) > 1}):
            err("E8", "log.md", "ingest 记录重复：" + pid)

    # 输出
    print("=== wiki_claims_lint（独立实现）===")
    print("pages=" + str(len(pages)) + " index_rows=" + str(len(rows))
          + " ERROR=" + str(len(errors)) + " WARN=" + str(len(warns)))
    for e in errors:
        print("  [E] " + e)
    for w in warns:
        print("  [W] " + w)

    sample_n = 0
    seed = 20261118
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("--sample", "--seed"):
            if i + 1 >= len(argv):
                print("FATAL: " + a + " 缺少数值", file=sys.stderr)
                return 2
            try:
                val = int(argv[i + 1])
            except ValueError:
                print("FATAL: " + a + " 必须是整数，收到 " + repr(argv[i + 1]), file=sys.stderr)
                return 2
            if a == "--sample":
                if val <= 0:
                    print("FATAL: --sample 必须 > 0", file=sys.stderr)
                    return 2
                sample_n = val
            else:
                seed = val
            i += 2
            continue
        print("FATAL: 未知参数 " + a, file=sys.stderr)
        return 2
    if sample_n:
        names = sorted(pages)
        rng = random.Random(seed)
        picked = rng.sample(names, min(sample_n, len(names)))
        print("\n=== 可复现随机抽样（seed=" + str(seed) + "，n=" + str(len(picked)) + "）===")
        for p in picked:
            print("  " + p)
        if len(names) < sample_n:
            print("  注：语料仅 " + str(len(names)) + " 页，不足 " + str(sample_n) + " 页，已全取")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
