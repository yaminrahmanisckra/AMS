#!/usr/bin/env python3
"""
Parse LLB_Curriculum (Revised 7 Feb 2023).docx to infer Part A/B/C/D structure.
Output: structure note for Curriculator data model and UI.
"""
import os
import sys

# Ensure project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DOCX_PATH = os.path.join(
    os.path.expanduser("~"),
    "Library", "CloudStorage", "OneDrive-ku.ac.bd",
    "Syllabus Update 1 July 2022",
    "LLB_Curriculum (Revised 7 Feb 2023).docx",
)


def main():
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    if not os.path.isfile(DOCX_PATH):
        print(f"File not found: {DOCX_PATH}")
        return

    doc = Document(DOCX_PATH)
    out = []

    def style_name(p):
        return (p.style and p.style.name) or ""

    def is_heading(p):
        n = style_name(p)
        return "heading" in n.lower() or "Heading" in n

    def heading_level(p):
        n = style_name(p)
        for i in range(1, 10):
            if f"Heading {i}" in n or f"heading {i}" in n:
                return i
        return 0

    i = 0
    part_boundaries = []  # (idx, "Part X", level)
    tables_seen = 0
    part_tables = {}  # part -> list of (idx, num_cols, num_rows, preview)

    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag
        if tag == "p":
            para = Paragraph(block, doc)
            text = (para.text or "").strip()
            style = style_name(para)
            lvl = heading_level(para)
            t = text.upper()
            if "PART A" in t or "PART B" in t or "PART C" in t or "PART D" in t:
                for label in ("Part A", "Part B", "Part C", "Part D"):
                    if label.upper() in t:
                        part_boundaries.append((i, label, lvl))
                        break
            if text and (is_heading(para) or "part" in text.lower()):
                out.append(f"[{i}] Lvl={lvl} Style={style!r} | {text[:120]}")
            i += 1
        elif tag == "tbl":
            tbl = Table(block, doc)
            rows, cols = len(tbl.rows), len(tbl.columns)
            preview = []
            for r in tbl.rows[:2]:
                row_text = [c.text.strip()[:30] for c in r.cells[:5]]
                preview.append(" | ".join(row_text))
            tables_seen += 1
            # Associate with current part (last part boundary before this)
            current = part_boundaries[-1][1] if part_boundaries else "Preamble"
            if current not in part_tables:
                part_tables[current] = []
            part_tables[current].append((tables_seen, cols, rows, preview))
            out.append(f"[TBL {tables_seen}] {rows}x{cols} (part ~{current})")
            for p in preview:
                out.append(f"    {p}")
            i += 1

    # Summary
    lines = [
        "# LLB Curriculum DOCX structure (inferred)",
        "",
        "## Part boundaries (headings containing 'Part A/B/C/D')",
    ]
    for idx, label, lvl in part_boundaries:
        lines.append(f"- {label} at block index {idx}, heading level {lvl}")

    lines.extend([
        "",
        "## Tables per part",
    ])
    for part in ("Part A", "Part B", "Part C", "Part D", "Preamble"):
        if part in part_tables:
            lst = part_tables[part]
            lines.append(f"- **{part}**: {len(lst)} table(s)")
            for tnum, c, r, prev in lst[:5]:
                lines.append(f"  - Table {tnum}: {r} rows x {c} cols")
                for p in prev[:2]:
                    lines.append(f"      {p[:80]}")

    lines.extend([
        "",
        "## Sample headings / part-related paragraphs",
    ])
    lines.extend(out[:80])

    result = "\n".join(lines)
    print(result)

    note_path = os.path.join(ROOT, "CURRICULUM_DOCX_STRUCTURE.md")
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"\nWrote {note_path}")


if __name__ == "__main__":
    main()
