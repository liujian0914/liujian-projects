#!/usr/bin/env python3
"""批量抽取大挑计划书的结构信息。

策略：
- 有文本层的 PDF → 直接提取
- 扫描件 → 抽页转 PNG，调 Windows 内置 OCR（ocr_page.ps1）

输出：每份计划书的 页数 / 目录页 / 各章节标题 / 方法章节 / 参考文献数

用法：python extract_datiao_proposals.py <输出目录> [--pages N]
"""
import sys
import re
import json
import subprocess
import pathlib

import pymupdf

CASES_ROOT = pathlib.Path(r"C:\Users\hp\Desktop\大挑案例")
OCR_PS1 = pathlib.Path(r"D:\AI\competition-forge\scripts\ocr_page.ps1")


def ocr_image(img_path: pathlib.Path, txt_path: pathlib.Path) -> str:
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(OCR_PS1), "-ImagePath", str(img_path), "-OutPath", str(txt_path)],
        capture_output=True, timeout=120,
    )
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8", errors="replace")
    return ""


def clean_ocr(text: str) -> str:
    """去掉 OCR 在汉字之间插的空格，去掉水印行。"""
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        # 去水印
        if any(k in s for k in ("公众号", "创赛指南", "举报", "盗版", "侵权", "法院传票", "配 套 视 频")):
            continue
        # 汉字之间去空格
        s = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", s)
        s = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[，。、；：？！“”（）《》])", "", s)
        s = re.sub(r"(?<=[，。、；：？！“”（）《》])\s+(?=[\u4e00-\u9fff])", "", s)
        lines.append(s)
    return "\n".join(lines)


HEADING_PAT = re.compile(
    r"^(第[一二三四五六七八九十]+[部分章]|[一二三四五六七八九十]+、|"
    r"\d+\.\d+(\.\d+)?\s*|（[一二三四五六七八九十]+）)"
)


def extract_headings(text: str) -> list[str]:
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if 3 <= len(s) <= 60 and HEADING_PAT.match(s):
            out.append(s)
    return out


def analyze(pdf: pathlib.Path, outdir: pathlib.Path, max_pages: int) -> dict:
    doc = pymupdf.open(pdf)
    n = len(doc)
    raw_text = "".join(pg.get_text() for pg in doc)

    result = {
        "file": str(pdf.relative_to(CASES_ROOT)),
        "pages": n,
        "has_text_layer": len(raw_text.strip()) > 200,
        "text_chars": len(raw_text.strip()),
        "headings": [],
        "methods": [],
        "refs": 0,
        "ocr_pages": 0,
    }

    stem = re.sub(r"[^\w\u4e00-\u9fff]", "_", pdf.stem)[:40]
    pages_text = []

    if result["has_text_layer"]:
        pages_text = [pg.get_text() for pg in doc]
        result["headings"] = extract_headings(raw_text)
    else:
        # 扫描件：抽前 max_pages 页做 OCR（目录与结构通常在前 1/4）
        take = min(max_pages, n)
        # 均匀取页：前 6 页（封面+目录+开头）+ 后面均匀分布
        idxs = list(range(min(6, n)))
        if n > 12:
            step = max(1, n // 10)
            idxs += list(range(6, n, step))[:8]
        idxs = sorted(set(i for i in idxs if i < n))[:max_pages]
        for i in idxs:
            png = outdir / f"{stem}_p{i+1:03d}.png"
            txt = outdir / f"{stem}_p{i+1:03d}.txt"
            if not png.exists():
                pix = doc[i].get_pixmap(dpi=170)
                pix.save(png)
            t = ocr_image(png, txt)
            pages_text.append(clean_ocr(t))
            result["ocr_pages"] += 1
        joined = "\n".join(pages_text)
        result["headings"] = extract_headings(joined)

    joined = "\n".join(pages_text)
    # 研究方法
    methods = []
    for m in ("问卷调查法", "问卷", "访谈法", "访谈", "实地考察", "实地调研", "实地走访",
              "案例分析法", "文献研究法", "文献综述", "比较研究", "定量分析", "定性分析",
              "田野调查", "参与式观察", "SPSS", "描述性统计", "回归分析"):
        if m in joined:
            methods.append(m)
    result["methods"] = methods
    # 参考文献条数（形如 [1] 且含四位年份）
    refs = re.findall(r"\[\d{1,3}\][^\n]{0,200}?(19|20)\d{2}", joined)
    result["refs"] = len(refs)

    # 保存清洗后的文本
    (outdir / f"{stem}_clean.txt").write_text(joined, encoding="utf-8")
    doc.close()
    return result


def main():
    outdir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(".")
    max_pages = 20
    if "--pages" in sys.argv:
        max_pages = int(sys.argv[sys.argv.index("--pages") + 1])
    outdir.mkdir(parents=True, exist_ok=True)

    pdfs = [p for p in CASES_ROOT.rglob("*.pdf")
            if "PPT" not in p.name and "协议" not in p.name]
    results = []
    for p in sorted(pdfs):
        try:
            r = analyze(p, outdir, max_pages)
            results.append(r)
            print(f"[ok] {r['pages']:3d}页 text={r['has_text_layer']} "
                  f"ocr={r['ocr_pages']:2d} 标题={len(r['headings']):2d} 方法={len(r['methods']):2d} {r['file'][:50]}")
        except Exception as e:
            print(f"[ERR] {p.name[:50]}: {e}")

    (outdir / "proposals_analysis.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n完成 {len(results)} 份，结果写入 {outdir/'proposals_analysis.json'}")


if __name__ == "__main__":
    main()
