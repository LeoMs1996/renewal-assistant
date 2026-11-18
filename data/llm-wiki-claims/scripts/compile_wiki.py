#!/usr/bin/env python3
"""D3：把 raw 源单元编译成 LLM-Wiki 页面（严格证据驱动，不写无来源断言）。

只读：raw/sources/*.json、raw/manifest.json（以及 normalize_raw.py 里的三层切分逻辑）
只写：wiki/{schema.md,index.md,log.md,<type>/<slug>.md}

纪律（R1 spec §8）：
  * 串行：按 manifest.ingest_order 逐单元处理，日志条目顺序 = 处理顺序；
  * 单写者：整次编译持 `wiki/.ingest.lock`，已存在锁则直接失败（不抢写）；
  * 幂等：页面/index 由输入完全决定；log 只追加缺失的 ingest 记录，不重写历史。

用法：
    python3 scripts/compile_wiki.py build --pages <id>[,<id>...]
    python3 scripts/compile_wiki.py build --all
    python3 scripts/compile_wiki.py check
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import normalize_raw as d2  # noqa: E402  复用 D2 的三层切分，避免维护两份计划

CLAIMS = HERE.parent
WIKI = CLAIMS / "wiki"
LOCK = WIKI / ".ingest.lock"
MANIFEST = CLAIMS / "raw" / "manifest.json"
SOURCES = CLAIMS / "raw" / "sources"
UPDATED = "2026-11-18"  # 固定日期：产物不含运行时时间，保证幂等

TYPE_DIR = {"doc": "docs", "section": "sections", "entity": "entities", "faq": "faqs"}
INSURANCE_LINE = {
    "claim": "auto_claim",
    "liability": "auto_liability",
    "agri": "agricultural_claim",
    "health": "health_underwriting",
    "property": "property_claim",
}
CROSS = "cross_cutting"
# 各分片的「判断类字段」：FAQ 页与索引短标签共用（此前写在 body_faq 内）
DECISION_KEY = {
    "claim": "claim",
    "agri": "claim",
    "property": "claim_decision",
    "health": "underwriting_decision",
    "liability": "primary_responsibility",
}


# ---------------------------------------------------------------- 基础工具


def load_plan() -> tuple[dict, list[dict]]:
    records = {s: d2.load_split(s) for s in d2.SPLIT_ORDER}
    pages, _ = d2.build_plan_rows(records)
    return records, pages


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text("utf-8"))


def read_raw(raw_id: str) -> dict:
    return json.loads((SOURCES / (raw_id + ".json")).read_text("utf-8"))


def qid_for_raw_id(raw_id: str) -> str:
    _, split, idx = raw_id.split("-", 2)
    return split + "_" + str(int(idx))


def raw_id_for_qid(qid: str) -> str:
    split, idx = qid.rsplit("_", 1)
    return "raw-" + split + "-" + format(int(idx), "04d")


def page_rel_path(page_id: str, ptype: str) -> str:
    slug = page_id.split("-", 2)[2]
    return TYPE_DIR[ptype] + "/" + slug + ".md"


def question_lines(raw: dict) -> list[str]:
    return str(raw["content"]["question"]["text"]).split("\n")


def output_block(lines: list[str]) -> tuple[int, int] | None:
    start = None
    for i, line in enumerate(lines, start=1):
        if "strictly output" in line.lower():
            start = i
            break
    if start is None:
        return None
    end = start
    for i in range(start, len(lines) + 1):
        if lines[i - 1].strip():
            end = i
    return start, end


def key_line(lines: list[str], keys: list[str]) -> tuple[int, int] | None:
    needles: list[str] = []
    for k in keys:
        needles.append(k.lower())
        needles.append(k.replace("_", " ").lower())
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if any(n in low for n in needles):
            return i, i
    return None


def quote_block(lines: list[str], span: tuple[int, int]) -> str:
    return "\n".join("> " + lines[i - 1] for i in range(span[0], span[1] + 1))


def m1(qid: str, span: str) -> str:
    return "⟦S:INS-MMBench:qid=" + qid + "@" + span + "⟧"


def mrange(qids: list[str], span: str) -> str:
    return "⟦S:INS-MMBench:qids=" + qids[0] + ".." + qids[-1] + "@" + span + "⟧"


def markers_by_split(qids: list[str], span: str) -> str:
    """把一串 qid 按分片分组、再按**连续段**生成区间标记。

    两条硬约束（D4b 修复）：
      1. 跨分片不能拼成一个区间；
      2. **非连续 qid 不能折叠成一个区间**——汇总分片是抽样得到的非连续集合
         （如 liability 只留 0000/0001/0003/.../0020），写成 `liability_0..liability_20`
         会凭空断言中间 9 个不存在的单元。非连续时按连续段拆分。
    """
    groups: dict[str, list[str]] = {}
    for q in qids:
        groups.setdefault(q.rsplit("_", 1)[0], []).append(q)
    out: list[str] = []
    for split in sorted(groups):
        idxs = sorted({int(q.rsplit("_", 1)[1]) for q in groups[split]})
        run: list[int] = []
        for i in idxs:
            if run and i != run[-1] + 1:
                out.append(_range_of(split, run, span))
                run = []
            run.append(i)
        if run:
            out.append(_range_of(split, run, span))
    return " ".join(out)


def _range_of(split: str, idxs: list[int], span: str) -> str:
    qs = [split + "_" + str(i) for i in idxs]
    return m1(qs[0], span) if len(qs) == 1 else mrange(qs, span)


def cell(value: object, limit: int = 80) -> str:
    text = str(value).replace("|", "\\|").strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def distribution(qids: list[str], key: str) -> str:
    counter: dict[str, int] = {}
    for qid in qids:
        raw = read_raw(raw_id_for_qid(qid))
        v = str(raw["labels"].get(key, "—"))
        counter[v] = counter.get(v, 0) + 1
    return "/".join(cell(v, 24) + "×" + str(c) for v, c in counter.items())


def _all_numeric(qids: list[str], key: str) -> bool:
    """该分片内该键的取值是否全为数值（用于识别「同名不同义」）。"""
    vals = [str(read_raw(raw_id_for_qid(q))["labels"].get(key, "")) for q in qids]
    vals = [v for v in vals if v]
    if not vals:
        return False
    for v in vals:
        try:
            float(v)
        except ValueError:
            return False
    return True


def heterogeneous_note(qids: list[str], keys: list[str], splits: list[str]) -> str:
    """同名 label 键在不同分片类型不同时，显式告警（lint 查不出，属人工复核职责）。"""
    for key in keys:
        per: dict[str, bool] = {}
        for split in splits:
            group = [q for q in qids if q.rsplit("_", 1)[0] == split]
            per[split] = _all_numeric(group, key)
        if len(set(per.values())) < 2:
            continue
        numeric = [s for s, ok in per.items() if ok]
        other = [s for s, ok in per.items() if not ok]
        sample_numeric = next(
            (str(read_raw(raw_id_for_qid(q))["labels"].get(key)) for q in qids
             if q.rsplit("_", 1)[0] in numeric and read_raw(raw_id_for_qid(q))["labels"].get(key)),
            "",
        )
        sample_other = next(
            (str(read_raw(raw_id_for_qid(q))["labels"].get(key)) for q in qids
             if q.rsplit("_", 1)[0] in other and read_raw(raw_id_for_qid(q))["labels"].get(key)),
            "",
        )
        return (
            "- 【方法约束】同名不同义（机器标记可回溯、语义却不同）：`" + key + "` 在 "
            + "/".join(numeric) + " 分片为数值（如 " + sample_numeric + "），在 "
            + "/".join(other) + " 分片为枚举（如 " + sample_other + "）；"
            + "本页按分片分别登记，**不得合并统计**"
            + markers_by_split(qids, "labels." + key)
        )
    return ""

# ---------------------------------------------------------------- 页面元数据


def page_meta(page: dict, compiled: set[str]) -> dict:
    pid = str(page["page_id"])
    ptype = str(page["type"])
    raw_refs = [str(r) for r in page["source_refs"]]
    qids = [qid_for_raw_id(r) for r in raw_refs]
    split = raw_refs[0].split("-")[1] if raw_refs else "cross"
    if ptype == "entity":
        splits = sorted({r.split("-")[1] for r in raw_refs})
        insurance_line = INSURANCE_LINE.get(splits[0], CROSS) if len(splits) == 1 else CROSS
    else:
        insurance_line = INSURANCE_LINE.get(split, CROSS)
    return {
        "pid": pid,
        "ptype": ptype,
        "page": page,
        "raw_refs": raw_refs,
        "qids": qids,
        "split": split,
        "splits": sorted({r.split("-")[1] for r in raw_refs}),
        "insurance_line": insurance_line,
        "title": str(page["title"]),
        "related": [],  # 由 attach_related() 统一计算
    }


def attach_related(metas: list[dict]) -> None:
    """双向 related：只在「已编译」页面之间连边；同 split 且跨类型的邻居 + 同一类型族内互连。"""
    by_id = {m["pid"]: m for m in metas}
    edges: set[tuple[str, str]] = set()
    for m in metas:
        for other in metas:
            if other["pid"] == m["pid"]:
                continue
            same_split = other["split"] == m["split"] and m["split"] != "cross"
            # doc 页可能跨分片（auto = claim + liability），故按「单元有交集」连边更准确
            refs_overlap = bool(set(m["raw_refs"]) & set(other["raw_refs"]))
            if m["ptype"] == "doc" and other["ptype"] in ("section", "faq") and refs_overlap:
                edges.add(tuple(sorted((m["pid"], other["pid"]))))
            if m["ptype"] in ("section", "faq") and other["ptype"] == "doc" and refs_overlap:
                edges.add(tuple(sorted((m["pid"], other["pid"]))))
            if m["ptype"] == "section" and other["ptype"] == "section" and same_split:
                edges.add(tuple(sorted((m["pid"], other["pid"]))))
            # entity ↔ 同分片且键有交集的 section；entity ↔ 该分片 doc 页
            if m["ptype"] == "entity" and same_split:
                if other["ptype"] == "doc":
                    edges.add(tuple(sorted((m["pid"], other["pid"]))))
                elif other["ptype"] == "section":
                    k1 = {str(k) for k in m["page"].get("label_keys", [])}
                    k2 = {str(k) for k in other["page"].get("label_keys", [])}
                    if k1 & k2:
                        edges.add(tuple(sorted((m["pid"], other["pid"]))))
            if m["ptype"] == "section" and other["ptype"] == "entity" and same_split:
                k1 = {str(k) for k in m["page"].get("label_keys", [])}
                k2 = {str(k) for k in other["page"].get("label_keys", [])}
                if k1 & k2:
                    edges.add(tuple(sorted((m["pid"], other["pid"]))))
    for a, b in sorted(edges):
        by_id[a]["related"].append(b)
        by_id[b]["related"].append(a)
    for m in metas:
        m["related"] = sorted(set(m["related"]))


# ---------------------------------------------------------------- 各类型正文


def body_doc(m: dict) -> str:
    qids = m["qids"]
    keys_union: list[str] = []
    rows: list[str] = []
    for qid in qids:
        raw = read_raw(raw_id_for_qid(qid))
        labels = raw["labels"]
        for k in labels:
            if k not in keys_union:
                keys_union.append(k)
        nlines = raw["content"]["question"]["lines"]
        span = "L1-L" + str(nlines)
        rows.append(
            "| `" + qid + "` | " + str(raw["sample"]["task_name"]) + " | "
            + str(len(raw["images"])) + " | " + str(nlines) + " | "
            + m1(qid, span) + " |"
        )
    first = read_raw(m["raw_refs"][0])
    lines = question_lines(first)
    ob = output_block(lines)
    tasks = sorted({str(read_raw(r)["sample"]["task_name"]) for r in m["raw_refs"]})
    n_images = sum(len(read_raw(r)["images"]) for r in m["raw_refs"])
    first_img = str(read_raw(m["raw_refs"][0])["images"][0]["path"])
    n = len(qids)
    parts: list[str] = []
    parts.append("# " + m["title"])
    parts.append("")
    parts.append("> 本页是抽样层登记页：只登记「本子集里有哪些样本、字段是否齐全」，不做业务推断。")
    parts.append("> 全子集 54 条，本页覆盖 " + str(m["page"]["layer"]) + " 的 " + str(n) + " 条。")
    parts.append("")
    parts.append("## 1. 样本清单（逐行可回溯）")
    parts.append("")
    parts.append("| qid | 任务 | 图片数 | 题干行数 | 定位 |")
    parts.append("|---|---|---|---|---|")
    parts.extend(rows)
    parts.append("")
    parts.append("## 2. 字段齐全度（由上表聚合，非外部知识）")
    parts.append("")
    own_qids: dict[str, list[str]] = {}
    for qid in qids:
        for k in read_raw(raw_id_for_qid(qid))["labels"]:
            own_qids.setdefault(k, []).append(qid)
    parts.append(
        "- 本页 " + str(n) + " 条样本共出现 " + str(len(keys_union)) + " 个 LABEL 键："
        + ", ".join("`" + k + "`(" + str(len(own_qids[k])) + " 条)" for k in keys_union)
        + "（证据：下列标记逐键覆盖真正含该键的单元；§1 表只登记每条样本本身的定位）"
        + " ".join(markers_by_split(own_qids[k], "labels." + k) for k in keys_union)
    )
    parts.append("")
    parts.append("## 3. 题干规约（逐字，取首单元 `" + qids[0] + "`）")
    parts.append("")
    if ob:
        parts.append(quote_block(lines, ob))
        parts.append("")
        parts.append(m1(qids[0], "L" + str(ob[0]) + "-L" + str(ob[1])))
    else:
        parts.append("（该分片题干无「严格输出格式」段落，故此处只登记样本，不做规约引用）")
    parts.append("")
    parts.append("## 4. 层级说明")
    parts.append("")
    parts.append(
        "- 本子集 54 条的 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`："
        "**分层实际只落在 `task_name` 这一层**（本页对应 "
        + ", ".join("`" + t + "`" for t in tasks) + "），不存在更粗/更细的层级区分度"
        + " ".join(m1(q, "sample.task_layer") for q in [g[0] for g in
            [[q for q in qids if q.rsplit("_", 1)[0] == sp] for sp in sorted({q.rsplit("_", 1)[0] for q in qids})]])
        + " ".join(m1(q, "sample.meta_task") for q in [g[0] for g in
            [[q for q in qids if q.rsplit("_", 1)[0] == sp] for sp in sorted({q.rsplit("_", 1)[0] for q in qids})]])
    )
    parts.append("")
    parts.append("## 5. 图片引用前提")
    parts.append("")
    parts.append(
        "- 本页 " + str(n_images) + " 张图片**未入库**（避免 33 MiB 重复）：引用形态为 "
        "`data/ins-mmbench/raw/<split>/<index>/<n>.jpg`，已在 manifest 固定 sha256；"
        "新 clone 需先按 `data/ins-mmbench/FETCH.md` 重取，再跑 "
        "`python3 data/llm-wiki-claims/scripts/normalize_raw.py check` 复核" + m1(qids[0], first_img)
    )
    parts.append("")
    parts.append("## 6. 相关条目")
    parts.append("")
    parts.extend(related_lines(m))
    return "\n".join(parts)


def body_section(m: dict) -> str:
    keys = [str(k) for k in m["page"].get("label_keys", [])]
    qids = m["qids"]
    rows: list[str] = []
    for qid in qids:
        raw = read_raw(raw_id_for_qid(qid))
        vals = " | ".join(cell(raw["labels"].get(k, "—")) for k in keys)
        marks = " ".join(m1(qid, "labels." + k) for k in keys if k in raw["labels"])
        rows.append("| `" + qid + "` | " + vals + " | " + marks + " |")
    first = read_raw(m["raw_refs"][0])
    lines = question_lines(first)
    quotes: list[tuple[str, str]] = []
    seen: set[tuple[int, int]] = set()
    # D4b 修复：逐个字段各取一条代表行。旧实现只取“第一个命中任一字段名”的行，
    # 导致 Amount/Severity 这类多字段章节只引到 severity 指令、完全漏掉金额指令
    # （引用仍逐字成立，但语义不完整——机器检查查不出的那类缺陷）。
    for key in keys:
        kl = key_line(lines, [key])
        if kl and kl not in seen:
            seen.add(kl)
            quotes.append(
                (quote_block(lines, kl), m1(qids[0], "L" + str(kl[0]) + "-L" + str(kl[1])))
            )
    if not quotes:   # 字段名未在题干出现时，退回整串 keys 的启发式
        kl = key_line(lines, keys)
        if kl:
            seen.add(kl)
            quotes.append(
                (quote_block(lines, kl), m1(qids[0], "L" + str(kl[0]) + "-L" + str(kl[1])))
            )
    ob = output_block(lines)
    if ob and ob not in seen:
        quotes.append((quote_block(lines, ob), m1(qids[0], "L" + str(ob[0]) + "-L" + str(ob[1]))))
    dist = "；".join(k + "=" + distribution(qids, k) for k in keys)
    parts: list[str] = []
    parts.append("# " + m["title"])
    parts.append("")
    parts.append(
        "> 本页只陈述本子集中 " + ", ".join("`" + k + "`" for k in keys)
        + " 的 " + str(len(qids)) + " 条样本事实与题干规约，不引入外部条款知识。"
    )
    parts.append("")
    parts.append("## 1. 题干规约（逐字，取首单元 `" + qids[0] + "`）")
    parts.append("")
    if quotes:
        for block, mark in quotes:
            parts.append(block)
            parts.append("")
            parts.append(mark)
            parts.append("")
    else:
        parts.append("（该分片题干未显式提及本主题字段，故无规约引用）")
        parts.append("")
    parts.append("## 2. 样本事实（逐行 span 级）")
    parts.append("")
    parts.append("| qid | " + " | ".join("`" + k + "`" for k in keys) + " | 原文定位 |")
    parts.append("|---|" + "---|" * len(keys) + "---|")
    parts.extend(rows)
    parts.append("")
    parts.append("## 3. 聚合观察（派生自上表，不是外部知识）")
    parts.append("")
    parts.append(
        "- " + str(len(qids)) + "/" + str(len(qids)) + " 条样本均具备上述字段；取值分布："
        + dist + "（证据：§2 全 " + str(len(qids)) + " 行）" + markers_by_split(qids, "labels." + keys[0])
    )
    parts.append(
        "- 【方法约束】本子集按标签排序，若某字段为单值分布，不得用于分类准确率（台账 D-04）；"
        "该句是评测口径约束，不是样本事实，故不挂引用标记"
    )
    parts.append("")
    parts.append("## 4. 相关条目")
    parts.append("")
    parts.extend(related_lines(m))
    return "\n".join(parts)


def body_faq(m: dict) -> str:
    qids = m["qids"]
    first = read_raw(m["raw_refs"][0])
    lines = question_lines(first)
    ob = output_block(lines)
    keys: list[str] = []
    for qid in qids:
        for k in read_raw(raw_id_for_qid(qid))["labels"]:
            if k not in keys:
                keys.append(k)
    decision_key = DECISION_KEY.get(m["split"], "claim")
    dist = distribution(qids, decision_key)
    question = str(m["page"]["themes"][0]) if m["page"].get("themes") else "（未登记）"
    parts: list[str] = []
    parts.append("# " + m["title"])
    parts.append("")
    parts.append("> 本页只回答「本子集语料能支持到什么程度」：答案由样本字段与题干规约拼成，不是业务建议。")
    parts.append("")
    parts.append("目录中的问题：" + question)
    parts.append("")
    parts.append("## 1. 题干规约（逐字，取首单元 `" + qids[0] + "`）")
    parts.append("")
    if ob:
        parts.append(quote_block(lines, ob))
        parts.append("")
        parts.append(m1(qids[0], "L" + str(ob[0]) + "-L" + str(ob[1])))
    else:
        parts.append("（该分片题干无「严格输出格式」段落）")
    parts.append("")
    parts.append("## 2. 本子集能给出的答案（逐条引用）")
    parts.append("")
    rows: list[str] = []
    for qid in qids:
        r = read_raw(raw_id_for_qid(qid))
        cells = " | ".join(cell(r["labels"].get(k, "—"), 24) for k in keys)
        marks = " ".join(m1(qid, "labels." + k) for k in keys if k in r["labels"])
        rows.append("| `" + qid + "` | " + cells + " | " + marks + " |")
    parts.append("| qid | " + " | ".join("`" + k + "`" for k in keys) + " | 原文定位 |")
    parts.append("|---|" + "---|" * len(keys) + "---|")
    parts.extend(rows)
    parts.append("")
    parts.append(
        "- 以本子集 " + str(len(qids)) + " 条 " + m["split"] + " 样本为准，判断类字段 `" + decision_key + "` 的取值分布为 "
        + dist + "（证据：上表逐行）" + markers_by_split(qids, "labels." + decision_key)
    )
    parts.append(
        "- 可用于回答的字段清单（与本页 `source_refs` 同集合）："
        + ", ".join("`" + k + "`" for k in keys)
        + " " + " ".join(m1(qids[0], "labels." + k) for k in keys)
    )
    parts.append("")
    parts.append("## 3. 本页不回答什么")
    parts.append("")
    parts.append(
        "- 不给出条款级依据：本子集无条款文本，且 `answer` 列不存在（`answer_status=absent_in_source`）"
        + m1(qids[0], "answer_status")
    )
    parts.append("")
    parts.append("## 4. 相关条目")
    parts.append("")
    parts.extend(related_lines(m))
    return "\n".join(parts)




def body_entity(m: dict) -> str:
    """实体页：只登记「该实体在本子集里出现过哪些单元、每个属性取值是什么」。

    硬要求（船长）：每个实体属性必须带 @labels.* 或行区间，不允许裸断言。
    """
    page = m["page"]
    keys = [str(k) for k in page.get("label_keys", [])]
    qids = m["qids"]
    first = read_raw(m["raw_refs"][0])
    lines = question_lines(first)

    rows: list[str] = []
    for qid in qids:
        raw = read_raw(raw_id_for_qid(qid))
        vals = " | ".join(cell(raw["labels"].get(k, "—"), 40) for k in keys)
        marks = " ".join(m1(qid, "labels." + k) for k in keys if k in raw["labels"])
        rows.append("| `" + qid + "` | " + vals + " | " + marks + " |")

    quotes: list[tuple[str, str]] = []
    kl = key_line(lines, keys)
    if kl:
        quotes.append((quote_block(lines, kl), m1(qids[0], "L" + str(kl[0]) + "-L" + str(kl[1]))))
    ob = output_block(lines)
    if ob:
        quotes.append((quote_block(lines, ob), m1(qids[0], "L" + str(ob[0]) + "-L" + str(ob[1]))))

    dist = "；".join(k + "=" + distribution(qids, k) for k in keys)
    parts: list[str] = []
    parts.append("# " + m["title"] + "（实体页）")
    parts.append("")
    parts.append(
        "> 本页把「" + str(page.get("themes", [m["title"]])[0]) + "」登记为跨样本实体："
        "只列本子集中出现过该字段的单元与取值，不做条款解释、不做精算推断。"
    )
    parts.append("")
    parts.append("## 1. 字段出处（逐字，取首单元 `" + qids[0] + "`）")
    parts.append("")
    if quotes:
        for block, mark in quotes:
            parts.append(block)
            parts.append("")
            parts.append(mark)
            parts.append("")
    else:
        parts.append("（该分片题干未显式提及本实体字段，故无出处引用）")
        parts.append("")
    parts.append("## 2. 属性事实（逐单元、逐属性带标记）")
    parts.append("")
    parts.append("| qid | " + " | ".join("`" + k + "`" for k in keys) + " | 原文定位 |")
    parts.append("|---|" + "---|" * len(keys) + "---|")
    parts.extend(rows)
    parts.append("")
    parts.append("## 3. 取值分布（派生自 §2，不是外部知识）")
    parts.append("")
    splits = sorted({q.rsplit("_", 1)[0] for q in qids})
    if len(splits) <= 1:
        parts.append(
            "- 本实体在子集中出现于 " + str(len(qids)) + " 个单元（" + m["split"] + " 分片），"
            "每个属性均可在 §2 对应单元格回溯；取值分布：" + dist + markers_by_split(qids, "labels." + keys[0])
        )
    else:
        # 跨分片实体（D4b 修复）：同一 label 键在不同分片可能语义不同，
        # 故逐分片分开登记，不得把不同分片的取值合并成一个分布。
        for split in splits:
            group = sorted(
                [q for q in qids if q.rsplit("_", 1)[0] == split],
                key=lambda q: int(q.rsplit("_", 1)[1]),
            )
            parts.append(
                "- `" + split + "` 分片（" + str(len(group)) + " 个单元）："
                + "；".join(k + "=" + distribution(group, k) for k in keys)
                + markers_by_split(group, "labels." + keys[0])
            )
        note = heterogeneous_note(qids, keys, splits)
        if note:
            parts.append(note)
    parts.append(
        "- 属性个数：" + str(len(keys)) + "（" + ", ".join("`" + k + "`" for k in keys) + "）；"
        "本页不含任何未在上述单元格出现过的取值"
        + m1(qids[0], "labels." + keys[0])
    )
    parts.append("")
    parts.append("## 4. 相关条目")
    parts.append("")
    parts.extend(related_lines(m))
    return "\n".join(parts)


def related_lines(m: dict) -> list[str]:
    if not m["related"]:
        return ["- （暂无已编译的互链对象；计划内相邻条目见 `plan.md` §4，编译后由脚本自动建立双向 `related`）"]
    return ["- [[" + r + "]] `" + r + "`" for r in m["related"]]


BUILDERS = {"doc": body_doc, "section": body_section, "entity": body_entity, "faq": body_faq}


# ---------------------------------------------------------------- 渲染


def summary_of(m: dict) -> str:
    n = len(m["qids"])
    split = m["split"]
    if m["ptype"] == "doc":
        return "INS-MMBench 子集 " + split + " 保险 " + str(n) + " 条样本的登记页：字段齐全、逐行可回溯。"
    if m["ptype"] == "section":
        keys = "/".join(str(k) for k in m["page"].get("label_keys", []))
        return keys + " 在 " + str(n) + " 条 " + split + " 样本中的字段事实与题干规约（逐条 span 可回溯）。"
    if m["ptype"] == "entity":
        keys2 = "/".join(str(k) for k in m["page"].get("label_keys", []))
        splits2 = m.get("splits") or [split]
        tail = ("（跨 " + "+".join(splits2) + " 分片）") if len(splits2) > 1 else ""
        return keys2 + " 实体登记：" + str(n) + " 个单元" + tail + "，逐属性可回溯。"
    return split + " 任务语料能支持到的回答范围（" + str(n) + " 条样本，逐条引用）。"


def render_page(m: dict) -> str:
    tags = ["ins-mmbench", m["split"], m["ptype"]]
    fm = [
        "---",
        "id: " + m["pid"],
        "type: " + m["ptype"],
        "title: " + m["title"],
        "domain: claims",
        "insurance_line: " + m["insurance_line"],
        "summary: " + summary_of(m),
        "tags: [" + ", ".join(tags) + "]",
        "source_refs: [" + ", ".join("INS-MMBench:qid=" + q for q in m["qids"]) + "]",
        "raw_refs: [" + ", ".join(m["raw_refs"]) + "]",
        "updated: " + UPDATED,
        "related: [" + ", ".join(m["related"]) + "]",
        "status: verified",
        "---",
        "",
    ]
    return "\n".join(fm) + BUILDERS[m["ptype"]](m) + "\n"


LABEL_MAX = 30


def distinct_values(qids: list[str], key: str) -> list[str]:
    seen: list[str] = []
    for qid in qids:
        v = str(read_raw(raw_id_for_qid(qid))["labels"].get(key, ""))
        if v and v not in seen:
            seen.append(v)
    return seen


def index_label(m: dict) -> str:
    """索引短标签：由页面元数据确定性生成（不是 summary 截断，不含省略号）。

    规则：`·` 分隔的 2–3 段，必须含「区分维度 + 数量」；超 30 字时按固定顺序降级，
    绝不截断成半句话。
    """
    n = len(m["qids"])
    keys = [str(k) for k in m["page"].get("label_keys", [])]
    ptype = m["ptype"]
    if ptype == "doc":
        splits = "+".join(sorted({r.split("-")[1] for r in m["raw_refs"]}))
        ku: list[str] = []
        for qid in m["qids"]:
            for k in read_raw(raw_id_for_qid(qid))["labels"]:
                if k not in ku:
                    ku.append(k)
        cands = [
            [splits, str(n) + " 条样本", str(len(ku)) + " 字段"],
            [splits, str(n) + " 条", str(len(ku)) + " 字段"],
            [splits, str(n) + " 条"],
        ]
    elif ptype == "section":
        two = "/".join(keys[:2])
        cands = [
            [m["split"], two, str(n) + " 单元"],
            [m["split"], keys[0] if keys else "-", str(n) + " 单元"],
            [m["split"], str(n) + " 单元"],
        ]
    elif ptype == "entity":
        key0 = keys[0] if keys else "-"
        d = distinct_values(m["qids"], key0) if key0 != "-" else []
        short_vals = [v for v in d if len(v) <= 8][:2]
        with_vals = (
            [m["title"], str(len(d)) + " 种：" + "/".join(short_vals)] if short_vals else None
        )
        cands = [
            [m["title"], key0, str(len(d)) + " 种取值"],
            *([with_vals] if with_vals else []),
            [m["title"], str(len(d)) + " 种取值"],
            [m["title"], str(n) + " 单元"],
        ]
    else:  # faq
        dk = DECISION_KEY.get(m["split"], "claim")
        d = distinct_values(m["qids"], dk)
        dk_show = dk if dk != m["split"] else "判断档位"
        cands = [
            [m["split"], dk_show, str(len(d)) + " 种取值"],
            [m["split"], str(len(d)) + " 种取值"],
            [m["split"], str(n) + " 单元"],
        ]
    for parts in cands:
        text = " · ".join(parts)
        if len(text) <= LABEL_MAX and "…" not in text:
            return text
    return m["split"] + " · " + str(n) + " 单元"


def render_index(metas: list[dict]) -> str:
    lines = [
        "# 理赔域 LLM-Wiki 索引（index.md）",
        "",
        "> 脚本生成，勿手改。条目 " + str(len(metas)) + "；类型见分组标题；末列「短标签」由页面元数据确定性生成（≤30 字，含区分维度与数量）。",
        "> 分层只落在 `task_name`（54 条 `task_layer` 全为 `scenario`）。查询：本索引定位 id → 读条目 → 逐字核对回 raw。",
        "",
    ]
    for ptype, label in [("doc", "文档页"), ("section", "章节页"), ("entity", "实体页"), ("faq", "问答页")]:
        group = [m for m in metas if m["ptype"] == ptype]
        if not group:
            continue
        lines += [
            "## " + label + "（" + str(len(group)) + "）",
            "",
            "| id | 标题 | 短标签 | tags | updated |",
            "|---|---|---|---|---|",
        ]
        for m in group:
            rel = page_rel_path(m["pid"], m["ptype"])
            short_id = m["pid"].split("-", 2)[2]          # claims-<type>-<slug> → slug
            short_title = m["title"].split("（")[0]        # 去掉「（task_name）」括注
            tags = m["split"]                              # type 见分组标题；ins-mmbench 是全站常量
            lines.append(
                "| [`" + short_id + "`](" + rel + ") | " + short_title + " | "
                + index_label(m) + " | " + tags + " | " + UPDATED + " |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


SCHEMA = """# 理赔域 LLM-Wiki schema（schema.md）

