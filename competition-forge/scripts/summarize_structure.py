#!/usr/bin/env python3
"""从 OCR 清洗后的计划书文本里提取章节结构，统计各赛道骨架范式。

用法：python summarize_structure.py <ocr目录> <输出md>
"""
import sys
import re
import pathlib
from collections import Counter

# 一级标题：第X部分 / 一、二、 / 第一部分 / 第X章
L1_PAT = re.compile(r"^(第[一二三四五六七八九十]+[部分章]|[一二三四五六七八九十]{1,2}、)\s*(.{2,40})$")
# 二级：1.1 / （一） / 1.2.3
L2_PAT = re.compile(r"^(（[一二三四五六七八九十]+）|\d+\.\d+(\.\d+)?)\s*(.{2,40})$")

WATERMARK_KEYS = ("公众号", "创赛指南", "举报", "盗版", "侵权", "法院传票", "版权所有",
                  "报警立案", "请联系我们", "知乎号", "淘宝")


def is_watermark(s: str) -> bool:
    return any(k in s for k in WATERMARK_KEYS) or len(s) < 4


def extract(path: pathlib.Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    l1, l2 = [], []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or is_watermark(s):
            continue
        # 去掉行尾页码
        s = re.sub(r"[\s\.·]*\d{1,3}$", "", s).strip()
        m1 = L1_PAT.match(s)
        if m1:
            title = m1.group(2).strip()
            if len(title) >= 2 and not title.startswith("xxxx"):
                l1.append(f"{m1.group(1)}{title}")
            continue
        m2 = L2_PAT.match(s)
        if m2:
            title = m2.group(3).strip()
            if len(title) >= 2:
                l2.append(f"{m2.group(1)}{title}")
    # 去重保序
    seen = set()
    l1u = [x for x in l1 if not (x in seen or seen.add(x))]
    seen = set()
    l2u = [x for x in l2 if not (x in seen or seen.add(x))]
    return l1u, l2u


def main():
    ocrdir = pathlib.Path(sys.argv[1])
    outmd = pathlib.Path(sys.argv[2])
    files = sorted(ocrdir.glob("*_clean.txt"))

    sections = []
    for f in files:
        l1, l2 = extract(f)
        sections.append((f.stem, l1, l2))

    lines = ["# 大挑计划书章节结构统计", "", f"样本：{len(files)} 份计划书（OCR 提取）", ""]

    # 一级标题词频
    cnt = Counter()
    for _, l1, _ in sections:
        for h in l1:
            core = re.sub(r"^(第[一二三四五六七八九十]+[部分章]|[一二三四五六七八九十]{1,2}、)\s*", "", h)
            core = re.sub(r"[\s，。、；：]+$", "", core)
            if 2 <= len(core) <= 20:
                cnt[core] += 1

    lines += ["## 一、一级章节高频词（跨案例出现次数）", "", "| 章节 | 出现次数 |", "|---|---|"]
    for k, v in cnt.most_common(40):
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines += ["## 二、逐份结构", ""]
    for name, l1, l2 in sections:
        lines.append(f"### {name}")
        lines.append("")
        if l1:
            lines.append("**一级章节：**")
            for h in l1[:20]:
                lines.append(f"- {h}")
        else:
            lines.append("_（未提取到一级章节，可能 OCR 质量不足或结构为纯段落式）_")
        if l2:
            lines.append("")
            lines.append(f"**二级标题（前 15 条）：**")
            for h in l2[:15]:
                lines.append(f"- {h}")
        lines.append("")

    outmd.write_text("\n".join(lines), encoding="utf-8")
    print(f"写入 {outmd}，样本 {len(files)} 份")

    print("\n一级章节高频词 TOP20:")
    for k, v in cnt.most_common(20):
        print(f"  {v:2d}x  {k}")


if __name__ == "__main__":
    main()
