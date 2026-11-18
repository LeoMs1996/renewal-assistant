#!/usr/bin/env python3
"""D2：把 D1 抽样子集规范化成 LLM-Wiki 的 raw 源层（**不改写、不摘要、不翻译**）。

只读：data/ins-mmbench/raw/<split>/records.jsonl 与其引用的图片
只写：data/llm-wiki-claims/raw/sources/*.json、data/llm-wiki-claims/raw/manifest.json、
      data/llm-wiki-claims/plan.md

幂等：产物不含时间戳、不含随机数、不含运行顺序依赖；同一输入连跑两次逐字节一致。

用法：
    python3 data/llm-wiki-claims/scripts/normalize_raw.py build   # 生成（默认）
    python3 data/llm-wiki-claims/scripts/normalize_raw.py check   # 只校验，不写盘；不一致 exit 1
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

# ---------------------------------------------------------------- 常量（纯静态，无环境依赖）

ROOT = pathlib.Path(__file__).resolve().parents[3]  # renewal-assistant/
IN_ROOT = ROOT / "data" / "ins-mmbench" / "raw"
OUT_ROOT = ROOT / "data" / "llm-wiki-claims"
SOURCES_DIR = OUT_ROOT / "raw" / "sources"
MANIFEST_PATH = OUT_ROOT / "raw" / "manifest.json"
PLAN_PATH = OUT_ROOT / "plan.md"

SCHEMA_VERSION = "d2-raw-1.0"
# 固定分片顺序 = D3 的串行 ingest 顺序（不由文件系统枚举顺序决定）
SPLIT_ORDER = ["claim", "agri", "health", "liability", "property"]

DATASET = "FDU-INS/INS-MMBench"
LICENSE = "apache-2.0"

# 三层切分的第三层：主题。键取自各分片实测 labels 字段（见 D1 报告），不自造。
THEMES: dict[str, list[dict[str, object]]] = {
    "claim": [
        {"slug": "policy-validity", "title": "保单有效期与失效", "keys": ["Expiry_date", "expired"]},
        {"slug": "coverage-limits", "title": "保额上下限", "keys": ["Min_coverage", "Max_coverage"]},
        {"slug": "loss-amount", "title": "损失金额与严重程度", "keys": ["Amount", "Severity"]},
        {"slug": "vehicle-condition", "title": "车辆条件与车值", "keys": ["Condition", "Cost_of_vehicle"]},
    ],
    "liability": [
        {"slug": "accident-occurrence", "title": "是否构成事故", "keys": ["whether an accident occurred"]},
        {"slug": "causation", "title": "事故成因与主责", "keys": ["causes", "primary_responsibility"]},
        {"slug": "scene-context", "title": "道路场景与路段形态", "keys": ["scenes", "linear"]},
        {"slug": "environment", "title": "天气与光照条件", "keys": ["weather", "light"]},
    ],
    "agri": [
        {"slug": "insured-subject", "title": "标的物种与数量", "keys": ["species", "count"]},
        {"slug": "infection-status", "title": "病害感染判定", "keys": ["infection"]},
        {"slug": "compensation-tier", "title": "赔付档位", "keys": ["claim"]},
    ],
    "health": [
        {"slug": "imaging-part", "title": "影像部位", "keys": ["part"]},
        {"slug": "report-consistency", "title": "报告一致性", "keys": ["original_report", "adjusted_report", "match"]},
        {"slug": "risk-level", "title": "风险等级", "keys": ["risk_level"]},
        {"slug": "underwriting-decision", "title": "核保决定", "keys": ["underwriting_decision"]},
    ],
    "property": [
        {"slug": "disaster-type", "title": "灾种识别", "keys": ["disaster", "type"]},
        {"slug": "damage-count", "title": "受灾与损失计数", "keys": ["number", "damage_number"]},
        {"slug": "claim-decision", "title": "理赔决定", "keys": ["claim_decision"]},
    ],
}

# 跨主题的概念实体页（entity）。keys 用于自动计算 source_refs（出现该字段的 raw 单元）。
ENTITIES: list[dict[str, object]] = [
    {"slug": "coverage-limit", "title": "保额与赔付上限", "aliases": ["Min_coverage", "Max_coverage"],
     "keys": ["Min_coverage", "Max_coverage"]},
    {"slug": "policy-expiry", "title": "保单有效期", "aliases": ["Expiry_date", "expired"],
     "keys": ["Expiry_date", "expired"]},
    {"slug": "loss-severity", "title": "损失严重程度", "aliases": ["Severity"], "keys": ["Amount", "Severity"]},
    {"slug": "primary-responsibility", "title": "事故主责判定", "aliases": ["primary_responsibility"],
     "keys": ["primary_responsibility", "causes"]},
    {"slug": "infection-status", "title": "病害感染判定", "aliases": ["infection"], "keys": ["infection"]},
    {"slug": "compensation-tier", "title": "赔付档位", "aliases": ["claim"], "keys": ["claim"]},
    {"slug": "report-consistency", "title": "报告一致性", "aliases": ["match"],
     "keys": ["match", "original_report", "adjusted_report"]},
    {"slug": "underwriting-decision", "title": "核保决定", "aliases": ["underwriting_decision"],
     "keys": ["underwriting_decision", "risk_level"]},
    {"slug": "claim-decision", "title": "理赔决定", "aliases": ["claim_decision"], "keys": ["claim_decision"]},
]

# 每个任务一条 FAQ（问句取自 question 模板的评判要求，不新增事实）
FAQS: dict[str, dict[str, str]] = {
    "claim": {"title": "车损理赔金额如何受保额与损失金额约束？",
              "question": "给定车辆价值、保单保额上下限与损失金额，理赔金额与严重程度如何对应？"},
    "liability": {"title": "如何判定事故是否发生以及主责归属？",
                  "question": "仅凭连续行车记录仪图像，如何逐步判定是否发生事故、成因与主要责任方？"},
    "agri": {"title": "农业保险赔付档位如何确定？",
             "question": "给定标的物种、数量与病害感染情况，赔付档位（不赔/部分/全额）如何确定？"},
    "health": {"title": "影像报告与核保决定如何对应？",
               "question": "给定影像部位与放射科报告，报告一致性、风险等级与核保决定如何推定？"},
    "property": {"title": "财产险理赔决定如何判定？",
                 "question": "给定灾前灾后卫星图像，灾种、受灾与损失计数、理赔决定如何判定？"},
}

# 分片 → 任务标识（用于页面 id，稳定且短）
SPLIT_SLUG = {
    "claim": "claim",
    "liability": "liability",
    "agri": "agri",
    "health": "health",
    "property": "property",
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(t: str) -> str:
    return sha256_bytes(t.encode("utf-8"))


def dump_json(obj: object) -> bytes:
    """确定性 JSON：固定缩进、不转义中文、保持构造顺序。"""
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


# ---------------------------------------------------------------- 读输入


def load_split(split: str) -> list[dict[str, object]]:
    path = IN_ROOT / split / "records.jsonl"
    if not path.exists():
        raise SystemExit(f"FATAL: 输入缺失 {path}")
    raw = path.read_bytes()
    rows: list[dict[str, object]] = []
    for lineno, line in enumerate(raw.split(b"\n"), start=1):
        if not line.strip():
            continue
        rec = json.loads(line)
        rows.append({"line": lineno, "rec": rec, "line_bytes": line})
    return rows


# ---------------------------------------------------------------- 构造 raw 源文件


def build_source(split: str, row: dict[str, object], ingest_order: int) -> dict[str, object]:
    rec: dict[str, object] = row["rec"]  # type: ignore[assignment]
    source_index = str(rec["source_index"])
    raw_id = f"raw-{split}-{int(source_index):04d}"

    question = str(rec["question"])
    q_lines = question.count("\n") + 1

    images: list[dict[str, object]] = []
    for im in rec["images"]:  # type: ignore[union-attr]
        asset_ref = f"data/ins-mmbench/raw/{im['path']}"
        asset_path = ROOT / asset_ref
        if not asset_path.exists():
            raise SystemExit(f"FATAL: 图片缺失 {asset_ref}（raw_id={raw_id}）")
        disk_sha = sha256_bytes(asset_path.read_bytes())
        if disk_sha != im["sha256"]:
            raise SystemExit(f"FATAL: 图片 sha256 不一致 {asset_ref}（raw_id={raw_id}）")
        images.append(
            {
                "path": im["path"],
                "bytes": im["bytes"],
                "sha256": im["sha256"],
                "asset_ref": asset_ref,
                "asset_sha256_verified": True,
            }
        )

    labels: dict[str, object] = dict(rec["labels"])  # type: ignore[arg-type]
    return {
        "schema_version": SCHEMA_VERSION,
        "raw_id": raw_id,
        "unit": {
            "unit_id": raw_id,
            "kind": "record",
            "sub_units": ["question", "labels", "images"],
            "ingest_order": ingest_order,
        },
        "source": {
            "dataset": DATASET,
            "revision": rec["source_revision"],
            "license": LICENSE,
            "split": split,
            "source_file": rec["source_file"],
            "source_index": source_index,
            "record_id": rec["id"],
            "records_path": f"data/ins-mmbench/raw/{split}/records.jsonl",
            "records_line": row["line"],
            "record_line_sha256": sha256_bytes(row["line_bytes"]),  # type: ignore[arg-type]
        },
        "sample": {
            "insurance_type": rec["insurance_type"],
            "task_layer": rec["task_layer"],
            "task_name": rec["task_name"],
            "meta_task": rec["meta_task"],
        },
        "content": {
            "question": {
                "text": question,
                "chars": len(question),
                "lines": q_lines,
                "sha256": sha256_text(question),
            },
            "options": rec["options"],
            "answer": rec["answer"],
        },
        "answer_status": "absent_in_source",
        "labels": labels,
        "images": images,
        "spans": {
            "question": {
                "scheme": "line",
                "start_line": 1,
                "end_line": q_lines,
                "char_start": 0,
                "char_end": len(question),
            },
            "labels": {"scheme": "json_path", "paths": [f"labels.{k}" for k in labels]},
            "images": {"scheme": "asset", "refs": [im["asset_ref"] for im in images]},
        },
    }


# ---------------------------------------------------------------- 页面计划（三层切分）


def build_plan_rows(
    records_by_split: dict[str, list[dict[str, object]]],
) -> tuple[list[dict[str, object]], dict[str, list[str]]]:
    """返回 (页面清单, raw_id → 引用它的页面 id 列表)。"""
    pages: list[dict[str, object]] = []
    used_by: dict[str, list[str]] = {}

    def raw_ids_of_split(split: str) -> list[str]:
        return [f"raw-{split}-{int(str(r['rec']['source_index'])):04d}" for r in records_by_split[split]]  # type: ignore[index]

    def task_name_of(split: str) -> str:
        return str(records_by_split[split][0]["rec"]["task_name"])  # type: ignore[index]

    def insurance_type_of(split: str) -> str:
        return str(records_by_split[split][0]["rec"]["insurance_type"])  # type: ignore[index]

    def add(page: dict[str, object]) -> None:
        pages.append(page)
        for rid in page["source_refs"]:  # type: ignore[union-attr]
            used_by.setdefault(str(rid), []).append(str(page["page_id"]))

    # 第一层：保险类型 → 一个 doc 页
    by_type: dict[str, list[str]] = {}
    for split in SPLIT_ORDER:
        by_type.setdefault(insurance_type_of(split), []).append(split)
    for itype in sorted(by_type):
        splits = by_type[itype]
        add(
            {
                "page_id": f"claims-doc-ins-mmbench-{itype}",
                "type": "doc",
                "title": f"INS-MMBench 子集：{itype} 保险样本总览",
                "layer": f"{itype}",
                "source_refs": [rid for s in splits for rid in raw_ids_of_split(s)],
                "themes": [t["title"] for s in splits for t in THEMES[s]],
            }
        )

    # 第二层：任务层级（本子集全为 scenario）→ 第三层：主题 → section 页
    for split in SPLIT_ORDER:
        itype = insurance_type_of(split)
        task = task_name_of(split)
        for theme in THEMES[split]:
            add(
                {
                    "page_id": f"claims-section-{SPLIT_SLUG[split]}-{theme['slug']}",
                    "type": "section",
                    "title": f"{theme['title']}（{task}）",
                    "layer": f"{itype} > scenario > {theme['slug']}",
                    "source_refs": raw_ids_of_split(split),
                    "themes": [theme["title"]],
                    "label_keys": list(theme["keys"]),  # type: ignore[arg-type]
                }
            )

    # 实体页：按 label 字段反查出现过的 raw 单元
    for ent in ENTITIES:
        keys = list(ent["keys"])  # type: ignore[arg-type]
        refs: list[str] = []
        for split in SPLIT_ORDER:
            for row in records_by_split[split]:
                labels = row["rec"]["labels"]  # type: ignore[index]
                if any(k in labels for k in keys):
                    refs.append(f"raw-{split}-{int(str(row['rec']['source_index'])):04d}")  # type: ignore[index]
        add(
            {
                "page_id": f"claims-entity-{ent['slug']}",
                "type": "entity",
                "title": str(ent["title"]),
                "layer": "跨任务实体",
                "source_refs": refs,
                "themes": [str(ent["title"])],
                "label_keys": keys,
            }
        )

    # FAQ 页
    for split in SPLIT_ORDER:
        faq = FAQS[split]
        add(
            {
                "page_id": f"claims-faq-{SPLIT_SLUG[split]}",
                "type": "faq",
                "title": faq["title"],
                "layer": f"{insurance_type_of(split)} > scenario > faq",
                "source_refs": raw_ids_of_split(split),
                "themes": [faq["question"]],
            }
        )

    return pages, used_by


# ---------------------------------------------------------------- plan.md


def build_plan_md(
    records_by_split: dict[str, list[dict[str, object]]],
    pages: list[dict[str, object]],
    used_by: dict[str, list[str]],
    ingest_order: list[str],
) -> bytes:
    n_src = sum(len(v) for v in records_by_split.values())
    n_img = sum(len(r["rec"]["images"]) for v in records_by_split.values() for r in v)  # type: ignore[union-attr]
    by_type: dict[str, int] = {}
    by_task: dict[str, int] = {}
    for split in SPLIT_ORDER:
        for row in records_by_split[split]:
            by_type[str(row["rec"]["insurance_type"])] = by_type.get(str(row["rec"]["insurance_type"]), 0) + 1  # type: ignore[index]
            by_task[str(row["rec"]["task_name"])] = by_task.get(str(row["rec"]["task_name"]), 0) + 1  # type: ignore[index]

    L: list[str] = []
    L.append("# 理赔域 LLM-Wiki 萃取计划（D2 产出 · D3 执行契约）")
    L.append("")
    L.append("> 生成方式：`python3 data/llm-wiki-claims/scripts/normalize_raw.py build`（**勿手改**，改脚本重跑）。")
    L.append("> 规范依据：`docs/research/llmwiki-spec.md`（R1 定稿）；本文件只做「切分与顺序」，不定义新 schema。")
    L.append(f"> 数据来源：INS-MMBench 子集，revision pin `{records_by_split[SPLIT_ORDER[0]][0]['rec']['source_revision']}`，许可 Apache-2.0。")  # type: ignore[index]
    L.append("")
    L.append("## 1. 规模与输入")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| raw 源单元（单元=1 条记录） | **{n_src}** |")
    L.append(f"| 引用图片 | **{n_img}**（磁盘已逐张 sha256 校验） |")
    L.append(f"| 分片 | {', '.join(f'{s}={len(records_by_split[s])}' for s in SPLIT_ORDER)} |")
    L.append(f"| 保险类型 | {', '.join(f'{k}={v}' for k, v in sorted(by_type.items()))} |")
    L.append(f"| 任务 | {', '.join(f'{k}={v}' for k, v in sorted(by_task.items()))} |")
    L.append(f"| 计划页面 | **{len(pages)}**（doc/section/entity/faq 四类；query 由 D4 事后回写） |")
    L.append("")
    L.append("## 2. 萃取单元决策：单元 = 一条记录（54 个单元）")
    L.append("")
    L.append("**决策**：一个 raw 源单元 = D1 的一条抽样记录，`unit_id = raw_id = raw-<split>-<source_index:04d>`。")
    L.append("")
    L.append("**理由（可机械执行，不需要 D3 再判断）**：")
    L.append("")
    L.append("1. 一条记录本身就自洽：`question`（任务与规则文本）+ `labels`（事实字段）+ `images`（视觉证据）三者互相解释；只取 `labels` 会失去「这条事实在什么任务语境下成立」，只取 `question` 会失去全部事实。")
    L.append("2. 记一条 = 一个 ingest 事务，正好匹配「一次只编译一个来源」的串行纪律（R1 spec §8）：取一次锁、写一次日志、跑一次 lint，读写边界清晰。")
    L.append("3. 若再按字段组拆（question 单元 / labels 单元），单元数翻倍到 108，同一事实会跨两个单元落地，容易产生两边互不同步的实体页——反而放大 R1 spec 里点名的「共享状态冲突」问题。")
    L.append("")
    L.append("**被否决方案**：按字段组拆单元。否决理由见上第 3 条；字段组的可引用性改由 **span 方案**解决（见 §5），不必靠拆单元实现。")
    L.append("")
    L.append("## 3. 三层切分：保险类型 → 任务层级 → 主题")
    L.append("")
    L.append("> **诚实说明**：本子集 54 条的 `task_layer` **全为 `scenario`**、`meta_task` 全为 null（D1 实测）。")
    L.append("> 因此「任务层级」这一层在本子集只有一个取值，第二层的实际区分度落在 `task_name`（5 个场景任务）上。")
    L.append("> 保留该层是为了与全量数据集的 `fundamental / meta_task` 层级对齐，避免日后扩样时改 schema。")
    L.append("")
    L.append("| 保险类型 | 任务层级 | 任务（task_name） | 分片 | 单元数 | 主题（第三层） |")
    L.append("|---|---|---|---|---|---|")
    for split in SPLIT_ORDER:
        row0 = records_by_split[split][0]
        itype = row0["rec"]["insurance_type"]  # type: ignore[index]
        task = row0["rec"]["task_name"]  # type: ignore[index]
        themes = "、".join(str(t["title"]) for t in THEMES[split])
        L.append(f"| {itype} | scenario | `{task}` | {split} | {len(records_by_split[split])} | {themes} |")
    L.append("")
    L.append("## 4. 页面清单（D3 按此顺序产出）")
    L.append("")
    L.append("| # | page_id | type | 标题 | 层级路径 | source_refs（全部单元 id） |")
    L.append("|---|---|---|---|---|---|")
    for i, page in enumerate(pages, start=1):
        refs = page["source_refs"]
        L.append(
            f"| {i} | `{page['page_id']}` | {page['type']} | {page['title']} | "
            f"{page['layer']} | {len(refs)}: " + ", ".join(f"`{r}`" for r in refs) + " |"  # type: ignore[index]
        )
    L.append("")
    L.append("### 4.1 单元 → 页面（D3 每编译一个单元要碰的页面）")
    L.append("")
    L.append("按 `ingest_order` 列出；D3 编译第 N 个单元时，只允许写这个表里列出的页面（新增页面需先改 `plan.md` 的生成器并重跑）。")
    L.append("")
    L.append("| # | raw_id | 本章元要写入的页面 |")
    L.append("|---|---|---|")
    for order_i, rid in enumerate(ingest_order, start=1):
        L.append(f"| {order_i} | `{rid}` | " + ", ".join(f"`{p}`" for p in used_by[rid]) + " |")
    L.append("")
    L.append("每条 `section` 页的产出要求：正文断言逐条带 `⟦S:<raw_id>@<span>⟧`（span 写法见 §5），")
    L.append("frontmatter 九项必填（R1 spec §3.1），`source_refs` 不得超出上表列出的集合（超集即 lint L6 失败）。")
    L.append("")
    L.append("## 5. 引用语法（本语料的两种 span）")
    L.append("")
    L.append("| 证据类型 | 写法 | 说明 |")
    L.append("|---|---|---|")
    L.append("| 题干行 | `⟦S:raw-claim-0000@L3-L7⟧` | `content.question.text` 按 `\\n` 切分的**行号**，1-based 含端点；每单元 13–17 行 |")
    L.append("| 标签字段 | `⟦S:raw-claim-0000@labels.Amount⟧` | `labels` 的 JSON 路径；值必须与源文件逐字一致 |")
    L.append("| 图片 | `⟦S:raw-claim-0000@claim/0/0.jpg⟧` | 用 `images[].path`；sha256 已在 manifest 固定 |")
    L.append("")
    L.append("## 6. 覆盖自检（生成时自动计算）")
    L.append("")
    L.append("| 检查 | 结果 |")
    L.append("|---|---|")
    uncovered = [rid for rid in sorted(used_by) if not used_by[rid]]
    n_refs = sum(len(v) for v in used_by.values())
    L.append(f"| 每个 raw 单元至少被 1 个页面引用 | {'PASS' if not uncovered else 'FAIL: ' + ','.join(uncovered)} |")
    L.append(f"| 被引用单元数 / 总单元数 | {len(used_by)} / {n_src} |")
    L.append(f"| 引用总次数（含重复引用） | {n_refs} |")
    L.append(f"| 覆盖保险类型数 | {len(by_type)} / {len(by_type)}（{', '.join(sorted(by_type))}） |")
    L.append(f"| 覆盖任务数 | {len(by_task)} |")
    L.append("")
    L.append("## 7. D3 执行契约（照做即可，无需再判断）")
    L.append("")
    L.append("1. **顺序**：严格按 `raw/manifest.json` 的 `ingest_order` 逐单元编译（与 §4 表序一致），**一次一个单元**。")
    L.append("2. **加锁**：`data/llm-wiki-claims/wiki/.ingest.lock`（写 `pid` + 开始时间），取不到锁则排队，禁止并发写。")
    L.append("3. **单事务**：读源 → 写/改页面 → 双向 `related` → 重建 `index.md` → 追加 `log.md` → lint → 释放锁。")
    L.append("4. **幂等**：`log.md` 已有 `ingest | <raw_id>` 的单元不得重编（R1 spec §8 第 4 步）。")
    L.append("5. **禁止**：写 `data/llm-wiki-claims/wiki/` 以外的知识路径；写 `renewal-assistant/wiki/`、`server/`、`traces/`；改写 `raw/`。")
    L.append("6. **无答案**：54 单元 `answer` 均为 null（场景分片本身无 answer 列），页面只写「样本给出的字段事实 + 题干规则」，")
    L.append("   **禁止**编造标准答案；D5 只评检索指标（台账 D-04）。")
    L.append("")
    L.append("## 8. 已知限制")
    L.append("")
    L.append("| # | 限制 | 影响 / 处置 |")
    L.append("|---|---|---|")
    L.append("| 1 | 图片未复制进 `raw/assets/`，只记 `asset_ref` + sha256 | 避免 33 MiB 重复；但 `data/ins-mmbench/**` 被 gitignore，**新 clone 无图片** |")
    L.append("| 2 | 本子集 `task_layer` 单一（全 scenario）、部分标签单一值（如 `Severity` 全 minor） | 不得据此算分类准确率；只评检索与引用接地 |")
    L.append("| 3 | liability 12 条非严格 head-k（index 0–20 间 12 条） | 偏差敏感分析须按 `source.source_index` 追溯（manifest 已留） |")
    L.append("| 4 | `property` 的 `claim_decision` 覆盖面 No/Partial/Full | 是否可作 GT 待 D2/D5 判定（台账 O-02）；本步不改写、不判定 |")
    L.append("")
    return ("\n".join(L) + "\n").encode("utf-8")


# ---------------------------------------------------------------- 主流程


def build_all() -> dict[str, bytes]:
    """在内存里构造全部产物：relpath → bytes（不落盘）。"""
    records_by_split: dict[str, list[dict[str, object]]] = {}
    for split in SPLIT_ORDER:
        records_by_split[split] = load_split(split)

    artifacts: dict[str, bytes] = {}
    sources_meta: list[dict[str, object]] = []
    ingest_order: list[str] = []
    order = 0

    for split in SPLIT_ORDER:
        rows = records_by_split[split]
        # 单元内按 source_index 升序；source_index 必须唯一（否则 raw_id 冲突）
        idxs = [int(str(r["rec"]["source_index"])) for r in rows]  # type: ignore[index]
        if len(idxs) != len(set(idxs)):
            raise SystemExit(f"FATAL: {split} 的 source_index 有重复：{sorted(idxs)}")
        for row in sorted(rows, key=lambda r: int(str(r["rec"]["source_index"]))):  # type: ignore[index]
            order += 1
            src = build_source(split, row, order)
            raw_id = str(src["raw_id"])
            rel = f"raw/sources/{raw_id}.json"
            body = dump_json(src)
            artifacts[rel] = body
            ingest_order.append(raw_id)
            images = src["images"]
            sources_meta.append(
                {
                    "raw_id": raw_id,
                    "file": rel,
                    "sha256": sha256_bytes(body),
                    "split": split,
                    "source_index": src["source"]["source_index"],  # type: ignore[index]
                    "record_id": src["source"]["record_id"],  # type: ignore[index]
                    "records_line": src["source"]["records_line"],  # type: ignore[index]
                    "record_line_sha256": src["source"]["record_line_sha256"],  # type: ignore[index]
                    "insurance_type": src["sample"]["insurance_type"],  # type: ignore[index]
                    "task_layer": src["sample"]["task_layer"],  # type: ignore[index]
                    "task_name": src["sample"]["task_name"],  # type: ignore[index]
                    "question_chars": src["content"]["question"]["chars"],  # type: ignore[index]
                    "question_lines": src["content"]["question"]["lines"],  # type: ignore[index]
                    "question_sha256": src["content"]["question"]["sha256"],  # type: ignore[index]
                    "labels_keys": list(src["labels"]),  # type: ignore[arg-type]
                    "images": [
                        {"path": im["path"], "bytes": im["bytes"], "sha256": im["sha256"], "asset_ref": im["asset_ref"]}
                        for im in images  # type: ignore[union-attr]
                    ],
                }
            )

    pages, used_by = build_plan_rows(records_by_split)

    by_split: dict[str, int] = {s: len(records_by_split[s]) for s in SPLIT_ORDER}
    by_type: dict[str, int] = {}
    by_task: dict[str, int] = {}
    for split in SPLIT_ORDER:
        for row in records_by_split[split]:
            t = str(row["rec"]["insurance_type"])  # type: ignore[index]
            n = str(row["rec"]["task_name"])  # type: ignore[index]
            by_type[t] = by_type.get(t, 0) + 1
            by_task[n] = by_task.get(n, 0) + 1

    n_images = sum(len(s["images"]) for s in sources_meta)  # type: ignore[arg-type]
    uncovered = [rid for rid in ingest_order if rid not in used_by]
    if uncovered:
        raise SystemExit(f"FATAL: 以下单元未被任何计划页面引用：{uncovered}")
    if set(by_type) != {"auto", "agricultural", "health", "property"}:
        raise SystemExit(f"FATAL: 保险类型覆盖异常：{sorted(by_type)}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator": "data/llm-wiki-claims/scripts/normalize_raw.py",
        "dataset": DATASET,
        "revision": records_by_split[SPLIT_ORDER[0]][0]["rec"]["source_revision"],  # type: ignore[index]
        "license": LICENSE,
        "source_of_truth": "data/ins-mmbench/raw/<split>/records.jsonl（本清单由它派生，不是手写）",
        "unit_policy": {
            "unit": "record",
            "unit_id": "raw-<split>-<source_index:04d>",
            "sub_units": ["question", "labels", "images"],
            "ingest": "serial，一次一个 unit，顺序见 ingest_order",
        },
        "counts": {
            "sources": len(sources_meta),
            "images": n_images,
            "by_split": by_split,
            "by_insurance_type": by_type,
            "by_task_name": by_task,
            "planned_pages": len(pages),
        },
        "coverage": {
            "units_referenced_by_plan": len(used_by),
            "units_total": len(sources_meta),
            "insurance_types": sorted(by_type),
        },
        "ingest_order": ingest_order,
        "sources": sources_meta,
    }
    artifacts["raw/manifest.json"] = dump_json(manifest)
    artifacts["plan.md"] = build_plan_md(records_by_split, pages, used_by, ingest_order)
    return artifacts


def cmd_build() -> int:
    artifacts = build_all()
    for rel, body in sorted(artifacts.items()):
        path = OUT_ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        print(f"wrote {rel}  {len(body)} bytes  sha256={sha256_bytes(body)[:16]}…")
    print(f"\nOK: {len(artifacts)} 个产物已写入 {OUT_ROOT}")
    return 0


def cmd_check() -> int:
    artifacts = build_all()
    problems: list[str] = []
    for rel, body in sorted(artifacts.items()):
        path = OUT_ROOT / rel
        if not path.exists():
            problems.append(f"缺少产物 {rel}")
        elif path.read_bytes() != body:
            problems.append(f"内容不一致（非幂等或被人手改）: {rel}")
    # 多余源文件（孤立）
    if SOURCES_DIR.exists():
        expected = {pathlib.Path(rel).name for rel in artifacts if rel.startswith("raw/sources/")}
        for p in sorted(SOURCES_DIR.glob("*.json")):
            if p.name not in expected:
                problems.append(f"孤立源文件（不在清单里）: raw/sources/{p.name}")
    if problems:
        print("CHECK FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    n = len([r for r in artifacts if r.startswith("raw/sources/")])
    print(f"CHECK OK: {n} 个源文件与清单一致、内容逐字节可复现、无孤立文件")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "build"
    if cmd == "build":
        return cmd_build()
    if cmd == "check":
        return cmd_check()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