> 规范来源：`docs/research/llmwiki-spec.md`（R1 定稿）；本文件是它在本语料根的落地摘要。
> 生成方式：`python3 data/llm-wiki-claims/scripts/compile_wiki.py build --all`（勿手改；`build` 不带选择器会报错，防误触全量）。

## 1. 三层

| 层 | 位置 | 谁写 |
|---|---|---|
| raw（事实，不可变） | `../raw/sources/*.json` | D2 生成器；LLM 只读 |
| wiki（知识，本目录） | `index.md` / `log.md` / `<type>/*.md` | 编译脚本（D3） |
| schema | 本文件 | 人 + 脚本共演进 |

## 2. frontmatter（9 必填 + 1 补充）

| 字段 | 必填 | 取值 |
|---|---|---|
| `id` | 是 | `claims-<type>-<slug>`，全局唯一 |
| `type` | 是 | `doc｜section｜entity｜faq`（`query` 由 D4 回写时新增） |
| `title` | 是 | 中文短标题 |
| `domain` | 是 | 恒 `claims` |
| `insurance_line` | 是 | `auto_claim｜auto_liability｜agricultural_claim｜health_underwriting｜property_claim｜cross_cutting` |
| `summary` | 是 | 一句话 ≤80 字，与 index 摘要列完全一致 |
| `tags` | 是 | 3 个：`ins-mmbench` / 分片 / 页类型 |
| `source_refs` | 是 | `INS-MMBench:qid=<split>_<idx>` 列表（D4 核对用） |
| `raw_refs` | 补充 | `raw-<split>-<idx:04d>` 列表（R1 spec 的 raw_id 形式） |
| `updated` | 是 | ISO 日期（本批固定 `2026-11-18`） |
| `related` | 是 | 其它 `id`，必须双向；可为空（尚无已编译邻居时） |
| `status` | 是 | `draft｜verified｜conflicted｜stale` |

