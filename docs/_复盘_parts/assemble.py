#!/usr/bin/env python3
"""把 docs/_复盘_parts/*.md 按 <!-- CHn --> 占位符拼进 docs/实现过程复盘.md。可增量重复运行。"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAIN = ROOT / "docs" / "实现过程复盘.md"
PARTS = pathlib.Path(__file__).resolve().parent

main = MAIN.read_text(encoding="utf-8")
filled, remaining = [], sorted(set(re.findall(r"<!-- (CH\d+) -->", main)))

for pf in sorted(PARTS.glob("*.md")):
    text = pf.read_text(encoding="utf-8")
    chunks = re.split(r"^<!-- (CH\d+) -->\s*$", text, flags=re.M)
    # chunks: ['', 'CH4', body, 'CH2', body, ...]
    for tag, body in zip(chunks[1::2], chunks[2::2]):
        body = body.strip("\n")
        lines = body.split("\n")
        if lines and lines[0].startswith("## "):   # 剥掉 part 里重复的章节标题（主文件已有）
            lines = lines[1:]
            while lines and not lines[0].strip():
                lines = lines[1:]
        body = "\n".join(lines).strip("\n")
        ph = f"<!-- {tag} -->"
        if ph in main:
            main = main.replace(ph, body)
            filled.append(f"{tag}←{pf.name}({len(lines)}行)")
            if tag in remaining:
                remaining.remove(tag)
        else:
            print(f"[skip] {tag} in {pf.name}: 主文件已无占位符（已填过？）", file=sys.stderr)

MAIN.write_text(main, encoding="utf-8")
print("filled:", ", ".join(filled) or "(none)")
print("remaining placeholders:", ", ".join(remaining) or "(none)")
print("main lines:", main.count("\n") + 1)
