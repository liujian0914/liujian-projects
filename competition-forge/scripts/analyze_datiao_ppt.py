#!/usr/bin/env python3
"""分析大挑案例 PPT（PDF 形态）的结构与风格，输出可提炼的规律。

用法：python analyze_datiao_ppt.py <输出目录>
"""
import sys
import re
import json
import pathlib
from collections import Counter

import pymupdf

CASES_ROOT = pathlib.Path(r"C:\Users\hp\Desktop\大挑案例")


def find_ppt_pdfs():
    out = []
    for p in CASES_ROOT.rglob("*PPT*.pdf"):
        out.append(p)
    return sorted(out)


def analyze_one(pdf_path: pathlib.Path) -> dict:
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        # 收集这一页的填充色（粗略判断配色）
        fills = []
        try:
            drawings = page.get_drawings()
            for d in drawings:
                if d.get("fill"):
                    fills.append(tuple(round(c, 2) for c in d["fill"]))
        except Exception:
            pass
        pages.append({
            "page": i + 1,
            "chars": len(text),
            "text": text[:600],
            "n_fill_colors": len(set(fills)),
            "top_colors": [list(c) for c, _ in Counter(fills).most_common(3)],
            "images": len(page.get_images(full=True)),
        })
    info = {
        "file": str(pdf_path.relative_to(CASES_ROOT)),
        "pages": len(doc),
        "size_mb": round(pdf_path.stat().st_size / 1024 / 1024, 2),
        "page_detail": pages,
    }
    doc.close()
    return info


def main():
    outdir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")
    outdir.mkdir(parents=True, exist_ok=True)
    pdfs = find_ppt_pdfs()
    results = []
    for p in pdfs:
        try:
            r = analyze_one(p)
            results.append(r)
            print(f"[ok] {r['pages']:3d}页  {r['size_mb']:6.2f}MB  {r['file']}")
        except Exception as e:
            print(f"[ERR] {p.name}: {e}")
    (outdir / "ppt_analysis_raw.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    if results:
        counts = [r["pages"] for r in results]
        print(f"案例数: {len(results)}  页数 min={min(counts)} max={max(counts)} 中位={sorted(counts)[len(counts)//2]}")
        for r in results:
            avg = sum(p["chars"] for p in r["page_detail"]) / max(len(r["page_detail"]), 1)
            print(f"  {r['pages']:3d}页 平均每页{avg:5.0f}字  {r['file'][:70]}")


if __name__ == "__main__":
    main()