`qid <-> raw_id` 是机械双射：`qid = <split>_<idx>`，`raw_id = raw-<split>-<idx:04d>`，均可从 `../raw/manifest.json` 反查。

### 2.1 字段改名记录（2026-11-18）

**`claim_type` → `insurance_line`**（船长评审裁决定名）。原因：`claim` 在本项目同时表示「理赔域（claims）」与「断言（claim）」，36 页规模下极易被误读成 fact/rule 那类断言分类。
方法名与值域**未变**（仍是 6 个业务类型枚举），只改字段名；旧名 `claim_type` **不要再使用**，两套 lint 均已把它移出必填列表。
若看到历史文本写 `claim_type`，按本条映射理解为 `insurance_line`。

## 3. 引用语法（断言级，span 必须落到字段/行/图）

| 形态 | 例子 | 适用 |
|---|---|---|
| 单单元 | `⟦S:INS-MMBench:qid=agri_0@labels.species⟧` | 单条样本事实 |
| 单元区间 | `⟦S:INS-MMBench:qids=agri_0..agri_11@labels.count⟧` | 聚合陈述（集合必须 ⊆ 本页 source_refs） |
| 行区间 | `⟦S:INS-MMBench:qid=agri_0@L9-L10⟧` | 题干规约逐字引用（1-based，含端点） |
| 图片 | `⟦S:INS-MMBench:qid=agri_0@agri/0/0.jpg⟧` | 视觉证据（图片未入库，见 §6） |
| 字段路径 | `⟦S:INS-MMBench:qid=agri_0@answer_status⟧` / `@sample.task_layer` | raw JSON 的任意标量路径（点分；`labels.a.b` 同理） |

禁止只写「来源：raw-xxx」这类粗引用。逐字引用块（`> ` 行）之后必须紧跟行区间标记，且内容必须与 raw 该行区间一致（比较时忽略行尾空白）。

## 4. 页面正文约定

1. 只写两类内容：逐字引用（`>` 块 + 行区间标记）与样本表行（每行带字段级标记）。
2. 聚合陈述必须紧跟区间标记，且区间集合 ⊆ 本页 `source_refs`。
3. 不得引入 raw 之外的知识；业务解释一律标注「本页不回答」。
   评测口径等**方法约束**必须以 `- 【方法约束】` 开头，且**不得挂引用标记**（它是规则，不是样本事实）。
4. 图片未入库：正文必须写明「需按 FETCH.md 重取后校验 sha256」的前提。

## 5. index.md / log.md

- `index.md`：每页一行，列为 `id | 标题 | 短标签 | tags | updated`，**type 由分组标题承载**（`## 文档页 / 章节页 / 实体页 / 问答页`）；脚本重建。
  **末列是「生成的短标签」，不是 summary 截断**（截断会切出「标题同义重复 + …」，无定位价值）。短标签由页面元数据确定性生成，规则：
  | 页型 | 生成模板（`·` 分隔） | 例 |
  |---|---|---|
  | doc | `分片[+分片] · N 条样本 · K 字段` | `claim+liability · 24 条 · 16 字段` |
  | section | `分片 · 主字段[/次字段] · N 单元` | `claim · Min_coverage · 12 单元` |
  | entity | `标题 · 主字段 · D 种取值`（或 `标题 · D 种：值1/值2`） | `保额与赔付上限 · 12 种：1122.5/715.0` |
  | faq | `分片 · 判断字段 · D 种取值` | `agri · claim · 2 种取值` |
  生成时按固定降级顺序选出 **≤30 字且不含省略号** 的第一种候选；**禁止**人工手写（36 页会出 36 种风格）。
  两套 lint 各自校验：≤30 字 / 无 `…` / 必须含数字（数量维度）/ 必须以分片（entity 为标题）开头（区分维度）+ updated 相等 + tags ⊆ frontmatter tags。
  链接标签用 slug（`claims-<type>-` 前缀在分组标题里已表达，省字节）。
  **体积台账（2026-11-18 实测，t26 短标签版）**：`index.md` = **5867 B**；估算 token ≈ **1955**（方法：UTF-8 中文 3 B/字，按「1 字 ≈ 1 token」保守换算，即 B/3；英文与标点略偏保守）。
  上限 **6144 B（≈3k tokens）**，来自 R1 spec §4 的 L0 预算。增长到超限时：**不再压缩字数或删列**，改为报告并提出按 type 分卷（`index-{doc,section,entity,faq}.md`），分卷须经批准。
- `log.md`：只追加，格式 `## [YYYY-MM-DD] <op> | <title>`；`op ∈ ingest｜query｜lint｜fix｜schema｜retract`；每条 `ingest` 必须含 `page`、`units`、`result`、`lint` 四项。

## 6. 已知边界

- 本子集 54 条 `task_layer` 全为 `scenario`、`meta_task` 全为 `null`：分层只落在 `task_name`。
- 54 条 `answer` 全为 `null`（场景分片无 answer 列）：页面不得编造标准答案，D5 只评检索/接地指标。
- 图片未入 `raw/assets/`：需按 `../ins-mmbench/FETCH.md` 重取后校验 sha256。
- 部分标签在本子集为单值分布（按标签排序所致）：不得据此算分类准确率。
"""


# ---------------------------------------------------------------- 落盘


def build(pages_filter: list[str] | None) -> dict[str, str]:
    """→ {wiki 相对路径: 内容}，不写盘。"""
    records, pages = load_plan()
    metas_all = [page_meta(p, set()) for p in pages]
    by_id = {m["pid"]: m for m in metas_all}
    if pages_filter:
        wanted = [w for w in pages_filter if w in by_id]
        missing = [w for w in pages_filter if w not in by_id]
        if missing:
            raise SystemExit("FATAL: 未知 page_id: " + ", ".join(missing))
    else:
        wanted = [m["pid"] for m in metas_all]
    metas = [by_id[w] for w in wanted]
    attach_related(metas)
    out: dict[str, str] = {}
    for m in metas:
        out[page_rel_path(m["pid"], m["ptype"])] = render_page(m)
    out["index.md"] = render_index(metas)
    out["schema.md"] = SCHEMA
    return out


def render_log(existing: str, metas: list[dict]) -> str:
    """只追加缺失的 ingest 条目；已有内容原样保留。"""
    header = "# Wiki 操作账本（log.md）\n\n> 只追加；前缀 `## [YYYY-MM-DD] <op> | <标题>` 可被 `grep '^## \\['` 解析（R1 spec §5）。\n"
    text = existing if existing else header
    for m in metas:
        tag = "## [" + UPDATED + "] ingest | " + m["pid"]
        if tag in text:
            continue
        entry = [
            "",
            tag,
            "- page: " + page_rel_path(m["pid"], m["ptype"]),
            "- units: " + ", ".join(m["raw_refs"]),
            "- qids: " + ", ".join(m["qids"]),
            "- result: ok (serial, one unit at a time)",
            "- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出",
        ]
        text = text.rstrip("\n") + "\n" + "\n".join(entry) + "\n"
    return text


def cmd_build(pages_filter: list[str] | None) -> int:
    if LOCK.exists():
        print("FATAL: 已存在锁 " + str(LOCK) + "（另一写入者正在编译，拒绝抢写）")
        return 1
    WIKI.mkdir(parents=True, exist_ok=True)
    LOCK.write_text("pid=" + str(sys.argv) + "\n", "utf-8")
    try:
        out = build(pages_filter)
        # 先写页面 + index + schema
        for rel, body in sorted(out.items()):
            path = WIKI / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, "utf-8")
            print("wrote wiki/" + rel + "  " + str(len(body.encode("utf-8"))) + " bytes")
        # 再追加 log（读旧 → 追加缺失条目）
        log_path = WIKI / "log.md"
        old = log_path.read_text("utf-8") if log_path.exists() else ""
        records, pages = load_plan()
        metas = [page_meta(p, set()) for p in pages]
        by_id = {m["pid"]: m for m in metas}
        wanted = pages_filter or list(by_id)
        metas = [by_id[w] for w in wanted]
        log_path.write_text(render_log(old, metas), "utf-8")
        print("wrote wiki/log.md（append-only）")
        return 0
    finally:
        if LOCK.exists():
            LOCK.unlink()


def cmd_check() -> int:
    out = build(None)
    problems: list[str] = []
    for rel, body in sorted(out.items()):
        if rel == "index.md" or rel == "schema.md":
            continue
        path = WIKI / rel
        if not path.exists():
            problems.append("缺少页面: wiki/" + rel)
        elif path.read_text("utf-8") != body:
            problems.append("内容不一致（非幂等或手改）: wiki/" + rel)
    if problems:
        print("CHECK FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("CHECK OK: " + str(len(out) - 2) + " 页可逐字节复现（仅校验 --all 视图，样张子集见 git 状态）")
    return 0


USAGE_EXIT = 2


def usage_error(msg: str) -> int:
    print("FATAL: " + msg, file=sys.stderr)
    print("用法：compile_wiki.py build --pages <id1,id2,...>  或  build --all", file=sys.stderr)
    return USAGE_EXIT


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "build"
    if cmd == "build":
        pages_arg: list[str] | None = None
        all_flag = False
        i = 2
        while i < len(argv):
            a = argv[i]
            if a == "--all":
                all_flag = True
                i += 1
                continue
            if a == "--pages":
                if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
                    return usage_error("--pages 后必须跟至少一个 page id（本次为空值）")
                raw = argv[i + 1]
                ids = [x.strip() for x in raw.split(",") if x.strip()]
                if not ids:
                    return usage_error(
                        "--pages 的值为空：必须给出至少一个 page id；"
                        "若确实要全量重建请显式使用 --all"
                    )
                pages_arg = ids
                i += 2
                continue
            return usage_error("未知参数: " + a)
        if all_flag and pages_arg:
            return usage_error("--all 与 --pages 不能同时使用")
        if not all_flag and not pages_arg:
            return usage_error(
                "必须显式指定构建范围：--pages <id,...> 或 --all"
                "（不提供任何选择器就等于“全量重写”，已禁止）"
            )
        return cmd_build(pages_arg)
    if cmd == "check":
        return cmd_check()
    if cmd == "order":
        _records, pages2 = load_plan()
        for pg in pages2:
            print(pg["page_id"])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
